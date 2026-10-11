from fastapi import FastAPI
from app.api.courses import router as courses_router

app = FastAPI(
    title="LearnCloud",
    description="Backend API for the LearnCloud learning platform",
    version="0.1.0",
)

app.include_router(courses_router)

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}