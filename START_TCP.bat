@echo off
setlocal
cd /d "%~dp0"
echo Available scenarios:
py -3 elm_mock.py --list-scenarios
echo.
set "SCENARIO=climate_ddt_0456"
set /p "SCENARIO=Scenario [climate_ddt_0456]: "
if "%SCENARIO%"=="" set "SCENARIO=climate_ddt_0456"
if /I "%SCENARIO%"=="replay" (
  py -3 elm_mock.py --scenario "%SCENARIO%" --host 127.0.0.1 --port 35000
) else (
  py -3 elm_mock.py --scenario "%SCENARIO%" --host 127.0.0.1 --port 35000 --definition "Clim_J81_Serie_(vers07).json"
)
pause
