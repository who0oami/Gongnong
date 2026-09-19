@echo off
setlocal

if "%~1"=="" (
  echo Usage: run_motion.cmd ^<motion-json-file^>
  exit /b 1
)

set "KSL_MOTION_JSON=%~f1"
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --python "%~dp0open_word2153_test.py"

endlocal
