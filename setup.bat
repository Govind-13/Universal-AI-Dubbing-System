@echo off
echo Setting up AI Video Localization Platform...

echo Installing Backend Dependencies...
cd backend
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install backend dependencies. Please ensure Python is installed and added to PATH.
    pause
    exit /b %errorlevel%
)
cd ..

echo Installing Frontend Dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo Failed to install frontend dependencies. Please ensure Node.js is installed.
    pause
    exit /b %errorlevel%
)
cd ..

echo Setup Complete! Run start_app.bat to launch the platform.
pause
