import uvicorn
from fastapi import FastAPI
from app.api.api_v1.api import api_router
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import init_indexes


app = FastAPI(swagger_ui_parameters={"defaultModelsExpandDepth": -1})
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
                   "https://ed-summarizer.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers

)


@app.on_event("startup")
async def startup_event():
    # This will be called when the FastAPI application starts
    await init_indexes()
    print("Application started and database indexes initialized")


app.include_router(api_router, prefix="/api/v1")


@app.get("/heath", tags=["health"])
async def health():
    """
    Health check endpoint.
    """
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print("Server started at port", 8000)
