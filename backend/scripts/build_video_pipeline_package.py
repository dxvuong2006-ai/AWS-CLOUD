"""Offline ZIP packaging only. Never uploads/deploys or reads .env/credentials.

First install Linux Python 3.12 x86_64 wheels into a dedicated dependency folder.
See docs/aws-video-pipeline-console-setup.md. This script does not install them.
"""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/video-pipeline.zip"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    dependencies = args.dependencies.resolve()
    # Never package the repository, a venv or a directory containing secrets.
    if not dependencies.is_dir() or not (dependencies / "psycopg2").is_dir():
        parser.error("Provide the dedicated Linux dependency directory containing psycopg2.")
    if dependencies == root or (dependencies / "pyvenv.cfg").exists():
        parser.error("A repository or virtualenv is not a dependency directory.")
    for path in dependencies.rglob("*"):
        if path.name.startswith(".env") or path.name in {"credentials", ".aws", ".git"} or path.suffix in {".pyd", ".exe"}:
            parser.error("Dependency folder contains a secret/config or Windows binary.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, "w", ZIP_DEFLATED) as archive:
        for base, prefix in ((dependencies, ""), (root / "backend/app", "app/")):
            for path in sorted(base.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    archive.write(path, prefix + path.relative_to(base).as_posix())
        archive.write(root / "infrastructure/lambda/video_pipeline_handler.py", "video_pipeline_handler.py")
        archive.write(
            root / "infrastructure/lambda/video_pipeline_test_handler.py",
            "video_pipeline_test_handler.py",
        )
    print(f"Local package created: {args.output}")


if __name__ == "__main__":
    main()
