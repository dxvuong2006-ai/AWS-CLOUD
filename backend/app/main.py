from fastapi import FastAPI
from app.api.courses import router as courses_router
from app.api.lessons import router as lessons_router
from app.api.sections import router as sections_router
from app.api.enrollments import router as enrollments_router
from app.api.uploads import router as uploads_router

app = FastAPI(
    title="LearnCloud",
    description="Backend API for the LearnCloud learning platform",
    version="0.1.0",
)

app.include_router(courses_router)
app.include_router(sections_router)
app.include_router(lessons_router)
app.include_router(enrollments_router)
app.include_router(uploads_router)

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}