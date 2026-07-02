"""
ui.py — Redesigned Clean ILUM HUD + Full Settings Suite.

Layout:
- Top-left: Large floating clock + date
- Top-right: Two colored dots + hamburger menu (≡) → opens settings
- Right side: RAM % + CPU % + TEM °C readouts
- Center: I.L.U.M logo + waveform (via WebGL orb)
- Bottom-left: Bell / Folder / Calendar icon buttons + notification liquid-glass panel
- Bottom-center: Camera | Moon-Sun (suspend) | Chat-bubble icons
- Bottom-right: "I.L.U.M Pro" badge
- Floating Spotify widget (opens on click / command)
- Auto-sizing pill chat bar (hidden by default, opens on chat icon press)

Settings Dialog includes ALL tabs:
  CEREBRO, PERSONALIDAD, IA LOCAL, DISPOSITIVOS, APARIENCIA, RENDIMIENTO,
  SPOTIFY, WIDGETS E IDENTIDAD, MACROS
"""
from __future__ import annotations
import sys
import os
import json
import psutil
import urllib
from pathlib import Path
from datetime import datetime, timezone, timedelta

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QProgressBar, QDialog, QMessageBox,
    QComboBox, QCheckBox, QGraphicsDropShadowEffect,
    QScrollArea, QSlider, QFrame, QTabWidget, QColorDialog,
    QStackedWidget, QTextBrowser, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QUrl, pyqtSignal, pyqtSlot, QObject, QTimer,
    QSize, QThread, QRect, QRectF, QEvent, QPropertyAnimation,
    QEasingCurve, QPoint
)
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QMouseEvent, QPainterPath,
    QRegion, QResizeEvent, QPainter, QPen
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from shop import ShopWidget
from core.media_monitor import MediaMonitorWorker

try:
    import qtawesome as qta
    HAS_QTA = True
except ImportError:
    HAS_QTA = False

_BA_TZ = timezone(timedelta(hours=-5))


def get_bundled_path(*paths):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).joinpath(*paths)
    return Path(__file__).resolve().parent.joinpath(*paths)


# ── Theme palette ──────────────────────────────────────────────────────────
THEMES = {
    "cyan":   {"PRI": "#00d4ff", "PRI_DIM": "#005f77", "BG": "#050c14",
               "PANEL": "rgba(10, 22, 32, 0.35)", "BORDER": "rgba(0, 212, 255, 0.35)", "TEXT": "#7aeeff"},
    "green":  {"PRI": "#00ff88", "PRI_DIM": "#006633", "BG": "#040e08",
               "PANEL": "rgba(8, 26, 16, 0.35)", "BORDER": "rgba(0, 255, 136, 0.35)", "TEXT": "#7affcc"},
    "red":    {"PRI": "#ff3b30", "PRI_DIM": "#7a1a15", "BG": "#0e0404",
               "PANEL": "rgba(26, 8, 8, 0.35)", "BORDER": "rgba(255, 59, 48, 0.35)", "TEXT": "#ffaaaa"},
    "purple": {"PRI": "#a855f7", "PRI_DIM": "#5b21b6", "BG": "#07030f",
               "PANEL": "rgba(15, 6, 24, 0.35)", "BORDER": "rgba(168, 85, 247, 0.35)", "TEXT": "#c084fc"},
    "gold":   {"PRI": "#f59e0b", "PRI_DIM": "#78350f", "BG": "#0f0a02",
               "PANEL": "rgba(35, 28, 10, 0.35)", "BORDER": "rgba(245, 158, 11, 0.35)", "TEXT": "#fde68a"},
    "white":  {"PRI": "#e2e8f0", "PRI_DIM": "#64748b", "BG": "#050a14",
               "PANEL": "rgba(12, 22, 38, 0.35)", "BORDER": "rgba(226, 232, 240, 0.35)", "TEXT": "#cbd5e1"},
}

C_PRI = "#f59e0b"; C_PRI_DIM = "#78350f"; C_BG = "#0f0a02"
C_PANEL = "rgba(35, 28, 10, 0.70)"; C_BORDER = "rgba(245, 158, 11, 0.45)"; C_TEXT = "#fde68a"
GREEN = "#00ff88"; RED = "#ff3b30"
FONT_FAMILY = "Century Gothic"


def generate_custom_theme_colors(base_color: QColor):
    r, g, b = base_color.red(), base_color.green(), base_color.blue()
    pri = base_color.name()
    h, s, v, a = base_color.getHsv()
    dim_color = QColor.fromHsv(h, s, int(v * 0.45))
    pri_dim = dim_color.name()
    bg_color = QColor.fromHsv(h, int(s * 0.7), int(v * 0.08))
    bg = bg_color.name()
    panel_color = QColor.fromHsv(h, int(s * 0.6), int(v * 0.12))
    panel = f"rgba({panel_color.red()}, {panel_color.green()}, {panel_color.blue()}, 0.40)"
    border = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba({r},{g},{b},0.6), stop:1 rgba({r},{g},{b},0.1))"
    text_color = QColor.fromHsv(h, min(s, 50), max(v, 240))
    return {"PRI": pri, "PRI_DIM": pri_dim, "BG": bg,
            "PANEL": panel, "BORDER": border, "TEXT": text_color.name()}


def apply_theme_tokens(theme_name: str, custom_hex: str = None):
    global C_PRI, C_PRI_DIM, C_BG, C_PANEL, C_BORDER, C_TEXT
    if theme_name.lower() == "custom" and custom_hex:
        c = QColor(custom_hex)
        if c.isValid():
            t = generate_custom_theme_colors(c)
            THEMES["custom"] = t
        else:
            t = THEMES.get("gold")
    else:
        t = THEMES.get(theme_name.lower(), THEMES["gold"])
    C_PRI = t["PRI"]; C_PRI_DIM = t["PRI_DIM"]; C_BG = t["BG"]
    C_PANEL = t["PANEL"]; C_BORDER = t["BORDER"]; C_TEXT = t["TEXT"]
    try:
        from memory.config_manager import load_api_keys
        cfg = load_api_keys()
        if cfg.get("ilum_bg_color"):    C_BG    = cfg["ilum_bg_color"]
        if cfg.get("ilum_panel_color"): C_PANEL = cfg["ilum_panel_color"]
        if cfg.get("ilum_text_color"):  C_TEXT  = cfg["ilum_text_color"]
    except Exception:
        pass


def apply_glass_shadow(widget: QWidget, blur_radius: int = 30, x_offset: int = 0,
                       y_offset: int = 10, alpha: int = 150):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setColor(QColor(0, 0, 0, alpha))
    shadow.setOffset(x_offset, y_offset)
    widget.setGraphicsEffect(shadow)


def hex_to_bgr(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.strip()
    if hex_str.startswith("rgba"):
        try:
            parts = hex_str.replace("rgba(", "").replace(")", "").split(",")
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            return b, g, r
        except Exception:
            return 11, 158, 245
    elif hex_str.startswith("#"):
        try:
            hv = hex_str.lstrip("#")
            return int(hv[4:6], 16), int(hv[2:4], 16), int(hv[0:2], 16)
        except Exception:
            return 11, 158, 245
    return 11, 158, 245


try:
    from memory.config_manager import load_api_keys
    _cfg = load_api_keys()
    apply_theme_tokens(_cfg.get("ilum_theme", "gold"), _cfg.get("ilum_custom_theme_color", ""))
    FONT_FAMILY = _cfg.get("ilum_font_family", "Century Gothic")
except Exception:
    apply_theme_tokens("gold")


# ═══════════════════════════════════════════════════════════════════════════
#  WebBridge + CustomParticleOrb
# ═══════════════════════════════════════════════════════════════════════════

class WebBridge(QObject):
    def __init__(self, orb): super().__init__(); self.orb = orb
    @pyqtSlot()
    def toggle_mute(self):
        if self.orb.ui: self.orb.ui._win._toggle_mute()
    @pyqtSlot()
    def request_theme(self): QTimer.singleShot(0, self.orb.sync_theme)


class CustomParticleOrb(QWidget):
    audio_signal = pyqtSignal(float)
    state_signal = pyqtSignal(str)
    theme_signal = pyqtSignal()

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        def get_base_dir():
            if getattr(sys, "frozen", False): return Path(sys.executable).parent
            return Path(__file__).resolve().parent
        BASE_DIR = get_base_dir()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.web_view = QWebEngineView(self)
        self.web_view.setStyleSheet("background: transparent;")
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        try:
            from PyQt6.QtWebEngineCore import QWebEngineSettings
            s = self.web_view.settings()
            s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
        except Exception: pass
        self.channel = QWebChannel()
        self.bridge = WebBridge(self)
        self.channel.registerObject("pyBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        sphere_path = get_bundled_path("assets", "sphere.html")
        print(f"[ORB] Loading sphere.html from: {sphere_path}")
        self.web_view.setUrl(QUrl.fromLocalFile(str(sphere_path.absolute())))
        layout.addWidget(self.web_view)
        self.setLayout(layout)
        self.audio_signal.connect(self._safe_set_audio)
        self.state_signal.connect(self._safe_set_state)
        self.theme_signal.connect(self._safe_sync_theme)
        self.web_view.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, ok):
        print(f"[ORB] loadFinished: {ok}")
        if ok:
            self.sync_theme()
            self.set_state("MUTED" if self.ui.muted else "LISTENING")
            try:
                from memory.config_manager import load_api_keys
                cfg = load_api_keys()
                q = cfg.get("performance_quality", 80)
                self.web_view.page().runJavaScript(f"if(window.updatePerformance)window.updatePerformance({q});")
            except Exception: pass

    def sync_theme(self): self.theme_signal.emit()
    def set_audio(self, level: float): self.audio_signal.emit(level)
    def set_state(self, state: str): self.state_signal.emit(state)

    def _safe_sync_theme(self):
        colors = {'PRI': C_PRI, 'PRI_DIM': C_PRI_DIM, 'TEXT': C_TEXT, 'BG': C_BG}
        self.web_view.page().runJavaScript(
            f"if(window.setThemeColors)window.setThemeColors({json.dumps(colors)});")

    def _safe_set_audio(self, level: float):
        self.web_view.page().runJavaScript(f"if(window.updateVolume)window.updateVolume({level});")

    def _safe_set_state(self, state: str):
        self.web_view.page().runJavaScript(f"if(window.updateState)window.updateState('{state}');")


# ═══════════════════════════════════════════════════════════════════════════
#  CameraPreviewWindow
# ═══════════════════════════════════════════════════════════════════════════

class CameraPreviewWindow(QWidget):
    def __init__(self, shared_thread=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(370, 320)
        self.shared_thread = shared_thread
        self.drag_position = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        container = QFrame(self)
        container.setObjectName("CameraContainer")
        container.setStyleSheet(f"""
            QFrame#CameraContainer {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(12,10,5,0.60), stop:1 rgba(2,2,2,0.85));
                border: 1.8px solid {C_PRI};
                border-radius: 16px;
            }}
            QLabel {{ color:{C_TEXT}; font-family:'{FONT_FAMILY}',sans-serif; }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20); shadow.setColor(QColor(0,0,0,190)); shadow.setOffset(0,6)
        container.setGraphicsEffect(shadow)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(10,10,10,10); c_layout.setSpacing(6)
        title_layout = QHBoxLayout(); title_layout.setSpacing(6)
        self.lbl_title_icon = QLabel(self)
        if HAS_QTA: self.lbl_title_icon.setPixmap(qta.icon('fa5s.video', color=C_PRI).pixmap(11,11))
        title_label = QLabel("PILOTO GESTUAL  ·  HUD", self)
        title_label.setStyleSheet(f"font-weight:bold;font-size:9px;letter-spacing:1.8px;color:{C_PRI};background:transparent;border:none;")
        self.btn_min = QPushButton("–", self); self.btn_min.setFixedSize(22,22)
        self.btn_min.setStyleSheet(f"QPushButton{{background:transparent;color:{C_PRI};border:1px solid rgba(245,158,11,0.4);border-radius:11px;font-size:13px;font-weight:bold;}}QPushButton:hover{{background-color:rgba(245,158,11,0.25);}}")
        self.btn_min.clicked.connect(self.hide)
        self.btn_close = QPushButton("×", self); self.btn_close.setFixedSize(22,22)
        self.btn_close.setStyleSheet(f"QPushButton{{background:transparent;color:{C_PRI};border:1px solid rgba(245,158,11,0.4);border-radius:11px;font-size:14px;font-weight:bold;}}QPushButton:hover{{background-color:#ff3b30;color:white;border-color:#ff3b30;}}")
        self.btn_close.clicked.connect(self.hide)
        title_layout.addWidget(self.lbl_title_icon); title_layout.addWidget(title_label)
        title_layout.addStretch(); title_layout.addWidget(self.btn_min); title_layout.addWidget(self.btn_close)
        c_layout.addLayout(title_layout)
        self.lbl_feed = QLabel(self); self.lbl_feed.setFixedSize(346,226)
        self.lbl_feed.setStyleSheet(f"background-color:rgba(0,0,0,0.45);border-radius:10px;border:1.2px dashed rgba(245,158,11,0.40);")
        self.lbl_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.lbl_feed)
        footer = QHBoxLayout(); footer.setSpacing(4)
        self.lbl_status = QLabel("Buscando mano...", self)
        self.lbl_status.setStyleSheet(f"font-size:9px;color:{C_TEXT};font-style:italic;background:transparent;border:none;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        self.lbl_bg_indicator = QLabel("Activo en 2do plano", self)
        self.lbl_bg_indicator.setStyleSheet("font-size:8px;color:#00ff88;font-weight:bold;background:transparent;border:none;")
        footer.addWidget(self.lbl_status); footer.addStretch(); footer.addWidget(self.lbl_bg_indicator)
        c_layout.addLayout(footer)
        layout.addWidget(container)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
    def on_frame_received(self, q_img, status):
        from PyQt6.QtGui import QPixmap
        if not self.isVisible(): return
        pixmap = QPixmap.fromImage(q_img).scaled(self.lbl_feed.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        self.lbl_feed.setPixmap(pixmap); self.lbl_status.setText(f"Piloto: {status}")
    def on_active_changed(self, active):
        if not active: self.lbl_status.setText("Cámara Desconectada"); self.lbl_feed.clear()
    def attach_thread(self, thread):
        self.shared_thread = thread
        thread.frame_signal.connect(self.on_frame_received)
        thread.active_signal.connect(self.on_active_changed)
    def closeEvent(self, event): event.ignore(); self.hide()


# ═══════════════════════════════════════════════════════════════════════════
#  HUD Overlay Elements
# ═══════════════════════════════════════════════════════════════════════════

class ClockWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setObjectName("ClockWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.lbl_time = QLabel("12:00:00 AM")
        font_t = QFont(FONT_FAMILY, 28, QFont.Weight.Bold)
        font_t.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        self.lbl_time.setFont(font_t)
        self.lbl_time.setStyleSheet("color: white; border: none; background: transparent;")
        layout.addWidget(self.lbl_time)
        self.lbl_date = QLabel("Monday, 09 June 2026")
        font_d = QFont(FONT_FAMILY, 11)
        self.lbl_date.setFont(font_d)
        self.lbl_date.setStyleSheet("color: rgba(255,255,255,0.95); border: none; background: transparent; letter-spacing: 0.5px;")
        layout.addWidget(self.lbl_date)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.tick()

    def tick(self):
        now = datetime.now()
        self.lbl_time.setText(now.strftime("%I:%M:%S %p"))
        self.lbl_date.setText(now.strftime("%A, %d %B %Y"))

    def update_style(self):
        self.setStyleSheet("QWidget#ClockWidget { background: transparent; border: none; }")


class SystemMonitorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setObjectName("SysMonitor")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        neon_white = "rgba(255,255,255,0.95)"

        # ───── RAM ─────
        self.row_ram = QHBoxLayout()
        self.row_ram.setSpacing(6)
        self.row_ram.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_ram_val = QLabel("RAM 0%")
        self.lbl_ram_val.setStyleSheet(f"color: {neon_white}; font-size: 11px; font-weight: 700; background:transparent; border:none; letter-spacing:0.5px;")
        self.lbl_ram_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if HAS_QTA:
            self.icon_ram = QLabel()
            self.icon_ram.setPixmap(qta.icon('fa5s.microchip', color='#ffffff').pixmap(13, 13))
            self.row_ram.addWidget(self.lbl_ram_val)
            self.row_ram.addWidget(self.icon_ram)
        else:
            self.row_ram.addWidget(self.lbl_ram_val)

        layout.addLayout(self.row_ram)

        # ───── CPU ─────
        self.row_cpu = QHBoxLayout()
        self.row_cpu.setSpacing(6)
        self.row_cpu.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_cpu_val = QLabel("CPU 0%")
        self.lbl_cpu_val.setStyleSheet(f"color: {neon_white}; font-size: 11px; font-weight: 700; background:transparent; border:none; letter-spacing:0.5px;")
        self.lbl_cpu_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if HAS_QTA:
            self.icon_cpu = QLabel()
            self.icon_cpu.setPixmap(qta.icon('fa5s.tachometer-alt', color='#ffffff').pixmap(13, 13))
            self.row_cpu.addWidget(self.lbl_cpu_val)
            self.row_cpu.addWidget(self.icon_cpu)
        else:
            self.row_cpu.addWidget(self.lbl_cpu_val)

        layout.addLayout(self.row_cpu)

        # ───── DISK ─────
        self.row_disk = QHBoxLayout()
        self.row_disk.setSpacing(6)
        self.row_disk.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_disk_val = QLabel("DSK 0%")
        self.lbl_disk_val.setStyleSheet(f"color: {neon_white}; font-size: 11px; font-weight: 700; background:transparent; border:none; letter-spacing:0.5px;")
        self.lbl_disk_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if HAS_QTA:
            self.icon_disk = QLabel()
            self.icon_disk.setPixmap(qta.icon('fa5s.hdd', color='#ffffff').pixmap(13, 13))
            self.row_disk.addWidget(self.lbl_disk_val)
            self.row_disk.addWidget(self.icon_disk)
        else:
            self.row_disk.addWidget(self.lbl_disk_val)

        layout.addLayout(self.row_disk)

        # ───── TEMPERATURA ─────
        self.row_tem = QHBoxLayout()
        self.row_tem.setSpacing(6)
        self.row_tem.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_tem_val = QLabel("TEM --°C")
        self.lbl_tem_val.setStyleSheet(f"color: {neon_white}; font-size: 11px; font-weight: 700; background:transparent; border:none; letter-spacing:0.5px;")
        self.lbl_tem_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if HAS_QTA:
            self.icon_tem = QLabel()
            self.icon_tem.setPixmap(qta.icon('fa5s.thermometer-half', color='#ffffff').pixmap(13, 13))
            self.row_tem.addWidget(self.lbl_tem_val)
            self.row_tem.addWidget(self.icon_tem)
        else:
            self.row_tem.addWidget(self.lbl_tem_val)

        layout.addLayout(self.row_tem)

        # ⏱️ TIMER
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)

        self.update_stats()

    def update_stats(self):
        try:
            ram = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent(interval=None)
            disk = psutil.disk_usage('/').percent

            self.lbl_ram_val.setText(f"RAM {int(ram)}%")
            if hasattr(self, 'lbl_cpu_val'): self.lbl_cpu_val.setText(f"CPU {int(cpu)}%")
            if hasattr(self, 'lbl_disk_val'): self.lbl_disk_val.setText(f"DSK {int(disk)}%")
        except Exception:
            pass

        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for k in ("coretemp", "cpu_thermal", "acpitz"):
                    if k in temps and temps[k]:
                        self.lbl_tem_val.setText(f"TEM {int(temps[k][0].current)}°C")
                        return
            self.lbl_tem_val.setText("TEM --°C")
        except Exception:
            self.lbl_tem_val.setText("TEM --°C")


class HUDIconButton(QPushButton):
    def __init__(self, icon_name: str, size: int = 36, icon_size: int = 14,
                 color: str = "#d8dbe2", parent=None):
        super().__init__(parent)

        self.setFixedSize(size, size)

        self._icon_name = icon_name
        self._color = color
        self._icon_size = icon_size
        self._active = False

        if HAS_QTA:
            self.setIcon(qta.icon(icon_name, color=color))
            self.setIconSize(QSize(icon_size, icon_size))

        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        self.glow = QGraphicsDropShadowEffect(self)
        self.glow.setBlurRadius(18)
        self.glow.setColor(QColor(color))
        self.glow.setOffset(0, 0)
        self.setGraphicsEffect(self.glow)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()

    def update_style(self):
        from ui import C_PRI
        c_pri_color = QColor(C_PRI)
        r, g, b = c_pri_color.red(), c_pri_color.green(), c_pri_color.blue()

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
        """)

        # Set the icon color based on active status
        if HAS_QTA:
            if self._active:
                # Active state: smoky logo color
                c = QColor(r, g, b, 160)
                self.setIcon(qta.icon(self._icon_name, color=c))
                self.glow.setColor(c)
            else:
                # Normal state: gray / plomo
                c = QColor("#d8dbe2")
                self.setIcon(qta.icon(self._icon_name, color=c))
                self.glow.setColor(c)

    def set_active(self, active: bool, active_color: str = "#ffffff"):
        self._active = active
        self.update_style()

    def enterEvent(self, event):
        # Hover: strong white (glow!)
        if HAS_QTA:
            self.setIcon(qta.icon(self._icon_name, color=QColor("#ffffff")))
            self.glow.setColor(QColor("#ffffff"))
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Back to normal or active color
        if HAS_QTA:
            if self._active:
                from ui import C_PRI
                c_pri_color = QColor(C_PRI)
                r, g, b = c_pri_color.red(), c_pri_color.green(), c_pri_color.blue()
                c = QColor(r, g, b, 160)
                self.setIcon(qta.icon(self._icon_name, color=c))
                self.glow.setColor(c)
            else:
                c = QColor("#d8dbe2")
                self.setIcon(qta.icon(self._icon_name, color=c))
                self.glow.setColor(c)
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Pressed: smoky logo color (darker)
            if HAS_QTA:
                from ui import C_PRI
                c_pri_color = QColor(C_PRI)
                r, g, b = c_pri_color.red(), c_pri_color.green(), c_pri_color.blue()
                c = QColor(r, g, b, 120)
                self.setIcon(qta.icon(self._icon_name, color=c))
                self.glow.setColor(c)
                self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.underMouse():
                # Release inside: back to hover (strong white)
                if HAS_QTA:
                    self.setIcon(qta.icon(self._icon_name, color=QColor("#ffffff")))
                    self.glow.setColor(QColor("#ffffff"))
            else:
                # Release outside: back to normal or active color
                if HAS_QTA:
                    if self._active:
                        from ui import C_PRI
                        c_pri_color = QColor(C_PRI)
                        r, g, b = c_pri_color.red(), c_pri_color.green(), c_pri_color.blue()
                        c = QColor(r, g, b, 160)
                        self.setIcon(qta.icon(self._icon_name, color=c))
                        self.glow.setColor(c)
                    else:
                        c = QColor("#d8dbe2")
                        self.setIcon(qta.icon(self._icon_name, color=c))
                        self.glow.setColor(c)
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        from PyQt6.QtWidgets import QStyleOptionButton, QStyle
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.icon = QIcon()  # Remove icon from style option to bypass default pressed darkening

        self.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, painter, self)

        icon = self.icon()
        if not icon.isNull():
            sz = self.iconSize()
            x = (self.width() - sz.width()) // 2
            y = (self.height() - sz.height()) // 2
            rect = QRect(x, y, sz.width(), sz.height())
            icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter, QIcon.Mode.Normal, QIcon.State.Off)

        painter.end()


class BottomDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BottomDock")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 🟡 ICONOS GRIS HUMO VISIBLE
        icon_color = "#d8dbe2"

        self.btn_camera  = HUDIconButton('fa5s.video',       36, 14, icon_color, self)
        self.btn_suspend = HUDIconButton('fa5s.moon',        36, 14, icon_color, self)
        self.btn_chat    = HUDIconButton('fa5s.comment-dots',36, 14, icon_color, self)

        layout.addWidget(self.btn_camera)
        layout.addWidget(self.btn_suspend)
        layout.addWidget(self.btn_chat)

        # 🔥 DOCK TRANSPARENTE
        self.setStyleSheet(
            "QWidget#BottomDock {"
            "background: transparent;"
            "border: none;"
            "}"
        )

        # 💎 SIN SOMBRA GLASS
        # apply_glass_shadow(self, blur_radius=18, y_offset=4, alpha=120)

    def update_suspend_icon(self, is_sleeping: bool):
        icon = 'fa5s.sun' if is_sleeping else 'fa5s.moon'
        self.btn_suspend._icon_name = icon

        if HAS_QTA:
            color = "#ffffff" if self.btn_suspend._active else "#d8dbe2"
            self.btn_suspend.setIcon(qta.icon(icon, color=color))


class BottomLeftDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("BottomLeftDock")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft |
            Qt.AlignmentFlag.AlignVCenter
        )

        icon_color = "#d8dbe2"

        # 🔔 Campana con círculo glass
        self.btn_bell = HUDIconButton(
            'fa5s.bell',
            36,
            14,
            icon_color,
            self
        )

        # 📁 Carpeta CON CÍRCULO GLASS
        self.btn_folder = HUDIconButton(
            'fa5s.folder',
            36,
            14,
            icon_color,
            self
        )

        # 📅 Calendario CON CÍRCULO GLASS
        self.btn_calendar = HUDIconButton(
            'fa5s.calendar-alt',
            36,
            14,
            icon_color,
            self
        )

        layout.addWidget(self.btn_bell)
        layout.addWidget(self.btn_folder)
        layout.addWidget(self.btn_calendar)

        self.setStyleSheet("""
            QWidget#BottomLeftDock{
                background: transparent;
                border: none;
            }
        """)

    def set_notification(self, has_notif: bool):

        color = "#f59e0b" if has_notif else "#d8dbe2"

        self.btn_bell._color = color
        self.btn_bell.set_active(
            has_notif,
            "#f59e0b"
        )

        if HAS_QTA:
            self.btn_bell.setIcon(
                qta.icon(
                    'fa5s.bell',
                    color=color
                )
            )


class TopRightDock(QWidget):
    hamburger_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopRightDock")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        dots_layout = QHBoxLayout()
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(8)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        # 🟣 MINIMIZAR (Morado)
        self.dot1 = QPushButton()
        self.dot1.setFixedSize(12, 12)
        self.dot1.setStyleSheet("""
        QPushButton {
            background:#a855f7;
            border-radius:6px;
            border:none;
        }
        QPushButton:hover {
            background:#c084fc;
        }
        """)
        self.dot1.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dot1.clicked.connect(lambda: self.window().showMinimized())

        # 🔵 CERRAR (Cyan)
        self.dot2 = QPushButton()
        self.dot2.setFixedSize(12, 12)
        self.dot2.setStyleSheet("""
        QPushButton {
            background:#06b6d4;
            border-radius:6px;
            border:none;
        }
        QPushButton:hover {
            background:#22d3ee;
        }
        """)
        self.dot2.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dot2.clicked.connect(lambda: self.window().close())

        dots_layout.addWidget(self.dot1)
        dots_layout.addWidget(self.dot2)
        layout.addLayout(dots_layout)

        # ☰ MENÚ
        self.btn_menu = QPushButton("≡")
        self.btn_menu.setFixedSize(30, 26)
        self.btn_menu.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        self.btn_menu.setStyleSheet("""
        QPushButton {
            background: transparent;
            color: white;
            border: none;
            font-size: 18px;
        }
        QPushButton:hover {
            color: white;
        }
        """)
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.clicked.connect(self.hamburger_clicked.emit)

        layout.addWidget(self.btn_menu, alignment=Qt.AlignmentFlag.AlignRight)

        self.setFixedHeight(60)

class ProBadge(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.update_text()

    def update_text(self, ai_name: str = "I.L.U.M"):

        self.setText(
            f"""
            <span style="
                color:#d8dbe2;
                font-weight:500;
                letter-spacing:0.5px;
            ">
                {ai_name}
            </span>

            <span style="
                color:#b56cff;
                font-weight:700;
                background-color:rgba(35,20,55,0.85);
                border:1px solid rgba(181,108,255,0.55);
                border-radius:3px;
                padding:1px 6px;
            ">
                Pro
            </span>
            """
        )

        self.setTextFormat(Qt.TextFormat.RichText)

        self.setStyleSheet("""
            QLabel {
                font-size: 12px;
                background: transparent;
                border: none;
            }
        """)

        self.adjustSize()


class NotificationCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NotifCard")
        self.setFixedWidth(310)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 🔥 GLASS CLEAN PRO
        self.setStyleSheet("""
        QWidget#NotifCard {
            background: rgba(12,12,16,0.80);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 18px;
        }
        QLabel {
            background: transparent;
            border: none;
            color: rgba(245,245,250,0.96);
        }
        """)

        apply_glass_shadow(self, blur_radius=24, y_offset=6, alpha=120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # 🔔 HEADER
        hdr = QHBoxLayout()
        self.icon_lbl = QLabel()

        if HAS_QTA:
            self.icon_lbl.setPixmap(qta.icon('fa5s.bell', color='#ffffff').pixmap(14, 14))

        self.title_lbl = QLabel("Notificaciones")
        self.title_lbl.setStyleSheet("font-size:11px; font-weight:700; color:#ffffff;")

        self.btn_close_notif = QPushButton("×")
        self.btn_close_notif.setFixedSize(20, 20)
        self.btn_close_notif.setStyleSheet("""
        QPushButton {
            background: transparent;
            color: rgba(255,255,255,0.5);
            border: none;
            font-size: 14px;
        }
        QPushButton:hover {
            color: #ffffff;
        }
        """)

        hdr.addWidget(self.icon_lbl)
        hdr.addWidget(self.title_lbl)
        hdr.addStretch()
        hdr.addWidget(self.btn_close_notif)

        layout.addLayout(hdr)

        # 🔥 SIN COLORES FEOS
        self.default_item = self._make_item("ILUM", "Sistema iniciado correctamente.")
        self.update_item  = self._make_item("Actualización", "Nueva versión disponible.")
        self.secure_item  = self._make_item("Sistema protegido", "Protección activa correctamente.")

        layout.addWidget(self.default_item)
        layout.addWidget(self.update_item)
        layout.addWidget(self.secure_item)

        self.layout_ref = layout
        self.hide()

    def _make_item(self, title: str, body: str, thumbnail_path=None) -> QFrame:
        frame = QFrame()

        # 💎 ULTRA CLEAN (AQUÍ ESTABA EL PROBLEMA)
        frame.setObjectName("NotifItem")
        frame.setStyleSheet("""
        QFrame#NotifItem {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
        }
        QLabel {
            background: transparent;
            border: none;
        }
        """)

        fl = QHBoxLayout(frame)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(10)

        txt = QVBoxLayout()

        t = QLabel(title)
        t.setStyleSheet("""
            background: transparent;
            border: none;
            font-size:11px;
            font-weight:700;
            color:#ffffff;
        """)

        b = QLabel(body)
        b.setWordWrap(True)
        b.setStyleSheet("""
            background: transparent;
            border: none;
            font-size:10px;
            color:rgba(255,255,255,0.85);
        """)

        txt.addWidget(t)
        txt.addWidget(b)

        fl.addLayout(txt)

        return frame

    def push_notification(self, title: str, body: str,
                          thumbnail_path=None, action_label: str = None, action_callback=None):

        item = self._make_item(title, body, thumbnail_path)

        if action_label and action_callback:
            btn = QPushButton(action_label)
            btn.setFixedHeight(26)
            btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.12);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 10px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.20);
            }
            """)
            btn.clicked.connect(action_callback)
            item.layout().addWidget(btn)

        self.layout_ref.insertWidget(1, item)
        self.adjustSize()
        self.show()


class FloatingSpotifyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SpotifyFloat")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 120)
        self.drag_position = None

        # 💎 GLASS CLEAN
        self.setStyleSheet("""
QWidget#SpotifyFloat {
    background: rgba(18,18,22,0.75);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 24px;
}

QLabel {
    background: transparent;
    border: none;
    color: rgba(245,245,250,0.96);
}

QPushButton {
    background: transparent;
    border: none;
}

QPushButton:hover {
    background: rgba(255,255,255,0.06);
    border-radius: 15px;
}
""")

        apply_glass_shadow(self, blur_radius=35, y_offset=8, alpha=180)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # 🎧 ART
        self.lbl_art = QLabel()
        self.lbl_art.setFixedSize(50, 50)
        self.lbl_art.setStyleSheet("""
        background: rgba(255,255,255,0.06);
        border-radius: 8px;
        """)
        self.lbl_art.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if HAS_QTA:
            self.lbl_art.setPixmap(qta.icon('fa5b.spotify', color='rgba(255,255,255,0.7)').pixmap(20, 20))

        layout.addWidget(self.lbl_art)

        # 📄 RIGHT
        right = QVBoxLayout()
        right.setSpacing(4)

        # 🔝 TOP ROW
        top_row = QHBoxLayout()
        info_col = QVBoxLayout()
        info_col.setSpacing(1)

        self.lbl_track = QLabel("Not Playing")
        self.lbl_track.setStyleSheet("""
        font-size:11px;
        font-weight:600;
        color:#ffffff;
        """)

        self.lbl_artist = QLabel("Spotify")
        self.lbl_artist.setStyleSheet("""
        font-size:10px;
        color:rgba(200,200,210,0.70);
        """)

        info_col.addWidget(self.lbl_track)
        info_col.addWidget(self.lbl_artist)

        top_row.addLayout(info_col)
        top_row.addStretch()

        if HAS_QTA:
            self.btn_shuffle = QPushButton()
            self.btn_shuffle.setFixedSize(20, 20)
            self.btn_shuffle.setIcon(qta.icon('fa5s.random', color='rgba(200,200,210,0.6)'))
            self.btn_shuffle.setIconSize(QSize(12, 12))
            top_row.addWidget(self.btn_shuffle)

        right.addLayout(top_row)

        # 📊 PROGRESS
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(3)
        self.prog_bar.setStyleSheet("""
        QProgressBar {
            background: rgba(255,255,255,0.08);
            border: none;
            border-radius: 2px;
        }
        QProgressBar::chunk {
            background: rgba(255,255,255,0.85);
            border-radius: 2px;
        }
        """)

        self.lbl_time_l = QLabel("0:00")
        self.lbl_time_l.setStyleSheet("font-size:8px;color:rgba(200,200,210,0.55);")

        self.lbl_time_r = QLabel("0:00")
        self.lbl_time_r.setStyleSheet("font-size:8px;color:rgba(200,200,210,0.55);")

        prog_row = QHBoxLayout()
        prog_row.setSpacing(4)
        prog_row.addWidget(self.lbl_time_l)
        prog_row.addWidget(self.prog_bar, 1)
        prog_row.addWidget(self.lbl_time_r)

        right.addLayout(prog_row)

        # 🎮 CONTROLES
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        ctrl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if HAS_QTA:
            self.btn_prev = QPushButton()
            self.btn_prev.setFixedSize(26, 26)
            self.btn_prev.setIcon(qta.icon('fa5s.step-backward', color='rgba(220,220,230,0.85)'))
            self.btn_prev.setIconSize(QSize(11, 11))

            self.btn_play = QPushButton()
            self.btn_play.setFixedSize(30, 30)
            self.btn_play.setIcon(qta.icon('fa5s.pause', color='rgba(10,10,15,0.95)'))
            self.btn_play.setIconSize(QSize(13, 13))
            self.btn_play.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.85);
                border-radius: 15px;
            }
            QPushButton:hover {
                background: white;
            }
            """)

            self.btn_next = QPushButton()
            self.btn_next.setFixedSize(26, 26)
            self.btn_next.setIcon(qta.icon('fa5s.step-forward', color='rgba(220,220,230,0.85)'))
            self.btn_next.setIconSize(QSize(11, 11))

            ctrl.addWidget(self.btn_prev)
            ctrl.addWidget(self.btn_play)
            ctrl.addWidget(self.btn_next)

            self.btn_prev.clicked.connect(lambda: self._press("prevtrack"))
            self.btn_play.clicked.connect(lambda: self._press("playpause"))
            self.btn_next.clicked.connect(lambda: self._press("nexttrack"))

        right.addLayout(ctrl)
        layout.addLayout(right)

        # ⏱️ TIMER
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_playback_info)
        self.timer.start(5000)

        QTimer.singleShot(800, self.update_playback_info)
        self.hide()

        # 🔥 CARGAR POSICIÓN GUARDADA AL INICIAR
        QTimer.singleShot(100, self.load_position)

    def load_position(self):
        """Carga la posición guardada del widget"""
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            w_name = self.__class__.__name__
            x = cfg.get(f"widget_pos_{w_name}_x")
            y = cfg.get(f"widget_pos_{w_name}_y")
            if x is not None and y is not None:
                self.move(int(x), int(y))
                print(f"[Spotify] Posición cargada: X={x}, Y={y}")
            else:
                print("[Spotify] No hay posición guardada, usando por defecto")
        except Exception as e:
            print(f"[Spotify] Error cargando posición: {e}")

    def _press(self, key):
        try:
            import logging
            logging.getLogger('spotipy').setLevel(logging.CRITICAL)

            from memory.config_manager import load_api_keys, BASE_DIR
            cfg = load_api_keys()

            cid = cfg.get("spotify_client_id")
            csec = cfg.get("spotify_client_secret")

            if cid and csec:
                import spotipy
                from spotipy.oauth2 import SpotifyOAuth

                sp_oauth = SpotifyOAuth(
                    client_id=cid,
                    client_secret=csec,
                    redirect_uri=cfg.get("spotify_redirect_uri", "http://127.0.0.1:8765/callback"),
                    scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
                    open_browser=False,
                    cache_path=str(BASE_DIR / ".spotify_cache")
                )

                tok = sp_oauth.get_cached_token()

                if tok:
                    sp = spotipy.Spotify(auth_manager=sp_oauth)
                    devs = sp.devices().get("devices", [])
                    did = next((d["id"] for d in devs if d["is_active"]), devs[0]["id"] if devs else None)

                    if key == "playpause":
                        c = sp.current_playback()
                        if c:
                            (sp.pause_playback if c["is_playing"] else sp.start_playback)(device_id=did)
                    elif key == "nexttrack":
                        sp.next_track(device_id=did)
                    elif key == "prevtrack":
                        sp.previous_track(device_id=did)

                    QTimer.singleShot(400, self.update_playback_info)
                    return
        except Exception:
            pass

        try:
            import pyautogui
            pyautogui.press({
                "playpause": "playpause",
                "nexttrack": "nexttrack",
                "prevtrack": "prevtrack"
            }[key])
        except Exception:
            pass

    def update_playback_info(self):
        try:
            import logging
            logging.getLogger('spotipy').setLevel(logging.CRITICAL)

            from memory.config_manager import load_api_keys, BASE_DIR
            cfg = load_api_keys()

            cid = cfg.get("spotify_client_id")
            csec = cfg.get("spotify_client_secret")

            if not cid or not csec:
                return

            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            sp_oauth = SpotifyOAuth(
                client_id=cid,
                client_secret=csec,
                redirect_uri=cfg.get("spotify_redirect_uri", "http://127.0.0.1:8765/callback"),
                scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
                open_browser=False,
                cache_path=str(BASE_DIR / ".spotify_cache")
            )

            tok = sp_oauth.get_cached_token()
            if not tok:
                return

            sp = spotipy.Spotify(auth_manager=sp_oauth)
            curr = sp.current_playback()

            if curr and curr.get("item"):
                if not self.isVisible() and hasattr(self.window(), "animate_show_widget"):
                    self.window().animate_show_widget(self)
                item = curr["item"]

                name = item["name"][:28] + ("…" if len(item["name"]) > 28 else "")
                artist = item["artists"][0]["name"][:30] + ("…" if len(item["artists"][0]["name"]) > 30 else "")

                self.lbl_track.setText(name)
                self.lbl_artist.setText(artist)

                dur = item["duration_ms"] // 1000
                pos = curr["progress_ms"] // 1000

                self.prog_bar.setValue(int(pos / dur * 100) if dur else 0)

                self.lbl_time_l.setText(f"{pos//60}:{pos%60:02d}")
                self.lbl_time_r.setText(f"{dur//60}:{dur%60:02d}")

                if HAS_QTA:
                    icon = 'fa5s.pause' if curr["is_playing"] else 'fa5s.play'
                    self.btn_play.setIcon(qta.icon(icon, color='rgba(10,10,15,0.95)'))

                images = item.get("album", {}).get("images", [])
                if images:
                    try:
                        import urllib.request as urllib_req
                        from PyQt6.QtGui import QPixmap

                        data = urllib_req.urlopen(images[-1]["url"], timeout=3).read()
                        pix = QPixmap()
                        pix.loadFromData(data)

                        pix = pix.scaled(
                            50, 50,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )

                        self.lbl_art.setPixmap(pix)
                        self.lbl_art.setStyleSheet("border-radius:8px;")

                    except Exception:
                        pass
            else:
                self.lbl_track.setText("Not Playing")
                self.lbl_artist.setText("Spotify")
                if self.isVisible() and hasattr(self.window(), "animate_hide_widget"):
                    self.window().animate_hide_widget(self)

        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            print(f"[Spotify] Click en: {self.drag_position}")

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            print(f"[Spotify] Moviendo a: {self.x()}, {self.y()}")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            # Guardar posición al soltar
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                w_name = self.__class__.__name__
                cfg[f"widget_pos_{w_name}_x"] = self.x()
                cfg[f"widget_pos_{w_name}_y"] = self.y()
                save_api_keys(cfg)
                print(f"[Spotify] ✅ Posición guardada: X={self.x()}, Y={self.y()}")
            except Exception as e:
                print(f"[Spotify] ❌ Error guardando posición: {e}")
            self.drag_position = None
        super().mouseReleaseEvent(event)


class FloatingMediaWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MediaFloat")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 90)
        self.drag_position = None
        self._is_playing = False

        self.setStyleSheet('''
QWidget#MediaFloat {
    background: rgba(18,18,22,0.85);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 20px;
}
QLabel {
    background: transparent;
    border: none;
    color: rgba(245,245,250,0.96);
}
QPushButton {
    background: transparent;
    border: none;
}
QPushButton:hover {
    background: rgba(255,255,255,0.06);
    border-radius: 15px;
}
''')
        apply_glass_shadow(self, blur_radius=30, y_offset=6, alpha=150)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.lbl_art = QLabel()
        self.lbl_art.setFixedSize(40, 40)
        self.lbl_art.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 8px;")
        self.lbl_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if HAS_QTA:
            self.lbl_art.setPixmap(qta.icon('fa5b.youtube', color='rgba(255,20,20,0.8)').pixmap(20, 20))
        layout.addWidget(self.lbl_art)

        right = QVBoxLayout()
        right.setSpacing(2)

        self.lbl_track = QLabel("Not Playing")
        self.lbl_track.setStyleSheet("font-size:11px; font-weight:600; color:#ffffff;")
        self.lbl_artist = QLabel("Windows Media")
        self.lbl_artist.setStyleSheet("font-size:10px; color:rgba(200,200,210,0.70);")

        right.addWidget(self.lbl_track)
        right.addWidget(self.lbl_artist)
        
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        ctrl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        if HAS_QTA:
            self.btn_prev = QPushButton()
            self.btn_prev.setFixedSize(24, 24)
            self.btn_prev.setIcon(qta.icon('fa5s.step-backward', color='rgba(220,220,230,0.85)'))
            
            self.btn_play = QPushButton()
            self.btn_play.setFixedSize(28, 28)
            self.btn_play.setIcon(qta.icon('fa5s.play', color='rgba(255,255,255,0.95)'))
            
            self.btn_next = QPushButton()
            self.btn_next.setFixedSize(24, 24)
            self.btn_next.setIcon(qta.icon('fa5s.step-forward', color='rgba(220,220,230,0.85)'))

            ctrl.addWidget(self.btn_prev)
            ctrl.addWidget(self.btn_play)
            ctrl.addWidget(self.btn_next)
            
            self.btn_prev.clicked.connect(lambda: self._press("prevtrack"))
            self.btn_play.clicked.connect(lambda: self._press("playpause"))
            self.btn_next.clicked.connect(lambda: self._press("nexttrack"))

        right.addLayout(ctrl)
        layout.addLayout(right)

        self.hide()
        QTimer.singleShot(100, self.load_position)

    def update_info(self, title, artist, is_playing, thumb):
        if not title:
            self.lbl_track.setText("Not Playing")
            self.lbl_artist.setText("Windows Media")
            self._is_playing = False
            return

        self._is_playing = is_playing
        name = title[:30] + ("..." if len(title) > 30 else "")
        art = artist[:30] + ("..." if len(artist) > 30 else "")
        self.lbl_track.setText(name)
        self.lbl_artist.setText(art)

        if HAS_QTA:
            icon = 'fa5s.pause' if is_playing else 'fa5s.play'
            self.btn_play.setIcon(qta.icon(icon, color='rgba(255,255,255,0.95)'))

    def _press(self, key):
        try:
            import pyautogui
            pyautogui.press(key)
        except Exception:
            pass

    def load_position(self):
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            w_name = self.__class__.__name__
            x = cfg.get(f"widget_pos_{w_name}_x")
            y = cfg.get(f"widget_pos_{w_name}_y")
            if x is not None and y is not None:
                self.move(int(x), int(y))
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                w_name = self.__class__.__name__
                cfg[f"widget_pos_{w_name}_x"] = self.x()
                cfg[f"widget_pos_{w_name}_y"] = self.y()
                save_api_keys(cfg)
            except Exception:
                pass
            self.drag_position = None
        super().mouseReleaseEvent(event)

class PillChatBar(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PillChatBar")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(56)
        layout = QHBoxLayout(self); layout.setContentsMargins(20, 0, 14, 0); layout.setSpacing(10)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Escribe un mensaje…")
        self.inp.setFont(QFont(FONT_FAMILY, 13))
        self.inp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.inp.returnPressed.connect(self._submit)
        self.inp.setStyleSheet("QLineEdit {background: transparent;border: none;color: white;font-size: 14px;}")
        layout.addWidget(self.inp)
        if HAS_QTA:
            self.btn_send = QPushButton(); self.btn_send.setFixedSize(38, 38)
            self.btn_send.setIcon(qta.icon('fa5s.paper-plane', color='rgba(200,200,210,0.70)')); self.btn_send.setIconSize(QSize(17, 17))
            self.btn_send.setStyleSheet("QPushButton{background:transparent;border:none;}QPushButton:hover{color:white;}")
            self.btn_send.clicked.connect(self._submit); layout.addWidget(self.btn_send)
        self.setStyleSheet("QWidget#PillChatBar {background: rgba(20,20,24,0.72);border: 1px solid rgba(255,255,255,0.14);border-radius: 28px;}")
        apply_glass_shadow(self, blur_radius=14, y_offset=3, alpha=110)
        self.hide()

    def _submit(self):
        text = self.inp.text().strip()
        if text: self.submitted.emit(text); self.inp.clear()

    def toggle(self):
        if self.isVisible(): self.hide()
        else: self.show(); self.inp.setFocus()


class HUDCalendarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CalendarPop")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(230, 190)
        self.setStyleSheet("QWidget#CalendarPop {background: rgba(18,18,22,0.88);border: 1px solid rgba(255,255,255,0.12);border-radius: 16px;}QLabel { background: transparent; border: none; color: rgba(220,220,230,0.9); }")
        apply_glass_shadow(self, blur_radius=18, y_offset=5, alpha=120)
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 12, 14, 12); layout.setSpacing(8)
        now = datetime.now()
        month_lbl = QLabel(now.strftime("%B %Y").upper())
        month_lbl.setStyleSheet("font-size:10px;font-weight:700;letter-spacing:1px;color:rgba(200,200,210,0.80);")
        month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(month_lbl)
        days_hdr = QHBoxLayout()
        for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            l = QLabel(d); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setStyleSheet("font-size:9px;color:rgba(150,150,160,0.60);font-weight:600;")
            days_hdr.addWidget(l)
        layout.addLayout(days_hdr)
        import calendar
        cal = calendar.monthcalendar(now.year, now.month)
        for week in cal:
            row = QHBoxLayout()
            for day in week:
                if day == 0:
                    l = QLabel("")
                else:
                    l = QLabel(str(day))
                    if day == now.day:
                        l.setStyleSheet("background: rgba(168,85,247,0.40);border-radius: 10px;font-size:9px; font-weight:700;color: white;")
                    else:
                        l.setStyleSheet("font-size:9px;color:rgba(200,200,210,0.70);")
                l.setAlignment(Qt.AlignmentFlag.AlignCenter); l.setFixedSize(22, 20); row.addWidget(l)
            layout.addLayout(row)
        self.hide()

class TodoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TodoWidget")
        self._drag_offset = None  # <--- AGREGAR ESTO
        self.update_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        header = QHBoxLayout()
        lbl_icon = QLabel()
        if HAS_QTA:
            lbl_icon.setPixmap(qta.icon('fa5s.check-circle', color=C_PRI).pixmap(18, 18))
        header.addWidget(lbl_icon)
        
        self.lbl_title = QLabel("TODOS")
        header.addWidget(self.lbl_title)
        header.addStretch()
        layout.addLayout(header)
        
        inp_layout = QHBoxLayout()
        self.txt_task = QLineEdit()
        self.txt_task.setPlaceholderText("New chore...")
        inp_layout.addWidget(self.txt_task)
        
        self.btn_add = QPushButton("+")
        inp_layout.addWidget(self.btn_add)
        layout.addLayout(inp_layout)
        
        self.lst_todo = QListWidget()
        self.lst_todo.setStyleSheet("QListWidget { border: none; background: transparent; } QListWidget::item { padding: 4px; color: white; }")
        layout.addWidget(self.lst_todo)
        
        self.btn_add.clicked.connect(self.add_task)
        self.txt_task.returnPressed.connect(self.add_task)
        
    def add_task(self):
        text = self.txt_task.text().strip()
        if text:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.lst_todo.addItem(item)
            self.txt_task.clear()

    def update_style(self):
        self.setStyleSheet(f"""
            QWidget#TodoWidget {{
                background: {C_PANEL};
                border-top: 1.5px solid rgba(255, 255, 255, 0.25);
                border-left: 1.5px solid rgba(255, 255, 255, 0.15);
                border: 1.5px solid {C_BORDER};
                border-radius: 20px;
            }}
        """)
        if hasattr(self, "lbl_title"):
            self.lbl_title.setStyleSheet(f"font-weight: bold; font-size: 11px; letter-spacing: 2px; color: {C_PRI}; border: none; background: transparent;")
            self.txt_task.setStyleSheet(f"QLineEdit {{ background: rgba(0,0,0,0.3); border: 1px solid {C_BORDER}; border-radius: 20px; padding: 4px; color: white; }}")
            self.btn_add.setStyleSheet(f"QPushButton {{ background: {C_PRI}; color: black; border: 1px solid {C_PRI}; font-weight: bold; border-radius: 20px; padding: 4px 10px; }}")
        apply_glass_shadow(self)
    
    # ---------------- DRAG SYSTEM ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_offset is not None
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_offset
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                w_name = self.__class__.__name__
                cfg[f"widget_pos_{w_name}_x"] = self.x()
                cfg[f"widget_pos_{w_name}_y"] = self.y()
                save_api_keys(cfg)
                print(f"[{w_name}] ✅ Posición guardada: X={self.x()}, Y={self.y()}")
            except Exception as e:
                print(f"Error saving {self.__class__.__name__} position: {e}")
            self._drag_offset = None
        super().mouseReleaseEvent(event)
        
class NotesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NotesWidget")
        self._drag_offset = None  # <--- AGREGAR ESTO
        self.update_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        header = QHBoxLayout()
        lbl_icon = QLabel()
        if HAS_QTA:
            lbl_icon.setPixmap(qta.icon('fa5s.sticky-note', color=C_PRI).pixmap(18, 18))
        header.addWidget(lbl_icon)
        
        self.lbl_title = QLabel("PAD NOTES")
        header.addWidget(self.lbl_title)
        header.addStretch()
        layout.addLayout(header)
        
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Write details...")
        layout.addWidget(self.txt_notes)

    def update_style(self):
        self.setStyleSheet(f"""
            QWidget#NotesWidget {{
                background: {C_PANEL};
                border-top: 1.5px solid rgba(255, 255, 255, 0.25);
                border-left: 1.5px solid rgba(255, 255, 255, 0.15);
                border: 1.5px solid {C_BORDER};
                border-radius: 20px;
            }}
        """)
        if hasattr(self, "lbl_title"):
            self.lbl_title.setStyleSheet(f"font-weight: bold; font-size: 11px; letter-spacing: 2px; color: {C_PRI}; border: none; background: transparent;")
            self.txt_notes.setStyleSheet(f"QTextEdit {{ border: none; background: rgba(0,0,0,0.2); border-radius: 20px; padding: 6px; color: white; }}")
        apply_glass_shadow(self)
    
    # ---------------- DRAG SYSTEM ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_offset is not None
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_offset
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                w_name = self.__class__.__name__
                cfg[f"widget_pos_{w_name}_x"] = self.x()
                cfg[f"widget_pos_{w_name}_y"] = self.y()
                save_api_keys(cfg)
                print(f"[{w_name}] ✅ Posición guardada: X={self.x()}, Y={self.y()}")
            except Exception as e:
                print(f"Error saving {self.__class__.__name__} position: {e}")
            self._drag_offset = None
        super().mouseReleaseEvent(event)

class FilesPanel(QWidget):
    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.setObjectName("FilesPanel")
        self._drag_offset = None  # <--- AGREGAR ESTO
        self.update_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        header = QHBoxLayout()
        lbl_icon = QLabel()
        if HAS_QTA:
            lbl_icon.setPixmap(qta.icon('fa5s.keyboard', color=C_PRI).pixmap(18, 18))
        header.addWidget(lbl_icon)
        
        self.lbl_title = QLabel("MACROS GUARDADOS")
        header.addWidget(self.lbl_title)
        
        self.btn_open_folder = QPushButton()
        if HAS_QTA:
            self.btn_open_folder.setIcon(qta.icon('fa5s.folder-open', color=C_PRI))
        self.btn_open_folder.setFixedSize(20, 20)
        self.btn_open_folder.setToolTip("Abrir Carpeta de Macros")
        self.btn_open_folder.setStyleSheet("background: transparent; border: none;")
        self.btn_open_folder.clicked.connect(self.open_macros_folder)
        header.addWidget(self.btn_open_folder)

        self.btn_refresh = QPushButton()
        if HAS_QTA:
            self.btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color=C_PRI))
        self.btn_refresh.setFixedSize(20, 20)
        self.btn_refresh.setToolTip("Actualizar Macros")
        self.btn_refresh.setStyleSheet("background: transparent; border: none;")
        self.btn_refresh.clicked.connect(self.load_macros)
        header.addWidget(self.btn_refresh)
        
        header.addStretch()
        layout.addLayout(header)
        
        self.list_macros = QListWidget()
        self.list_macros.setStyleSheet(f"background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); border-radius: 5px; color: {C_TEXT}; font-size: 11px;")
        self.list_macros.itemDoubleClicked.connect(self.execute_macro)
        layout.addWidget(self.list_macros)
        
        self.load_macros()
        
    def load_macros(self):
        self.list_macros.clear()
        try:
            from memory.config_manager import BASE_DIR
            import json
            macros_file = BASE_DIR / "config" / "macros.json"
            if macros_file.exists():
                with open(macros_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for m in data.keys():
                        item = QListWidgetItem(f"▶ {m}")
                        self.list_macros.addItem(item)
                if self.list_macros.count() == 0:
                    self.list_macros.addItem(QListWidgetItem("No hay macros guardadas."))
            else:
                self.list_macros.addItem(QListWidgetItem("No hay macros guardadas."))
        except Exception:
            self.list_macros.addItem(QListWidgetItem("Error al cargar macros."))

    def execute_macro(self, item):
        macro_name = item.text().replace("▶ ", "").strip()
        if macro_name and "No hay" not in macro_name and "Error" not in macro_name:
            import threading
            from actions.macros import macros
            threading.Thread(target=macros, args=({"action": "execute_macro", "macro_name": macro_name}, self.ui), daemon=True).start()

    def open_macros_folder(self):
        from memory.config_manager import BASE_DIR
        import os, subprocess
        folder = BASE_DIR / "config"
        if os.name == 'nt':
            subprocess.Popen(f'explorer "{folder}"')
        
    def update_style(self):
        self.setStyleSheet(f"""
            QWidget#FilesPanel {{
                background: {C_PANEL};
                border-top: 1.5px solid rgba(255, 255, 255, 0.25);
                border-left: 1.5px solid rgba(255, 255, 255, 0.15);
                border: 1.5px solid {C_BORDER};
                border-radius: 20px;
            }}
        """)
        if hasattr(self, "lbl_title"):
            self.lbl_title.setStyleSheet(f"font-weight: bold; font-size: 11px; letter-spacing: 2px; color: {C_PRI}; border: none; background: transparent;")
            self.list_macros.setStyleSheet(f"background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; color: {C_TEXT}; font-size: 11px;")
        apply_glass_shadow(self)
    
    # ---------------- DRAG SYSTEM ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_offset is not None
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_offset
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                w_name = self.__class__.__name__
                cfg[f"widget_pos_{w_name}_x"] = self.x()
                cfg[f"widget_pos_{w_name}_y"] = self.y()
                save_api_keys(cfg)
                print(f"[{w_name}] ✅ Posición guardada: X={self.x()}, Y={self.y()}")
            except Exception as e:
                print(f"Error saving {self.__class__.__name__} position: {e}")
            self._drag_offset = None
        super().mouseReleaseEvent(event)



class WeatherWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("WeatherWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(250, 130)

        self.setStyleSheet(f"""
        QWidget#WeatherWidget {{
            background: rgba(18,18,22,0.78);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 18px;
        }}

        QLabel {{
            background: transparent;
            border: none;
            color: {C_TEXT};
        }}
        """)

        apply_glass_shadow(
            self,
            blur_radius=18,
            y_offset=4,
            alpha=120
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.lbl_city = QLabel("🌤 Medellín")
        self.lbl_city.setStyleSheet("""
            font-size:12px;
            font-weight:700;
            color:white;
        """)

        self.lbl_temp = QLabel("--°C")
        self.lbl_temp.setStyleSheet(f"""
            font-size:28px;
            font-weight:800;
            color:{C_PRI};
        """)

        self.lbl_desc = QLabel("Cargando clima...")
        self.lbl_desc.setStyleSheet("""
            font-size:10px;
            color:rgba(220,220,230,0.75);
        """)

        self.lbl_extra = QLabel("--")
        self.lbl_extra.setStyleSheet("""
            font-size:9px;
            color:rgba(220,220,230,0.60);
        """)

        layout.addWidget(self.lbl_city)
        layout.addWidget(self.lbl_temp)
        layout.addWidget(self.lbl_desc)
        layout.addWidget(self.lbl_extra)

        # Timer principal (actualización cada 30 min)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_weather)
        self.timer.start(1800000)

        # Primera actualización (delay 1 segundo)
        QTimer.singleShot(1000, self.update_weather)

        # Drag state
        self._drag_offset = None

    # ---------------- DRAG SYSTEM ----------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_offset is not None
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_offset
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            # Guardar posición al soltar
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                w_name = self.__class__.__name__
                cfg[f"widget_pos_{w_name}_x"] = self.x()
                cfg[f"widget_pos_{w_name}_y"] = self.y()
                save_api_keys(cfg)
            except Exception as e:
                print(f"Error saving WeatherWidget position: {e}")
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ---------------- WEATHER LOGIC ----------------

    def weather_icon(self, code: int):
        if code == 0:
            return "☀️"
        if code in [1, 2]:
            return "🌤"
        if code == 3:
            return "☁️"
        if code in [45, 48]:
            return "🌫"
        if code in [51, 53, 55, 56, 57]:
            return "🌦"
        if code in [61, 63, 65]:
            return "🌧"
        if code in [66, 67]:
            return "🌧"
        if code in [71, 73, 75]:
            return "❄️"
        if code in [80, 81, 82]:
            return "🌧"
        if code in [95, 96, 99]:
            return "⛈"
        return "🌤"

    def weather_text(self, code: int):
        mapping = {
            0: "Despejado",
            1: "Mayormente despejado",
            2: "Parcialmente nublado",
            3: "Nublado",
            45: "Neblina",
            48: "Neblina",
            51: "Llovizna ligera",
            53: "Llovizna",
            55: "Llovizna fuerte",
            61: "Lluvia ligera",
            63: "Lluvia",
            65: "Lluvia intensa",
            71: "Nieve ligera",
            73: "Nieve",
            75: "Nieve intensa",
            80: "Chubascos",
            81: "Chubascos fuertes",
            82: "Tormenta de lluvia",
            95: "Tormenta eléctrica"
        }
        return mapping.get(code, "Clima desconocido")

    def update_weather(self):
        try:
            lat = 6.2442
            lon = -75.5812

            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}"
                f"&longitude={lon}"
                "&current=temperature_2m,relative_humidity_2m,"
                "apparent_temperature,weather_code,wind_speed_10m"
            )

            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))

            current = data["current"]

            temp = current["temperature_2m"]
            humidity = current["relative_humidity_2m"]
            feels = current["apparent_temperature"]
            wind = current["wind_speed_10m"]
            code = current["weather_code"]

            icon = self.weather_icon(code)

            self.lbl_city.setText(f"{icon} Medellín")
            self.lbl_temp.setText(f"{round(temp)}°C")
            self.lbl_desc.setText(self.weather_text(code))
            self.lbl_extra.setText(
                f"Sensación {round(feels)}°C   •   "
                f"Humedad {humidity}%   •   "
                f"Viento {round(wind)} km/h"
            )

        except Exception as e:
            self.lbl_temp.setText("--°C")
            self.lbl_desc.setText("Sin conexión")
            self.lbl_extra.setText(str(e)[:60])

class SystemWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SystemWidget")
        self._drag_offset = None  # <--- AGREGAR ESTO
        self.update_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        header = QHBoxLayout()
        lbl_icon = QLabel()
        if HAS_QTA:
            lbl_icon.setPixmap(qta.icon('fa5s.bolt', color=C_PRI).pixmap(18, 18))
        header.addWidget(lbl_icon)
        
        self.lbl_title = QLabel("SYSTEM GAUGES")
        header.addWidget(self.lbl_title)
        header.addStretch()
        layout.addLayout(header)
        
        self.cpu_bar = QProgressBar()
        self.ram_bar = QProgressBar()
        
        self.bars = [(self.cpu_bar, "CPU Status"), (self.ram_bar, "RAM Status")]
        for bar, label in self.bars:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size: 10px; color: {C_PRI_DIM}; border: none; background: transparent;")
            layout.addWidget(lbl)
            bar.setTextVisible(True)
            layout.addWidget(bar)
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)
        self.update_stats()
        
    def update_stats(self):
        try:
            self.cpu_bar.setValue(int(psutil.cpu_percent()))
            self.ram_bar.setValue(int(psutil.virtual_memory().percent))
        except Exception:
            pass

    def update_style(self):
        self.setStyleSheet(f"""
            QWidget#SystemWidget {{
                background: {C_PANEL};
                border-top: 1.5px solid rgba(255, 255, 255, 0.25);
                border-left: 1.5px solid rgba(255, 255, 255, 0.15);
                border: 1.5px solid {C_BORDER};
                border-radius: 20px;
            }}
        """)
        if hasattr(self, "lbl_title"):
            self.lbl_title.setStyleSheet(f"font-weight: bold; font-size: 11px; letter-spacing: 2px; color: {C_PRI}; border: none; background: transparent;")
            for bar, label in self.bars:
                bar.setStyleSheet(f"""
                    QProgressBar {{
                        border: 1px solid {C_BORDER};
                        border-radius: 20px;
                        text-align: center;
                        background: transparent;
                        color: white;
                        height: 14px;
                    }}
                    QProgressBar::chunk {{
                        background-color: {C_PRI};
                        border-radius: 20px;
                    }}
                """)
        apply_glass_shadow(self)
    
    # ---------------- DRAG SYSTEM ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_offset is not None
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_offset
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys()
                w_name = self.__class__.__name__
                cfg[f"widget_pos_{w_name}_x"] = self.x()
                cfg[f"widget_pos_{w_name}_y"] = self.y()
                save_api_keys(cfg)
                print(f"[{w_name}] ✅ Posición guardada: X={self.x()}, Y={self.y()}")
            except Exception as e:
                print(f"Error saving {self.__class__.__name__} position: {e}")
            self._drag_offset = None
        super().mouseReleaseEvent(event)

# ═══════════════════════════════════════════════════════════════════════════
#  Dialogs: IlumMessageBox, LogsDialog, IlumColorPicker
# ═══════════════════════════════════════════════════════════════════════════

class IlumMessageBox(QDialog):
    def __init__(self, parent, title, text, is_error=False):
        super().__init__(parent)
        self.setWindowTitle(title); self.setModal(True); self.setFixedSize(380, 160)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.container = QWidget(self); self.container.setObjectName("msgContainer")
        main_lay = QVBoxLayout(self); main_lay.setContentsMargins(0, 0, 0, 0); main_lay.addWidget(self.container)
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, 380, 160), 12.0, 12.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        layout = QVBoxLayout(self.container); layout.setContentsMargins(20, 15, 20, 15)
        header = QHBoxLayout()
        self.lbl_icon = QLabel()
        if HAS_QTA:
            iname = 'fa5s.exclamation-triangle' if is_error else 'fa5s.info-circle'
            self.lbl_icon.setPixmap(qta.icon(iname, color='#e11d48' if is_error else C_PRI).pixmap(18, 18))
        header.addWidget(self.lbl_icon)
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(f"color:{C_PRI};font-size:13px;font-weight:bold;letter-spacing:1.5px;background:transparent;")
        header.addWidget(self.lbl_title); header.addStretch(); layout.addLayout(header)
        self.lbl_text = QLabel(text); self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet("color:white;font-size:12px;background:transparent;margin-top:10px;")
        layout.addWidget(self.lbl_text)
        btn_layout = QHBoxLayout(); btn_layout.addStretch()
        self.btn_ok = QPushButton("ACEPTAR"); self.btn_ok.setFixedSize(90, 30)
        self.btn_ok.clicked.connect(self.accept); btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)
        self.setStyleSheet(f"QWidget#msgContainer{{background-color:{C_BG};border:2px solid {C_PRI};border-radius:12px;}}QPushButton{{background-color:rgba(10,22,32,0.7);color:{C_PRI};border:1.5px solid {C_PRI};font-weight:bold;border-radius:4px;}}QPushButton:hover{{background-color:{C_PRI};color:{C_BG};}}")


class LogsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ILUM Logs"); self.setFixedSize(750, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.container = QWidget(self); self.container.setObjectName("logsContainer")
        main_lay = QVBoxLayout(self); main_lay.setContentsMargins(0, 0, 0, 0); main_lay.addWidget(self.container)
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, 750, 500), 12.0, 12.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        layout = QVBoxLayout(self.container); layout.setContentsMargins(15, 15, 15, 15); layout.setSpacing(10)
        header = QHBoxLayout()
        self.lbl_icon = QLabel()
        if HAS_QTA: self.lbl_icon.setPixmap(qta.icon('fa5s.terminal', color=C_PRI).pixmap(18, 18))
        header.addWidget(self.lbl_icon)
        self.lbl_title = QLabel("ILUM TELEMETRÍA Y LOGS")
        self.lbl_title.setStyleSheet(f"color:{C_PRI};font-size:13px;font-weight:bold;letter-spacing:2px;background:transparent;")
        header.addWidget(self.lbl_title); header.addStretch()
        self.btn_close = QPushButton("×"); self.btn_close.setFixedSize(22, 22); self.btn_close.clicked.connect(self.accept)
        self.btn_close.setStyleSheet(f"QPushButton{{background:transparent;color:{C_PRI};border:1px solid rgba(245,158,11,0.4);border-radius:11px;font-size:14px;font-weight:bold;}}QPushButton:hover{{background-color:#ff3b30;color:white;}}")
        header.addWidget(self.btn_close); layout.addLayout(header)
        filter_layout = QHBoxLayout(); filter_layout.setSpacing(8)
        self.inp_filter = QLineEdit(); self.inp_filter.setPlaceholderText("Filtrar logs…")
        self.inp_filter.textChanged.connect(self.filter_logs)
        self.inp_filter.setStyleSheet(f"QLineEdit{{background-color:rgba(0,0,0,0.4);color:white;border:1px solid rgba(245,158,11,0.4);border-radius:6px;padding:6px 10px;font-size:11px;}}QLineEdit:focus{{border-color:{C_PRI};}}")
        filter_layout.addWidget(self.inp_filter)
        self.btn_refresh = QPushButton("ACTUALIZAR"); self.btn_refresh.setFixedSize(110, 28)
        self.btn_refresh.clicked.connect(self.load_logs)
        self.btn_refresh.setStyleSheet(f"QPushButton{{background-color:rgba(10,22,32,0.7);color:{C_PRI};border:1.5px solid {C_PRI};font-weight:bold;border-radius:6px;font-size:10px;}}QPushButton:hover{{background-color:{C_PRI};color:{C_BG};}}")
        filter_layout.addWidget(self.btn_refresh); layout.addLayout(filter_layout)
        self.txt_logs = QTextEdit(); self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont("Consolas", 10))
        self.txt_logs.setStyleSheet(f"QTextEdit{{background-color:rgba(5,7,10,0.9);color:#e2e8f0;border:1.2px solid rgba(245,158,11,0.35);border-radius:8px;padding:8px;}}")
        layout.addWidget(self.txt_logs)
        self.setStyleSheet(f"QWidget#logsContainer{{background-color:{C_BG};border:2px solid {C_PRI};border-radius:12px;}}")
        self.raw_log_lines = []; self.load_logs()
        self.refresh_timer = QTimer(self); self.refresh_timer.timeout.connect(self.load_logs); self.refresh_timer.start(2000)

    def load_logs(self):
        try:
            from memory.config_manager import BASE_DIR
            log_file = BASE_DIR / "ilum.log"
            if not log_file.exists(): log_file = Path("ilum.log")
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    self.raw_log_lines = f.readlines()
            else: self.raw_log_lines = ["No se encontró 'ilum.log'."]
        except Exception as e: self.raw_log_lines = [f"Error: {e}"]
        self.filter_logs()

    def filter_logs(self):
        ft = self.inp_filter.text().lower().strip()
        lines = self.raw_log_lines[-400:]
        html = ""
        for line in lines:
            if ft and ft not in line.lower(): continue
            esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if any(x in line.lower() for x in ("err", "exception", "fail")): c, fw = "#ff4d4d", "bold"
            elif "sys:" in line.lower(): c, fw = C_PRI, "bold"
            elif "ilum:" in line.lower(): c, fw = "#00ff88", "normal"
            elif any(x in line.lower() for x in ("tú:", "tu:")): c, fw = "#00d4ff", "normal"
            else: c, fw = "#cbd5e1", "normal"
            html += f"<span style='color:{c};font-weight:{fw};'>{esc}</span><br>"
        self.txt_logs.setHtml(html)
        QTimer.singleShot(50, lambda: self.txt_logs.verticalScrollBar().setValue(self.txt_logs.verticalScrollBar().maximum()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_position') and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)


class IlumColorPicker(QDialog):
    def __init__(self, parent=None, initial_color=None):
        super().__init__(parent)
        self.setWindowTitle("ILUM Color Picker"); self.resize(380, 490)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.selected_color = initial_color or QColor(C_PRI)
        self.drag_position = None
        self.container = QFrame(self); self.container.setObjectName("pickerContainer")
        cl = QVBoxLayout(self.container); cl.setContentsMargins(15, 15, 15, 15); cl.setSpacing(12)
        hdr = QHBoxLayout()
        lbl = QLabel("SELECTOR DE COLOR")
        lbl.setStyleSheet(f"color:{C_PRI};font-size:11px;font-weight:bold;letter-spacing:2px;background:transparent;")
        hdr.addWidget(lbl); hdr.addStretch()
        bc = QPushButton("×"); bc.setFixedSize(22, 22); bc.clicked.connect(self.reject)
        bc.setStyleSheet(f"QPushButton{{background:transparent;color:{C_PRI};border:1px solid {C_BORDER};border-radius:11px;font-size:14px;}}QPushButton:hover{{background:#ff3b30;color:white;}}")
        hdr.addWidget(bc); cl.addLayout(hdr)
        self.preview_frame = QFrame(); self.preview_frame.setFixedSize(80, 80); self.preview_frame.setStyleSheet("border-radius:40px;")
        self.glow_effect = QGraphicsDropShadowEffect(); self.glow_effect.setBlurRadius(25); self.glow_effect.setXOffset(0); self.glow_effect.setYOffset(0)
        self.preview_frame.setGraphicsEffect(self.glow_effect)
        pc = QHBoxLayout(); pc.addStretch(); pc.addWidget(self.preview_frame); pc.addStretch(); cl.addLayout(pc)
        sliders_lay = QGridLayout(); sliders_lay.setSpacing(8)
        sliders_lay.addWidget(QLabel("Tono (H):"), 0, 0); self.sld_h = QSlider(Qt.Orientation.Horizontal); self.sld_h.setRange(0, 359); sliders_lay.addWidget(self.sld_h, 0, 1); self.lbl_h = QLabel("0"); self.lbl_h.setFixedWidth(30); sliders_lay.addWidget(self.lbl_h, 0, 2)
        sliders_lay.addWidget(QLabel("Sat (S):"), 1, 0); self.sld_s = QSlider(Qt.Orientation.Horizontal); self.sld_s.setRange(0, 255); sliders_lay.addWidget(self.sld_s, 1, 1); self.lbl_s = QLabel("0"); self.lbl_s.setFixedWidth(30); sliders_lay.addWidget(self.lbl_s, 1, 2)
        sliders_lay.addWidget(QLabel("Brillo (V):"), 2, 0); self.sld_v = QSlider(Qt.Orientation.Horizontal); self.sld_v.setRange(0, 255); sliders_lay.addWidget(self.sld_v, 2, 1); self.lbl_v = QLabel("0"); self.lbl_v.setFixedWidth(30); sliders_lay.addWidget(self.lbl_v, 2, 2)
        cl.addLayout(sliders_lay)
        self.sld_h.valueChanged.connect(self._on_slider_changed); self.sld_s.valueChanged.connect(self._on_slider_changed); self.sld_v.valueChanged.connect(self._on_slider_changed)
        hex_lay = QHBoxLayout(); hex_lay.addWidget(QLabel("Hex:"))
        self.inp_hex = QLineEdit(); self.inp_hex.setFixedWidth(120); self.inp_hex.setAlignment(Qt.AlignmentFlag.AlignCenter); self.inp_hex.textChanged.connect(self._on_hex_input_changed); hex_lay.addWidget(self.inp_hex); hex_lay.addStretch(); cl.addLayout(hex_lay)
        self.btn_apply = QPushButton("APLICAR"); self.btn_apply.setFixedHeight(35); self.btn_apply.clicked.connect(self.accept); cl.addWidget(self.btn_apply)
        self.setStyleSheet(f"QFrame#pickerContainer{{background-color:{C_BG};border:2.2px solid {C_PRI};border-radius:12px;}}QLabel{{color:{C_TEXT};font-weight:bold;font-size:11px;background:transparent;}}QLineEdit{{background:rgba(0,0,0,0.6);border:1px solid {C_BORDER};color:white;padding:4px;border-radius:4px;}}QPushButton{{background-color:{C_PRI};color:black;border:1px solid {C_PRI};font-weight:bold;border-radius:6px;font-size:11px;}}QPushButton:hover{{background-color:transparent;color:{C_PRI};}}")
        mv = QVBoxLayout(self); mv.setContentsMargins(0, 0, 0, 0); mv.addWidget(self.container)
        h, s, v, a = self.selected_color.getHsv()
        self.sld_h.setValue(h); self.sld_s.setValue(s); self.sld_v.setValue(v)
        self.lbl_h.setText(str(h)); self.lbl_s.setText(str(s)); self.lbl_v.setText(str(v))
        self.inp_hex.setText(self.selected_color.name().upper()); self._update_preview()

    def _on_slider_changed(self):
        h, s, v = self.sld_h.value(), self.sld_s.value(), self.sld_v.value()
        self.lbl_h.setText(str(h)); self.lbl_s.setText(str(s)); self.lbl_v.setText(str(v))
        self.selected_color = QColor.fromHsv(h, s, v)
        self.inp_hex.blockSignals(True); self.inp_hex.setText(self.selected_color.name().upper()); self.inp_hex.blockSignals(False)
        self._update_preview()

    def _on_hex_input_changed(self, text):
        c = QColor(text)
        if c.isValid():
            self.selected_color = c; h, s, v, a = c.getHsv()
            for sl, val in ((self.sld_h, h), (self.sld_s, s), (self.sld_v, v)):
                sl.blockSignals(True); sl.setValue(val); sl.blockSignals(False)
            self.lbl_h.setText(str(h)); self.lbl_s.setText(str(s)); self.lbl_v.setText(str(v))
            self._update_preview()

    def _update_preview(self):
        c = self.selected_color.name()
        self.preview_frame.setStyleSheet(f"background-color:{c};border:2.5px solid white;border-radius:40px;")
        self.glow_effect.setColor(self.selected_color)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.drag_position = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self.drag_position: self.move(e.globalPosition().toPoint() - self.drag_position)


# ═══════════════════════════════════════════════════════════════════════════
#  Ollama Workers
# ═══════════════════════════════════════════════════════════════════════════

class OllamaPullWorker(QThread):
    progress_signal = pyqtSignal(str, int, str)
    def __init__(self, model_name, ollama_url="http://127.0.0.1:11434"):
        super().__init__(); self.model_name = model_name; self.ollama_url = ollama_url.rstrip("/"); self.is_running = True
    def run(self):
        import urllib.request, json
        url = f"{self.ollama_url}/api/pull"; data = json.dumps({"name": self.model_name}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            response = urllib.request.urlopen(req, timeout=1200); buf = ""
            while self.is_running:
                chunk = response.read(256)
                if not chunk: break
                buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1); line = line.strip()
                    if not line: continue
                    try:
                        r = json.loads(line); st = r.get("status", ""); comp = r.get("completed", 0); tot = r.get("total", 0)
                        pct = int((comp / tot) * 100) if tot > 0 else 0
                        self.progress_signal.emit(st, pct, "")
                    except Exception: pass
            if self.is_running: self.progress_signal.emit("success", 100, "")
            else: self.progress_signal.emit("cancelled", 0, "")
        except Exception as e: self.progress_signal.emit("error", 0, str(e))


class OllamaInstallerWorker(QThread):
    progress_signal = pyqtSignal(str, int, str)
    def __init__(self): super().__init__(); self.is_running = True
    def run(self):
        import urllib.request, os, tempfile
        url = "https://ollama.com/download/OllamaSetup.exe"; exe = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                tot = r.getheader('content-length'); dl = 0; cs = 1024 * 64
                with open(exe, 'wb') as f:
                    while self.is_running:
                        ch = r.read(cs)
                        if not ch: break
                        f.write(ch); dl += len(ch)
                        if tot: self.progress_signal.emit("DESCARGANDO", int(dl / int(tot) * 100), "")
            if self.is_running:
                self.progress_signal.emit("EJECUTANDO...", 100, ""); os.startfile(exe); self.progress_signal.emit("success_installer", 100, "")
            else: self.progress_signal.emit("cancelled", 0, "")
        except Exception as e: self.progress_signal.emit("error", 0, str(e))


class OllamaCheckWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)
    def __init__(self, ollama_url="http://127.0.0.1:11434"): super().__init__(); self.ollama_url = ollama_url.rstrip("/")
    def run(self):
        import urllib.request, json
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{self.ollama_url}/api/tags"), timeout=1.2) as r:
                data = json.loads(r.read().decode()); models = [m["name"] for m in data.get("models", [])]
                v = ""
                try:
                    with urllib.request.urlopen(urllib.request.Request(f"{self.ollama_url}/api/version"), timeout=0.8) as rv:
                        v = json.loads(rv.read().decode()).get("version", "")
                except: pass
                self.finished_signal.emit(True, models, v)
        except Exception: self.finished_signal.emit(False, [], "")


# ═══════════════════════════════════════════════════════════════════════════
#  DeviceSettingsDialog — REDISEÑADO CON NAVEGACIÓN LATERAL
#  ESTILO LIQUID GLASS - VERSIÓN ULTRA ESPACIADA
# ═══════════════════════════════════════════════════════════════════════════

class SettingsCard(QFrame):
    """Panel estilo card para agrupar opciones - Versión ultra espaciada."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setStyleSheet("""
            QFrame#SettingsCard {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 22px;
            }
            QFrame#SettingsCard:hover {
                background: rgba(255, 255, 255, 0.07);
                border-color: rgba(255, 255, 255, 0.16);
            }
        """)
        apply_glass_shadow(self, blur_radius=30, y_offset=6, alpha=120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 30)
        layout.setSpacing(20)

        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.85);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 3px;
            background: transparent;
            border: none;
            padding-bottom: 14px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        """)
        layout.addWidget(self.title_label)

        self.content_layout = QGridLayout()
        self.content_layout.setSpacing(22)
        self.content_layout.setContentsMargins(0, 16, 0, 0)
        layout.addLayout(self.content_layout)


class StyledSideNav(QWidget):
    """Barra de navegación lateral - Estilo Liquid Glass - Ultra espaciado."""
    tab_changed = pyqtSignal(int)
    back_clicked = pyqtSignal()

    def __init__(self, tabs: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.tabs = tabs
        self.current_index = 0
        self.setFixedWidth(260)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(10)

        from PyQt6.QtGui import QColor
        color = QColor(C_PRI)
        r, g, b = color.red(), color.green(), color.blue()

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 8, 8, 16)
        header_layout.setSpacing(12)
        
        self.btn_back = QPushButton()
        self.btn_back.setFixedSize(44, 44)
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #a855f7);
                color: #ffffff;
                border: none;
                border-radius: 22px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8b5cf6, stop:1 #c084fc);
            }
        """)
        if HAS_QTA:
            self.btn_back.setIcon(qta.icon("fa5s.chevron-left", color="white"))
            self.btn_back.setIconSize(QSize(14, 14))
        else:
            self.btn_back.setText("◀")
        self.btn_back.clicked.connect(self.back_clicked.emit)
            
        header_layout.addWidget(self.btn_back)
        
        nav_header = QLabel("CONFIG")
        nav_header.setStyleSheet("""
            color: rgba(255,255,255,0.7);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 2px;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(nav_header)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255,255,255,0.03);
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15);
                min-height: 30px;
                border-radius: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 0, 8, 0)
        scroll_layout.setSpacing(6)

        self.buttons = []
        
        for i, (name, icon_name) in enumerate(tabs):
            btn = QPushButton(f"  {name}")
            btn.setCheckable(True)
            btn.setFixedHeight(50)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Setup icon if HAS_QTA
            if HAS_QTA and icon_name:
                btn.setIcon(qta.icon(icon_name, color='rgba(255, 255, 255, 0.5)'))
                btn.setIconSize(QSize(18, 18))
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: rgba(255, 255, 255, 0.55);
                    border: 1px solid transparent;
                    border-radius: 14px;
                    padding: 12px 18px;
                    font-family: '{FONT_FAMILY}';
                    font-weight: 500;
                    font-size: 13px;
                    letter-spacing: 1px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    color: rgba(255, 255, 255, 0.95);
                    background: rgba({r}, {g}, {b}, 0.05);
                    border: 1px solid rgba({r}, {g}, {b}, 0.15);
                }}
                QPushButton:checked {{
                    color: {C_PRI};
                    background: rgba({r}, {g}, {b}, 0.12);
                    border: 1px solid rgba({r}, {g}, {b}, 0.35);
                    font-weight: 700;
                }}
            """)
            btn.clicked.connect(lambda checked, idx=i: self.set_current_tab(idx))
            scroll_layout.addWidget(btn)
            self.buttons.append(btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        self.buttons[0].setChecked(True)

    def set_current_tab(self, index: int):
        if 0 <= index < len(self.buttons):
            for i, btn in enumerate(self.buttons):
                btn.setChecked(i == index)
                name, icon_name = self.tabs[i]
                if HAS_QTA and icon_name:
                    color = C_PRI if i == index else 'rgba(255, 255, 255, 0.5)'
                    btn.setIcon(qta.icon(icon_name, color=color))
            self.current_index = index
            self.tab_changed.emit(index)




class DeviceSettingsDialog(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.custom_color_hex = ""
        self.drag_position = None
        self._custom_bg_color = ""
        self._custom_panel_color = ""
        self._custom_text_color = ""
        self._custom_bg_image = ""
        self._custom_sticker_path = ""
        self._is_checking_ollama = False
        self._personalities_dict = {}
        self._active_ollama_model = "gemma2:2b"
        self.pull_worker = None
        self.install_worker = None
        self.check_worker = None
        self.model_cards = {}
        self.recommended_models = []
        self._on_close_callback = None

        # Dummy compatibility attributes for custom model downloading
        self.btn_custom_pull = QPushButton(self)
        self.btn_custom_pull.setVisible(False)
        self.inp_custom_model = QLineEdit(self)
        self.inp_custom_model.setVisible(False)

        # --- Contenedor Principal ---
        self.container = QFrame(self)
        self.container.setObjectName("settingsContainer")
        self.container.setStyleSheet(f"""
            QFrame#settingsContainer {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgb(22, 12, 35),
                    stop: 0.5 rgb(12, 8, 20),
                    stop: 1 rgb(5, 5, 10)
                );
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 28px;
            }}
        """)
        apply_glass_shadow(self.container, blur_radius=60, y_offset=15, alpha=220)

        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # --- Nav Panel (Sidebar) ---
        nav_panel = QFrame()
        nav_panel.setFixedWidth(276)
        nav_panel.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgb(30, 15, 45),
                    stop: 1 rgb(15, 8, 25)
                );
                border-right: 1px solid rgba(168, 85, 247, 0.25);
                border-top-left-radius: 28px;
                border-bottom-left-radius: 28px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top: none;
                border-bottom: none;
                border-left: none;
            }
        """)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        tab_names = [
            ("General", "fa5s.cog"),
            ("Inteligencia", "fa5s.brain"),
            ("Personalidad", "fa5s.user-astronaut"),
            ("Dispositivos", "fa5s.laptop-house"),
            ("Automatización", "fa5s.robot"),
            ("Macros", "fa5s.keyboard"),
            ("Tienda", "fa5s.store")
        ]
        self.tab_bar = StyledSideNav(tab_names)
        self.tab_bar.back_clicked.connect(self.reject)
        nav_layout.addWidget(self.tab_bar)
        container_layout.addWidget(nav_panel)

        # --- Content Panel (Right side) ---
        content_panel = QFrame()
        content_panel.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(28, 28, 28, 28)
        content_layout.setSpacing(16)

        self.lbl_main_title = QLabel("PANEL DE CONFIGURACIÓN")
        self.lbl_main_title.setStyleSheet("""
            color: #ffffff;
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 4px;
            background: transparent;
            border: none;
            padding-bottom: 8px;
        """)
        content_layout.addWidget(self.lbl_main_title)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent; border: none;")
        content_layout.addWidget(self.stacked_widget, 1)

        # ═══════════════════════════════════════════════════════════════
        # FOOTER (inside content_layout)
        # ═══════════════════════════════════════════════════════════════
        footer_frame = QFrame()
        footer_frame.setFixedHeight(72)
        footer_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.01);
                border-top: 1px solid rgba(168, 85, 247, 0.12);
                border-radius: 0px;
            }
        """)
        bottom_lay = QHBoxLayout(footer_frame)
        bottom_lay.setContentsMargins(12, 12, 12, 12)
        bottom_lay.setSpacing(16)

        self.btn_cancel = QPushButton("CERRAR")
        self.btn_cancel.setFixedSize(150, 46)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: rgba(255, 59, 48, 0.08);
                color: rgba(255, 59, 48, 0.7);
                border: 1px solid rgba(255, 59, 48, 0.15);
                font-weight: 600;
                border-radius: 14px;
                font-size: 12px;
                letter-spacing: 1.2px;
            }
            QPushButton:hover {
                background: rgba(255, 59, 48, 0.15);
                color: rgba(255, 255, 255, 0.9);
                border-color: rgba(255, 59, 48, 0.3);
            }
        """)
        bottom_lay.addWidget(self.btn_cancel)
        bottom_lay.addStretch()

        self.btn_apply = QPushButton("APLICAR CAMBIOS")
        self.btn_apply.setFixedSize(190, 46)
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self.apply_changes)
        self.btn_apply.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.12);
                font-family: '{FONT_FAMILY}';
                font-weight: 600;
                border-radius: 14px;
                font-size: 12px;
                letter-spacing: 1.2px;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 1);
                border-color: rgba(255, 255, 255, 0.25);
            }}
        """)
        bottom_lay.addWidget(self.btn_apply)

        self.btn_save = QPushButton("GUARDAR Y SALIR")
        self.btn_save.setFixedSize(190, 46)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.save)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C_PRI_DIM}, stop:1 {C_PRI});
                color: #ffffff;
                border: none;
                font-family: '{FONT_FAMILY}';
                font-weight: 700;
                border-radius: 14px;
                font-size: 13px;
                letter-spacing: 1.5px;
            }}
            QPushButton:hover {{
                background: {C_PRI};
            }}
        """)
        bottom_lay.addWidget(self.btn_save)
        content_layout.addWidget(footer_frame)

        container_layout.addWidget(content_panel, 1)

        # --- Layout final ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        # --- Construir pestañas agrupadas ---
        self._build_tab_general()
        self._build_tab_intelligence()
        self._build_tab_personality()
        self._build_tab_devices_combined()
        self._build_tab_automation()
        self._build_tab_macros()
        self._build_tab_store()

        # Conectar navegación
        self.tab_bar.tab_changed.connect(self.stacked_widget.setCurrentIndex)

        # Cargar datos
        self.update_style()
        self.load_settings()
        self.load_macros()
        self.clean_all_emojis(self)

    def clean_all_emojis(self, widget):
        import re
        emoji_pattern = re.compile(
            r'[\U00010000-\U0010ffff]'
            r'|[\u2600-\u27BF]'
            r'|[\u2300-\u23FF]'
            r'|[\u2B50-\u2B55]'
        )
        if hasattr(widget, "text") and hasattr(widget, "setText"):
            txt = widget.text()
            if txt and len(txt.strip()) > 1:
                cleaned = emoji_pattern.sub('', txt).strip()
                if cleaned != txt:
                    widget.setText(cleaned)
        for child in widget.findChildren(QWidget):
            self.clean_all_emojis(child)

    # ------------------------------------------------------------------
    # PESTAÑA TIENDA - COMING SOON
    # ------------------------------------------------------------------
    from shop import ShopWidget 

    def _build_tab_store(self):
        """
        Reemplaza el método original.
        ShopWidget gestiona todo: productos, modales y desbloqueos persistentes.
        """
        self.shop_widget = ShopWidget()

        # (opcional) reaccionar cuando el usuario desbloquea algo:
        self.shop_widget.item_unlocked.connect(self._on_item_unlocked)

        self.stacked_widget.addWidget(self.shop_widget)

    def _on_item_unlocked(self, product_id: str):
        """
        Callback opcional — la app principal puede aplicar el desbloqueo al vuelo.
        Ejemplo: si compró 'gif_wallpaper', habilita el selector de GIF en Ajustes.
        """
        if product_id == "neon_color":
            # habilitar selector de color neón en tu configuración
            pass
        elif product_id == "gif_wallpaper":
            # habilitar carga de GIF como wallpaper
            pass
        elif product_id == "custom_fonts":
            # habilitar panel de fuentes personalizadas
            pass

    # ------------------------------------------------------------------
    # MÉTODOS PARA CONSTRUIR CADA PESTAÑA - ULTRA ESPACIADO
    # ------------------------------------------------------------------

    def _create_tab_widget(self):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255,255,255,0.02);
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.1);
                min-height: 40px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QGridLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(32)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        widget._content_layout = content_layout
        widget._row_counter = 0
        widget._max_cols = 2

        def add_card(self, title: str, col_span: int = 1):
            card = SettingsCard(title)
            row = self._row_counter // self._max_cols
            col = self._row_counter % self._max_cols
            self._content_layout.addWidget(card, row, col, 1, col_span)
            self._row_counter += 1 if col_span > 1 else 0
            if col_span > 1:
                self._row_counter += 1
            return card

        widget.add_card = add_card.__get__(widget)
        return widget

    # ─── PESTAÑA GENERAL (PERFIL + APARIENCIA + RENDIMIENTO) ───────────────

    def load_user_profile(self) -> dict:
        import json
        from memory.config_manager import BASE_DIR
        profile_path = BASE_DIR / "config" / "user_profile.json"
        if not profile_path.exists():
            return {"name": "Usuario", "habits": {}}
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception:
            return {"name": "Usuario", "habits": {}}

    def save_user_profile(self, profile: dict) -> None:
        import json
        from memory.config_manager import BASE_DIR
        profile_path = BASE_DIR / "config" / "user_profile.json"
        try:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _change_user_name(self):
        from PyQt6.QtWidgets import QInputDialog
        current_name = self.inp_user_name.text().strip()
        new_name, ok = QInputDialog.getText(
            self, "Editar Nombre", "Introduce tu nombre de usuario:",
            QLineEdit.EchoMode.Normal, current_name
        )
        if ok and new_name.strip():
            username = new_name.strip()
            self.inp_user_name.setText(username)
            self.lbl_user_name_title.setText(f"Usuario Registrado: {username}")
            try:
                profile = self.load_user_profile()
                profile["name"] = username
                self.save_user_profile(profile)
            except Exception:
                pass

    def _change_profile_pic(self):
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QPixmap, QImage
        import shutil
        from memory.config_manager import BASE_DIR
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar foto de perfil", "", "Imágenes (*.png *.jpg *.jpeg)"
        )
        if file_path:
            try:
                dest_dir = BASE_DIR / "config"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / "profile_pic.png"
                
                # Resize and save to ensure it's not a huge file
                img = QImage(file_path)
                scaled = img.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                scaled.save(str(dest_path))
                
                # Update UI
                pix = QPixmap(str(dest_path)).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.lbl_avatar.setPixmap(pix)
                self.lbl_avatar.setStyleSheet("border-radius: 32px;")
                
                # Save to profile
                profile = self.load_user_profile()
                profile["profile_pic"] = str(dest_path)
                self.save_user_profile(profile)
            except Exception as e:
                print(f"Error cambiando foto de perfil: {e}")

    def _build_tab_general(self):
        tab = self._create_tab_widget()
        
        # --- Card 1: 👤 PERFIL DE USUARIO ---
        card_user = tab.add_card("👤 PERFIL DE USUARIO", col_span=2)
        layout_user = card_user.content_layout
        
        prof_hbox = QHBoxLayout()
        prof_hbox.setSpacing(24)
        
        avatar_vbox = QVBoxLayout()
        avatar_vbox.setSpacing(5)
        
        self.lbl_avatar = QLabel()
        self.lbl_avatar.setFixedSize(64, 64)
        self.lbl_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load existing pic
        profile = self.load_user_profile()
        pic_path = profile.get("profile_pic", "")
        import os
        from PyQt6.QtGui import QPixmap
        if pic_path and os.path.exists(pic_path):
            pix = QPixmap(pic_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.lbl_avatar.setPixmap(pix)
            self.lbl_avatar.setStyleSheet("border-radius: 32px;")
        elif HAS_QTA:
            self.lbl_avatar.setPixmap(qta.icon("fa5s.user-circle", color=C_PRI).pixmap(64, 64))
        else:
            self.lbl_avatar.setText("👤")
            self.lbl_avatar.setStyleSheet("font-size: 48px; background: transparent;")
            
        avatar_vbox.addWidget(self.lbl_avatar)
        
        btn_change_pic = QPushButton("Cambiar foto")
        btn_change_pic.setStyleSheet("font-size: 10px; padding: 2px; color: #a855f7;")
        btn_change_pic.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_change_pic.clicked.connect(self._change_profile_pic)
        avatar_vbox.addWidget(btn_change_pic)
        
        prof_hbox.addLayout(avatar_vbox)
        
        details_layout = QVBoxLayout()
        details_layout.setSpacing(6)
        
        self.lbl_user_name_title = QLabel("Cargando usuario...")
        self.lbl_user_name_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff; background: transparent;")
        details_layout.addWidget(self.lbl_user_name_title)
        
        self.lbl_user_email = QLabel("Email: No registrado")
        self.lbl_user_email.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.6); background: transparent;")
        details_layout.addWidget(self.lbl_user_email)

        self.lbl_user_license = QLabel("Licencia: —")
        self.lbl_user_license.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.6); background: transparent;")
        details_layout.addWidget(self.lbl_user_license)

        self.lbl_user_stats = QLabel("Sin estadísticas de uso.")
        self.lbl_user_stats.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.4); background: transparent;")
        details_layout.addWidget(self.lbl_user_stats)
        
        prof_hbox.addLayout(details_layout)
        prof_hbox.addStretch()
        
        self.btn_edit_profile = QPushButton("✏️ EDITAR NOMBRE")
        self.btn_edit_profile.setFixedSize(140, 36)
        self.btn_edit_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit_profile.clicked.connect(self._change_user_name)
        self.btn_edit_profile.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.7);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.9);
            }
        """)
        prof_hbox.addWidget(self.btn_edit_profile)
        
        layout_user.addLayout(prof_hbox, 0, 0, 1, 2)
        
        # Hidden input that standard save expects to read name from:
        self.inp_user_name = QLineEdit(self)
        self.inp_user_name.setVisible(False)
        
        # --- Card 2: 🎨 TEMA Y ESTILOS ---
        card1 = tab.add_card("🎨 TEMA Y ESTILOS", col_span=2)
        layout1 = card1.content_layout
        
        self.cmb_theme = QComboBox()
        self.cmb_theme.setMinimumHeight(40)
        for k in THEMES:
            if k != "custom":
                self.cmb_theme.addItem(k.upper(), k)
        self.cmb_theme.addItem("PERSONALIZADO", "custom")
        self.cmb_theme.currentIndexChanged.connect(self._toggle_theme_fields)
        layout1.addWidget(QLabel("Tema HUD:"), 0, 0)
        layout1.addWidget(self.cmb_theme, 0, 1)

        self.btn_color_picker = QPushButton("SELECCIONAR COLOR ACENTO")
        self.btn_color_picker.setFixedHeight(40)
        self.btn_color_picker.clicked.connect(self._open_color_picker)
        layout1.addWidget(self.btn_color_picker, 1, 0, 1, 2)
        
        self.lbl_color_preview = QLabel("MUESTRA")
        self.lbl_color_preview.setFixedSize(180, 30)
        self.lbl_color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_color_preview.setStyleSheet("border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:transparent;")
        layout1.addWidget(self.lbl_color_preview, 2, 0, 1, 2)

        self.cmb_font_family = QComboBox()
        self.cmb_font_family.setMinimumHeight(40)
        for f, d in [("Century Gothic", "Century Gothic"), ("Orbitron", "Orbitron"),
                     ("Inter", "Inter"), ("Consolas", "Consolas"), ("Montserrat", "Montserrat")]:
            self.cmb_font_family.addItem(d, f)
        layout1.addWidget(QLabel("Tipografía:"), 3, 0)
        layout1.addWidget(self.cmb_font_family, 3, 1)

        self.btn_custom_font = QPushButton("AÑADIR FUENTE (PREMIUM)")
        self.btn_custom_font.setFixedHeight(40)
        self.btn_custom_font.clicked.connect(self._add_custom_font)
        layout1.addWidget(self.btn_custom_font, 4, 0, 1, 2)

        # --- Card 3: 🛠️ COLOR PERSONALIZADO ---
        card2 = tab.add_card("🛠️ COLOR PERSONALIZADO", col_span=2)
        layout2 = card2.content_layout
        
        grid = QGridLayout()
        grid.setSpacing(12)
        self.btn_color_bg = QPushButton("FONDO HUD")
        self.btn_color_bg.setFixedHeight(40)
        self.btn_color_bg.clicked.connect(lambda: self._select_override_color("bg"))
        grid.addWidget(self.btn_color_bg, 0, 0)
        self.btn_color_panel = QPushButton("PANEL WIDGETS")
        self.btn_color_panel.setFixedHeight(40)
        self.btn_color_panel.clicked.connect(lambda: self._select_override_color("panel"))
        grid.addWidget(self.btn_color_panel, 0, 1)
        self.btn_color_text = QPushButton("COLOR TEXTO")
        self.btn_color_text.setFixedHeight(40)
        self.btn_color_text.clicked.connect(lambda: self._select_override_color("text"))
        grid.addWidget(self.btn_color_text, 1, 0)
        self.btn_color_reset = QPushButton("REINICIAR COLORES")
        self.btn_color_reset.setFixedHeight(40)
        self.btn_color_reset.clicked.connect(self._reset_override_colors)
        self.btn_color_reset.setStyleSheet("""
            QPushButton {
                background: rgba(255,59,48,0.08);
                color: rgba(255,59,48,0.6);
                border: 1px solid rgba(255,59,48,0.15);
            }
            QPushButton:hover {
                background: rgba(255,59,48,0.15);
                color: rgba(255,255,255,0.9);
            }
        """)
        grid.addWidget(self.btn_color_reset, 1, 1)
        layout2.addLayout(grid, 0, 0, 1, 2)

        # --- Card 4: 🖼️ RECURSOS VISUALES ---
        card3 = tab.add_card("🖼️ RECURSOS VISUALES", col_span=2)
        layout3 = card3.content_layout
        
        bg_btns = QHBoxLayout()
        bg_btns.setSpacing(16)
        self.btn_select_bg_image = QPushButton("SELECCIONAR FOTO")
        self.btn_select_bg_image.setFixedHeight(40)
        self.btn_select_bg_image.clicked.connect(self._select_bg_image)
        bg_btns.addWidget(self.btn_select_bg_image)
        self.btn_remove_bg_image = QPushButton("ELIMINAR FOTO")
        self.btn_remove_bg_image.setFixedHeight(40)
        self.btn_remove_bg_image.clicked.connect(self._remove_bg_image)
        self.btn_remove_bg_image.setStyleSheet("""
            QPushButton {
                background: rgba(255,59,48,0.08);
                color: rgba(255,59,48,0.6);
                border: 1px solid rgba(255,59,48,0.15);
            }
            QPushButton:hover {
                background: rgba(255,59,48,0.15);
                color: rgba(255,255,255,0.9);
            }
        """)
        bg_btns.addWidget(self.btn_remove_bg_image)
        layout3.addWidget(QLabel("Imagen de Fondo:"), 0, 0)
        layout3.addLayout(bg_btns, 0, 1, 1, 2)

        op_lay = QHBoxLayout()
        op_lay.setSpacing(12)
        op_lay.addWidget(QLabel("Transparencia:"))
        self.lbl_bg_opacity_val = QLabel("85%")
        self.lbl_bg_opacity_val.setStyleSheet("font-weight:bold;color:rgba(255,255,255,0.6);font-size:13px;")
        op_lay.addStretch()
        op_lay.addWidget(self.lbl_bg_opacity_val)
        layout3.addLayout(op_lay, 1, 0, 1, 3)
        
        self.sld_bg_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sld_bg_opacity.setRange(10, 100)
        self.sld_bg_opacity.setValue(85)
        self.sld_bg_opacity.valueChanged.connect(lambda v: self.lbl_bg_opacity_val.setText(f"{v}%"))
        layout3.addWidget(self.sld_bg_opacity, 2, 0, 1, 3)

        st_btns = QHBoxLayout()
        st_btns.setSpacing(16)
        self.btn_select_sticker = QPushButton("SELECCIONAR STICKER")
        self.btn_select_sticker.setFixedHeight(40)
        self.btn_select_sticker.clicked.connect(self._select_sticker)
        st_btns.addWidget(self.btn_select_sticker)
        self.btn_remove_sticker = QPushButton("ELIMINAR")
        self.btn_remove_sticker.setFixedHeight(40)
        self.btn_remove_sticker.clicked.connect(self._remove_sticker)
        self.btn_remove_sticker.setStyleSheet("""
            QPushButton {
                background: rgba(255,59,48,0.08);
                color: rgba(255,59,48,0.6);
                border: 1px solid rgba(255,59,48,0.15);
            }
            QPushButton:hover {
                background: rgba(255,59,48,0.15);
                color: rgba(255,255,255,0.9);
            }
        """)
        st_btns.addWidget(self.btn_remove_sticker)
        layout3.addWidget(QLabel("Sticker Flotante:"), 3, 0)
        layout3.addLayout(st_btns, 3, 1, 1, 2)

        st_size_lay = QHBoxLayout()
        st_size_lay.setSpacing(12)
        self.sld_sticker_w = QSlider(Qt.Orientation.Horizontal)
        self.sld_sticker_w.setRange(20, 250)
        self.sld_sticker_w.setValue(100)
        self.sld_sticker_h = QSlider(Qt.Orientation.Horizontal)
        self.sld_sticker_h.setRange(20, 250)
        self.sld_sticker_h.setValue(100)
        st_size_lay.addWidget(QLabel("Ancho:"))
        st_size_lay.addWidget(self.sld_sticker_w)
        st_size_lay.addWidget(QLabel("Alto:"))
        st_size_lay.addWidget(self.sld_sticker_h)
        layout3.addLayout(st_size_lay, 4, 0, 1, 3)

        # --- Card 5: ⚡ RENDIMIENTO ---
        card4 = tab.add_card("⚡ RENDIMIENTO Y CALIDAD", col_span=2)
        layout4 = card4.content_layout
        
        perf_lay = QHBoxLayout()
        perf_lay.setSpacing(12)
        perf_lay.addWidget(QLabel("Calidad Visual (Orbe):"))
        self.lbl_performance_val = QLabel("80%")
        self.lbl_performance_val.setStyleSheet("font-weight:bold;color:rgba(255,255,255,0.6);font-size:13px;")
        perf_lay.addStretch()
        perf_lay.addWidget(self.lbl_performance_val)
        layout4.addLayout(perf_lay, 0, 0, 1, 2)
        
        self.sld_performance = QSlider(Qt.Orientation.Horizontal)
        self.sld_performance.setRange(1, 100)
        self.sld_performance.setValue(80)
        self.sld_performance.valueChanged.connect(lambda v: self.lbl_performance_val.setText(f"{v}%"))
        layout4.addWidget(self.sld_performance, 1, 0, 1, 2)
        
        self.chk_gpu = QCheckBox("GPU Acceleration (Experimental)")
        self.chk_gpu.setStyleSheet("QCheckBox { padding: 10px 0; }")
        layout4.addWidget(self.chk_gpu, 2, 0, 1, 2)

        self.stacked_widget.addWidget(tab)

    # ─── PESTAÑA INTELIGENCIA (IA CLOUD + IA LOCAL OLLAMA + VOZ) ───────────

    def _build_tab_intelligence(self):
        tab = self._create_tab_widget()
        
        # --- Card 1: INTEGRACIÓN DE IA (Cloud Keys & Provider) ---
        card1 = tab.add_card("🧠 INTEGRACIÓN DE IA", col_span=2)
        layout1 = card1.content_layout
        
        # Gemini API Key
        lbl_gemini = QLabel("🔑 Gemini API Key:")
        lbl_gemini.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_gemini, 0, 0)
        
        self.inp_gemini = QLineEdit()
        self.inp_gemini.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_gemini.setPlaceholderText("Ingresa tu API Key de Gemini")
        self.inp_gemini.setMinimumHeight(42)
        self.inp_gemini.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 16px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgba(245, 158, 11, 0.3);
            }
        """)
        layout1.addWidget(self.inp_gemini, 0, 1, 1, 3)
        
        # OpenRouter API Key
        lbl_openrouter = QLabel("🔓 OpenRouter API Key:")
        lbl_openrouter.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_openrouter, 1, 0)
        
        self.inp_openrouter = QLineEdit()
        self.inp_openrouter.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_openrouter.setPlaceholderText("Ingresa tu API Key de OpenRouter")
        self.inp_openrouter.setMinimumHeight(42)
        self.inp_openrouter.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 16px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgba(245, 158, 11, 0.3);
            }
        """)
        layout1.addWidget(self.inp_openrouter, 1, 1, 1, 3)
        
        # Modelo OpenRouter
        lbl_model = QLabel("🤖 Modelo OpenRouter:")
        lbl_model.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_model, 2, 0)
        
        self.inp_openrouter_model = QLineEdit()
        self.inp_openrouter_model.setPlaceholderText("google/gemini-2.5-flash")
        self.inp_openrouter_model.setMinimumHeight(42)
        self.inp_openrouter_model.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 16px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgba(245, 158, 11, 0.3);
            }
        """)
        layout1.addWidget(self.inp_openrouter_model, 2, 1, 1, 3)
        
        # Proveedor IA
        lbl_provider = QLabel("🎯 Proveedor IA:")
        lbl_provider.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_provider, 3, 0)
        
        self.cmb_ai_provider = QComboBox()
        self.cmb_ai_provider.setMinimumHeight(42)
        self.cmb_ai_provider.addItem("🔵 Google Gemini (Cloud)", "gemini")
        self.cmb_ai_provider.addItem("🟣 OpenRouter (Cloud)", "openrouter")
        self.cmb_ai_provider.addItem("🟢 Ollama (Local)", "ollama")
        self.cmb_ai_provider.setStyleSheet("""
            QComboBox {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 8px 14px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background: rgba(10,15,25,0.95);
                color: rgba(255,255,255,0.9);
                selection-background-color: rgba(245,158,11,0.2);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 4px;
            }
        """)
        layout1.addWidget(self.cmb_ai_provider, 3, 1, 1, 3)
        
        # Zona Horaria
        lbl_timezone = QLabel("🌐 Zona Horaria:")
        lbl_timezone.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_timezone, 4, 0)
        
        self.cmb_timezone = QComboBox()
        self.cmb_timezone.setMinimumHeight(42)
        self.timezones = [
            ("America/Lima", "Perú (GMT-5)"),
            ("America/Bogota", "Colombia (GMT-5)"),
            ("America/Argentina/Buenos_Aires", "Argentina (GMT-3)"),
            ("America/Santiago", "Chile (GMT-3)"),
            ("America/Mexico_City", "México (GMT-6)"),
            ("America/Caracas", "Venezuela (GMT-4)"),
            ("Europe/Madrid", "España (GMT+1)"),
            ("America/New_York", "Estados Unidos (GMT-5)")
        ]
        for val, desc in self.timezones:
            self.cmb_timezone.addItem(desc, val)
            
        self.cmb_timezone.setStyleSheet("""
            QComboBox {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 8px 14px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background: rgba(10,15,25,0.95);
                color: rgba(255,255,255,0.9);
                selection-background-color: rgba(245,158,11,0.2);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 4px;
            }
        """)
        layout1.addWidget(self.cmb_timezone, 4, 1, 1, 3)
        
        # --- Card 2: 🟢 CONFIGURACIÓN OLLAMA ---
        card_ollama = tab.add_card("🟢 CONFIGURACIÓN OLLAMA", col_span=2)
        layout_ollama = card_ollama.content_layout
        
        lbl_ollama_url = QLabel("🌐 URL de Ollama:")
        lbl_ollama_url.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout_ollama.addWidget(lbl_ollama_url, 0, 0)
        
        self.inp_ollama_url = QLineEdit()
        self.inp_ollama_url.setPlaceholderText("http://127.0.0.1:11434")
        self.inp_ollama_url.setMinimumHeight(42)
        self.inp_ollama_url.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 10px 16px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: rgba(245, 158, 11, 0.3);
            }
        """)
        layout_ollama.addWidget(self.inp_ollama_url, 0, 1, 1, 3)
        
        lbl_ollama_model = QLabel("📦 Modelo Ollama:")
        lbl_ollama_model.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout_ollama.addWidget(lbl_ollama_model, 1, 0)
        
        self.cmb_ollama_model = QComboBox()
        self.cmb_ollama_model.setEditable(True)
        self.cmb_ollama_model.setMinimumHeight(42)
        self.cmb_ollama_model.setPlaceholderText("Ej: gemma2:2b, llama3.2, deepseek-r1:1.5b")
        self.cmb_ollama_model.setStyleSheet("""
            QComboBox {
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 8px 14px;
                color: rgba(255,255,255,0.9);
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background: rgba(10,15,25,0.95);
                color: rgba(255,255,255,0.9);
                selection-background-color: rgba(245,158,11,0.2);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 4px;
            }
        """)
        layout_ollama.addWidget(self.cmb_ollama_model, 1, 1, 1, 3)
        
        status_box = QHBoxLayout()
        status_box.setSpacing(16)
        self.lbl_ollama_status = QLabel("⏳ ESTADO: SIN VERIFICAR")
        self.lbl_ollama_status.setStyleSheet("color: rgba(255,255,255,0.5); font-weight: bold; font-size: 12px; letter-spacing: 1.5px;")
        status_box.addWidget(self.lbl_ollama_status)
        status_box.addStretch()
        self.btn_check_ollama = QPushButton("🔄 VERIFICAR ESTADO")
        self.btn_check_ollama.setMinimumSize(170, 38)
        self.btn_check_ollama.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.7);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                font-weight: 600;
                font-size: 11px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: rgba(255,255,255,0.9);
            }
        """)
        self.btn_check_ollama.clicked.connect(self.check_ollama_status)
        status_box.addWidget(self.btn_check_ollama)
        layout_ollama.addLayout(status_box, 2, 0, 1, 4)
        
        self.btn_install_ollama = QPushButton("⬇️ DESCARGAR INSTALADOR WINDOWS")
        self.btn_install_ollama.setMinimumHeight(44)
        self.btn_install_ollama.setStyleSheet("""
            QPushButton {
                background: rgba(245, 158, 11, 0.1);
                color: rgba(245, 158, 11, 0.8);
                border: 1px solid rgba(245, 158, 11, 0.2);
                border-radius: 10px;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: rgba(245, 158, 11, 0.2);
                color: rgba(245, 158, 11, 0.9);
                border-color: rgba(245, 158, 11, 0.4);
            }
        """)
        self.btn_install_ollama.clicked.connect(self.start_install_ollama)
        layout_ollama.addWidget(self.btn_install_ollama, 3, 0, 1, 4)
        
        # --- Card 3: 🎤 MÓDULO DE VOZ ---
        card2 = tab.add_card("🎤 MÓDULO DE VOZ", col_span=2)
        layout2 = card2.content_layout
        
        self.cmb_voice = QComboBox()
        self.cmb_voice.setMinimumHeight(40)
        voices = [
            ("Aoede", "Aoede (Femenina)"),
            ("Charon", "Charon (Masculina)"),
            ("Fenrir", "Fenrir (Masculina)"),
            ("Kore", "Kore (Femenina)"),
            ("Puck", "Puck (Masculina)")
        ]
        for val, desc in voices:
            self.cmb_voice.addItem(desc, val)
        layout2.addWidget(QLabel("Voz por defecto (Gemini):"), 0, 0)
        layout2.addWidget(self.cmb_voice, 0, 1)

        self.chk_fish_audio = QCheckBox("Habilitar Fish Audio TTS (Premium)")
        self.chk_fish_audio.setStyleSheet("QCheckBox { padding: 8px 0; }")
        self.chk_fish_audio.toggled.connect(self._toggle_fish_fields)
        layout2.addWidget(self.chk_fish_audio, 1, 0, 1, 2)

        self.inp_fish_api_key = QLineEdit()
        self.inp_fish_api_key.setPlaceholderText("API Key de Fish Audio")
        self.inp_fish_api_key.setMinimumHeight(40)
        self.inp_fish_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_fish_voice_id = QLineEdit()
        self.inp_fish_voice_id.setPlaceholderText("Voice ID de tu modelo entrenado")
        self.inp_fish_voice_id.setMinimumHeight(40)

        layout2.addWidget(QLabel("API Key:"), 2, 0)
        layout2.addWidget(self.inp_fish_api_key, 2, 1)
        layout2.addWidget(QLabel("Voice ID:"), 3, 0)
        layout2.addWidget(self.inp_fish_voice_id, 3, 1)

        self.chk_local_tts = QCheckBox("Habilitar Coqui Local TTS (Voz local sin internet)")
        self.chk_local_tts.setStyleSheet("QCheckBox { padding: 8px 0; }")
        layout2.addWidget(self.chk_local_tts, 4, 0, 1, 2)
        self._toggle_fish_fields(False)

        # --- Card 4: 📦 MODELOS OLLAMA RECOMENDADOS ---
        card3 = tab.add_card("📦 MODELOS LOCALES RECOMENDADOS", col_span=2)
        layout3 = card3.content_layout

        self.recommended_models = [
            ("gemma2:2b", "GEMMA 2 2B", "1.6 GB", "Excelente para español"),
            ("llama3.2-vision:11b", "LLAMA 3.2 VISION", "7.9 GB", "Análisis visual local"),
            ("llava:7b", "LLAVA 7B", "4.7 GB", "Modelo multimodal"),
            ("llama3:latest", "LLAMA 3 8B", "4.7 GB", "Meta AI potente"),
            ("deepseek-r1:1.5b", "DEEPSEEK R1 1.5B", "900 MB", "Razonamiento ultra-ligero"),
            ("deepseek-r1:8b", "DEEPSEEK R1 8B", "4.7 GB", "Razonamiento avanzado"),
        ]
        self.model_cards = {}
        for i, (code, name, size, desc) in enumerate(self.recommended_models):
            row = i // 2
            col = i % 2
            model_frame = QFrame()
            model_frame.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 16px;
                }
            """)
            m_layout = QVBoxLayout(model_frame)
            m_layout.setContentsMargins(18, 16, 18, 16)
            m_layout.setSpacing(10)

            hdr = QHBoxLayout()
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("color:white;font-weight:bold;font-size:13px;letter-spacing:0.5px;background:transparent;")
            hdr.addWidget(lbl_name)
            hdr.addStretch()
            lbl_size = QLabel(size)
            lbl_size.setStyleSheet("color:rgba(200,200,210,0.5);font-size:11px;background:transparent;")
            hdr.addWidget(lbl_size)
            m_layout.addLayout(hdr)

            lbl_desc = QLabel(desc)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color:rgba(200,200,210,0.7);font-size:11px;background:transparent;")
            m_layout.addWidget(lbl_desc)

            actions = QHBoxLayout()
            actions.addStretch()
            btn_action = QPushButton("DESCARGAR")
            btn_action.setMinimumSize(130, 34)
            btn_action.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.04);
                    color: rgba(255,255,255,0.4);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 10px;
                    font-weight: bold;
                    font-size: 10px;
                    letter-spacing: 0.8px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.08);
                    color: rgba(255,255,255,0.8);
                }
            """)
            actions.addWidget(btn_action)
            m_layout.addLayout(actions)

            layout3.addWidget(model_frame, row, col)
            self.model_cards[code] = {"card": model_frame, "btn_action": btn_action, "lbl_status": lbl_size}

        # --- Card 5: 📥 PANEL DE DESCARGAS ---
        card4 = tab.add_card("📥 PANEL DE DESCARGAS", col_span=2)
        layout4 = card4.content_layout
        
        self.lbl_progress_status = QLabel("DESCARGAS INACTIVAS")
        self.lbl_progress_status.setStyleSheet("color:rgba(255,255,255,0.3);font-weight:bold;font-size:11px;letter-spacing:1.5px;background:transparent;")
        layout4.addWidget(self.lbl_progress_status, 0, 0, 1, 2)
        
        self.bar_pull_progress = QProgressBar()
        self.bar_pull_progress.setFixedHeight(8)
        self.bar_pull_progress.setRange(0, 100)
        self.bar_pull_progress.setTextVisible(False)
        self.bar_pull_progress.setStyleSheet("""
            QProgressBar {
                background: rgba(255,255,255,0.05);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: rgba(255,255,255,0.3);
                border-radius: 4px;
            }
        """)
        layout4.addWidget(self.bar_pull_progress, 1, 0, 1, 2)
        
        cancel_box = QHBoxLayout()
        cancel_box.setSpacing(12)
        self.btn_cancel_pull = QPushButton("DETENER DESCARGA")
        self.btn_cancel_pull.setMinimumSize(160, 36)
        self.btn_cancel_pull.setEnabled(False)
        self.btn_cancel_pull.clicked.connect(self.cancel_pull)
        self.btn_cancel_pull.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.08);
                color: rgba(239, 68, 68, 0.6);
                border: 1px solid rgba(239, 68, 68, 0.15);
                border-radius: 10px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.15);
                color: white;
            }
        """)
        cancel_box.addWidget(self.btn_cancel_pull)
        cancel_box.addStretch()
        layout4.addLayout(cancel_box, 2, 0, 1, 2)

        # Hook download buttons
        for code, info in self.model_cards.items():
            info["btn_action"].clicked.connect(lambda checked, c=code: self.start_pull(c))

        self.stacked_widget.addWidget(tab)

    def _toggle_fish_fields(self, checked):
        self.inp_fish_api_key.setEnabled(checked)
        self.inp_fish_voice_id.setEnabled(checked)

    # ─── PESTAÑA PERSONALIDAD ─────────────────────────────────────────────

    def _build_tab_personality(self):
        tab = self._create_tab_widget()
        card = tab.add_card("GESTIÓN DE PERSONALIDAD", col_span=2)
        layout = card.content_layout

        self.cmb_personality = QComboBox()
        self.cmb_personality.setMinimumHeight(40)
        self.cmb_personality.currentIndexChanged.connect(self._on_personality_changed)
        layout.addWidget(QLabel("Personalidad Activa:"), 0, 0)
        layout.addWidget(self.cmb_personality, 0, 1, 1, 3)

        layout.addWidget(QLabel("Prompt del Sistema:"), 1, 0, 1, 4)
        self.txt_personality_prompt = QTextEdit()
        self.txt_personality_prompt.setMinimumHeight(180)
        self.txt_personality_prompt.setStyleSheet("""
            QTextEdit {
                background: rgba(0,0,0,0.35);
                color: rgba(255,255,255,0.9);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 18px;
                font-family: Consolas;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: rgba(255,255,255,0.2);
            }
        """)
        self.txt_personality_prompt.textChanged.connect(self._on_personality_prompt_edited)
        layout.addWidget(self.txt_personality_prompt, 2, 0, 1, 4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(18)
        self.btn_rename_pers = QPushButton("RENOMBRAR")
        self.btn_rename_pers.setFixedHeight(40)
        self.btn_rename_pers.clicked.connect(self._rename_active_personality)
        btn_row.addWidget(self.btn_rename_pers)
        self.btn_delete_pers = QPushButton("ELIMINAR")
        self.btn_delete_pers.setFixedHeight(40)
        self.btn_delete_pers.setStyleSheet("""
            QPushButton {
                background: rgba(255,59,48,0.08);
                color: rgba(255,59,48,0.6);
                border: 1px solid rgba(255,59,48,0.15);
                border-radius: 10px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background: rgba(255,59,48,0.15);
                color: rgba(255,255,255,0.9);
            }
        """)
        self.btn_delete_pers.clicked.connect(self._delete_personality)
        btn_row.addWidget(self.btn_delete_pers)
        layout.addLayout(btn_row, 3, 0, 1, 4)

        self.btn_create_pers = QPushButton("CREAR NUEVA PERSONALIDAD")
        self.btn_create_pers.setFixedHeight(44)
        self.btn_create_pers.clicked.connect(self._create_new_personality)
        layout.addWidget(self.btn_create_pers, 4, 0, 1, 2)

        layout.addWidget(QLabel("Generador Rápido:"), 5, 0, 1, 2)
        gen_lay = QHBoxLayout()
        gen_lay.setSpacing(18)
        self.inp_prompt_generator = QLineEdit()
        self.inp_prompt_generator.setPlaceholderText("Ej: Hacker ético sarcástico...")
        self.inp_prompt_generator.setMinimumHeight(40)
        gen_lay.addWidget(self.inp_prompt_generator)
        self.btn_generate_prompt = QPushButton("GENERAR")
        self.btn_generate_prompt.setFixedHeight(40)
        self.btn_generate_prompt.clicked.connect(self._generate_role_prompt)
        gen_lay.addWidget(self.btn_generate_prompt)
        layout.addLayout(gen_lay, 6, 0, 1, 4)

        self.stacked_widget.addWidget(tab)

    # ─── PESTAÑA DISPOSITIVOS & SPOTIFY ────────────────────────────────────

    def _build_tab_devices_combined(self):
        tab = self._create_tab_widget()
        card1 = tab.add_card("DISPOSITIVOS DE ENTRADA/SALIDA", col_span=2)
        layout = card1.content_layout
        
        self.cmb_mic = QComboBox()
        self.cmb_mic.setMinimumHeight(40)
        self.cmb_speaker = QComboBox()
        self.cmb_speaker.setMinimumHeight(40)
        self.cmb_camera = QComboBox()
        self.cmb_camera.setMinimumHeight(40)

        layout.addWidget(QLabel("Micrófono:"), 0, 0)
        layout.addWidget(self.cmb_mic, 0, 1, 1, 2)
        
        sens_lay = QHBoxLayout()
        sens_lay.setSpacing(12)
        self.lbl_mic_sens_val = QLabel("0.0030")
        self.lbl_mic_sens_val.setStyleSheet("font-weight:bold;color:rgba(255,255,255,0.6);font-size:13px;")
        sens_lay.addWidget(QLabel("Sensibilidad VAD:"))
        sens_lay.addStretch()
        sens_lay.addWidget(self.lbl_mic_sens_val)
        layout.addLayout(sens_lay, 1, 0, 1, 3)
        
        self.sld_mic_sens = QSlider(Qt.Orientation.Horizontal)
        self.sld_mic_sens.setRange(1, 100)
        self.sld_mic_sens.setValue(30)
        self.sld_mic_sens.valueChanged.connect(lambda v: self.lbl_mic_sens_val.setText(f"{v / 10000:.4f}"))
        layout.addWidget(self.sld_mic_sens, 2, 0, 1, 3)

        layout.addWidget(QLabel("Altavoz:"), 3, 0)
        layout.addWidget(self.cmb_speaker, 3, 1, 1, 2)

        layout.addWidget(QLabel("Cámara:"), 4, 0)
        layout.addWidget(self.cmb_camera, 4, 1, 1, 2)
        
        self.inp_camera_ip = QLineEdit()
        self.inp_camera_ip.setPlaceholderText("192.168.1.50 (Opcional)")
        self.inp_camera_ip.setMinimumHeight(40)
        layout.addWidget(QLabel("DroidCam IP:"), 5, 0)
        layout.addWidget(self.inp_camera_ip, 5, 1, 1, 2)

        # Spotify Connection Card
        card2 = tab.add_card("🎵 CONFIGURACIÓN DE SPOTIFY", col_span=2)
        layout1 = card2.content_layout
        
        self.chk_advanced_spotify = QCheckBox("Configuración Avanzada")
        self.chk_advanced_spotify.setStyleSheet("QCheckBox { padding: 8px 0; }")
        layout1.addWidget(self.chk_advanced_spotify, 0, 0, 1, 2)
        
        self.inp_spotify_id = QLineEdit()
        self.inp_spotify_id.setMinimumHeight(40)
        self.inp_spotify_id.setPlaceholderText("Client ID")
        self.inp_spotify_secret = QLineEdit()
        self.inp_spotify_secret.setMinimumHeight(40)
        self.inp_spotify_secret.setPlaceholderText("Client Secret")
        self.inp_spotify_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_spotify_uri = QLineEdit()
        self.inp_spotify_uri.setMinimumHeight(40)
        self.inp_spotify_uri.setText("http://127.0.0.1:8765/callback")
        
        layout1.addWidget(QLabel("Client ID:"), 1, 0)
        layout1.addWidget(self.inp_spotify_id, 1, 1)
        layout1.addWidget(QLabel("Client Secret:"), 2, 0)
        layout1.addWidget(self.inp_spotify_secret, 2, 1)
        layout1.addWidget(QLabel("Redirect URI:"), 3, 0)
        layout1.addWidget(self.inp_spotify_uri, 3, 1)
        
        self.chk_advanced_spotify.toggled.connect(self._toggle_advanced_spotify)
        self._toggle_advanced_spotify(False)

        auth_box = QHBoxLayout()
        auth_box.setSpacing(16)
        self.btn_spotify_login = QPushButton("CONECTAR SPOTIFY")
        self.btn_spotify_login.setFixedHeight(40)
        self.btn_spotify_login.clicked.connect(self.connect_spotify)
        self.lbl_spotify_status = QLabel("Consultando…")
        self.lbl_spotify_status.setStyleSheet("color:rgba(255,255,255,0.4);font-size:12px;font-style:italic;")
        auth_box.addWidget(self.btn_spotify_login)
        auth_box.addStretch()
        auth_box.addWidget(self.lbl_spotify_status)
        layout1.addLayout(auth_box, 4, 0, 1, 2)

        note = QLabel("ℹ️ El widget de Spotify se muestra/oculta desde la pestaña AUTOMATIZACIÓN")
        note.setStyleSheet("color:rgba(255,255,255,0.3);font-size:11px;font-style:italic;background:transparent;border:none;padding:8px 0;")
        layout1.addWidget(note, 5, 0, 1, 2)

        self.stacked_widget.addWidget(tab)

    # ─── PESTAÑA AUTOMATIZACIÓN (WIDGETS + MACROS) ─────────────────────────

    def _build_tab_automation(self):
        tab = self._create_tab_widget()
        
        card1 = tab.add_card("🤖 IDENTIDAD DEL SISTEMA", col_span=2)
        layout1 = card1.content_layout
        
        self.inp_ai_name = QLineEdit()
        self.inp_ai_name.setPlaceholderText("I.L.U.M.")
        self.inp_ai_name.setMinimumHeight(40)
        layout1.addWidget(QLabel("Nombre de la IA:"), 0, 0)
        layout1.addWidget(self.inp_ai_name, 0, 1)
        
        icon_lay = QHBoxLayout()
        icon_lay.setSpacing(16)
        self.inp_app_icon = QLineEdit()
        self.inp_app_icon.setPlaceholderText("Ruta al .ico / .png")
        self.inp_app_icon.setMinimumHeight(40)
        self.btn_browse_icon = QPushButton("EXAMINAR...")
        self.btn_browse_icon.setFixedHeight(40)
        self.btn_browse_icon.clicked.connect(self._browse_app_icon)
        icon_lay.addWidget(self.inp_app_icon)
        icon_lay.addWidget(self.btn_browse_icon)
        layout1.addWidget(QLabel("Icono Aplicación:"), 1, 0)
        layout1.addLayout(icon_lay, 1, 1)

        card2 = tab.add_card("🎛️ CONTROL DE WIDGETS", col_span=2)
        layout2 = card2.content_layout
        
        self.chk_widget_spotify = QCheckBox("Mostrar Widget Spotify Flotante")
        self.chk_widget_media = QCheckBox("Mostrar Widget YouTube/Medios (Universal)")
        self.chk_widget_weather = QCheckBox("Mostrar Widget del Clima")
        self.chk_widget_notifications = QCheckBox("Mostrar Panel de Notificaciones")
        self.chk_widget_calendar = QCheckBox("Mostrar Calendario")
        self.chk_widget_system = QCheckBox("Mostrar Widget de Sistema")
        self.chk_widget_todo = QCheckBox("Mostrar Widget de Tareas")
        self.chk_widget_notes = QCheckBox("Mostrar Widget de Notas")
        self.chk_widget_files = QCheckBox("Mostrar Panel de Archivos/Macros")

        widgets = [self.chk_widget_spotify, self.chk_widget_media, self.chk_widget_weather, self.chk_widget_notifications,
                   self.chk_widget_calendar, self.chk_widget_system, self.chk_widget_todo,
                   self.chk_widget_notes, self.chk_widget_files]
        for i, w in enumerate(widgets):
            w.setStyleSheet("QCheckBox { color: rgba(255,255,255,0.7); font-size: 12px; spacing: 14px; padding: 8px 0; }")
            w.setChecked(False)
            layout2.addWidget(w, i // 2, i % 2)

        card3 = tab.add_card("MEMORIA A LARGO PLAZO", col_span=2)
        layout3 = card3.content_layout
        
        self.btn_clear_memory = QPushButton("LIMPIAR MEMORIA DE ILUM")
        self.btn_clear_memory.setFixedHeight(44)
        self.btn_clear_memory.setStyleSheet("""
            QPushButton {
                background: rgba(255,59,48,0.08);
                color: rgba(255,59,48,0.6);
                border: 1px solid rgba(255,59,48,0.15);
                border-radius: 12px;
                padding: 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,59,48,0.15);
                color: rgba(255,255,255,0.9);
            }
        """)
        self.btn_clear_memory.clicked.connect(self._clear_ilum_memory)
        layout3.addWidget(self.btn_clear_memory, 0, 0, 1, 2)

        self.stacked_widget.addWidget(tab)

    # ─── PESTAÑA MACROS ───────────────────────────────────────────────────

    def _build_tab_macros(self):
        tab = self._create_tab_widget()
        card = tab.add_card("GESTIÓN DE MACROS", col_span=2)
        layout = card.content_layout
        
        self.lst_macros = QListWidget()
        self.lst_macros.setStyleSheet("""
            QListWidget {
                background: rgba(0,0,0,0.3);
                color: rgba(255,255,255,0.8);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 14px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 12px 16px;
            }
        """)
        layout.addWidget(self.lst_macros, 0, 0, 1, 2)

        self.btn_record_macro = QPushButton("GRABAR NUEVO MACRO")
        self.btn_record_macro.setFixedHeight(44)
        self.btn_record_macro.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.7);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: rgba(255,255,255,0.95);
            }
        """)
        self.btn_record_macro.clicked.connect(self._open_macro_recorder)
        layout.addWidget(self.btn_record_macro, 1, 0, 1, 2)

        mac_btns = QHBoxLayout()
        mac_btns.setSpacing(18)
        self.btn_del_macro = QPushButton("ELIMINAR")
        self.btn_del_macro.setFixedHeight(40)
        self.btn_del_macro.clicked.connect(self._delete_selected_macro)
        self.btn_run_macro = QPushButton("EJECUTAR")
        self.btn_run_macro.setFixedHeight(40)
        self.btn_run_macro.clicked.connect(self._run_selected_macro)
        mac_btns.addWidget(self.btn_del_macro)
        mac_btns.addWidget(self.btn_run_macro)
        layout.addLayout(mac_btns, 2, 0, 1, 2)

        self.stacked_widget.addWidget(tab)

    # ------------------------------------------------------------------
    # MÉTODOS DE ESTILO - Liquid Glass Ultra Espaciado
    # ------------------------------------------------------------------

    def update_style(self):
        self.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.8);
                font-weight: 500;
                background: transparent;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.9);
                padding: 14px 20px;
                border-radius: 14px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: rgba(255, 255, 255, 0.15);
                background: rgba(0, 0, 0, 0.4);
            }
            QComboBox QAbstractItemView {
                background: rgba(10, 15, 25, 0.95);
                color: rgba(255, 255, 255, 0.9);
                selection-background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 8px;
            }
            QCheckBox {
                color: rgba(255, 255, 255, 0.7);
                font-weight: 500;
                font-size: 13px;
                background: transparent;
                spacing: 16px;
            }
            QCheckBox:hover {
                color: rgba(255, 255, 255, 0.9);
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.04);
                color: rgba(255, 255, 255, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.06);
                font-weight: 600;
                padding: 12px 24px;
                border-radius: 14px;
                font-size: 12px;
                letter-spacing: 0.8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.9);
                border-color: rgba(255, 255, 255, 0.12);
            }
            QSlider::groove:horizontal {
                border: none;
                height: 6px;
                background: rgba(255, 255, 255, 0.06);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: rgba(255, 255, 255, 0.6);
                width: 20px;
                margin: -7px 0;
                border-radius: 10px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(255, 255, 255, 0.8);
            }
            QProgressBar {
                background: rgba(255, 255, 255, 0.04);
                border: none;
                border-radius: 4px;
                text-align: center;
                color: rgba(255, 255, 255, 0.6);
            }
            QProgressBar::chunk {
                background: rgba(255, 255, 255, 0.3);
                border-radius: 4px;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255, 255, 255, 0.02);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.08);
                min-height: 40px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        apply_glass_shadow(self)

    # ═══════════════════════════════════════════════════════════════════════
    # TODOS LOS MÉTODOS DE FUNCIONALIDAD SE MANTIENEN IGUAL
    # (No se modifican para no romper nada)
    # ═══════════════════════════════════════════════════════════════════════
    
    # ── Personality methods ──────────────────────────────────────────────

    def _on_personality_changed(self):
        key = self.cmb_personality.currentData()
        if key and hasattr(self, "_personalities_dict") and key in self._personalities_dict:
            self.txt_personality_prompt.blockSignals(True)
            self.txt_personality_prompt.setPlainText(self._personalities_dict[key]["prompt"])
            self.txt_personality_prompt.blockSignals(False)

    def _on_personality_prompt_edited(self):
        key = self.cmb_personality.currentData()
        if key and hasattr(self, "_personalities_dict") and key in self._personalities_dict:
            self._personalities_dict[key]["prompt"] = self.txt_personality_prompt.toPlainText()

    def _rename_active_personality(self):
        from PyQt6.QtWidgets import QInputDialog
        key = self.cmb_personality.currentData()
        if not key or not hasattr(self, "_personalities_dict") or key not in self._personalities_dict:
            return
        old_name = self._personalities_dict[key]["name"]
        new_name, ok = QInputDialog.getText(self, "Renombrar", f"Nuevo nombre para '{old_name}':", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            self._personalities_dict[key]["name"] = new_name.strip()
            idx = self.cmb_personality.findData(key)
            if idx >= 0:
                self.cmb_personality.setItemText(idx, new_name.strip())

    def _create_new_personality(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Crear Personalidad", "Nombre:")
        if not ok or not name.strip():
            return
        import re
        key = re.sub(r'[^a-z0-9_]', '_', name.strip().lower())
        if not hasattr(self, "_personalities_dict"):
            self._personalities_dict = {}
        if key in self._personalities_dict:
            IlumMessageBox(self, "Error", f"Ya existe '{key}'.").exec()
            return
        self._personalities_dict[key] = {"name": name.strip(), "prompt": "Describe aqui el comportamiento..."}
        self.cmb_personality.blockSignals(True)
        self.cmb_personality.addItem(name.strip(), key)
        self.cmb_personality.setCurrentIndex(self.cmb_personality.count() - 1)
        self.cmb_personality.blockSignals(False)
        self._on_personality_changed()

    def _delete_personality(self):
        key = self.cmb_personality.currentData()
        if not key or not hasattr(self, "_personalities_dict") or key not in self._personalities_dict:
            return
        if key == "actual":
            IlumMessageBox(self, "Error", "No se puede eliminar la personalidad original.").exec()
            return
        if self.cmb_personality.count() <= 1:
            IlumMessageBox(self, "Error", "Debe quedar al menos una personalidad.").exec()
            return
        del self._personalities_dict[key]
        self.cmb_personality.blockSignals(True)
        idx = self.cmb_personality.currentIndex()
        self.cmb_personality.removeItem(idx)
        self.cmb_personality.setCurrentIndex(0)
        self.cmb_personality.blockSignals(False)
        self._on_personality_changed()

    def _generate_role_prompt(self):
        kw = self.inp_prompt_generator.text().strip()
        if not kw:
            return
        prompt = (f"Adopta de manera estricta la siguiente personalidad y rol: {kw}.\n"
                  "Tu comportamiento, tono y manera de expresarte deben estar completamente alineados con esta descripción en cada interacción.")
        self.txt_personality_prompt.setPlainText(prompt)

    def _save_personalities_file(self):
        try:
            from memory.config_manager import BASE_DIR
            pers_path = BASE_DIR / "config" / "personalities.json"
            active_key = self.cmb_personality.currentData()
            pers_data = {"active": active_key, "personalities": getattr(self, "_personalities_dict", {})}
            pers_path.write_text(json.dumps(pers_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"Error saving personalities: {e}")

    # ── Ollama methods ───────────────────────────────────────────────────

    def check_ollama_status(self):
        url = self.inp_ollama_url.text().strip() or "http://127.0.0.1:11434"
        self._is_checking_ollama = True
        self.lbl_ollama_status.setText("ESTADO: COMPROBANDO...")
        self.lbl_ollama_status.setStyleSheet("color: rgba(255,255,255,0.5); font-weight: bold; font-size: 12px; letter-spacing: 1.5px;")
        self.check_worker = OllamaCheckWorker(url)
        self.check_worker.finished_signal.connect(self.on_check_finished)
        self.check_worker.start()

    def on_check_finished(self, is_online, models, version):
        self._is_checking_ollama = False
        if is_online:
            v_str = f" (v{version})" if version else ""
            self.lbl_ollama_status.setText(f"ESTADO: OLLAMA ONLINE{v_str}")
            self.lbl_ollama_status.setStyleSheet("color: rgba(0, 255, 136, 0.7); font-weight: bold; font-size: 12px; letter-spacing: 1.5px;")
            self.update_model_states(models)
            current = self.cmb_ollama_model.currentText()
            self.cmb_ollama_model.blockSignals(True)
            self.cmb_ollama_model.clear()
            for m in models:
                self.cmb_ollama_model.addItem(m, m)
            target = getattr(self, "_active_ollama_model", current)
            if target:
                idx = self.cmb_ollama_model.findText(target)
                if idx >= 0:
                    self.cmb_ollama_model.setCurrentIndex(idx)
                else:
                    self.cmb_ollama_model.addItem(target, target)
                    self.cmb_ollama_model.setCurrentText(target)
            self.cmb_ollama_model.blockSignals(False)
        else:
            self.lbl_ollama_status.setText("ESTADO: OLLAMA OFFLINE")
            self.lbl_ollama_status.setStyleSheet("color: rgba(255, 59, 48, 0.6); font-weight: bold; font-size: 12px; letter-spacing: 1.5px;")
            self.update_model_states([])

    def update_model_states(self, downloaded_models):
        for code, info in self.model_cards.items():
            is_dl = any(dm == code or dm.split(":")[0] == code.split(":")[0] for dm in downloaded_models)
            lbl_status = info.get("lbl_status")
            btn_action = info["btn_action"]
            try:
                btn_action.clicked.disconnect()
            except:
                pass
            if is_dl:
                if lbl_status:
                    lbl_status.setText("INSTALADO ✓")
                    lbl_status.setStyleSheet("color: rgba(0, 255, 136, 0.6); font-size: 10px; background: transparent;")
                btn_action.setText("SELECCIONAR")
                btn_action.setStyleSheet("""
                    QPushButton {
                        background: rgba(0, 255, 136, 0.08);
                        color: rgba(0, 255, 136, 0.6);
                        border: 1px solid rgba(0, 255, 136, 0.15);
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 9px;
                    }
                    QPushButton:hover {
                        background: rgba(0, 255, 136, 0.15);
                        color: rgba(255, 255, 255, 0.9);
                    }
                """)
                btn_action.clicked.connect(lambda checked, c=code: self.select_active_ollama_model(c))
            else:
                if lbl_status:
                    lbl_status.setText(self._get_model_size(code))
                    lbl_status.setStyleSheet("color: rgba(255, 255, 255, 0.3); font-size: 10px; background: transparent;")
                btn_action.setText("DESCARGAR")
                btn_action.setStyleSheet("""
                    QPushButton {
                        background: rgba(255, 255, 255, 0.04);
                        color: rgba(255, 255, 255, 0.4);
                        border: 1px solid rgba(255, 255, 255, 0.06);
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 9px;
                        letter-spacing: 0.8px;
                    }
                    QPushButton:hover {
                        background: rgba(255, 255, 255, 0.08);
                        color: rgba(255, 255, 255, 0.8);
                    }
                """)
                btn_action.clicked.connect(lambda checked, c=code: self.pull_ollama_model(c))

    def _get_model_size(self, code):
        for c, n, s, d in self.recommended_models:
            if c == code:
                return s
        return ""

    def select_active_ollama_model(self, model_name):
        idx = self.cmb_ai_provider.findData("ollama")
        if idx >= 0:
            self.cmb_ai_provider.setCurrentIndex(idx)
        idx_model = self.cmb_ollama_model.findText(model_name)
        if idx_model >= 0:
            self.cmb_ollama_model.setCurrentIndex(idx_model)
        else:
            self.cmb_ollama_model.addItem(model_name, model_name)
            self.cmb_ollama_model.setCurrentText(model_name)
        IlumMessageBox(self, "SUCCESS", f"Modelo {model_name.upper()} seleccionado.").exec()

    def pull_ollama_model(self, model_name):
        self.start_pull(model_name)

    def start_install_ollama(self):
        for info in self.model_cards.values():
            info["btn_action"].setEnabled(False)
        self.btn_custom_pull.setEnabled(False)
        self.btn_install_ollama.setEnabled(False)
        self.lbl_progress_status.setText("INICIANDO DESCARGA DEL INSTALADOR")
        self.bar_pull_progress.setValue(0)
        self.btn_cancel_pull.setEnabled(True)
        self.install_worker = OllamaInstallerWorker()
        self.install_worker.progress_signal.connect(self.on_pull_progress)
        self.install_worker.start()

    def start_pull(self, model_name):
        url = self.inp_ollama_url.text().strip() or "http://127.0.0.1:11434"
        for info in self.model_cards.values():
            info["btn_action"].setEnabled(False)
        self.btn_custom_pull.setEnabled(False)
        self.lbl_progress_status.setText(f"DESCARGANDO: {model_name.upper()}")
        self.bar_pull_progress.setValue(0)
        self.btn_cancel_pull.setEnabled(True)
        self.pull_worker = OllamaPullWorker(model_name, url)
        self.pull_worker.progress_signal.connect(self.on_pull_progress)
        self.pull_worker.start()

    def on_pull_progress(self, status, percent, error):
        if status == "success":
            self.lbl_progress_status.setText("DESCARGA COMPLETADA")
            self.bar_pull_progress.setValue(100)
            self.finish_pull()
            IlumMessageBox(self, "SUCCESS", "DESCARGA DE MODELO COMPLETADA.").exec()
        elif status == "success_installer":
            self.lbl_progress_status.setText("INSTALADOR ABIERTO")
            self.bar_pull_progress.setValue(100)
            self.finish_pull()
        elif status in ("cancelled", "error"):
            self.lbl_progress_status.setText(f"{'CANCELADO' if status=='cancelled' else 'ERROR: '+error.upper()}")
            self.bar_pull_progress.setValue(0)
            self.finish_pull()
            if status == "error":
                IlumMessageBox(self, "ERROR", f"Fallo: {error}", is_error=True).exec()
        else:
            self.lbl_progress_status.setText(f"{status.upper()}: {percent}%")
            self.bar_pull_progress.setValue(percent)

    def cancel_pull(self):
        if hasattr(self, "pull_worker") and self.pull_worker and self.pull_worker.isRunning():
            self.pull_worker.is_running = False
            self.pull_worker.wait()
            self.finish_pull()

    def finish_pull(self):
        for info in self.model_cards.values():
            info["btn_action"].setEnabled(True)
        self.btn_custom_pull.setEnabled(True)
        self.btn_install_ollama.setEnabled(True)
        self.btn_cancel_pull.setEnabled(False)
        self.check_ollama_status()

    def pull_custom_model(self):
        model = self.inp_custom_model.text().strip()
        if not model:
            IlumMessageBox(self, "WARNING", "Escribe un nombre de modelo válido.", is_error=True).exec()
            return
        self.start_pull(model)

    # ── Appearance helpers ───────────────────────────────────────────────

    def _toggle_theme_fields(self):
        if not hasattr(self, "btn_color_picker"):
            return
        is_custom = (self.cmb_theme.currentData() == "custom")
        self.btn_color_picker.setVisible(is_custom)
        self.lbl_color_preview.setVisible(is_custom)

    def _open_color_picker(self):
        try:
            from shop import load_unlocks
            from memory.ui_helpers import IlumMessageBox
            if not load_unlocks().get("neon_color", False):
                IlumMessageBox(self, "Tienda ILUM", "Para usar colores de acento personalizados necesitas desbloquear el complemento 'Color Neón' en la tienda.").exec()
                return
        except Exception as e:
            print("Error validating neon_color:", e)

        initial = QColor(self.custom_color_hex) if self.custom_color_hex else QColor("rgba(255,255,255,0.8)")
        dialog = IlumColorPicker(self, initial)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.custom_color_hex = dialog.selected_color.name()
            self.lbl_color_preview.setStyleSheet(
                f"background-color:{self.custom_color_hex};border:1.5px solid rgba(255,255,255,0.2);border-radius:4px;")

    def _select_override_color(self, target):
        initial = {"bg": QColor(C_BG), "panel": QColor("rgba(255,255,255,0.05)"), "text": QColor("rgba(255,255,255,0.8)")}.get(target, QColor("rgba(255,255,255,0.8)"))
        color = QColorDialog.getColor(initial, self, f"Color de {target.upper()}")
        if color.isValid():
            if target == "bg":
                self._custom_bg_color = color.name()
            elif target == "panel":
                self._custom_panel_color = f"rgba({color.red()},{color.green()},{color.blue()},0.70)"
            elif target == "text":
                self._custom_text_color = color.name()

    def _reset_override_colors(self):
        self._custom_bg_color = ""
        self._custom_panel_color = ""
        self._custom_text_color = ""

    def _add_custom_font(self):
        try:
            from shop import load_unlocks
            from memory.ui_helpers import IlumMessageBox
            if not load_unlocks().get("custom_fonts", False):
                IlumMessageBox(self, "Tienda ILUM", "Para instalar tipografías desde archivos necesitas desbloquear el complemento 'Fuentes Premium' en la tienda.").exec()
                return
        except Exception as e:
            print("Error validating custom_fonts:", e)
            
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QFontDatabase
        fp, _ = QFileDialog.getOpenFileName(self, "Seleccionar Fuente", "", "Fuentes (*.ttf *.otf)")
        if fp:
            font_id = QFontDatabase.addApplicationFont(fp)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    family = font_families[0]
                    self.cmb_font_family.addItem(family + " (Custom)", family)
                    self.cmb_font_family.setCurrentText(family)

    def _select_bg_image(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(self, "Imagen de Fondo", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)")
        if fp:
            if fp.lower().endswith(".gif"):
                try:
                    from shop import load_unlocks
                    from memory.ui_helpers import IlumMessageBox
                    if not load_unlocks().get("gif_wallpaper", False):
                        IlumMessageBox(self, "Tienda ILUM", "Para usar fondos animados (GIF) necesitas desbloquear el complemento 'GIF Wallpaper' en la tienda.").exec()
                        return
                except Exception as e:
                    print("Error validating gif_wallpaper:", e)
            self._custom_bg_image = fp

    def _remove_bg_image(self):
        self._custom_bg_image = ""

    def _select_sticker(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(self, "Seleccionar Sticker", "", "Imágenes (*.png *.jpg *.jpeg *.gif)")
        if fp:
            self._custom_sticker_path = fp

    def _remove_sticker(self):
        self._custom_sticker_path = ""

    def _toggle_advanced_spotify(self, checked):
        for w in (self.inp_spotify_id, self.inp_spotify_secret, self.inp_spotify_uri):
            w.setVisible(checked)

    def _browse_app_icon(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Icono", "", "Images (*.png *.ico)")
        if path:
            self.inp_app_icon.setText(path)

    def _clear_ilum_memory(self):
        reply = QMessageBox.question(self, "Confirmar", "¿Borrar TODA la memoria de ILUM?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from memory.memory_manager import forget_memory
                forget_memory()
                QMessageBox.information(self, "Listo", "Memoria borrada.")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ── Macros ───────────────────────────────────────────────────────────

    def load_macros(self):
        self.lst_macros.clear()
        try:
            from memory.config_manager import BASE_DIR
            mp = BASE_DIR / "config" / "macros.json"
            if mp.exists():
                with open(mp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name in data:
                    self.lst_macros.addItem(name)
        except Exception as e:
            print("Error loading macros:", e)

    def _open_macro_recorder(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Grabar Macro", "Nombre:")
        if ok and name.strip():
            name = name.strip()
            self.btn_record_macro.setText("Grabando…")
            self.btn_record_macro.setEnabled(False)
            import threading

            def _rec():
                try:
                    from actions.macro_recorder import record_macro_until_esc
                    record_macro_until_esc(name)
                    from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                    QMetaObject.invokeMethod(self, "_on_macro_record_finished",
                                             Qt.ConnectionType.QueuedConnection,
                                             Q_ARG(str, name), Q_ARG(str, "success"))
                except Exception as e:
                    from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                    QMetaObject.invokeMethod(self, "_on_macro_record_finished",
                                             Qt.ConnectionType.QueuedConnection,
                                             Q_ARG(str, name), Q_ARG(str, str(e)))

            threading.Thread(target=_rec, daemon=True).start()

    @pyqtSlot(str, str)
    def _on_macro_record_finished(self, name: str, result: str):
        self.btn_record_macro.setText("GRABAR NUEVO MACRO")
        self.btn_record_macro.setEnabled(True)
        if result == "success":
            QMessageBox.information(self, "OK", f"Macro '{name}' grabado.")
            self.load_macros()
        else:
            QMessageBox.critical(self, "Error", f"Error: {result}")

    def _delete_selected_macro(self):
        item = self.lst_macros.currentItem()
        if not item:
            return
        try:
            from memory.config_manager import BASE_DIR
            mp = BASE_DIR / "config" / "macros.json"
            if mp.exists():
                with open(mp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.pop(item.text(), None)
                with open(mp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            self.load_macros()
        except Exception:
            pass

    def _run_selected_macro(self):
        item = self.lst_macros.currentItem()
        if not item:
            return
        try:
            import threading
            from actions.macro_recorder import play_macro
            threading.Thread(target=play_macro, args=(item.text(),), daemon=True).start()
        except Exception:
            pass

    # ── Spotify ──────────────────────────────────────────────────────────

    def check_spotify_auth_status(self):
        try:
            cid = self.inp_spotify_id.text().strip() or "455d312ba37a4e0c8be373b53f6305a4"
            csec = self.inp_spotify_secret.text().strip() or "5a075d9e504c4f3cb4cc6c5e533d1b4a"
            ru = self.inp_spotify_uri.text().strip() or "http://127.0.0.1:8765/callback"
            from memory.config_manager import BASE_DIR
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
            sp = SpotifyOAuth(client_id=cid, client_secret=csec, redirect_uri=ru,
                              open_browser=False, cache_path=str(BASE_DIR / ".spotify_cache"))
            tok = sp.get_cached_token()
            if tok:
                self.lbl_spotify_status.setStyleSheet("color: rgba(29, 185, 84, 0.8); font-weight: bold;")
                return "Conectado"
            else:
                self.lbl_spotify_status.setStyleSheet("color: rgba(255, 59, 48, 0.6); font-weight: bold;")
                return "Desconectado"
        except Exception as e:
            return f"Error: {e}"

    def connect_spotify(self):
        import threading
        import webbrowser
        import urllib.parse
        from http.server import HTTPServer, BaseHTTPRequestHandler

        cid = self.inp_spotify_id.text().strip() or "455d312ba37a4e0c8be373b53f6305a4"
        csec = self.inp_spotify_secret.text().strip() or "5a075d9e504c4f3cb4cc6c5e533d1b4a"
        ru_raw = self.inp_spotify_uri.text().strip() or "http://127.0.0.1:8765/callback"
        port = urllib.parse.urlparse(ru_raw).port or 8765
        ru = f"http://127.0.0.1:{port}/callback"

        self.lbl_spotify_status.setText("Abriendo…")
        self.btn_spotify_login.setEnabled(False)

        from memory.config_manager import BASE_DIR
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        sp_oauth = SpotifyOAuth(client_id=cid, client_secret=csec, redirect_uri=ru,
                                scope="user-modify-playback-state user-read-playback-state user-read-currently-playing user-library-read user-library-modify",
                                open_browser=False, cache_path=str(BASE_DIR / ".spotify_cache"))

        auth_url = sp_oauth.get_authorize_url()
        ev = threading.Event()
        res = {"ok": False, "err": ""}
        outer = self

        class _H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                prs = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(prs.query)
                if prs.path == "/callback":
                    code = qs.get("code", [None])[0]
                    err = qs.get("error", [None])[0]
                    if err:
                        res["err"] = err
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b"Error")
                        ev.set()
                    elif code:
                        try:
                            sp_oauth.get_access_token(code, as_dict=False)
                            res["ok"] = True
                        except Exception as ex:
                            res["err"] = str(ex)
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(
                            "<h2 style='font-family:sans-serif;text-align:center;margin-top:120px;color:white;background:rgba(0,0,0,0.8);padding:40px;border-radius:20px;'>Spotify Conectado ✓<br><small style='color:rgba(255,255,255,0.5);'>Puedes cerrar esta ventana</small></h2>".encode(
                                "utf-8"))
                        ev.set()
                    else:
                        self.send_response(200)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

        def _srv():
            try:
                srv = HTTPServer(("127.0.0.1", port), _H)
                srv.timeout = 1.0
                t = 0
                while not ev.is_set() and t < 300:
                    srv.handle_request()
                    t += 1
                srv.server_close()
                if res["ok"]:
                    QTimer.singleShot(0, outer.spotify_auth_success)
                else:
                    QTimer.singleShot(0, lambda: outer.spotify_auth_failed(res.get("err", "Tiempo agotado")))
            except Exception as ex:
                QTimer.singleShot(0, lambda: outer.spotify_auth_failed(str(ex)))

        threading.Thread(target=_srv, daemon=True).start()
        threading.Thread(target=lambda: (__import__("time").sleep(0.5), webbrowser.open(auth_url)), daemon=True).start()

    def spotify_auth_success(self):
        self.btn_spotify_login.setEnabled(True)
        self.lbl_spotify_status.setText("Conectado")
        self.lbl_spotify_status.setStyleSheet("color: rgba(29, 185, 84, 0.8); font-weight: bold;")
        IlumMessageBox(self, "Spotify", "¡Autenticación exitosa!").exec()

    def spotify_auth_failed(self, error):
        self.btn_spotify_login.setEnabled(True)
        self.lbl_spotify_status.setText("Error")
        self.lbl_spotify_status.setStyleSheet("color: rgba(255, 59, 48, 0.6); font-weight: bold;")
        IlumMessageBox(self, "Error Spotify", f"Fallo: {error}", is_error=True).exec()

    # ── Load / Save ──────────────────────────────────────────────────────

    def load_settings(self):
        self.cmb_camera.clear()
        try:
            from PyQt6.QtMultimedia import QMediaDevices
            cams = QMediaDevices.videoInputs()
            if not cams:
                for i, n in enumerate(["Principal (0)", "Secundaria (1)", "Externa (2)"]):
                    self.cmb_camera.addItem(n, i)
            else:
                for i, c in enumerate(cams):
                    self.cmb_camera.addItem(f"{c.description()} ({i})", i)
        except Exception:
            for i, n in enumerate(["Principal (0)", "Secundaria (1)", "Externa (2)"]):
                self.cmb_camera.addItem(n, i)

        try:
            import sounddevice as sd
            devs = sd.query_devices()
            self.cmb_mic.addItem("Default", "")
            self.cmb_speaker.addItem("Default", "")
            for i, d in enumerate(devs):
                if d.get("max_input_channels", 0) > 0:
                    self.cmb_mic.addItem(d["name"], i)
                if d.get("max_output_channels", 0) > 0:
                    self.cmb_speaker.addItem(d["name"], i)
        except Exception:
            pass

        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()

            self.inp_gemini.setText(cfg.get("gemini_api_key", ""))
            self.inp_openrouter.setText(cfg.get("openrouter_api_key", ""))
            self.inp_openrouter_model.setText(cfg.get("openrouter_model", "google/gemini-2.5-flash"))
            self.inp_ai_name.setText(cfg.get("ai_name", ""))
            self.inp_app_icon.setText(cfg.get("ilum_app_icon", ""))

            prov = cfg.get("ai_provider", "gemini")
            idx = self.cmb_ai_provider.findData(prov)
            if idx >= 0:
                self.cmb_ai_provider.setCurrentIndex(idx)

            voice = cfg.get("ilum_voice", "Aoede")
            for i in range(self.cmb_voice.count()):
                if self.cmb_voice.itemData(i) == voice:
                    self.cmb_voice.setCurrentIndex(i)
                    break

            self.chk_fish_audio.setChecked(cfg.get("fish_audio_enabled", False))
            self.inp_fish_api_key.setText(cfg.get("fish_api_key", ""))
            self.inp_fish_voice_id.setText(cfg.get("fish_voice_id", ""))
            self.chk_local_tts.setChecked(cfg.get("local_tts_enabled", False))
            self.inp_ollama_url.setText(cfg.get("ollama_url", "http://127.0.0.1:11434"))
            self._active_ollama_model = cfg.get("ollama_model", "gemma2:2b")

            theme = cfg.get("ilum_theme", "gold")
            self.custom_color_hex = cfg.get("ilum_custom_theme_color", "")
            idx = self.cmb_theme.findData(theme)
            if idx >= 0:
                self.cmb_theme.setCurrentIndex(idx)
            self._toggle_theme_fields()
            if self.custom_color_hex:
                self.lbl_color_preview.setStyleSheet(
                    f"background-color:{self.custom_color_hex};border:1.5px solid rgba(255,255,255,0.2);border-radius:4px;")

            tz = cfg.get("timezone", "America/Lima")
            idx = self.cmb_timezone.findData(tz)
            if idx >= 0:
                self.cmb_timezone.setCurrentIndex(idx)

            username = cfg.get("user_name", "Usuario")
            self.inp_user_name.setText(username)
            self.lbl_user_name_title.setText(f"Usuario Registrado: {username}")
            try:
                import json
                from memory.config_manager import BASE_DIR
                lic_path = BASE_DIR / "config" / "license.json"
                if lic_path.exists():
                    lic = json.loads(lic_path.read_text(encoding="utf-8"))
                    email = lic.get("email", "")
                    if email:
                        self.lbl_user_email.setText(f"Licencia vinculada: {email}")
                    else:
                        self.lbl_user_email.setText("Licencia local activa")

                    key = lic.get("license_key", "")
                    days_remaining = lic.get("days_remaining")

                    if key:
                        # Mostrar la key ofuscada en el medio, ej: ILUM-7MZV-****-5J06
                        parts = key.split("-")
                        if len(parts) >= 2:
                            masked_key = f"{parts[0]}-{parts[1]}-****-{parts[-1]}"
                        else:
                            masked_key = key
                    else:
                        masked_key = "No disponible"

                    if days_remaining is None:
                        days_txt = "de por vida ✦"
                    elif days_remaining <= 0:
                        days_txt = "expirada"
                    elif days_remaining == 1:
                        days_txt = "1 día"
                    else:
                        days_txt = f"{days_remaining} días"

                    self.lbl_user_license.setText(f"Key: {masked_key}  ·  Vence en: {days_txt}")
                else:
                    self.lbl_user_email.setText("Licencia no registrada (Modo Demo)")
                    self.lbl_user_license.setText("Licencia: —")
            except Exception:
                self.lbl_user_email.setText("Licencia activa")
                self.lbl_user_license.setText("Licencia: —")

            try:
                profile = self.load_user_profile()
                habits = profile.get("habits", {})
                if habits:
                    sorted_habits = sorted(habits.items(), key=lambda x: x[1], reverse=True)
                    top_cmd = sorted_habits[0][0]
                    top_count = sorted_habits[0][1]
                    self.lbl_user_stats.setText(f"Estadísticas: Comando más usado '{top_cmd}' ({top_count} veces)")
                else:
                    self.lbl_user_stats.setText("Estadísticas: Listo para registrar comandos.")
            except Exception:
                self.lbl_user_stats.setText("Estadísticas: No disponibles.")

            mic = cfg.get("mic_device", "")
            idx = self.cmb_mic.findData(mic)
            if idx >= 0:
                self.cmb_mic.setCurrentIndex(idx)

            ms = float(cfg.get("mic_sensitivity", 0.003))
            self.sld_mic_sens.setValue(int(ms * 10000))

            spk = cfg.get("speaker_device", "")
            idx = self.cmb_speaker.findData(spk)
            if idx >= 0:
                self.cmb_speaker.setCurrentIndex(idx)

            cam = int(cfg.get("camera_device", 0))
            idx = self.cmb_camera.findData(cam)
            if idx >= 0:
                self.cmb_camera.setCurrentIndex(idx)

            self.inp_camera_ip.setText(cfg.get("camera_ip", ""))

            self.inp_spotify_id.setText(cfg.get("spotify_client_id", ""))
            self.inp_spotify_secret.setText(cfg.get("spotify_client_secret", ""))
            self.inp_spotify_uri.setText(cfg.get("spotify_redirect_uri", "http://127.0.0.1:8765/callback"))

            has_cust = bool(cfg.get("spotify_client_id"))
            self.chk_advanced_spotify.setChecked(has_cust)
            self._toggle_advanced_spotify(has_cust)

            self.lbl_spotify_status.setText(self.check_spotify_auth_status())

            ff = cfg.get("ilum_font_family", "Century Gothic")
            idx = self.cmb_font_family.findData(ff)
            if idx >= 0:
                self.cmb_font_family.setCurrentIndex(idx)

            self.sld_performance.setValue(int(cfg.get("performance_quality", 80)))
            self.chk_gpu.setChecked(cfg.get("gpu_acceleration", False))

            self._custom_bg_color = cfg.get("ilum_bg_color", "")
            self._custom_panel_color = cfg.get("ilum_panel_color", "")
            self._custom_text_color = cfg.get("ilum_text_color", "")
            self._custom_bg_image = cfg.get("ilum_bg_image", "")
            self._custom_sticker_path = cfg.get("ilum_sticker_path", "")

            bg_op = int(float(cfg.get("ilum_bg_opacity", 0.85)) * 100)
            self.sld_bg_opacity.setValue(bg_op)
            self.sld_sticker_w.setValue(int(cfg.get("ilum_sticker_w", 100)))
            self.sld_sticker_h.setValue(int(cfg.get("ilum_sticker_h", 100)))

            # Cargar visibilidad de widgets
            self.chk_widget_spotify.setChecked(cfg.get("show_widget_spotify", False))
            self.chk_widget_media.setChecked(cfg.get("show_widget_media", False))
            self.chk_widget_weather.setChecked(cfg.get("show_widget_weather", False))
            self.chk_widget_notifications.setChecked(cfg.get("show_widget_notifications", False))
            self.chk_widget_calendar.setChecked(cfg.get("show_widget_calendar", False))
            self.chk_widget_system.setChecked(cfg.get("show_widget_system", False))
            self.chk_widget_todo.setChecked(cfg.get("show_widget_todo", False))
            self.chk_widget_notes.setChecked(cfg.get("show_widget_notes", False))
            self.chk_widget_files.setChecked(cfg.get("show_widget_files", False))

            # Personalidades
            try:
                self.cmb_personality.blockSignals(True)
                self.cmb_personality.clear()
                from memory.config_manager import BASE_DIR
                pers_path = BASE_DIR / "config" / "personalities.json"
                if pers_path.exists():
                    pers_data = json.loads(pers_path.read_text(encoding="utf-8"))
                    self._personalities_dict = pers_data.get("personalities", {})
                    active_key = pers_data.get("active", "actual")
                    for k, v in self._personalities_dict.items():
                        self.cmb_personality.addItem(v["name"], k)
                    idx = self.cmb_personality.findData(active_key)
                    if idx >= 0:
                        self.cmb_personality.setCurrentIndex(idx)
                else:
                    self._personalities_dict = {}
                self.cmb_personality.blockSignals(False)
                curr_key = self.cmb_personality.currentData()
                if curr_key and hasattr(self, "_personalities_dict") and curr_key in self._personalities_dict:
                    self.txt_personality_prompt.setPlainText(self._personalities_dict[curr_key]["prompt"])
            except Exception:
                self.cmb_personality.blockSignals(False)

            self.check_ollama_status()

        except Exception as e:
            print(f"Error loading settings: {e}")

    def apply_changes(self):
        self._do_save(close_after_save=False)

    def save(self):
        self._do_save(close_after_save=True)

    def _do_save(self, close_after_save=True):
        try:
            from memory.config_manager import save_api_keys, load_api_keys
            theme_val = self.cmb_theme.currentData()
            custom_hex = self.custom_color_hex if theme_val == "custom" else ""
            cam_dev = self.cmb_camera.currentData() or 0

            cfg = load_api_keys()
            cfg.update({
                "ai_name": self.inp_ai_name.text().strip(),
                "ilum_app_icon": self.inp_app_icon.text().strip(),
                "gemini_api_key": self.inp_gemini.text().strip(),
                "openrouter_api_key": self.inp_openrouter.text().strip(),
                "openrouter_model": self.inp_openrouter_model.text().strip(),
                "ai_provider": self.cmb_ai_provider.currentData(),
                "fish_audio_enabled": self.chk_fish_audio.isChecked(),
                "fish_api_key": self.inp_fish_api_key.text().strip(),
                "fish_voice_id": self.inp_fish_voice_id.text().strip(),
                "local_tts_enabled": self.chk_local_tts.isChecked(),
                "ollama_url": self.inp_ollama_url.text().strip(),
                "ollama_model": self.cmb_ollama_model.currentText().strip(),
                "performance_quality": self.sld_performance.value(),
                "ilum_voice": self.cmb_voice.currentData(),
                "ilum_theme": theme_val,
                "ilum_custom_theme_color": custom_hex,
                "gpu_acceleration": self.chk_gpu.isChecked(),
                "mic_device": self.cmb_mic.currentData(),
                "mic_sensitivity": self.sld_mic_sens.value() / 10000.0,
                "speaker_device": self.cmb_speaker.currentData(),
                "camera_device": cam_dev,
                "camera_ip": self.inp_camera_ip.text().strip(),
                "timezone": self.cmb_timezone.currentData(),
                "user_name": self.inp_user_name.text().strip() or "Señor",
                "spotify_client_id": self.inp_spotify_id.text().strip(),
                "spotify_client_secret": self.inp_spotify_secret.text().strip(),
                "spotify_redirect_uri": self.inp_spotify_uri.text().strip(),
                "ilum_font_family": self.cmb_font_family.currentData(),
                "ilum_bg_color": self._custom_bg_color,
                "ilum_panel_color": self._custom_panel_color,
                "ilum_text_color": self._custom_text_color,
                "ilum_bg_image": self._custom_bg_image,
                "ilum_bg_opacity": self.sld_bg_opacity.value() / 100.0,
                "ilum_sticker_path": self._custom_sticker_path,
                "ilum_sticker_w": self.sld_sticker_w.value(),
                "ilum_sticker_h": self.sld_sticker_h.value(),
                "show_widget_spotify": self.chk_widget_spotify.isChecked(),
                "show_widget_media": self.chk_widget_media.isChecked(),
                "show_widget_weather": self.chk_widget_weather.isChecked(),
                "show_widget_notifications": self.chk_widget_notifications.isChecked(),
                "show_widget_calendar": self.chk_widget_calendar.isChecked(),
                "show_widget_system": self.chk_widget_system.isChecked(),
                "show_widget_todo": self.chk_widget_todo.isChecked(),
                "show_widget_notes": self.chk_widget_notes.isChecked(),
                "show_widget_files": self.chk_widget_files.isChecked(),
            })

            save_api_keys(cfg)
            self._save_personalities_file()
            apply_theme_tokens(theme_val, custom_hex)

            main_win = self.window()
            if main_win and hasattr(main_win, "update_theme_styles"):
                main_win.update_theme_styles()
                if hasattr(main_win, "orb") and main_win.orb:
                    main_win.orb.web_view.page().runJavaScript(
                        f"if(window.updatePerformance)window.updatePerformance({self.sld_performance.value()});")
                if hasattr(main_win, "_apply_widget_visibility"):
                    main_win._apply_widget_visibility()

            if close_after_save:
                QMessageBox.information(self, "OK", "Configuración guardada.")
                self.accept()
            else:
                IlumMessageBox(self, "OK", "Cambios aplicados.").exec()

        except Exception as e:
            IlumMessageBox(self, "Error", f"Error al guardar: {e}", is_error=True).exec()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_position = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.window().move(e.globalPosition().toPoint() - self.drag_position)

    def reject(self):
        self._cleanup()
        self.hide()
        if hasattr(self, "_on_close_callback") and self._on_close_callback:
            self._on_close_callback(False)

    def accept(self):
        self._cleanup()
        self.hide()
        if hasattr(self, "_on_close_callback") and self._on_close_callback:
            self._on_close_callback(True)

    def closeEvent(self, e):
        self._cleanup()
        self.hide()
        if e: e.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 28.0, 28.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _cleanup(self):
        for attr in ("check_worker", "pull_worker", "install_worker"):
            w = getattr(self, attr, None)
            if w:
                try:
                    if hasattr(w, "finished_signal"):
                        w.finished_signal.disconnect()
                    elif hasattr(w, "progress_signal"):
                        w.progress_signal.disconnect()
                except:
                    pass
                if w.isRunning():
                    w.quit()


# ═══════════════════════════════════════════════════════════════════════════
#  MainWindow
# ═══════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    _shutdown_sig = pyqtSignal()
    student_action_sig = pyqtSignal(str, dict)

    def __init__(self, ui, face_path):
        super().__init__()
        self.ui = ui
        self.ui._win = self
        self.camera_window = None
        self.student_action_sig.connect(self.handle_student_action, Qt.ConnectionType.QueuedConnection)

        self.resize(1150, 780) 
        self.setMinimumSize(850, 600)
        self.setWindowTitle("ILUM-AI-HUD")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)

        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            ci = cfg.get("ilum_app_icon", "")
            if ci and Path(ci).exists(): self.setWindowIcon(QIcon(ci))
            else:
                ip = get_bundled_path("assets", "ilum_icono.ico")
                if ip.exists(): self.setWindowIcon(QIcon(str(ip)))
        except Exception: pass

        self.lbl_bg_image = QLabel(self.central_widget)
        self.lbl_bg_image.lower()
        self.lbl_bg_image.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_bg_image.setStyleSheet("background:transparent;")
        self.lbl_bg_image.hide()

        self.lbl_sticker = QLabel(self.central_widget)
        self.lbl_sticker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_sticker.setStyleSheet("background:transparent;")
        self.lbl_sticker.hide()

        self.orb = CustomParticleOrb(self.ui, self.central_widget)
        self.clock_w = ClockWidget(self.central_widget)
        self.top_right_dock = TopRightDock(self.central_widget)
        self.top_right_dock.hamburger_clicked.connect(self._open_settings)
        self.sys_monitor = SystemMonitorWidget(self.central_widget)
        self.bottom_dock = BottomDock(self.central_widget)
        self.bottom_dock.btn_camera.clicked.connect(self._toggle_camera_gestures)
        self.bottom_dock.btn_suspend.clicked.connect(self._toggle_suspend)
        self.bottom_dock.btn_chat.clicked.connect(self._toggle_chat)
        self.bottom_left_dock = BottomLeftDock(self.central_widget)
        self.bottom_left_dock.btn_bell.clicked.connect(self._toggle_notification_panel)
        self.bottom_left_dock.btn_folder.clicked.connect(self._open_folder)
        self.bottom_left_dock.btn_calendar.clicked.connect(self._toggle_calendar)
        self.pro_badge = ProBadge(self.central_widget)
        self.pro_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # ── WIDGETS FLOTANTES ──────────────────────────────────────────────
        self.spotify_float = FloatingSpotifyWidget(self.central_widget)
        self.media_float = FloatingMediaWidget(self.central_widget)
        self.weather_widget = WeatherWidget(self.central_widget)
        self.notif_panel = NotificationCard(self.central_widget)
        self.notif_panel.btn_close_notif.clicked.connect(self._toggle_notification_panel)
        self.calendar_popup = HUDCalendarWidget(self.central_widget)

        # ── WIDGETS CLÁSICOS (ocultos por defecto) ─────────────────────────
        self.files_panel = FilesPanel(self.ui, self.central_widget)
        self.notes_w = NotesWidget(self.central_widget)
        self.todo_w = TodoWidget(self.central_widget)
        self.system_w = SystemWidget(self.central_widget)

        # Ocultar widgets clásicos inicialmente
        self.files_panel.hide()
        self.notes_w.hide()
        self.todo_w.hide()
        self.system_w.hide()

        self.chat_bar = PillChatBar(self.central_widget)
        self.chat_bar.submitted.connect(self._submit_chat_command)
        self.txt_console = QLabel(self.central_widget)
        self.txt_console.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self.txt_console.setWordWrap(True)
        self.txt_console.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.txt_console.setStyleSheet("color:rgba(220,220,230,0.80);font-size:14px;font-weight:600;background:transparent;border:none;")

        self._drag_pos = None
        self._force_close = False
        self.tray_icon = None
        self.ui.is_sleeping = False
        self._setup_tray_icon()
        self._shutdown_sig.connect(self._handle_shutdown)
        self.update_theme_styles()

        # Cargar posiciones guardadas de los widgets
        self._load_widget_positions()

        self.settings_overlay = DeviceSettingsDialog(self.central_widget)
        self.settings_overlay.hide()

        def on_close(accepted):
            self._active_settings_dialog = None
            if accepted:
                if self.ui.on_config_saved:
                    from memory.config_manager import load_api_keys
                    self.ui.on_config_saved(load_api_keys())
            self.settings_overlay.hide()
            if hasattr(self, "_hud_widgets_states") and self._hud_widgets_states:
                for w, was_visible in self._hud_widgets_states.items():
                    if w and was_visible:
                        w.show()
                self._hud_widgets_states = {}

        self.settings_overlay._on_close_callback = on_close

        # Media Monitor (YouTube)
        self.media_worker = MediaMonitorWorker(self)
        self.media_worker.media_updated.connect(self.media_float.update_info)
        self.media_worker.start()

        # Aplicar visibilidad inicial de widgets
        QTimer.singleShot(500, self._apply_widget_visibility)

        # Habilitar mouse tracking para el redimensionamiento del HUD
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)

    def _load_widget_positions(self):
        """Carga las posiciones guardadas de los widgets desde la configuración."""
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()

            # ── WeatherWidget ──
            wx = cfg.get("widget_pos_WeatherWidget_x")
            wy = cfg.get("widget_pos_WeatherWidget_y")
            if wx is not None and wy is not None:
                self.weather_widget.move(int(wx), int(wy))
            else:
                self.weather_widget.move(self.width() - 280, 120)

            # ── FloatingSpotifyWidget ──
            wx = cfg.get("widget_pos_FloatingSpotifyWidget_x")
            wy = cfg.get("widget_pos_FloatingSpotifyWidget_y")
            if wx is not None and wy is not None:
                self.spotify_float.move(int(wx), int(wy))
            else:
                self.spotify_float.move((self.width() - 280) // 2 + 80, self.height() // 2 - 120)
                self._spotify_positioned = True

            # FloatingMediaWidget
            wx = cfg.get("widget_pos_FloatingMediaWidget_x")
            wy = cfg.get("widget_pos_FloatingMediaWidget_y")
            if wx is not None and wy is not None:
                self.media_float.move(int(wx), int(wy))
            else:
                self.media_float.move((self.width() - 280) // 2 + 80, self.height() // 2)


            # ── Widgets clásicos (posiciones relativas al HUD) ──
            # Se cargan en la ventana de configuración

        except Exception as e:
            print(f"Error loading widget positions: {e}")

    def _apply_widget_visibility(self):
        """Muestra u oculta los widgets según configuración."""
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
        except Exception:
            cfg = {}

        # ── WIDGETS FLOTANTES ──
        # Spotify
        
        if cfg.get("show_widget_media", False):
            if not self.media_float.isVisible():
                self.animate_show_widget(self.media_float)
        else:
            self.media_float.hide()

        if cfg.get("show_widget_spotify", False):
            if not self.spotify_float.isVisible():
                self.animate_show_widget(self.spotify_float)
        else:
            self.spotify_float.hide()

        # Clima
        if cfg.get("show_widget_weather", False):
            if not self.weather_widget.isVisible():
                self.animate_show_widget(self.weather_widget)
        else:
            self.weather_widget.hide()

        # Notificaciones
        self.notif_panel.hide()

        # Calendario
        if cfg.get("show_widget_calendar", False):
            if not self.calendar_popup.isVisible():
                self.animate_show_widget(self.calendar_popup)
        else:
            self.calendar_popup.hide()

        # ── WIDGETS CLÁSICOS ──
        if cfg.get("show_widget_system", False):
            if not self.system_w.isVisible():
                self.animate_show_widget(self.system_w)
        else:
            self.system_w.hide()

        if cfg.get("show_widget_todo", False):
            if not self.todo_w.isVisible():
                self.animate_show_widget(self.todo_w)
        else:
            self.todo_w.hide()

        if cfg.get("show_widget_notes", False):
            if not self.notes_w.isVisible():
                self.animate_show_widget(self.notes_w)
        else:
            self.notes_w.hide()

        if cfg.get("show_widget_files", False):
            if not self.files_panel.isVisible():
                self.animate_show_widget(self.files_panel)
        else:
            self.files_panel.hide()

    def resizeEvent(self, event):
        if event is not None: super().resizeEvent(event)
        W = self.central_widget.width()
        H = self.central_widget.height()

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, W, H), 18.0, 18.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

        if hasattr(self, "lbl_bg_image") and self.lbl_bg_image.isVisible():
            self.lbl_bg_image.setGeometry(0, 0, W, H); self.lbl_bg_image.lower()

        if hasattr(self, "settings_overlay") and self.settings_overlay:
            self.settings_overlay.setGeometry(0, 0, W, H)

        self.orb.setGeometry(8, 8, W - 16, H - 16)
        self.clock_w.setGeometry(28, 28, 320, 70)
        self.top_right_dock.setGeometry(W - 120, 14, 88, 60)
        self.sys_monitor.setGeometry(W - 130, 80, 100, 110)
        self.bottom_left_dock.setGeometry(28, H - 62, 140, 46)
        np_h = self.notif_panel.sizeHint().height() if self.notif_panel.isVisible() else 0
        self.notif_panel.setGeometry(28, H - 72 - max(np_h, 150), 310, max(np_h, 150))
        self.calendar_popup.setGeometry(50, H - 310, 230, 190)
        dock_w = 140; dock_h = 46
        self.bottom_dock.setGeometry((W - dock_w) // 2, H - 62, dock_w, dock_h)
        chat_w = 300
        self.chat_bar.setFixedWidth(chat_w)
        self.chat_bar.setGeometry((W - chat_w) // 2, H - 114, chat_w, 44)
        self.pro_badge.setGeometry(W - 85, H - 30, 80, 22)
        self.txt_console.setGeometry(80, H - 168, W - 160, 50)

        # Posicionar widgets flotantes solo si no se han movido manualmente
        if not hasattr(self, "_spotify_positioned"):
            self.spotify_float.move((W - 280) // 2 + 80, H // 2 - 120)
            self._spotify_positioned = True
            
            # FloatingMediaWidget
            self.media_float.move((W - 280) // 2 + 80, H // 2)


        # Sticker
        if hasattr(self, "_sticker_path") and self._sticker_path and self.lbl_sticker.isVisible():
            sw = getattr(self, "_sticker_w", 100); sh = getattr(self, "_sticker_h", 100)
            sx = int((W - sw) * 0.5); sy = int((H - sh) * 0.5)
            self.lbl_sticker.setGeometry(sx, sy, sw, sh)

        self.lbl_bg_image.lower(); self.orb.lower()
        for w in (self.clock_w, self.top_right_dock, self.sys_monitor,
                  self.bottom_left_dock, self.notif_panel, self.calendar_popup,
                  self.bottom_dock, self.chat_bar, self.spotify_float,
                  self.txt_console, self.pro_badge, self.lbl_sticker,
                  self.weather_widget, self.system_w, self.todo_w,
                  self.notes_w, self.files_panel):
            w.raise_()

    def update_theme_styles(self):
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            apply_theme_tokens(cfg.get("ilum_theme", "gold"), cfg.get("ilum_custom_theme_color", ""))
            global FONT_FAMILY
            FONT_FAMILY = cfg.get("ilum_font_family", "Century Gothic")
            QApplication.instance().setFont(QFont(FONT_FAMILY))

            ai_name = cfg.get("ai_name", "").strip().upper() or "I.L.U.M"
            if "." not in ai_name and len(ai_name) > 1 and " " not in ai_name:
                ai_name = ".".join(list(ai_name)) + "."
            self.pro_badge.update_text(ai_name)

            bg_img = cfg.get("ilum_bg_image", "")
            if bg_img and Path(bg_img).exists():
                from PyQt6.QtGui import QPixmap, QMovie
                from PyQt6.QtWidgets import QGraphicsOpacityEffect
                
                # Check for GIF
                if str(bg_img).lower().endswith(".gif"):
                    movie = QMovie(bg_img)
                    self.lbl_bg_image.setMovie(movie)
                    self.lbl_bg_image.show()
                    movie.start()
                    # keep a reference to movie
                    self._current_bg_movie = movie
                else:
                    pix = QPixmap(bg_img)
                    if not pix.isNull():
                        self.lbl_bg_image.setPixmap(pix)
                        self.lbl_bg_image.show()
                        if hasattr(self, "_current_bg_movie"):
                            self._current_bg_movie = None
                
                oe = QGraphicsOpacityEffect(self); oe.setOpacity(float(cfg.get("ilum_bg_opacity", 0.85)))
                self.lbl_bg_image.setGraphicsEffect(oe)
            else:
                self.lbl_bg_image.clear(); self.lbl_bg_image.hide()
                if hasattr(self, "_current_bg_movie"):
                    self._current_bg_movie = None

            # Sticker
            sticker_path = cfg.get("ilum_sticker_path", "")
            self._sticker_path = sticker_path
            self._sticker_w = int(cfg.get("ilum_sticker_w", 100))
            self._sticker_h = int(cfg.get("ilum_sticker_h", 100))
            if sticker_path and Path(sticker_path).exists():
                from PyQt6.QtGui import QPixmap
                pix = QPixmap(sticker_path)
                if not pix.isNull():
                    pix = pix.scaled(self._sticker_w, self._sticker_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.lbl_sticker.setPixmap(pix); self.lbl_sticker.setFixedSize(self._sticker_w, self._sticker_h); self.lbl_sticker.show()
            else:
                self.lbl_sticker.clear(); self.lbl_sticker.hide()
        except Exception as e:
            print(f"[UI] update_theme_styles error: {e}")

        bg_c = QColor(C_BG); r, g, b = bg_c.red(), bg_c.green(), bg_c.blue()
        self.central_widget.setStyleSheet(f"""
            QWidget#centralWidget {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba({r},{g},{b},0.92), stop:1 rgba({max(0,r-12)},{max(0,g-12)},{max(0,b-12)},0.97));
                border: 1.5px solid rgba(255,255,255,0.06);
                border-radius: 18px;
            }}
        """)
        if hasattr(self, "clock_w"): self.clock_w.update_style()
        if hasattr(self, "orb"): self.orb.sync_theme()
        if hasattr(self, "bottom_dock"):
            self.bottom_dock.update_suspend_icon(getattr(self.ui, "is_sleeping", False))
        for btn in self.findChildren(HUDIconButton):
            try:
                btn.update_style()
            except Exception:
                pass

    def update_widgets_visibility(self): pass
    def update_macros_list_if_open(self): pass

    def _open_settings(self):
        self._hud_widgets_states = {}
        for w in [self.orb, self.clock_w, self.top_right_dock, self.sys_monitor,
                  self.bottom_left_dock, self.notif_panel, self.calendar_popup,
                  self.bottom_dock, self.chat_bar, self.spotify_float,
                  self.txt_console, self.pro_badge, self.lbl_sticker,
                  self.weather_widget, self.system_w, self.todo_w,
                  self.notes_w, self.files_panel]:
            if w is not None:
                self._hud_widgets_states[w] = w.isVisible()
                w.hide()

        W = self.central_widget.width()
        H = self.central_widget.height()
        self.settings_overlay.setGeometry(0, 0, W, H)
        self.settings_overlay.load_settings()
        self.settings_overlay.show()
        self.settings_overlay.raise_()
        self._active_settings_dialog = self.settings_overlay

    def _open_folder(self):
        try:
            ruta = os.path.join(os.path.expanduser("~"), "Downloads", "Ilum_Downloads")
            os.makedirs(ruta, exist_ok=True); os.startfile(ruta)
        except Exception: pass

    def animate_show_widget(self, widget):
        # Grab target position
        target_pos = widget.pos()
        target_x = target_pos.x()
        target_y = target_pos.y()
        start_y = target_y + 80  # Slide up from 80px below
        
        # Move widget to initial animation state
        widget.move(target_x, start_y)
        widget.show()
        widget.raise_()
        
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
        
        opacity_effect = QGraphicsOpacityEffect(widget)
        opacity_effect.setOpacity(0.0)
        widget.setGraphicsEffect(opacity_effect)
        
        # Position slide up animation
        pos_anim = QPropertyAnimation(widget, b"pos", self)
        pos_anim.setDuration(450)
        pos_anim.setStartValue(QPoint(target_x, start_y))
        pos_anim.setEndValue(QPoint(target_x, target_y))
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Opacity fade in animation
        op_anim = QPropertyAnimation(opacity_effect, b"opacity", self)
        op_anim.setDuration(350)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Keep animation references alive
        if not hasattr(self, "_widget_anims"):
            self._widget_anims = {}
        self._widget_anims[widget] = (pos_anim, op_anim, opacity_effect)
        
        # Cleanup effect on finish so mouse interaction is unaffected
        def _on_finish():
            try:
                widget.setGraphicsEffect(None)
                if widget in self._widget_anims:
                    del self._widget_anims[widget]
            except Exception:
                pass
        
        pos_anim.finished.connect(_on_finish)
        
        pos_anim.start()
        op_anim.start()

    def animate_hide_widget(self, widget):
        if not widget.isVisible():
            return
            
        target_pos = widget.pos()
        target_x = target_pos.x()
        target_y = target_pos.y()
        end_y = target_y + 80  # Slide down to 80px below
        
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
        
        opacity_effect = QGraphicsOpacityEffect(widget)
        opacity_effect.setOpacity(1.0)
        widget.setGraphicsEffect(opacity_effect)
        
        # Position slide down animation
        pos_anim = QPropertyAnimation(widget, b"pos", self)
        pos_anim.setDuration(400)
        pos_anim.setStartValue(QPoint(target_x, target_y))
        pos_anim.setEndValue(QPoint(target_x, end_y))
        pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        
        # Opacity fade out animation
        op_anim = QPropertyAnimation(opacity_effect, b"opacity", self)
        op_anim.setDuration(300)
        op_anim.setStartValue(1.0)
        op_anim.setEndValue(0.0)
        op_anim.setEasingCurve(QEasingCurve.Type.InQuad)
        
        # Keep animation references alive
        if not hasattr(self, "_widget_anims"):
            self._widget_anims = {}
        self._widget_anims[widget] = (pos_anim, op_anim, opacity_effect)
        
        # When position animation finishes, hide the widget and clean up
        def _on_finish():
            try:
                widget.hide()
                widget.move(target_x, target_y)  # Restore correct position
                widget.setGraphicsEffect(None)
                if widget in self._widget_anims:
                    del self._widget_anims[widget]
            except Exception:
                pass
        
        pos_anim.finished.connect(_on_finish)
        
        pos_anim.start()
        op_anim.start()

    def _toggle_chat(self):
        if self.chat_bar.isVisible():
            self.chat_bar.hide()
            self.bottom_dock.btn_chat.set_active(False, "#ffffff")
        else:
            W = self.central_widget.width(); H = self.central_widget.height()
            self.chat_bar.setGeometry((W - 300) // 2, H - 114, 300, 44)
            self.animate_show_widget(self.chat_bar)
            self.chat_bar.inp.setFocus()
            self.bottom_dock.btn_chat.set_active(True, "#ffffff")

    def _toggle_notification_panel(self):
        if self.notif_panel.isVisible():
            self.notif_panel.hide()
            self.bottom_left_dock.set_notification(False)
        else:
            self.resizeEvent(None)
            self.animate_show_widget(self.notif_panel)
            self.bottom_left_dock.set_notification(False)

    def _toggle_calendar(self):
        if self.calendar_popup.isVisible():
            self.calendar_popup.hide()
        else:
            self.resizeEvent(None)
            self.animate_show_widget(self.calendar_popup)

    def _toggle_mute(self):
        if self.ui.on_stop_command: self.ui.on_stop_command()
        if self.ui.on_text_command: self.ui.on_text_command("SYS_TOGGLE_SUSPEND")

    def _toggle_suspend(self):
        if self.ui.on_text_command: self.ui.on_text_command("SYS_TOGGLE_SUSPEND")

    def update_suspend_button(self, is_sleeping: bool):
        self.ui.is_sleeping = is_sleeping
        self.bottom_dock.update_suspend_icon(is_sleeping)
        self.bottom_dock.btn_suspend.set_active(is_sleeping, "#f59e0b")

    def _toggle_camera_gestures(self):
        if not hasattr(self, "_gesture_thread") or self._gesture_thread is None:
            try: import mediapipe
            except ImportError: IlumMessageBox(self, "Piloto Gestual", "MediaPipe no instalado.", is_error=True).exec(); return
            try:
                from actions.gesture_engine import GestureTrackingThread
                cam_idx = 0
                try:
                    from memory.config_manager import load_api_keys
                    cam_idx = int(load_api_keys().get("camera_device", 0))
                except Exception: pass
                self._gesture_thread = GestureTrackingThread(camera_index=cam_idx, theme_bgr=hex_to_bgr(C_PRI), text_bgr=hex_to_bgr(C_TEXT))
                self._gesture_thread.start()
            except Exception as e: IlumMessageBox(self, "Error", f"Error al iniciar cámara:\n{e}", is_error=True).exec(); return
        if self.camera_window is None:
            self.camera_window = CameraPreviewWindow(shared_thread=self._gesture_thread, parent=None)
            self.camera_window.attach_thread(self._gesture_thread)
            self.camera_window.show(); self.camera_window.move(50, 50)
        else:
            if self.camera_window.isVisible(): self.camera_window.hide()
            else: self.camera_window.show(); self.camera_window.raise_()

    def stop_gesture_thread(self):
        if hasattr(self, "_gesture_thread") and self._gesture_thread:
            self._gesture_thread.stop(); self._gesture_thread = None

    def _open_diagnostic_logs(self): LogsDialog(self).exec()

    def _submit_chat_command(self, text: str):
        if not text: return
        self.ui.write_log(f"Tú: {text}")
        self.txt_console.setText(text)
        if self.ui.on_text_command: self.ui.on_text_command(text)
        self.resizeEvent(None)

    def push_notification(self, title: str, body: str, accent: str = "#a855f7",
                          thumbnail_path=None, action_label=None, action_callback=None):
        self.notif_panel.push_notification(title, body, accent, thumbnail_path, action_label, action_callback)
        self.bottom_left_dock.set_notification(True)
        self.resizeEvent(None)

    def show_spotify(self):
        if not hasattr(self, "_spotify_positioned"):
            W = self.central_widget.width(); H = self.central_widget.height()
            self.spotify_float.move((W - 280) // 2 + 80, H // 2 - 120)
            self._spotify_positioned = True
            
            # FloatingMediaWidget
            self.media_float.move((W - 280) // 2 + 80, H // 2)

        if self.spotify_float.isVisible(): self.animate_hide_widget(self.spotify_float)
        else: self.animate_show_widget(self.spotify_float)

    def _setup_tray_icon(self):
        from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
        self.tray_icon = QSystemTrayIcon(self)
        ip = get_bundled_path("assets", "ilum_icono.ico")
        if ip.exists(): self.tray_icon.setIcon(QIcon(str(ip)))
        else:
            from PyQt6.QtWidgets import QStyle
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        menu = QMenu(self)
        menu.addAction("Mostrar").triggered.connect(self.show_and_activate)
        menu.addAction("Mute/Listen").triggered.connect(self._toggle_mute)
        menu.addSeparator()
        menu.addAction("Salir").triggered.connect(self._exit_application)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def show_and_activate(self): self.showNormal(); self.activateWindow(); self.raise_()

    def _exit_application(self):
        self._force_close = True; self.close()
        try: self.stop_gesture_thread()
        except Exception: pass
        try: QApplication.quit()
        except Exception: pass
        os._exit(0)

    def _handle_shutdown(self): self._exit_application()

    def _on_tray_activated(self, reason):
        from PyQt6.QtWidgets import QSystemTrayIcon
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            if self.isVisible(): self.hide()
            else: self.show_and_activate()

    def closeEvent(self, event):
        if getattr(self, "_force_close", False):
            self.stop_gesture_thread(); event.accept()
        else:
            event.ignore(); self.hide()
            if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
                from PyQt6.QtWidgets import QSystemTrayIcon
                self.tray_icon.showMessage("ILUM AI", "Sigo activo en segundo plano.",
                    QSystemTrayIcon.MessageIcon.Information, 3000)

    def _get_resize_edge(self, pos):
        margin = 8
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        
        edge = []
        if y < margin:
            edge.append('top')
        elif y > h - margin:
            edge.append('bottom')
            
        if x < margin:
            edge.append('left')
        elif x > w - margin:
            edge.append('right')
            
        return '_'.join(edge) if edge else None

    def _update_cursor(self, edge):
        if not edge:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif edge in ('top', 'bottom'):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edge in ('left', 'right'):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ('top_left', 'bottom_right'):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ('top_right', 'bottom_left'):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._resize_edge = self._get_resize_edge(pos)
            if self._resize_edge:
                self._resize_start_geometry = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.NoButton:
            pos = event.position().toPoint()
            edge = self._get_resize_edge(pos)
            self._update_cursor(edge)
            return

        if hasattr(self, "_resize_edge") and self._resize_edge:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geom = self._resize_start_geometry
            x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
            min_w, min_h = self.minimumSize().width(), self.minimumSize().height()
            
            if 'left' in self._resize_edge:
                new_w = w - delta.x()
                if new_w >= min_w:
                    x = geom.x() + delta.x()
                    w = new_w
            elif 'right' in self._resize_edge:
                new_w = w + delta.x()
                if new_w >= min_w:
                    w = new_w
                    
            if 'top' in self._resize_edge:
                new_h = h - delta.y()
                if new_h >= min_h:
                    y = geom.y() + delta.y()
                    h = new_h
            elif 'bottom' in self._resize_edge:
                new_h = h + delta.y()
                if new_h >= min_h:
                    h = new_h
                    
            self.setGeometry(x, y, w, h)
        elif hasattr(self, "_drag_pos") and self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            self._resize_edge = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            try:
                from memory.config_manager import load_api_keys, save_api_keys
                cfg = load_api_keys(); pos = self.frameGeometry().topLeft()
                cfg["window_x"] = pos.x(); cfg["window_y"] = pos.y(); save_api_keys(cfg)
            except Exception: pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.ui.on_stop_command: self.ui.on_stop_command()
        else: super().keyPressEvent(event)

    @pyqtSlot()
    def open_student_mode(self): self.ui.open_student_mode()

    @pyqtSlot(str, dict)
    def handle_student_action(self, action_name, data): self.ui.open_student_mode()

    @pyqtSlot()
    def toggle_hud_edit_mode(self): pass


# ═══════════════════════════════════════════════════════════════════════════
#  MockRoot + IlumUI
# ═══════════════════════════════════════════════════════════════════════════

class MockRoot:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
    def mainloop(self): sys.exit(self.qapp.exec())
    def after(self, ms: int, func): QTimer.singleShot(ms, func)


class IlumUI:
    def __init__(self, face_path=""):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.root = MockRoot(self.app)
        self.muted = False
        self.current_file = ""
        self.on_text_command = None
        self.on_stop_command = None
        self.on_config_saved = None
        self.ilum_response_buffer = ""
        self.last_user_message = ""
        self._win = MainWindow(self, face_path)
        self._win.show(); self._win.raise_(); self._win.activateWindow()
        try:
            from ui_glass_overlay import apply_liquid_glass
            apply_liquid_glass(self._win)
        except Exception: pass
        QTimer.singleShot(2000, self.ensure_startup_shortcut)

    def wait_for_api_key(self): pass

    def update_suspend_button(self, is_sleeping: bool):
        QTimer.singleShot(0, lambda: self._win.update_suspend_button(is_sleeping))

    def write_log(self, text: str):
        print(text)
        def _update():
            if text.startswith("SYS:") or text.startswith("ERR:") or text.startswith("⚡"):
                self.ilum_response_buffer = ""; self._win.txt_console.setText(text)
            elif text.startswith("Tú:"):
                self.last_user_message = text
                disp = self.last_user_message
                if self.ilum_response_buffer: disp += f"\nILUM: {self.ilum_response_buffer}"
                self._win.txt_console.setText(disp)
            elif text.startswith("ILUM:"):
                clean = text.replace("ILUM:", "").strip()
                if clean:
                    self.ilum_response_buffer = clean
                    disp = f"ILUM: {self.ilum_response_buffer}"
                    if self.last_user_message: disp = f"{self.last_user_message}\n{disp}"
                    self._win.txt_console.setText(disp)
            else:
                self._win.txt_console.setText(text)
        QTimer.singleShot(0, _update)

    def set_state(self, state: str):
        if state == "MUTED": self.muted = True
        elif state == "LISTENING": self.muted = False
        def _do():
            s = "MUTED" if self.muted else state
            self._win.orb.set_state(s)
        QTimer.singleShot(0, _do)

    def set_audio_level(self, level: float): self._win.orb.set_audio(level)

    def clear_ilum_response(self):
        def _do():
            self.ilum_response_buffer = ""
            self._win.txt_console.setText(self.last_user_message if self.last_user_message else "")
        QTimer.singleShot(0, _do)

    def stream_ilum_chunk(self, chunk: str):
        def _do():
            text = chunk.replace("ILUM:", "").strip()
            if text:
                if self.ilum_response_buffer: self.ilum_response_buffer += " " + text
                else: self.ilum_response_buffer = text
                disp = f"ILUM: {self.ilum_response_buffer}"
                if self.last_user_message: disp = f"{self.last_user_message}\n{disp}"
                self._win.txt_console.setText(disp)
        QTimer.singleShot(0, _do)

    def push_notification(self, title: str, body: str, accent: str = "#a855f7",
                          thumbnail_path=None, action_label=None, action_callback=None):
        QTimer.singleShot(0, lambda: self._win.push_notification(title, body, accent, thumbnail_path, action_label, action_callback))

    def show_spotify(self): QTimer.singleShot(0, self._win.show_spotify)

    def open_student_mode(self):
        if not hasattr(self, "student_window") or self.student_window is None:
            try:
                from ui import StudentModeWindow
                self.student_window = StudentModeWindow(self._win)
            except Exception: self.student_window = None; return
        if self.student_window and self.student_window.isHidden(): self.student_window.show()
        if self.student_window: self.student_window.raise_(); self.student_window.activateWindow()

    def ensure_startup_shortcut(self):
        try:
            import os, subprocess
            appdata = os.getenv('APPDATA')
            if not appdata: return
            startup_dir = os.path.join(appdata, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            shortcut_path = os.path.join(startup_dir, 'ILUM AI.lnk')
            current_dir = os.path.abspath(os.path.dirname(__file__))
            target_vbs = os.path.join(current_dir, "Iniciar ILUM Beta.vbs")
            icon_path = os.path.join(current_dir, "assets", "ilum_icono.ico")
            if not os.path.exists(target_vbs): return
            ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_path}');"
                  f"$s.TargetPath='{target_vbs}';$s.WorkingDirectory='{current_dir}';"
                  f"$s.IconLocation='{icon_path}';$s.Save()")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e: print(f"[STARTUP] {e}")
    
    



# ═══════════════════════════════════════════════════════════════════════════
#  Student Mode Workers + Window
# ═══════════════════════════════════════════════════════════════════════════

class DocumentRenderWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(list, str)
    def __init__(self, file_path): super().__init__(); self.file_path = file_path
    def run(self):
        import os, fitz
        from PyQt6.QtGui import QImage
        temp_pdf = None
        try:
            self.status.emit("Preparando…"); self.progress.emit(10)
            ext = os.path.splitext(self.file_path)[1].lower(); pdf = self.file_path
            if ext == ".docx":
                self.status.emit("Convirtiendo Word a PDF…"); self.progress.emit(25)
                import comtypes.client; comtypes.CoInitialize()
                try:
                    w = comtypes.client.CreateObject("Word.Application"); w.Visible = False
                    doc = w.Documents.Open(os.path.abspath(self.file_path))
                    temp_pdf = os.path.join(os.path.dirname(self.file_path), f"_tmp_{os.path.basename(self.file_path)}.pdf")
                    doc.SaveAs(os.path.abspath(temp_pdf), FileFormat=17); doc.Close(); w.Quit(); pdf = temp_pdf
                except Exception as we: self.finished.emit([], f"Error Word→PDF: {we}"); return
                finally: comtypes.CoUninitialize()
            self.status.emit("Renderizando páginas…"); self.progress.emit(50)
            d = fitz.open(pdf); pages = []; tot = len(d)
            for i in range(tot):
                self.status.emit(f"Página {i+1}/{tot}…"); p = d.load_page(i); pix = p.get_pixmap(dpi=120)
                qi = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy(); pages.append(qi)
                self.progress.emit(50 + int((i + 1) / tot * 40))
            d.close()
            if temp_pdf and os.path.exists(temp_pdf):
                try: os.remove(temp_pdf)
                except: pass
            self.progress.emit(100); self.finished.emit(pages, "")
        except Exception as e: self.finished.emit([], f"Error: {e}")


class PdfToWordWorker(QThread):
    progress = pyqtSignal(int); status = pyqtSignal(str); finished = pyqtSignal(str)
    def __init__(self, pp, dp): super().__init__(); self.pdf_path = pp; self.docx_path = dp
    def run(self):
        try:
            self.status.emit("Iniciando…"); self.progress.emit(20)
            from pdf2docx import Converter; cv = Converter(self.pdf_path)
            self.status.emit("Reconstruyendo…"); self.progress.emit(50)
            cv.convert(self.docx_path); cv.close(); self.progress.emit(100)
            self.finished.emit(f"Éxito: guardado en '{self.docx_path}'")
        except Exception as e:
            try:
                from docx import Document
                from actions.student_mode import extract_text
                txt = extract_text(self.pdf_path)
                doc = Document(); doc.add_paragraph(txt); doc.save(self.docx_path)
                self.progress.emit(100); self.finished.emit(f"Guardado (fallback) en '{self.docx_path}'")
            except Exception as e2: self.finished.emit(f"Error: {e}\nFallback: {e2}")


class QualityReportWorker(QThread):
    status = pyqtSignal(str); finished = pyqtSignal(str)
    def __init__(self, text, filename): super().__init__(); self.text = text; self.filename = filename
    def run(self):
        try:
            self.status.emit("Llamando a Artemisa…")
            from memory.config_manager import load_api_keys; cfg = load_api_keys()
            from google import genai; client = genai.Client(api_key=cfg.get("gemini_api_key", ""))
            prompt = (f"Actúa como revisor académico senior. Analiza el texto del documento '{self.filename}' y genera un REPORTE DE CALIDAD en HTML estilizado con fondo oscuro. Sin bloques markdown.\n\nTEXTO:\n\n{self.text[:9000]}")
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            html = resp.text.strip()
            if html.startswith("```"):
                lines = html.split("\n"); lines = lines[1:] if lines[0].startswith("```") else lines
                if lines[-1].startswith("```"): lines = lines[:-1]
                html = "\n".join(lines).strip()
            self.finished.emit(html)
        except Exception as e: self.finished.emit(f"<div style='color:#ff3b30;'>Error: {e}</div>")


class ApaVerifyWorker(QThread):
    status = pyqtSignal(str); progress = pyqtSignal(int); finished = pyqtSignal(str)
    def __init__(self, text, file_path): super().__init__(); self.text = text; self.file_path = file_path
    def run(self):
        try:
            self.status.emit("Iniciando…"); self.progress.emit(10)
            from memory.config_manager import load_api_keys; cfg = load_api_keys()
            from google import genai; client = genai.Client(api_key=cfg.get("gemini_api_key", ""))
            pil_images = []
            if self.file_path:
                try:
                    import fitz; from PIL import Image
                    pdf = self.file_path; tmp = None
                    ext = os.path.splitext(self.file_path)[1].lower()
                    if ext == ".docx":
                        import comtypes.client; comtypes.CoInitialize()
                        try:
                            w = comtypes.client.CreateObject("Word.Application"); w.Visible = False
                            doc = w.Documents.Open(os.path.abspath(self.file_path))
                            tmp = os.path.join(os.path.dirname(self.file_path), "_tmp_apa_.pdf")
                            doc.SaveAs(os.path.abspath(tmp), FileFormat=17); doc.Close(); w.Quit(); pdf = tmp
                        finally: comtypes.CoUninitialize()
                    d = fitz.open(pdf)
                    for i in range(min(2, len(d))):
                        p = d.load_page(i); pix = p.get_pixmap(dpi=120)
                        pil_images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
                    d.close()
                    if tmp and os.path.exists(tmp): os.remove(tmp)
                except Exception: pass
            self.progress.emit(65); self.status.emit("Llamando a Artemisa…")
            prompt = ("Actúa como experto en normas APA 7ma edición. Analiza el texto y las imágenes adjuntas. Devuelve un reporte estructurado.\n\nTEXTO:\n\n" + self.text)
            contents = [prompt] + pil_images
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=contents)
            self.progress.emit(100); self.finished.emit(resp.text.strip())
        except Exception as e: self.finished.emit(f"Error: {e}")


class StudentModeWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ILUM — Herramientas Académicas")
        self.resize(850, 600); self.setMinimumSize(800, 550)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.loaded_quality_text = ""; self.loaded_quality_file = ""; self.loaded_apa_file = ""
        self.drag_pos = None; self.init_ui()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.drag_pos = e.globalPosition().toPoint()
    def mouseMoveEvent(self, e):
        if self.drag_pos: self.move(self.pos() + e.globalPosition().toPoint() - self.drag_pos); self.drag_pos = e.globalPosition().toPoint()
    def mouseReleaseEvent(self, e): self.drag_pos = None

    def init_ui(self):
        ml = QVBoxLayout(self); ml.setContentsMargins(12, 12, 12, 12)
        bg = QFrame(self); bg.setObjectName("StuBg")
        try:
            from memory.config_manager import load_api_keys
            is_glass = load_api_keys().get("student_glass_mode", True)
        except: is_glass = True
        bg.setStyleSheet(f"QFrame#StuBg{{{'background:rgba(15,23,42,0.85);' if is_glass else 'background:rgb(15,23,42);'}border:1px solid rgba(255,255,255,0.10);border-radius:12px;}}")
        bl = QVBoxLayout(bg); bl.setContentsMargins(15, 15, 15, 15); ml.addWidget(bg)
        hdr = QHBoxLayout()
        ic = QLabel()
        if HAS_QTA: ic.setPixmap(qta.icon("fa5s.graduation-cap", color=C_PRI).pixmap(28, 28))
        hdr.addWidget(ic)
        tl = QLabel(" MODO ESTUDIANTE"); tl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        tl.setStyleSheet(f"color:{C_PRI};letter-spacing:1px;"); hdr.addWidget(tl); hdr.addStretch()
        for txt, fn in [("-", self.showMinimized), ("X", self.close)]:
            b = QPushButton(txt); b.setFixedSize(28, 28)
            b.setStyleSheet("QPushButton{border:none;}QPushButton:hover{background:rgba(255,255,255,0.12);border-radius:14px;}")
            b.clicked.connect(fn); hdr.addWidget(b)
        bl.addLayout(hdr)
        self.tabs = QTabWidget(); bl.addWidget(self.tabs)
        # Tab Ghost
        tg = QWidget(); gl = QVBoxLayout(tg); gl.setContentsMargins(12, 12, 12, 12)
        gl.addWidget(QLabel("Texto a parafrasear:"))
        sp = QHBoxLayout(); self.ghost_input = QTextEdit(); self.ghost_input.setPlaceholderText("Texto original…")
        self.ghost_output = QTextEdit(); self.ghost_output.setPlaceholderText("Resultado…"); self.ghost_output.setReadOnly(True)
        sp.addWidget(self.ghost_input); sp.addWidget(self.ghost_output); gl.addLayout(sp)
        self.btn_ghost_run = QPushButton(" Parafrasear"); self.btn_ghost_run.clicked.connect(self.trigger_paraphrase_manually); gl.addWidget(self.btn_ghost_run)
        self.tabs.addTab(tg, qta.icon("fa5s.ghost", color=C_PRI) if HAS_QTA else QIcon(), "Parafraseo")
        # Tab PDF→Word
        tp = QWidget(); pl = QVBoxLayout(tp); pl.setContentsMargins(20, 20, 20, 20); pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_file_label = QLabel("Ningún archivo"); self.pdf_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter); pl.addWidget(self.pdf_file_label)
        self.btn_pdf_convert = QPushButton(" Seleccionar PDF y Convertir"); self.btn_pdf_convert.setMinimumHeight(42); self.btn_pdf_convert.clicked.connect(self.select_pdf_manually); pl.addWidget(self.btn_pdf_convert)
        self.pdf_progress = QProgressBar(); self.pdf_progress.setRange(0, 100); self.pdf_progress.setFixedHeight(10)
        self.pdf_progress.setStyleSheet(f"QProgressBar{{background:rgba(255,255,255,0.10);border:none;border-radius:5px;}}QProgressBar::chunk{{background:{C_PRI};border-radius:5px;}}")
        pl.addWidget(self.pdf_progress)
        self.pdf_status_label = QLabel("Esperando…"); self.pdf_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter); pl.addWidget(self.pdf_status_label)
        self.tabs.addTab(tp, qta.icon("fa5s.file-word", color=C_PRI) if HAS_QTA else QIcon(), "PDF→Word")
        # Tab APA
        ta = QWidget(); al = QVBoxLayout(ta); al.setContentsMargins(12, 12, 12, 12)
        ah = QHBoxLayout(); ah.addWidget(QLabel("Verificador APA 7 Visual")); ah.addStretch()
        self.btn_apa_load = QPushButton(" Cargar Doc"); self.btn_apa_load.clicked.connect(self.load_apa_file_manually); ah.addWidget(self.btn_apa_load)
        al.addLayout(ah)
        self.apa_viewer = QScrollArea(); self.apa_viewer.setWidgetResizable(True)
        avc = QWidget(); avc.setStyleSheet("background:rgba(20,20,20,0.95);")
        self.apa_viewer_layout = QVBoxLayout(avc); self.apa_viewer_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.apa_placeholder = QLabel("Carga un PDF/DOCX para ver la vista previa"); self.apa_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.apa_viewer_layout.addWidget(self.apa_placeholder); self.apa_viewer.setWidget(avc)
        asplit = QHBoxLayout(); asplit.addWidget(self.apa_viewer)
        self.apa_output = QTextEdit(); self.apa_output.setReadOnly(True); asplit.addWidget(self.apa_output); al.addLayout(asplit)
        abl = QHBoxLayout()
        self.btn_apa_run = QPushButton(" Verificar APA 7"); self.btn_apa_run.clicked.connect(self.trigger_apa_manually); abl.addWidget(self.btn_apa_run)
        self.btn_apa_download = QPushButton(" Descargar"); self.btn_apa_download.clicked.connect(self.download_apa_report); self.btn_apa_download.setEnabled(False); abl.addWidget(self.btn_apa_download)
        al.addLayout(abl)
        self.tabs.addTab(ta, qta.icon("fa5s.book", color=C_PRI) if HAS_QTA else QIcon(), "APA 7")
        # Tab Calidad
        tq = QWidget(); ql = QVBoxLayout(tq); ql.setContentsMargins(12, 12, 12, 12)
        qh = QHBoxLayout(); qh.addWidget(QLabel("Evaluador de Rigor Académico")); qh.addStretch()
        self.btn_q_load = QPushButton(" Cargar Doc"); self.btn_q_load.clicked.connect(self.load_quality_file_manually); qh.addWidget(self.btn_q_load)
        ql.addLayout(qh)
        self.quality_file_label = QLabel("Ningún archivo"); ql.addWidget(self.quality_file_label)
        self.quality_output = QTextBrowser(); self.quality_output.setStyleSheet("background:rgba(20,20,20,0.95);border:1px solid rgba(255,255,255,0.10);border-radius:8px;"); ql.addWidget(self.quality_output)
        qbl = QHBoxLayout()
        self.btn_q_run = QPushButton(" Generar Reporte"); self.btn_q_run.clicked.connect(self.run_quality_report_manually); self.btn_q_run.setEnabled(False); qbl.addWidget(self.btn_q_run)
        self.btn_q_download = QPushButton(" Descargar HTML"); self.btn_q_download.clicked.connect(self.download_quality_report); self.btn_q_download.setEnabled(False); qbl.addWidget(self.btn_q_download)
        ql.addLayout(qbl)
        self.tabs.addTab(tq, qta.icon("fa5s.award", color=C_PRI) if HAS_QTA else QIcon(), "Calidad")
        # Status bar
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); bl.addWidget(sep)
        sbr = QHBoxLayout(); sbr.setContentsMargins(8, 2, 8, 2)
        self.global_status_label = QLabel("Estado: Listo"); self.global_status_label.setStyleSheet(f"color:{C_TEXT};font-size:11px;"); sbr.addWidget(self.global_status_label); sbr.addStretch()
        self.global_progress_bar = QProgressBar(); self.global_progress_bar.setRange(0, 100); self.global_progress_bar.setFixedSize(180, 10)
        self.global_progress_bar.setStyleSheet(f"QProgressBar{{background:rgba(0,0,0,0.4);border:1px solid {C_BORDER};border-radius:4px;}}QProgressBar::chunk{{background:{C_PRI};border-radius:4px;}}")
        sbr.addWidget(self.global_progress_bar); bl.addLayout(sbr)
        self.update_style()

    def update_style(self):
        self.setStyleSheet(f"""
        QLabel{{color:{C_TEXT};font-family:'Segoe UI';}}
        QPushButton{{background:{C_PRI_DIM};color:{C_TEXT};border:1px solid {C_BORDER};border-radius:8px;padding:8px;font-weight:bold;}}
        QPushButton:hover{{background:{C_PRI};color:#0f0a02;}}
        QPushButton:disabled{{background:rgba(128,128,128,0.1);color:rgba(255,255,255,0.3);border:1px solid rgba(128,128,128,0.2);}}
        QTextEdit,QTextBrowser{{background:rgba(0,0,0,0.6);color:#fff;border:1px solid {C_BORDER};border-radius:8px;font-family:'Consolas';font-size:13px;}}
        QTabWidget::pane{{border:1px solid {C_BORDER};border-radius:10px;background:rgba(22,16,5,0.4);}}
        QTabBar::tab{{background:rgba(35,28,10,0.6);color:{C_TEXT};padding:10px 16px;border-radius:6px;border:1px solid {C_BORDER};margin-right:4px;}}
        QTabBar::tab:selected{{background:{C_PRI_DIM};border-bottom:2px solid {C_PRI};font-weight:bold;}}
        QScrollArea{{background:rgba(0,0,0,0.5);border:1px solid {C_BORDER};border-radius:8px;}}
        """)
        apply_glass_shadow(self)

    def select_pdf_manually(self):
        from PyQt6.QtWidgets import QFileDialog
        pp, _ = QFileDialog.getOpenFileName(self, "Seleccionar PDF", "", "PDF (*.pdf)")
        if not pp: return
        dp = str(Path(pp).with_suffix(".docx"))
        self.pdf_file_label.setText(f"Archivo: {pp}"); self.btn_pdf_convert.setEnabled(False); self.pdf_progress.setValue(0)
        self.pdf_status_label.setText("Iniciando…")
        self.pdf_worker = PdfToWordWorker(pp, dp)
        self.pdf_worker.progress.connect(self.pdf_progress.setValue); self.pdf_worker.status.connect(self.pdf_status_label.setText)
        self.pdf_worker.finished.connect(self.pdf_conversion_finished); self.pdf_worker.start()

    def pdf_conversion_finished(self, msg):
        self.btn_pdf_convert.setEnabled(True); self.pdf_status_label.setText("Completado.")
        if "Error" in msg: QMessageBox.critical(self, "Error", msg)
        else: QMessageBox.information(self, "Éxito", msg)

    def trigger_paraphrase_manually(self):
        text = self.ghost_input.toPlainText().strip()
        if not text: return
        self.ghost_output.setPlainText("Procesando…"); self.btn_ghost_run.setEnabled(False)
        def run_api():
            try:
                from memory.config_manager import load_api_keys; cfg = load_api_keys()
                from google import genai; client = genai.Client(api_key=cfg.get("gemini_api_key", ""))
                prompt = "Actúa como reescritor académico sofisticado. Reescribe el texto evadiendo detectores de IA.\n\n"
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt + text)
                return resp.text.strip()
            except Exception as e: return f"Error: {e}"
        class W(QThread):
            res = pyqtSignal(str)
            def run(self): self.res.emit(run_api())
        self.para_worker = W(); self.para_worker.res.connect(self.paraphrase_finished); self.para_worker.start()

    def paraphrase_finished(self, result):
        self.ghost_output.setPlainText(result); self.btn_ghost_run.setEnabled(True)

    def load_apa_file_manually(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(self, "Cargar Doc", "", "Documentos (*.pdf *.docx)")
        if not fp: return
        self.loaded_apa_file = fp; self.global_status_label.setText("Cargando…")
        self.btn_apa_load.setEnabled(False); self.btn_apa_run.setEnabled(False)
        self.render_worker = DocumentRenderWorker(fp)
        self.render_worker.status.connect(self.global_status_label.setText)
        self.render_worker.progress.connect(self.global_progress_bar.setValue)
        self.render_worker.finished.connect(self.apa_file_rendered); self.render_worker.start()

    def apa_file_rendered(self, pages, error):
        self.btn_apa_load.setEnabled(True); self.btn_apa_run.setEnabled(True)
        if error: QMessageBox.critical(self, "Error", error); return
        while self.apa_viewer_layout.count():
            it = self.apa_viewer_layout.takeAt(0); w = it.widget()
            if w: w.deleteLater()
        from PyQt6.QtGui import QPixmap
        for qi in pages:
            l = QLabel(); l.setPixmap(QPixmap.fromImage(qi)); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setStyleSheet("border:1px solid rgba(245,158,11,0.45);border-radius:4px;background:white;margin:12px;padding:2px;")
            self.apa_viewer_layout.addWidget(l)
        self.global_status_label.setText("Documento cargado."); self.global_progress_bar.setValue(100)

    def trigger_apa_manually(self):
        if not self.loaded_apa_file: QMessageBox.warning(self, "Aviso", "Carga primero un documento."); return
        self.apa_output.setPlainText("Analizando…"); self.btn_apa_run.setEnabled(False)
        self.global_status_label.setText("Verificando APA 7…"); self.global_progress_bar.setValue(15)
        self.apa_verify_worker = ApaVerifyWorker("", self.loaded_apa_file)
        self.apa_verify_worker.status.connect(self.global_status_label.setText)
        self.apa_verify_worker.progress.connect(self.global_progress_bar.setValue)
        self.apa_verify_worker.finished.connect(self.apa_verification_finished); self.apa_verify_worker.start()

    def apa_verification_finished(self, report):
        self.apa_output.setPlainText(report); self.btn_apa_run.setEnabled(True)
        if report.startswith("Error"): self.btn_apa_download.setEnabled(False)
        else: self.global_status_label.setText("Reporte APA generado."); self.global_progress_bar.setValue(100); self.btn_apa_download.setEnabled(True)

    def load_quality_file_manually(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(self, "Cargar Doc", "", "Documentos (*.txt *.pdf *.docx)")
        if not fp: return
        from actions.student_mode import extract_text
        text = extract_text(fp)
        if not text or text.startswith("[Error"): QMessageBox.critical(self, "Error", "No se pudo extraer texto."); return
        self.loaded_quality_text = text; self.loaded_quality_file = fp
        self.quality_file_label.setText(f"Archivo: {fp}"); self.btn_q_run.setEnabled(True)

    def run_quality_report_manually(self):
        if not self.loaded_quality_text: return
        self.btn_q_run.setEnabled(False); self.global_status_label.setText("Generando reporte…"); self.global_progress_bar.setValue(25)
        self.quality_worker = QualityReportWorker(self.loaded_quality_text, Path(self.loaded_quality_file).name)
        self.quality_worker.status.connect(lambda s: self.global_status_label.setText(f"Calidad: {s}"))
        self.quality_worker.finished.connect(self.quality_report_finished); self.quality_worker.start()

    def quality_report_finished(self, html):
        self.btn_q_run.setEnabled(True); self.quality_output.setHtml(html)
        if "Error" in html: self.global_progress_bar.setValue(0); self.btn_q_download.setEnabled(False)
        else: self.global_status_label.setText("Reporte generado."); self.global_progress_bar.setValue(100); self.btn_q_download.setEnabled(True)

    def download_apa_report(self):
        try:
            from memory.config_manager import BASE_DIR; import time, os
            d = os.path.join(BASE_DIR, "Descargas_Ilum"); os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, f"APA_{int(time.time())}.txt")
            with open(fp, "w", encoding="utf-8") as f: f.write(self.apa_output.toPlainText())
            QMessageBox.information(self, "OK", f"Guardado en:\n{d}"); os.startfile(d)
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def download_quality_report(self):
        try:
            from memory.config_manager import BASE_DIR; import time, os
            d = os.path.join(BASE_DIR, "Descargas_Ilum"); os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, f"Calidad_{int(time.time())}.html")
            with open(fp, "w", encoding="utf-8") as f: f.write(self.quality_output.toHtml())
            QMessageBox.information(self, "OK", f"Guardado en:\n{d}"); os.startfile(d)
        except Exception as e: QMessageBox.critical(self, "Error", str(e))