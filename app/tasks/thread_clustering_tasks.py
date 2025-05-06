from sklearn.cluster import KMeans as SKLearnKMeans, HDBSCAN
import numpy as np
from celery_worker import app
from app.services.pinecone_service import pc_service, INDEX_NAME
import pandas as pd
from typing import Dict, List, Any, Optional
from pymongo import MongoClient
from datetime import datetime
from app.core import config
from app.models.clusters_result import ClusterResultModel, DocumentClusterModel
from app.schemas.tasks.cluster_schema import ClusterRecord, ClusterTaskResult
from app.db.session import MongoDatabase
from app.repositories.task_transaction_repository import TaskTransactionRepository

client = MongoClient(config.settings.MONGO_DATABASE_URI)
db = client.get_database(config.settings.MONGO_DATABASE_NAME)


def get_embeddings_from_db(namespace, vector_store, start_date=None, end_date=None) -> pd.DataFrame:
    """
    Fetch embeddings from the database for a given namespace with optional date filtering.

    Args:
        namespace: The namespace (unit_id) to fetch embeddings from
        vector_store: The vector store client
        start_date: Filter documents after this date (string in ISO format or datetime)
        end_date: Filter documents before this date (string in ISO format or datetime)

    Returns:
        DataFrame with embeddings and metadata
    """
    # Get all ids in the namespace
    ids = list(vector_store.list(namespace=namespace))

    if not ids:
        print(f"No documents found for namespace: {namespace}")
        return pd.DataFrame()

    # Fetch all embeddings from the vector store
    embeddings = vector_store.fetch(ids[0], namespace=namespace)
    embeddings_dict = embeddings.vectors

    # Convert to a list of dictionaries for DataFrame conversion
    embeddings = [{"id": vector.id, "embedding": vector.values,
                  "metadata": vector.metadata} for vector in embeddings_dict.values()]

    # Create DataFrame from all embeddings
    embeddings_df = pd.DataFrame(embeddings)

    if embeddings_df.empty:
        return embeddings_df

    # Apply date filtering if dates are provided
    if start_date or end_date:
        print(f"Filtering documents by date range: {start_date} to {end_date}")

        # Convert string dates to datetime if they're not already
        from datetime import datetime

        # Function to parse date from metadata
        def parse_date(date_str):
            if isinstance(date_str, str):
                # Handle the format in the metadata: "2024-02-13 18:26:19.711432+11:00"
                try:
                    return datetime.fromisoformat(date_str)
                except ValueError:
                    try:
                        # Fallback parsing if the format is different
                        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f%z")
                    except ValueError:
                        print(
                            f"Warning: Could not parse date string: {date_str}")
                        return None
            return date_str  # If it's already a datetime object

        # Convert filter dates
        if start_date and isinstance(start_date, str):
            start_date = parse_date(start_date)
        if end_date and isinstance(end_date, str):
            end_date = parse_date(end_date)

        # Filter the DataFrame based on dates
        filtered_embeddings = []
        filtered_count = 0
        total_count = len(embeddings_df)

        for _, row in embeddings_df.iterrows():
            metadata = row.get("metadata", {})
            doc_date_str = metadata.get("created_at")

            if not doc_date_str:
                continue

            doc_date = parse_date(doc_date_str)
            if not doc_date:
                continue

            # Apply date filters
            if start_date and doc_date < start_date:
                filtered_count += 1
                continue
            if end_date and doc_date > end_date:
                filtered_count += 1
                continue

            filtered_embeddings.append(row)

        # Create new filtered DataFrame
        if filtered_embeddings:
            embeddings_df = pd.DataFrame(filtered_embeddings)
            print(
                f"Date filtering: {filtered_count} documents filtered out, {len(embeddings_df)} documents remain")
        else:
            print("No documents found within the specified date range")
            return pd.DataFrame()

    return embeddings_df


@app.task(bind=True, name="cluster_unit_documents")
def cluster_unit_documents(self, prev_result: Dict, unit_id: str, start_date, end_date, auto_optimize: bool = True,
                           min_cluster_size: int = 2, min_samples: int = 2) -> Dict:
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
    # Check if previous task was successful
    if prev_result.get("status") != "success":
        print(f"Previous task failed: {prev_result.get('message')}")
        return prev_result  # Forward the error

    print(f"Starting clustering task for unit_id: {unit_id}")
    print(f"Previous task result: {prev_result}")

    # Extract data from previous task if needed
    prev_transaction_id = prev_result.get("transaction_id")

    task_transaction_repo = TaskTransactionRepository()
    # Update the task transaction if needed
    task_transaction_repo.update_task_status_sync(
        task_id=prev_transaction_id,
        status="finish clustering"
    )

    # Update task state to show progress
    self.update_state(state="PROCESSING",
                      meta={"status": "Fetching embeddings", "unit_id": unit_id})

    namespace = str(unit_id)
    vector_store = pc_service.Index(INDEX_NAME)

    # Get embeddings from vector database
    embeddings_df = get_embeddings_from_db(
        namespace, vector_store, start_date, end_date)

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
    if auto_optimize and len(embeddings_df) > 10:
        # self.update_state(state="PROCESSING",
        #                   meta={"status": "Optimizing clustering parameters", "unit_id": unit_id})
        min_cluster_size, min_samples, metric = optimize_hdbscan_parameters(
            embeddings_df)
    else:
        metric = 'cosine'  # Default to cosine for text embeddings

    # Update task state
    self.update_state(state="PROCESSING",
                      meta={"status": f"Performing clustering with min_cluster_size={min_cluster_size}, min_samples={min_samples}",
                            "unit_id": unit_id})

    # Perform HDBSCAN clustering with the determined parameters
    core_docs, cluster_stats = perform_hdbscan_clustering(
        embeddings_df,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric=metric
    )

    # if core_docs is empty then just use the first 10 documents
    if not core_docs:
        core_docs = {str(i): {
            'id': doc.get('id'),
            'probability': float(doc.get('probability', 0)),
            'metadata': doc.get('metadata', {})
        } for i, doc in enumerate(embeddings_df.head(10).to_dict(orient='records'))}

    print(f"Core documents: {core_docs}")

    cluster_record = ClusterRecord(** {
        "unit_id": unit_id,
        "created_at": datetime.now(),
        "num_documents": len(embeddings_df),
        "num_clusters": cluster_stats["num_clusters"],
        "parameters": {
            "min_cluster_size": min_cluster_size,
            "min_samples": min_samples,
            "metric": metric
        },
        "core_docs": list(core_docs.values()),
    }
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

    return ClusterTaskResult(
        status="success",
        message="Clustering completed successfully",
        result=cluster_record,
        transaction_id=prev_transaction_id
    ).model_dump()


def optimize_hdbscan_parameters(df: pd.DataFrame) -> tuple:
    """
    Find optimal HDBSCAN parameters through grid search

    Returns:
        tuple: (best_min_cluster_size, best_min_samples, best_metric)
    """
    embeddings_array = np.stack(df['embedding'].values)

    # Parameter grid
    min_cluster_sizes = [2, 3, 5, 7, 10]
    min_samples_params = [1, 2, 3, 5, 8]
    metrics = ['euclidean', 'cosine']

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
                    clusterer = HDBSCAN(
                        min_cluster_size=min_cluster_size,
                        min_samples=min_samples,
                        metric=metric,
                        cluster_selection_method='eom'
                    )
                    clusterer.fit(embeddings_array)
                    labels = clusterer.labels_

                    # Scoring: We want to maximize clusters while minimizing noise
                    num_clusters = len(set(labels)) - \
                        (1 if -1 in labels else 0)
                    noise_percentage = (labels == -1).sum() / \
                        len(labels) if -1 in labels else 0

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
                    print(
                        f"Error with parameters (mcs={min_cluster_size}, ms={min_samples}, metric={metric}): {e}")

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

    return best_params


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
    embeddings_array = np.stack(df['embedding'].values)

    # Initialize and fit HDBSCAN
    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric=metric,  # Consider 'cosine' for text embeddings
        cluster_selection_method='eom'  # Excess of Mass - usually better for text
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

    return core_docs, stats


if __name__ == "__main__":
    # Example usage for testing
    unit_id = "22913"  # Replace with your test unit_id
    result = cluster_unit_documents(unit_id)
    print(result)
