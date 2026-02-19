@REM title Portale Hydro 
@REM cd C:\Users\Sviluppo_Software_ZG\Desktop\hydro\portale_hydro_3_0
@REM .venv\Scripts\activate.bat
@REM python manage.py runserver 192.168.10.229:9984


@echo off
setlocal
title Portale Hydro

cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro\portale_hydro_3_0"

if not exist "logs" mkdir "logs"
call ".venv\Scripts\activate.bat"

:loop
echo [%date% %time%] START runserver>> logs\runserver.log
python manage.py runserver 192.168.10.229:9984 >> logs\runserver.log 2>>&1
echo [%date% %time%] STOP  runserver exitcode=%ERRORLEVEL%>> logs\runserver.log
timeout /t 10 /nobreak >nul
goto loop

