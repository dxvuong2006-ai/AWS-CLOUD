
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


DB_PASSWORD_PARAMETER_NAME = "/learncloud/db/password"


def get_lambda_db_password() -> str:
    password = os.getenv("DB_PASSWORD")
    if password:
        return password

    parameter_name = os.getenv("DB_PASSWORD_PARAMETER_NAME", DB_PASSWORD_PARAMETER_NAME)
    try:
        response = boto3.client(
            "ssm",
            region_name=os.getenv("AWS_REGION", "ap-southeast-1"),
        ).get_parameter(Name=parameter_name, WithDecryption=True)
        password = response.get("Parameter", {}).get("Value")
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(
            "Unable to read the RDS password from SSM Parameter Store"
        ) from exc

    if not password:
        raise RuntimeError(
            "SSM Parameter Store returned an empty RDS password"
        )
    return password


if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    database_url = URL.create(
        drivername="postgresql+pg8000",
        username=os.environ["DB_USER"],
        password=get_lambda_db_password(),
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
    )
else:
    database_url = settings.DATABASE_URL

engine_options = {"pool_pre_ping": True}
if isinstance(database_url, URL):
    is_sqlite = database_url.get_backend_name() == "sqlite"
else:
    is_sqlite = str(database_url).startswith("sqlite:")

if is_sqlite:
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options["pool_size"] = 1
    engine_options["max_overflow"] = 1

engine = create_engine(database_url, **engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

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
