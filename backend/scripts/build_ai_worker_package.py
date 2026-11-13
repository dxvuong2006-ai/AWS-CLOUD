"""Build the K5 worker ZIP offline; never deploy or read AWS credentials."""

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_UNZIPPED_BYTES = 250 * 1024 * 1024
ELF_X86_64 = 62


def _validate_dependencies(dependencies: Path, parser) -> None:
    required = ("psycopg2", "sqlalchemy", "pydantic", "jsonschema", "boto3")
    if not dependencies.is_dir() or any(
        not (dependencies / name).is_dir() for name in required
    ):
        parser.error(
            "Provide dedicated Linux Python 3.12 dependencies for the K5 worker."
        )
    if (dependencies / "pyvenv.cfg").exists():
        parser.error("A virtualenv is not a dependency directory.")
    forbidden_names = {"credentials", ".aws", ".git", ".env"}
    for path in dependencies.rglob("*"):
        lowered = path.name.lower()
        if lowered.startswith(".env") or lowered in forbidden_names:
            parser.error("Dependency folder contains secret/config material.")
        if path.suffix.lower() in {".pyd", ".exe", ".dll", ".dylib"}:
            parser.error(f"Dependency folder contains a non-Linux binary: {path.name}")
        if path.is_file() and ".so" in lowered:
            header = path.read_bytes()[:20]
            if (
                len(header) < 20
                or header[:4] != b"\x7fELF"
                or header[4] != 2
                or header[5] != 1
                or int.from_bytes(header[18:20], "little") != ELF_X86_64
            ):
                parser.error(f"Native dependency is not Linux x86_64 ELF: {path.name}")
            if ".cpython-" in lowered and ".cpython-312-" not in lowered:
                parser.error(f"Native dependency is not for CPython 3.12: {path.name}")


def _write_tree(archive: ZipFile, base: Path, prefix: str) -> None:
    for path in sorted(base.rglob("*")):
        lowered = path.name.lower()
        if lowered.startswith(".env") or lowered in {"credentials", ".aws", ".git"}:
            raise ValueError(f"Refusing secret/config material in package: {path.name}")
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        ):
            archive.write(path, prefix + path.relative_to(base).as_posix())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/ai-worker-k5.zip"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    dependencies = args.dependencies.resolve()
    if dependencies == root:
        parser.error("A repository is not a dependency directory.")
    _validate_dependencies(dependencies, parser)
    output = args.output.resolve()
    if output.exists() and not args.force:
        parser.error("Output already exists; choose a new path or pass --force explicitly.")
    source_roots = (
        dependencies,
        root / "backend/app",
        root / "ai_pipeline",
    )
    if any(output == base or output.is_relative_to(base) for base in source_roots):
        parser.error("Output ZIP must be outside all package source directories.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for base, prefix in (
            (dependencies, ""),
            (root / "backend/app", "app/"),
            (root / "ai_pipeline", "ai_pipeline/"),
        ):
            _write_tree(archive, base, prefix)
        archive.write(root / "infrastructure/lambda/ai_worker_handler.py", "ai_worker_handler.py")
        archive.write(
            root / "infrastructure/lambda/ai_worker_test_handler.py",
            "ai_worker_test_handler.py",
        )
    with ZipFile(output) as archive:
        names = archive.namelist()
        required_members = {
            "ai_worker_handler.py",
            "ai_worker_test_handler.py",
            "app/config.py",
            "app/database.py",
            "app/services/ai_worker_service.py",
            "app/services/video_pipeline_service.py",
            "app/repositories/review_repo.py",
            "app/schemas/review.py",
            "app/adapters/transcription/aws_transcribe.py",
            "app/adapters/transcription/s3_transcript.py",
            "app/adapters/ai/bedrock_ai.py",
            "ai_pipeline/schemas/summary.schema.json",
            "ai_pipeline/schemas/quiz.schema.json",
        }
        missing = required_members - set(names)
        if missing or len(names) != len(set(names)):
            output.unlink(missing_ok=True)
            parser.error("ZIP structure is incomplete or contains duplicate members.")
        uncompressed = sum(item.file_size for item in archive.infolist())
    compressed = output.stat().st_size
    if compressed > MAX_ZIP_BYTES or uncompressed > MAX_UNZIPPED_BYTES:
        output.unlink(missing_ok=True)
        parser.error("Lambda package exceeds AWS ZIP size limits.")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Local K5 package created: {output}")
    print(f"Compressed bytes: {compressed}")
    print(f"Uncompressed bytes: {uncompressed}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
