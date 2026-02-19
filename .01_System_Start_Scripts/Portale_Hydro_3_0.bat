@REM title Portale Hydro 
@REM cd C:\Users\Sviluppo_Software_ZG\Desktop\hydro\portale_hydro_3_0
@REM .venv\Scripts\activate.bat
@REM python manage.py runserver 192.168.10.229:9984


@echo off
setlocal EnableDelayedExpansion
title Portale Hydro

cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro\portale_hydro_3_0"

call ".venv\Scripts\activate.bat"

set "base_wait=10"
set "max_retries=10"
set "retry=0"

:loop
echo [%date% %time%] START runserver
python -u manage.py runserver 192.168.10.229:9984
set "exitcode=%ERRORLEVEL%"
echo [%date% %time%] STOP  runserver exitcode=!exitcode!

if "!exitcode!"=="0" (
  echo [%date% %time%] EXIT  runserver clean_exit
  exit /b 0
) else (
  set /a retry+=1
  if !retry! gtr %max_retries% (
    echo [%date% %time%] GIVEUP runserver retries=%max_retries% last_exitcode=!exitcode!
    exit /b !exitcode!
  )
  set /a wait=%base_wait%
  set /a exp=retry-1
  for /l %%i in (1,1,!exp!) do set /a wait*=2
)

echo [%date% %time%] WAIT  runserver seconds=!wait! retry=!retry!

timeout /t !wait! /nobreak >nul
goto loop

