import sys
import os
import ctypes
import time
import winreg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QVBoxLayout, QHBoxLayout, QSystemTrayIcon, QMessageBox, QMenu, QAction, QStyle
)

try:
    import serial.tools.list_ports
    HAVE_SERIAL = True
except ImportError:
    HAVE_SERIAL = False

# === Constants
VID = 0x1A86
PID = 0x55D3
DEFAULT_NAME = "USB-SERIAL CH340"
TARGET_DESC = "USB-Enhanced-SERIAL CH343"
MAX_NAME_LENGTH = 40


# === Helpers
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def get_device_info():
    for port in serial.tools.list_ports.comports():
        if port.vid == VID and port.pid == PID:
            return port.description or "Unknown", port.device
    return None, None


def list_usb_devices():
    return [
        f"{p.device} - {p.description or 'Unknown'}"
        for p in serial.tools.list_ports.comports()
    ]


def update_registry_name(vid, pid, new_name, com_port=None):
    key_path = f"SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{vid:04X}&PID_{pid:04X}"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS)
        for i in range(winreg.QueryInfoKey(key)[0]):
            subkey = winreg.EnumKey(key, i)
            subkey_path = f"{key_path}\\{subkey}"
            sub = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path, 0, winreg.KEY_ALL_ACCESS)
            suffix = f" ({com_port})" if com_port else ""
            max_len = MAX_NAME_LENGTH - len(suffix)
            final_name = f"{new_name[:max_len]}{suffix}"
            winreg.SetValueEx(sub, "FriendlyName", 0, winreg.REG_SZ, final_name)
            winreg.CloseKey(sub)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        return False


def reenumerate_usb():
    try:
        cfg = ctypes.WinDLL("cfgmgr32")
        dev_inst = ctypes.c_uint32()
        cfg.CM_Locate_DevNodeW(ctypes.byref(dev_inst), None, 0)
        cfg.CM_Reenumerate_DevNode(dev_inst, 0)
        time.sleep(2)
        return True
    except:
        return False


class SpoofTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clouds MAKCU WOOFER REMAKE v1.0")
        self.setFixedSize(540, 400)
        self.setFont(QFont("Consolas", 10, QFont.Normal))

        self.is_admin = is_admin()
        self.device_name, self.com_port = get_device_info()

        self.init_ui()
        self.apply_style()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("🔍 Status: Ready")
        self.device_list = QListWidget()
        self.refresh_devices()

        self.custom_name_input = QLineEdit()
        self.custom_name_input.setPlaceholderText("Enter custom spoof name")

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        btn_row = QHBoxLayout()
        restore_btn = QPushButton("♻ Restore")
        spoof_btn = QPushButton("🧪 Spoof Default")
        custom_btn = QPushButton("✨ Custom Name")
        export_btn = QPushButton("💾 Export .reg")
        refresh_btn = QPushButton("🔁 Refresh")

        restore_btn.clicked.connect(self.restore_default)
        spoof_btn.clicked.connect(self.spoof_default)
        custom_btn.clicked.connect(self.set_custom_name)
        export_btn.clicked.connect(self.export_reg)
        refresh_btn.clicked.connect(self.refresh_devices)

        for btn in (restore_btn, spoof_btn, custom_btn, export_btn, refresh_btn):
            btn_row.addWidget(btn)

        layout.addWidget(QLabel("Connected USB Devices:"))
        layout.addWidget(self.device_list)
        layout.addWidget(QLabel("Custom Spoof Name:"))
        layout.addWidget(self.custom_name_input)
        layout.addWidget(self.status_label)
        layout.addLayout(btn_row)
        layout.addWidget(QLabel("Output Log:"))
        layout.addWidget(self.log_output)

    def log(self, text):
        self.log_output.append(text)

    def refresh_devices(self):
        self.device_list.clear()
        if HAVE_SERIAL:
            for dev in list_usb_devices():
                self.device_list.addItem(dev)
            self.device_name, self.com_port = get_device_info()
            if self.device_name:
                self.status_label.setText(f"🟢 Found: {self.device_name} ({self.com_port})")
            else:
                self.status_label.setText("🔴 No compatible device found.")
        else:
            self.status_label.setText("Error: PySerial not available.")

    def restore_default(self):
        if not self.is_admin:
            return self.warn_admin()
        if not self.device_name:
            return self.warn_not_found()

        if update_registry_name(VID, PID, TARGET_DESC, self.com_port):
            reenumerate_usb()
            self.status_label.setText("✅ Restored to original.")
            self.log(f"Restored to: {TARGET_DESC}")
            self.refresh_devices()
        else:
            self.log("❌ Failed to update registry.")

    def spoof_default(self):
        if not self.is_admin:
            return self.warn_admin()
        if not self.device_name:
            return self.warn_not_found()

        if update_registry_name(VID, PID, DEFAULT_NAME, self.com_port):
            reenumerate_usb()
            self.status_label.setText("✅ Spoofed to default.")
            self.log(f"Spoofed to: {DEFAULT_NAME}")
            self.refresh_devices()
        else:
            self.log("❌ Failed to spoof device.")

    def set_custom_name(self):
        if not self.is_admin:
            return self.warn_admin()
        if not self.device_name:
            return self.warn_not_found()

        name = self.custom_name_input.text().strip()
        if not name:
            return self.log("⚠️ Name is empty.")
        if len(name) > 40:
            return self.log("⚠️ Name too long.")

        if update_registry_name(VID, PID, name, self.com_port):
            reenumerate_usb()
            self.status_label.setText(f"✅ Spoofed to: {name}")
            self.log(f"Spoofed to: {name}")
            self.refresh_devices()
        else:
            self.log("❌ Failed to apply custom name.")

    def export_reg(self):
        name = self.custom_name_input.text().strip()
        if not name:
            return self.log("⚠️ Enter a name first.")

        content = f"""Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{VID:04X}&PID_{PID:04X}]
"FriendlyName"="{name}"
"""
        try:
            with open("spoof_patch.reg", "w") as f:
                f.write(content)
            self.log("✅ Exported to: spoof_patch.reg")
        except Exception as e:
            self.log(f"❌ Export failed: {e}")

    def warn_admin(self):
        self.log("🔒 Requires Administrator privileges!")

    def warn_not_found(self):
        self.log("⚠️ Device not found. Please connect supported device.")

    def apply_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1b26;
                color: #c0caf5;
                font-family: Consolas;
                font-size: 10pt;
            }
            QLineEdit, QTextEdit, QListWidget {
                background-color: #2b2d3c;
                border: 1px solid #44475a;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton {
                background-color: #3b3d5e;
                border: 1px solid #44475a;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4b4d6e;
            }
            QLabel {
                margin-top: 8px;
            }
        """)


# === Main Run ===
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SpoofTool()
    window.show()
    sys.exit(app.exec_())