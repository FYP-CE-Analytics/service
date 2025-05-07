import uvicorn
from fastapi import FastAPI
from app.api.api_v1.api import api_router
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import init_indexes
from app.schemas import APIKeyTestRequest

import httpx


# Configure FastAPI without trailing slash redirects
app = FastAPI(
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    # Disable automatic redirect
    redirect_slashes=False
)


# Fix CORS - cannot use * with credentials=True
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://ed-summarizer.vercel.app",
        "https://ed-summarizer-gsv0kt57i-cooi123s-projects.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await init_indexes()
    print("Application started and database indexes initialized")


# Fix the typo in the health endpoint
@app.get("/health", tags=["health"])  # Fixed "heath" to "health"
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/v1/proxy/ed-forum/validate-key", tags=["proxy"])
async def validate_ed_forum_key(apiKeyReqiest: APIKeyTestRequest):
    api_key = apiKeyReqiest.apiKey

    # Make request to Ed Forum
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://edstem.org/api/user",
            headers={"Authorization": f"Bearer {api_key}"}
        )

    return {"valid": response.status_code == 200}
# Include your API router
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print("Server started at port", 8000)
