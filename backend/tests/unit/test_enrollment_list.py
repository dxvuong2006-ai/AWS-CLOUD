import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user


class EnrollmentListApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_current_user] = lambda: _Student()
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_student_course_list_returns_service_shape(self):
        expected = [{
            "course": {
                "id": 7,
                "title": "AWS Fundamentals",
                "description": "Cloud basics",
                "status": "PUBLISHED",
            },
            "status": "NOT_STARTED",
            "progress_percent": 0,
            "resume_lesson_id": 11,
            "unlocked_section_ids": [3],
        }]

        with patch(
            "app.api.enrollments.enrollment_service.list_student_courses",
            return_value=expected,
        ):
            response = self.client.get("/students/me/courses")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_only_students_can_list_enrolled_courses(self):
        app.dependency_overrides[get_current_user] = lambda: _Instructor()
        response = self.client.get("/students/me/courses")
        self.assertEqual(response.status_code, 403)


class _Student:
    id = 42
    role = "STUDENT"


class _Instructor:
    id = 43
    role = "INSTRUCTOR"
