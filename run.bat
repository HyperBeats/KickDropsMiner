@echo off
setlocal enableextensions
cd /d "%~dp0"

set "PYCMD="
py -3.10 -c "import sys" >NUL 2>&1 && set "PYCMD=py -3.10"
if not defined PYCMD (
  py -3 -c "import sys" >NUL 2>&1 && set "PYCMD=py -3"
)
if not defined PYCMD (
  python -c "import sys" >NUL 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
  echo Python 3.10+ not found. Please install from https://www.python.org/downloads/
  exit /b 1
)

echo Checking Python packages...
%PYCMD% -c "import selenium, webdriver_manager" >NUL 2>&1
if errorlevel 1 (
  echo Installing required packages: selenium, webdriver-manager
  %PYCMD% -m pip install --upgrade pip
  %PYCMD% -m pip install customtkinter pillow selenium webdriver-manager undetected-chromedriver
  if errorlevel 1 (
    echo Failed to install dependencies. Check your internet connection and try again.
    exit /b 1
  )
)

echo Launching Kick Drop Miner...
%PYCMD% main.py

endlocal
