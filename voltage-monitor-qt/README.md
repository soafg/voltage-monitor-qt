# 电压监测 Qt（Voltage Monitor Qt）

基于 **Qt（PySide6）** 的 Windows 硬件传感器实时监测工具，专为华硕主板优化。

可读取华硕主板上几乎全部传感器（约 245 个），按硬件类型和传感器类别分组展示，支持一键隐藏/显示各类传感器。

## ✨ 功能特性

- **全面监测**：主板（SuperIO）、CPU、内存、GPU、硬盘 五大类硬件，约 245 个传感器
- **按类分组**：电压 / 温度 / 风扇 / 频率 / 负载 / 功耗 / 时序 等分类展示
- **可隐藏显示**：每个类别标题前有勾选框，一键显示或隐藏整类传感器
- **告警变色**：电压、温度超阈值自动变橙/红
- **单文件运行**：打包后为单 exe，免安装，双击即用
- **简洁界面**：淡蓝白配色，圆角卡片设计

## 🖥️ 系统要求

- Windows 10 / 11（x64）
- 华硕主板（其他主板也可运行，传感器数量取决于硬件）
- 首次使用需安装 PawnIO 驱动（见下方说明）

## 📦 目录结构

```
voltage-monitor-qt/
├── src/
│   └── qt_monitor.py          # 主程序源码
├── libs/                       # 硬件监控库及 .NET 依赖
│   ├── LibreHardwareMonitorLib.dll
│   ├── RAMSPDToolkit-NDD.dll
│   ├── DiskInfoToolkit.dll
│   ├── BlackSharp.Core.dll
│   ├── HidSharp.dll
│   └── System.*.dll
├── assets/
│   ├── icon.jpg                # 界面图标
│   └── app.ico                 # 应用图标
├── driver/
│   └── PawnIO_setup.exe        # PawnIO 驱动安装程序
├── release/
│   └── VoltageMonitorQt.exe    # 打包好的可执行文件
├── requirements.txt            # Python 依赖
├── build.bat                   # 一键打包脚本
└── README.md
```

## 🚀 快速使用（免安装）

1. 下载 `release/VoltageMonitorQt.exe`
2. **首次使用**：运行 `driver/PawnIO_setup.exe` 安装硬件访问驱动（仅需一次）
3. 双击 `VoltageMonitorQt.exe` 启动
4. 顶部标签页切换硬件，勾选/取消勾选类别标题可显示/隐藏传感器

## 🔧 从源码运行

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 将 libs/ 下的所有 DLL 复制到 src/ 目录（或与脚本同目录）
copy libs\*.dll src\

# 3. 运行
cd src
python qt_monitor.py
```

## 📦 打包为 exe

```bash
# 使用 build.bat 一键打包
build.bat
```

手动打包命令：

```bash
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
```

## 📊 传感器清单（华硕 TUF B760M-PLUS WIFI D4 实测）

| 硬件 | 传感器数 | 类别 |
|------|---------|------|
| 主板（Nuvoton NCT6798D） | 33 | 电压16 / 温度5 / 风扇6 / 控制6 |
| CPU（i5-14600KF） | 87 | 负载22 / 温度31 / 频率15 / 功耗4 / 电压15 |
| 内存条 ×2 | 23 each | 温度 / 时序 / 容量 |
| 虚拟内存 / 总量 | 3 each | 数据 / 负载 |
| GPU（RTX 5060） | 38 | 温度/频率/风扇/负载/电压等 |
| 存储 ×2 | 22 + 13 | 温度 / 寿命 / 读写 / 负载 |

## ⚠️ 告警阈值

| 项目 | 正常 | 告警（橙） | 危险（红） |
|------|------|-----------|-----------|
| 电压 | < 1.40 V | ≥ 1.40 V | ≥ 1.45 V |
| 温度 | < 70 °C | ≥ 70 °C | ≥ 85 °C |

## 🛠️ 技术栈

- **界面**：PySide6（Qt 6）
- **硬件读取**：LibreHardwareMonitorLib（通过 pythonnet 调用）
- **驱动**：PawnIO（硬件底层访问）
- **打包**：PyInstaller

## 📄 许可

本项目源码采用 MIT License。

依赖的第三方库遵循其各自的许可证：
- [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) - MPL-2.0
- [PawnIO](https://github.com/namazso/PawnIO) - 见其仓库
- [PySide6](https://wiki.qt.io/Qt_for_Python) - LGPL-3.0 / GPL-3.0

## ❓ 常见问题

**Q: 双击 exe 无反应？**
A: 单文件首次启动较慢（解压约 5-10 秒），请稍等。

**Q: 提示"硬件初始化失败"？**
A: 先运行 `driver/PawnIO_setup.exe` 安装驱动，再重新打开。

**Q: 部分传感器显示 "--"？**
A: 该传感器当前无读数（如空闲风扇、未插入的接口），属正常现象。

**Q: 杀毒软件报毒？**
A: PyInstaller 打包的程序可能被误报，添加信任即可。
