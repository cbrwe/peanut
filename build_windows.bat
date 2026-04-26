@echo off
REM Peanut Windows build
REM ====================
REM Produces dist\Peanut\ and (if Inno Setup is installed) a setup .exe
REM
REM Prerequisites:
REM   pip install -r requirements.txt
REM   pip install -r requirements-build.txt
REM
REM Optional: Inno Setup 6 (https://jrsoftware.org/isinfo.php) to build
REM           Peanut-1.0.0-windows-installer.exe

setlocal
set APP_NAME=Peanut
set APP_VERSION=1.0.0

cd /d "%~dp0"

echo ----------------------------------------------------
echo  Building %APP_NAME% for Windows
echo ----------------------------------------------------

REM 1. Clean
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo Cleaned previous builds.

REM 2. Generate icons if missing
if not exist static\icon.ico (
    echo Generating platform icons from static\icon.png...
    python build_icon.py
)

REM 3. PyInstaller
echo Running PyInstaller...
pyinstaller peanut.spec --clean --noconfirm
if errorlevel 1 goto :err
if not exist dist\%APP_NAME%\%APP_NAME%.exe goto :err
echo Built dist\%APP_NAME%\%APP_NAME%.exe

REM 4. Inno Setup installer (optional)
where /q ISCC.exe
if errorlevel 1 (
    echo Inno Setup ^(ISCC.exe^) not found in PATH — skipping installer.
    echo Install from https://jrsoftware.org/isinfo.php to enable.
    goto :done
)

echo Building Inno Setup installer...
ISCC.exe installer.iss
if errorlevel 1 goto :err
echo Installer created in dist\

:done
echo.
echo ----------------------------------------------------
echo  Build complete!
echo ----------------------------------------------------
echo  App:       dist\%APP_NAME%\%APP_NAME%.exe
echo  Installer: dist\%APP_NAME%-%APP_VERSION%-windows-installer.exe (if Inno Setup ran)
echo ----------------------------------------------------
goto :eof

:err
echo.
echo Build FAILED.
exit /b 1
