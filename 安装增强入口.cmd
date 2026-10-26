@echo off
cd /d "%~dp0"
python -X utf8 integration\patch_client.py install
if errorlevel 1 goto failed
powershell -NoProfile -File integration\desktop-shortcut.ps1 -Action Create
if errorlevel 1 goto failed
echo Done. Use the enhanced desktop shortcut after exiting the original client.
pause
exit /b 0
:failed
echo Installation did not complete. The original installation was not modified.
pause
exit /b 1
