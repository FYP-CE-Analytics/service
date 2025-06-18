from sklearn.cluster import HDBSCAN
import numpy as np
from celery_worker import app
from app.services.pinecone_service import pc_service, INDEX_NAME
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime
from app.core import config
from app.schemas.tasks.cluster_schema import ClusterRecord, ClusterTaskResult, ClusteringParameters, CoreDocument
from app.db.session import get_sync_client
from app.repositories.task_transaction_repository import TaskTransactionRepository
from app.schemas.tasks.task_status import TaskStatus
import gc
import psutil
import os

db = get_sync_client()


def get_memory_usage():
    """Get current memory usage of the process in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def get_embeddings_from_db(namespace, vector_store, ids: List[str]) -> pd.DataFrame:
    """
    Fetch embeddings from the database for a given namespace with optional date filtering.

    Args:
        namespace: The namespace (unit_id) to fetch embeddings from
        vector_store: The vector store client
        start_date: Filter documents after this date (string in ISO format or datetime)
        end_date: Filter documents before this date (string in ISO format or datetime)

    Returns:
        DataFrame with embeddings and metadata

    to do: collection take time to load so need to wait for it to load
    """
    # Get all ids in the namespace

    if not ids:
        print(f"No documents found for namespace: {namespace}")
        return pd.DataFrame()

    # Fetch all embeddings from the vector store
    print(f"Fetching embeddings for {ids} documents")
    embeddings = vector_store.fetch(ids, namespace=namespace)
    embeddings_dict = embeddings.vectors

    # Convert to a list of dictionaries for DataFrame conversion
    embeddings = [{"id": vector.id, "embedding": vector.values,
                  "metadata": vector.metadata} for vector in embeddings_dict.values()]

    # Create DataFrame from all embeddings
    embeddings_df = pd.DataFrame(embeddings)

    return embeddings_df


@app.task(bind=True, name="cluster_unit_documents")
def cluster_unit_documents(self, prev_req: Dict, unit_id: str, auto_optimize: bool = True,
                           min_cluster_size: int = 2, min_samples: int = 2, **kwargs) -> Dict:
    """
    Celery task to perform HDBSCAN clustering on documents for a specific unit.
    Gets the embeddings from vector database - from previous task

    Args:
        prev_result: Result from the previous task in the chain
        unit_id: The ID of the unit (used as namespace)
        auto_optimize: Whether to automatically optimize clustering parameters
        min_cluster_size: Minimum size of clusters for HDBSCAN
        min_samples: Minimum samples parameter for HDBSCAN
    """
    print("input parameters: ", prev_req, unit_id, auto_optimize, min_cluster_size, min_samples)
    try:
        # Check if previous task was successful
        if prev_req.get("status") != "success":
            print(f"Previous task failed: {prev_req.get('message')}")
            return prev_req  # Forward the error

        print(f"Starting clustering task for unit_id: {unit_id}")
        print(f"Previous task result: {prev_req}")

        # Extract data from previous task
        prev_transaction_id = prev_req.get("transaction_id")
        thread_ids = prev_req.get("result").get("thread_ids")
        task_transaction_repo = TaskTransactionRepository()
        
        # Update the task transaction 
        task_transaction_repo.update_task_status_sync(
            task_id=prev_transaction_id,
            status=TaskStatus.RUNNING_CLUSTERING
        )

        # If we have less than 5 threads, return them directly without clustering
        if len(thread_ids) < 5:
            namespace = str(unit_id)
            vector_store = pc_service.Index(INDEX_NAME)
            
            # Get embeddings from vector database
            embeddings_df = get_embeddings_from_db(namespace, vector_store, thread_ids)
            
            if embeddings_df.empty:
                return {
                    "status": "error",
                    "message": f"No documents found for unit_id: {unit_id}",
                    "unit_id": unit_id
                }
                
            # Create core docs directly from the embeddings
            core_docs = {str(i): {
                'id': doc.get('id'),
                'probability': 1.0,  # Set probability to 1 since we're not clustering
                'metadata': doc.get('metadata', {})
            } for i, doc in enumerate(embeddings_df.to_dict(orient='records'))}
            
            # Create proper CoreDocument objects
            core_docs_list = [
                CoreDocument(
                    id=doc['id'],
                    probability=doc['probability'],
                    metadata=doc['metadata']
                ) for doc in core_docs.values()
            ]
            
            # Create proper ClusteringParameters object
            clustering_params = ClusteringParameters(
                min_cluster_size=1,
                min_samples=len(core_docs),
                metric="cosine"
            )
            
            cluster_record = ClusterRecord(
                unit_id=unit_id,
                created_at=datetime.now(),
                num_documents=len(embeddings_df),
                num_clusters=len(core_docs),
                parameters=clustering_params,
                core_docs=core_docs_list
            )
            
            # Save to database
            cluster_id = db.clusters.insert_one(cluster_record.model_dump()).inserted_id
            if not cluster_id:
                return {
                    "status": "error",
                    "message": "Failed to save clustering results to database",
                    "unit_id": unit_id
                }
                
            cluster_record.cluster_id = str(cluster_id)
            
            # Update task status to completed
            task_transaction_repo.update_task_status_sync(
                task_id=prev_transaction_id,
                status=TaskStatus.COMPLETED
            )
            
            return ClusterTaskResult(
                status="success",
                message="Retrieved questions directly (no clustering needed)",
                result=cluster_record,
                transaction_id=prev_transaction_id
            ).model_dump()

        # Update task state to show progress
        self.update_state(state="PROCESSING",
                          meta={"status": "Fetching embeddings", "unit_id": unit_id})

        namespace = str(unit_id)
        vector_store = pc_service.Index(INDEX_NAME)

        # Get embeddings from vector database
        embeddings_df = get_embeddings_from_db(
            namespace, vector_store, thread_ids)

        if embeddings_df.empty:
            return {
                "status": "error",
                "message": f"No documents found for unit_id: {unit_id}",
                "unit_id": unit_id
            }

        # Update task state for parameter selection
        self.update_state(state="PROCESSING",
                          meta={"status": "Determining optimal parameters" if auto_optimize else "Using provided parameters",
                                "unit_id": unit_id})

        # Determine parameters - either auto-optimize or use provided values
        if auto_optimize and len(embeddings_df) >=5:
            try:
                min_cluster_size, min_samples, metric = optimize_hdbscan_parameters(
                    embeddings_df)
            except Exception as e:
                print(f"Error during parameter optimization: {e}")
                # Fall back to default parameters
                min_cluster_size = 5
                min_samples = 5
                metric = 'cosine'
        else:
            metric = 'cosine'  # Default to cosine for text embeddings

        # Update task state
        self.update_state(state="PROCESSING",
                          meta={"status": f"Performing clustering with min_cluster_size={min_cluster_size}, min_samples={min_samples}",
                                "unit_id": unit_id})

        try:
            # Perform HDBSCAN clustering with the determined parameters
            core_docs, cluster_stats = perform_hdbscan_clustering(
                embeddings_df,
                min_cluster_size=min_cluster_size,
                min_samples=min_samples,
                metric=metric
            )
        except Exception as e:
            print(f"Error during clustering: {e}")
            # If clustering fails, use the first 10 documents as core docs
            core_docs = {str(i): {
                'id': doc.get('id'),
                'probability': 1.0,
                'metadata': doc.get('metadata', {})
            } for i, doc in enumerate(embeddings_df.head(10).to_dict(orient='records'))}
            cluster_stats = {
                "num_clusters": len(core_docs),
                "noise_percentage": 0.0,
                "cluster_distribution": {str(i): 1 for i in range(len(core_docs))}
            }

        print(f"Core documents: {core_docs}")
        print(f"min cluster size: {min_cluster_size}")
        print(f"min samples: {min_samples}")
        print(f"metric: {metric}")
        clustering_params = ClusteringParameters(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric=metric
        )
        core_docs_list = [
            CoreDocument(
                id=doc['id'],
                probability=doc['probability'],
                metadata=doc['metadata']
            ) for doc in core_docs.values()
        ]
        cluster_record = ClusterRecord(
            unit_id=unit_id,
            created_at=datetime.now(),
            num_documents=len(embeddings_df),
            num_clusters=cluster_stats["num_clusters"],
            parameters=clustering_params,
            core_docs=core_docs_list,
        )

        # handle if fail
        cluster_id = db.clusters.insert_one(
            cluster_record.model_dump()).inserted_id
        if not cluster_id:
            return {
                "status": "error",
                "message": "Failed to save clustering results to database",
                "unit_id": unit_id
            }

        cluster_record.cluster_id = str(cluster_id)

        # Update task status to completed
        task_transaction_repo.update_task_status_sync(
            task_id=prev_transaction_id,
            status=TaskStatus.COMPLETED
        )

        return ClusterTaskResult(
            status="success",
            message="Clustering completed successfully",
            result=cluster_record,
            transaction_id=prev_transaction_id
        ).model_dump()
        
    except Exception as e:
        print(f"Unexpected error in cluster_unit_documents: {e}")
        # Update task status to failed
        if 'prev_transaction_id' in locals():
            task_transaction_repo.update_task_status_sync(
                task_id=prev_transaction_id,
                status=TaskStatus.FAILURE
            )
        return {
            "status": "error",
            "message": f"Unexpected error during clustering: {str(e)}",
            "unit_id": unit_id
        }


def optimize_hdbscan_parameters(df: pd.DataFrame) -> tuple:
    """
    Find optimal HDBSCAN parameters through grid search

    Returns:
        tuple: (best_min_cluster_size, best_min_samples, best_metric)
    """
    try:
        embeddings_array = np.stack(df['embedding'].values)
        
        # Check memory usage before starting
        initial_memory = get_memory_usage()
        print(f"Initial memory usage: {initial_memory:.2f} MB")
        
        if initial_memory > 1000:  # If using more than 1GB
            print("High memory usage detected, using conservative parameters")
            return 5, 5, 'cosine'

        # Parameter grid - reduced to minimize memory usage
        min_cluster_sizes = [2, 5, 10]
        min_samples_params = [2, 5]
        metrics = ['cosine']  # Only use cosine to reduce memory usage

        best_score = -1
        best_params = (5, 5, 'cosine')  # Default

        print("Optimizing HDBSCAN parameters...")
        print(f"Dataset size: {len(embeddings_array)} documents")

        results = []

        # Grid search
        for metric in metrics:
            for min_cluster_size in min_cluster_sizes:
                for min_samples in min_samples_params:
                    # Skip invalid combinations
                    if min_samples > min_cluster_size:
                        continue

                    try:
                        # Force garbage collection before each iteration
                        gc.collect()
                        
                        clusterer = HDBSCAN(
                            min_cluster_size=min_cluster_size,
                            min_samples=min_samples,
                            metric=metric,
                            cluster_selection_method='eom',
                        )
                        clusterer.fit(embeddings_array)
                        labels = clusterer.labels_

                        # Scoring: We want to maximize clusters while minimizing noise
                        num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
                        noise_percentage = (labels == -1).sum() / len(labels) if -1 in labels else 0

                        # Skip if all points are noise or all in one cluster
                        if num_clusters <= 1:
                            score = -1
                        else:
                            # Scoring formula: balance between number of clusters and low noise
                            score = num_clusters * (1 - noise_percentage)

                        results.append({
                            'min_cluster_size': min_cluster_size,
                            'min_samples': min_samples,
                            'metric': metric,
                            'num_clusters': num_clusters,
                            'noise_percentage': noise_percentage,
                            'score': score
                        })

                        print(f"min_cluster_size={min_cluster_size}, min_samples={min_samples}, "
                              f"metric={metric}: clusters={num_clusters}, noise={noise_percentage:.2%}, score={score:.3f}")

                        if score > best_score:
                            best_score = score
                            best_params = (min_cluster_size, min_samples, metric)

                    except Exception as e:
                        print(f"Error with parameters (mcs={min_cluster_size}, ms={min_samples}, metric={metric}): {e}")
                        continue

        # Sort and print top 3 parameter combinations
        results_df = pd.DataFrame(results)
        if not results_df.empty:
            top_results = results_df.sort_values('score', ascending=False).head(3)
            print("\nTop 3 parameter combinations:")
            for i, row in enumerate(top_results.itertuples(), 1):
                print(f"{i}. min_cluster_size={row.min_cluster_size}, min_samples={row.min_samples}, "
                      f"metric={row.metric}: clusters={row.num_clusters}, "
                      f"noise={row.noise_percentage:.2%}, score={row.score:.3f}")

        print(f"\nSelected parameters: min_cluster_size={best_params[0]}, "
              f"min_samples={best_params[1]}, metric={best_params[2]}")

        # Force garbage collection after optimization
        gc.collect()
        
        return best_params
        
    except Exception as e:
        print(f"Error in optimize_hdbscan_parameters: {e}")
        return 5, 5, 'cosine'  # Return safe default parameters


def perform_hdbscan_clustering(df: pd.DataFrame, min_cluster_size: int = 5, min_samples: int = 5, metric: str = 'cosine') -> tuple:
    """
    Perform HDBSCAN clustering on document embeddings.

    Args:
        df: DataFrame with 'embedding' column
        min_cluster_size: Minimum size of clusters
        min_samples: Core point definition

    Returns:
        Tuple of (labels, statistics_dict)
    """
    try:
        # Check memory usage before starting
        initial_memory = get_memory_usage()
        print(f"Initial memory usage before clustering: {initial_memory:.2f} MB")
        
        if initial_memory > 1000:  # If using more than 1GB
            raise MemoryError("High memory usage detected before clustering")
            
        embeddings_array = np.stack(df['embedding'].values)

        # Initialize and fit HDBSCAN with memory management
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric=metric,
            cluster_selection_method='eom',
        )

        clusterer.fit(embeddings_array)
        labels = clusterer.labels_
        probabilities = clusterer.probabilities_

        # Calculate cluster statistics
        unique_labels, counts = np.unique(labels, return_counts=True)
        cluster_distribution = {str(label): int(count)
                              for label, count in zip(unique_labels, counts)}

        num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        noise_percentage = float((labels == -1).sum() /
                               len(labels)) if -1 in labels else 0.0

        stats = {
            "num_clusters": num_clusters,
            "noise_percentage": noise_percentage,
            "cluster_distribution": cluster_distribution
        }

        # Print summary for logging
        print(f"HDBSCAN found {num_clusters} clusters")
        print(
            f"Number of noise points: {int(noise_percentage * len(labels))} ({noise_percentage:.2%})")

        # Add cluster labels and probabilities to the DataFrame
        df = df.copy()  # Create a copy to avoid modifying original
        df['cluster'] = labels
        df['probability'] = probabilities

        # Only keep relevant columns for the result
        core_docs = {}

        # Find documents with maximum probability for each cluster
        for cluster_label in set(labels):
            if cluster_label == -1:  # Skip noise
                continue

            # Get documents in this cluster
            cluster_docs = df[df['cluster'] == cluster_label]

            # Get the document with highest probability
            top_doc = cluster_docs.loc[cluster_docs['probability'].idxmax()]

            # Add to core docs with only relevant fields
            core_docs[str(cluster_label)] = {
                'id': top_doc['id'],
                'probability': float(top_doc['probability']),
                'metadata': top_doc['metadata'],
            }

        # Force garbage collection after clustering
        gc.collect()
        
        return core_docs, stats
        
    except Exception as e:
        print(f"Error in perform_hdbscan_clustering: {e}")
        raise  # Re-raise to be caught by the caller


if __name__ == "__main__":
    # Example usage for testing
    unit_id = "22913"  # Replace with your test unit_id
    result = cluster_unit_documents(unit_id)
    print(result)
