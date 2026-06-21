@echo off
REM TUI-do launcher for Windows
REM Place this .bat file anywhere on your PATH, or double-click from the project folder.

setlocal

REM Resolve the directory this .bat lives in
set "SCRIPT_DIR=%~dp0"

REM Activate virtual environment if it exists alongside the script
if exist "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%venv\Scripts\activate.bat"
) else if exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
)

REM Run tuido — works both when installed as CLI and when run directly
where tuido >nul 2>&1
if %ERRORLEVEL%==0 (
    tuido %*
) else (
    python "%SCRIPT_DIR%main.py" %*
)

endlocal
