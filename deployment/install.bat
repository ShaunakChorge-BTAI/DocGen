@echo off
REM ============================================================
REM  DBAnalyser — Windows Installation Script
REM  Run as Administrator from the ltfs-analyzer folder
REM ============================================================

setlocal

SET APP_DIR=D:\LTFS\ltfs-analyzer
SET VENV_DIR=%APP_DIR%\.venv
SET PYTHON=python

echo.
echo ===================================================
echo   DBAnalyser Installation
echo ===================================================
echo.

REM ── 1. Check Python ─────────────────────────────────
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3.11+ first.
    exit /b 1
)
echo [OK] Python found.

REM ── 2. Create virtual environment ────────────────────
if not exist "%VENV_DIR%" (
    echo Creating virtual environment ...
    %PYTHON% -m venv "%VENV_DIR%"
    if errorlevel 1 ( echo [ERROR] venv creation failed. & exit /b 1 )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

REM ── 3. Activate and install package ──────────────────
call "%VENV_DIR%\Scripts\activate.bat"
echo Upgrading pip ...
python -m pip install --upgrade pip --quiet

echo Installing DBAnalyser and dependencies ...
pip install -e "%APP_DIR%[dev]" --quiet
if errorlevel 1 ( echo [ERROR] Package installation failed. & exit /b 1 )
echo [OK] Package installed.

REM ── 4. Test CLI ───────────────────────────────────────
dbanalyser --version
if errorlevel 1 ( echo [ERROR] CLI not available. & exit /b 1 )
echo [OK] CLI available.

REM ── 5. Optionally init the PostgreSQL database ────────
set /p INIT_DB="Initialise PostgreSQL database now? (y/n): "
if /i "%INIT_DB%"=="y" (
    dbanalyser init-db --config "%APP_DIR%\analysis_config.yaml"
)

REM ── 6. Optionally register scheduled task ─────────────
set /p SCHED="Register Windows Task Scheduler job? (y/n): "
if /i "%SCHED%"=="y" (
    schtasks /Create /XML "%APP_DIR%\deployment\task_scheduler_template.xml" /TN "DBAnalyser\DailyRun" /F
    if errorlevel 1 (
        echo [WARNING] Task Scheduler registration failed — try running as Administrator.
    ) else (
        echo [OK] Scheduled task registered.
    )
)

echo.
echo ===================================================
echo   Installation complete!
echo.
echo   Quickstart:
echo     dbanalyser validate
echo     dbanalyser run --format all
echo     dbanalyser dashboard
echo ===================================================
echo.

endlocal
