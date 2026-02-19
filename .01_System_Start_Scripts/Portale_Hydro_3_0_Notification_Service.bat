
@REM @echo off
@REM title Portale Hydro - Notifications Service

@REM cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

@REM call ".venv\Scripts\activate.bat"
@REM python notifications_service\interactive_bot.py

@REM pause


@echo off
setlocal EnableDelayedExpansion
title Portale Hydro - Notifications Service

cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

call ".venv\Scripts\activate.bat"

set "base_wait=10"
set "max_retries=10"
set "retry=0"

:loop
echo [%date% %time%] START notifications
python -u notifications_service\interactive_bot.py
set "exitcode=%ERRORLEVEL%"
echo [%date% %time%] STOP  notifications exitcode=!exitcode!

if "!exitcode!"=="0" (
  echo [%date% %time%] EXIT  notifications clean_exit
  exit /b 0
) else (
  set /a retry+=1
  if !retry! gtr %max_retries% (
    echo [%date% %time%] GIVEUP notifications retries=%max_retries% last_exitcode=!exitcode!
    exit /b !exitcode!
  )
  set /a wait=%base_wait%
  set /a exp=retry-1
  for /l %%i in (1,1,!exp!) do set /a wait*=2
)

echo [%date% %time%] WAIT  notifications seconds=!wait! retry=!retry!

timeout /t !wait! /nobreak >nul
goto loop
