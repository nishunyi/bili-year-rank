@echo off
cd /d "%~dp0"
pythonw gui.py
if errorlevel 1 (
  echo Failed to launch. Check Python and Tkinter.
  pause
)
