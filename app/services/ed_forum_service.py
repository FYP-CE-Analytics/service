from edapi import EdAPI, User as EdUser
from edapi.models.course import CourseInfo
from edapi.types.api_types.thread import API_Thread_WithComments
from fastapi import HTTPException
from typing import List, Dict, Any, Optional, TypedDict
import httpx
from datetime import datetime, timedelta
from functools import lru_cache
import json
from edapi.types.api_types.endpoints.threads import API_ListThreads_Response


class EdService:
    # can apply caching
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._client = None
        self._user = None
        self.base_url = "https://edstem.org/api"
        self._thread_cache = {}  # In-memory cache for threads
        self._cache_ttl = timedelta(minutes=5)  # Cache TTL

    @property
    def client(self) -> EdAPI:
        if not self._client:
            if not self.api_key:
                raise ValueError("API key is required")
            self._client = EdAPI(self.api_key)
            print(f"Initializing Ed API client with API key: {self.api_key[:5]}...")
        return self._client

    @property
    def user(self) -> EdUser:
        if not self._user:
            if not self.client:
                raise ValueError("Client not initialized")
            self._user = self.client.get_user_info()
        return self._user

    async def get_user_info(self) -> EdUser:
        """Get user information from Ed"""
        try:
            return self.user
        except Exception as e:
            # Handle Ed API specific errors
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching user info from Ed: {str(e)}"
            )

    async def get_user_active_courses(self) -> List[CourseInfo]:
        """Get user's active courses"""
        try:
            return self.user.get_active_courses()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching active courses: {str(e)}"
            )
    
    def _get_cached_thread(self, thread_id: str) -> Optional[Dict]:
        """Get thread from cache if not expired"""
        if thread_id in self._thread_cache:
            cache_entry = self._thread_cache[thread_id]
            if datetime.now() - cache_entry["timestamp"] < self._cache_ttl:
                return cache_entry["data"]
        return None

    def _cache_thread(self, thread_id: str, thread_data: Dict):
        """Cache thread data with timestamp"""
        self._thread_cache[thread_id] = {
            "data": thread_data,
            "timestamp": datetime.now()
        }

    async def get_thread_by_id(self, thread_id: int):
        """Get thread by ID with caching"""
        try:
            # Check cache first
            cached_thread = self._get_cached_thread(str(thread_id))
            if cached_thread:
                return cached_thread

            # If not in cache, fetch from API
            thread = await self.client.get_thread(thread_id)
            
            # Cache the result
            self._cache_thread(str(thread_id), thread)
            
            return thread
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching thread from Ed: {str(e)}"
            )

    async def get_threads_by_ids(self, thread_ids: List[int]) -> List[API_Thread_WithComments]:
        """Get multiple threads by their IDs with caching"""
        threads = []
        async with httpx.AsyncClient() as client:
            for thread_id in thread_ids:
                # Check cache first
                cached_thread = self._get_cached_thread(str(thread_id))
                if cached_thread:
                    threads.append(cached_thread)
                    continue

                try:
                    response = await client.get(
                        f"{self.base_url}/threads/{thread_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"}
                    )
                    response.raise_for_status()
                    thread_data = response.json()
                    
                    # Cache the result
                    self._cache_thread(str(thread_id), thread_data)
                    
                    threads.append(thread_data)
                except Exception as e:
                    print(f"Error fetching thread {thread_id}: {str(e)}")
                    # Continue with other threads even if one fails
        return threads

    async def get_unanswered_threads(self, course_id: int, limit: int = 100) -> List[API_Thread_WithComments]:
        """Get unanswered threads with pagination and caching"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/courses/{course_id}/threads",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={
                        "sort": "new",
                        "filter": "unanswered",
                        "limit": limit,
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                # Cache each thread
                for thread in data["data"]:
                    self._cache_thread(str(thread["id"]), thread)
                
                return {
                    "data": data["data"],
                    "next": data.get("next"),
                    "previous": data.get("previous")
                }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching unanswered threads: {str(e)}"
            )



    async def post_thread(self, course_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Post a new thread"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/courses/{course_id}/threads",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=params
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error posting thread: {str(e)}"
            )

    async def add_comment(self, thread_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add a comment to a thread"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/threads/{thread_id}/comments",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=params
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error adding comment: {str(e)}"
            )

    async def mark_as_duplicate(self, thread_id: int, duplicate_id: int) -> Dict[str, Any]:
        """Mark a thread as duplicate"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/threads/{thread_id}/mark_duplicate",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"duplicate_id": duplicate_id}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error marking thread as duplicate: {str(e)}"
            )
        
    async def get_all_students_threads(self, course_id: int) -> List[Dict[str, Any]]:
        """Get all threads from a course with pagination, filtered to only include student threads"""
        try:
            threads: List[Dict[str, Any]] = []
            offset = 0
            limit = 100  # Number of threads per page
            
            while True:
                print(f"fetching threads from {offset} to {offset + limit}")
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/courses/{course_id}/threads",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        params={
                            "limit": limit,
                            "offset": offset,
                            "sort": "new"
                        }
                    )
                    
                    # Check if we've reached the end of pages
                    if response.status_code != 200:
                        print(f"Reached end of pages at offset {offset}")
                        break
                        
                    print("fetching threads")
                    response_data: API_ListThreads_Response = response.json()
                    api_threads: List[Dict[str, Any]] = response_data["threads"]
                    
                    # If no threads returned, we've reached the end
                    if not api_threads:
                        print(f"No more threads found at offset {offset}")
                        break
                    
                    # Filter for student threads only
                    student_threads: List[Dict[str, Any]] = [
                        {
                            **thread,
                            "user_role": "student" if thread.get("user") else "anonymous"
                        }
                        for thread in api_threads
                        if thread.get("user") is None or  # Include anonymous threads
                        (thread.get("user") and thread["user"].get("course_role") == "student")
                    ]
                    
                    threads.extend(student_threads)
                    
                    # If we got fewer threads than the limit, we've reached the end
                    if len(api_threads) < limit:
                        print(f"Received fewer threads than limit at offset {offset}")
                        break
                        
                    offset += limit
                    
            print(f"Total threads fetched: {len(threads)}")
            return threads
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching student threads: {str(e)}"
            )

    async def get_course_info(self, unit_id: int) -> CourseInfo:
        """Get course info by unit ID"""
        try:
            course = next((course for course in self.user.courses if course.id == unit_id), None)
            if course:
                return course
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Course not found"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching course info: {str(e)}"
            )


async def get_ed_service(api_key: str = None) -> EdService:
    return EdService(api_key)
