@REM @echo off
@REM title Portale Hydro - Db Manager

@REM cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

@REM call ".venv\Scripts\activate.bat"
@REM python -m db_manager.run

@REM pause


@echo off
setlocal
title Portale Hydro - Db Manager

cd /d "C:\Users\Sviluppo_Software_ZG\Desktop\hydro"

if not exist "logs" mkdir "logs"
call ".venv\Scripts\activate.bat"

:loop
echo [%date% %time%] START db_manager>> logs\db_manager.log
python -m db_manager.run >> logs\db_manager.log 2>>&1
echo [%date% %time%] STOP  db_manager exitcode=%ERRORLEVEL%>> logs\db_manager.log
timeout /t 10 /nobreak >nul
goto loop