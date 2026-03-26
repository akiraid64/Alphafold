@echo off
echo Starting AlphaFold Viewer...
echo Please wait while the server starts.
echo The browser will open automatically.

start "" "http://localhost:8000"
python server.py
pause
