@echo off
rem ============================================================
rem  Lance l'application directement avec Python (sans build)
rem ============================================================
cd /d "%~dp0"
python -c "import tkinter" 2>nul || (
    echo Tkinter est absent : re-installez Python en cochant "tcl/tk and IDLE".
    pause
    exit /b 1
)
python -m pip show send2trash >nul 2>&1 || python -m pip install send2trash
python doublons.py
