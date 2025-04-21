from sklearn.cluster import KMeans as SKLearnKMeans, HDBSCAN
import numpy as np
from celery_worker import app
from app.services.pinecone_service import pc_service, INDEX_NAME
import pandas as pd
from typing import Dict, List, Any, Optional
from pymongo import MongoClient
from datetime import datetime
from app.core import config


client = MongoClient(config.settings.MONGO_DATABASE_URI)
db = client.get_database(config.settings.MONGO_DATABASE_NAME)


def get_embeddings_from_db(namespace, vector_store):
    """
    Fetch embeddings from the database for a given namespace.
    """
    ids = list(vector_store.list(namespace=namespace)
               )  # get all ids in the namespace

    if not ids:
        print(f"No documents found for namespace: {namespace}")
        return pd.DataFrame()

    embeddings = vector_store.fetch(ids[0], namespace=namespace)
    embeddings_dict = embeddings.vectors
    embeddings = [{"id": vector.id, "embedding": vector.values,
                  "metadata": vector.metadata} for vector in embeddings_dict.values()]
    embeddings_df = pd.DataFrame(embeddings)
    return embeddings_df


@app.task(bind=True, name="cluster_unit_documents")
def cluster_unit_documents(self, unit_id: str, auto_optimize: bool = True,
                           min_cluster_size: int = 5, min_samples: int = 5) -> Dict[str, Any]:
    """
    Celery task to perform HDBSCAN clustering on documents for a specific unit.

    Args:
        unit_id: The ID of the unit (used as namespace)
        auto_optimize: Whether to automatically optimize clustering parameters
        min_cluster_size: Minimum size of clusters for HDBSCAN (used if auto_optimize=False)
        min_samples: Minimum samples parameter for HDBSCAN (used if auto_optimize=False)

    Returns:
        Dictionary with clustering results
    """
    # Update task state to show progress
    self.update_state(state="PROCESSING",
                      meta={"status": "Fetching embeddings", "unit_id": unit_id})

    namespace = str(unit_id)
    vector_store = pc_service.Index(INDEX_NAME)

    # Get embeddings from vector database
    embeddings_df = get_embeddings_from_db(namespace, vector_store)

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
    if auto_optimize:
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
    labels, cluster_stats = perform_hdbscan_clustering(
        embeddings_df,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric=metric
    )

    # Map document IDs to cluster labels (rest of the function remains the same)
    document_clusters = []
    for i, row in embeddings_df.iterrows():
        cluster_label = int(labels[i])
        document_clusters.append({
            "id": row['id'],
            "cluster": cluster_label,
            "title": row.get('metadata', {}).get('content', ''),
            "category": row.get('metadata', {}).get('category', '')
        })

    cluster_record = {
        "unit_id": unit_id,
        "created_at": datetime.now(),
        "num_documents": len(embeddings_df),
        "num_clusters": cluster_stats["num_clusters"],
        "parameters": {
            "auto_optimized": auto_optimize,
            "min_cluster_size": min_cluster_size,
            "min_samples": min_samples,
            "metric": metric
        },
        "document_clusters": document_clusters
    }

    cluster_id = db.clusters.insert_one(cluster_record).inserted_id
    # Return clustering results with parameter info
    return {
        "status": "success",
        "unit_id": unit_id,
        "cluster_id": str(cluster_id),
        "num_documents": len(embeddings_df),
        "num_clusters": cluster_stats["num_clusters"],
        "noise_percentage": cluster_stats["noise_percentage"],
        "parameters": {
            "auto_optimized": auto_optimize,
            "min_cluster_size": min_cluster_size,
            "min_samples": min_samples,
            "metric": metric
        }
    }


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

    return labels, stats


if __name__ == "__main__":
    # Example usage for testing
    unit_id = "22913"  # Replace with your test unit_id
    result = cluster_unit_documents(unit_id)
    print(result)
