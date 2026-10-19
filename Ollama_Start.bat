@echo off
chcp 65001 >nul
title Ollama IPEX Server

REM ============================================================
REM  Ollama IPEX Launcher
REM  NOT: OLLAMA_EXE yolunu kendi kurulumunuza gore duzenleyin.
REM ============================================================

set OLLAMA_EXE=C:\AI_IPEX\Ollama\portable\ollama.exe

if not exist "%OLLAMA_EXE%" (
    echo [HATA] Ollama bulunamadi: %OLLAMA_EXE%
    echo Lutfen OLLAMA_EXE yolunu bu dosyada duzenleyin.
    pause
    exit /b 1
)

REM IPEX LLM ortam degiskenleri
set OLLAMA_NUM_GPU=999
set ONEAPI_DEVICE_SELECTOR=level_zero:0
set ZES_ENABLE_SYSMAN=1
set SYCL_CACHE_PERSISTENT=1
set SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1
set IPEX_LLM_NUM_CTX=12288
set OLLAMA_CONTEXT_LENGTH=12288
set no_proxy=localhost,127.0.0.1
set NO_PROXY=localhost,127.0.0.1
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_KEEP_ALIVE=24h
set OLLAMA_MAX_LOADED_MODELS=1
set OLLAMA_FLASH_ATTENTION=false

echo Ollama IPEX baslatiliyor: %OLLAMA_EXE%
"%OLLAMA_EXE%" serve
