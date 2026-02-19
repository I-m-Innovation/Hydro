@REM @echo off
@REM title Portale Hydro - Db Manager

@REM cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

@REM call ".venv\Scripts\activate.bat"
@REM python -m db_manager.run

@REM pause


@echo off
setlocal EnableDelayedExpansion
title Portale Hydro - Db Manager

cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

if not exist "logs" mkdir "logs"
call ".venv\Scripts\activate.bat"

set "base_wait=10"
set "max_retries=10"
set "retry=0"

:loop
echo [%date% %time%] START db_manager>> logs\db_manager.log
python -m db_manager.run >> logs\db_manager.log 2>>&1
set "exitcode=%ERRORLEVEL%"
echo [%date% %time%] STOP  db_manager exitcode=!exitcode!>> logs\db_manager.log

if "!exitcode!"=="0" (
  echo [%date% %time%] EXIT  db_manager clean_exit>> logs\db_manager.log
  exit /b 0
) else (
  set /a retry+=1
  if !retry! gtr %max_retries% (
    echo [%date% %time%] GIVEUP db_manager retries=%max_retries% last_exitcode=!exitcode!>> logs\db_manager.log
    exit /b !exitcode!
  )
  set /a wait=%base_wait%
  set /a exp=retry-1
  for /l %%i in (1,1,!exp!) do set /a wait*=2
)

echo [%date% %time%] WAIT  db_manager seconds=!wait! retry=!retry!>> logs\db_manager.log

timeout /t !wait! /nobreak >nul
goto loop
