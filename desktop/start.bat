@echo off
cd /d "%~dp0"
if exist "dist\Migi\Migi.exe" (
  start "" "dist\Migi\Migi.exe"
) else (
  echo Migi.exe is missing. Please keep the complete dist\Migi folder.
  pause
)
