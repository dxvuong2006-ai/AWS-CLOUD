from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


# One source of truth on Windows, containers and Lambda alike. Configure RDS
# credentials/TLS through DATABASE_URL; importing the app never calls AWS SSM.
database_url = settings.DATABASE_URL
if not database_url:
    raise RuntimeError("DATABASE_URL must be configured")

engine_options = {"pool_pre_ping": True, "hide_parameters": True}
if database_url.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options["pool_size"] = 1
    engine_options["max_overflow"] = 1

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def migrate_local_quiz_attempts():
    """Bổ sung schema phục vụ lịch sử checkpoint, giữ nguyên mọi bản ghi."""
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as connection:
        # Khóa ghi trước khi kiểm tra để các tiến trình không thêm cột đồng thời.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            course_columns = {
                row[1] for row in connection.exec_driver_sql(
                    'PRAGMA table_info("courses")'
                )
            }
            if course_columns:
                if "cover_image" not in course_columns:
                    connection.exec_driver_sql(
                        "ALTER TABLE courses ADD COLUMN cover_image TEXT"
                    )
                if "learning_objectives" not in course_columns:
                    connection.exec_driver_sql(
                        "ALTER TABLE courses ADD COLUMN learning_objectives "
                        "JSON NOT NULL DEFAULT '[]' "
                        "CHECK (json_type(learning_objectives) = 'array')"
                    )
            columns = {
                row[1] for row in connection.exec_driver_sql(
                    'PRAGMA table_info("quiz_attempts")'
                )
            }
            if not columns:
                connection.commit()
                return
            if "request_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE quiz_attempts ADD COLUMN request_id VARCHAR(36)"
                )
            if "request_hash" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE quiz_attempts ADD COLUMN request_hash VARCHAR(64)"
                )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_attempts_request "
                "ON quiz_attempts (student_id, quiz_id, request_id)"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
