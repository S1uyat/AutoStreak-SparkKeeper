@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
if exist ".venv\Scripts\python.exe" goto :deps
set "PY_CMD="
for /d %%D in ("%LocalAppData%\Programs\Python\Python*") do if exist "%%~D\python.exe" set PY_CMD="%%~D\python.exe"
if not defined PY_CMD (
  py -3 --version >nul 2>&1
  if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
  python --version >nul 2>&1
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD goto :failed
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] 创建独立 Python 环境...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :failed
)
:deps
echo [2/3] 安装 Playwright...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo [3/3] 安装备用 Chromium 浏览器组件...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
  echo 备用 Chromium 安装失败。可先使用 Windows 自带 Edge 模式。
)
echo.
echo 安装结束。首次打开管理界面后，请先扫码登录、选择好友、保存设置，最后点击「安装开机自启」。
start "" ".venv\Scripts\pythonw.exe" "%~dp0manager.py"
exit /b 0
:failed
echo 安装失败。请检查 Python / 网络环境，然后重新运行本文件。
pause
exit /b 1
