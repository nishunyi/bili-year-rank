@echo off
cd /d "%~dp0"
echo Exit the enhanced Bilibili client before continuing.
pause
python -X utf8 integration\patch_client.py restore
if errorlevel 1 goto failed
powershell -NoProfile -File integration\desktop-shortcut.ps1 -Action Remove
if errorlevel 1 goto failed
echo Restored. Use the original Bilibili desktop shortcut.
pause
exit /b 0
:failed
echo Restore did not complete. No unknown files were overwritten.
pause
exit /b 1
