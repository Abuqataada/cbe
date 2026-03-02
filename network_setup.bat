@echo off
echo ========================================
echo ARNDALE CBT SERVER NETWORK SETUP
echo ========================================
echo.

REM Get IP address
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /C:"IPv4 Address"') do (
    set IP=%%i
    goto :found
)
:found
set IP=%IP:~1%

echo Your server IP address: %IP%
echo.
echo To access the server from other computers:
echo 1. Make sure all computers are on the SAME NETWORK
echo 2. Open browser and go to: http://%IP%:5000
echo.
echo Press any key to start the server...
pause >nul

REM Start the server
python run_server.py