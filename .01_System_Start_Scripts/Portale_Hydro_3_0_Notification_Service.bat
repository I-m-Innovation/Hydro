
@REM @echo off
@REM title Portale Hydro - Notifications Service

@REM cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

@REM call ".venv\Scripts\activate.bat"
@REM python notifications_service\interactive_bot.py

@REM pause


@echo off
setlocal
title Portale Hydro - Notifications Service

cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

if not exist "logs" mkdir "logs"
call ".venv\Scripts\activate.bat"

:loop
echo [%date% %time%] START notifications>> logs\notifications.log
python notifications_service\interactive_bot.py >> logs\notifications.log 2>>&1
echo [%date% %time%] STOP  notifications exitcode=%ERRORLEVEL%>> logs\notifications.log
timeout /t 10 /nobreak >nul
goto loop
