@echo off
REM Build script for RustChain DOS/XT Miner
REM Requires Open Watcom C Compiler

echo.
echo ============================================
echo  RustChain Miner for IBM PC/XT - Build
echo ============================================
echo.

REM Check if WATCOM is set
if "%WATCOM%"=="" (
    echo ERROR: WATCOM environment variable not set!
    echo.
    echo Please set up Open Watcom environment:
    echo   SET WATCOM=C:\WATCOM
    echo   SET PATH=%%WATCOM%%\BINW;%%PATH%%
    echo.
    goto :error
)

echo [1/6] Checking Watcom installation...
if not exist "%WATCOM%\BINW\wcc.exe" (
    echo ERROR: Watcom compiler not found at %WATCOM%\BINW\wcc.exe
    goto :error
)
echo [OK] Watcom compiler found

echo.
echo [2/6] Setting up environment...
set INCLUDE=%WATCOM%\H
set LIB=%WATCOM%\LIB286;%WATCOM%\LIB286\DOS
echo [OK] Environment configured

echo.
echo [3/6] Compiling source files...

echo       - main.c
wcc -ml -bt=dos -ox -s -zq src\main.c
if errorlevel 1 goto :compile_error

echo       - hw_xt.c
wcc -ml -bt=dos -ox -s -zq src\hw_xt.c
if errorlevel 1 goto :compile_error

echo       - pit.c
wcc -ml -bt=dos -ox -s -zq src\pit.c
if errorlevel 1 goto :compile_error

echo       - attest.c
wcc -ml -bt=dos -ox -s -zq src\attest.c
if errorlevel 1 goto :compile_error

echo       - network.c
wcc -ml -bt=dos -ox -s -zq src\network.c
if errorlevel 1 goto :compile_error

echo [OK] All source files compiled

echo.
echo [4/6] Linking...
wlink system dos ^
    file main.obj ^
    file hw_xt.obj ^
    file pit.obj ^
    file attest.obj ^
    file network.obj ^
    name miner.com ^
    option quiet
if errorlevel 1 goto :link_error

echo [OK] Linked successfully

echo.
echo [5/6] Checking output...
if not exist miner.com (
    echo ERROR: miner.com not created!
    goto :error
)

dir miner.com
echo [OK] Output file created

echo.
echo [6/6] Cleaning up object files...
del *.obj
echo [OK] Cleanup complete

echo.
echo ============================================
echo  BUILD SUCCESSFUL!
echo ============================================
echo.
echo Output: miner.com
echo Size: 
dir miner.com | find "miner.com"
echo.
echo To run:
echo   miner.com -w YOUR_WALLET_ADDRESS
echo.
echo For help:
echo   miner.com -h
echo.
goto :end

:compile_error
echo.
echo ============================================
echo  COMPILE ERROR
echo ============================================
echo.
echo Check source files for errors.
goto :error

:link_error
echo.
echo ============================================
echo  LINK ERROR
echo ============================================
echo.
echo Check object files and libraries.
goto :error

:error
echo.
echo Build failed!
echo.
exit /b 1

:end
exit /b 0
