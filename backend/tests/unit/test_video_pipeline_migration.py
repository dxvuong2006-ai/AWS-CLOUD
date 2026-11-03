"""Static migration/ORM parity. PostgreSQL runtime tests are separate and opt-in."""
from pathlib import Path
import importlib.util
import os
import re
import unittest
from unittest.mock import patch

from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql

from app.models.video_pipeline import VideoPipelineRun, VideoUpload

ROOT = Path(__file__).resolve().parents[3]


class VideoPipelineMigrationTests(unittest.TestCase):
    def test_composite_fk_and_existing_checks_match_orm_and_sql(self):
        migration = (ROOT / "database/migrations/0005_video_pipeline_ledger.sql").read_text()
        for model in (VideoUpload, VideoPipelineRun):
            ddl = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
            for constraint in model.__table__.constraints:
                if constraint.name:
                    self.assertIn(constraint.name, migration)
                    self.assertIn(constraint.name, ddl)
        foreign_key = next(c for c in VideoPipelineRun.__table__.foreign_key_constraints
                           if c.name == "fk_video_run_upload_lesson")
        self.assertEqual(list(foreign_key.column_keys), ["upload_id", "lesson_id"])
        self.assertEqual([e.target_fullname for e in foreign_key.elements], ["video_uploads.id", "video_uploads.lesson_id"])
        index = next(i for i in VideoPipelineRun.__table__.indexes if i.name == "ix_video_pipeline_outbox")
        self.assertIn("WHERE state = 'QUEUED'", str(CreateIndex(index).compile(dialect=postgresql.dialect())))

    def test_version_registration_is_transactional_and_0004_is_not_modified(self):
        migration = (ROOT / "database/migrations/0005_video_pipeline_ledger.sql").read_text()
        normalized = "\n".join(line for line in migration.splitlines() if not line.lstrip().startswith("--"))
        self.assertLess(normalized.index("BEGIN;"), normalized.index("CREATE TABLE public.video_uploads"))
        self.assertLess(normalized.index("INSERT INTO public.schema_migrations"), normalized.index("COMMIT;"))
        self.assertIn("VALUES ('0005', 'Add video upload intents and pipeline ledger with upload/lesson integrity')", normalized)
        self.assertIn("WHERE version = '0004'", normalized)
        self.assertNotRegex(normalized, r"(?im)^\s*(UPDATE|DELETE|TRUNCATE|DROP|ALTER)\s")
        self.assertNotIn("confirmed_at", VideoUpload.__table__.columns)

    def test_preflight_is_read_only_and_handles_absent_tables(self):
        sql = (ROOT / "database/checks/video_pipeline_preflight.sql").read_text()
        self.assertIn("REPEATABLE READ READ ONLY", sql)
        self.assertIn("to_regclass('public.video_uploads')", sql)
        self.assertIn("READY_TO_APPLY", sql)
        self.assertIn("ALREADY_APPLIED", sql)
        self.assertIn("fk_video_run_upload_lesson", sql)
        self.assertNotRegex(sql, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s+\S+\s+SET|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|TRUNCATE\s)")

    def test_postgres_suite_refuses_development_and_remote_targets_before_connecting(self):
        spec = importlib.util.spec_from_file_location("isolated_ledger_guard", ROOT / "backend/tests/integration/test_video_pipeline_ledger_db.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for value in ("", "postgresql://unit:unused@127.0.0.1:5434/learncloud",
                      "postgresql://unit:unused@remote.invalid/learncloud_pipeline_test",
                      "postgresql://unit:unused@127.0.0.1/learncloud_pipeline_test?host=remote.invalid"):
            with patch.dict(os.environ, {"LEARNCLOUD_PIPELINE_TEST_DATABASE_URL": value}), \
                 patch.object(module, "create_engine") as factory:
                with self.assertRaises(RuntimeError):
                    module.VideoPipelinePostgresTests.setUpClass()
                factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
