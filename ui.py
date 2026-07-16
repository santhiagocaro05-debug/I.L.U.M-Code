"""
ui.py — Redesigned Clean NEXUS HUD + Full Settings Suite.

Layout:
- Top-left: Large floating clock + date
- Top-right: Two colored dots + hamburger menu (≡) → opens settings
- Right side: RAM % + CPU % + TEM °C readouts
- Center:  logo + waveform (via WebGL orb)
- Bottom-left: Bell / Folder / Calendar icon buttons + notification liquid-glass panel
- Bottom-center: Camera | Moon-Sun (suspend) | Chat-bubble icons
- Bottom-right: "NEXUS Pro" badge
- Floating Spotify widget (opens on click / command)
- Auto-sizing pill chat bar (hidden by default, opens on chat icon press)

Settings Dialog includes ALL tabs:
  CEREBRO, PERSONALIDAD, IA LOCAL, DISPOSITIVOS, APARIENCIA, RENDIMIENTO,
  SPOTIFY, WIDGETS E IDENTIDAD, MACROS
"""
from __future__ import annotations

# ─── SISTEMA Y UTILIDADES ────────────────────────────────────────────────
import sys
import os
import json
import threading
import urllib
import ctypes
from pathlib import Path
from datetime import datetime, timezone, timedelta
from PyQt6.QtCore import QPointF, pyqtProperty

# ─── PYQT6 WIDGETS ──────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QProgressBar, QDialog, QMessageBox,
    QComboBox, QCheckBox, QGraphicsDropShadowEffect,
    QScrollArea, QSlider, QFrame, QTabWidget, QColorDialog,
    QStackedWidget, QTextBrowser, QSizePolicy
)

# ─── PYQT6 CORE ─────────────────────────────────────────────────────────
from PyQt6.QtCore import (
    Qt, QUrl, pyqtSignal, pyqtSlot, QObject, QTimer,
    QSize, QThread, QRect, QRectF, QEvent, QPropertyAnimation,
    QEasingCurve, QPoint, QMetaObject, Q_ARG
)

# ─── PYQT6 GUI ──────────────────────────────────────────────────────────
from PyQt6.QtGui import (
    QBrush, QFont, QColor, QIcon, QMouseEvent, QPainterPath, QRadialGradient,
    QRegion, QResizeEvent, QPainter, QPen, QPixmap,
    QLinearGradient
)

# ─── PYQT6 WEB ENGINE ──────────────────────────────────────────────────
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

# ─── EXTERNAS ───────────────────────────────────────────────────────────
import psutil
from pyparsing import Dict

# ─── MÓDULOS PROPIOS ────────────────────────────────────────────────────
from shop import ShopWidget
from core.media_monitor import MediaMonitorWorker

# ─── QTAWESOME (ICONOS) ─────────────────────────────────────────────────
try:
    import qtawesome as qta
    HAS_QTA = True
except ImportError:
    HAS_QTA = False

def get_bundled_path(*paths):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).joinpath(*paths)
    return Path(__file__).resolve().parent.joinpath(*paths)

# ─── SISTEMA DE SONIDOS ──────────────────────────────────────────────────

class SoundManager:
    """Sistema de sonidos estilo macOS para NEXUS."""
    
    SOUND_FILES = {
        "click": "click.mp3",
        "hover": "hover.mp3",
        "open": "open_panel.mp3",
        "close": "close_panel.mp3",
        "listen": "listen_start.mp3",
        "respond": "response.mp3",
        "mute": "mute.mp3",
        "error": "error.mp3",
        "success": "success.mp3",
        "notification": "notification.mp3",
        "typing": "typing.mp3",
    }
    
    def __init__(self):
        self._enabled = True
        self._volume = 0.6
        self._sounds = {}
        self._pygame_available = False
        self._event_enabled = {}  # 🆕 Estado individual por evento
        
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._pygame_available = True
        except ImportError:
            print("[SoundManager] Pygame no instalado. Usando winsound.")
        except Exception as e:
            print(f"[SoundManager] Error inicializando pygame: {e}")
        
        self._load_sounds()
    
    def _load_sounds(self):
        if not self._pygame_available:
            return
            
        import pygame
        
        sound_dir = get_bundled_path("assets", "sounds")
        if not sound_dir.exists():
            print(f"[SoundManager] Carpeta de sonidos no encontrada: {sound_dir}")
            return
        
        for event_name, filename in self.SOUND_FILES.items():
            file_path = sound_dir / filename
            if file_path.exists():
                try:
                    sound = pygame.mixer.Sound(str(file_path))
                    sound.set_volume(self._volume)
                    self._sounds[event_name] = sound
                except Exception as e:
                    print(f"[SoundManager] Error cargando {filename}: {e}")
            else:
                print(f"[SoundManager] Sonido no encontrado: {file_path}")
        
        print(f"[SoundManager] {len(self._sounds)} sonidos cargados.")
    
    def play(self, event_name: str):
        """Reproduce un sonido si está habilitado globalmente Y individualmente."""
        if not self._enabled:
            return
        # 🆕 Verificar estado individual
        if not self._event_enabled.get(event_name, True):
            return
            
        if event_name in self._sounds:
            try:
                self._sounds[event_name].play()
            except Exception as e:
                print(f"[SoundManager] Error reproduciendo {event_name}: {e}")
        else:
            try:
                import winsound
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
            except:
                pass
    
    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))
        for sound in self._sounds.values():
            sound.set_volume(self._volume)
    
    def set_enabled(self, enabled: bool):
        self._enabled = enabled
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    # 🆕 Métodos para control individual
    def set_event_enabled(self, event_name: str, enabled: bool):
        """Activa o desactiva un sonido específico."""
        self._event_enabled[event_name] = enabled
    
    def is_event_enabled(self, event_name: str) -> bool:
        """Devuelve si un sonido específico está activado."""
        return self._event_enabled.get(event_name, True)
    
# ─── INSTANCIA GLOBAL DE SONIDOS ──────────────────────────────────────
_sound_manager = None

def get_sound_manager() -> SoundManager:
    """Obtiene la instancia global del SoundManager."""
    global _sound_manager
    if _sound_manager is None:
        _sound_manager = SoundManager()
    return _sound_manager

def play_sound(event_name: str):
    """Función de acceso rápido para reproducir sonidos."""
    get_sound_manager().play(event_name)

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
        if cfg.get("nexus_bg_color"):    C_BG    = cfg["nexus_bg_color"]
        if cfg.get("nexus_panel_color"): C_PANEL = cfg["nexus_panel_color"]
        if cfg.get("nexus_text_color"):  C_TEXT  = cfg["nexus_text_color"]
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
    apply_theme_tokens(_cfg.get("nexus_theme", "gold"), _cfg.get("nexus_custom_theme_color", ""))
    FONT_FAMILY = _cfg.get("nexus_font_family", "Century Gothic")
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


class HolographicAvatarWidget(QWidget):
    audio_signal = pyqtSignal(float)
    state_signal = pyqtSignal(str)
    
    def __init__(self, ui_ref, parent=None):
        super().__init__(parent)
        self.ui = ui_ref
        self._current_vol = 0.0
        self._state = "idle"
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(30)
        
        self.audio_signal.connect(self._on_audio)
        self.state_signal.connect(self._on_state)
        
    def sync_theme(self):
        pass

    def set_audio(self, level: float):
        self.audio_signal.emit(level)

    def set_state(self, state: str):
        self.state_signal.emit(state)
        
        # Rotational angles
        self.angle1 = 0
        self.angle2 = 0
        self.angle3 = 0

    def _on_audio(self, v: float):
        self._current_vol = self._current_vol * 0.7 + v * 0.3

    def _on_state(self, s: str):
        self._state = s

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        
        # Increase angles
        self.angle1 = (self.angle1 + 2) % 360
        self.angle2 = (self.angle2 - 1.5) % 360
        self.angle3 = (self.angle3 + 1) % 360
        
        # Base color based on state
        if self._state == "listening":
            base_color = QColor(0, 255, 204)  # Cyan
        elif self._state == "speaking":
            base_color = QColor(255, 51, 102)  # Neon Pink
        elif self._state == "thinking":
            base_color = QColor(245, 158, 11)  # Amber
        elif self._state == "error":
            base_color = QColor(255, 59, 48)  # Red
        else:
            base_color = QColor(C_PRI) if 'C_PRI' in globals() else QColor(180, 138, 255) # Primary
            
        vol_boost = min(1.0, self._current_vol * 1.5)
        radius = 50 + (vol_boost * 30)
        
        painter.translate(cx, cy)
        
        # Draw central glowing orb
        glow = QRadialGradient(0, 0, radius * 1.5)
        glow_color = QColor(base_color)
        glow_color.setAlphaF(0.4 + (vol_boost * 0.4))
        glow.setColorAt(0, glow_color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(0, 0), radius * 1.5, radius * 1.5)
        
        # Draw tech rings
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Inner Ring
        painter.save()
        painter.rotate(self.angle1)
        pen1 = QPen(base_color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen1)
        painter.drawEllipse(QPointF(0, 0), radius * 1.2, radius * 1.2)
        painter.restore()
        
        # Middle Ring
        painter.save()
        painter.rotate(self.angle2)
        mid_color = QColor(base_color)
        mid_color.setAlphaF(0.6)
        pen2 = QPen(mid_color, 1.5, Qt.PenStyle.DotLine)
        painter.setPen(pen2)
        painter.drawEllipse(QPointF(0, 0), radius * 1.5, radius * 1.5)
        painter.restore()
        
        # Outer Ring
        painter.save()
        painter.rotate(self.angle3)
        out_color = QColor(base_color)
        out_color.setAlphaF(0.3)
        pen3 = QPen(out_color, 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen3)
        painter.drawEllipse(QPointF(0, 0), radius * 1.8, radius * 1.8)
        
        # Draw some tech arcs on outer ring
        pen_arc = QPen(base_color, 3, Qt.PenStyle.SolidLine)
        pen_arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_arc)
        r = int(radius * 1.8)
        painter.drawArc(-r, -r, r*2, r*2, 0 * 16, 45 * 16)
        painter.drawArc(-r, -r, r*2, r*2, 180 * 16, 45 * 16)
        painter.restore()

class CustomParticleOrb(QWidget):
    audio_signal = pyqtSignal(float)
    state_signal = pyqtSignal(str)
    theme_signal = pyqtSignal()
    logo_style_signal = pyqtSignal(str)

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
        self.logo_style_signal.connect(self._safe_set_logo_style)  # ✅ AHORA EXISTE
        self.web_view.loadFinished.connect(self._on_load_finished)

    # ─── MÉTODOS PARA ESTILOS DE LOGO (DEFINIDOS ANTES DE USARSE) ───
    def sync_logo_style(self, style_name: str):
        """Envía el estilo de logo al HTML."""
        self.logo_style_signal.emit(style_name)

    def _safe_set_logo_style(self, style_name: str):
        """Ejecuta el JavaScript para cambiar el estilo del logo."""
        self.web_view.page().runJavaScript(
            f"if(window.setLogoStyle)window.setLogoStyle('{style_name}');")

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
                # 🆕 Cargar estilo de logo guardado
                self.sync_logo_style(cfg.get("nexus_logo_style", "clasico"))
            except Exception: 
                pass

    def sync_theme(self): 
        self.theme_signal.emit()
        
    def set_audio(self, level: float): 
        self.audio_signal.emit(level)
        
    def set_state(self, state: str): 
        self.state_signal.emit(state)

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
    THEMES = [
        {
            "name": "Clásico",
            "time_font": FONT_FAMILY,
            "time_color": "white",
            "time_weight": 700,
            "sec_color": "rgba(255,255,255,0.60)",
            "ampm_color": "rgba(255,255,255,0.75)",
            "date_font": FONT_FAMILY,
            "date_color": "rgba(255,255,255,0.85)",
            "date_italic": False,
            "date_upper": False,
            "panel_bg": "transparent",
            "panel_radius": 0,
        },
        {
            "name": "Neón",
            "time_font": FONT_FAMILY,
            "time_color": "#28e6ff",
            "time_weight": 800,
            "sec_color": "rgba(40,230,255,0.55)",
            "ampm_color": "#ff3fd8",
            "date_font": FONT_FAMILY,
            "date_color": "#ff3fd8",
            "date_italic": False,
            "date_upper": True,
            "panel_bg": "rgba(20, 10, 35, 0.35)",
            "panel_radius": 14,
        },
        {
            "name": "Oro Elegante",
            "time_font": "Georgia",
            "time_color": "#e8c27a",
            "time_weight": 500,
            "sec_color": "rgba(232,194,122,0.55)",
            "ampm_color": "rgba(232,194,122,0.85)",
            "date_font": "Georgia",
            "date_color": "rgba(255,255,255,0.75)",
            "date_italic": True,
            "date_upper": False,
            "panel_bg": "transparent",
            "panel_radius": 0,
        },
        {
            "name": "Retro Digital",
            "time_font": "Courier New",
            "time_color": "#39ff6a",
            "time_weight": 700,
            "sec_color": "rgba(57,255,106,0.55)",
            "ampm_color": "rgba(57,255,106,0.85)",
            "date_font": "Courier New",
            "date_color": "rgba(57,255,106,0.70)",
            "date_italic": False,
            "date_upper": True,
            "panel_bg": "rgba(0, 20, 5, 0.45)",
            "panel_radius": 8,
        },
        {
            "name": "Minimal Mono",
            "time_font": "Consolas",
            "time_color": "rgba(255,255,255,0.92)",
            "time_weight": 400,
            "sec_color": "rgba(255,255,255,0.45)",
            "ampm_color": "rgba(255,255,255,0.55)",
            "date_font": "Consolas",
            "date_color": "rgba(255,255,255,0.55)",
            "date_italic": False,
            "date_upper": True,
            "panel_bg": "transparent",
            "panel_radius": 0,
        },
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setObjectName("ClockWidget")

        self._theme_index = 0

        # Layout principal (misma altura que antes: sin fila extra)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # ─── FILA DE LA HORA + botón pegadito arriba-derecha ─────────
        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(4)

        self.lbl_time = QLabel()
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_time.setTextFormat(Qt.TextFormat.RichText)

        self.btn_theme = QPushButton("+")
        self.btn_theme.setFixedSize(18, 18)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip("Cambiar diseño del reloj")
        self.btn_theme.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.14);
                border: none;
                border-radius: 9px;
                color: white;
                font-size: 13px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.26); }
            QPushButton:pressed { background: rgba(255, 255, 255, 0.34); }
        """)
        self.btn_theme.clicked.connect(self.next_theme)

        # La hora ocupa el espacio disponible; el botón queda arriba-derecha, sin agregar altura
        time_row.addWidget(self.lbl_time, 1)
        time_row.addWidget(self.btn_theme, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        layout.addLayout(time_row)

        # ─── FECHA ────────────────────────────────────────────────────
        self.lbl_date = QLabel("Monday, 09 June 2026")
        layout.addWidget(self.lbl_date)

        # ⏱️ Timer para actualizar cada segundo
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

        self.apply_theme()
        self.tick()

    def next_theme(self):
        """Avanza al siguiente diseño del reloj (cíclico)."""
        self._theme_index = (self._theme_index + 1) % len(self.THEMES)
        self.apply_theme()
        self.tick()

    def apply_theme(self):
        theme = self.THEMES[self._theme_index]

        self.setStyleSheet(f"""
            QWidget#ClockWidget {{
                background: {theme['panel_bg']};
                border-radius: {theme['panel_radius']}px;
            }}
        """)

        self.lbl_date.setFont(QFont(theme['date_font'], 11, italic=theme['date_italic']))
        self.lbl_date.setStyleSheet(f"""
            color: {theme['date_color']};
            border: none;
            background: transparent;
            letter-spacing: 0.5px;
        """)

        self.btn_theme.setToolTip(f"Diseño actual: {theme['name']} — clic para cambiar")

    def tick(self):
        now = datetime.now()
        theme = self.THEMES[self._theme_index]

        horas = now.strftime("%I").lstrip("0") or "12"
        minutos = now.strftime("%M")
        segundos = now.strftime("%S")
        ampm = now.strftime("%p")

        html = f"""
        <span style="font-size: 34px; font-weight: {theme['time_weight']}; font-family: '{theme['time_font']}'; color: {theme['time_color']};">
            {horas}:{minutos}
        </span>
        <span style="font-size: 16px; font-weight: 600; font-family: '{theme['time_font']}'; color: {theme['sec_color']};">
            :{segundos}
        </span>
        <span style="font-size: 18px; font-weight: 600; font-family: '{theme['time_font']}'; color: {theme['ampm_color']}; margin-left: 6px;">
            {ampm}
        </span>
        """
        self.lbl_time.setText(html)

        fecha_txt = now.strftime("%A, %d %B %Y")
        if theme['date_upper']:
            fecha_txt = fecha_txt.upper()
        self.lbl_date.setText(fecha_txt)

    def update_style(self):
        self.apply_theme()

class MiniRing(QWidget):
    """Ícono circular chiquito (tipo ◔) que se rellena según el porcentaje."""
 
    def __init__(self, size=14, ring_width=2, parent=None):
        super().__init__(parent)
        self._size = size
        self._ring_width = ring_width
        self._value = 0
        self._ring_color = QColor("#ffffff")
        self._track_color = QColor(255, 255, 255, 45)
        self.setFixedSize(size, size)
 
    def setValue(self, value: float):
        self._value = max(0, min(100, value))
        self.update()
 
    def setColors(self, ring_hex: str, track_qcolor: QColor):
        self._ring_color = QColor(ring_hex)
        self._track_color = track_qcolor
        self.update()
 
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
 
        pad = self._ring_width / 2 + 0.5
        rect = QRectF(pad, pad, self._size - 2 * pad, self._size - 2 * pad)
 
        pen = QPen(self._track_color)
        pen.setWidthF(self._ring_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)
 
        pen.setColor(self._ring_color)
        painter.setPen(pen)
        span_angle = int(-self._value / 100 * 360 * 16)
        painter.drawArc(rect, 90 * 16, span_angle)
 
        painter.end()
 
 
class SystemMonitorWidget(QWidget):
    THEMES = [
        {
            "name": "Blanco",
            "text_color": "rgba(255,255,255,0.95)",
            "icon_color": "#ffffff",
            "panel_bg": "transparent",
            "panel_radius": 0,
            "btn_bg": "rgba(255,255,255,0.16)",
            "btn_fg": "#ffffff",
        },
        {
            "name": "Negro",
            "text_color": "rgba(20,20,20,0.90)",
            "icon_color": "#141414",
            "panel_bg": "rgba(255,255,255,0.55)",
            "panel_radius": 10,
            "btn_bg": "rgba(0,0,0,0.14)",
            "btn_fg": "#141414",
        },
        {
            "name": "Pastel Lavanda",
            "text_color": "#dccdff",
            "icon_color": "#dccdff",
            "panel_bg": "rgba(90, 70, 120, 0.25)",
            "panel_radius": 10,
            "btn_bg": "rgba(220,205,255,0.22)",
            "btn_fg": "#dccdff",
        },
        {
            "name": "Pastel Menta",
            "text_color": "#c3f2df",
            "icon_color": "#c3f2df",
            "panel_bg": "rgba(50, 100, 85, 0.22)",
            "panel_radius": 10,
            "btn_bg": "rgba(195,242,223,0.22)",
            "btn_fg": "#c3f2df",
        },
        {
            "name": "Pastel Durazno",
            "text_color": "#ffd9c2",
            "icon_color": "#ffd9c2",
            "panel_bg": "rgba(120, 80, 60, 0.22)",
            "panel_radius": 10,
            "btn_bg": "rgba(255,217,194,0.22)",
            "btn_fg": "#ffd9c2",
        },
    ]
 
    def __init__(self, parent=None):
        super().__init__(parent)
        # Antes era 100% click-through; lo desactivamos para que el botón "+" reciba el clic
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setObjectName("SysMonitor")
 
        self._theme_index = 0
        self._icon_names = {
            "ram": "fa5s.microchip",
            "cpu": "fa5s.tachometer-alt",
            "disk": "fa5s.hdd",
        }
 
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
 
        # ───── RAM (+ botón de tema en la misma fila, sin sumar altura) ─────
        self.row_ram = QHBoxLayout()
        self.row_ram.setSpacing(6)
        self.row_ram.setAlignment(Qt.AlignmentFlag.AlignRight)
 
        self.btn_theme = QPushButton("+")
        self.btn_theme.setFixedSize(16, 16)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip("Cambiar diseño del monitor")
        self.btn_theme.clicked.connect(self.next_theme)
 
        self.lbl_ram_val = QLabel("RAM 0%")
        self.lbl_ram_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
 
        self.ring_ram = MiniRing()
 
        self.row_ram.addWidget(self.btn_theme, 0, Qt.AlignmentFlag.AlignVCenter)
        self.row_ram.addWidget(self.lbl_ram_val)
        self.row_ram.addWidget(self.ring_ram, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(self.row_ram)
 
        # ───── CPU ─────
        self.row_cpu = QHBoxLayout()
        self.row_cpu.setSpacing(6)
        self.row_cpu.setAlignment(Qt.AlignmentFlag.AlignRight)
 
        self.lbl_cpu_val = QLabel("CPU 0%")
        self.lbl_cpu_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.row_cpu.addWidget(self.lbl_cpu_val)
 
        self.ring_cpu = MiniRing()
        self.row_cpu.addWidget(self.ring_cpu, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(self.row_cpu)
 
        # ───── DISK ─────
        self.row_disk = QHBoxLayout()
        self.row_disk.setSpacing(6)
        self.row_disk.setAlignment(Qt.AlignmentFlag.AlignRight)
 
        self.lbl_disk_val = QLabel("DSK 0%")
        self.lbl_disk_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.row_disk.addWidget(self.lbl_disk_val)
 
        self.ring_disk = MiniRing()
        self.row_disk.addWidget(self.ring_disk, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(self.row_disk)
 
        # Nota: si además querés el ícono fontawesome (fa5s) junto al mini-anillo,
        # descomentá este bloque:
        # if HAS_QTA:
        #     self.icon_ram = QLabel()
        #     self.row_ram.addWidget(self.icon_ram)
        #     self.icon_cpu = QLabel()
        #     self.row_cpu.addWidget(self.icon_cpu)
        #     self.icon_disk = QLabel()
        #     self.row_disk.addWidget(self.icon_disk)
 
        # ⏱️ TIMER
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)
 
        self.apply_theme()
        self.update_stats()
 
    def next_theme(self):
        """Avanza al siguiente diseño del monitor (cíclico)."""
        self._theme_index = (self._theme_index + 1) % len(self.THEMES)
        self.apply_theme()
 
    def apply_theme(self):
        theme = self.THEMES[self._theme_index]
 
        self.setStyleSheet(f"""
            QWidget#SysMonitor {{
                background: {theme['panel_bg']};
                border-radius: {theme['panel_radius']}px;
            }}
        """)
 
        text_style = f"""
            color: {theme['text_color']};
            font-size: 11px;
            font-weight: 700;
            background: transparent;
            border: none;
            letter-spacing: 0.5px;
        """
        self.lbl_ram_val.setStyleSheet(text_style)
        self.lbl_cpu_val.setStyleSheet(text_style)
        self.lbl_disk_val.setStyleSheet(text_style)
 
        track = QColor(theme["icon_color"])
        track.setAlpha(45)
        self.ring_ram.setColors(theme["icon_color"], track)
        self.ring_cpu.setColors(theme["icon_color"], track)
        self.ring_disk.setColors(theme["icon_color"], track)
 
        if HAS_QTA and hasattr(self, 'icon_ram'):
            self.icon_ram.setPixmap(qta.icon(self._icon_names["ram"], color=theme['icon_color']).pixmap(13, 13))
            self.icon_cpu.setPixmap(qta.icon(self._icon_names["cpu"], color=theme['icon_color']).pixmap(13, 13))
            self.icon_disk.setPixmap(qta.icon(self._icon_names["disk"], color=theme['icon_color']).pixmap(13, 13))
 
        self.btn_theme.setStyleSheet(f"""
            QPushButton {{
                background: {theme['btn_bg']};
                border: none;
                border-radius: 8px;
                color: {theme['btn_fg']};
                font-size: 11px;
                font-weight: 700;
                padding: 0px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.10); }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.18); }}
        """)
        self.btn_theme.setToolTip(f"Diseño actual: {theme['name']} — clic para cambiar")
 
    def update_stats(self):
        try:
            ram = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent(interval=None)
            disk = psutil.disk_usage('/').percent
 
            self.lbl_ram_val.setText(f"RAM {int(ram)}%")
            self.ring_ram.setValue(ram)
 
            if hasattr(self, 'lbl_cpu_val'):
                self.lbl_cpu_val.setText(f"CPU {int(cpu)}%")
                self.ring_cpu.setValue(cpu)
 
            if hasattr(self, 'lbl_disk_val'):
                self.lbl_disk_val.setText(f"DSK {int(disk)}%")
                self.ring_disk.setValue(disk)
        except Exception:
            pass

class HUDIconButton(QPushButton):
    def __init__(self, icon_name: str, size: int = 36, icon_size: int = 14,
                 color: str = "#d8dbe2", parent=None, liquid_glass: bool = False):
        super().__init__(parent)

        self.setFixedSize(size, size)

        self._icon_name = icon_name
        self._color = color
        self._icon_size = icon_size
        self._active = False
        self._liquid_glass = liquid_glass
        self._y_offset = 0.0  # 🔑 NUEVO: maneja el rebote sin mover el widget
        self._hover_played = False

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

        # 🔑 UNA SOLA ANIMACIÓN (no dos peleando)
        self._bounce_anim = QPropertyAnimation(self, b"yOffset")
        self._bounce_anim.setDuration(150)
        self._bounce_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ─── PROPIEDAD PARA ANIMACIÓN ─────────────────────────────────────
    def _get_y_offset(self) -> float:
        return self._y_offset

    def _set_y_offset(self, v: float):
        self._y_offset = v
        self.update()  # 🔑 fuerza repintado, NO mueve el widget

    yOffset = pyqtProperty(float, _get_y_offset, _set_y_offset)

    # ─── ANIMACIÓN ÚNICA ──────────────────────────────────────────────
    def _animate_offset_to(self, target: float, duration: int = 150):
        self._bounce_anim.stop()  # 🔑 corta la animación anterior
        self._bounce_anim.setDuration(duration)
        self._bounce_anim.setStartValue(self._y_offset)
        self._bounce_anim.setEndValue(target)
        self._bounce_anim.start()

    def update_style(self):
        from ui import C_PRI
        c_pri_color = QColor(C_PRI)
        r, g, b = c_pri_color.red(), c_pri_color.green(), c_pri_color.blue()

        if self._liquid_glass:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(255, 255, 255, 0.10),
                        stop:0.5 rgba(255, 255, 255, 0.05),
                        stop:1 rgba(255, 255, 255, 0.02)
                    );
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 18px;
                }
                QPushButton:hover {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(255, 255, 255, 0.25),
                        stop:0.5 rgba(255, 255, 255, 0.15),
                        stop:1 rgba(255, 255, 255, 0.08)
                    );
                    border: 1px solid rgba(255, 255, 255, 0.35);
                }
                QPushButton:pressed {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(255, 255, 255, 0.35),
                        stop:0.5 rgba(255, 255, 255, 0.25),
                        stop:1 rgba(255, 255, 255, 0.15)
                    );
                    border: 1px solid rgba(255, 255, 255, 0.50);
                }
            """)
            
            self.glow.setBlurRadius(18)
            self.glow.setColor(QColor(0, 0, 0, 40))
            self.glow.setOffset(0, 2)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
            """)
            self.glow.setBlurRadius(18)
            self.glow.setColor(QColor(self._color))
            self.glow.setOffset(0, 0)

        if HAS_QTA:
            if self._active:
                c = QColor(r, g, b, 160)
                self.setIcon(qta.icon(self._icon_name, color=c))
                if not self._liquid_glass:
                    self.glow.setColor(c)
            else:
                c = QColor("#d8dbe2")
                self.setIcon(qta.icon(self._icon_name, color=c))
                if not self._liquid_glass:
                    self.glow.setColor(c)

    def set_active(self, active: bool, active_color: str = "#ffffff"):
        self._active = active
        self.update_style()

    def set_liquid_glass(self, enabled: bool):
        self._liquid_glass = enabled
        self.update_style()

    # ─── EVENTOS CON ANIMACIÓN DE OFFSET ──────────────────────────────

    def enterEvent(self, event):
        """Animación al pasar el mouse: sube 2px y cambia brillo."""
        if not self._hover_played:
            self._hover_played = True
            play_sound("hover")
        
        if HAS_QTA:
            if self._liquid_glass:
                self.setIcon(qta.icon(self._icon_name, color=QColor("#ffffff")))
                self.glow.setColor(QColor(255, 255, 255, 30))
            else:
                self.setIcon(qta.icon(self._icon_name, color=QColor("#ffffff")))
                self.glow.setColor(QColor("#ffffff"))
            self.update()
        
        # 🔑 sube 2px (el widget NO se mueve, solo se dibuja arriba)
        self._animate_offset_to(-2)
        
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Animación al salir el mouse: vuelve a la posición original."""
        self._hover_played = False
        
        if HAS_QTA:
            if self._liquid_glass:
                color = "#f59e0b" if self._active else "#d8dbe2"
                self.setIcon(qta.icon(self._icon_name, color=color))
                self.glow.setColor(QColor(0, 0, 0, 40))
            else:
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
        
        # 🔑 vuelve a 0 (posición original)
        self._animate_offset_to(0)
        
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Animación al presionar: baja 1px."""
        if event.button() == Qt.MouseButton.LeftButton:
            play_sound("click")
            
            if HAS_QTA:
                if self._liquid_glass:
                    self.setIcon(qta.icon(self._icon_name, color=QColor(255, 255, 255, 100)))
                    self.glow.setColor(QColor(255, 255, 255, 20))
                else:
                    from ui import C_PRI
                    c_pri_color = QColor(C_PRI)
                    r, g, b = c_pri_color.red(), c_pri_color.green(), c_pri_color.blue()
                    c = QColor(r, g, b, 120)
                    self.setIcon(qta.icon(self._icon_name, color=c))
                    self.glow.setColor(c)
                self.update()
            
            # 🔑 baja 1px desde donde esté (sin importar si está en hover o no)
            self._animate_offset_to(self._y_offset + 1, duration=80)
            
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Animación al soltar: vuelve a la posición de hover o normal."""
        if event.button() == Qt.MouseButton.LeftButton:
            if HAS_QTA:
                if self.underMouse():
                    if self._liquid_glass:
                        self.setIcon(qta.icon(self._icon_name, color=QColor("#ffffff")))
                        self.glow.setColor(QColor(255, 255, 255, 30))
                    else:
                        self.setIcon(qta.icon(self._icon_name, color=QColor("#ffffff")))
                        self.glow.setColor(QColor("#ffffff"))
                else:
                    if self._liquid_glass:
                        color = "#f59e0b" if self._active else "#d8dbe2"
                        self.setIcon(qta.icon(self._icon_name, color=color))
                        self.glow.setColor(QColor(0, 0, 0, 40))
                    else:
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
            
            # 🔑 si el mouse está encima → hover (-2), si no → posición normal (0)
            target = -2 if self.underMouse() else 0
            self._animate_offset_to(target)
            
        super().mouseReleaseEvent(event)

    # ─── PAINT EVENT (el secreto del rebote sin mover el widget) ──────

    def paintEvent(self, event):
        from PyQt6.QtWidgets import QStyleOptionButton, QStyle
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 🔑 AQUÍ ESTÁ EL TRUCO: se dibuja desplazado, pero el widget NO se mueve
        # El layout nunca se entera de este movimiento
        painter.translate(0, self._y_offset)

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.icon = QIcon()

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

        # ✨ ACCESOS DIRECTOS CON LIQUID GLASS ✅
        self.btn_bell = HUDIconButton(
            'fa5s.th',
            36,
            14,
            '#ffffff',
            self,
            liquid_glass=True
        )
        self.btn_bell.setToolTip("Accesos Directos")

        # 📁 CARPETA NORMAL (sin Liquid Glass)
        self.btn_folder = HUDIconButton(
            'fa5s.folder',
            36,
            14,
            icon_color,
            self,
            liquid_glass=False  # 🆕 Desactivado
        )

        # 📅 CALENDARIO NORMAL (sin Liquid Glass)
        self.btn_calendar = HUDIconButton(
            'fa5s.calendar-alt',
            36,
            14,
            icon_color,
            self,
            liquid_glass=False  # 🆕 Desactivado
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
        """Cambia el color cuando hay notificaciones (obsoleto para accesos, pero mantenemos compatibilidad)"""
        color = "#f59e0b" if has_notif else "#d8dbe2"
        
        if HAS_QTA:
            self.btn_bell.setIcon(qta.icon('fa5s.th', color=color))
            
        if has_notif:
            self.btn_bell._active = True
        else:
            self.btn_bell._active = False
        
        self.btn_bell.update_style()


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

    def update_text(self, ai_name: str = "◉ N.E.X.U.S"):  

        self.setText(
            f"""
            <span style="
                color:#d8dbe2;
                font-weight:700;
                letter-spacing:1px;
                font-size:13px;
            ">
                {ai_name}
            </span>
            <span style="
                color:#b56cff;
                font-weight:700;
                background-color:rgba(35,20,55,0.85);
                border:1px solid rgba(181,108,255,0.55);
                border-radius:3px;
                padding:1px 8px;
                margin-left:6px;
                font-size:10px;
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
    """Panel de notificaciones premium estilo macOS/Windows 11 con Liquid Glass."""
 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NotifCard")
        self.setFixedWidth(380)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._max_notifications = 10
        self._notification_count = 0
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)
        self._animations = []
        self._notifications_data = []
        self._initialized = False
        self._has_date_header = False  # 🆕 controla el encabezado "HOY"
 
        self.setStyleSheet("""
        QWidget#NotifCard {
            background: rgba(8, 8, 12, 0.88);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 24px;
        }
        QWidget#NotifCard:hover {
            border-color: rgba(255, 255, 255, 0.08);
        }
        QLabel {
            background: transparent;
            border: none;
            color: rgba(245, 245, 250, 0.96);
        }
        QScrollArea {
            background: transparent;
            border: none;
        }
        QScrollBar:vertical {
            border: none;
            background: rgba(255, 255, 255, 0.02);
            width: 4px;
            border-radius: 2px;
            margin: 4px 2px;
        }
        QScrollBar::handle:vertical {
            background: rgba(255, 255, 255, 0.08);
            min-height: 30px;
            border-radius: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background: rgba(255, 255, 255, 0.15);
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QPushButton {
            background: transparent;
            border: none;
            font-family: inherit;
        }
        """)
 
        apply_glass_shadow(self, blur_radius=32, y_offset=8, alpha=140)
 
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
 
        # ─── HEADER ──────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(12)
 
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(20, 20)
        self.icon_lbl.setStyleSheet("background: rgba(255,255,255,0.04); border-radius: 10px;")
        if HAS_QTA:
            self.icon_lbl.setPixmap(qta.icon('fa5s.bell', color='rgba(255,255,255,0.7)').pixmap(14, 14))
        hdr.addWidget(self.icon_lbl)
 
        self.title_lbl = QLabel("Notificaciones")
        self.title_lbl.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: rgba(255,255,255,0.92);
            letter-spacing: 0.3px;
        """)
        hdr.addWidget(self.title_lbl)
 
        self.badge_count = QLabel("0")
        self.badge_count.setFixedSize(22, 22)
        self.badge_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_count.setStyleSheet("""
            background: rgba(255, 255, 255, 0.06);
            color: rgba(255, 255, 255, 0.5);
            border-radius: 11px;
            font-size: 10px;
            font-weight: 600;
        """)
        self.badge_count.hide()
        hdr.addWidget(self.badge_count)
 
        hdr.addStretch()
 
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setFixedHeight(28)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.4);
                border-radius: 8px;
                font-size: 10px;
                font-weight: 500;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.7);
            }
        """)
        self.btn_clear.clicked.connect(self.clear_notifications)
        hdr.addWidget(self.btn_clear)
 
        self.btn_close_notif = QPushButton("✕")
        self.btn_close_notif.setFixedSize(26, 26)
        self.btn_close_notif.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255,255,255,0.15);
                border: none;
                border-radius: 13px;
                font-size: 14px;
                font-weight: 300;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.5);
            }
        """)
        self.btn_close_notif.clicked.connect(self.close)
        hdr.addWidget(self.btn_close_notif)
 
        layout.addLayout(hdr)
 
        # ─── SEPARADOR ──────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: rgba(255,255,255,0.03); border: none; max-height: 1px;")
        layout.addWidget(sep)
 
        # ─── SCROLL AREA ────────────────────────────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(280)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
 
        self.notif_container = QWidget()
        self.notif_container.setStyleSheet("background: transparent;")
        self.notif_layout = QVBoxLayout(self.notif_container)
        self.notif_layout.setContentsMargins(2, 4, 2, 4)
        self.notif_layout.setSpacing(6)
        self.notif_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
 
        self.scroll_area.setWidget(self.notif_container)
        layout.addWidget(self.scroll_area)
 
        # ─── FOOTER ──────────────────────────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(8)
 
        self.footer_label = QLabel("Mostrando notificaciones recientes")
        self.footer_label.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.12);")
        footer.addWidget(self.footer_label)
        footer.addStretch()
 
        self.unread_label = QLabel()
        self.unread_label.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.12);")
        footer.addWidget(self.unread_label)
 
        layout.addLayout(footer)
 
        self.notifications = []
        self.layout_ref = layout
        self.hide()
 
        self._initialized = True
        self._add_default_notifications()
 
    # ─────────────────────────────────────────────────────────────
    #  Encabezado "HOY"
    # ─────────────────────────────────────────────────────────────
    def _ensure_date_header(self):
        """Inserta el encabezado 'HOY' una sola vez, siempre fijo arriba."""
        if self._has_date_header:
            return
        header = QLabel(datetime.now().strftime("HOY · %d %b").upper())
        header.setStyleSheet("""
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: rgba(255,255,255,0.28);
            padding: 2px 4px 4px 4px;
        """)
        self.notif_layout.insertWidget(0, header)
        self._date_header_widget = header
        self._has_date_header = True
 
    def _add_default_notifications(self):
        self._clear_layout_clean()
        self.push_notification(" Sistema protegido", "Notificacion desactivada", priority="normal")

    def _clear_layout_clean(self):
        while self.notif_layout.count():
            item = self.notif_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.notifications = []
        self._notifications_data = []
        self._notification_count = 0
        self._has_date_header = False
 
    def _on_update_click(self):
        self.push_notification("🔄 Actualizando...", "Descargando la versión 2.5.0", priority="high")
 
    # ─────────────────────────────────────────────────────────────
    #  Construcción de cada tarjeta
    # ─────────────────────────────────────────────────────────────
    def _make_item(self, title: str, body: str, thumbnail_path=None,
                    priority: str = "normal", action_label: str = None,
                    action_callback=None) -> QWidget:
        container = QWidget()
        container.setObjectName("NotifItem")
        container.setFixedHeight(64)
 
        bg_opacity = {"normal": "0.03", "high": "0.05", "urgent": "0.07"}
        border_opacity = {"normal": "0.04", "high": "0.08", "urgent": "0.12"}
        accent_color = {  # 🆕 acento de color por prioridad
            "normal": "rgba(255,255,255,0.10)",
            "high": "rgba(245,158,11,0.55)",
            "urgent": "rgba(255,59,48,0.65)",
        }.get(priority, "rgba(255,255,255,0.10)")
 
        container.setStyleSheet(f"""
            QWidget#NotifItem {{
                background: rgba(255, 255, 255, {bg_opacity.get(priority, '0.03')});
                border: 1px solid rgba(255, 255, 255, {border_opacity.get(priority, '0.04')});
                border-left: 3px solid {accent_color};
                border-radius: 12px;
            }}
            QWidget#NotifItem:hover {{
                background: rgba(255, 255, 255, 0.06);
                border-color: rgba(255, 255, 255, 0.10);
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
 
        item_shadow = QGraphicsDropShadowEffect(container)
        item_shadow.setBlurRadius(10)
        item_shadow.setColor(QColor(0, 0, 0, 25))
        item_shadow.setOffset(0, 2)
        container.setGraphicsEffect(item_shadow)
 
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(12)
 
        icon_container = QLabel()
        icon_container.setFixedSize(36, 36)
        icon_text = {"normal": "•", "high": "◆", "urgent": "⬤"}.get(priority, "•")
        icon_container.setText(icon_text)
        icon_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_container.setStyleSheet("""
            border-radius: 10px;
            background: rgba(255,255,255,0.04);
            font-size: 16px;
            color: rgba(255,255,255,0.3);
        """)
        main_layout.addWidget(icon_container)
 
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
 
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
 
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.92);")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
 
        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.2);")
        header_layout.addWidget(time_label)
 
        content_layout.addLayout(header_layout)
 
        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setStyleSheet("font-size: 10px; color: rgba(255,255,255,0.55);")
        content_layout.addWidget(body_label)
 
        main_layout.addLayout(content_layout, 1)
 
        if action_label and action_callback:
            action_btn = QPushButton(action_label)
            action_btn.setFixedHeight(26)
            action_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.06);
                    color: rgba(255,255,255,0.6);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 8px;
                    font-size: 10px;
                    font-weight: 500;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.12);
                    border-color: rgba(255,255,255,0.12);
                }
                QPushButton:pressed { background: rgba(255,255,255,0.04); }
            """)
            action_btn.clicked.connect(action_callback)
            main_layout.addWidget(action_btn)
 
        return container
 
    def _update_badge(self):
        count = len(self.notifications)
        unread = sum(1 for n in self._notifications_data if not n.get("read", False))
 
        if count > 0:
            self.badge_count.setText(str(count))
            self.badge_count.show()
        else:
            self.badge_count.hide()
 
        self.unread_label.setText(f"{unread} no leída{'s' if unread != 1 else ''}" if unread > 0 else "Todas leídas")
 
    # ─────────────────────────────────────────────────────────────
    #  ANIMACIÓN — FIX del bug (antes usaba setWindowOpacity en un hijo)
    # ─────────────────────────────────────────────────────────────
    def _animate_item(self, widget):
        """Animación de entrada correcta: QGraphicsOpacityEffect + QPropertyAnimation.
 
        Nunca usar widget.setWindowOpacity() aquí: ese método solo es válido
        en ventanas top-level. Usarlo en un widget hijo (como esta tarjeta)
        fuerza a Qt a crear un handle de ventana nativo para él, lo que en
        una app translúcida y sin bordes produce artefactos de composición
        (texto/ventanas de fondo "fantasma", como el bug reportado).
        """
        from PyQt6.QtCore import QParallelAnimationGroup
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
 
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
 
        end_pos = widget.pos()
        start_pos = QPoint(end_pos.x(), end_pos.y() + 20)
        widget.move(start_pos)
 
        group = QParallelAnimationGroup(self)
 
        pos_anim = QPropertyAnimation(widget, b"pos", self)
        pos_anim.setDuration(280)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
 
        op_anim = QPropertyAnimation(effect, b"opacity", self)
        op_anim.setDuration(240)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
 
        group.addAnimation(pos_anim)
        group.addAnimation(op_anim)
        self._animations.append(group)
 
        def _cleanup():
            try:
                widget.setGraphicsEffect(None)
            except RuntimeError:
                pass  # el widget pudo haber sido eliminado (ej. clear_notifications)
            if group in self._animations:
                self._animations.remove(group)
 
        group.finished.connect(_cleanup)
        group.start()
 
    def push_notification(self, title: str, body: str,
                           thumbnail_path=None, action_label: str = None,
                           action_callback=None, priority: str = "normal"):
        """Agrega una nueva notificación premium."""
 
        if len(self.notifications) >= self._max_notifications:
            oldest = self.notif_layout.takeAt(self.notif_layout.count() - 1)
            if oldest and oldest.widget():
                oldest.widget().deleteLater()
            if self.notifications:
                self.notifications.pop(-1)
            if self._notifications_data:
                self._notifications_data.pop(-1)
 
        self._ensure_date_header()  # 🆕 asegura que "HOY" esté siempre arriba
 
        item = self._make_item(title, body, thumbnail_path, priority, action_label, action_callback)
 
        # El header (si existe) va en el índice 0; el item nuevo se inserta justo debajo.
        insert_at = 1 if self._has_date_header else 0
        self.notif_layout.insertWidget(insert_at, item)
 
        self.notifications.append(item)
        self._notifications_data.append({
            "title": title, "body": body, "priority": priority,
            "timestamp": datetime.now(), "read": False,
        })
        self._notification_count += 1
 
        self._update_badge()
        self._animate_item(item)
 
        if not self.isVisible():
            self.show()
            self.raise_()
            self._fade_in()
 
        self.adjustSize()
        self.scroll_area.verticalScrollBar().setValue(0)
 
        if len(self.notifications) >= 3:
            self._hide_timer.start(5000)
 
    def _fade_in(self):
        """Fade-in del panel completo (esto SÍ es correcto: self es top-level)."""
        self.setWindowOpacity(0.0)
        animation = QPropertyAnimation(self, b"windowOpacity")
        animation.setDuration(250)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        self._animations.append(animation)
 
    def clear_notifications(self):
        self._animations.clear()
        count = self.notif_layout.count()
        if count > 0:
            widgets = [self.notif_layout.itemAt(i).widget()
                       for i in range(count) if self.notif_layout.itemAt(i).widget()]
            for widget in widgets:
                widget.deleteLater()
            self._clear_layout_clean()
            self._update_badge()
        else:
            self._clear_layout_clean()
 
    def _auto_hide(self):
        if self.isVisible() and len(self.notifications) >= 3:
            self.close()
 
    def showEvent(self, event):
        if self.notif_layout.count() == 0 and self._initialized:
            self._add_default_notifications()
        super().showEvent(event)
 
    def closeEvent(self, event):
        self._animations.clear()
        main_window = self.window()
        if main_window and hasattr(main_window, "bottom_left_dock"):
            main_window.bottom_left_dock.set_notification(False)
        super().closeEvent(event)
 
    def mark_all_read(self):
        for data in self._notifications_data:
            data["read"] = True
        self._update_badge()

class ShortcutsCard(QWidget):
    """Panel de accesos directos premium con Liquid Glass real (igual que Spotify)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ShortcutsCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 420)
        self._radius = 22
        self.drag_position = None

        # Load shortcuts
        self.shortcuts = []
        self._load_shortcuts()

        apply_glass_shadow(self, blur_radius=35, y_offset=8, alpha=140)

        # Solo estilos internos (fondo lo pinta paintEvent)
        self.setStyleSheet("""
QLabel { background: transparent; border: none; }
QPushButton { background: transparent; border: none; }
""")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 12)
        root.setSpacing(10)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Accesos Directos")
        title.setStyleSheet("color: rgba(255,255,255,0.92); font-size:15px; font-weight:700;")
        header.addWidget(title)
        header.addStretch()

        self.btn_add = QPushButton()
        self.btn_add.setFixedSize(28, 28)
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.10);
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.18);
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.20);
                border: 1px solid rgba(255,255,255,0.35);
            }
        """)
        if HAS_QTA:
            self.btn_add.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_add.clicked.connect(self._add_shortcut)
        header.addWidget(self.btn_add)
        root.addLayout(header)

        # Separator line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.08);")
        root.addWidget(sep)

        # Scroll area para la grilla
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QWidget#gridContainer { background: transparent; }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.03);
                width: 5px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.grid_container = QWidget()
        self.grid_container.setObjectName("gridContainer")
        from PyQt6.QtWidgets import QGridLayout
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(4, 8, 4, 8)
        self.grid_layout.setSpacing(12)

        self.scroll.setWidget(self.grid_container)
        root.addWidget(self.scroll, 1)

        # Hint label
        self.hint_label = QLabel("Click + para agregar apps  ·  Click derecho para eliminar")
        self.hint_label.setStyleSheet("color: rgba(255,255,255,0.25); font-size:10px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.hint_label)

        self._refresh_grid()
        self.hide()

    # ── Liquid Glass Paint (idéntico al de Spotify) ──
    def showEvent(self, event):
        super().showEvent(event)
        try:
            apply_acrylic_blur(int(self.winId()), color=(15, 15, 25, 60))
        except Exception:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 1) Base MUY transparente
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 30))
        base_gradient.setColorAt(0.5, QColor(200, 210, 230, 18))
        base_gradient.setColorAt(1.0, QColor(160, 170, 200, 25))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)

        # 2) Frost
        painter.setBrush(QColor(255, 255, 255, 6))
        painter.drawPath(path)

        # 3) Sombra interior
        bottom_gradient = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 20))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)

        # 4) Borde de cristal
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 5) Reflejo superior
        shine_rect = QRectF(
            rect.left() + self._radius * 0.6, rect.top() + 2,
            rect.width() - self._radius * 1.2, self._radius * 0.65
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)
        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)

        super().paintEvent(event)

    # ── Drag ──
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_position and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        super().mouseReleaseEvent(event)

    # ── Data ──
    def _load_shortcuts(self):
        import json
        from pathlib import Path
        config_path = Path(__file__).parent / "config" / "shortcuts.json"
        if config_path.exists():
            try:
                self.shortcuts = json.loads(config_path.read_text(encoding="utf-8"))
            except:
                self.shortcuts = []
        else:
            self.shortcuts = []

    def _save_shortcuts(self):
        import json
        from pathlib import Path
        config_path = Path(__file__).parent / "config" / "shortcuts.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(self.shortcuts, indent=4), encoding="utf-8")

    def _get_exe_icon(self, exe_path):
        """Extrae el icono del .exe y devuelve un QPixmap"""
        try:
            from PyQt6.QtWidgets import QFileIconProvider
            from PyQt6.QtCore import QFileInfo
            provider = QFileIconProvider()
            info = QFileInfo(exe_path)
            icon = provider.icon(info)
            return icon.pixmap(40, 40)
        except:
            pass
        # Fallback: icono genérico
        if HAS_QTA:
            return qta.icon('fa5s.cube', color='rgba(255,255,255,0.6)').pixmap(32, 32)
        return QPixmap()

    def _add_shortcut(self):
        from PyQt6.QtWidgets import QFileDialog
        import os
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Aplicación", "",
            "Ejecutables (*.exe);;Accesos directos (*.lnk);;Todos los archivos (*.*)"
        )
        if path:
            name = os.path.basename(path).split(".")[0]
            # Capitalizar bonito
            name = name.replace("_", " ").replace("-", " ").title()
            if len(name) > 14:
                name = name[:13] + "…"
            self.shortcuts.append({"name": name, "path": path})
            self._save_shortcuts()
            self._refresh_grid()
            play_sound("success")

    def _remove_shortcut(self, index):
        if 0 <= index < len(self.shortcuts):
            self.shortcuts.pop(index)
            self._save_shortcuts()
            self._refresh_grid()

    def _open_shortcut(self, path):
        import os
        try:
            os.startfile(path)
            play_sound("open")
        except Exception as e:
            print(f"Error abriendo acceso directo: {e}")
            play_sound("error")

    def _refresh_grid(self):
        # Limpiar grid
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # Llenar grid (5 columnas)
        cols = 5
        for i, sc in enumerate(self.shortcuts):
            row, col = divmod(i, cols)

            # Container vertical: icono + nombre
            container = QWidget()
            container.setFixedSize(68, 78)
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            vl = QVBoxLayout(container)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(4)
            vl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Icono
            icon_btn = QPushButton()
            icon_btn.setFixedSize(48, 48)
            icon_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 14px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.16);
                    border: 1px solid rgba(255,255,255,0.30);
                }
            """)
            pix = self._get_exe_icon(sc["path"])
            if pix and not pix.isNull():
                icon_btn.setIcon(QIcon(pix))
                icon_btn.setIconSize(QSize(32, 32))
            icon_btn.clicked.connect(lambda checked, p=sc["path"]: self._open_shortcut(p))

            # Click derecho para eliminar
            icon_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            icon_btn.customContextMenuRequested.connect(lambda pos, idx=i: self._remove_shortcut(idx))

            # Nombre
            name_lbl = QLabel(sc["name"])
            name_lbl.setStyleSheet("color: rgba(255,255,255,0.75); font-size:9px; font-weight:500;")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setFixedWidth(68)

            vl.addWidget(icon_btn, 0, Qt.AlignmentFlag.AlignCenter)
            vl.addWidget(name_lbl)

            self.grid_layout.addWidget(container, row, col)

        # Update hint visibility
        self.hint_label.setVisible(len(self.shortcuts) == 0)


class FloatingSpotifyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SpotifyFloat")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 150)  # 🔧 un poco más alto para el nuevo layout
        self.drag_position = None
        self._current_track_id = None
        self._radius = 26  # 💎 tarjeta redondeada, no píldora completa (como la foto)
        self._duration_ms = 0
        self._seeking = False
        self._pending_seek_ms = 0
 
        # 💎 Solo estilos de contenido interno (el fondo lo pinta paintEvent)
        self.setStyleSheet("""
QLabel {
    background: transparent;
    border: none;
}
 
QPushButton {
    background: transparent;
    border: none;
}
 
QPushButton:hover {
    background: rgba(255,255,255,0.10);
    border-radius: 15px;
}
""")
 
        apply_glass_shadow(self, blur_radius=35, y_offset=8, alpha=140)
 
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(10)
 
        # 🔝 FILA SUPERIOR: carátula + título/artista
        top = QHBoxLayout()
        top.setSpacing(12)
 
        self.lbl_art = QLabel()
        self.lbl_art.setFixedSize(44, 44)
        self.lbl_art.setStyleSheet("""
        background: rgba(255,255,255,0.10);
        border-radius: 10px;
        """)
        self.lbl_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
 
        if HAS_QTA:
            self.lbl_art.setPixmap(qta.icon('fa5b.spotify', color='rgba(255,255,255,0.75)').pixmap(20, 20))
 
        top.addWidget(self.lbl_art)
 
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
 
        self.lbl_track = QLabel("Not Playing")
        self.lbl_track.setStyleSheet("""
        font-size:14px;
        font-weight:700;
        color: rgba(255,255,255,0.95);
        """)
 
        self.lbl_artist = QLabel("Spotify")
        self.lbl_artist.setStyleSheet("""
        font-size:11px;
        font-weight:600;
        color: rgba(190,210,255,0.90);
        """)
 
        info_col.addWidget(self.lbl_track)
        info_col.addWidget(self.lbl_artist)
 
        top.addLayout(info_col, 1)
        root.addLayout(top)
 
        # 📊 BARRA DE PROGRESO (ahora interactiva: click + arrastre = seek)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(4)
        self.prog_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prog_bar.setStyleSheet('''
        QProgressBar { background: rgba(255,255,255,0.15); border: none; border-radius: 2px; }
        QProgressBar::chunk { background: rgba(255,255,255,0.85); border-radius: 2px; }
        ''')
        # 🔧 interceptamos el mouse para poder adelantar/atrasar
        self.prog_bar.mousePressEvent = self._prog_mouse_press
        self.prog_bar.mouseMoveEvent = self._prog_mouse_move
        self.prog_bar.mouseReleaseEvent = self._prog_mouse_release
 
        root.addWidget(self.prog_bar)
 
        # ⏱️ TIEMPOS (debajo de la barra, izquierda/derecha, como en la foto)
        time_row = QHBoxLayout()
        self.lbl_time_l = QLabel("0:00")
        self.lbl_time_l.setStyleSheet("font-size:11px; font-weight:600; color: rgba(255,255,255,0.70);")
        self.lbl_time_r = QLabel("0:00")
        self.lbl_time_r.setStyleSheet("font-size:11px; font-weight:600; color: rgba(255,255,255,0.70);")
        time_row.addWidget(self.lbl_time_l)
        time_row.addStretch()
        time_row.addWidget(self.lbl_time_r)
        root.addLayout(time_row)
 
        # ⏯️ CONTROLES (centrados)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(22)
        ctrl.setAlignment(Qt.AlignmentFlag.AlignCenter)
 
        if HAS_QTA:
            self.btn_prev = QPushButton()
            self.btn_prev.setFixedSize(32, 32)
            self.btn_prev.setIcon(qta.icon('fa5s.step-backward', color='rgba(255,255,255,0.85)'))
            self.btn_prev.setIconSize(QSize(15, 15))
 
            self.btn_play = QPushButton()
            self.btn_play.setFixedSize(36, 36)
            self.btn_play.setIcon(qta.icon('fa5s.pause', color='rgba(255,255,255,0.95)'))
            self.btn_play.setIconSize(QSize(17, 17))
 
            self.btn_next = QPushButton()
            self.btn_next.setFixedSize(32, 32)
            self.btn_next.setIcon(qta.icon('fa5s.step-forward', color='rgba(255,255,255,0.85)'))
            self.btn_next.setIconSize(QSize(15, 15))
 
            ctrl.addWidget(self.btn_prev)
            ctrl.addWidget(self.btn_play)
            ctrl.addWidget(self.btn_next)
 
            self.btn_prev.clicked.connect(lambda: self._press("prevtrack"))
            self.btn_play.clicked.connect(lambda: self._press("playpause"))
            self.btn_next.clicked.connect(lambda: self._press("nexttrack"))
            def _press(self, key):
                play_sound("click") 
 
        root.addLayout(ctrl)
 
        # ⏱️ TIMER
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_playback_info)
        self.timer.start(5000)
 
        QTimer.singleShot(800, self.update_playback_info)
        self.hide()
 
        # 🔥 CARGAR POSICIÓN GUARDADA AL INICIAR
        QTimer.singleShot(100, self.load_position)
 
    def showEvent(self, event):
        """Aplica el blur nativo de Windows cada vez que el widget se muestra
        (hay que hacerlo aquí porque necesitamos el HWND real, que solo
        existe una vez que la ventana fue creada por el sistema)."""
        super().showEvent(event)
        try:
            apply_acrylic_blur(int(self.winId()), color=(15, 15, 25, 60))
        except Exception:
            pass
 
    def paintEvent(self, event):
        """Fondo liquid glass REAL: muy transparente, con un leve tinte
        y bordes de luz. Si apply_acrylic_blur funcionó (Windows), el
        sistema operativo se encarga del desenfoque de lo que hay detrás;
        esta capa solo agrega el tinte y los brillos de vidrio."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
 
        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
 
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
 
        # 1) Base MUY transparente (tinte sutil, no tarjeta opaca)
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 35))
        base_gradient.setColorAt(0.5, QColor(200, 210, 230, 22))
        base_gradient.setColorAt(1.0, QColor(160, 170, 200, 30))
 
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)
 
        # 2) Frost casi imperceptible (solo textura, no opacidad)
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawPath(path)
 
        # 3) Sombra interior abajo, muy leve, para dar profundidad
        bottom_gradient = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 25))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)
 
        # 4) Borde de luz (el que realmente vende el efecto "cristal")
        painter.setPen(QPen(QColor(255, 255, 255, 90), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
 
        # 5) Reflejo superior curvo (sutil)
        shine_rect = QRectF(
            rect.left() + self._radius * 0.6,
            rect.top() + 2,
            rect.width() - self._radius * 1.2,
            self._radius * 0.7
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)
 
        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 45))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
 
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)
 
        super().paintEvent(event)
 
    # ── 🎯 SEEK: adelantar/atrasar tocando o arrastrando la barra ──
    def _prog_seek_to(self, x):
        w = self.prog_bar.width()
        if w <= 0 or self._duration_ms <= 0:
            return
        frac = max(0.0, min(1.0, x / w))
        new_ms = int(frac * self._duration_ms)
        self._pending_seek_ms = new_ms
 
        # Reflejar de inmediato en la UI (feedback visual instantáneo)
        self.prog_bar.setValue(int(frac * 100))
        pos_sec = new_ms // 1000
        self.lbl_time_l.setText(f"{pos_sec//60}:{pos_sec%60:02d}")
 
    def _prog_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._seeking = True
            self._prog_seek_to(event.position().x())
 
    def _prog_mouse_move(self, event):
        if self._seeking:
            self._prog_seek_to(event.position().x())
 
    def _prog_mouse_release(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._seeking:
            self._seeking = False
            self._do_seek(self._pending_seek_ms)
 
    def _do_seek(self, position_ms):
        def run():
            try:
                import logging
                logging.getLogger('spotipy').setLevel(logging.CRITICAL)
 
                from memory.config_manager import load_api_keys, BASE_DIR
                cfg = load_api_keys()
 
                cid = cfg.get("spotify_client_id")
                csec = cfg.get("spotify_client_secret")
 
                if not (cid and csec):
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
                devs = sp.devices().get("devices", [])
                did = next((d["id"] for d in devs if d["is_active"]), devs[0]["id"] if devs else None)
 
                sp.seek_track(position_ms, device_id=did)
                QTimer.singleShot(400, self.update_playback_info)
            except Exception as e:
                print(f"[Spotify] Error al hacer seek: {e}")
 
        import threading
        threading.Thread(target=run, daemon=True).start()
 
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
        def fetch_data():
            from PyQt6.QtCore import QMetaObject, Qt as _Qt, Q_ARG
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
                    item = curr["item"]
                    data = {
                        "is_playing": curr["is_playing"],
                        "name": item["name"],
                        "artist": item["artists"][0]["name"] if item.get("artists") else "Desconocido",
                        "duration_ms": item["duration_ms"],
                        "progress_ms": curr["progress_ms"],
                        "id": item.get("id"),
                        "image_url": item.get("album", {}).get("images", [{}])[-1].get("url") if item.get("album", {}).get("images") else None
                    }
                    if data["image_url"] and data["id"] != getattr(self, "_current_track_id", None):
                        import urllib.request as urllib_req
                        try:
                            data["image_data"] = urllib_req.urlopen(data["image_url"], timeout=3).read()
                        except:
                            data["image_data"] = None
                    else:
                        data["image_data"] = None
 
                    QMetaObject.invokeMethod(self, "_on_playback_info_ready",
                                             _Qt.ConnectionType.QueuedConnection,
                                             Q_ARG(dict, data))
                else:
                    QMetaObject.invokeMethod(self, "_on_playback_info_ready",
                                             _Qt.ConnectionType.QueuedConnection,
                                             Q_ARG(dict, {}))
            except Exception as e:
                pass
 
        import threading
        threading.Thread(target=fetch_data, daemon=True).start()
 
    @pyqtSlot(dict)
    def _on_playback_info_ready(self, data):
        if not data:
            self.lbl_track.setText("Not Playing")
            self.lbl_artist.setText("Spotify")
            self._duration_ms = 0
            if self.isVisible() and hasattr(self.window(), "animate_hide_widget"):
                self.window().animate_hide_widget(self)
            return
 
        if not self.isVisible() and hasattr(self.window(), "animate_show_widget"):
            self.window().animate_show_widget(self)
 
        name = data["name"][:28] + ("…" if len(data["name"]) > 28 else "")
        artist = data["artist"][:30] + ("…" if len(data["artist"]) > 30 else "")
 
        self.lbl_track.setText(name)
        self.lbl_artist.setText(artist)
 
        self._duration_ms = data["duration_ms"]
        dur = data["duration_ms"] // 1000
        pos = data["progress_ms"] // 1000
 
        # 🔧 mientras el usuario está arrastrando, no pisamos su valor con el del servidor
        if not self._seeking:
            self.prog_bar.setValue(int(pos / dur * 100) if dur else 0)
            self.lbl_time_l.setText(f"{pos//60}:{pos%60:02d}")
        self.lbl_time_r.setText(f"{dur//60}:{dur%60:02d}")
 
        if HAS_QTA:
            icon = 'fa5s.pause' if data["is_playing"] else 'fa5s.play'
            self.btn_play.setIcon(qta.icon(icon, color='rgba(255,255,255,0.95)'))
 
        if data.get("id") != self._current_track_id:
            self._current_track_id = data.get("id")
            if data.get("image_data"):
                try:
                    from PyQt6.QtGui import QPixmap
                    pix = QPixmap()
                    pix.loadFromData(data["image_data"])
                    pix = pix.scaled(
                        44, 44,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.lbl_art.setPixmap(pix)
                    self.lbl_art.setStyleSheet("border-radius:10px;")
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

# ─────────────────────────────────────────────────────────────
# 🎵 CARÁTULA REAL DE WINDOWS MEDIA (SMTC)
# Requiere: pip install winsdk
# Esto lee la sesión activa de reproducción (Spotify, YouTube en
# el navegador, apps nativas, etc.) usando la misma API que usa
# el propio "Now Playing" de Windows, incluida la carátula.
# ─────────────────────────────────────────────────────────────
def fetch_windows_media_info():
    """
    Devuelve un dict:
    {
        "title": str, "artist": str, "is_playing": bool,
        "position": int (seg), "duration": int (seg),
        "thumb_bytes": bytes | None  (PNG/JPEG crudo, listo para QPixmap)
    }
    o None si no hay sesión activa. Debe llamarse desde un hilo
    aparte (usa asyncio internamente) para no congelar la UI.
    """
    try:
        import asyncio
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager
        )
        from winsdk.windows.storage.streams import DataReader, Buffer, InputStreamOptions

        async def _get():
            mgr = await MediaManager.request_async()
            session = mgr.get_current_session()
            if session is None:
                return None

            info = await session.try_get_media_properties_async()
            timeline = session.get_timeline_properties()
            playback_info = session.get_playback_info()

            title = info.title or ""
            artist = info.artist or ""
            is_playing = (
                playback_info.playback_status
                == playback_info.playback_status.__class__.PLAYING
            )

            pos = int(timeline.position.total_seconds()) if timeline.position else 0
            dur = int(timeline.end_time.total_seconds()) if timeline.end_time else 0

            thumb_bytes = None
            thumb_ref = info.thumbnail
            if thumb_ref is not None:
                stream = await thumb_ref.open_read_async()
                size = stream.size
                if size > 0:
                    buffer = Buffer(size)
                    await stream.read_async(buffer, size, InputStreamOptions.READ_AHEAD)
                    reader = DataReader.from_buffer(buffer)
                    raw = bytearray(size)
                    reader.read_bytes(raw)
                    thumb_bytes = bytes(raw)

            return {
                "title": title,
                "artist": artist,
                "is_playing": is_playing,
                "position": pos,
                "duration": dur,
                "thumb_bytes": thumb_bytes,
            }

        # Cada hilo nuevo necesita su propio event loop para winsdk/asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_get())
        finally:
            loop.close()

    except ImportError:
        print("[WindowsMedia] Falta 'winsdk'. Instala con: pip install winsdk")
        return None
    except Exception as e:
        print(f"[WindowsMedia] Error leyendo sesión: {e}")
        return None


class FloatingMediaWidget(QWidget):
    seek_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MediaFloat")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 150)  # 💎 mismo tamaño que la tarjeta de Spotify
        self.drag_position = None
        self._is_playing = False
        self._dur = 0
        self._current_thumb_hash = None
        self._radius = 26  # 💎 tarjeta redondeada, igual que Spotify (ya no es píldora)
        self._seeking = False
        self._pending_seek_ms = 0

        # ── ESTILO LIQUID GLASS (solo contenido interno; el fondo lo pinta paintEvent) ──
        self.setStyleSheet('''
QLabel {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.90);
}

QPushButton {
    background: transparent;
    border: none;
}

QPushButton:hover {
    background: rgba(255,255,255,0.10);
    border-radius: 15px;
}
''')

        apply_glass_shadow(self, blur_radius=35, y_offset=8, alpha=140)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(10)

        # 🔝 FILA SUPERIOR: carátula + título/artista
        top = QHBoxLayout()
        top.setSpacing(12)

        self.lbl_art = QLabel()
        self.lbl_art.setFixedSize(44, 44)
        self.lbl_art.setStyleSheet("""
        background: rgba(255,255,255,0.10);
        border-radius: 10px;
        """)
        self.lbl_art.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if HAS_QTA:
            self.lbl_art.setPixmap(qta.icon('fa5b.youtube', color='rgba(255,255,255,0.75)').pixmap(20, 20))

        top.addWidget(self.lbl_art)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        self.lbl_track = QLabel("Not Playing")
        self.lbl_track.setStyleSheet("""
        font-size:14px;
        font-weight:700;
        color: rgba(255,255,255,0.95);
        """)

        self.lbl_artist = QLabel("Windows Media")
        self.lbl_artist.setStyleSheet("""
        font-size:11px;
        font-weight:600;
        color: rgba(190,210,255,0.90);
        """)

        info_col.addWidget(self.lbl_track)
        info_col.addWidget(self.lbl_artist)

        top.addLayout(info_col, 1)
        root.addLayout(top)

        # 📊 BARRA DE PROGRESO (interactiva: click + arrastre = seek)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(4)
        self.prog_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prog_bar.setStyleSheet('''
        QProgressBar { background: rgba(255,255,255,0.15); border: none; border-radius: 2px; }
        QProgressBar::chunk { background: rgba(255,255,255,0.85); border-radius: 2px; }
        ''')
        self.prog_bar.mousePressEvent = self._prog_mouse_press
        self.prog_bar.mouseMoveEvent = self._prog_mouse_move
        self.prog_bar.mouseReleaseEvent = self._prog_mouse_release

        root.addWidget(self.prog_bar)

        # ⏱️ TIEMPOS (debajo de la barra, izquierda/derecha)
        time_row = QHBoxLayout()
        self.lbl_time_l = QLabel("0:00")
        self.lbl_time_l.setStyleSheet("font-size:11px; font-weight:600; color: rgba(255,255,255,0.70);")
        self.lbl_time_r = QLabel("0:00")
        self.lbl_time_r.setStyleSheet("font-size:11px; font-weight:600; color: rgba(255,255,255,0.70);")
        time_row.addWidget(self.lbl_time_l)
        time_row.addStretch()
        time_row.addWidget(self.lbl_time_r)
        root.addLayout(time_row)

        # ⏯️ CONTROLES (centrados)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(22)
        ctrl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if HAS_QTA:
            self.btn_prev = QPushButton()
            self.btn_prev.setFixedSize(32, 32)
            self.btn_prev.setIcon(qta.icon('fa5s.step-backward', color='rgba(255,255,255,0.85)'))
            self.btn_prev.setIconSize(QSize(15, 15))

            self.btn_play = QPushButton()
            self.btn_play.setFixedSize(36, 36)
            self.btn_play.setIcon(qta.icon('fa5s.play', color='rgba(255,255,255,0.95)'))
            self.btn_play.setIconSize(QSize(17, 17))

            self.btn_next = QPushButton()
            self.btn_next.setFixedSize(32, 32)
            self.btn_next.setIcon(qta.icon('fa5s.step-forward', color='rgba(255,255,255,0.85)'))
            self.btn_next.setIconSize(QSize(15, 15))

            ctrl.addWidget(self.btn_prev)
            ctrl.addWidget(self.btn_play)
            ctrl.addWidget(self.btn_next)

            self.btn_prev.clicked.connect(lambda: self._press("prevtrack"))
            self.btn_play.clicked.connect(lambda: self._press("playpause"))
            self.btn_next.clicked.connect(lambda: self._press("nexttrack"))

        root.addLayout(ctrl)

        # ⏱️ TIMER: refresca la info de Windows Media (título, artista, carátula...)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_from_windows_media)
        self.timer.start(2000)

        self.hide()
        QTimer.singleShot(100, self.load_position)
        QTimer.singleShot(600, self.refresh_from_windows_media)

    def showEvent(self, event):
        """Blur nativo de Windows — necesita el HWND real, por eso va acá
        y no en __init__ (ahí la ventana todavía no existe a nivel de SO)."""
        super().showEvent(event)
        try:
            apply_acrylic_blur(int(self.winId()), color=(15, 15, 25, 60))
        except Exception:
            pass

    def paintEvent(self, event):
        """Fondo liquid glass REAL: muy transparente, con un leve tinte
        y bordes de luz. Idéntico al de FloatingSpotifyWidget para que
        ambas tarjetas se vean consistentes."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 1) Base MUY transparente (tinte sutil, no tarjeta opaca)
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 35))
        base_gradient.setColorAt(0.5, QColor(200, 210, 230, 22))
        base_gradient.setColorAt(1.0, QColor(160, 170, 200, 30))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)

        # 2) Frost casi imperceptible (solo textura, no opacidad)
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawPath(path)

        # 3) Sombra interior abajo, muy leve, para dar profundidad
        bottom_gradient = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 25))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)

        # 4) Borde de luz (el que realmente vende el efecto "cristal")
        painter.setPen(QPen(QColor(255, 255, 255, 90), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 5) Reflejo superior curvo (sutil)
        shine_rect = QRectF(
            rect.left() + self._radius * 0.6,
            rect.top() + 2,
            rect.width() - self._radius * 1.2,
            self._radius * 0.7
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)

        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 45))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)

        super().paintEvent(event)

    # ── 🎯 SEEK: adelantar/atrasar tocando o arrastrando la barra ──
    def _prog_seek_to(self, x):
        w = self.prog_bar.width()
        if w <= 0 or self._dur <= 0:
            return
        frac = max(0.0, min(1.0, x / w))
        new_sec = int(frac * self._dur)
        self._pending_seek_ms = new_sec

        # Reflejar de inmediato en la UI (feedback visual instantáneo)
        self.prog_bar.setValue(int(frac * 100))
        self.lbl_time_l.setText(f"{new_sec//60}:{new_sec%60:02d}")

    def _prog_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._seeking = True
            self._prog_seek_to(event.position().x())

    def _prog_mouse_move(self, event):
        if self._seeking:
            self._prog_seek_to(event.position().x())

    def _prog_mouse_release(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._seeking:
            self._seeking = False
            self.seek_requested.emit(self._pending_seek_ms)

    # ── 🎵 CARÁTULA REAL: pide la sesión activa de Windows Media en un hilo ──
    def refresh_from_windows_media(self):
        def worker():
            data = fetch_windows_media_info()
            QMetaObject.invokeMethod(
                self, "_on_media_info_ready",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(dict, data if data else {})
            )
        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot(dict)
    def _on_media_info_ready(self, data):
        if not data:
            self.update_info("", "", False, None)
            return
        self.update_info(
            data.get("title", ""),
            data.get("artist", ""),
            data.get("is_playing", False),
            data.get("thumb_bytes"),
        )
        self.update_timeline(data.get("position", 0), data.get("duration", 0))

    # ── MÉTODOS ──
    def update_timeline(self, pos, dur):
        self._dur = dur
        # 🔧 mientras el usuario está arrastrando, no pisamos su valor con el del servidor
        if not self._seeking:
            self.prog_bar.setValue(int(pos / dur * 100) if dur else 0)
            self.lbl_time_l.setText(f"{pos//60}:{pos%60:02d}")
        self.lbl_time_r.setText(f"{dur//60}:{dur%60:02d}")

    def update_info(self, title, artist, is_playing, thumb):
        """thumb: bytes crudos de imagen (PNG/JPEG) o None."""
        if not title:
            self.lbl_track.setText("Not Playing")
            self.lbl_artist.setText("Windows Media")
            self._is_playing = False
            self._current_thumb_hash = None
            if HAS_QTA:
                self.lbl_art.setPixmap(
                    qta.icon('fa5b.youtube', color='rgba(255,255,255,0.75)').pixmap(20, 20)
                )
                self.lbl_art.setStyleSheet("""
                background: rgba(255,255,255,0.10);
                border-radius: 10px;
                """)
            if self.isVisible() and hasattr(self.window(), "animate_hide_widget"):
                self.window().animate_hide_widget(self)
            return

        if not self.isVisible() and hasattr(self.window(), "animate_show_widget"):
            self.window().animate_show_widget(self)

        self._is_playing = is_playing
        self.lbl_track.setText(title[:28] + ("…" if len(title) > 28 else ""))
        self.lbl_artist.setText(artist[:30] + ("…" if len(artist) > 30 else ""))

        if HAS_QTA:
            icon_name = 'fa5s.pause' if is_playing else 'fa5s.play'
            self.btn_play.setIcon(qta.icon(icon_name, color='rgba(255,255,255,0.95)'))

        if thumb:
            thumb_hash = hash(thumb)
            if thumb_hash != self._current_thumb_hash:
                self._current_thumb_hash = thumb_hash
                try:
                    pix = QPixmap()
                    pix.loadFromData(thumb)
                    if not pix.isNull():
                        pix = pix.scaled(
                            44, 44,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.lbl_art.setPixmap(pix)
                        self.lbl_art.setStyleSheet("border-radius:10px;")
                except Exception as e:
                    print(f"[MediaWidget] Error pintando carátula: {e}")

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
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

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
        self.setFixedHeight(52)  # Un poco más compacto
        self._radius = 26  # 💎 mitad de la altura -> píldora perfecta
        self._glow_active = False  # 🔧 controla el color del borde en paintEvent

        # ─── Solo estilos de contenido interno (el fondo lo pinta paintEvent) ───
        self.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.90);
                font-size: 14px;
                padding: 0 4px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.35);
                font-weight: 400;
            }
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(168, 85, 247, 0.20),
                    stop:1 rgba(139, 92, 246, 0.10)
                );
                border: 1px solid rgba(168, 85, 247, 0.25);
                border-radius: 19px;
                color: rgba(255, 255, 255, 0.80);
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(168, 85, 247, 0.35),
                    stop:1 rgba(139, 92, 246, 0.20)
                );
                border: 1px solid rgba(168, 85, 247, 0.45);
            }
            QPushButton:pressed {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(168, 85, 247, 0.50),
                    stop:1 rgba(139, 92, 246, 0.30)
                );
            }
        """)
        
        # ─── SOMBRA LIQUID GLASS ───
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)
        
        # Layout principal
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 4, 8, 4)  # 🔧 un poco más de margen izquierdo para la píldora
        layout.setSpacing(8)
        
        # ─── INPUT ───
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Escribe un mensaje…")
        self.inp.setFont(QFont(FONT_FAMILY, 13))
        self.inp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.inp.returnPressed.connect(self._submit)
        self.inp.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.90);
                font-size: 13px;
                padding: 8px 4px;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.35);
            }
        """)
        layout.addWidget(self.inp)
        
        # ─── BOTÓN ENVIAR ───
        self.btn_send = QPushButton()
        self.btn_send.setFixedSize(40, 40)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if HAS_QTA:
            self.btn_send.setIcon(qta.icon('fa5s.paper-plane', color='rgba(255,255,255,0.70)'))
            self.btn_send.setIconSize(QSize(18, 18))
        
        self.btn_send.clicked.connect(self._submit)
        layout.addWidget(self.btn_send)
        
        # Efecto de brillo en el borde (opcional)
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._update_glow)
        self._glow_timer.start(2000)
        self._glow_state = 0
        
        self.hide()

    def paintEvent(self, event):
        """Dibuja el fondo liquid glass en forma de píldora: translúcido
        de verdad (baja opacidad) + capa de frost + reflejo curvo arriba + borde con glow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 1) Base translúcida (baja opacidad -> se ve lo de atrás)
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        base_gradient.setColorAt(0.5, QColor(255, 255, 255, 20))
        base_gradient.setColorAt(1.0, QColor(0, 0, 0, 35))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)

        # 2) Capa "frost" (blanco muy tenue, uniforme) para simular esmerilado
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.drawPath(path)

        # 3) Sombra interior sutil abajo (da profundidad, sigue siendo transparente)
        bottom_gradient = QLinearGradient(0, self.height() * 0.55, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 30))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)

        # 4) Borde de luz (filo del cristal) -> cambia de color si el glow está activo
        if self._glow_active:
            border_color = QColor(168, 85, 247, 130)  # morado pulsante
        else:
            border_color = QColor(255, 255, 255, 90)  # blanco normal

        painter.setPen(QPen(border_color, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 5) Reflejo superior curvo (la parte más brillante del cristal)
        shine_rect = QRectF(
            rect.left() + self._radius * 0.4,
            rect.top() + 2,
            rect.width() - self._radius * 0.8,
            self._radius * 0.55
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)

        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 50))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)

        super().paintEvent(event)
    
    def _update_glow(self):
        """Efecto de brillo pulsante en el borde (ahora vía paintEvent, no vía QSS)."""
        self._glow_state = (self._glow_state + 1) % 4
        if self._glow_state == 0:
            self._glow_active = True
        elif self._glow_state == 2:
            self._glow_active = False
        self.update()  # 🔧 fuerza el repintado con el nuevo color de borde

    def _submit(self):
        text = self.inp.text().strip()
        if text:
            self.submitted.emit(text)
            self.inp.clear()
            # Pequeña animación al enviar
            self.btn_send.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(53, 212, 147, 0.30),
                        stop:1 rgba(53, 212, 147, 0.15)
                    );
                    border: 1px solid rgba(53, 212, 147, 0.35);
                    border-radius: 19px;
                }
            """)
            QTimer.singleShot(300, lambda: self.btn_send.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(168, 85, 247, 0.20),
                        stop:1 rgba(139, 92, 246, 0.10)
                    );
                    border: 1px solid rgba(168, 85, 247, 0.25);
                    border-radius: 19px;
                }
            """))

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.inp.setFocus()
            self.inp.selectAll()
    
    def showEvent(self, event):
        """Cuando se muestra, enfocar el input."""
        super().showEvent(event)
        self.inp.setFocus()
    
    def keyPressEvent(self, event):
        """Cerrar con Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class HUDCalendarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CalendarPop")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(260, 230)  # Un poco más grande para mejor legibilidad
        self._radius = 30  # 💎 tarjeta redondeada (no píldora, porque el widget es casi cuadrado)

        # ─── Solo estilos de contenido interno (el fondo lo pinta paintEvent) ───
        self.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                color: rgba(230, 230, 240, 0.95);
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
        """)

        # ─── SOMBRA LIQUID GLASS ───
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 10)
        self.setGraphicsEffect(shadow)
        
        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        
        # Fecha actual
        now = datetime.now()
        
        # ─── HEADER con mes y año ───
        header = QHBoxLayout()
        header.setSpacing(10)
        
        # Flecha izquierda
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(28, 28)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(200,200,210,0.6);
                border: 1px solid rgba(255,255,255,0.06);
                font-size: 12px;
                font-weight: bold;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.10);
                color: #ffffff;
                border-color: rgba(255,255,255,0.15);
            }
        """)
        self.btn_prev.clicked.connect(self._prev_month)
        header.addWidget(self.btn_prev)
        
        # Mes y año
        self.month_lbl = QLabel(now.strftime("%B %Y").upper())
        self.month_lbl.setStyleSheet("""
            font-size:13px;
            font-weight:700;
            letter-spacing:2px;
            color: rgba(255,255,255,0.90);
        """)
        self.month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.month_lbl, 1)
        
        # Flecha derecha
        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(28, 28)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: rgba(200,200,210,0.6);
                border: 1px solid rgba(255,255,255,0.06);
                font-size: 12px;
                font-weight: bold;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.10);
                color: #ffffff;
                border-color: rgba(255,255,255,0.15);
            }
        """)
        self.btn_next.clicked.connect(self._next_month)
        header.addWidget(self.btn_next)
        
        layout.addLayout(header)
        
        # ─── DÍAS DE LA SEMANA ───
        days_hdr = QHBoxLayout()
        days_hdr.setSpacing(4)
        for d in ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]:
            l = QLabel(d)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setStyleSheet("""
                font-size:9px;
                color:rgba(180,180,200,0.50);
                font-weight:700;
                letter-spacing:0.8px;
            """)
            l.setFixedSize(28, 18)
            days_hdr.addWidget(l)
        layout.addLayout(days_hdr)
        
        # ─── DÍAS DEL MES ───
        self.days_layout = QVBoxLayout()
        self.days_layout.setSpacing(4)
        layout.addLayout(self.days_layout)
        
        # Guardar año y mes actual
        self._year = now.year
        self._month = now.month
        self._today = now.day
        
        # Generar días
        self._update_calendar()
        
        self.hide()

    def paintEvent(self, event):
        """Dibuja el fondo liquid glass en forma de tarjeta redondeada: translúcido
        de verdad (baja opacidad) + capa de frost + reflejo curvo arriba."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 1) Base translúcida (baja opacidad -> se ve lo de atrás)
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        base_gradient.setColorAt(0.5, QColor(255, 255, 255, 20))
        base_gradient.setColorAt(1.0, QColor(0, 0, 0, 35))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)

        # 2) Capa "frost" (blanco muy tenue, uniforme) para simular esmerilado
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.drawPath(path)

        # 3) Sombra interior sutil abajo (da profundidad, sigue siendo transparente)
        bottom_gradient = QLinearGradient(0, self.height() * 0.55, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 30))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)

        # 4) Borde de luz (filo del cristal)
        painter.setPen(QPen(QColor(255, 255, 255, 90), 1.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 5) Reflejo superior curvo (la parte más brillante del cristal)
        shine_rect = QRectF(
            rect.left() + self._radius * 0.5,
            rect.top() + 3,
            rect.width() - self._radius,
            self._radius * 0.9
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)

        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 50))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)

        super().paintEvent(event)
    
    def _update_calendar(self):
        """Actualiza el calendario con el mes actual."""
        import calendar
        
        # Limpiar días existentes
        while self.days_layout.count():
            item = self.days_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            if item.widget():
                item.widget().deleteLater()
        
        # Generar nuevo calendario
        cal = calendar.monthcalendar(self._year, self._month)
        
        for week in cal:
            row = QHBoxLayout()
            row.setSpacing(4)
            
            for day in week:
                if day == 0:
                    l = QLabel("")
                    l.setFixedSize(28, 26)
                else:
                    l = QLabel(str(day))
                    l.setFixedSize(28, 26)
                    l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    # Verificar si es hoy
                    is_today = (day == self._today and 
                               self._year == datetime.now().year and 
                               self._month == datetime.now().month)
                    
                    # Verificar si es fin de semana (sábado o domingo)
                    # Calcular día de la semana para este día
                    day_of_week = datetime(self._year, self._month, day).weekday()
                    is_weekend = day_of_week >= 5  # 5=sábado, 6=domingo
                    
                    if is_today:
                        # Día actual - destacado con morado
                        l.setStyleSheet("""
                            background: qlineargradient(
                                x1:0, y1:0, x2:1, y2:1,
                                stop:0 rgba(168,85,247,0.55),
                                stop:1 rgba(139,92,246,0.35)
                            );
                            border: 1px solid rgba(168,85,247,0.30);
                            border-radius: 13px;
                            font-size:11px;
                            font-weight:800;
                            color: #ffffff;
                        """)
                    elif is_weekend:
                        # Fin de semana - color más suave
                        l.setStyleSheet("""
                            font-size:10px;
                            font-weight:500;
                            color: rgba(200,200,220,0.45);
                            border-radius: 13px;
                        """)
                        # Hover effect para fines de semana
                        l.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
                        l.enterEvent = lambda e, w=l: w.setStyleSheet("""
                            font-size:10px;
                            font-weight:500;
                            color: rgba(255,255,255,0.70);
                            background: rgba(255,255,255,0.04);
                            border-radius: 13px;
                        """)
                        l.leaveEvent = lambda e, w=l: w.setStyleSheet("""
                            font-size:10px;
                            font-weight:500;
                            color: rgba(200,200,220,0.45);
                            border-radius: 13px;
                        """)
                    else:
                        # Días normales
                        l.setStyleSheet("""
                            font-size:10px;
                            font-weight:500;
                            color: rgba(220,220,230,0.80);
                            border-radius: 13px;
                        """)
                        # Hover effect para días normales
                        l.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
                        l.enterEvent = lambda e, w=l: w.setStyleSheet("""
                            font-size:10px;
                            font-weight:600;
                            color: rgba(255,255,255,0.95);
                            background: rgba(255,255,255,0.08);
                            border-radius: 13px;
                        """)
                        l.leaveEvent = lambda e, w=l: w.setStyleSheet("""
                            font-size:10px;
                            font-weight:500;
                            color: rgba(220,220,230,0.80);
                            border-radius: 13px;
                        """)
                
                row.addWidget(l)
            
            self.days_layout.addLayout(row)
        
        # Actualizar título del mes en español
        month_names = {
            1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
            5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
            9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
        }
        self.month_lbl.setText(f"{month_names.get(self._month, '')} {self._year}")
    
    def _prev_month(self):
        """Va al mes anterior."""
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._update_calendar()
    
    def _next_month(self):
        """Va al mes siguiente."""
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._update_calendar()
    
    def showEvent(self, event):
        """Cuando se muestra, actualizar al mes actual."""
        now = datetime.now()
        self._year = now.year
        self._month = now.month
        self._today = now.day
        self._update_calendar()
        super().showEvent(event)

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
            play_sound("click")

    def __post_init__(self):
        self.lst_todo.itemChanged.connect(self._on_task_toggled)

    def _on_task_toggled(self, item):
        if item.checkState() == Qt.CheckState.Checked:
            play_sound("notification")  # ✅ Al completar tarea


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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 💎 fondo real transparente
        self._drag_offset = None
        self._radius = 20  # 💎 mismo radio que tenías en el QSS

        # 💎 Solo estilos de contenido interno (el fondo lo pinta paintEvent)
        self.setStyleSheet("""
        QLabel { background: transparent; border: none; }
        """)

        apply_glass_shadow(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        header = QHBoxLayout()
        lbl_icon = QLabel()
        if HAS_QTA:
            lbl_icon.setPixmap(qta.icon('fa5s.sticky-note', color=C_PRI).pixmap(18, 18))
        header.addWidget(lbl_icon)

        self.lbl_title = QLabel("PAD NOTES")
        self.lbl_title.setStyleSheet(
            f"font-weight: bold; font-size: 11px; letter-spacing: 2px; "
            f"color: {C_PRI}; border: none; background: transparent;"
        )
        header.addWidget(self.lbl_title)
        header.addStretch()
        layout.addLayout(header)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Write details...")
        self.txt_notes.setStyleSheet("""
        QTextEdit {
            border: none;
            background: rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 6px;
            color: white;
        }
        """)
        layout.addWidget(self.txt_notes)

    def showEvent(self, event):
        """Blur nativo de Windows: hay que aplicarlo aquí porque necesita
        el HWND real, que solo existe una vez que la ventana ya se mostró."""
        super().showEvent(event)
        try:
            apply_acrylic_blur(int(self.winId()), color=(15, 15, 25, 60))
        except Exception:
            pass

    def paintEvent(self, event):
        """Fondo liquid glass: tinte sutil + frost + sombra interior +
        borde de luz + reflejo superior curvo, todo dentro de un
        rounded-rect (evita las esquinas cuadradas del QSS anterior)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 1) Base transparente con tinte
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 30))
        base_gradient.setColorAt(0.5, QColor(200, 210, 230, 18))
        base_gradient.setColorAt(1.0, QColor(160, 170, 200, 26))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)

        # 2) Frost sutil
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawPath(path)

        # 3) Sombra interior abajo
        bottom_gradient = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 25))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)

        # 4) Borde de luz
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 5) Reflejo superior curvo
        shine_rect = QRectF(
            rect.left() + self._radius * 0.6,
            rect.top() + 2,
            rect.width() - self._radius * 1.2,
            self._radius * 0.7
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)

        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)

        super().paintEvent(event)

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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 💎 fondo real transparente
        self._drag_offset = None
        self._radius = 20  # 💎 mismo radio que NotesWidget

        # 💎 Solo estilos de contenido interno (el fondo lo pinta paintEvent)
        self.setStyleSheet("""
        QLabel { background: transparent; border: none; }
        QPushButton { background: transparent; border: none; }
        """)

        apply_glass_shadow(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        header = QHBoxLayout()
        lbl_icon = QLabel()
        if HAS_QTA:
            lbl_icon.setPixmap(qta.icon('fa5s.keyboard', color=C_PRI).pixmap(18, 18))
        header.addWidget(lbl_icon)

        self.lbl_title = QLabel("MACROS GUARDADOS")
        self.lbl_title.setStyleSheet(
            f"font-weight: bold; font-size: 11px; letter-spacing: 2px; "
            f"color: {C_PRI}; border: none; background: transparent;"
        )
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
        self.list_macros.setStyleSheet(f"""
            QListWidget {{
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                color: {C_TEXT};
                font-size: 11px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-radius: 8px;
            }}
            QListWidget::item:selected {{
                background: rgba(245, 158, 11, 0.15);
                border: 1px solid rgba(245, 158, 11, 0.2);
            }}
            QListWidget::item:hover {{
                background: rgba(255,255,255,0.05);
            }}
        """)
        self.list_macros.itemDoubleClicked.connect(self.execute_macro)
        layout.addWidget(self.list_macros)

        self.load_macros()

    def showEvent(self, event):
        """Blur nativo de Windows: hay que aplicarlo aquí porque necesita
        el HWND real, que solo existe una vez que la ventana ya se mostró."""
        super().showEvent(event)
        try:
            apply_acrylic_blur(int(self.winId()), color=(15, 15, 25, 60))
        except Exception:
            pass

    def paintEvent(self, event):
        """Fondo liquid glass: tinte sutil + frost + sombra interior +
        borde de luz + reflejo superior curvo, todo dentro de un
        rounded-rect (evita las esquinas cuadradas del QSS anterior)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 1) Base transparente con tinte
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 30))
        base_gradient.setColorAt(0.5, QColor(200, 210, 230, 18))
        base_gradient.setColorAt(1.0, QColor(160, 170, 200, 26))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)

        # 2) Frost sutil
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawPath(path)

        # 3) Sombra interior abajo
        bottom_gradient = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 25))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)

        # 4) Borde de luz
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 5) Reflejo superior curvo
        shine_rect = QRectF(
            rect.left() + self._radius * 0.6,
            rect.top() + 2,
            rect.width() - self._radius * 1.2,
            self._radius * 0.7
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)

        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)

        super().paintEvent(event)

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



class StarOverlayWidget(QWidget):
    def __init__(self, parent=None, variant: str = "estrellas"):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

        self.variant = variant if variant in STAR_VARIANTS else "estrellas"
        self.stars = []
        self.max_stars = 45
        self._init_stars()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stars)

    def set_variant(self, variant: str):
        """Cambia la variante activa y reinicia las partículas."""
        if variant not in STAR_VARIANTS:
            variant = "estrellas"
        if variant == self.variant:
            return
        self.variant = variant
        self._init_stars()
        self.update()

    def _init_stars(self):
        import random
        cfg = STAR_VARIANTS[self.variant]
        motion = cfg["motion"]
        is_square = cfg["shape"] == "square"
        self.stars = []
        for _ in range(self.max_stars):
            star = {
                'x': random.uniform(0, 1920),
                'y': random.uniform(0, 1080),
                'size': random.uniform(3.0, 7.0) if is_square else random.uniform(1.8, 4.5),
                'opacity': random.uniform(0.1, 0.9),
                'pulse': random.uniform(0.015, 0.04),
                'pulse_dir': random.choice([1, -1]),
                'color': random.choice(cfg["colors"]),
                'angle': random.uniform(0, 360),
            }
            if motion == "up":
                star['speed_y'] = random.uniform(-0.5, -2.0)
                star['speed_x'] = random.uniform(-0.4, 0.4)
            elif motion == "down":
                star['speed_y'] = random.uniform(0.4, 1.6)
                star['speed_x'] = random.uniform(-0.3, 0.3)
                star['spin'] = random.uniform(-3.0, 3.0)
            elif motion == "wander":
                star['speed_y'] = random.uniform(-0.3, 0.3)
                star['speed_x'] = random.uniform(-0.3, 0.3)
                star['wander_timer'] = random.uniform(0, 60)
            self.stars.append(star)

    def update_stars(self):
        if not self.isVisible():
            return
        import random
        w = self.width()
        h = self.height()
        motion = STAR_VARIANTS[self.variant]["motion"]

        for star in self.stars:
            if motion == "wander":
                star['wander_timer'] -= 1
                if star['wander_timer'] <= 0:
                    star['speed_x'] = random.uniform(-0.5, 0.5)
                    star['speed_y'] = random.uniform(-0.5, 0.5)
                    star['wander_timer'] = random.uniform(40, 120)

            star['x'] += star['speed_x']
            star['y'] += star['speed_y']
            if 'spin' in star:
                star['angle'] = (star['angle'] + star['spin']) % 360

            star['opacity'] += star['pulse'] * star['pulse_dir']
            if star['opacity'] > 1.0:
                star['opacity'] = 1.0
                star['pulse_dir'] = -1
            elif star['opacity'] < 0.1:
                star['opacity'] = 0.1
                star['pulse_dir'] = 1

            if motion == "up" and (star['y'] < -15 or star['x'] < -15 or star['x'] > w + 15):
                star['y'] = h + 15
                star['x'] = random.uniform(0, w)
            elif motion == "down" and (star['y'] > h + 15 or star['x'] < -15 or star['x'] > w + 15):
                star['y'] = -15
                star['x'] = random.uniform(0, w)
            elif motion == "wander":
                if star['x'] < -15: star['x'] = w + 15
                if star['x'] > w + 15: star['x'] = -15
                if star['y'] < -15: star['y'] = h + 15
                if star['y'] > h + 15: star['y'] = -15

        self.update()

    def showEvent(self, event):
        if hasattr(self, 'timer') and self.timer:
            self.timer.start(33)
        super().showEvent(event)

    def hideEvent(self, event):
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        shape = STAR_VARIANTS[self.variant]["shape"]

        for star in self.stars:
            r, g, b = star['color']
            base_opacity = int(star['opacity'] * 255)
            s = star['size']

            if shape == "glow":
                glow_opacity = int(base_opacity * 0.35)
                painter.setBrush(QColor(r, g, b, int(glow_opacity * 0.3)))
                painter.drawEllipse(int(star['x'] - s * 1.5), int(star['y'] - s * 1.5), int(s * 4), int(s * 4))
                painter.setBrush(QColor(r, g, b, glow_opacity))
                painter.drawEllipse(int(star['x'] - s * 0.5), int(star['y'] - s * 0.5), int(s * 2), int(s * 2))
                painter.setBrush(QColor(r, g, b, base_opacity))
                painter.drawEllipse(int(star['x']), int(star['y']), int(s), int(s))

            elif shape == "soft":
                painter.setBrush(QColor(r, g, b, int(base_opacity * 0.4)))
                painter.drawEllipse(int(star['x'] - s), int(star['y'] - s), int(s * 3), int(s * 3))
                painter.setBrush(QColor(r, g, b, base_opacity))
                painter.drawEllipse(int(star['x']), int(star['y']), int(s), int(s))

            elif shape == "ring":
                pen = QPen(QColor(r, g, b, base_opacity))
                pen.setWidthF(1.2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(int(star['x']), int(star['y']), int(s * 2), int(s * 2))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, int(base_opacity * 0.5)))
                painter.drawEllipse(int(star['x'] + s * 0.4), int(star['y'] + s * 0.3), int(s * 0.5), int(s * 0.5))

            elif shape == "square":
                painter.save()
                painter.translate(star['x'], star['y'])
                painter.rotate(star.get('angle', 0))
                painter.setBrush(QColor(r, g, b, base_opacity))
                painter.drawRect(int(-s / 2), int(-s / 2), int(s), int(s))
                painter.restore()

class WeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WeatherWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 💎 fondo real transparente
        self.setFixedSize(250, 130)
        self._drag_offset = None
        self._radius = 18  # 💎 mismo radio que tenía antes

        # 💎 Solo estilos de contenido interno (el fondo lo pinta paintEvent)
        self.setStyleSheet("""
        QLabel {
            background: transparent;
            border: none;
        }
        """)

        apply_glass_shadow(self, blur_radius=18, y_offset=4, alpha=120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.lbl_city = QLabel("🌐 Detectando…")
        self.lbl_city.setStyleSheet("font-size:12px; font-weight:700; color:white;")

        self.lbl_temp = QLabel("--°C")
        self.lbl_temp.setStyleSheet(f"font-size:28px; font-weight:800; color:{C_PRI};")

        self.lbl_desc = QLabel("Cargando clima...")
        self.lbl_desc.setStyleSheet("font-size:10px; color:rgba(220,220,230,0.75);")

        self.lbl_extra = QLabel("--")
        self.lbl_extra.setStyleSheet("font-size:9px; color:rgba(220,220,230,0.60);")

        layout.addWidget(self.lbl_city)
        layout.addWidget(self.lbl_temp)
        layout.addWidget(self.lbl_desc)
        layout.addWidget(self.lbl_extra)

        # Coordenadas por defecto (fallback si falla la detección)
        self._lat = 6.2442
        self._lon = -75.5812
        self._city_name = "Medellín"

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_weather)
        self.timer.start(1800000)  # cada 30 min

        # 1) Primero detecta ubicación, 2) luego pide el clima
        QTimer.singleShot(500, self.detect_location_and_update)

    def showEvent(self, event):
        """Blur nativo de Windows: hay que aplicarlo aquí porque necesita
        el HWND real, que solo existe una vez que la ventana ya se mostró."""
        super().showEvent(event)
        try:
            apply_acrylic_blur(int(self.winId()), color=(15, 15, 25, 60))
        except Exception:
            pass

    def paintEvent(self, event):
        """Fondo liquid glass: tinte sutil + frost + sombra interior +
        borde de luz + reflejo superior curvo, todo dentro de un
        rounded-rect (evita las esquinas cuadradas del QSS anterior)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 1) Base transparente con tinte
        base_gradient = QLinearGradient(0, 0, 0, self.height())
        base_gradient.setColorAt(0.0, QColor(255, 255, 255, 30))
        base_gradient.setColorAt(0.5, QColor(200, 210, 230, 18))
        base_gradient.setColorAt(1.0, QColor(160, 170, 200, 26))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_gradient)
        painter.drawPath(path)

        # 2) Frost sutil
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawPath(path)

        # 3) Sombra interior abajo
        bottom_gradient = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 25))
        painter.setBrush(bottom_gradient)
        painter.drawPath(path)

        # 4) Borde de luz
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 5) Reflejo superior curvo
        shine_rect = QRectF(
            rect.left() + self._radius * 0.6,
            rect.top() + 2,
            rect.width() - self._radius * 1.2,
            self._radius * 0.7
        )
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, shine_rect.height() / 2, shine_rect.height() / 2)

        shine_gradient = QLinearGradient(0, shine_rect.top(), 0, shine_rect.bottom())
        shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine_gradient)
        painter.drawPath(shine_path)

        super().paintEvent(event)

    # ---------------- DRAG SYSTEM ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
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

    # ---------------- DETECCIÓN DE UBICACIÓN ----------------
    def detect_location_and_update(self):
        """
        Intenta usar una ubicación guardada por el usuario (manual).
        Si no hay, detecta la ubicación por IP automáticamente.
        """
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()

            # Si el usuario configuró manualmente su ciudad, usar esa
            manual_lat = cfg.get("weather_lat")
            manual_lon = cfg.get("weather_lon")
            manual_city = cfg.get("weather_city")

            if manual_lat and manual_lon:
                self._lat = float(manual_lat)
                self._lon = float(manual_lon)
                self._city_name = manual_city or "Mi ubicación"
                self.update_weather()
                return
        except Exception:
            pass

        try:
            url = "http://ip-api.com/json/?fields=status,country,city,lat,lon"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

            if data.get("status") == "success":
                self._lat = data["lat"]
                self._lon = data["lon"]
                self._city_name = data.get("city", "Mi ubicación")
        except Exception as e:
            print(f"[WeatherWidget] No se pudo detectar ubicación: {e}")
            # Se queda con el fallback (Medellín)

        self.update_weather()

    # ---------------- WEATHER LOGIC ----------------
    def weather_icon(self, code: int):
        if code == 0: return "☀️"
        if code in [1, 2]: return "🌤"
        if code == 3: return "☁️"
        if code in [45, 48]: return "🌫"
        if code in [51, 53, 55, 56, 57]: return "🌦"
        if code in [61, 63, 65, 66, 67, 80, 81, 82]: return "🌧"
        if code in [71, 73, 75]: return "❄️"
        if code in [95, 96, 99]: return "⛈"
        return "🌤"

    def weather_text(self, code: int):
        mapping = {
            0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
            3: "Nublado", 45: "Neblina", 48: "Neblina", 51: "Llovizna ligera",
            53: "Llovizna", 55: "Llovizna fuerte", 61: "Lluvia ligera", 63: "Lluvia",
            65: "Lluvia intensa", 71: "Nieve ligera", 73: "Nieve", 75: "Nieve intensa",
            80: "Chubascos", 81: "Chubascos fuertes", 82: "Tormenta de lluvia",
            95: "Tormenta eléctrica"
        }
        return mapping.get(code, "Clima desconocido")

    def update_weather(self):
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={self._lat}"
                f"&longitude={self._lon}"
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

            self.lbl_city.setText(f"{icon} {self._city_name}")
            self.lbl_temp.setText(f"{round(temp)}°C")
            self.lbl_desc.setText(self.weather_text(code))
            self.lbl_extra.setText(
                f"Sensación {round(feels)}°C   •   "
                f"Humedad {humidity}%   •   "
                f"Viento {round(wind)} km/h"
                
            )
            play_sound("success")

        except Exception as e:
            self.lbl_temp.setText("--°C")
            self.lbl_desc.setText("Sin conexión")
            self.lbl_extra.setText(str(e)[:60])
            play_sound("error") 

# ═══════════════════════════════════════════════════════════════════════════
#  STAR VARIANTS DICTIONARY - AÑADIR AQUÍ
# ═══════════════════════════════════════════════════════════════════════════

STAR_VARIANTS = {
    "estrellas": {
        "label": "✨ Estrellas Clásicas",
        "colors": [(255, 215, 0), (0, 255, 255), (255, 105, 180), (180, 200, 255), (255, 255, 255)],
        "motion": "up",
        "shape": "glow",
    },
    "nieve": {
        "label": "❄️ Nieve",
        "colors": [(255, 255, 255), (225, 235, 255), (200, 220, 255)],
        "motion": "down",
        "shape": "soft",
    },
    "burbujas": {
        "label": "🫧 Burbujas",
        "colors": [(150, 220, 255), (200, 240, 255), (255, 255, 255)],
        "motion": "up",
        "shape": "ring",
    },
    "luciernagas": {
        "label": "🌟 Luciérnagas",
        "colors": [(180, 255, 120), (255, 240, 150), (255, 200, 100)],
        "motion": "wander",
        "shape": "glow",
    },
    "confeti": {
        "label": "🎉 Confeti",
        "colors": [(255, 90, 90), (90, 200, 255), (255, 215, 0), (190, 120, 255), (120, 255, 170)],
        "motion": "down",
        "shape": "square",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  Dialogs: NexusMessageBox, LogsDialog, NexusColorPicker
# ═══════════════════════════════════════════════════════════════════════════

class NexusMessageBox(QDialog):
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
        self.setWindowTitle("NEXUS Logs"); self.setFixedSize(750, 500)
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
        self.lbl_title = QLabel("NEXUS TELEMETRÍA Y LOGS")
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
            log_file = BASE_DIR / "nexus.log"
            if not log_file.exists(): log_file = Path("nexus.log")
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    self.raw_log_lines = f.readlines()
            else: self.raw_log_lines = ["No se encontró 'nexus.log'."]
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
            elif "nexus:" in line.lower(): c, fw = "#00ff88", "normal"
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


class NexusColorPicker(QDialog):
    def __init__(self, parent=None, initial_color=None):
        super().__init__(parent)
        self.setWindowTitle("NEXUS Color Picker"); self.resize(380, 490)
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


# ─── SMART HOME WIDGET ──────────────────────────────────────────────────────
class SmartHomeWidget(QWidget):
    """Widget flotante para controlar dispositivos inteligentes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SmartHomeWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(390, 470)
        self._drag_offset = None

        # ─── ESTILO LIQUID GLASS PREMIUM ────────────
        self.setStyleSheet("""
            QWidget#SmartHomeWidget {
                background: rgba(18, 18, 22, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 24px;
            }
            QLabel {
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.85);
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.78);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 12px;
                font-weight: 700;
                font-size: 11px;
                letter-spacing: 0.5px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background: rgba(168, 85, 247, 0.10);
                color: rgba(255, 255, 255, 0.95);
                border-color: rgba(168, 85, 247, 0.30);
            }
            QPushButton:pressed {
                background: rgba(168, 85, 247, 0.18);
            }
            QPushButton#btn_on {
                background: rgba(16, 220, 140, 0.10);
                border-color: rgba(16, 220, 140, 0.28);
                color: rgba(60, 240, 170, 0.95);
            }
            QPushButton#btn_on:hover {
                background: rgba(16, 220, 140, 0.20);
                border-color: rgba(16, 220, 140, 0.45);
            }
            QPushButton#btn_off {
                background: rgba(255, 69, 58, 0.10);
                border-color: rgba(255, 69, 58, 0.28);
                color: rgba(255, 110, 100, 0.95);
            }
            QPushButton#btn_off:hover {
                background: rgba(255, 69, 58, 0.20);
                border-color: rgba(255, 69, 58, 0.45);
            }
            QPushButton#btn_toggle {
                background: rgba(251, 191, 36, 0.10);
                border-color: rgba(251, 191, 36, 0.28);
                color: rgba(251, 191, 36, 0.95);
            }
            QPushButton#btn_toggle:hover {
                background: rgba(251, 191, 36, 0.20);
                border-color: rgba(251, 191, 36, 0.45);
            }
            QPushButton#btn_close {
                background: rgba(255, 69, 58, 0.08);
                color: rgba(255, 110, 100, 0.55);
                border: 1px solid rgba(255, 69, 58, 0.16);
                border-radius: 15px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#btn_close:hover {
                background: rgba(255, 69, 58, 0.18);
                color: rgba(255, 110, 100, 0.95);
                border-color: rgba(255, 69, 58, 0.35);
            }
            QListWidget {
                background: rgba(0, 0, 0, 0.32);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 14px;
                color: rgba(255, 255, 255, 0.85);
                padding: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 9px 10px;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background: rgba(168, 85, 247, 0.18);
                border: 1px solid rgba(168, 85, 247, 0.30);
                color: rgba(255, 255, 255, 0.95);
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QProgressBar {
                background: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 4px;
                height: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(168, 85, 247, 0.85),
                    stop:1 rgba(251, 191, 36, 0.85)
                );
                border-radius: 4px;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255, 255, 255, 0.02);
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.12);
                min-height: 30px;
                border-radius: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # ─── SOMBRA GLASS ──────────────────────────────────────────────────
        apply_glass_shadow(self, blur_radius=40, y_offset=10, alpha=180)

        # ─── LAYOUT ──────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        # ─── HEADER ──────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)

        self.lbl_icon = QLabel()
        if HAS_QTA:
            self.lbl_icon.setPixmap(qta.icon('fa5s.home', color='#fbbf24').pixmap(20, 20))
        header.addWidget(self.lbl_icon)

        self.lbl_title = QLabel("SMART HOME")
        self.lbl_title.setStyleSheet("""
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 3px;
            color: rgba(255, 255, 255, 0.92);
        """)
        header.addWidget(self.lbl_title)
        header.addStretch()

        self.btn_close = QPushButton()
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(30, 30)
        if HAS_QTA:
            self.btn_close.setIcon(qta.icon('fa5s.times', color='#ff6e64'))
        else:
            self.btn_close.setText("×")
        self.btn_close.clicked.connect(self.hide)
        header.addWidget(self.btn_close)

        layout.addLayout(header)

        # ─── BOTONES DE ACCIÓN RÁPIDA ──────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btn_scan = QPushButton("  ESCANEAR")
        self.btn_scan.setFixedHeight(38)
        if HAS_QTA:
            self.btn_scan.setIcon(qta.icon('fa5s.search', color='#c9a8f7'))
        self.btn_scan.clicked.connect(self._scan_devices)
        action_row.addWidget(self.btn_scan)

        self.btn_refresh = QPushButton("  ACTUALIZAR")
        self.btn_refresh.setFixedHeight(38)
        if HAS_QTA:
            self.btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color='#c9a8f7'))
        self.btn_refresh.clicked.connect(self._refresh_list)
        action_row.addWidget(self.btn_refresh)

        self.btn_setup = QPushButton("  CONFIGURAR")
        self.btn_setup.setFixedHeight(38)
        if HAS_QTA:
            self.btn_setup.setIcon(qta.icon('fa5s.cog', color='#fbbf24'))
        self.btn_setup.clicked.connect(self._open_setup)
        action_row.addWidget(self.btn_setup)

        layout.addLayout(action_row)

        # ─── ESTADO ──────────────────────────────────────────────────────
        self.lbl_status = QLabel("Cargando dispositivos...")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("""
            color: rgba(255,255,255,0.45);
            font-size: 11px;
            font-weight: 600;
        """)
        layout.addWidget(self.lbl_status)

        # ─── LISTA DE DISPOSITIVOS ──────────────────────────────────────
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(200)
        self.device_list.setIconSize(QSize(16, 16))
        self.device_list.itemDoubleClicked.connect(self._on_device_double_click)
        layout.addWidget(self.device_list)

        # ─── CONTROLES DE DISPOSITIVO SELECCIONADO ──────────────────────
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(251, 191, 36, 0.10);
                border-radius: 14px;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(14, 10, 14, 10)
        control_layout.setSpacing(8)

        self.lbl_selected = QLabel("Selecciona un dispositivo")
        self.lbl_selected.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: rgba(255,255,255,0.45);
        """)
        control_layout.addWidget(self.lbl_selected, 1)

        self.btn_on = QPushButton("ON")
        self.btn_on.setObjectName("btn_on")
        self.btn_on.setFixedSize(52, 34)
        self.btn_on.clicked.connect(lambda: self._control_device("on"))
        control_layout.addWidget(self.btn_on)

        self.btn_off = QPushButton("OFF")
        self.btn_off.setObjectName("btn_off")
        self.btn_off.setFixedSize(52, 34)
        self.btn_off.clicked.connect(lambda: self._control_device("off"))
        control_layout.addWidget(self.btn_off)

        self.btn_toggle = QPushButton("TOGGLE")
        self.btn_toggle.setObjectName("btn_toggle")
        self.btn_toggle.setFixedSize(74, 34)
        self.btn_toggle.clicked.connect(lambda: self._control_device("toggle"))
        control_layout.addWidget(self.btn_toggle)

        layout.addWidget(control_frame)

        # ─── BARRA DE PROGRESO (para escaneos) ──────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        layout.addWidget(self.progress_bar)

        # ─── CARGAR DISPOSITIVOS ──────────────────────────────────────
        self._devices = []
        self._selected_device = None
        self._load_devices()

        self.hide()

        # Cargar posición guardada
        QTimer.singleShot(100, self._load_position)

    # ─── STATUS HELPER ──────────────────────────────────────────────────
    def _set_status(self, text: str, kind: str = "info"):
        """Actualiza el mensaje de estado con color semántico, sin emojis."""
        colors = {
            "info": "rgba(255,255,255,0.45)",
            "success": "rgba(60, 240, 170, 0.85)",
            "warning": "rgba(251, 191, 36, 0.85)",
            "error": "rgba(255, 110, 100, 0.85)",
        }
        self.lbl_status.setStyleSheet(f"""
            color: {colors.get(kind, colors['info'])};
            font-size: 11px;
            font-weight: 700;
        """)
        self.lbl_status.setText(text)

    def _load_position(self):
        """Carga la posición guardada del widget."""
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

    def _save_position(self):
        """Guarda la posición actual del widget."""
        try:
            from memory.config_manager import load_api_keys, save_api_keys
            cfg = load_api_keys()
            w_name = self.__class__.__name__
            cfg[f"widget_pos_{w_name}_x"] = self.x()
            cfg[f"widget_pos_{w_name}_y"] = self.y()
            save_api_keys(cfg)
        except Exception:
            pass

    def _load_devices(self):
        """Carga los dispositivos desde la configuración."""
        try:
            from actions.smart_home import load_config
            cfg = load_config()

            self._devices = []
            self.device_list.clear()

            for dev in cfg.get("devices", []):
                self._devices.append({
                    "name": dev.get("name", "Desconocido"),
                    "type": "ble",
                    "data": dev
                })

            for tv in cfg.get("tvs", []):
                self._devices.append({
                    "name": tv.get("name", "TV Desconocida"),
                    "type": "tv",
                    "data": tv
                })

            for phone in cfg.get("phones", []):
                self._devices.append({
                    "name": phone.get("name", "Celular Desconocido"),
                    "type": "phone",
                    "data": phone
                })

            ha = cfg.get("home_assistant", {})
            if ha.get("url") and ha.get("token"):
                self._devices.append({
                    "name": "Home Assistant",
                    "type": "ha",
                    "data": ha
                })

            if not self._devices:
                self.device_list.addItem("Sin dispositivos configurados")
                self._set_status("Usa CONFIGURAR para añadir dispositivos", "warning")
                return

            for dev in self._devices:
                item = QListWidgetItem(dev['name'])
                if HAS_QTA:
                    item.setIcon(self._get_device_qicon(dev))
                item.setData(Qt.ItemDataRole.UserRole, dev)
                self.device_list.addItem(item)

            self._set_status(f"{len(self._devices)} dispositivos cargados", "success")

        except Exception as e:
            self._set_status(f"Error: {e}", "error")

    def _get_device_qicon(self, dev: dict):
        """Obtiene el ícono qtawesome para un tipo de dispositivo."""
        icon_map = {
            "ble": ('fa5s.lightbulb', '#fbbf24'),
            "tv": ('fa5s.tv', '#c9a8f7'),
            "phone": ('fa5s.mobile-alt', '#c9a8f7'),
            "ha": ('fa5s.home', '#fbbf24'),
        }
        name, color = icon_map.get(dev.get("type"), ('fa5s.plug', 'rgba(255,255,255,0.6)'))
        return qta.icon(name, color=color)

    def _refresh_list(self):
        """Refresca la lista de dispositivos."""
        self._load_devices()

    def _scan_devices(self):
        """Escanea dispositivos Bluetooth."""
        from PyQt6.QtCore import QMetaObject, Qt as _Qt, Q_ARG 
        self.progress_bar.setValue(20)
        self._set_status("Escaneando Bluetooth...", "info")
        self.btn_scan.setEnabled(False)

        def scan_thread():
            # IMPORTANTE: importar QMetaObject/Qt/Q_ARG ANTES del try.
            # Si se importa solo dentro del bloque try (tras la línea que
            # puede fallar), un error temprano deja estos nombres sin
            # definir y el except revienta con UnboundLocalError en vez
            # de mostrar el error real.
            from PyQt6.QtCore import QMetaObject, Qt as _Qt, Q_ARG
            try:
                import asyncio
                from actions.smart_home import _ble_scan
                found = asyncio.run(_ble_scan(timeout=8.0))

                QMetaObject.invokeMethod(self, "_on_scan_finished",
                                         _Qt.ConnectionType.QueuedConnection,
                                         Q_ARG(list, found))
            except Exception as e:
                # Mensaje amigable si el problema es que no hay adaptador
                # Bluetooth disponible en el equipo (caso muy común).
                msg = str(e)
                if "NO_BLUETOOTH" in msg or "No Bluetooth adapter" in msg:
                    msg = ("No se detectó ningún adaptador Bluetooth en este equipo. "
                           "Verifica que el Bluetooth esté activado en Windows, o conecta "
                           "un adaptador USB Bluetooth si tu PC no tiene uno integrado.")
                QMetaObject.invokeMethod(self, "_on_scan_error",
                                         _Qt.ConnectionType.QueuedConnection,
                                         Q_ARG(str, msg))

        threading.Thread(target=scan_thread, daemon=True).start()

    @pyqtSlot(list)
    def _on_scan_finished(self, devices):
        """Callback cuando el escaneo termina."""
        self.progress_bar.setValue(100)
        self.btn_scan.setEnabled(True)

        if not devices:
            self._set_status("No se encontraron dispositivos Bluetooth", "warning")
            return

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Dispositivos Bluetooth Encontrados")
        dialog.setFixedSize(420, 320)
        dialog.setStyleSheet("""
            QDialog {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 16, 28, 0.97),
                    stop:1 rgba(10, 9, 18, 0.97)
                );
                border: 1px solid rgba(251, 191, 36, 0.14);
                border-radius: 14px;
            }
            QLabel {
                color: rgba(255,255,255,0.85);
                font-weight: 700;
                font-size: 12px;
            }
            QListWidget {
                background: rgba(0, 0, 0, 0.32);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 10px;
                color: rgba(255,255,255,0.85);
                font-weight: 600;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: rgba(168, 85, 247, 0.10);
            }
            QPushButton {
                background: rgba(168, 85, 247, 0.15);
                color: rgba(255, 255, 255, 0.88);
                border: 1px solid rgba(168, 85, 247, 0.30);
                border-radius: 10px;
                padding: 8px 18px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: rgba(168, 85, 247, 0.28);
                border-color: rgba(168, 85, 247, 0.5);
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel("DISPOSITIVOS ENCONTRADOS"))

        list_widget = QListWidget()
        for dev in devices[:20]:
            name = dev.get("name", "Desconocido")
            address = dev.get("address", "")
            rssi = dev.get("rssi", "")
            list_widget.addItem(f"{name}  ·  {address}  ·  RSSI {rssi}")
        layout.addWidget(list_widget)

        btn_layout = QHBoxLayout()
        btn_close = QPushButton("CERRAR")
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        dialog.exec()
        self._set_status(f"Escaneo completado: {len(devices)} dispositivos", "success")
        QTimer.singleShot(2000, lambda: self._refresh_list())

    @pyqtSlot(str)
    def _on_scan_error(self, error):
        """Callback cuando hay error en el escaneo."""
        self.progress_bar.setValue(0)
        self.btn_scan.setEnabled(True)
        self._set_status(error, "error")

    def _on_device_double_click(self, item):
        """Cuando se hace doble clic en un dispositivo."""
        dev = item.data(Qt.ItemDataRole.UserRole)
        if dev:
            self._selected_device = dev
            self.lbl_selected.setText(dev['name'])
            self.lbl_selected.setStyleSheet("""
                font-size: 11px;
                font-weight: 800;
                color: rgba(251, 191, 36, 0.9);
            """)

    def _control_device(self, command: str):
        """Controla el dispositivo seleccionado."""
        if not self._selected_device:
            self._set_status("Selecciona un dispositivo primero", "warning")
            return

        dev = self._selected_device
        name = dev.get("name", "")
        dev_type = dev.get("type", "")

        self._set_status(f"Ejecutando {command.upper()} en {name}...", "info")

        def control_thread():
            # Mismo fix de scoping que en scan_thread: importar antes del try.
            from PyQt6.QtCore import QMetaObject, Qt as _Qt, Q_ARG
            try:
                from actions.smart_home import smart_home as sh

                if dev_type == "ble":
                    result = sh({"action": command, "device": name})
                elif dev_type == "tv":
                    if command in ("on", "off", "toggle"):
                        result = sh({"action": "tv_power", "device": name})
                    else:
                        result = f"Comando {command} no soportado para TV"
                elif dev_type == "phone":
                    if command == "on":
                        result = sh({"action": "phone_screen_on", "device": name})
                    elif command == "off":
                        result = sh({"action": "phone_screen_off", "device": name})
                    else:
                        result = sh({"action": f"phone_{command}", "device": name})
                elif dev_type == "ha":
                    result = "Home Assistant: usa la configuración avanzada"
                else:
                    result = f"Tipo {dev_type} no soportado"

                QMetaObject.invokeMethod(self, "_on_control_result",
                                         _Qt.ConnectionType.QueuedConnection,
                                         Q_ARG(str, result))
            except Exception as e:
                QMetaObject.invokeMethod(self, "_on_control_result",
                                         _Qt.ConnectionType.QueuedConnection,
                                         Q_ARG(str, f"Error: {e}"))

        threading.Thread(target=control_thread, daemon=True).start()

    @pyqtSlot(str)
    def _on_control_result(self, result):
        """Callback cuando el control termina."""
        kind = "error" if result.lower().startswith("error") else "success"
        self._set_status(result[:150], kind)
        QTimer.singleShot(2000, self._refresh_list)

    def _open_setup(self):
        """Abre la configuración de Smart Home."""
        try:
            import subprocess
            from memory.config_manager import BASE_DIR
            config_path = BASE_DIR / "config" / "smart_home.json"

            if config_path.exists():
                subprocess.Popen(f'notepad "{config_path}"', shell=True)
                self._set_status("Configuración abierta en Notepad", "info")
            else:
                default = {
                    "devices": [],
                    "tvs": [],
                    "phones": [],
                    "home_assistant": {"url": "", "token": ""}
                }
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(
                    json.dumps(default, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                subprocess.Popen(f'notepad "{config_path}"', shell=True)
                self._set_status("Configuración creada y abierta", "success")
        except Exception as e:
            self._set_status(f"Error: {e}", "error")

    # ─── DRAG SYSTEM ──────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            self._save_position()
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def showEvent(self, event):
        """Cuando se muestra, refrescar la lista."""
        self._refresh_list()
        super().showEvent(event)

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
                    stop: 0 rgba(20, 20, 25, 0.92),
                    stop: 0.5 rgba(15, 15, 20, 0.92),
                    stop: 1 rgba(10, 10, 15, 0.92)
                );
                border: 1px solid rgba(255, 255, 255, 0.08);
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
                    stop: 0 rgba(40, 25, 55, 0.80),
                    stop: 1 rgba(20, 12, 35, 0.80)
                );
                border-right: 1px solid rgba(168, 85, 247, 0.20);
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
            ("Tienda", "fa5s.store"),
            ("Arduino", "fa5s.microchip")
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
        self._build_tab_arduino()

        # Conectar navegación
        self.tab_bar.tab_changed.connect(self.stacked_widget.setCurrentIndex)

        # Cargar datos
        self.update_style()
        self.load_settings()
        self.load_macros()
        self.clean_all_emojis(self)
        self._setup_sound_controls()

    def _setup_sound_controls(self):
        """Configura los sonidos del panel de configuración."""
        # Sonido al abrir el panel
        QTimer.singleShot(50, lambda: play_sound("open"))
    
    def showEvent(self, event):
        """Cuando se muestra el panel, reproducir sonido."""
        super().showEvent(event)
        play_sound("open")

    def reject(self):
        """Cerrar el panel con sonido."""
        play_sound("close")
        self._cleanup()
        self.hide()
        if hasattr(self, "_on_close_callback") and self._on_close_callback:
            self._on_close_callback(False)

    def accept(self):
        """Aceptar cambios y cerrar con sonido."""
        play_sound("success")
        self._cleanup()
        self.hide()
        if hasattr(self, "_on_close_callback") and self._on_close_callback:
            self._on_close_callback(True)

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


    def _build_tab_arduino(self):
        tab = self._create_tab_widget()
        card = tab.add_card("🚀 CONEXIÓN ARDUINO", col_span=2)
        layout = card.content_layout
        
        # Puertos COM
        lbl_port = QLabel("🔌 Puerto COM:")
        lbl_port.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout.addWidget(lbl_port, 0, 0)
        
        self.cmb_arduino_port = QComboBox()
        self.cmb_arduino_port.setMinimumHeight(42)
        self.cmb_arduino_port.setStyleSheet(self.cmb_ai_provider.styleSheet())
        layout.addWidget(self.cmb_arduino_port, 0, 1)
        
        self.btn_refresh_ports = QPushButton("🔄 ACTUALIZAR")
        self.btn_refresh_ports.setFixedHeight(42)
        self.btn_refresh_ports.clicked.connect(self._refresh_arduino_ports)
        layout.addWidget(self.btn_refresh_ports, 0, 2)
        
        # Botón Conectar
        self.btn_connect_arduino = QPushButton("CONECTAR")
        self.btn_connect_arduino.setFixedHeight(42)
        self.btn_connect_arduino.clicked.connect(self._toggle_arduino_connection)
        layout.addWidget(self.btn_connect_arduino, 1, 0, 1, 3)
        
        # Enviar Comandos
        self.inp_arduino_cmd = QLineEdit()
        self.inp_arduino_cmd.setPlaceholderText("Comando a enviar (ej: 1, 0, ON, OFF)")
        self.inp_arduino_cmd.setMinimumHeight(42)
        self.inp_arduino_cmd.setStyleSheet("""
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
        layout.addWidget(self.inp_arduino_cmd, 2, 0, 1, 2)
        
        self.btn_send_cmd = QPushButton("ENVIAR")
        self.btn_send_cmd.setFixedHeight(42)
        self.btn_send_cmd.clicked.connect(self._send_arduino_cmd)
        layout.addWidget(self.btn_send_cmd, 2, 2)
        
        # Consola
        self.arduino_console = QTextEdit()
        self.arduino_console.setReadOnly(True)
        self.arduino_console.setMinimumHeight(150)
        self.arduino_console.setStyleSheet("""
            QTextEdit {
                background: rgba(0,0,0,0.5);
                color: #00ff00;
                font-family: Consolas, monospace;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.arduino_console, 3, 0, 1, 3)
        
        self.stacked_widget.addWidget(tab)
        self._refresh_arduino_ports()
        
    def _refresh_arduino_ports(self):
        self.cmb_arduino_port.clear()
        try:
            from core.arduino_manager import arduino
            ports = arduino.get_available_ports()
            for p in ports:
                self.cmb_arduino_port.addItem(p)
            if not ports:
                self.cmb_arduino_port.addItem("No hay puertos")
        except:
            self.cmb_arduino_port.addItem("Error cargando puertos")
            
    def _toggle_arduino_connection(self):
        try:
            from core.arduino_manager import arduino
            if arduino.is_connected:
                arduino.disconnect()
                self.btn_connect_arduino.setText("CONECTAR")
                self.arduino_console.append("[Sistema] Desconectado.")
            else:
                port = self.cmb_arduino_port.currentText()
                if "No hay" in port or "Error" in port:
                    return
                ok, msg = arduino.connect(port)
                self.arduino_console.append(f"[Sistema] {msg}")
                if ok:
                    self.btn_connect_arduino.setText("DESCONECTAR")
                    arduino.on_message_received = self._arduino_msg_received
        except Exception as e:
            self.arduino_console.append(f"[Error] {e}")
            
    def _send_arduino_cmd(self):
        cmd = self.inp_arduino_cmd.text().strip()
        if not cmd: return
        try:
            from core.arduino_manager import arduino
            ok, msg = arduino.send_command(cmd)
            self.arduino_console.append(f"> {msg}")
            self.inp_arduino_cmd.clear()
        except Exception as e:
            self.arduino_console.append(f"[Error] {e}")
            
    def _arduino_msg_received(self, msg):
        # We need to use a signal or QMetaObject.invokeMethod to update GUI from thread
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(self.arduino_console, "append", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"< {msg}"))

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
        
        # --- Card 6: 🔊 CONFIGURACIÓN DE SONIDOS ---
        card_sound = tab.add_card("🔊 CONFIGURACIÓN DE SONIDOS", col_span=2)
        layout_sound = card_sound.content_layout

        # Activar/Desactivar sonidos
        self.chk_sounds_enabled = QCheckBox("Activar todos los sonidos")
        self.chk_sounds_enabled.setChecked(True)
        self.chk_sounds_enabled.toggled.connect(self._toggle_sounds)
        layout_sound.addWidget(self.chk_sounds_enabled, 0, 0, 1, 2)

        # Control de volumen
        vol_lay = QHBoxLayout()
        vol_lay.addWidget(QLabel("Volumen global:"))
        self.lbl_volume_val = QLabel("60%")
        self.lbl_volume_val.setStyleSheet("font-weight:bold;color:rgba(255,255,255,0.6);font-size:13px;")
        vol_lay.addStretch()
        vol_lay.addWidget(self.lbl_volume_val)
        layout_sound.addLayout(vol_lay, 1, 0, 1, 2)

        self.sld_volume = QSlider(Qt.Orientation.Horizontal)
        self.sld_volume.setRange(0, 100)
        self.sld_volume.setValue(60)
        self.sld_volume.valueChanged.connect(lambda v: self.lbl_volume_val.setText(f"{v}%"))
        self.sld_volume.sliderReleased.connect(self._apply_volume)
        layout_sound.addWidget(self.sld_volume, 2, 0, 1, 2)

        # Sonidos individuales
        layout_sound.addWidget(QLabel("Sonidos individuales:"), 3, 0, 1, 2)
        sound_checkboxes = [
            ("click", "Click de botón"),
            ("hover", "Hover sobre botón"),
            ("open", "Abrir paneles"),
            ("close", "Cerrar paneles"),
            ("listen", "Iniciar escucha"),
            ("respond", "Responder"),
            ("notification", "Notificaciones"),
            ("error", "Errores"),
        ]
        self._sound_checkboxes = {}

        for i, (key, label) in enumerate(sound_checkboxes):
            cb = QCheckBox(label)
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
            cb.toggled.connect(lambda checked, k=key: self._toggle_individual_sound(k, checked))
            self._sound_checkboxes[key] = cb
            layout_sound.addWidget(cb, 4 + i // 2, i % 2)
        
        # Botón de prueba
        test_lay = QHBoxLayout()
        test_lay.addStretch()
        self.btn_test_sound = QPushButton("🔊 PROBAR SONIDO")
        self.btn_test_sound.setFixedHeight(40)
        self.btn_test_sound.clicked.connect(lambda: play_sound("notification"))
        test_lay.addWidget(self.btn_test_sound)
        layout_sound.addLayout(test_lay, 4 + len(sound_checkboxes) // 2 + 1, 0, 1, 2)

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
        
        self.chk_stars = QCheckBox("Activar Estrellitas Flotantes")
        layout1.addWidget(self.chk_stars, 5, 0, 1, 2)
        self.cmb_star_variant = QComboBox()
        self.cmb_star_variant.setMinimumHeight(38)
        for key, data in STAR_VARIANTS.items():
            self.cmb_star_variant.addItem(data["label"], key)
        self.chk_stars.toggled.connect(self.cmb_star_variant.setEnabled)
        layout1.addWidget(QLabel("Variante de Partículas:"), 6, 0)
        layout1.addWidget(self.cmb_star_variant, 6, 1)

        self.chk_pro_widgets = QCheckBox("Estilos de Widgets PRO (Requiere Tienda)")
        layout1.addWidget(self.chk_pro_widgets, 7, 0, 1, 2)


        # ─── DISEÑO DEL LOGO ──────────────────────────────────────────
        self.cmb_logo_style = QComboBox()
        self.cmb_logo_style.setMinimumHeight(40)
        logo_styles = [
            ("clasico", "Clásico (por defecto)"),
            ("neon", "Neón"),
            ("minimal", "Minimalista"),
            ("cyberpunk", "Cyberpunk"),
            ("oro", "Oro Elegante"),
            ("retro", "Retro Digital"),
        ]
        for val, desc in logo_styles:
            self.cmb_logo_style.addItem(desc, val)
            layout1.addWidget(QLabel("Diseño del Logo (Orbe):"), 8, 0)
            layout1.addWidget(self.cmb_logo_style, 8, 1)
        


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
        self._internal_api_keys = {}
        tab = self._create_tab_widget()
        
        # --- Card 1: INTEGRACIÓN DE IA (Cloud Keys & Provider) ---
        card1 = tab.add_card("🧠 INTEGRACIÓN DE IA", col_span=2)
        layout1 = card1.content_layout
        
        # Dynamic API Key Input
        self.lbl_dynamic_api = QLabel("🔑 API Key:")
        self.lbl_dynamic_api.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(self.lbl_dynamic_api, 4, 0)
        
        self.inp_dynamic_api = QLineEdit()
        self.inp_dynamic_api.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_dynamic_api.setPlaceholderText("Ingresa tu API Key")
        self.inp_dynamic_api.setMinimumHeight(42)
        self.inp_dynamic_api.setStyleSheet("""
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
        layout1.addWidget(self.inp_dynamic_api, 4, 1, 1, 3)

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
        self.cmb_ai_provider.addItem("🟢 ChatGPT (OpenAI)", "openai")
        self.cmb_ai_provider.addItem("🌌 Grok", "grok")
        self.cmb_ai_provider.addItem("⚡ Groq", "groq")
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
        
        def _on_provider_changed():
            provider = self.cmb_ai_provider.currentData()
            # save current text to previous provider
            if hasattr(self, "_last_provider"):
                self._internal_api_keys[self._last_provider] = self.inp_dynamic_api.text().strip()
            # load new provider text
            self.inp_dynamic_api.setText(self._internal_api_keys.get(provider, ""))
            self.lbl_dynamic_api.setText(f"🔑 API Key ({provider.capitalize()}):")
            self._last_provider = provider

        self.cmb_ai_provider.currentIndexChanged.connect(_on_provider_changed)
        
        # Zona Horaria
        lbl_timezone = QLabel("🌐 Zona Horaria:")
        lbl_timezone.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout1.addWidget(lbl_timezone, 5, 0)
        
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
        layout1.addWidget(self.cmb_timezone, 5, 1, 1, 3)
        
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

        # ─── CARD: SMART HOME ──────────────────────────────────────────────  ← NUEVO, va aquí
        card_smart = tab.add_card("🏠 SMART HOME - CONTROL DE DISPOSITIVOS", col_span=2)
        layout_smart = card_smart.content_layout
        
        self.btn_open_smarthome = QPushButton("🔌 ABRIR PANEL SMART HOME")
        self.btn_open_smarthome.setFixedHeight(50)
        self.btn_open_smarthome.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(168, 85, 247, 0.15),
                    stop:1 rgba(139, 92, 246, 0.08)
                );
                border: 1px solid rgba(168, 85, 247, 0.25);
                border-radius: 14px;
                color: rgba(255, 255, 255, 0.85);
                font-weight: 700;
                font-size: 13px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(168, 85, 247, 0.25),
                    stop:1 rgba(139, 92, 246, 0.15)
                );
                border-color: rgba(168, 85, 247, 0.4);
            }
        """)
        self.btn_open_smarthome.clicked.connect(self._open_smarthome_widget)
        layout_smart.addWidget(self.btn_open_smarthome, 0, 0, 1, 2)
        
        self.lbl_smarthome_status = QLabel("📡 Estado: Conectado a Smart Home")
        self.lbl_smarthome_status.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px; font-style: italic;")
        layout_smart.addWidget(self.lbl_smarthome_status, 1, 0, 1, 2)
        
        self.lbl_smarthome_devices = QLabel("Dispositivos: Cargando...")
        self.lbl_smarthome_devices.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 10px;")
        layout_smart.addWidget(self.lbl_smarthome_devices, 2, 0, 1, 2)
        
        QTimer.singleShot(500, self._update_smarthome_info)
        # ─── FIN CARD SMART HOME ─────────────────────────────────────────────

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

    def _open_smarthome_widget(self):
        """Abre el widget flotante de Smart Home."""
        main_win = self.window()
        if main_win and hasattr(main_win, "smarthome_widget"):
            widget = main_win.smarthome_widget
            if widget.isVisible():
                widget.hide()
            else:
                w = main_win.width()
                h = main_win.height()
                widget.move((w - widget.width()) // 2, (h - widget.height()) // 2)
                widget.show()
                widget.raise_()
        else:
            if main_win and hasattr(main_win, "create_smarthome_widget"):
                main_win.create_smarthome_widget()
                self._open_smarthome_widget()

    def _update_smarthome_info(self):
        """Actualiza la información de dispositivos Smart Home."""
        try:
            from actions.smart_home import load_config
            cfg = load_config()

            ble_count = len(cfg.get("devices", []))
            tv_count = len(cfg.get("tvs", []))
            phone_count = len(cfg.get("phones", []))
            ha = cfg.get("home_assistant", {})
            ha_active = bool(ha.get("url") and ha.get("token"))

            total = ble_count + tv_count + phone_count
            if total > 0:
                self.lbl_smarthome_devices.setText(
                    f"💡 {ble_count} luces | 📺 {tv_count} TVs | 📱 {phone_count} celulares | "
                    f"{'🏠 HA activo' if ha_active else '🏠 HA no configurado'}"
                )
                self.lbl_smarthome_status.setText("✅ Sistema Smart Home activo")
                self.lbl_smarthome_status.setStyleSheet("color: rgba(0, 255, 136, 0.6); font-size: 11px;")
            else:
                self.lbl_smarthome_devices.setText("📭 No hay dispositivos configurados")
                self.lbl_smarthome_status.setText("⚠️ Configura Smart Home en config/smart_home.json")
                self.lbl_smarthome_status.setStyleSheet("color: rgba(255, 200, 0, 0.6); font-size: 11px;")

        except Exception as e:
            self.lbl_smarthome_devices.setText(f"❌ Error: {e}")

    def _build_tab_automation(self):
        tab = self._create_tab_widget()
        
        card1 = tab.add_card("IDENTIDAD DEL SISTEMA", col_span=2)
        layout1 = card1.content_layout
        
        self.inp_ai_name = QLineEdit()
        self.inp_ai_name.setPlaceholderText("NEXUS")
        self.inp_ai_name.setMinimumHeight(40)
        layout1.addWidget(QLabel("Nombre de la IA:"), 0, 0)
        layout1.addWidget(self.inp_ai_name, 0, 1)

        self.chk_only_name_response = QCheckBox("Solo responder cuando me llamen por NEXUS (BETA)")
        self.chk_only_name_response.setStyleSheet("QCheckBox { color: rgba(255,255,255,0.7); font-size: 12px; spacing: 14px; padding: 8px 0; }")
        layout1.addWidget(self.chk_only_name_response, 1, 0, 1, 2)
        
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
        layout1.addWidget(QLabel("Icono Aplicación:"), 2, 0)
        layout1.addLayout(icon_lay, 2, 1)

        card2 = tab.add_card("🎛️ CONTROL DE WIDGETS", col_span=2)
        layout2 = card2.content_layout
        
        self.chk_widget_spotify = QCheckBox("Mostrar Widget Spotify Flotante")
        self.chk_widget_media = QCheckBox("Mostrar Widget YouTube/Medios (Universal)")
        self.chk_widget_weather = QCheckBox("Mostrar Widget del Clima")
        self.chk_widget_notifications = QCheckBox("Mostrar Accesos Directos")
        self.chk_widget_calendar = QCheckBox("Mostrar Calendario")
        self.chk_widget_todo = QCheckBox("Mostrar Widget de Tareas")
        self.chk_widget_notes = QCheckBox("Mostrar Widget de Notas")
        self.chk_widget_files = QCheckBox("Mostrar Panel de Archivos/Macros")

        widgets = [self.chk_widget_spotify, self.chk_widget_media, self.chk_widget_weather, self.chk_widget_notifications,
                   self.chk_widget_calendar, self.chk_widget_todo,
                   self.chk_widget_notes, self.chk_widget_files]
        for i, w in enumerate(widgets):
            w.setStyleSheet("QCheckBox { color: rgba(255,255,255,0.7); font-size: 12px; spacing: 14px; padding: 8px 0; }")
            w.setChecked(False)
            layout2.addWidget(w, i // 2, i % 2)

        card3 = tab.add_card("MEMORIA A LARGO PLAZO", col_span=2)
        layout3 = card3.content_layout
        
        self.btn_clear_memory = QPushButton("LIMPIAR MEMORIA DE NEXUS")
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
        self.btn_clear_memory.clicked.connect(self._clear_nexus_memory)
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
            NexusMessageBox(self, "Error", f"Ya existe '{key}'.").exec()
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
            NexusMessageBox(self, "Error", "No se puede eliminar la personalidad original.").exec()
            return
        if self.cmb_personality.count() <= 1:
            NexusMessageBox(self, "Error", "Debe quedar al menos una personalidad.").exec()
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
        NexusMessageBox(self, "SUCCESS", f"Modelo {model_name.upper()} seleccionado.").exec()

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
            NexusMessageBox(self, "SUCCESS", "DESCARGA DE MODELO COMPLETADA.").exec()
        elif status == "success_installer":
            self.lbl_progress_status.setText("INSTALADOR ABIERTO")
            self.bar_pull_progress.setValue(100)
            self.finish_pull()
        elif status in ("cancelled", "error"):
            self.lbl_progress_status.setText(f"{'CANCELADO' if status=='cancelled' else 'ERROR: '+error.upper()}")
            self.bar_pull_progress.setValue(0)
            self.finish_pull()
            if status == "error":
                NexusMessageBox(self, "ERROR", f"Fallo: {error}", is_error=True).exec()
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
            NexusMessageBox(self, "WARNING", "Escribe un nombre de modelo válido.", is_error=True).exec()
            return
        self.start_pull(model)

    # ── Appearance helpers ───────────────────────────────────────────────

    def _toggle_theme_fields(self):
        if not hasattr(self, "btn_color_picker"):
            return
        is_custom = (self.cmb_theme.currentData() == "custom")
        self.btn_color_picker.setVisible(is_custom)
        self.lbl_color_preview.setVisible(is_custom)
    
    def _toggle_sounds(self, enabled):
        """Activa o desactiva todos los sonidos globalmente."""
        get_sound_manager().set_enabled(enabled)
        try:
            from memory.config_manager import load_api_keys, save_api_keys
            cfg = load_api_keys()
            cfg["sounds_enabled"] = enabled
            save_api_keys(cfg)
        except Exception as e:
            print(f"Error guardando sounds_enabled: {e}")
    # 🆕 Ya NO se hace cb.setEnabled(enabled) — los checkboxes individuales
    # siempre quedan interactuables, incluso con el interruptor global apagado.
            
    def _toggle_individual_sound(self, sound_key: str, enabled: bool):
        """Activa o desactiva un sonido específico y lo aplica en caliente."""
        try:
            from memory.config_manager import load_api_keys, save_api_keys
            cfg = load_api_keys()
        
            # Usar el nuevo formato
            cfg[f"sound_{sound_key}"] = enabled
        
            # Opcional: eliminar la clave antigua si existe
            if f"sound_chk_{sound_key}" in cfg:
                del cfg[f"sound_chk_{sound_key}"]
            
            save_api_keys(cfg)
            get_sound_manager().set_event_enabled(sound_key, enabled)
            print(f"[Sound] {sound_key} -> {enabled} guardado")
        except Exception as e:
            print(f"Error guardando configuración de sonido: {e}")

    def save_api_keys(cfg: dict):
        """Guarda la configuración en api_keys.json."""
        import json
        from pathlib import Path
        BASE_DIR = Path(__file__).resolve().parent.parent
        config_path = BASE_DIR / "config" / "api_keys.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    
    def _apply_volume(self):
        """Aplica el volumen seleccionado."""
        volume = self.sld_volume.value() / 100.0
        get_sound_manager().set_volume(volume)

    def _load_sound_settings(self):
        try:
            from memory.config_manager import load_api_keys, save_api_keys
            cfg = load_api_keys()

            enabled = cfg.get("sounds_enabled", True)
            self.chk_sounds_enabled.setChecked(enabled)
            get_sound_manager().set_enabled(enabled)
        
            volume = cfg.get("sounds_volume", 0.6)
            self.sld_volume.setValue(int(volume * 100))
            self.lbl_volume_val.setText(f"{int(volume * 100)}%")
            get_sound_manager().set_volume(volume)

            # Mapeo de claves del JSON a los checkboxes
            for key, cb in self._sound_checkboxes.items():
                # Intentar leer con el nuevo formato
                individual_enabled = cfg.get(f"sound_{key}", True)
            
                # Si no existe, intentar con el formato antiguo (sound_chk_)
                if f"sound_{key}" not in cfg:
                    individual_enabled = cfg.get(f"sound_chk_{key}", True)
                    # Migrar a nuevo formato
                    cfg[f"sound_{key}"] = individual_enabled
                    if f"sound_chk_{key}" in cfg:
                        del cfg[f"sound_chk_{key}"]
            
                cb.setChecked(individual_enabled)
                get_sound_manager().set_event_enabled(key, individual_enabled)
        
            # Guardar los cambios de migración
            save_api_keys(cfg)
        
        except Exception as e:
            print(f"Error cargando configuración de sonidos: {e}")

    def _open_color_picker(self):
        try:
            from shop import load_unlocks
            from memory.ui_helpers import NexusMessageBox
            if not load_unlocks().get("neon_color", False):
                NexusMessageBox(self, "Tienda NEXUS", "Para usar colores de acento personalizados necesitas desbloquear el complemento 'Color Neón' en la tienda.").exec()
                return
        except Exception as e:
            print("Error validating neon_color:", e)

        initial = QColor(self.custom_color_hex) if self.custom_color_hex else QColor("rgba(255,255,255,0.8)")
        dialog = NexusColorPicker(self, initial)
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
            from memory.ui_helpers import NexusMessageBox
            if not load_unlocks().get("custom_fonts", False):
                NexusMessageBox(self, "Tienda NEXUS", "Para instalar tipografías desde archivos necesitas desbloquear el complemento 'Fuentes Premium' en la tienda.").exec()
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
                    from memory.ui_helpers import NexusMessageBox
                    if not load_unlocks().get("gif_wallpaper", False):
                        NexusMessageBox(self, "Tienda NEXUS", "Para usar fondos animados (GIF) necesitas desbloquear el complemento 'GIF Wallpaper' en la tienda.").exec()
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

    def _clear_nexus_memory(self):
        reply = QMessageBox.question(self, "Confirmar", "¿Borrar TODA la memoria de NEXUS?",
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
        NexusMessageBox(self, "Spotify", "¡Autenticación exitosa!").exec()

    def spotify_auth_failed(self, error):
        self.btn_spotify_login.setEnabled(True)
        self.lbl_spotify_status.setText("Error")
        self.lbl_spotify_status.setStyleSheet("color: rgba(255, 59, 48, 0.6); font-weight: bold;")
        NexusMessageBox(self, "Error Spotify", f"Fallo: {error}", is_error=True).exec()

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

            self._internal_api_keys["gemini"] = cfg.get("gemini_api_key", "")
            self._internal_api_keys["openai"] = cfg.get("openai_api_key", "")
            self._internal_api_keys["grok"] = cfg.get("grok_api_key", "")
            self._internal_api_keys["groq"] = cfg.get("groq_api_key", "")
            self._internal_api_keys["openrouter"] = cfg.get("openrouter_api_key", "")
            self._internal_api_keys["ollama"] = cfg.get("ollama_api_key", "http://localhost:11434")
            self.inp_openrouter_model.setText(cfg.get("openrouter_model", "google/gemini-2.5-flash"))
            
            # Select provider
            active_provider = cfg.get("active_ai_provider", "gemini")
            idx = self.cmb_ai_provider.findData(active_provider)
            if idx >= 0:
                self.cmb_ai_provider.setCurrentIndex(idx)
            self._last_provider = active_provider
            self.inp_dynamic_api.setText(self._internal_api_keys.get(active_provider, ""))
            self.lbl_dynamic_api.setText(f"?? API Key ({active_provider.capitalize()}):")
            self.inp_ai_name.setText(cfg.get("ai_name", ""))
            self.chk_only_name_response.setChecked(bool(cfg.get("respond_only_by_name", False)))
            self.inp_app_icon.setText(cfg.get("nexus_app_icon", ""))

            prov = cfg.get("ai_provider", "gemini")
            idx = self.cmb_ai_provider.findData(prov)
            if idx >= 0:
                self.cmb_ai_provider.setCurrentIndex(idx)

            voice = cfg.get("nexus_voice", "Aoede")
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

            theme = cfg.get("nexus_theme", "gold")
            self.custom_color_hex = cfg.get("nexus_custom_theme_color", "")
            idx = self.cmb_theme.findData(theme)
            if idx >= 0:
                self.cmb_theme.setCurrentIndex(idx)
            self.chk_stars.setChecked(cfg.get("nexus_stars", False))
            star_variant = cfg.get("nexus_star_variant", "estrellas")
            idx = self.cmb_star_variant.findData(star_variant)
            if idx >= 0:
                self.cmb_star_variant.setCurrentIndex(idx)
            self.cmb_star_variant.setEnabled(self.chk_stars.isChecked())

            logo_style = cfg.get("nexus_logo_style", "clasico")
            idx = self.cmb_logo_style.findData(logo_style)
            if idx >= 0:
                self.cmb_logo_style.setCurrentIndex(idx)
            
            try:
                from shop import load_unlocks
                ul = load_unlocks()
                
                has_widgets = bool(ul.get("widget_customization", False))
                self.chk_pro_widgets.setEnabled(has_widgets)
                self.chk_pro_widgets.setChecked(cfg.get("pro_widget_styles", False) and has_widgets)
                if not has_widgets:
                    self.chk_pro_widgets.setText("Estilos de Widgets PRO (Desbloquea en Tienda)")
                

            except Exception:
                pass

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
                        # Mostrar la key ofuscada en el medio, ej: NEXUS-7MZV-****-5J06
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

            ff = cfg.get("nexus_font_family", "Century Gothic")
            idx = self.cmb_font_family.findData(ff)
            if idx >= 0:
                self.cmb_font_family.setCurrentIndex(idx)

            self.sld_performance.setValue(int(cfg.get("performance_quality", 80)))
            self.chk_gpu.setChecked(cfg.get("gpu_acceleration", False))

            self._custom_bg_color = cfg.get("nexus_bg_color", "")
            self._custom_panel_color = cfg.get("nexus_panel_color", "")
            self._custom_text_color = cfg.get("nexus_text_color", "")
            self._custom_bg_image = cfg.get("nexus_bg_image", "")
            self._custom_sticker_path = cfg.get("nexus_sticker_path", "")

            bg_op = int(float(cfg.get("nexus_bg_opacity", 0.85)) * 100)
            self.sld_bg_opacity.setValue(bg_op)
            self.sld_sticker_w.setValue(int(cfg.get("nexus_sticker_w", 100)))
            self.sld_sticker_h.setValue(int(cfg.get("nexus_sticker_h", 100)))

            # Cargar visibilidad de widgets
            self.chk_widget_spotify.setChecked(cfg.get("show_widget_spotify", False))
            self.chk_widget_media.setChecked(cfg.get("show_widget_media", True))
            self.chk_widget_weather.setChecked(cfg.get("show_widget_weather", False))
            self.chk_widget_notifications.setChecked(cfg.get("show_widget_notifications", False))
            self.chk_widget_calendar.setChecked(cfg.get("show_widget_calendar", False))
            self.chk_widget_todo.setChecked(cfg.get("show_widget_todo", False))
            self.chk_widget_notes.setChecked(cfg.get("show_widget_notes", False))
            self.chk_widget_files.setChecked(cfg.get("show_widget_files", False))
            self._load_sound_settings()

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
            # Save currently typing key to dict
            provider = self.cmb_ai_provider.currentData()
            self._internal_api_keys[provider] = self.inp_dynamic_api.text().strip()
            cfg.update({
                "nexus_stars": self.chk_stars.isChecked(),
                "nexus_star_variant": self.cmb_star_variant.currentData(),
                "nexus_logo_style": self.cmb_logo_style.currentData(),  
                "sounds_enabled": self.chk_sounds_enabled.isChecked(),
                "sounds_volume": self.sld_volume.value() / 100.0,
                "ai_name": self.inp_ai_name.text().strip(),
                "respond_only_by_name": self.chk_only_name_response.isChecked(),
                "nexus_app_icon": self.inp_app_icon.text().strip(),
                "gemini_api_key": self._internal_api_keys.get("gemini", "").strip(),
                "openai_api_key": self._internal_api_keys.get("openai", "").strip(),
                "grok_api_key": self._internal_api_keys.get("grok", "").strip(),
                "groq_api_key": self._internal_api_keys.get("groq", "").strip(),
                "openrouter_api_key": self._internal_api_keys.get("openrouter", "").strip(),
                "ollama_api_key": self._internal_api_keys.get("ollama", "").strip(),
                "active_ai_provider": self.cmb_ai_provider.currentData(),
                "pro_widget_styles": self.chk_pro_widgets.isChecked(),

                "openrouter_model": self.inp_openrouter_model.text().strip(),
                "ai_provider": self.cmb_ai_provider.currentData(),
                "fish_audio_enabled": self.chk_fish_audio.isChecked(),
                "fish_api_key": self.inp_fish_api_key.text().strip(),
                "fish_voice_id": self.inp_fish_voice_id.text().strip(),
                "local_tts_enabled": self.chk_local_tts.isChecked(),
                "ollama_url": self.inp_ollama_url.text().strip(),
                "ollama_model": self.cmb_ollama_model.currentText().strip(),
                "performance_quality": self.sld_performance.value(),
                "nexus_voice": self.cmb_voice.currentData(),
                "nexus_theme": theme_val,
                "nexus_custom_theme_color": custom_hex,
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
                "nexus_font_family": self.cmb_font_family.currentData(),
                "nexus_bg_color": self._custom_bg_color,
                "nexus_panel_color": self._custom_panel_color,
                "nexus_text_color": self._custom_text_color,
                "nexus_bg_image": self._custom_bg_image,
                "nexus_bg_opacity": self.sld_bg_opacity.value() / 100.0,
                "nexus_sticker_path": self._custom_sticker_path,
                "nexus_sticker_w": self.sld_sticker_w.value(),
                "nexus_sticker_h": self.sld_sticker_h.value(),
                "show_widget_spotify": self.chk_widget_spotify.isChecked(),
                "show_widget_media": self.chk_widget_media.isChecked(),
                "show_widget_weather": self.chk_widget_weather.isChecked(),
                "show_widget_notifications": self.chk_widget_notifications.isChecked(),
                "show_widget_calendar": self.chk_widget_calendar.isChecked(),
                "show_widget_todo": self.chk_widget_todo.isChecked(),
                "show_widget_notes": self.chk_widget_notes.isChecked(),
                "show_widget_files": self.chk_widget_files.isChecked(),
            })

            # Guardar estados individuales de sonidos
            if hasattr(self, '_sound_checkboxes'):
                for key, cb in self._sound_checkboxes.items():
                    cfg[f"sound_{key}"] = cb.isChecked()

            save_api_keys(cfg)
            self._save_personalities_file()
            apply_theme_tokens(theme_val, custom_hex)

            main_win = self.window()
            if main_win and hasattr(main_win, "update_theme_styles"):
                main_win.update_theme_styles()
                if hasattr(main_win, "orb") and main_win.orb:
                    main_win.orb.web_view.page().runJavaScript(
                        f"if(window.updatePerformance)window.updatePerformance({self.sld_performance.value()});")
                    # 🆕 Actualizar estilo de logo en caliente
                    main_win.orb.sync_logo_style(self.cmb_logo_style.currentData())
                if hasattr(main_win, "_apply_widget_visibility"):
                    main_win._apply_widget_visibility()

            if close_after_save:
                QMessageBox.information(self, "OK", "Configuración guardada.")
                self.accept()
            else:
                NexusMessageBox(self, "OK", "Cambios aplicados.").exec()

        except Exception as e:
            NexusMessageBox(self, "Error", f"Error al guardar: {e}", is_error=True).exec()

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


class EmbeddedBrowserDialog(QDialog):
    def __init__(self, parent=None, url="https://google.com"):
        super().__init__(parent)
        self.setWindowTitle("NEXUS Web")
        self.setFixedSize(1200, 800)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Contenedor principal con fondo redondeado
        container = QFrame(self)
        container.setObjectName("WebContainer")
        container.setStyleSheet('''
            #WebContainer {
                background: rgba(15, 15, 20, 0.95);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
            }
        ''')
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(5, 5, 5, 5)

        # Barra superior con botón de cierre
        top_bar = QHBoxLayout()
        title = QLabel("NEXUS BROWSER")
        title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 14px; font-weight: bold; font-family: 'Segoe UI';")
        
        btn_close = QPushButton("YZ")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet('''
            QPushButton {
                background: rgba(255, 60, 60, 0.8);
                color: white;
                border-radius: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 60, 60, 1);
            }
        ''')
        btn_close.clicked.connect(self.close)

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(btn_close)
        
        c_layout.addLayout(top_bar)

        # Vista Web
        self.web = QWebEngineView()
        self.web.setUrl(QUrl(url))
        c_layout.addWidget(self.web)

        layout.addWidget(container)


class DraggableSticker(QLabel):
    """Sticker que se puede arrastrar a cualquier posición."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            # Clamp dentro del parent
            parent = self.parentWidget()
            if parent:
                max_x = parent.width() - self.width()
                max_y = parent.height() - self.height()
                new_pos.setX(max(0, min(new_pos.x(), max_x)))
                new_pos.setY(max(0, min(new_pos.y(), max_y)))
            self.move(new_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        # Guardar posición
        try:
            from memory.config_manager import load_api_keys, save_api_keys
            cfg = load_api_keys()
            cfg["sticker_pos_x"] = self.x()
            cfg["sticker_pos_y"] = self.y()
            save_api_keys(cfg)
        except Exception:
            pass
        super().mouseReleaseEvent(event)


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
        self.setWindowTitle("NEXUS-AI-HUD")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)

        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            ci = cfg.get("nexus_app_icon", "")
            if ci and Path(ci).exists(): 
                self.setWindowIcon(QIcon(ci))
            else:
                ip = get_bundled_path("assets", "nexus_icono.ico")
                if ip.exists(): 
                    self.setWindowIcon(QIcon(str(ip)))
        except Exception: 
            pass

        # ═══════════════════════════════════════════════════════════════
        # ✅ CREAR WIDGETS DE FONDO Y STICKER (ANTES DE update_theme_styles)
        # ═══════════════════════════════════════════════════════════════
        self.lbl_bg_image = QLabel(self.central_widget)
        self.lbl_bg_image.lower()
        self.lbl_bg_image.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_bg_image.setStyleSheet("background:transparent;")
        self.lbl_bg_image.hide()

        self.lbl_sticker = DraggableSticker(self.central_widget)
        self.lbl_sticker.setStyleSheet("background:transparent;")
        self.lbl_sticker.hide()

        try:
           from memory.config_manager import load_api_keys
           _cfg = load_api_keys()
           _star_variant = _cfg.get("nexus_star_variant", "estrellas")

           _pro_widgets = _cfg.get("pro_widget_styles", False)
        except Exception:
            _star_variant = "estrellas"

            _pro_widgets = False

        self.star_overlay = StarOverlayWidget(self.central_widget, variant=_star_variant)
        self.star_overlay.setGeometry(0, 0, self.central_widget.width(), self.central_widget.height())
        self.star_overlay.lower()
        self.lbl_bg_image.lower()

        # ─── WIDGETS PRINCIPALES ──────────────────────────────────────
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

        # ── WIDGETS FLOTANTES ───────────────────────────────────────
        self.spotify_float = FloatingSpotifyWidget(self.central_widget)
        self.media_float = FloatingMediaWidget(self.central_widget)
        self.weather_widget = WeatherWidget(self.central_widget)
        self.notif_panel = ShortcutsCard(self.central_widget)
        self.calendar_popup = HUDCalendarWidget(self.central_widget)

        # ─── SMART HOME WIDGET ──────────────────────────────────────
        self.smarthome_widget = SmartHomeWidget(self.central_widget)
        self.smarthome_widget.hide()

        # ── WIDGETS CLÁSICOS ────────────────────────────────────────
        self.files_panel = FilesPanel(self.ui, self.central_widget)
        self.notes_w = NotesWidget(self.central_widget)
        self.todo_w = TodoWidget(self.central_widget)

        # Ocultar widgets clásicos inicialmente
        self.files_panel.hide()
        self.notes_w.hide()
        self.todo_w.hide()
        
        # ─── APLICAR ESTILOS PRO ────────────────────────────────────
        if getattr(self, "_pro_widgets_enabled", False) or locals().get("_pro_widgets", False):
            try:
                from PyQt6.QtWidgets import QGraphicsDropShadowEffect
                from PyQt6.QtGui import QColor
                glow_color = QColor(C_PRI) if 'C_PRI' in globals() else QColor(0, 255, 204)
                glow_color.setAlphaF(0.6)
                
                widgets_to_glow = [
                    self.clock_w, self.sys_monitor, self.weather_widget, 
                    self.notif_panel, self.calendar_popup, self.files_panel, 
                    self.notes_w, self.todo_w
                ]
                
                for w in widgets_to_glow:
                    shadow = QGraphicsDropShadowEffect()
                    shadow.setBlurRadius(25)
                    shadow.setColor(glow_color)
                    shadow.setOffset(0, 0)
                    w.setGraphicsEffect(shadow)
            except Exception as e:
                print("Error aplicando estilos PRO:", e)

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
        
        # ✅ AHORA SÍ, LLAMAR A update_theme_styles (DESPUÉS de crear los widgets)
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
        self.media_worker.timeline_updated.connect(self.media_float.update_timeline)
        self.media_float.seek_requested.connect(self.media_worker.seek)
        self.media_worker.start()

        # Aplicar visibilidad inicial de widgets
        QTimer.singleShot(500, self._apply_widget_visibility)
        QTimer.singleShot(200, self._force_bg_load)

        # Habilitar mouse tracking para el redimensionamiento del HUD
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)

    # ═══════════════════════════════════════════════════════════════
    #  📌 AQUÍ VA EL MÉTODO - DENTRO DE LA CLASE
    # ═══════════════════════════════════════════════════════════════
    def create_smarthome_widget(self):
        """Crea y configura el widget Smart Home si no existe."""
        if not hasattr(self, "smarthome_widget") or self.smarthome_widget is None:
            self.smarthome_widget = SmartHomeWidget(self.central_widget)
            self.smarthome_widget.hide()
        return self.smarthome_widget

    # ─── MÉTODOS EXISTENTES ─────────────────────────────────────────
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

        # ── WIDGETS CLÁSICOS ─

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
        if event is not None: 
            super().resizeEvent(event)
        W = self.central_widget.width()
        H = self.central_widget.height()

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, W, H), 18.0, 18.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

        
        if hasattr(self, "lbl_bg_image") and self.lbl_bg_image.isVisible():
            self.lbl_bg_image.setGeometry(0, 0, W, H)
            self.lbl_bg_image.lower()

        # ═══════════════════════════════════════════════════════════════
        # CARGA DE IMAGEN DE FONDO
        # ═══════════════════════════════════════════════════════════════
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            bg_img = cfg.get("nexus_bg_image", "")
            if bg_img and Path(bg_img).exists():
                from PyQt6.QtGui import QPixmap, QMovie
                if str(bg_img).lower().endswith(".gif"):
                    if not hasattr(self, "_current_bg_movie"):
                        movie = QMovie(bg_img)
                        movie.setScaledSize(QSize(W, H))
                        self.lbl_bg_image.setMovie(movie)
                        movie.start()
                        self._current_bg_movie = movie
                    else:
                        self._current_bg_movie.setScaledSize(QSize(W, H))
                else:
                    pix = QPixmap(bg_img)
                    if not pix.isNull():
                        scaled = pix.scaled(W, H, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                        self.lbl_bg_image.setPixmap(scaled)
                self.lbl_bg_image.show()
        except Exception:
            pass
        if hasattr(self, "star_overlay"):
            self.star_overlay.setGeometry(0, 0, W, H)   
            try:
                from memory.config_manager import load_api_keys
                _cfg_star = load_api_keys()
                self.star_overlay.set_variant(_cfg_star.get("nexus_star_variant", "estrellas"))
                if _cfg_star.get("nexus_stars", False):
                    self.star_overlay.show()
                else:
                    self.star_overlay.hide()
            except Exception:
                pass
            
            

        if hasattr(self, "settings_overlay") and self.settings_overlay:
            self.settings_overlay.setGeometry(0, 0, W, H)

        if hasattr(self, "orb"):
            self.orb.setGeometry(8, 8, W - 16, H - 16)
        
        if hasattr(self, "clock_w"):
            self.clock_w.setGeometry(28, 28, 320, 70)
        
        if hasattr(self, "top_right_dock"):
            self.top_right_dock.setGeometry(W - 120, 14, 88, 60)
        
        if hasattr(self, "sys_monitor"):
            self.sys_monitor.setGeometry(W - 130, 80, 100, 110)
        
        if hasattr(self, "bottom_left_dock"):
            self.bottom_left_dock.setGeometry(28, H - 62, 140, 46)
        
        if hasattr(self, "notif_panel"):
            w = self.notif_panel.width()
            h = self.notif_panel.height()
            x = 28
            y = H - 72 - h 
            y = max(y, 20)
            self.notif_panel.setGeometry(x, y, w, h)
        
        if hasattr(self, "calendar_popup"):
            self.calendar_popup.setGeometry(50, H - 310, 230, 190)
        
        dock_w = 140
        dock_h = 46
        if hasattr(self, "bottom_dock"):
            self.bottom_dock.setGeometry((W - dock_w) // 2, H - 62, dock_w, dock_h)
        
        chat_w = 300
        if hasattr(self, "chat_bar"):
            self.chat_bar.setFixedWidth(chat_w)
            self.chat_bar.setGeometry((W - chat_w) // 2, H - 114, chat_w, 44)
        
        if hasattr(self, "pro_badge"):
            self.pro_badge.setGeometry(W - 100, H - 30, 100, 22)
        
        if hasattr(self, "txt_console"):
            self.txt_console.setGeometry(80, H - 168, W - 160, 50)

        # Posicionar widgets flotantes solo si no se han movido manualmente
        if not hasattr(self, "_spotify_positioned"):
            if hasattr(self, "spotify_float"):
                self.spotify_float.move((W - 280) // 2 + 80, H // 2 - 120)
            self._spotify_positioned = True
            
            if hasattr(self, "media_float"):
                self.media_float.move((W - 280) // 2 + 80, H // 2)

        # Sticker
        if hasattr(self, "_sticker_path") and self._sticker_path and hasattr(self, "lbl_sticker") and self.lbl_sticker.isVisible():
            sw = getattr(self, "_sticker_w", 100)
            sh = getattr(self, "_sticker_h", 100)
            sx = int((W - sw) * 0.5)
            sy = int((H - sh) * 0.5)
            self.lbl_sticker.setGeometry(sx, sy, sw, sh)

        # ✅ lower() CON VERIFICACIONES
        if hasattr(self, "lbl_bg_image"):
            self.lbl_bg_image.lower()

            # 🔥 NUEVO: Re-escalar imagen de fondo al redimensionar
            bg_img = None
            try:
                from memory.config_manager import load_api_keys
                cfg = load_api_keys()
                bg_img = cfg.get("nexus_bg_image", "")
            except:
                pass  

            if bg_img and Path(bg_img).exists():
                from PyQt6.QtGui import QPixmap, QMovie
                if str(bg_img).lower().endswith(".gif"):
                    # Re-escalar GIF en resize
                    if hasattr(self, "_current_bg_movie") and self._current_bg_movie:
                        self._current_bg_movie.setScaledSize(QSize(W, H))
                else:
                    # Re-escalar imagen estática
                    pix = QPixmap(bg_img)
                    if not pix.isNull():
                        scaled_pix = pix.scaled(
                            W, H,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.lbl_bg_image.setPixmap(scaled_pix)   
        if hasattr(self, "orb"):
            self.orb.lower()
        
        # ✅ raise() CON VERIFICACIONES - SOLUCIÓN PARA EL ERROR
        widgets_to_raise = [
            getattr(self, 'clock_w', None),
            getattr(self, 'top_right_dock', None),
            getattr(self, 'sys_monitor', None),
            getattr(self, 'bottom_left_dock', None),
            getattr(self, 'notif_panel', None),
            getattr(self, 'calendar_popup', None),
            getattr(self, 'bottom_dock', None),
            getattr(self, 'chat_bar', None),
            getattr(self, 'spotify_float', None),
            getattr(self, 'txt_console', None),
            getattr(self, 'pro_badge', None),
            getattr(self, 'lbl_sticker', None),
            getattr(self, 'weather_widget', None),
            getattr(self, 'todo_w', None),
            getattr(self, 'notes_w', None),
            getattr(self, 'files_panel', None),
            getattr(self, 'smarthome_widget', None),  # ← Agregar el nuevo widget
        ]
        for w in widgets_to_raise:
            if w is not None:
                try:
                    w.raise_()
                except Exception:
                    pass  # Ignorar errores en raise

    def update_theme_styles(self):
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            apply_theme_tokens(cfg.get("nexus_theme", "gold"), cfg.get("nexus_custom_theme_color", ""))
            global FONT_FAMILY
            FONT_FAMILY = cfg.get("nexus_font_family", "Century Gothic")
            QApplication.instance().setFont(QFont(FONT_FAMILY))

            ai_name = cfg.get("ai_name", "").strip().upper() or "◉ NEXUS"
            if "." not in ai_name and len(ai_name) > 1 and " " not in ai_name:
                ai_name = ".".join(list(ai_name)) + "."
            self.pro_badge.update_text(ai_name)

            bg_img = cfg.get("nexus_bg_image", "")
            if bg_img and Path(bg_img).exists():
                from PyQt6.QtGui import QPixmap, QMovie
                from PyQt6.QtWidgets import QGraphicsOpacityEffect

                widget_w = self.lbl_bg_image.width()
                widget_h = self.lbl_bg_image.height()

                # Si el widget no tiene tamaño aún, usar el tamaño de la ventana

                if widget_w == 0 or widget_h == 0:
                    widget_w = self.width()
                    widget_h = self.height()
                
                # 🔥 ESCALADO PARA 4K - MANTENER PROPORCIÓN
                if str(bg_img).lower().endswith(".gif"):
                    movie = QMovie(bg_img)
                    # Escalar el GIF al tamaño del widget manteniendo proporción
                    movie.setScaledSize(QSize(widget_w, widget_h))
                    self.lbl_bg_image.setMovie(movie)
                    self.lbl_bg_image.show()
                    movie.start()
                    self._current_bg_movie = movie
                else:
                    pix = QPixmap(bg_img)
                    if not pix.isNull():
                        # 🔥 ESCALAR MANTENIENDO PROPORCIÓN (Cover)
                        scaled_pix = pix.scaled(
                            widget_w, 
                            widget_h,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,  # 🔥 MODO COVER
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.lbl_bg_image.setPixmap(scaled_pix)
                        self.lbl_bg_image.show()
                        if hasattr(self, "_current_bg_movie"):
                            self._current_bg_movie = None
                    else:
                        self.lbl_bg_image.clear()
                        self.lbl_bg_image.hide()
                        
                    # Opacidad

                    oe = QGraphicsOpacityEffect(self)
                    oe.setOpacity(float(cfg.get("nexus_bg_opacity", 0.85)))
                    self.lbl_bg_image.setGraphicsEffect(oe)
            else:
                self.lbl_bg_image.clear(); self.lbl_bg_image.hide()
                if hasattr(self, "_current_bg_movie"):
                    self._current_bg_movie = None

            # Estrellitas Flotantes
            if hasattr(self, "star_overlay"):
                star_variant = cfg.get("nexus_star_variant", "estrellas")
                self.star_overlay.set_variant(star_variant)
                if cfg.get("nexus_stars", False):
                    self.star_overlay.show()
                else:
                    self.star_overlay.hide()

            # Sticker
            sticker_path = cfg.get("nexus_sticker_path", "")
            self._sticker_path = sticker_path
            self._sticker_w = int(cfg.get("nexus_sticker_w", 100))
            self._sticker_h = int(cfg.get("nexus_sticker_h", 100))
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

        # Lista de widgets con verificación de existencia
        widgets = [
            getattr(self, 'orb', None),
            getattr(self, 'clock_w', None),
            getattr(self, 'top_right_dock', None),
            getattr(self, 'sys_monitor', None),
            getattr(self, 'bottom_left_dock', None),
            getattr(self, 'notif_panel', None),
            getattr(self, 'calendar_popup', None),
            getattr(self, 'bottom_dock', None),
            getattr(self, 'chat_bar', None),
            getattr(self, 'spotify_float', None),
            getattr(self, 'txt_console', None),
            getattr(self, 'pro_badge', None),
            getattr(self, 'lbl_sticker', None),
            getattr(self, 'weather_widget', None),
            getattr(self, 'todo_w', None),
            getattr(self, 'notes_w', None),
            getattr(self, 'files_panel', None),
            getattr(self, 'smarthome_widget', None),
        ]

        for w in widgets:
            if w is not None:
                try:
                    # store visibility state and hide
                    self._hud_widgets_states[w] = w.isVisible()
                    w.hide()
                except Exception:
                    pass

        W = self.central_widget.width()
        H = self.central_widget.height()
        self.settings_overlay.setGeometry(0, 0, W, H)
        self.settings_overlay.load_settings()
        self.settings_overlay.show()
        self.settings_overlay.raise_()
        self._active_settings_dialog = self.settings_overlay

    def _open_folder(self):
        try:
            ruta = os.path.join(os.path.expanduser("~"), "Downloads", "Nexus_Downloads")
            os.makedirs(ruta, exist_ok=True); os.startfile(ruta)
        except Exception: pass

    def animate_show_widget(self, widget):
        # Grab target position
        target_pos = widget.frameGeometry().topLeft()
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
            play_sound("close")
            self.bottom_dock.btn_chat.set_active(False, "#ffffff")
        else:
            W = self.central_widget.width(); H = self.central_widget.height()
            self.chat_bar.setGeometry((W - 300) // 2, H - 114, 300, 44)
            self.animate_show_widget(self.chat_bar)
            self.chat_bar.inp.setFocus()
            play_sound("open")  # 🆕 Sonido al abrir
            self.bottom_dock.btn_chat.set_active(True, "#ffffff")

    def _toggle_notification_panel(self):
        if self.notif_panel.isVisible():
            self.notif_panel.hide()
            play_sound("close")
            self.bottom_left_dock.set_notification(False)
        else:
            self.resizeEvent(None)
            self.animate_show_widget(self.notif_panel)
            play_sound("open")
            self.bottom_left_dock.set_notification(False)

    def _toggle_calendar(self):
        if self.calendar_popup.isVisible():
            self.calendar_popup.hide()
            play_sound("close")
        else:
            self.resizeEvent(None)
            self.animate_show_widget(self.calendar_popup)
            play_sound("open") 

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
            except ImportError: NexusMessageBox(self, "Piloto Gestual", "MediaPipe no instalado.", is_error=True).exec(); return
            try:
                from actions.gesture_engine import GestureTrackingThread
                cam_idx = 0
                try:
                    from memory.config_manager import load_api_keys
                    cam_idx = int(load_api_keys().get("camera_device", 0))
                except Exception: pass
                self._gesture_thread = GestureTrackingThread(camera_index=cam_idx, theme_bgr=hex_to_bgr(C_PRI), text_bgr=hex_to_bgr(C_TEXT))
                self._gesture_thread.start()
            except Exception as e: NexusMessageBox(self, "Error", f"Error al iniciar cámara:\n{e}", is_error=True).exec(); return
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
        print(f"[Notificación Silenciada] {title}: {body}")

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
        ip = get_bundled_path("assets", "nexus_icono.ico")
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

    def _force_bg_load(self):
        """Forzar carga de imagen de fondo."""
        try:
            from memory.config_manager import load_api_keys
            cfg = load_api_keys()
            bg_img = cfg.get("nexus_bg_image", "")
            if bg_img and Path(bg_img).exists():
                self.resizeEvent(None)
        except Exception:
            pass

    def closeEvent(self, event):
        if getattr(self, "_force_close", False):
            self.stop_gesture_thread(); event.accept()
        else:
            event.ignore(); self.hide()
            if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
                from PyQt6.QtWidgets import QSystemTrayIcon
                self.tray_icon.showMessage("NEXUS AI", "Sigo activo en segundo plano.",
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
#  MockRoot + NexusUI
# ═══════════════════════════════════════════════════════════════════════════

class MockRoot:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
    def mainloop(self): sys.exit(self.qapp.exec())
    def after(self, ms: int, func): QTimer.singleShot(ms, func)


class NexusUI:
    def __init__(self, face_path=""):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.root = MockRoot(self.app)
        self.muted = False
        self.current_file = ""
        self.on_text_command = None
        self.on_stop_command = None
        self.on_config_saved = None
        self.nexus_response_buffer = ""
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
                self.nexus_response_buffer = ""; self._win.txt_console.setText(text)
            elif text.startswith("Tú:"):
                self.last_user_message = text
                disp = self.last_user_message
                if self.nexus_response_buffer: disp += f"\nNEXUS: {self.nexus_response_buffer}"
                self._win.txt_console.setText(disp)
            elif text.startswith("NEXUS:"):
                clean = text.replace("NEXUS:", "").strip()
                if clean:
                    self.nexus_response_buffer = clean
                    disp = f"NEXUS: {self.nexus_response_buffer}"
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

    def clear_nexus_response(self):
        def _do():
            self.nexus_response_buffer = ""
            self._win.txt_console.setText(self.last_user_message if self.last_user_message else "")
        QTimer.singleShot(0, _do)

    def stream_nexus_chunk(self, chunk: str):
        def _do():
            text = chunk.replace("NEXUS:", "").strip()
            if text:
                if self.nexus_response_buffer: self.nexus_response_buffer += " " + text
                else: self.nexus_response_buffer = text
                disp = f"NEXUS: {self.nexus_response_buffer}"
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
            shortcut_path = os.path.join(startup_dir, 'NEXUS AI.lnk')
            current_dir = os.path.abspath(os.path.dirname(__file__))
            target_vbs = os.path.join(current_dir, "Iniciar NEXUS Beta.vbs")
            icon_path = os.path.join(current_dir, "assets", "nexus_icono.ico")
            if not os.path.exists(target_vbs): return
            ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_path}');"
                  f"$s.TargetPath='{target_vbs}';$s.WorkingDirectory='{current_dir}';"
                  f"$s.IconLocation='{icon_path}';$s.Save()")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e: print(f"[STARTUP] {e}")

        """
student_mode_ui.py — Reemplazo de la sección "Student Mode Workers + Window" de ui.py

CÓMO INSTALARLO
────────────────
1. En ui.py, BORRA por completo estas clases (están todas seguidas al final del archivo):
     - DocumentRenderWorker
     - PdfToWordWorker
     - QualityReportWorker
     - ApaVerifyWorker
     - StudentModeWindow
   (busca el comentario "Student Mode Workers + Window" — es justo esa sección hasta el
   final del archivo).

2. Pega TODO el contenido de este archivo en su lugar (al final de ui.py), dejando arriba
   intactas las clases NexusUI, MainWindow, etc.

3. Instala las dependencias nuevas que usa el conversor universal:
     pip install pdf2docx python-docx openpyxl python-pptx pypdf comtypes

Este archivo asume que ya existen en ui.py (más arriba en el mismo módulo): HAS_QTA, qta,
C_PRI, C_PRI_DIM, C_BG, C_TEXT, C_BORDER, apply_glass_shadow, y los imports de PyQt6 ya
usados en el resto del archivo (QThread, pyqtSignal, etc.).
"""

from actions.student_mode import (
    extract_text,
    convert_file,
    get_available_targets,
    paraphrase_text,
    check_grammar_and_style,
    verify_apa_full,
    ask_consulta,
    translate_text,
    CONSULTA_SYSTEM_PROMPTS,
    LANGUAGES,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Workers (QThread) — cada pestaña tiene el suyo para no congelar la UI
# ═══════════════════════════════════════════════════════════════════════════

class DocumentRenderWorker(QThread):
    """Renderiza páginas de un PDF/DOCX como imágenes para la vista previa de APA 7."""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(list, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        import os
        import fitz
        from PyQt6.QtGui import QImage
        temp_pdf = None
        try:
            self.status.emit("Preparando…")
            self.progress.emit(10)
            ext = os.path.splitext(self.file_path)[1].lower()
            pdf = self.file_path
            if ext == ".docx":
                self.status.emit("Convirtiendo Word a PDF…")
                self.progress.emit(25)
                try:
                    from actions.student_mode import convert_file
                    pdf = convert_file(self.file_path, "pdf")
                    temp_pdf = pdf
                except Exception as we:
                    self.finished.emit([], f"Error Word→PDF: {we}")
                    return
            self.status.emit("Renderizando páginas…")
            self.progress.emit(50)
            d = fitz.open(pdf)
            pages = []
            tot = len(d)
            for i in range(tot):
                self.status.emit(f"Página {i + 1}/{tot}…")
                p = d.load_page(i)
                pix = p.get_pixmap(dpi=120)
                qi = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
                pages.append(qi)
                self.progress.emit(50 + int((i + 1) / tot * 40))
            d.close()
            if temp_pdf and os.path.exists(temp_pdf):
                try:
                    os.remove(temp_pdf)
                except Exception:
                    pass
            self.progress.emit(100)
            self.finished.emit(pages, "")
        except Exception as e:
            self.finished.emit([], f"Error: {e}")


class ConversionWorker(QThread):
    """Worker genérico para el Convertidor Universal (PDF/Word/Excel/PowerPoint/TXT/CSV)."""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str, str)  # (ruta_destino, error)

    def __init__(self, source_path, target_format):
        super().__init__()
        self.source_path = source_path
        self.target_format = target_format

    def run(self):
        try:
            def _cb(status, pct):
                self.status.emit(status)
                self.progress.emit(pct)
            dest = convert_file(self.source_path, self.target_format, progress_cb=_cb)
            self.finished.emit(dest, "")
        except Exception as e:
            self.finished.emit("", str(e))


class ParaphraseWorker(QThread):
    status = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, str)  # (resultado, error)

    def __init__(self, text, intensity):
        super().__init__()
        self.text = text
        self.intensity = intensity

    def run(self):
        try:
            def _cb(status, pct):
                self.status.emit(status)
                self.progress.emit(pct)
            result = paraphrase_text(self.text, intensity=self.intensity, progress_cb=_cb)
            self.finished.emit(result, "")
        except Exception as e:
            self.finished.emit("", str(e))


class GrammarWorker(QThread):
    status = pyqtSignal(str)
    finished = pyqtSignal(str, str)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            self.status.emit("Analizando ortografía y gramática…")
            html = check_grammar_and_style(self.text)
            self.finished.emit(html, "")
        except Exception as e:
            self.finished.emit("", str(e))


class ApaVerifyWorker(QThread):
    status = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, text, file_path):
        super().__init__()
        self.text = text
        self.file_path = file_path

    def run(self):
        try:
            def _cb(status, pct):
                self.status.emit(status)
                self.progress.emit(pct)
            report = verify_apa_full(self.text, self.file_path, progress_cb=_cb)
            self.finished.emit(report)
        except Exception as e:
            self.finished.emit(f"Error: {e}")


class QualityReportWorker(QThread):
    status = pyqtSignal(str)
    finished = pyqtSignal(str)

    def __init__(self, text, filename):
        super().__init__()
        self.text = text
        self.filename = filename

    def run(self):
        try:
            self.status.emit("Llamando a Artemisa…")
            from google import genai
            from actions.student_mode import _get_api_key, GEMINI_MODEL, _clean_html_fences
            client = genai.Client(api_key=_get_api_key())
            prompt = (
                "Actúa como revisor académico senior. Analiza el texto del documento "
                f"'{self.filename}' y genera un REPORTE DE CALIDAD en HTML estilizado con fondo "
                "oscuro. Incluye también errores de ortografía/gramática si los detectas. Sin "
                "bloques markdown.\n\nTEXTO:\n\n" + self.text[:9000]
            )
            resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            self.finished.emit(_clean_html_fences(resp.text.strip()))
        except Exception as e:
            self.finished.emit(f"<div style='color:#ff3b30;'>Error: {e}</div>")


class ConsultaWorker(QThread):
    status = pyqtSignal(str)
    finished = pyqtSignal(str, str)  # (respuesta_html, error)

    def __init__(self, question, mode, history):
        super().__init__()
        self.question = question
        self.mode = mode
        self.history = history

    def run(self):
        try:
            def _cb(status, pct):
                self.status.emit(status)
            answer = ask_consulta(self.question, mode=self.mode, history=self.history, progress_cb=_cb)
            self.finished.emit(answer, "")
        except Exception as e:
            self.finished.emit("", str(e))


class TranslateWorker(QThread):
    status = pyqtSignal(str)
    finished = pyqtSignal(str, str)

    def __init__(self, text, source_lang, target_lang):
        super().__init__()
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang

    def run(self):
        try:
            def _cb(status, pct):
                self.status.emit(status)
            result = translate_text(self.text, self.source_lang, self.target_lang, progress_cb=_cb)
            self.finished.emit(result, "")
        except Exception as e:
            self.finished.emit("", str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  StudentModeWindow — 6 pestañas
# ═══════════════════════════════════════════════════════════════════════════

class StudentModeWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NEXUS — Herramientas Académicas")
        self.resize(980, 680)
        self.setMinimumSize(880, 600)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.loaded_apa_file = ""
        self.loaded_quality_text = ""
        self.loaded_quality_file = ""
        self.loaded_conversion_file = ""
        self.consulta_history = []
        self.drag_pos = None
        self.init_ui()

    # ── Drag de ventana sin bordes ──────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self.drag_pos:
            self.move(self.pos() + e.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self.drag_pos = None

    # ── UI principal ─────────────────────────────────────────────────────
    def init_ui(self):
        ml = QVBoxLayout(self)
        ml.setContentsMargins(12, 12, 12, 12)
        bg = QFrame(self)
        bg.setObjectName("StuBg")
        bg.setStyleSheet(
            "QFrame#StuBg{background:rgba(15,23,42,0.90);border:1px solid rgba(255,255,255,0.10);border-radius:12px;}"
        )
        bl = QVBoxLayout(bg)
        bl.setContentsMargins(15, 15, 15, 15)
        ml.addWidget(bg)

        hdr = QHBoxLayout()
        ic = QLabel()
        if HAS_QTA:
            ic.setPixmap(qta.icon("fa5s.graduation-cap", color=C_PRI).pixmap(28, 28))
        hdr.addWidget(ic)
        tl = QLabel(" MODO ESTUDIANTE")
        tl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        tl.setStyleSheet(f"color:{C_PRI};letter-spacing:1px;")
        hdr.addWidget(tl)
        hdr.addStretch()
        for txt, fn in [("–", self.showMinimized), ("×", self.close)]:
            b = QPushButton(txt)
            b.setFixedSize(28, 28)
            b.setStyleSheet("QPushButton{border:none;}QPushButton:hover{background:rgba(255,255,255,0.12);border-radius:14px;}")
            b.clicked.connect(fn)
            hdr.addWidget(b)
        bl.addLayout(hdr)

        self.tabs = QTabWidget()
        bl.addWidget(self.tabs)

        self._build_tab_paraphrase()
        self._build_tab_converter()
        self._build_tab_apa()
        self._build_tab_quality()
        self._build_tab_consulta()
        self._build_tab_translate()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        bl.addWidget(sep)
        sbr = QHBoxLayout()
        sbr.setContentsMargins(8, 2, 8, 2)
        self.global_status_label = QLabel("Estado: Listo")
        self.global_status_label.setStyleSheet(f"color:{C_TEXT};font-size:11px;")
        sbr.addWidget(self.global_status_label)
        sbr.addStretch()
        self.global_progress_bar = QProgressBar()
        self.global_progress_bar.setRange(0, 100)
        self.global_progress_bar.setFixedSize(200, 10)
        self.global_progress_bar.setStyleSheet(
            f"QProgressBar{{background:rgba(0,0,0,0.4);border:1px solid {C_BORDER};border-radius:4px;}}"
            f"QProgressBar::chunk{{background:{C_PRI};border-radius:4px;}}"
        )
        sbr.addWidget(self.global_progress_bar)
        bl.addLayout(sbr)

        self.update_style()
    

    def update_style(self):
        self.setStyleSheet(f"""
        QLabel{{color:{C_TEXT};font-family:'Segoe UI';}}
        QPushButton{{background:{C_PRI_DIM};color:{C_TEXT};border:1px solid {C_BORDER};border-radius:8px;padding:8px;font-weight:bold;}}
        QPushButton:hoveSr{{background:{C_PRI};color:#0f0a02;}}
        QPushButton:disabled{{background:rgba(128,128,128,0.1);color:rgba(255,255,255,0.3);border:1px solid rgba(128,128,128,0.2);}}
        QTextEdit,QTextBrowser,QLineEdit{{background:rgba(0,0,0,0.6);color:#fff;border:1px solid {C_BORDER};border-radius:8px;font-family:'Consolas';font-size:13px;padding:6px;}}
        QComboBox{{background:rgba(0,0,0,0.5);color:#fff;border:1px solid {C_BORDER};border-radius:8px;padding:6px;}}
        QComboBox QAbstractItemView{{background:rgb(20,20,28);color:#fff;selection-background-color:{C_PRI_DIM};}}
        QTabWidget::pane{{border:1px solid {C_BORDER};border-radius:10px;background:rgba(22,16,5,0.25);}}
        QTabBar::tab{{background:rgba(35,28,10,0.6);color:{C_TEXT};padding:10px 16px;border-radius:6px;border:1px solid {C_BORDER};margin-right:4px;}}
        QTabBar::tab:selected{{background:{C_PRI_DIM};border-bottom:2px solid {C_PRI};font-weight:bold;}}
        QScrollArea{{background:rgba(0,0,0,0.5);border:1px solid {C_BORDER};border-radius:8px;}}
        """)
        apply_glass_shadow(self)

    # ─────────────────────────────────────────────────────────────────
    #  TAB 1 — Parafraseo
    # ─────────────────────────────────────────────────────────────────
    def _build_tab_paraphrase(self):
        tg = QWidget()
        gl = QVBoxLayout(tg)
        gl.setContentsMargins(12, 12, 12, 12)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Intensidad:"))
        self.cmb_paraphrase_intensity = QComboBox()
        self.cmb_paraphrase_intensity.addItems(["ligero", "moderado", "intenso"])
        self.cmb_paraphrase_intensity.setCurrentText("moderado")
        top_row.addWidget(self.cmb_paraphrase_intensity)
        top_row.addStretch()
        self.btn_ghost_load_file = QPushButton(" Cargar desde archivo")
        if HAS_QTA:
            self.btn_ghost_load_file.setIcon(qta.icon("fa5s.file-import", color=C_TEXT))
        self.btn_ghost_load_file.clicked.connect(self._ghost_load_file)
        top_row.addWidget(self.btn_ghost_load_file)
        gl.addLayout(top_row)

        gl.addWidget(QLabel("Texto original:"))
        sp = QHBoxLayout()
        self.ghost_input = QTextEdit()
        self.ghost_input.setPlaceholderText("Pega aquí el texto original o carga un archivo…")
        self.ghost_output = QTextEdit()
        self.ghost_output.setPlaceholderText("Resultado parafraseado…")
        self.ghost_output.setReadOnly(True)
        sp.addWidget(self.ghost_input)
        sp.addWidget(self.ghost_output)
        gl.addLayout(sp)

        btn_row = QHBoxLayout()
        self.btn_ghost_run = QPushButton(" Parafrasear")
        if HAS_QTA:
            self.btn_ghost_run.setIcon(qta.icon("fa5s.ghost", color=C_TEXT))
        self.btn_ghost_run.clicked.connect(self.trigger_paraphrase_manually)
        btn_row.addWidget(self.btn_ghost_run)
        self.btn_ghost_copy = QPushButton(" Copiar resultado")
        self.btn_ghost_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.ghost_output.toPlainText()))
        btn_row.addWidget(self.btn_ghost_copy)
        gl.addLayout(btn_row)

        self.tabs.addTab(tg, qta.icon("fa5s.ghost", color=C_PRI) if HAS_QTA else QIcon(), "Parafraseo")

    def _ghost_load_file(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(
            self, "Cargar archivo", "", "Documentos (*.txt *.docx *.pdf *.xlsx *.pptx)"
        )
        if not fp:
            return
        text = extract_text(fp)
        if text.startswith("[Error"):
            QMessageBox.critical(self, "Error", text)
            return
        self.ghost_input.setPlainText(text)

    def trigger_paraphrase_manually(self):
        text = self.ghost_input.toPlainText().strip()
        if not text:
            return
        self.ghost_output.setPlainText("Procesando…")
        self.btn_ghost_run.setEnabled(False)
        intensity = self.cmb_paraphrase_intensity.currentText()
        self.paraphrase_worker = ParaphraseWorker(text, intensity)
        self.paraphrase_worker.status.connect(self.global_status_label.setText)
        self.paraphrase_worker.progress.connect(self.global_progress_bar.setValue)
        self.paraphrase_worker.finished.connect(self._paraphrase_finished)
        self.paraphrase_worker.start()

    def _paraphrase_finished(self, result, error):
        self.btn_ghost_run.setEnabled(True)
        if error:
            self.ghost_output.setPlainText(f"Error: {error}")
            QMessageBox.critical(self, "Error", error)
        else:
            self.ghost_output.setPlainText(result)
            self.global_status_label.setText("Parafraseo completado.")

    # ─────────────────────────────────────────────────────────────────
    #  TAB 2 — Convertidor Universal
    # ─────────────────────────────────────────────────────────────────
    def _build_tab_converter(self):
        tc = QWidget()
        cl = QVBoxLayout(tc)
        cl.setContentsMargins(20, 20, 20, 20)
        cl.setAlignment(Qt.AlignmentFlag.AlignTop)

        cl.addWidget(QLabel("Convierte entre Word, Excel, PowerPoint, PDF, TXT y CSV."))

        row1 = QHBoxLayout()
        self.conv_file_label = QLabel("Ningún archivo seleccionado")
        self.conv_file_label.setWordWrap(True)
        row1.addWidget(self.conv_file_label, 1)
        self.btn_conv_select = QPushButton(" Seleccionar archivo")
        if HAS_QTA:
            self.btn_conv_select.setIcon(qta.icon("fa5s.file-upload", color=C_TEXT))
        self.btn_conv_select.clicked.connect(self._conv_select_file)
        row1.addWidget(self.btn_conv_select)
        cl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Convertir a:"))
        self.cmb_conv_target = QComboBox()
        self.cmb_conv_target.setEnabled(False)
        row2.addWidget(self.cmb_conv_target)
        row2.addStretch()
        self.btn_conv_run = QPushButton(" Convertir")
        if HAS_QTA:
            self.btn_conv_run.setIcon(qta.icon("fa5s.exchange-alt", color=C_TEXT))
        self.btn_conv_run.setEnabled(False)
        self.btn_conv_run.clicked.connect(self._run_conversion)
        row2.addWidget(self.btn_conv_run)
        cl.addLayout(row2)

        self.conv_progress = QProgressBar()
        self.conv_progress.setRange(0, 100)
        self.conv_progress.setFixedHeight(10)
        self.conv_progress.setStyleSheet(
            f"QProgressBar{{background:rgba(255,255,255,0.10);border:none;border-radius:5px;}}"
            f"QProgressBar::chunk{{background:{C_PRI};border-radius:5px;}}"
        )
        cl.addWidget(self.conv_progress)

        self.conv_status_label = QLabel("Esperando…")
        cl.addWidget(self.conv_status_label)

        self.btn_conv_open_folder = QPushButton(" Abrir carpeta del resultado")
        self.btn_conv_open_folder.setEnabled(False)
        self.btn_conv_open_folder.clicked.connect(self._conv_open_folder)
        cl.addWidget(self.btn_conv_open_folder)

        note = QLabel(
            "Nota: las conversiones hacia PDF de Word/Excel/PowerPoint requieren tener Office "
            "instalado en este equipo (usan automatización COM, igual que el resto de NEXUS)."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:rgba(255,255,255,0.45);font-size:11px;font-style:italic;")
        cl.addWidget(note)
        cl.addStretch()

        self.tabs.addTab(tc, qta.icon("fa5s.file-export", color=C_PRI) if HAS_QTA else QIcon(), "Convertidor")

    def _conv_select_file(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo",
            "", "Documentos (*.pdf *.docx *.doc *.xlsx *.xls *.pptx *.ppt *.txt *.csv)"
        )
        if not fp:
            return
        self.loaded_conversion_file = fp
        self.conv_file_label.setText(f"Archivo: {fp}")
        targets = get_available_targets(fp)
        self.cmb_conv_target.clear()
        if targets:
            self.cmb_conv_target.addItems(targets)
            self.cmb_conv_target.setEnabled(True)
            self.btn_conv_run.setEnabled(True)
        else:
            self.cmb_conv_target.setEnabled(False)
            self.btn_conv_run.setEnabled(False)
            QMessageBox.warning(self, "Sin conversiones", "No hay formatos de destino soportados para este archivo.")
        self.btn_conv_open_folder.setEnabled(False)

    def _run_conversion(self):
        if not self.loaded_conversion_file:
            return
        target = self.cmb_conv_target.currentText()
        self.btn_conv_run.setEnabled(False)
        self.conv_progress.setValue(0)
        self.conv_status_label.setText("Iniciando…")
        self.conv_worker = ConversionWorker(self.loaded_conversion_file, target)
        self.conv_worker.status.connect(self.conv_status_label.setText)
        self.conv_worker.progress.connect(self.conv_progress.setValue)
        self.conv_worker.finished.connect(self._conversion_finished)
        self.conv_worker.start()

    def _conversion_finished(self, dest, error):
        self.btn_conv_run.setEnabled(True)
        if error:
            self.conv_status_label.setText("Error.")
            QMessageBox.critical(self, "Error de conversión", error)
            return
        self._last_conversion_dest = dest
        self.conv_status_label.setText(f"Completado: {dest}")
        self.btn_conv_open_folder.setEnabled(True)
        QMessageBox.information(self, "Éxito", f"Archivo generado:\n{dest}")

    def _conv_open_folder(self):
        import os
        dest = getattr(self, "_last_conversion_dest", "")
        if dest and os.path.exists(dest):
            os.startfile(os.path.dirname(dest))

    # ─────────────────────────────────────────────────────────────────
    #  TAB 3 — APA 7 (con vista previa y búsqueda de errores)
    # ─────────────────────────────────────────────────────────────────
    def _build_tab_apa(self):
        ta = QWidget()
        al = QVBoxLayout(ta)
        al.setContentsMargins(12, 12, 12, 12)

        ah = QHBoxLayout()
        ah.addWidget(QLabel("Verificador APA 7 (formato + citas + ortografía)"))
        ah.addStretch()
        self.btn_apa_load = QPushButton(" Cargar Doc")
        self.btn_apa_load.clicked.connect(self.load_apa_file_manually)
        ah.addWidget(self.btn_apa_load)
        al.addLayout(ah)

        self.apa_viewer = QScrollArea()
        self.apa_viewer.setWidgetResizable(True)
        avc = QWidget()
        avc.setStyleSheet("background:rgba(20,20,20,0.95);")
        self.apa_viewer_layout = QVBoxLayout(avc)
        self.apa_viewer_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.apa_placeholder = QLabel("Carga un PDF/DOCX para ver la vista previa")
        self.apa_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.apa_viewer_layout.addWidget(self.apa_placeholder)
        self.apa_viewer.setWidget(avc)

        asplit = QHBoxLayout()
        asplit.addWidget(self.apa_viewer)
        self.apa_output = QTextBrowser()
        asplit.addWidget(self.apa_output)
        al.addLayout(asplit)

        abl = QHBoxLayout()
        self.btn_apa_run = QPushButton(" Verificar APA 7 completo")
        self.btn_apa_run.clicked.connect(self.trigger_apa_manually)
        abl.addWidget(self.btn_apa_run)
        self.btn_apa_errors = QPushButton(" Buscar solo errores de ortografía/gramática")
        self.btn_apa_errors.clicked.connect(self.trigger_apa_grammar_only)
        abl.addWidget(self.btn_apa_errors)
        self.btn_apa_download = QPushButton(" Descargar")
        self.btn_apa_download.clicked.connect(self.download_apa_report)
        self.btn_apa_download.setEnabled(False)
        abl.addWidget(self.btn_apa_download)
        al.addLayout(abl)

        self.tabs.addTab(ta, qta.icon("fa5s.book", color=C_PRI) if HAS_QTA else QIcon(), "APA 7")

    def load_apa_file_manually(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(self, "Cargar Doc", "", "Documentos (*.pdf *.docx)")
        if not fp:
            return
        self.loaded_apa_file = fp
        self.global_status_label.setText("Cargando vista previa…")
        self.btn_apa_load.setEnabled(False)
        self.btn_apa_run.setEnabled(False)
        self.render_worker = DocumentRenderWorker(fp)
        self.render_worker.status.connect(self.global_status_label.setText)
        self.render_worker.progress.connect(self.global_progress_bar.setValue)
        self.render_worker.finished.connect(self.apa_file_rendered)
        self.render_worker.start()

    def apa_file_rendered(self, pages, error):
        self.btn_apa_load.setEnabled(True)
        self.btn_apa_run.setEnabled(True)
        if error:
            QMessageBox.critical(self, "Error", error)
            return
        while self.apa_viewer_layout.count():
            it = self.apa_viewer_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        from PyQt6.QtGui import QPixmap
        for qi in pages:
            l = QLabel()
            l.setPixmap(QPixmap.fromImage(qi))
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setStyleSheet(
                "border:1px solid rgba(245,158,11,0.45);border-radius:4px;background:white;margin:12px;padding:2px;"
            )
            self.apa_viewer_layout.addWidget(l)
        self.global_status_label.setText("Documento cargado.")
        self.global_progress_bar.setValue(100)

    def trigger_apa_manually(self):
        if not self.loaded_apa_file:
            QMessageBox.warning(self, "Aviso", "Carga primero un documento.")
            return
        text = extract_text(self.loaded_apa_file)
        self.apa_output.setPlainText("Analizando…")
        self.btn_apa_run.setEnabled(False)
        self.apa_verify_worker = ApaVerifyWorker(text, self.loaded_apa_file)
        self.apa_verify_worker.status.connect(self.global_status_label.setText)
        self.apa_verify_worker.progress.connect(self.global_progress_bar.setValue)
        self.apa_verify_worker.finished.connect(self.apa_verification_finished)
        self.apa_verify_worker.start()

    def apa_verification_finished(self, report):
        self.apa_output.setPlainText(report)
        self.btn_apa_run.setEnabled(True)
        if report.startswith("Error"):
            self.btn_apa_download.setEnabled(False)
        else:
            self.global_status_label.setText("Reporte APA generado.")
            self.global_progress_bar.setValue(100)
            self.btn_apa_download.setEnabled(True)

    def trigger_apa_grammar_only(self):
        if not self.loaded_apa_file:
            QMessageBox.warning(self, "Aviso", "Carga primero un documento.")
            return
        text = extract_text(self.loaded_apa_file)
        self.apa_output.setPlainText("Buscando errores de ortografía y gramática…")
        self.btn_apa_errors.setEnabled(False)
        self.grammar_worker = GrammarWorker(text)
        self.grammar_worker.status.connect(self.global_status_label.setText)
        self.grammar_worker.finished.connect(self._apa_grammar_finished)
        self.grammar_worker.start()

    def _apa_grammar_finished(self, html, error):
        self.btn_apa_errors.setEnabled(True)
        if error:
            QMessageBox.critical(self, "Error", error)
            return
        self.apa_output.setHtml(html)
        self.btn_apa_download.setEnabled(True)
        self.global_status_label.setText("Revisión de errores completada.")

    def download_apa_report(self):
        try:
            from memory.config_manager import BASE_DIR
            import time, os
            d = os.path.join(BASE_DIR, "Descargas_Nexus")
            os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, f"APA_{int(time.time())}.html")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(self.apa_output.toHtml())
            QMessageBox.information(self, "OK", f"Guardado en:\n{d}")
            os.startfile(d)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ─────────────────────────────────────────────────────────────────
    #  TAB 4 — Calidad académica
    # ─────────────────────────────────────────────────────────────────
    def _build_tab_quality(self):
        tq = QWidget()
        ql = QVBoxLayout(tq)
        ql.setContentsMargins(12, 12, 12, 12)
        qh = QHBoxLayout()
        qh.addWidget(QLabel("Evaluador de Rigor Académico y Errores"))
        qh.addStretch()
        self.btn_q_load = QPushButton(" Cargar Doc")
        self.btn_q_load.clicked.connect(self.load_quality_file_manually)
        qh.addWidget(self.btn_q_load)
        ql.addLayout(qh)
        self.quality_file_label = QLabel("Ningún archivo")
        ql.addWidget(self.quality_file_label)
        self.quality_output = QTextBrowser()
        self.quality_output.setStyleSheet(
            "background:rgba(20,20,20,0.95);border:1px solid rgba(255,255,255,0.10);border-radius:8px;"
        )
        ql.addWidget(self.quality_output)
        qbl = QHBoxLayout()
        self.btn_q_run = QPushButton(" Generar Reporte")
        self.btn_q_run.clicked.connect(self.run_quality_report_manually)
        self.btn_q_run.setEnabled(False)
        qbl.addWidget(self.btn_q_run)
        self.btn_q_download = QPushButton(" Descargar HTML")
        self.btn_q_download.clicked.connect(self.download_quality_report)
        self.btn_q_download.setEnabled(False)
        qbl.addWidget(self.btn_q_download)
        ql.addLayout(qbl)
        self.tabs.addTab(tq, qta.icon("fa5s.award", color=C_PRI) if HAS_QTA else QIcon(), "Calidad")

    def load_quality_file_manually(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(
            self, "Cargar Doc", "", "Documentos (*.txt *.pdf *.docx *.xlsx *.pptx)"
        )
        if not fp:
            return
        text = extract_text(fp)
        if not text or text.startswith("[Error"):
            QMessageBox.critical(self, "Error", "No se pudo extraer texto.")
            return
        self.loaded_quality_text = text
        self.loaded_quality_file = fp
        self.quality_file_label.setText(f"Archivo: {fp}")
        self.btn_q_run.setEnabled(True)

    def run_quality_report_manually(self):
        if not self.loaded_quality_text:
            return
        self.btn_q_run.setEnabled(False)
        self.global_status_label.setText("Generando reporte…")
        self.global_progress_bar.setValue(25)
        from pathlib import Path
        self.quality_worker = QualityReportWorker(self.loaded_quality_text, Path(self.loaded_quality_file).name)
        self.quality_worker.status.connect(lambda s: self.global_status_label.setText(f"Calidad: {s}"))
        self.quality_worker.finished.connect(self.quality_report_finished)
        self.quality_worker.start()

    def quality_report_finished(self, html):
        self.btn_q_run.setEnabled(True)
        self.quality_output.setHtml(html)
        if "Error" in html:
            self.global_progress_bar.setValue(0)
            self.btn_q_download.setEnabled(False)
        else:
            self.global_status_label.setText("Reporte generado.")
            self.global_progress_bar.setValue(100)
            self.btn_q_download.setEnabled(True)

    def download_quality_report(self):
        try:
            from memory.config_manager import BASE_DIR
            import time, os
            d = os.path.join(BASE_DIR, "Descargas_Nexus")
            os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, f"Calidad_{int(time.time())}.html")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(self.quality_output.toHtml())
            QMessageBox.information(self, "OK", f"Guardado en:\n{d}")
            os.startfile(d)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ─────────────────────────────────────────────────────────────────
    #  TAB 5 — Consulta (pregúntame lo que sea)
    # ─────────────────────────────────────────────────────────────────
    def _build_tab_consulta(self):
        tk = QWidget()
        kl = QVBoxLayout(tk)
        kl.setContentsMargins(12, 12, 12, 12)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Tipo de ayuda:"))
        self.cmb_consulta_mode = QComboBox()
        mode_labels = {
            "general": "General",
            "matematicas": "Matemáticas",
            "investigacion": "Investigación",
            "programacion": "Programación",
            "ensayo": "Ensayo / Redacción",
        }
        for key, label in mode_labels.items():
            self.cmb_consulta_mode.addItem(label, key)
        top_row.addWidget(self.cmb_consulta_mode)
        top_row.addStretch()
        self.btn_consulta_attach = QPushButton(" Adjuntar archivo")
        self.btn_consulta_attach.clicked.connect(self._consulta_attach_file)
        top_row.addWidget(self.btn_consulta_attach)
        self.btn_consulta_clear = QPushButton(" Nueva conversación")
        self.btn_consulta_clear.clicked.connect(self._consulta_clear)
        top_row.addWidget(self.btn_consulta_clear)
        kl.addLayout(top_row)

        self.consulta_output = QTextBrowser()
        self.consulta_output.setStyleSheet(
            "background:rgba(20,20,20,0.95);border:1px solid rgba(255,255,255,0.10);border-radius:8px;"
        )
        self.consulta_output.setPlaceholderText("Aquí aparecerán tus preguntas y respuestas…")
        kl.addWidget(self.consulta_output, 1)

        input_row = QHBoxLayout()
        self.txt_consulta_input = QTextEdit()
        self.txt_consulta_input.setPlaceholderText(
            "Escribe tu tarea, pregunta, ejercicio de matemáticas, duda de investigación, código, etc…"
        )
        self.txt_consulta_input.setFixedHeight(90)
        input_row.addWidget(self.txt_consulta_input, 1)
        self.btn_consulta_ask = QPushButton(" Preguntar")
        if HAS_QTA:
            self.btn_consulta_ask.setIcon(qta.icon("fa5s.paper-plane", color=C_TEXT))
        self.btn_consulta_ask.clicked.connect(self._trigger_consulta)
        input_row.addWidget(self.btn_consulta_ask)
        kl.addLayout(input_row)

        self.tabs.addTab(tk, qta.icon("fa5s.comment-dots", color=C_PRI) if HAS_QTA else QIcon(), "Consulta")

    def _consulta_attach_file(self):
        from PyQt6.QtWidgets import QFileDialog
        fp, _ = QFileDialog.getOpenFileName(
            self, "Adjuntar archivo", "", "Documentos (*.txt *.pdf *.docx *.xlsx *.pptx)"
        )
        if not fp:
            return
        text = extract_text(fp)
        if text.startswith("[Error"):
            QMessageBox.critical(self, "Error", text)
            return
        current = self.txt_consulta_input.toPlainText().strip()
        addition = f"\n\n[Contenido de {fp}]:\n{text[:6000]}"
        self.txt_consulta_input.setPlainText((current + addition).strip())

    def _consulta_clear(self):
        self.consulta_history = []
        self.consulta_output.clear()

    def _trigger_consulta(self):
        question = self.txt_consulta_input.toPlainText().strip()
        if not question:
            return
        mode = self.cmb_consulta_mode.currentData()
        self.consulta_output.append(
            f"<div style='color:#7aeeff;font-weight:bold;margin-top:10px;'>Tú:</div><div>{question}</div>"
        )
        self.txt_consulta_input.clear()
        self.btn_consulta_ask.setEnabled(False)
        self.global_status_label.setText("Consultando a NEXUS…")
        self.consulta_worker = ConsultaWorker(question, mode, self.consulta_history)
        self.consulta_worker.status.connect(self.global_status_label.setText)
        self.consulta_worker.finished.connect(lambda ans, err: self._consulta_finished(question, ans, err))
        self.consulta_worker.start()

    def _consulta_finished(self, question, answer, error):
        self.btn_consulta_ask.setEnabled(True)
        if error:
            self.consulta_output.append(f"<div style='color:#ff3b30;'>Error: {error}</div>")
            return
        self.consulta_output.append(
            f"<div style='color:{C_PRI};font-weight:bold;margin-top:6px;'>NEXUS:</div><div>{answer}</div>"
        )
        self.consulta_history.append({"q": question, "a": answer})
        self.global_status_label.setText("Consulta respondida.")

    # ─────────────────────────────────────────────────────────────────
    #  TAB 6 — Traductor
    # ─────────────────────────────────────────────────────────────────
    def _build_tab_translate(self):
        tt = QWidget()
        tl = QVBoxLayout(tt)
        tl.setContentsMargins(12, 12, 12, 12)

        row = QHBoxLayout()
        row.addWidget(QLabel("Desde:"))
        self.cmb_trans_source = QComboBox()
        self.cmb_trans_source.addItem("Auto-detectar")
        self.cmb_trans_source.addItems(LANGUAGES)
        row.addWidget(self.cmb_trans_source)

        self.btn_trans_swap = QPushButton(" ⇄ ")
        self.btn_trans_swap.setFixedWidth(50)
        self.btn_trans_swap.clicked.connect(self._trans_swap_languages)
        row.addWidget(self.btn_trans_swap)

        row.addWidget(QLabel("Hacia:"))
        self.cmb_trans_target = QComboBox()
        self.cmb_trans_target.addItems(LANGUAGES)
        self.cmb_trans_target.setCurrentText("Español")
        row.addWidget(self.cmb_trans_target)
        row.addStretch()
        tl.addLayout(row)

        split = QHBoxLayout()
        self.txt_trans_input = QTextEdit()
        self.txt_trans_input.setPlaceholderText("Escribe o pega el texto a traducir…")
        self.txt_trans_output = QTextEdit()
        self.txt_trans_output.setPlaceholderText("Traducción…")
        self.txt_trans_output.setReadOnly(True)
        split.addWidget(self.txt_trans_input)
        split.addWidget(self.txt_trans_output)
        tl.addLayout(split)

        btn_row = QHBoxLayout()
        self.btn_trans_run = QPushButton(" Traducir")
        if HAS_QTA:
            self.btn_trans_run.setIcon(qta.icon("fa5s.language", color=C_TEXT))
        self.btn_trans_run.clicked.connect(self._trigger_translate)
        btn_row.addWidget(self.btn_trans_run)
        self.btn_trans_copy = QPushButton(" Copiar traducción")
        self.btn_trans_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_trans_output.toPlainText()))
        btn_row.addWidget(self.btn_trans_copy)
        tl.addLayout(btn_row)

        self.tabs.addTab(tt, qta.icon("fa5s.globe", color=C_PRI) if HAS_QTA else QIcon(), "Traductor")

    def _trans_swap_languages(self):
        src = self.cmb_trans_source.currentText()
        tgt = self.cmb_trans_target.currentText()
        if src == "Auto-detectar":
            return
        idx_src = self.cmb_trans_source.findText(tgt)
        idx_tgt = self.cmb_trans_target.findText(src)
        if idx_src >= 0:
            self.cmb_trans_source.setCurrentIndex(idx_src)
        if idx_tgt >= 0:
            self.cmb_trans_target.setCurrentIndex(idx_tgt)
        self.txt_trans_input.setPlainText(self.txt_trans_output.toPlainText())

    def _trigger_translate(self):
        text = self.txt_trans_input.toPlainText().strip()
        if not text:
            return
        source_lang = self.cmb_trans_source.currentText()
        target_lang = self.cmb_trans_target.currentText()
        self.txt_trans_output.setPlainText("Traduciendo…")
        self.btn_trans_run.setEnabled(False)
        self.translate_worker = TranslateWorker(text, source_lang, target_lang)
        self.translate_worker.status.connect(self.global_status_label.setText)
        self.translate_worker.finished.connect(self._translate_finished)
        self.translate_worker.start()

    def _translate_finished(self, result, error):
        self.btn_trans_run.setEnabled(True)
        if error:
            self.txt_trans_output.setPlainText(f"Error: {error}")
            QMessageBox.critical(self, "Error", error)
            return
        self.txt_trans_output.setPlainText(result)
        self.global_status_label.setText("Traducción completada.")