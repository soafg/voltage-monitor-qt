@echo off
chcp 65001 >nul
echo ============================================
echo   电压监测 Qt - 一键打包脚本
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装 Python 依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

REM 清理旧构建
echo [2/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist VoltageMonitorQt.spec del /q VoltageMonitorQt.spec

REM 打包
echo [3/3] 开始打包...
pyinstaller --noconfirm --onefile --windowed --name "VoltageMonitorQt" --icon "assets/app.ico" ^
  --add-data "libs/LibreHardwareMonitorLib.dll;." ^
  --add-data "libs/RAMSPDToolkit-NDD.dll;." ^
  --add-data "libs/DiskInfoToolkit.dll;." ^
  --add-data "libs/BlackSharp.Core.dll;." ^
  --add-data "libs/HidSharp.dll;." ^
  --add-data "libs/System.Memory.dll;." ^
  --add-data "libs/System.Buffers.dll;." ^
  --add-data "libs/System.Runtime.CompilerServices.Unsafe.dll;." ^
  --add-data "libs/System.Numerics.Vectors.dll;." ^
  --add-data "libs/System.Text.Json.dll;." ^
  --add-data "libs/System.Threading.AccessControl.dll;." ^
  --add-data "libs/System.Security.AccessControl.dll;." ^
  --add-data "libs/System.Security.Principal.Windows.dll;." ^
  --add-data "assets/icon.jpg;." ^
  src/qt_monitor.py

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包完成！输出: dist\VoltageMonitorQt.exe
echo ============================================
pause
