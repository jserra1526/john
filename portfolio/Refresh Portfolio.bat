@echo off
rem Double-click to refresh share-portfolio-tracker.xlsx (close Excel first).
cd /d "%~dp0"
title Refresh Portfolio
set PY=
where py >nul 2>nul && set PY=py
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python is not installed. See SETUP.md - install it from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
echo Checking add-ons (first run takes a minute)...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Could not install the required add-ons. Check your internet connection and try again.
  pause
  exit /b 1
)
%PY% refresh.py
echo.
pause
