@echo off
cd /d "%~dp0"
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate
python -m pip install -r requirements.txt --disable-pip-version-check -q
if errorlevel 1 (
    echo Could not install requirements. Check your internet connection and Python installation.
    pause
    exit /b 1
)
streamlit run app.py
pause
