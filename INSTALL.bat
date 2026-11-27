@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto installpython
py -3.12 -c "import struct; assert struct.calcsize('P')==8" >nul 2>&1
if not errorlevel 1 goto setup
:installpython
winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto fail
echo Open a new CMD and run INSTALL.bat again.
pause
exit /b 0
:setup
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto fail
set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto fail
choice /C GC /M "G = NVIDIA GPU (CUDA 12.6), C = CPU"
if errorlevel 2 goto cpu
"%PY%" -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
goto check
:cpu
"%PY%" -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu
:check
if errorlevel 1 goto fail
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto fail
"%PY%" -m pip check
if errorlevel 1 goto fail
"%PY%" -m unittest -v test_core
if errorlevel 1 goto fail
"%PY%" -c "import torch,cv2,ultralytics,tkinter; print('CUDA available:',torch.cuda.is_available())"
if errorlevel 1 goto fail
"%PY%" -m pip freeze > installed_versions.txt
echo Installation complete. Run START.bat.
pause
exit /b 0
:fail
echo Installation failed. Review the error above.
pause
exit /b 1
