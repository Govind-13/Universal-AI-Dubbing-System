@echo off
setlocal

echo Starting AI Video Localization Platform (Dev Mode)...
echo.

rem ---- Free ports 8000 and 5173 if something is already listening ----
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1

rem ---- Start Backend Server ----
start "FastAPI Backend" /d "%~dp0backend" cmd /k "python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

rem ---- Start Frontend Dev Server ----
start "Frontend UI" /d "%~dp0frontend" cmd /k "npm run dev"

echo Servers started!
echo Frontend is available at http://localhost:5173
echo Backend API is available at http://localhost:8000

timeout /t 5 > nul
start "" "http://localhost:5173"

endlocal
