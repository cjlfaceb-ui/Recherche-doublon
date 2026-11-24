@echo off
rem ============================================================
rem  Construit RechercheDoublons.exe (fichier unique)
rem  Necessite Python 3.8+ installe sur le PC
rem ============================================================
cd /d "%~dp0"

echo [1/2] Installation des outils...
python -m pip install --upgrade pyinstaller send2trash || goto :erreur

echo [2/2] Compilation de l'executable...
if exist icone.ico (
    python -m PyInstaller --onefile --noconsole --name "RechercheDoublons" --icon=icone.ico doublons.py
) else (
    python -m PyInstaller --onefile --noconsole --name "RechercheDoublons" doublons.py
)
if errorlevel 1 goto :erreur

echo.
echo Termine ! L'executable se trouve dans le dossier "dist\RechercheDoublons.exe"
pause
exit /b 0

:erreur
echo.
echo Erreur pendant la construction.
pause
exit /b 1
