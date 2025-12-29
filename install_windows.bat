@echo off
REM Windows installation script for Sonicarbi
REM Run this in Command Prompt or PowerShell

echo ========================================
echo    Sonicarbi Windows Installer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.11+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

echo [OK] Python is installed
python --version

REM Check if Git is installed
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed!
    echo.
    echo Please install Git from:
    echo https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [OK] Git is installed
git --version
echo.

REM Check if already in Sonicarbi directory
if exist "requirements.txt" (
    echo [INFO] Already in Sonicarbi directory
    goto :install_deps
)

REM Clone repository
echo Cloning Sonicarbi repository...
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
if errorlevel 1 (
    echo [ERROR] Failed to clone repository
    pause
    exit /b 1
)

cd Sonicarbi
echo.

:install_deps
REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

echo [OK] Virtual environment created
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo Installing Python packages (this may take a while)...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [WARNING] Some packages failed to install
    echo Trying with psycopg2-binary instead...
    pip install psycopg2-binary
)

echo.
echo [OK] Packages installed
echo.

REM Create .env file if doesn't exist
if not exist "config\.env" (
    echo Creating configuration file...
    copy config\.env.example config\.env
    echo [OK] Created config\.env
    echo.
    echo [IMPORTANT] Edit config\.env with your settings!
) else (
    echo [OK] config\.env already exists
)

REM Create helper batch files
echo.
echo Creating helper scripts...

REM Start bot script
echo @echo off > start_bot.bat
echo cd /d %%~dp0 >> start_bot.bat
echo call venv\Scripts\activate.bat >> start_bot.bat
echo python src\scanner.py >> start_bot.bat
echo pause >> start_bot.bat

REM Start background script
echo @echo off > start_background.bat
echo cd /d %%~dp0 >> start_background.bat
echo start /B cmd /c "venv\Scripts\activate.bat && python src\scanner.py ^> bot.log 2^>^&1" >> start_background.bat
echo echo Bot started in background >> start_background.bat
echo echo Check logs in bot.log >> start_background.bat
echo pause >> start_background.bat

REM Stop bot script
echo @echo off > stop_bot.bat
echo taskkill /F /IM python.exe /FI "WINDOWTITLE eq *scanner.py*" >> stop_bot.bat
echo echo Bot stopped >> stop_bot.bat
echo pause >> stop_bot.bat

REM Validate config script
echo @echo off > validate.bat
echo cd /d %%~dp0 >> validate.bat
echo call venv\Scripts\activate.bat >> validate.bat
echo python scripts\validate_config.py >> validate.bat
echo pause >> validate.bat

REM Run tests script
echo @echo off > run_tests.bat
echo cd /d %%~dp0 >> run_tests.bat
echo call venv\Scripts\activate.bat >> run_tests.bat
echo pytest -v >> run_tests.bat
echo pause >> run_tests.bat

echo [OK] Helper scripts created
echo.

REM Installation complete
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Next Steps:
echo.
echo 1. Edit configuration:
echo    notepad config\.env
echo.
echo 2. Add your private key and RPC URLs
echo.
echo 3. Validate configuration:
echo    validate.bat
echo.
echo 4. Run the bot:
echo    start_bot.bat
echo.
echo Helper Scripts:
echo    start_bot.bat       - Start bot (foreground)
echo    start_background.bat - Start bot (background)
echo    stop_bot.bat        - Stop bot
echo    validate.bat        - Validate configuration
echo    run_tests.bat       - Run tests
echo.
echo Documentation:
echo    docs\WINDOWS_SETUP.md - Complete Windows guide
echo    docs\TERMUX_SETUP.md  - Termux/Android guide
echo    FEATURES.md           - Feature documentation
echo.
echo REMEMBER:
echo - Test on testnet first!
echo - Keep device running and connected
echo - Set up Telegram alerts for monitoring
echo - Only use dedicated wallet with minimal funds
echo.

REM Ask to open config
set /p OPENCONFIG="Open config file now? (y/n): "
if /i "%OPENCONFIG%"=="y" (
    notepad config\.env
)

echo.
echo Installation complete! Press any key to exit.
pause >nul
