"""Approved operator recovery for RAW uploaded by the old, untracked PUT path.

Default is read-only preview. Never deletes or overwrites S3/lesson content.
"""
import argparse
import getpass
import hashlib
import json
from pathlib import Path
import re
import sys
import warnings
from datetime import timedelta

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def authorized_operator(db):
    from sqlalchemy import text
    if db.get_bind().dialect.name!="postgresql": raise ValueError("PostgreSQL operator authorization required")
    row=db.execute(text("""SELECT session_user::text AS actor,current_user::text AS effective,
        EXISTS(SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname='learncloud_video_metadata_operator'
        AND pg_catalog.pg_has_role(session_user,r.oid,'MEMBER')) AS allowed""")).mappings().one()
    if not row["allowed"] or row["actor"]!=row["effective"]:
        raise ValueError("Direct DBA-authorized video metadata operator login required")
    return row["actor"]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson-id",type=int,required=True)
    parser.add_argument("--expected-instructor-id",type=int,required=True)
    parser.add_argument("--object-key",required=True)
    parser.add_argument("--operator-db-user",required=True)
    parser.add_argument("--approval-reference",required=True)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args(argv)
    if not sys.stdin.isatty(): raise SystemExit("Trusted interactive terminal required")
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from app.config import settings
    from app.models.lesson import Lesson
    from app.models.section import Section
    from app.models.course import Course
    from app.models.video_pipeline import VideoUpload
    from app.adapters.storage.s3_storage import S3StorageAdapter
    from app.adapters.video.mediaconvert import source_identity
    from app.services.upload_service import UploadService, ALLOWED_VIDEO_TYPES, MAX_VIDEO_SIZE, _utc, ledger_available
    engine=None
    try:
        if args.lesson_id<1 or args.expected_instructor_id<1 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}",args.approval_reference):
            raise ValueError("Exact positive IDs and a safe approval reference are required")
        _,upload_id=source_identity(args.object_key,args.lesson_id)
        url=make_url(settings.DATABASE_URL)
        if url.get_backend_name()!="postgresql": raise ValueError("PostgreSQL required")
        with warnings.catch_warnings():
            warnings.simplefilter("error",getpass.GetPassWarning)
            url=url.set(username=args.operator_db_user,password=getpass.getpass("Authorized operator DB password: "))
        options="-c search_path=public -c lock_timeout=5s -c statement_timeout=30s"
        if not args.apply: options+=" -c default_transaction_read_only=on"
        engine=create_engine(url,hide_parameters=True,connect_args={"connect_timeout":5,"options":options})
        storage=S3StorageAdapter()
        with Session(engine,autoflush=False) as db:
            def candidate(lock=False):
                actor=authorized_operator(db)
                if actor!=args.operator_db_user: raise ValueError("Authenticated DB login mismatch")
                if not ledger_available(db): raise ValueError("Review upload ledger schema before recovery")
                if lock:
                    lesson,course=UploadService._lock(db,args.lesson_id,args.expected_instructor_id)
                else:
                    lesson=db.get(Lesson,args.lesson_id)
                    section=db.get(Section,lesson.section_id) if lesson else None
                    course=db.get(Course,section.course_id) if section else None
                if (lesson is None or course is None or course.instructor_id!=args.expected_instructor_id
                    or course.status!="DRAFT" or lesson.status!="DRAFT" or lesson.retry_count!=0
                    or lesson.raw_video_key or lesson.processed_video_key):
                    raise ValueError("Only an empty, unchanged owned draft lesson may be recovered")
                intents=db.query(VideoUpload).filter_by(lesson_id=lesson.id).all()
                if intents: raise ValueError("Existing upload intents require separate review; nothing will be overwritten")
                metadata=storage.head_video(args.object_key)
                expected_type=ALLOWED_VIDEO_TYPES.get(Path(args.object_key).suffix.lower())
                size=metadata.get("ContentLength")
                modified=metadata.get("LastModified")
                if (not expected_type or metadata.get("ContentType")!=expected_type
                    or not isinstance(size,int) or not 0<size<=MAX_VIDEO_SIZE
                    or not metadata.get("ETag") or modified is None or modified.tzinfo is None):
                    raise ValueError("Existing S3 RAW metadata is not valid")
                return actor,metadata
            actor,preview=candidate()
            print(json.dumps({"mode":"apply" if args.apply else "read-only preview","lesson_id":args.lesson_id,
                "instructor_id":args.expected_instructor_id,"operator":actor,"database":url.database,
                "host":url.host,"port":url.port,"key_sha256":hashlib.sha256(args.object_key.encode()).hexdigest(),
                "bytes":preview["ContentLength"],"approval_reference":args.approval_reference}))
            db.rollback()
            if not args.apply:
                print("No data changed. Review the exact RAW key before --apply.")
                return 0
            if input(f"Type ATTACH {args.lesson_id} after approval: ")!=f"ATTACH {args.lesson_id}":
                raise ValueError("Confirmation mismatch")
            _,current=candidate(lock=True)
            if current["ETag"]!=preview["ETag"]: raise ValueError("S3 object changed since preview")
            modified=_utc(current["LastModified"])
            db.add(VideoUpload(id=upload_id,lesson_id=args.lesson_id,source_key=args.object_key,
                content_type=current["ContentType"],size_bytes=current["ContentLength"],
                created_at=modified.replace(microsecond=0),expires_at=modified+timedelta(seconds=900)))
            db.flush()
            result=UploadService(storage).confirm_upload(db,args.lesson_id,args.expected_instructor_id,upload_id)
            print(json.dumps({"status":"attached","lesson_id":result["lesson_id"],"video_status":result["video_status"],
                              "operator":actor,"approval_reference":args.approval_reference}))
            return 0
    except Exception as exc:
        # Do not expose DSNs, keys, signed URLs or credentials in SDK errors.
        print(f"Recovery refused/failed ({type(exc).__name__}); verify outcome before retrying. No file was deleted.",file=sys.stderr)
        return 1
    finally:
        if engine is not None: engine.dispose()


if __name__=="__main__": sys.exit(main())
