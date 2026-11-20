@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Kipshot - сборка

echo ==================================================
echo   Kipshot - сборка exe и установщика
echo ==================================================
echo.
taskkill /IM Kipshot.exe /F >nul 2>nul
taskkill /IM Kipshot_Portable.exe /F >nul 2>nul

call :findpy
if defined PY goto havepy
echo [1/5] Python не найден - устанавливаю Python 3.12...
where winget >nul 2>nul
if errorlevel 1 goto download
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
call :findpy
if defined PY goto havepy
:download
echo Скачиваю установщик Python с python.org...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile \"$env:TEMP\py-setup.exe\""
if not exist "%TEMP%\py-setup.exe" goto nopy
"%TEMP%\py-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1
call :findpy
if not defined PY goto nopy

:havepy
echo [1/5] Python: %PY%
echo [2/5] Библиотеки PySide6 и PyInstaller...
"%PY%" -m pip install --disable-pip-version-check -q --upgrade PySide6 pyinstaller winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections
if errorlevel 1 goto fail

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if not exist release mkdir release

echo [3/5] Собираю программу для установщика...
"%PY%" -m PyInstaller --noconfirm --clean --log-level WARN --windowed --onedir --name Kipshot --icon assets\icon.ico --version-file assets\version_info.txt --add-data "assets\icon.ico;." --exclude-module tkinter kipshot.py
if errorlevel 1 goto fail
if not exist "dist\Kipshot\Kipshot.exe" goto fail

echo [4/5] Собираю портативную версию - один exe-файл...
"%PY%" -m PyInstaller --noconfirm --log-level WARN --windowed --onefile --name Kipshot_Portable --icon assets\icon.ico --version-file assets\version_info.txt --add-data "assets\icon.ico;." --exclude-module tkinter kipshot.py
if errorlevel 1 goto fail
copy /y "dist\Kipshot_Portable.exe" "release\Kipshot_Portable.exe" >nul

echo [5/5] Создаю установщик...
call :findiscc
if defined ISCC goto haveiscc
echo Inno Setup не найден - устанавливаю...
winget install -e --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
call :findiscc
if not defined ISCC goto noiscc
:haveiscc
"%ISCC%" /Q Kipshot.iss
if errorlevel 1 goto fail

echo.
echo ==================================================
echo   ГОТОВО! Папка release:
echo     Kipshot_Setup_1.2.0.exe  - установщик
echo     Kipshot_Portable.exe     - без установки
echo ==================================================
start "" explorer "%~dp0release"
pause
exit /b 0

:noiscc
echo.
echo Установщик не создан: не удалось поставить Inno Setup.
echo Портативная версия готова: release\Kipshot_Portable.exe
echo Можно поставить Inno Setup вручную: https://jrsoftware.org/isdl.php
start "" explorer "%~dp0release"
pause
exit /b 1

:nopy
echo.
echo Не получилось установить Python. Поставьте вручную: https://www.python.org/downloads/
echo Отметьте галочку "Add python.exe to PATH" и запустите этот файл снова.
pause
exit /b 1

:fail
echo.
echo ОШИБКА при сборке - пришлите скриншот этого окна.
pause
exit /b 1

:findpy
set "PY="
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
if defined PY exit /b 0
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)"') do set "PY=%%P"
if defined PY exit /b 0
python -c "import sys" >nul 2>nul
if not errorlevel 1 for /f "delims=" %%P in ('python -c "import sys;print(sys.executable)"') do set "PY=%%P"
exit /b 0

:findiscc
set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
exit /b 0
