@echo off
chcp 65001 >nul
title LinkedIn Takip - Flask
color 0A

echo ================================================
echo   LinkedIn Takip Asistani (Flask)
echo ================================================

REM Ollama kontrolu (bilgi amacli)
set OLLAMA_EXE=C:\AI_IPEX\Ollama\portable\ollama.exe
if not exist "%OLLAMA_EXE%" (
    echo [UYARI] IPEX Ollama bulunamadi: %OLLAMA_EXE%
    echo         Ollama_Start.bat icindeki yolu kontrol edin.
)

REM Eski Ollama sureclerini durdur
taskkill /f /im ollama.exe >nul 2>&1
taskkill /f /im ollama-lib.exe >nul 2>&1
taskkill /f /im "ollama app.exe" >nul 2>&1
timeout /t 2 /nobreak >nul

echo [1/4] Ollama (IPEX) baslatiliyor...
start "Ollama-IPEX" /min "%~dp0Ollama_Start.bat"

echo [2/4] Ollama API yaniti bekleniyor (max 45 sn)...
set /a n=0
:WAIT_OLLAMA
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto OLLAMA_READY
set /a n+=1
if %n% GEQ 45 goto OLLAMA_FAIL
goto WAIT_OLLAMA

:OLLAMA_READY
echo        Ollama hazir.

echo [3/4] Python venv aktif ediliyor...
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo        .venv aktif.
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
    echo        venv aktif.
) else (
    echo        venv bulunamadi, global python kullanilacak.
)

echo [4/4] Flask baslatiliyor...
python app.py

pause
goto :eof

:OLLAMA_FAIL
echo [HATA] Ollama 45 saniyede acilmadi.
echo        Manuel kontrol: Ollama_Start.bat
pause
