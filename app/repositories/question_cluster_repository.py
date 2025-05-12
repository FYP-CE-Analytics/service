from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models.question_cluster import QuestionClusterModel
from app.db.session import get_engine, get_sync_client
from odmantic import AIOEngine
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult
from bson import ObjectId


class QuestionClusterRepository:
    """Repository for managing question clusters using the singleton MongoDB connection"""

    async def create(self, cluster: QuestionClusterModel) -> QuestionClusterModel:
        """
        Create a new question cluster
        
        Args:
            cluster (QuestionClusterModel): The cluster to create
            
        Returns:
            QuestionClusterModel: The created cluster
        """
        engine = get_engine()
        return await engine.save(cluster)

    async def create_many(self, clusters: List[QuestionClusterModel]) -> List[QuestionClusterModel]:
        """
        Create multiple question clusters
        
        Args:
            clusters (List[QuestionClusterModel]): List of clusters to create
            
        Returns:
            List[QuestionClusterModel]: List of created clusters
        """
        engine = get_engine()
        return await engine.save_all(clusters)

    def create_cluster_sync(self, cluster_data: Dict[str, Any]) -> QuestionClusterModel:
        """Synchronous version of create_cluster for use in Celery tasks"""
        sync_client = get_sync_client()
        collection = sync_client["question_cluster"]
        cluster = QuestionClusterModel(**cluster_data)
        inserted_result: InsertOneResult = collection.insert_one(cluster.model_dump(by_alias=True))
        inserted_doc = collection.find_one({"_id": inserted_result.inserted_id})
        if inserted_doc:
            return QuestionClusterModel(**inserted_doc)
        else:
            raise Exception("Failed to retrieve inserted document after insertion")

    async def get_by_id(self, cluster_id: str) -> Optional[QuestionClusterModel]:
        """
        Get a question cluster by its ID
        
        Args:
            cluster_id (str): The ID of the cluster to retrieve
            
        Returns:
            Optional[QuestionClusterModel]: The found cluster or None
        """
        engine = get_engine()
        return await engine.find_one(QuestionClusterModel, QuestionClusterModel.id == cluster_id)

    async def get_by_theme(self, theme: str) -> List[QuestionClusterModel]:
        """
        Get all question clusters with a specific theme
        
        Args:
            theme (str): The theme to search for
            
        Returns:
            List[QuestionClusterModel]: List of clusters with the specified theme
        """
        engine = get_engine()
        return await engine.find(QuestionClusterModel, QuestionClusterModel.theme == theme)

    async def get_by_question_id(self, question_id: str) -> List[QuestionClusterModel]:
        """
        Get all question clusters containing a specific question ID
        
        Args:
            question_id (str): The question ID to search for
            
        Returns:
            List[QuestionClusterModel]: List of clusters containing the question ID
        """
        engine = get_engine()
        return await engine.find(QuestionClusterModel, QuestionClusterModel.question_ids.contains(question_id))

    async def get_clusters_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        unit_id: Optional[str] = None
    ) -> List[QuestionClusterModel]:
        """Get clusters within a date range"""
        engine = get_engine()
        query = {
            "start_date": {"$gte": start_date},
            "end_date": {"$lte": end_date}
        }
        if unit_id:
            query["unit_id"] = unit_id
            
        return await engine.find(QuestionClusterModel, query)

    async def update(self, cluster: QuestionClusterModel) -> QuestionClusterModel:
        """
        Update an existing question cluster
        
        Args:
            cluster (QuestionClusterModel): The cluster to update
            
        Returns:
            QuestionClusterModel: The updated cluster
        """
        engine = get_engine()
        return await engine.save(cluster)

    async def delete(self, cluster_id: str) -> bool:
        """
        Delete a question cluster by its ID
        
        Args:
            cluster_id (str): The ID of the cluster to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        engine = get_engine()
        cluster = await self.get_by_id(cluster_id)
        if cluster:
            await engine.delete(cluster)
            return True
        return False

    async def sync_clusters(self, clusters: List[QuestionClusterModel]) -> Dict[str, Any]:
        """
        Synchronize clusters with the database, updating existing ones and creating new ones
        
        Args:
            clusters (List[QuestionClusterModel]): List of clusters to synchronize
            
        Returns:
            Dict[str, Any]: Statistics about the sync operation
        """
        stats = {
            "created": 0,
            "updated": 0,
            "failed": 0
        }

        for cluster in clusters:
            try:
                existing_clusters = await self.get_by_theme(cluster.theme)
                
                if existing_clusters:
                    existing = existing_clusters[0]
                    existing.question_ids = cluster.question_ids
                    existing.metadata = cluster.metadata
                    await self.update(existing)
                    stats["updated"] += 1
                else:
                    await self.create(cluster)
                    stats["created"] += 1
            except Exception as e:
                stats["failed"] += 1
                print(f"Error syncing cluster {cluster.theme}: {str(e)}")

        return stats

    async def update_cluster(self, cluster_id: str, update_data: Dict[str, Any]) -> Optional[QuestionClusterModel]:
        """
        Update an existing cluster by ID.

        Args:
            cluster_id (str): The ID of the cluster to update
            update_data (Dict[str, Any]): Dictionary containing update data.

        Returns:
            Optional[QuestionClusterModel]: The updated cluster or None if not found.
        """
        engine = get_engine()
        cluster = await engine.find_one(QuestionClusterModel, QuestionClusterModel.id == cluster_id)
        if cluster:
            for key, value in update_data.items():
                if hasattr(cluster, key):
                    setattr(cluster, key, value)
            await engine.save(cluster)
            return cluster
        return None

    def update_cluster_sync(self, cluster_id: str, update_data: Dict[str, Any]) -> Optional[QuestionClusterModel]:
        """
        Synchronous version of update_cluster for use in Celery tasks.

        Args:
            cluster_id (str): The ID of the cluster to update
            update_data (Dict[str, Any]): Dictionary containing update data.

        Returns:
            Optional[QuestionClusterModel]: The updated cluster or None if not found.
        """
        sync_client = get_sync_client()
        collection = sync_client["question_cluster"]

        query_filter = {"_id": cluster_id}

        update_operation = {"$set": {}}
        for key, value in update_data.items():
            if key != "id" and key != "_id":
                update_operation["$set"][key] = value

        if update_operation["$set"]:
            result: UpdateResult = collection.update_one(
                query_filter,
                update_operation
            )

            if result.matched_count > 0:
                updated_doc = collection.find_one(query_filter)
                if updated_doc:
                    return QuestionClusterModel(**updated_doc)

        return None

    async def add_questions_to_cluster(
        self, 
        cluster_id: str, 
        question_ids: List[str],
        transaction_id: str
    ) -> Optional[QuestionClusterModel]:
        """
        Add questions to an existing cluster.

        Args:
            cluster_id (str): The ID of the cluster to update
            question_ids (List[str]): List of question IDs to add
            transaction_id (str): The transaction ID associated with the update

        Returns:
            Optional[QuestionClusterModel]: The updated cluster or None if not found
        """
        engine = get_engine()
        cluster = await engine.find_one(QuestionClusterModel, QuestionClusterModel.id == cluster_id)
        if cluster:
            for q_id in question_ids:
                if q_id not in cluster.question_ids:
                    cluster.question_ids.append(q_id)

            if transaction_id not in cluster.transaction_ids:
                cluster.transaction_ids.append(transaction_id)

            await engine.save(cluster)
        return cluster

    async def get_clusters_by_unit_id(self, unit_id: str) -> List[QuestionClusterModel]:
        """
        Get clusters by unit ID
        
        Args:
            unit_id (str): The ID of the unit
            
        Returns:
            List[QuestionClusterModel]: List of clusters belonging to the unit
        """
        engine = get_engine()
        return await engine.find(QuestionClusterModel, QuestionClusterModel.unit_id == unit_id)

