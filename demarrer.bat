@echo off
chcp 65001 >nul
title Timbre - lanceur
cd /d "%~dp0"

echo [Timbre] Reveil du serveur LM Studio (si installe)...
where lms >nul 2>nul
if %errorlevel%==0 (
    lms server start
) else (
    echo [Timbre] CLI "lms" introuvable - pense a demarrer le serveur dans LM Studio.
)

if not exist "ui\node_modules" (
    echo [Timbre] Premiere utilisation : installation des dependances UI...
    pushd ui
    call npm install
    popd
)

echo [Timbre] Lancement du backend...
start "Timbre - backend" /d "%~dp0" cmd /k "set PYTHONUTF8=1&& uv run --extra asr timbre"

echo [Timbre] Lancement de l'interface...
start "Timbre - UI" /d "%~dp0ui" cmd /k "npm run dev"

timeout /t 4 /nobreak >nul
start "" http://localhost:5173

echo.
echo [Timbre] Pret ! L'interface s'ouvre dans le navigateur.
echo [Timbre] Pour tout arreter : ferme les deux fenetres "Timbre - backend" et "Timbre - UI".
timeout /t 6 >nul
