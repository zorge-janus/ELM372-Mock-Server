@echo off
setlocal
cd /d "%~dp0"
echo Available scenarios:
py -3 elm_mock.py --list-scenarios
echo.
set "SCENARIO=climate_ddt_0456"
set /p "SCENARIO=Scenario [climate_ddt_0456]: "
if "%SCENARIO%"=="" set "SCENARIO=climate_ddt_0456"
set /p "COMPORT=Incoming Bluetooth COM port (example COM9): "
if "%COMPORT%"=="" (
  echo ERROR: COM port is required.
  pause
  exit /b 1
)
if /I "%SCENARIO%"=="replay" (
  py -3 elm_mock.py --scenario "%SCENARIO%" --serial "%COMPORT%"
) else (
  py -3 elm_mock.py --scenario "%SCENARIO%" --serial "%COMPORT%" --definition "Clim_J81_Serie_(vers07).json"
)
pause
