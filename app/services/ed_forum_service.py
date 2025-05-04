from edapi import EdAPI, User as EdUser
from fastapi import HTTPException


class EdService:
    # can apply caching
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._client = None
        self.user = None

    @property
    def client(self) -> EdAPI:
        if not self._client:
            if not self.api_key:
                raise ValueError("API key is required")
            self._client = EdAPI(self.api_key)
            print(
                f"Initializing Ed API client with API key: {self.api_key[:5]}...")

        return self._client

    async def get_user_info(self) -> EdUser:
        """Get user information from Ed"""
        if self.user:
            return self.user
        try:
            self.user = self.client.get_user_info()
            return self.user
        except Exception as e:
            # Handle Ed API specific errors
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching user info from Ed: {str(e)}"
            )

    async def get_user_active_courses(self) -> list:
        """Get user's active courses"""
        user = await self.get_user_info()

        return user.get_active_courses()


async def get_ed_service(api_key: str = None) -> EdService:
    return EdService(api_key)
