
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "learncloud-lambda.zip"

EXCLUDED = {
    "__pycache__", ".venv", "venv",
    ".git", ".pytest_cache"
}

with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as z:
    for source, destination in [
        (ROOT / "backend" / "app", "app"),
        (ROOT / "ai_pipeline", "ai_pipeline"),
    ]:
        if not source.is_dir():
            raise FileNotFoundError(source)

        for file in source.rglob("*"):
            if not file.is_file():
                continue

            if any(part in EXCLUDED for part in file.parts):
                continue

            if file.suffix in {".pyc", ".pyo"}:
                continue

            if file.name == ".env":
                continue

            arcname = (
                Path(destination) / file.relative_to(source)
            ).as_posix()

            z.write(file, arcname)

    handler = (
        "from app.main import lambda_handler\n"
    )

    z.writestr("lambda_function.py", handler)

print(f"Created: {OUTPUT}")

with ZipFile(OUTPUT) as z:
    required = [
        "lambda_function.py",
        "app/main.py",
        "app/database.py",
        "app/dependencies.py",
        "app/services/auth_service.py",
    ]

    for name in required:
        if name not in z.namelist():
            raise RuntimeError(f"Missing: {name}")

    if z.testzip() is not None:
        raise RuntimeError("Invalid ZIP")

    print("ZIP structure: OK")
    print("Files:", len(z.namelist()))
