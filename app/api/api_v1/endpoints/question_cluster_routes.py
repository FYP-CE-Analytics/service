from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from datetime import datetime
from app.repositories.question_cluster_repository import QuestionClusterRepository
from app.repositories.task_transaction_repository import TaskTransactionRepository
from app.services.ed_forum_service import get_ed_service
from app.schemas.crewai_faq_service_schema import QuestionClusterSchema
from app.utils.shared import parse_date

router = APIRouter()
# cluster_repo = QuestionClusterRepository()
task_repo = TaskTransactionRepository()


# @router.get("/clusters", response_model=List[Dict[str, Any]])
# async def get_clusters(
#     start_date: str,
#     end_date: str,
#     unit_id: str = None,
#     ed_service = Depends(get_ed_service)
# ):
#     """
#     Get question clusters within a date range, grouped by week.
#     Each cluster will include thread details from Ed.
#     """
#     try:
#         # Parse dates
#         start = parse_date(start_date)
#         end = parse_date(end_date)

#         # Get clusters from repository
#         clusters = await cluster_repo.get_clusters_by_date_range(start, end, unit_id)

#         # Group clusters by week (start_date and end_date)
#         grouped_clusters = {}
#         for cluster in clusters:
#             key = (cluster.start_date, cluster.end_date)
#             if key not in grouped_clusters:
#                 grouped_clusters[key] = []
#             grouped_clusters[key].append(cluster)

#         # Process each group to get thread details
#         result = []
#         for (week_start, week_end), week_clusters in grouped_clusters.items():
#             # Collect all question IDs from clusters in this week
#             all_question_ids = []
#             for cluster in week_clusters:
#                 all_question_ids.extend(cluster.question_ids)

#             # Get thread details from Ed
#             threads = await ed_service.get_threads_by_ids(all_question_ids)

#             # Create thread lookup dictionary
#             thread_lookup = {str(thread["id"]): thread for thread in threads}

#             # Process each cluster in the week
#             week_result = {
#                 "week_start": week_start,
#                 "week_end": week_end,
#                 "clusters": []
#             }

#             for cluster in week_clusters:
#                 cluster_data = {
#                     "theme": cluster.theme,
#                     "questions": []
#                 }

#                 # Add thread details for each question
#                 for qid in cluster.question_ids:
#                     if qid in thread_lookup:
#                         thread = thread_lookup[qid]
#                         cluster_data["questions"].append({
#                             "id": qid,
#                             "title": thread.get("title", ""),
#                             "content": thread.get("content", ""),
#                             "flags": cluster.flags.get(qid, {})
#                         })

#                 week_result["clusters"].append(cluster_data)

#             result.append(week_result)

#         return result

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post("/clusters/process-transaction/{transaction_id}")
# async def process_transaction_clusters(
#     transaction_id: str
# ):
#     """
#     Process a completed transaction and create/update question clusters.
#     This should be called after a transaction is completed.
#     """
#     try:
#         # Get transaction details
#         transaction = await task_repo.get_task_by_id(transaction_id)
#         if not transaction or transaction.status != "completed":
#             raise HTTPException(
#                 status_code=400,
#                 detail="Transaction not found or not completed"
#             )

#         # Get result from transaction
#         result = transaction.result
#         if not result or "questions" not in result:
#             raise HTTPException(
#                 status_code=400,
#                 detail="No question clusters found in transaction result"
#             )

#         # Process each cluster from the transaction
#         for cluster_data in result["questions"]:
#             # Create or update cluster
#             cluster = await cluster_repo.create_cluster({
#                 "theme": cluster_data["theme"],
#                 "start_date": parse_date(transaction.input.get("start_date")),
#                 "end_date": parse_date(transaction.input.get("end_date")),
#                 "unit_id": transaction.unit_id,
#                 "question_ids": cluster_data["questionIds"],
#                 "transaction_ids": [transaction_id]
#             })

#             # Get thread details from Ed
#             threads = await ed_service.get_threads_by_ids(cluster_data["questionIds"])
            
#             # Update cluster with thread details
#             await cluster_repo.update_cluster(
#                 str(cluster.id),
#                 {
#                     "questions": [
#                         {
#                             "id": str(thread["id"]),
#                             "title": thread.get("title", ""),
#                             "content": thread.get("content", "")
#                         }
#                         for thread in threads
#                     ]
#                 }
#             )

#         return {"status": "success", "message": "Transaction processed successfully"}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e)) 