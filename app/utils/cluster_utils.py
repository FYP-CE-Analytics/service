from typing import List, Dict, Any
from app.models.question_cluster import QuestionClusterModel
from app.db.session import get_sync_client
from datetime import datetime


def create_question_clusters(data: Dict[str, Any], unit_id: str, transaction_id: str, start_date: str, end_date: str, weeks: List[str]) -> List[QuestionClusterModel]:
    """
    Convert the JSON structure into QuestionClusterModel instances, handling existing clusters
    
    Args:
        data (Dict[str, Any]): The input data containing themes and question IDs
        unit_id (str): The unit ID
        transaction_id (str): The transaction ID
        start_date (str): Start date of the analysis period
        end_date (str): End date of the analysis period
        weeks (List[str]): List of week numbers this analysis covers
        
    Returns:
        List[QuestionClusterModel]: List of created or updated question clusters
    """
    clusters = []
    sync_client = get_sync_client()
    collection = sync_client["question_cluster"]
    
    for cluster_data in data.get("questions", []):
        print("cluster_data", cluster_data)
        # Check if a cluster with the same theme exists for this unit and date range
        existing_cluster = collection.find_one({
            "theme": cluster_data["theme"],
            "unit_id": unit_id,
            "weekStart": start_date,
            "weekEnd": end_date
        })
        
        if existing_cluster:
            # Convert existing document to model
            existing = QuestionClusterModel(**existing_cluster)
            
            # Append new question IDs if they don't exist
            new_question_ids = [qid for qid in cluster_data["questionIds"] 
                              if qid not in existing.question_ids]
            existing.question_ids.extend(new_question_ids)
            
            # Append transaction ID if it doesn't exist
            if transaction_id not in existing.transaction_ids:
                existing.transaction_ids.append(transaction_id)
            
            # Update summary if provided in new data
            if cluster_data.get("summary"):
                existing.summary = cluster_data["summary"]
            
            # Update metadata
            existing.metadata.update({
                "source": "analysis",
                "last_updated": datetime.now().isoformat()
            })
            
            clusters.append(existing)
        else:
            # Create new cluster
            cluster = QuestionClusterModel(
                theme=cluster_data["theme"],
                question_ids=cluster_data["questionIds"],
                unit_id=unit_id,
                transaction_ids=[transaction_id],
                weekStart=start_date,
                weekEnd=end_date,
                weeks=weeks,
                summary=cluster_data.get("summary", ""),
                metadata={
                    "source": "analysis",
                    "created_at": datetime.now().isoformat()
                }
            )
            clusters.append(cluster)
    
    return clusters


def create_cluster_from_dict(cluster_data: Dict[str, Any]) -> QuestionClusterModel:
    """
    Create a single QuestionClusterModel instance from a dictionary
    
    Args:
        cluster_data (Dict[str, Any]): Dictionary containing cluster data
        
    Returns:
        QuestionClusterModel: Created question cluster
    """
    return QuestionClusterModel(
        theme=cluster_data["theme"],
        question_ids=cluster_data["questionIds"],
        metadata={
            "source": "analysis",
            "created_at": datetime.now().isoformat()
        }
    ) 