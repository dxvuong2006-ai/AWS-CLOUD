import sys
from pathlib import Path

from fastapi import FastAPI

# app.main may be launched from the backend directory with --app-dir backend.
# Add the repository root before API modules import the sibling ai_pipeline package.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api import quizzes, review, tutor, analytics
from fastapi.middleware.cors import CORSMiddleware
from app.api.courses import router as courses_router
from app.api.lessons import router as lessons_router
from app.api.sections import router as sections_router
from app.api.enrollments import router as enrollments_router
from app.api.uploads import router as uploads_router
from app.api.auth import router as auth_router
from app.api.quizzes import router as quizzes_router
from app.api.review import router as review_router
from app.utils.errors import register_exception_handlers
from app.utils.logging import setup_logging, RequestLoggingMiddleware

setup_logging()
app = FastAPI(
    title="LearnCloud",
    description="Backend API for the LearnCloud learning platform",
    version="0.1.0",
)

# Thêm middleware để ghi log các yêu cầu
app.add_middleware(RequestLoggingMiddleware)

# Đăng ký các handler lỗi
register_exception_handlers(app)

# CORS: Cho phép frontend React gọi API FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(quizzes_router)
app.include_router(courses_router)
app.include_router(quizzes.router)
app.include_router(review.router)
app.include_router(tutor.router)
app.include_router(analytics.router)
app.include_router(sections_router)
app.include_router(lessons_router)
app.include_router(enrollments_router)
app.include_router(uploads_router)
app.include_router(review_router)

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
