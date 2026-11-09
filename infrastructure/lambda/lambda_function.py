
import sys
from pathlib import Path

DEPLOY_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DEPLOY_ROOT.parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"

if (DEPLOY_ROOT / "app").is_dir():
    sys.path.insert(0, str(DEPLOY_ROOT))
else:
    sys.path.insert(0, str(BACKEND_ROOT))
    sys.path.insert(0, str(REPO_ROOT))

from app.main import lambda_handler
