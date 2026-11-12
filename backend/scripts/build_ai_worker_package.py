"""Build the K5 worker ZIP offline; never deploy or read AWS credentials."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/ai-worker-k5.zip"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    dependencies = args.dependencies.resolve()
    required = ("psycopg2", "sqlalchemy", "pydantic", "jsonschema", "boto3")
    if not dependencies.is_dir() or any(not (dependencies / name).is_dir() for name in required):
        parser.error("Provide dedicated Linux Python 3.12 dependencies for the K5 worker.")
    if dependencies == root or (dependencies / "pyvenv.cfg").exists():
        parser.error("A repository or virtualenv is not a dependency directory.")
    for path in dependencies.rglob("*"):
        if path.name.startswith(".env") or path.name in {"credentials", ".aws", ".git"}:
            parser.error("Dependency folder contains secret/config material.")
        if path.suffix.lower() in {".pyd", ".exe"}:
            parser.error("Dependency folder contains a Windows binary.")
    output = args.output.resolve()
    if output.exists() and not args.force:
        parser.error("Output already exists; choose a new path or pass --force explicitly.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for base, prefix in (
            (dependencies, ""),
            (root / "backend/app", "app/"),
            (root / "ai_pipeline", "ai_pipeline/"),
        ):
            for path in sorted(base.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    archive.write(path, prefix + path.relative_to(base).as_posix())
        archive.write(root / "infrastructure/lambda/ai_worker_handler.py", "ai_worker_handler.py")
    print(f"Local K5 package created: {output}")


if __name__ == "__main__":
    main()
