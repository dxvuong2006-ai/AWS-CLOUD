@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1

set "PYTHONPATH=.;backend"
set "DATABASE_URL=sqlite:///./test.db"
set "JWT_SECRET_KEY=learncloud-super-secret-key-32chars-minimum-2026"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "AWS_EC2_METADATA_DISABLED=true"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

rem Open docs only after the server responds (bounded wait).
start "" /b "%PYTHON_EXE%" -c "import time, urllib.request, webbrowser; url='http://127.0.0.1:8000/docs'; exec('for _ in range(60):\n try:\n  with urllib.request.urlopen(url, timeout=1): pass\n except OSError:\n  time.sleep(1)\n else:\n  webbrowser.open(url)\n  break')"

echo LearnCloud: http://127.0.0.1:8000/docs
echo Press Ctrl+C to stop.
"%PYTHON_EXE%" -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
set "server_exit_code=%errorlevel%"
if not "%server_exit_code%"=="0" pause
exit /b %server_exit_code%
