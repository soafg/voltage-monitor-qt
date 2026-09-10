# -*- coding: utf-8 -*-
"""
电压监测 - Qt 版（PySide6）
读取华硕主板全部传感器，按硬件大类 + 传感器类型分组
- 左侧书签式导航（紧凑）
- 右侧可折叠分组（长条状，收起时与标题同高）
- 圆润滚动条
- QThread 后台刷新（解决卡顿）
- 传感器悬停显示简介
- 观察页：添加单项传感器，可设置上下限告警
- 硬件信息页：显示当前硬件配置
"""
import sys
import math
import os

import clr

APP_DIR = os.path.dirname(os.path.abspath(__file__))
clr.AddReference(os.path.join(APP_DIR, "LibreHardwareMonitorLib.dll"))

from LibreHardwareMonitor.Hardware import Computer  # noqa: E402

from PySide6.QtCore import Qt, QThread, Signal, QSize  # noqa: E402
from PySide6.QtGui import QColor, QIcon, QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QScrollArea, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame, QMessageBox, QSizePolicy, QPushButton,
    QDialog, QDoubleSpinBox, QLineEdit, QDialogButtonBox,
)

# ────────────────────────────────────────────────────────────
# 传感器类型 → 中文名 + 单位
# ────────────────────────────────────────────────────────────
TYPE_META = {
    "Voltage":     ("电压",   "V"),
    "Temperature": ("温度",   "°C"),
    "Fan":         ("风扇",   "RPM"),
    "Control":     ("风扇控制", "%"),
    "Clock":       ("频率",   "MHz"),
    "Load":        ("负载",   "%"),
    "Power":       ("功耗",   "W"),
    "Data":        ("数据",   ""),
    "SmallData":   ("数据",   ""),
    "Timing":      ("时序",   "ns"),
    "Level":       ("寿命",   "%"),
    "Factor":      ("计数",   ""),
    "Throughput":  ("吞吐",   ""),
}

TYPE_ORDER = ["Voltage", "Temperature", "Fan", "Control", "Clock",
              "Load", "Power", "Data", "SmallData", "Timing",
              "Level", "Factor", "Throughput"]

# 传感器简介（悬停提示用）
SENSOR_DESC = {
    "Vcore": "CPU 核心电压，主板 SuperIO 芯片实测",
    "DRAM": "内存条工作电压",
    "+5V": "电源 +5V 输出",
    "+12V": "电源 +12V 输出",
    "+3.3V": "电源 +3.3V 输出",
    "+3V Standby": "待机 +3.3V 电压",
    "AVSB": "辅助电压（芯片组/内存相关）",
    "CMOS Battery": "主板 CMOS 电池电压",
    "VTT": "内存总线终端电压",
    "CPU Package": "CPU 封装温度",
    "Core Max": "核心最高温度",
    "Core Average": "核心平均温度",
    "Motherboard": "主板温度",
    "CPU Fan": "CPU 散热器风扇转速（RPM）",
    "Chassis Fan 1": "机箱风扇 1 转速（RPM）",
    "Chassis Fan 2": "机箱风扇 2 转速（RPM）",
    "Chassis Fan 3": "机箱风扇 3 转速（RPM）",
    "AIO Pump": "一体式水冷泵转速（RPM）",
    "CPU Core": "CPU 核心电压（VID 请求值）",
    "GPU Core": "GPU 核心频率",
    "GPU Memory": "GPU 显存频率",
    "GPU Core Voltage": "GPU 核心电压",
    "GPU Memory Junction": "GPU 显存结温",
    "Composite Temperature": "硬盘综合温度",
    "Life": "固态硬盘剩余寿命",
    "Available Spare": "固态硬盘可用备用块",
    "Used Space": "已用空间百分比",
    "Free Space": "剩余可用空间",
    "Total Space": "总容量",
    "Data Read": "累计读取量",
    "Data Written": "累计写入量",
    "Power On Count": "通电次数",
    "Power On Hours": "通电时长（小时）",
}


def make_desc(sensor_type, name):
    cn = TYPE_META.get(sensor_type, (sensor_type, ""))[0]
    if name in SENSOR_DESC:
        return SENSOR_DESC[name]
    return f"{cn}传感器「{name}」"


def fmt_value(sensor_type, value):
    if value is None:
        return "--"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "--"
    if math.isnan(v) or math.isinf(v):
        return "--"
    t = sensor_type
    if t == "Voltage":
        return f"{v:.3f}"
    if t == "Temperature":
        return f"{v:.0f}"
    if t in ("Fan", "Clock"):
        return f"{v:.0f}"
    if t in ("Load", "Control", "Power", "Level"):
        return f"{v:.1f}"
    if t == "Timing":
        return f"{v:.2f}"
    if t in ("Data", "SmallData"):
        return f"{v:.1f}"
    if t in ("Factor", "Throughput"):
        return f"{v:.0f}"
    return f"{v:.1f}"


# ────────────────────────────────────────────────────────────
# QSS 全局主题（含圆润滚动条）
# ────────────────────────────────────────────────────────────
STYLE = """
* { outline: none; }
QMainWindow, QWidget#root { background: #f4f8fc; }

/* ── 左侧书签栏 ── */
QListWidget#bookmark {
    background: #ffffff;
    border: none;
    border-right: 1px solid #d8e6f2;
    padding: 6px;
}
QListWidget#bookmark::item {
    color: #6b84a0;
    padding: 9px 12px;
    border-radius: 8px;
    margin: 2px 0;
}
QListWidget#bookmark::item:hover {
    background: #eef4fa;
    color: #2e7db8;
}
QListWidget#bookmark::item:selected {
    background: #dcebfa;
    color: #2e7db8;
    font-weight: bold;
}

/* ── 内容区 ── */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── 圆润流畅滚动条 ── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px 1px 2px 1px;
}
QScrollBar::handle:vertical {
    background: #c6d8e8;
    border-radius: 3px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: #a8c2da; }
QScrollBar::handle:vertical:pressed { background: #8db0ce; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 1px 2px 1px 2px;
}
QScrollBar::handle:horizontal {
    background: #c6d8e8;
    border-radius: 3px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover { background: #a8c2da; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ── 可折叠分组头部 ── */
QPushButton#groupHeader {
    background: #ffffff;
    border: 1px solid #d8e6f2;
    border-radius: 8px;
    text-align: left;
    padding: 8px 14px;
    color: #2c3e50;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#groupHeader:hover { background: #f0f6fc; border-color: #b8d4ea; }
QPushButton#groupHeader:checked {
    background: #eaf3fb; border-color: #a8cce8; color: #2e7db8;
}

/* ── 传感器行 ── */
QFrame#sensorRow {
    background: #ffffff;
    border: 1px solid #e6eef6;
    border-radius: 6px;
}
QFrame#sensorRow:hover { background: #f5faff; border-color: #bcd6ec; }
QLabel#sensorName { color: #7a8ea6; font-size: 12px; }
QLabel#sensorValue { color: #2e7db8; font-size: 15px; font-weight: bold; }
QLabel#sensorUnit { color: #9ab0c4; font-size: 11px; }

/* ── 观察页 ── */
QPushButton#addBtn {
    background: #4a90d9; color: #ffffff;
    border: none; border-radius: 8px;
    padding: 8px 16px; font-weight: bold;
}
QPushButton#addBtn:hover { background: #3c82cc; }
QPushButton#delBtn {
    background: #fdecea; color: #e74c3c;
    border: none; border-radius: 6px;
    padding: 4px 10px; font-size: 12px;
}
QPushButton#delBtn:hover { background: #fadbd8; }
QDoubleSpinBox {
    background: #ffffff; border: 1px solid #d8e6f2;
    border-radius: 5px; padding: 2px 4px; color: #2c3e50;
    font-size: 11px; min-height: 20px;
}
QDoubleSpinBox:focus { border-color: #4a90d9; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 14px; background: #eef4fa;
    border: none; border-radius: 2px;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: #dcebfa;
}
QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
    width: 0; height: 0; border: none;
}
QLabel#limitLbl { color: #9ab0c4; font-size: 11px; }

/* ── 硬件信息页 ── */
QFrame#infoCard {
    background: #ffffff;
    border: 1px solid #d8e6f2;
    border-radius: 10px;
}
QLabel#infoTitle { color: #4a90d9; font-size: 13px; font-weight: bold; }
QLabel#infoKey { color: #7a8ea6; font-size: 12px; }
QLabel#infoVal { color: #2c3e50; font-size: 12px; font-weight: bold; }

/* ── 对话框 ── */
QDialog { background: #f4f8fc; }
QLineEdit {
    background: #ffffff; border: 1px solid #d8e6f2;
    border-radius: 6px; padding: 5px 8px; color: #2c3e50;
}
QLineEdit:focus { border-color: #4a90d9; }
"""


# ────────────────────────────────────────────────────────────
# 后台硬件刷新线程（skill 铁律：不阻塞 UI 线程）
# ────────────────────────────────────────────────────────────
class HardwareWorker(QThread):
    sensors_ready = Signal(list)       # [(id, type, name)]
    hw_info_ready = Signal(dict)       # 硬件配置信息
    data_ready = Signal(dict)          # {id: value}
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._computer = None
        self._sensor_refs = []

    def run(self):
        try:
            self._computer = Computer()
            self._computer.IsCpuEnabled = True
            self._computer.IsMotherboardEnabled = True
            self._computer.IsControllerEnabled = True
            self._computer.IsGpuEnabled = True
            self._computer.IsMemoryEnabled = True
            self._computer.IsStorageEnabled = True
            self._computer.Open()

            for hw in self._computer.Hardware:
                hw.Update()
                for sub in hw.SubHardware:
                    sub.Update()

            # 收集硬件信息
            self.hw_info_ready.emit(self._collect_hw_info())

            # 收集传感器（过滤无意义的 SPD 元数据）
            meta = []
            for hw in self._computer.Hardware:
                for sub in hw.SubHardware:
                    for s in sub.Sensors:
                        if self._skip_sensor(s):
                            continue
                        sid = str(s.Identifier)
                        self._sensor_refs.append((sid, s))
                        meta.append((sid, str(s.SensorType), str(s.Name)))
                for s in hw.Sensors:
                    if self._skip_sensor(s):
                        continue
                    sid = str(s.Identifier)
                    self._sensor_refs.append((sid, s))
                    meta.append((sid, str(s.SensorType), str(s.Name)))

            self.sensors_ready.emit(meta)

            import time
            while not self.isInterruptionRequested():
                for hw in self._computer.Hardware:
                    hw.Update()
                    for sub in hw.SubHardware:
                        sub.Update()
                data = {}
                for sid, s in self._sensor_refs:
                    v = s.Value
                    data[sid] = float(v) if v is not None else None
                self.data_ready.emit(data)
                time.sleep(1.0)
        except Exception as ex:
            self.failed.emit(str(ex))

    def _skip_sensor(self, s):
        """过滤无意义的传感器（如无温度传感器的内存 SPD 元数据）"""
        name = str(s.Name)
        # 内存 SPD 温度元数据：无实际传感器芯片时返回 nan/None
        if str(s.SensorType) == "Temperature" and (
            "Resolution" in name or "Limit" in name):
            return True
        return False

    def _collect_hw_info(self):
        """收集硬件配置信息（通过 WMI）"""
        info = {}
        try:
            import clr as _clr
            _clr.AddReference("System.Management")
            from System.Management import ManagementObjectSearcher

            def wmi_first(query):
                try:
                    s = ManagementObjectSearcher(query)
                    for o in s.Get():
                        return o
                except Exception:
                    pass
                return None

            # CPU
            cpu = wmi_first("SELECT Name, NumberOfCores, NumberOfLogicalProcessors, "
                            "MaxClockSpeed FROM Win32_Processor")
            if cpu:
                info["cpu"] = {
                    "name": str(cpu["Name"]).strip(),
                    "cores": f"{cpu['NumberOfCores']} 核 {cpu['NumberOfLogicalProcessors']} 线程",
                    "clock": f"{cpu['MaxClockSpeed']} MHz",
                }

            # 主板 + BIOS
            mb = wmi_first("SELECT Manufacturer, Product FROM Win32_BaseBoard")
            if mb:
                info["mb"] = f"{mb['Manufacturer']} {mb['Product']}"
            bios = wmi_first("SELECT SMBIOSBIOSVersion FROM Win32_BIOS")
            if bios:
                info["bios"] = str(bios["SMBIOSBIOSVersion"])

            # 内存
            try:
                s = ManagementObjectSearcher(
                    "SELECT Capacity, Speed, Manufacturer FROM Win32_PhysicalMemory")
                dimms = []
                total = 0
                for o in s.Get():
                    cap = int(o["Capacity"]) // (1024 ** 3)
                    total += cap
                    dimms.append(f"{cap}GB @ {o['Speed']}MHz")
                info["mem"] = f"{total} GB（{' / '.join(dimms)}）"
            except Exception:
                pass

            # GPU
            gpu = wmi_first("SELECT Name, AdapterRAM FROM Win32_VideoController")
            if gpu:
                vram = int(gpu["AdapterRAM"] or 0) // (1024 ** 2)
                info["gpu"] = f"{gpu['Name']}" + (f"（{vram} MB）" if vram else "")

            # 硬盘
            try:
                s = ManagementObjectSearcher(
                    "SELECT Model, Size FROM Win32_DiskDrive")
                disks = []
                for o in s.Get():
                    size = int(o["Size"] or 0) // (1024 ** 3)
                    disks.append(f"{o['Model']}（{size} GB）")
                info["disk"] = disks
            except Exception:
                pass
        except Exception:
            pass
        return info

    def stop(self):
        self.requestInterruption()
        self.wait(2000)
        try:
            if self._computer is not None:
                self._computer.Close()
        except Exception:
            pass


# ────────────────────────────────────────────────────────────
# 传感器行（长条状，悬停显示简介）
# ────────────────────────────────────────────────────────────
class SensorRow(QFrame):
    def __init__(self, sid, sensor_type, name, parent=None):
        super().__init__(parent)
        self.setObjectName("sensorRow")
        self.sid = sid
        self.sensor_type = sensor_type
        self.unit = TYPE_META.get(sensor_type, (sensor_type, ""))[1]

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("sensorName")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("sensorValue")
        self.unit_label = QLabel(self.unit)
        self.unit_label.setObjectName("sensorUnit")

        lay.addWidget(self.name_label)
        lay.addStretch()
        lay.addWidget(self.value_label)
        lay.addWidget(self.unit_label)

        self.setToolTip(make_desc(sensor_type, name))
        self.setCursor(Qt.PointingHandCursor)

    def update_value(self, value):
        v = fmt_value(self.sensor_type, value)
        if self.value_label.text() != v:
            self.value_label.setText(v)
        unit = self.unit if self.unit else ""
        self.setToolTip(
            f"{make_desc(self.sensor_type, self.name_label.text())}\n"
            f"当前值：{v} {unit}".strip())
        color = "#2e7db8"
        if v != "--":
            try:
                num = float(v)
                if self.sensor_type == "Voltage":
                    if num >= 1.45:
                        color = "#e74c3c"
                    elif num >= 1.40:
                        color = "#e67e22"
                elif self.sensor_type == "Temperature":
                    if num >= 85:
                        color = "#e74c3c"
                    elif num >= 70:
                        color = "#e67e22"
            except ValueError:
                pass
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold;")


# ────────────────────────────────────────────────────────────
# 可折叠分组：收起时高度与标题框相同
# ────────────────────────────────────────────────────────────
class CollapsibleGroup(QWidget):
    def __init__(self, title, count, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(4)
        self.header = QPushButton(f"{title}  ({count})")
        self.header.setObjectName("groupHeader")
        self.header.setCheckable(True)
        self.header.setChecked(True)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(self._toggle)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(4)
        self.outer.addWidget(self.header)
        self.outer.addWidget(self.content)

    def _toggle(self, checked):
        self._collapsed = not checked
        self.content.setVisible(checked)

    def add_row(self, row):
        self.content_layout.addWidget(row)

    def is_collapsed(self):
        return self._collapsed


# ────────────────────────────────────────────────────────────
# 单个大类页（书签选中时显示）
# ────────────────────────────────────────────────────────────
class CategoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = {}
        self.rows = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 4, 0)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch()
        self.scroll.setWidget(self.content)
        lay.addWidget(self.scroll)

    def add_sensor(self, sid, sensor_type, name):
        if sensor_type not in self.groups:
            grp = CollapsibleGroup(
                TYPE_META.get(sensor_type, (sensor_type, ""))[0], 0)
            self.content_layout.insertWidget(self.content_layout.count() - 1, grp)
            self.groups[sensor_type] = grp
            self.rows[sensor_type] = []
        row = SensorRow(sid, sensor_type, name)
        self.groups[sensor_type].add_row(row)
        self.rows[sensor_type].append(row)
        grp = self.groups[sensor_type]
        grp.header.setText(
            f"{TYPE_META.get(sensor_type, (sensor_type, ''))[0]}  ({len(self.rows[sensor_type])})")

    def update_readings(self, data):
        for row_list in self.rows.values():
            for row in row_list:
                if row.sid in data:
                    row.update_value(data[row.sid])


# ────────────────────────────────────────────────────────────
# 观察页：可添加单项传感器 + 设置上下限告警
# ────────────────────────────────────────────────────────────
class WatchRow(QFrame):
    """观察行：名称 + 值 + 上下限设置 + 删除"""
    def __init__(self, sid, sensor_type, name, parent=None):
        super().__init__(parent)
        self.setObjectName("sensorRow")
        self.sid = sid
        self.sensor_type = sensor_type
        self.unit = TYPE_META.get(sensor_type, (sensor_type, ""))[1]

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("sensorName")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("sensorValue")
        self.unit_label = QLabel(self.unit)
        self.unit_label.setObjectName("sensorUnit")

        # 下限 / 上限
        lbl_min = QLabel("下限")
        lbl_min.setObjectName("limitLbl")
        self.spin_min = QDoubleSpinBox()
        self.spin_min.setRange(-100000, 100000)
        self.spin_min.setDecimals(3)
        self.spin_min.setValue(-100000)
        self.spin_min.setSpecialValueText("不限")
        self.spin_min.setFixedWidth(64)
        self.spin_min.setButtonSymbols(QDoubleSpinBox.UpDownArrows)

        lbl_max = QLabel("上限")
        lbl_max.setObjectName("limitLbl")
        self.spin_max = QDoubleSpinBox()
        self.spin_max.setRange(-100000, 100000)
        self.spin_max.setDecimals(3)
        self.spin_max.setValue(100000)
        self.spin_max.setSpecialValueText("不限")
        self.spin_max.setFixedWidth(64)
        self.spin_max.setButtonSymbols(QDoubleSpinBox.UpDownArrows)

        del_btn = QPushButton("✕")
        del_btn.setObjectName("delBtn")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFixedWidth(28)

        lay.addWidget(self.name_label, 1)
        lay.addWidget(self.value_label)
        lay.addWidget(self.unit_label)
        lay.addWidget(lbl_min)
        lay.addWidget(self.spin_min)
        lay.addWidget(lbl_max)
        lay.addWidget(self.spin_max)
        lay.addWidget(del_btn)

        self.del_btn = del_btn
        self.setToolTip(make_desc(sensor_type, name))

    def current_min(self):
        v = self.spin_min.value()
        return None if v <= -99999 else v

    def current_max(self):
        v = self.spin_max.value()
        return None if v >= 99999 else v

    def is_over_limit(self):
        """当前值是否超出用户设置的上下限"""
        txt = self.value_label.text()
        if txt == "--":
            return False
        try:
            num = float(txt)
        except ValueError:
            return False
        lo = self.current_min()
        hi = self.current_max()
        return (lo is not None and num < lo) or (hi is not None and num > hi)

    def update_value(self, value):
        v = fmt_value(self.sensor_type, value)
        if self.value_label.text() != v:
            self.value_label.setText(v)
        unit = self.unit if self.unit else ""
        self.setToolTip(
            f"{make_desc(self.sensor_type, self.name_label.text())}\n"
            f"当前值：{v} {unit}".strip())

        color = "#2e7db8"
        if v != "--":
            try:
                num = float(v)
                lo = self.current_min()
                hi = self.current_max()
                if (lo is not None and num < lo) or (hi is not None and num > hi):
                    color = "#e74c3c"
                elif self.sensor_type == "Voltage":
                    if num >= 1.45:
                        color = "#e74c3c"
                    elif num >= 1.40:
                        color = "#e67e22"
                elif self.sensor_type == "Temperature":
                    if num >= 85:
                        color = "#e74c3c"
                    elif num >= 70:
                        color = "#e67e22"
            except ValueError:
                pass
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold;")


class WatchPage(QWidget):
    """观察页"""
    def __init__(self, all_meta_provider, parent=None):
        super().__init__(parent)
        self._meta_provider = all_meta_provider  # callable -> [(id, type, name)]
        self.rows = []  # WatchRow

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # 顶部工具条
        toolbar = QHBoxLayout()
        title = QLabel("单项观察")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50;")
        add_btn = QPushButton("+ 添加传感器")
        add_btn.setObjectName("addBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_sensor)
        hint = QLabel("超限时数值变红")
        hint.setStyleSheet("color: #9ab0c4; font-size: 11px;")
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(hint)
        toolbar.addWidget(add_btn)
        lay.addLayout(toolbar)

        # 滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 4, 0)
        self.content_layout.setSpacing(6)
        self.content_layout.addStretch()
        self.scroll.setWidget(self.content)
        lay.addWidget(self.scroll)

        self._empty = QLabel("点击右上角「+ 添加传感器」选择要观察的项目")
        self._empty.setStyleSheet("color: #9ab0c4; font-size: 12px; padding: 20px;")
        self.content_layout.insertWidget(0, self._empty)

        # 左下角状态小框
        self.status_bar = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #27ae60; font-size: 10px;")
        self.status_label = QLabel("观察 0 项")
        self.status_label.setStyleSheet("color: #7a8ea6; font-size: 11px;")
        self.status_bar.addWidget(self.status_dot)
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addStretch()
        lay.addLayout(self.status_bar)

    def _update_status(self):
        n = len(self.rows)
        over = sum(1 for r in self.rows if r.is_over_limit())
        self.status_label.setText(f"观察 {n} 项" + (f"，{over} 项超限" if over else ""))
        self.status_dot.setStyleSheet(
            "color: #e74c3c; font-size: 10px;" if over else
            "color: #27ae60; font-size: 10px;")

    def _add_sensor(self):
        meta = self._meta_provider()
        if not meta:
            QMessageBox.information(self, "提示", "传感器尚未就绪，请稍候")
            return
        dlg = SensorPickDialog(meta, self)
        if dlg.exec() == QDialog.Accepted:
            sid, stype, name = dlg.selected()
            if sid:
                # 去重
                for r in self.rows:
                    if r.sid == sid:
                        return
                self._empty.setVisible(False)
                row = WatchRow(sid, stype, name)
                row.del_btn.clicked.connect(lambda: self._remove_row(row))
                self.content_layout.insertWidget(self.content_layout.count() - 1, row)
                self.rows.append(row)
                self._update_status()

    def _remove_row(self, row):
        self.rows.remove(row)
        self.content_layout.removeWidget(row)
        row.deleteLater()
        if not self.rows:
            self._empty.setVisible(True)
        self._update_status()

    def update_readings(self, data):
        for row in self.rows:
            if row.sid in data:
                row.update_value(data[row.sid])
        self._update_status()


class SensorPickDialog(QDialog):
    """传感器选择对话框"""
    def __init__(self, meta, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择传感器")
        self.resize(480, 520)
        self._meta = meta
        self._selected = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        # 搜索框
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索传感器名称…")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)

        # 列表
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._accept)
        lay.addWidget(self.list, 1)

        # 按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._populate()

    def _populate(self):
        self.list.clear()
        for sid, stype, name in self._meta:
            cat = classify_id(sid)
            cn_type = TYPE_META.get(stype, (stype, ""))[0]
            item = QListWidgetItem(f"[{cat}] {name}")
            item.setData(Qt.UserRole, (sid, stype, name))
            self.list.addItem(item)

    def _filter(self, text):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _accept(self):
        item = self.list.currentItem()
        if item:
            self._selected = item.data(Qt.UserRole)
        self.accept()

    def selected(self):
        return self._selected


# ────────────────────────────────────────────────────────────
# 硬件信息页
# ────────────────────────────────────────────────────────────
class InfoPage(QWidget):
    def __init__(self, data_provider=None, parent=None):
        super().__init__(parent)
        self._info = {}
        self._data_provider = data_provider  # callable -> (meta, data)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # 标题行 + 导出按钮
        title_row = QHBoxLayout()
        title = QLabel("当前硬件配置")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50;")
        export_btn = QPushButton("导出到桌面")
        export_btn.setObjectName("addBtn")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self._export)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(export_btn)
        lay.addLayout(title_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 4, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.addStretch()
        self.scroll.setWidget(self.content)
        lay.addWidget(self.scroll)

    def _export(self):
        """一键生成当前硬件信息并保存到桌面"""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            path = os.path.join(desktop, "硬件信息.txt")
            lines = []
            lines.append("=" * 46)
            lines.append("当前硬件配置信息")
            lines.append(f"生成时间：{__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S}")
            lines.append("=" * 46)
            lines.append("")

            info = self._info
            if info.get("cpu"):
                lines.append("【处理器】")
                lines.append(f"  型号：{info['cpu'].get('name', '--')}")
                lines.append(f"  规格：{info['cpu'].get('cores', '--')}")
                lines.append(f"  基础频率：{info['cpu'].get('clock', '--')}")
                lines.append("")
            if info.get("mb"):
                lines.append("【主板】")
                lines.append(f"  型号：{info['mb']}")
                lines.append(f"  BIOS：{info.get('bios', '--')}")
                lines.append("")
            if info.get("mem"):
                lines.append("【内存】")
                lines.append(f"  配置：{info['mem']}")
                lines.append("")
            if info.get("gpu"):
                lines.append("【显卡】")
                lines.append(f"  型号：{info['gpu']}")
                lines.append("")
            if info.get("disk"):
                lines.append("【硬盘】")
                for i, d in enumerate(info["disk"], 1):
                    lines.append(f"  硬盘{i}：{d}")
                lines.append("")

            # 当前传感器读数
            if self._data_provider:
                meta, data = self._data_provider()
                if meta:
                    lines.append("=" * 46)
                    lines.append("当前传感器读数")
                    lines.append("=" * 46)
                    lines.append("")
                    by_cat = {}
                    for sid, stype, name in meta:
                        cat = classify_id(sid)
                        by_cat.setdefault(cat, []).append((sid, stype, name))
                    for cat in ["主板", "CPU", "内存", "GPU", "存储", "其他"]:
                        items = by_cat.get(cat, [])
                        if not items:
                            continue
                        lines.append(f"【{cat}】")
                        for sid, stype, name in items:
                            v = data.get(sid)
                            sval = fmt_value(stype, v)
                            unit = TYPE_META.get(stype, (stype, ""))[1]
                            lines.append(f"  {name}：{sval} {unit}".rstrip())
                        lines.append("")

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            QMessageBox.information(self, "导出成功", f"已保存到：\n{path}")
        except Exception as ex:
            QMessageBox.warning(self, "导出失败", str(ex))

    def set_info(self, info):
        self._info = info
        # 清空旧卡片
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cards = [
            ("处理器", [
                ("型号", info.get("cpu", {}).get("name", "--")),
                ("规格", info.get("cpu", {}).get("cores", "--")),
                ("基础频率", info.get("cpu", {}).get("clock", "--")),
            ]),
            ("主板", [
                ("型号", info.get("mb", "--")),
                ("BIOS 版本", info.get("bios", "--")),
            ]),
            ("内存", [
                ("配置", info.get("mem", "--")),
            ]),
            ("显卡", [
                ("型号", info.get("gpu", "--")),
            ]),
        ]
        for card_title, kv in cards:
            card = self._make_card(card_title, kv)
            self.content_layout.insertWidget(self.content_layout.count() - 1, card)

        # 硬盘单独处理（多个）
        disks = info.get("disk", [])
        if disks:
            kv = [(f"硬盘 {i+1}", d) for i, d in enumerate(disks)]
            card = self._make_card("硬盘", kv)
            self.content_layout.insertWidget(self.content_layout.count() - 1, card)

    def _make_card(self, title, kv):
        card = QFrame()
        card.setObjectName("infoCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        t = QLabel(title)
        t.setObjectName("infoTitle")
        lay.addWidget(t)

        for k, v in kv:
            row = QHBoxLayout()
            key = QLabel(k)
            key.setObjectName("infoKey")
            val = QLabel(str(v))
            val.setObjectName("infoVal")
            val.setWordWrap(True)
            row.addWidget(key)
            row.addStretch()
            row.addWidget(val)
            lay.addLayout(row)
        return card


# ────────────────────────────────────────────────────────────
# 主窗口
# ────────────────────────────────────────────────────────────
def classify_id(sid):
    s = sid.lower()
    if "/lpc/" in s:
        return "主板"
    if "/intelcpu/" in s or "/amdcpu/" in s:
        return "CPU"
    if "/gpu-" in s:
        return "GPU"
    if "/nvme/" in s or "/hdd/" in s or "/ssd/" in s:
        return "存储"
    if "/ram/" in s or "/vram/" in s or "/memory/" in s:
        return "内存"
    return "其他"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电压监测 · Qt")
        self.resize(820, 560)

        icon_path = os.path.join(APP_DIR, "icon.jpg")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(APP_DIR, "图标.jpg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        hlay = QHBoxLayout(root)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(0)

        self.bookmark = QListWidget()
        self.bookmark.setObjectName("bookmark")
        self.bookmark.setFixedWidth(130)
        self.bookmark.currentRowChanged.connect(self._on_bookmark_changed)

        self.stack = QStackedWidget()
        hlay.addWidget(self.bookmark)
        hlay.addWidget(self.stack, 1)

        self._loading = QLabel("正在初始化硬件…")
        self._loading.setStyleSheet("color: #7a8ea6; font-size: 13px; padding: 20px;")
        self.stack.addWidget(self._loading)

        self._all_meta = []
        self._watch_page = None
        self._info_page = None
        self._pages = {}
        self._hw_info_cache = None
        self._latest_data = {}

        self.worker = HardwareWorker()
        self.worker.sensors_ready.connect(self._on_sensors_ready)
        self.worker.hw_info_ready.connect(self._on_hw_info)
        self.worker.data_ready.connect(self._on_data_ready)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_sensors_ready(self, meta):
        self._all_meta = meta

        categories = {
            "主板": CategoryPage(),
            "CPU": CategoryPage(),
            "内存": CategoryPage(),
            "GPU": CategoryPage(),
            "存储": CategoryPage(),
        }

        # 清 loading
        while self.stack.count() > 0:
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            if w is not self._loading:
                w.deleteLater()

        for sid, stype, name in meta:
            cat = classify_id(sid)
            if cat in categories:
                categories[cat].add_sensor(sid, stype, name)

        self._watch_page = WatchPage(lambda: self._all_meta)
        self._info_page = InfoPage(lambda: (self._all_meta, self._latest_data))
        # 硬件信息可能已在 InfoPage 创建前到达，应用缓存
        if self._hw_info_cache:
            self._info_page.set_info(self._hw_info_cache)

        self.bookmark.blockSignals(True)
        self.bookmark.clear()
        self._pages = {}
        order = ["主板", "CPU", "内存", "GPU", "存储", "观察", "硬件信息"]
        for cat_name in order:
            if cat_name in categories and len(categories[cat_name].rows) > 0:
                item = QListWidgetItem(cat_name)
                item.setSizeHint(QSize(0, 32))
                self.bookmark.addItem(item)
                self.stack.addWidget(categories[cat_name])
                self._pages[cat_name] = categories[cat_name]
        # 观察页 + 硬件信息页
        item = QListWidgetItem("观察")
        item.setSizeHint(QSize(0, 32))
        self.bookmark.addItem(item)
        self.stack.addWidget(self._watch_page)
        item = QListWidgetItem("硬件信息")
        item.setSizeHint(QSize(0, 32))
        self.bookmark.addItem(item)
        self.stack.addWidget(self._info_page)

        self.bookmark.blockSignals(False)
        self.bookmark.setCurrentRow(0)

    def _on_hw_info(self, info):
        self._hw_info_cache = info
        if self._info_page is not None:
            self._info_page.set_info(info)

    def _on_data_ready(self, data):
        self._latest_data = data
        cur = self.stack.currentWidget()
        if isinstance(cur, (CategoryPage, WatchPage)):
            cur.update_readings(data)

    def _on_failed(self, msg):
        QMessageBox.critical(
            self, "错误",
            f"硬件初始化失败：\n{msg}\n\n请确认：\n"
            "1. PawnIO 驱动已安装并运行\n"
            "2. LibreHardwareMonitorLib.dll 与本程序同目录")
        self._loading.setText("硬件初始化失败，请检查 PawnIO 驱动")

    def _on_bookmark_changed(self, row):
        self.stack.setCurrentIndex(row)

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
