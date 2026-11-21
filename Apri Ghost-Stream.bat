@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "_gui_tk.py"
) else (
    start "" python "_gui_tk.py"
)
