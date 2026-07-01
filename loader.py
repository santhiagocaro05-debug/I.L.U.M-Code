"""
ILUM Neural Loader - Pantalla de carga futurista cyberpunk
Orbe 3D + anillo orbital lunar + efectos de scan
"""
from __future__ import annotations
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QProgressBar, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QPointF, QRectF
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPainterPath, QPen, QBrush, QConicalGradient
)
import math

try:
    import qtawesome as qta
    HAS_QTA = True
except ImportError:
    HAS_QTA = False

# ── Paleta Neural Dark ──────────────────────────────────────────────────────
C_BG_TOP    = QColor(13, 10, 28)
C_BG_BOT    = QColor(8, 6, 18)
C_ORB_CORE  = QColor(100, 70, 220)
C_ORB_GLOW  = QColor(140, 100, 255)
C_RING_1    = QColor(120, 80, 255)
C_RING_2    = QColor(80, 160, 255)
C_MOON_DOT  = QColor(160, 120, 255)
C_TEXT_PRI  = QColor(224, 212, 255)
C_TEXT_SEC  = QColor(140, 110, 220)
C_TEXT_HINT = QColor(90, 70, 160)
C_BAR_END   = QColor(180, 140, 255)
C_BORDER    = QColor(100, 80, 255, 60)


# ── Orbe 3D con Anillos Orbitales y Luna (Restaurado) ──────────────────
class MoonWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pulse = 0.0
        self._pulse_dir = 1
        self._orbit_angle = 0.0
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(30)

    def _tick(self):
        self._pulse += 0.05 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1
        self._orbit_angle = (self._orbit_angle + 2.5) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = 70, 70
        
        # 1. Glow behind the orb (central glow)
        glow_size = 35 + int(self._pulse * 10)
        bg_glow = QRadialGradient(cx, cy, glow_size)
        bg_glow.setColorAt(0.0, QColor(140, 100, 255, 100))
        bg_glow.setColorAt(0.6, QColor(100, 70, 220, 30))
        bg_glow.setColorAt(1.0, QColor(100, 70, 220, 0))
        p.setBrush(QBrush(bg_glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - glow_size, cy - glow_size, glow_size * 2, glow_size * 2)

        # 2. Draw Secondary Orbital Ring (C_RING_2, dashed, tilted opposite way)
        p.save()
        p.translate(cx, cy)
        p.rotate(25) # Tilt 25 degrees opposite
        pen_ring2 = QPen(C_RING_2, 1.2)
        pen_ring2.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen_ring2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(-48, -14, 96, 28))
        p.restore()

        # 3. Draw Primary Orbital Ring (C_RING_1, solid, tilted)
        p.save()
        p.translate(cx, cy)
        p.rotate(-25) # Tilt -25 degrees
        pen_ring1 = QPen(C_RING_1, 1.8)
        p.setPen(pen_ring1)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(-48, -14, 96, 28))
        p.restore()

        # 4. Draw Central 3D Orb Core (C_ORB_CORE & C_ORB_GLOW)
        r_orb = 22
        orb_grad = QRadialGradient(cx - 5, cy - 5, r_orb + 5)
        # 3D highlight effect
        orb_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        orb_grad.setColorAt(0.2, C_ORB_GLOW)
        orb_grad.setColorAt(0.7, C_ORB_CORE)
        orb_grad.setColorAt(1.0, QColor(50, 30, 120, 255))
        p.setBrush(QBrush(orb_grad))
        p.setPen(QPen(QColor(180, 150, 255, 180), 1.0))
        p.drawEllipse(cx - r_orb, cy - r_orb, r_orb * 2, r_orb * 2)

        # 5. Draw the Moon Dot orbiting the Primary Ring
        # Tilted ellipse math
        rad = math.radians(self._orbit_angle)
        # Position on the ellipse (a=48, b=14)
        x_prime = 48 * math.cos(rad)
        y_prime = 14 * math.sin(rad)
        # Rotate by -25 degrees
        theta = math.radians(-25)
        dot_x = cx + (x_prime * math.cos(theta) - y_prime * math.sin(theta))
        dot_y = cy + (x_prime * math.sin(theta) + y_prime * math.cos(theta))

        # Glowing Moon Dot
        p.setPen(Qt.PenStyle.NoPen)
        # Small white core
        p.setBrush(QBrush(QColor(255, 255, 255, 255)))
        p.drawEllipse(QPointF(dot_x, dot_y), 3.5, 3.5)
        # Glow ring around the dot
        dot_glow = QRadialGradient(dot_x, dot_y, 9)
        dot_glow.setColorAt(0.0, QColor(255, 255, 255, 220))
        dot_glow.setColorAt(0.4, C_MOON_DOT)
        dot_glow.setColorAt(1.0, QColor(160, 120, 255, 0))
        p.setBrush(QBrush(dot_glow))
        p.drawEllipse(QPointF(dot_x - 9, dot_y - 9), 18, 18)

        p.end()



# ── Barra de progreso custom ───────────────────────────────────────────────
class NeuralProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(360, 6)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._value = 0

    def setValue(self, v: int):
        self._value = max(0, min(100, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Track
        p.setBrush(QColor(60, 40, 140, 40))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 3, 3)

        if self._value <= 0:
            p.end()
            return

        fill_w = int(w * self._value / 100)

        # Fill gradient
        grad = QLinearGradient(0, 0, fill_w, 0)
        grad.setColorAt(0.0, QColor(80, 60, 200, 140))
        grad.setColorAt(0.5, QColor(140, 100, 255, 255))
        grad.setColorAt(1.0, QColor(180, 140, 255, 220))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(0, 0, fill_w, h, 3, 3)

        # Glow dot at tip
        if fill_w > 6:
            gx = fill_w
            glow = QRadialGradient(gx, h // 2, 9)
            glow.setColorAt(0.0, QColor(200, 170, 255, 200))
            glow.setColorAt(1.0, QColor(200, 170, 255, 0))
            p.setBrush(QBrush(glow))
            p.drawEllipse(gx - 9, h // 2 - 9, 18, 18)

        p.end()


# ── Loader principal ───────────────────────────────────────────────────────
class ILUMLoader(QWidget):
    finished = pyqtSignal()

    def __init__(self, duration: int = 3200, parent=None):
        super().__init__(parent)
        self.duration = duration
        self._progress = 0
        self._scan_y = 0
        self._scan_dir = 1
        self.setup_ui()
        self.setup_progress()

        # Scan line timer
        scan_timer = QTimer(self)
        scan_timer.timeout.connect(self._tick_scan)
        scan_timer.start(12)

    # ── UI ─────────────────────────────────────────────────────────────────
    def setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 400)

        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Canvas: pintamos fondo en paintEvent
        self.canvas = QWidget(self)
        self.canvas.setFixedSize(500, 400)
        self.canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        root.addWidget(self.canvas)

        layout = QVBoxLayout(self.canvas)
        layout.setContentsMargins(40, 30, 40, 26)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Luna Central
        self.moon = MoonWidget()
        layout.addWidget(self.moon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(10)

        # Título
        self.lbl_title = QLabel("I · L · U · M")
        font_title = QFont("Orbitron", 24, QFont.Weight.Black)
        font_title.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
        self.lbl_title.setFont(font_title)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet(
            "color: #e0d4ff; background: transparent; "
            "letter-spacing: 8px;"
        )
        layout.addWidget(self.lbl_title)
        layout.addSpacing(4)

        # Subtítulo
        self.lbl_sub = QLabel("INTELLIGENT LEARNING UNIFIED MODULE")
        font_sub = QFont("Share Tech Mono", 7, QFont.Weight.Normal)
        font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        self.lbl_sub.setFont(font_sub)
        self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sub.setStyleSheet("color: rgba(140,110,220,0.55); background: transparent;")
        layout.addWidget(self.lbl_sub)
        layout.addSpacing(20)

        # Barra progreso
        self.prog = NeuralProgressBar()
        layout.addWidget(self.prog, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)

        # Row: status + porcentaje
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row_layout = QVBoxLayout(row)  # usamos VBox para poner 2 lines
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(3)

        self.lbl_status = QLabel("INICIANDO NÚCLEO NEURAL")
        font_mono = QFont("Share Tech Mono", 8)
        self.lbl_status.setFont(font_mono)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: rgba(140,110,230,0.75); background: transparent; letter-spacing: 2px;")
        row_layout.addWidget(self.lbl_status)

        self.lbl_sys = QLabel("SYS :: AUTH OK  █")
        self.lbl_sys.setFont(font_mono)
        self.lbl_sys.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sys.setStyleSheet("color: rgba(100,80,180,0.55); background: transparent; letter-spacing: 2px;")
        row_layout.addWidget(self.lbl_sys)

        layout.addWidget(row, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(10)

        # Porcentaje grande
        self.lbl_pct = QLabel("0%")
        font_pct = QFont("Orbitron", 11, QFont.Weight.Bold)
        self.lbl_pct.setFont(font_pct)
        self.lbl_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_pct.setStyleSheet("color: rgba(180,150,255,0.85); background: transparent;")
        layout.addWidget(self.lbl_pct)

        # Títpulos
        self._status_data = [
            ("INICIANDO NÚCLEO NEURAL",      "SYS :: AUTH OK"),
            ("ACTIVANDO MÓDULOS DE IA",       "MOD :: LLM_CORE LOADED"),
            ("CONEXIÓN SEGURA ESTABLECIDA",   "NET :: TLS 1.3 OK"),
            ("CARGANDO MEMORIA RAM",          "MEM :: 16.4 GB ALLOCATED"),
            ("SINCRONIZANDO PERIFÉRICOS",     "IO :: DEVICES MAPPED"),
            ("VERIFICANDO LICENCIA",          "LIC :: KEY VALID 157-TEAM"),
            ("CALIBRANDO MICRÓFONO",          "MIC :: 44100 HZ READY"),
            ("ACTIVANDO VISIÓN IA",           "VIS :: STREAM ONLINE"),
            ("INICIALIZANDO HUD",             "HUD :: OVERLAYS OK"),
            ("¡ILUM ONLINE, SEÑOR!",          "SYS :: ALL SYSTEMS NOMINAL"),
        ]

        # Título blink timer
        self._blink = True
        blink_t = QTimer(self)
        blink_t.timeout.connect(self._blink_cursor)
        blink_t.start(500)

    # ── Blink cursor ───────────────────────────────────────────────────────
    def _blink_cursor(self):
        self._blink = not self._blink
        sys_txt = self.lbl_sys.text().rstrip(" █")
        self.lbl_sys.setText(sys_txt + ("  █" if self._blink else "   "))

    # ── Scan line ──────────────────────────────────────────────────────────
    def _tick_scan(self):
        self._scan_y += self._scan_dir * 2
        if self._scan_y > 400:
            self._scan_dir = -1
        elif self._scan_y < 0:
            self._scan_dir = 1
        self.canvas.update()

    # ── Progress ───────────────────────────────────────────────────────────
    def setup_progress(self):
        self._status_idx = 0
        self._anim_value = 0

        self._p_timer = QTimer(self)
        self._p_timer.timeout.connect(self._tick_progress)
        self._p_timer.start(40)

    def _tick_progress(self):
        if self._anim_value >= 100:
            self._p_timer.stop()
            self.lbl_status.setText("¡ILUM ONLINE, SEÑOR!")
            self.lbl_sys.setText("SYS :: ALL SYSTEMS NOMINAL  █")
            QTimer.singleShot(600, self._fade_out)
            return

        step = max(0.3, (100 - self._anim_value) / 60)
        self._anim_value = min(100, self._anim_value + step)
        v = int(self._anim_value)
        self.prog.setValue(v)
        self.lbl_pct.setText(f"{v}%")

        idx = min(int(v / 100 * len(self._status_data)), len(self._status_data) - 1)
        if idx != self._status_idx:
            self._status_idx = idx
            main_txt, sys_txt = self._status_data[idx]
            self.lbl_status.setText(main_txt)
            self.lbl_sys.setText(sys_txt + "  █")

    # ── Fade out ───────────────────────────────────────────────────────────
    def _fade_out(self):
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(500)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade.finished.connect(self.finished.emit)
        self._fade.start()

    # ── Paint fondo ────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Fondo
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(13, 10, 28, 250))
        bg.setColorAt(1.0, QColor(8, 6, 18, 254))
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 20, 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(path, QBrush(bg))

        # Borde exterior
        p.setPen(QPen(QColor(100, 80, 255, 55), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 20, 20)

        # Línea superior brillante
        top_grad = QLinearGradient(0, 0, w, 0)
        top_grad.setColorAt(0.0, QColor(120, 80, 255, 0))
        top_grad.setColorAt(0.35, QColor(140, 100, 255, 180))
        top_grad.setColorAt(0.65, QColor(160, 120, 255, 140))
        top_grad.setColorAt(1.0, QColor(120, 80, 255, 0))
        p.setPen(QPen(QBrush(top_grad), 1.5))
        p.drawLine(20, 1, w - 20, 1)

        # Scan line sutil
        scan_grad = QLinearGradient(0, self._scan_y - 10, 0, self._scan_y + 10)
        scan_grad.setColorAt(0.0, QColor(120, 80, 255, 0))
        scan_grad.setColorAt(0.5, QColor(120, 80, 255, 18))
        scan_grad.setColorAt(1.0, QColor(120, 80, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(scan_grad))
        p.drawRect(20, max(0, self._scan_y - 10), w - 40, 20)

        # Esquinas decorativas
        corner_pen = QPen(QColor(120, 80, 255, 140), 1.5)
        corner_pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        p.setPen(corner_pen)
        cs = 16  # corner size
        # TL
        p.drawLine(20, 20 + cs, 20, 20); p.drawLine(20, 20, 20 + cs, 20)
        # TR
        p.drawLine(w-20-cs, 20, w-20, 20); p.drawLine(w-20, 20, w-20, 20+cs)
        # BL
        p.drawLine(20, h-20-cs, 20, h-20); p.drawLine(20, h-20, 20+cs, h-20)
        # BR
        p.drawLine(w-20-cs, h-20, w-20, h-20); p.drawLine(w-20, h-20, w-20, h-20-cs)

        # Tag inferior izq
        p.setPen(QColor(80, 60, 160, 100))
        font_tag = QFont("Share Tech Mono", 7)
        p.setFont(font_tag)
        p.drawText(24, h - 10, "SYS-157 // ILUM-AI")

        # Tag inferior der
        p.drawText(w - 90, h - 10, "v1.0.0 NEURAL")

        p.end()

    def showEvent(self, event):
        super().showEvent(event)


def show_loader_and_launch(main_func, duration: int = 3000):
    app = QApplication.instance() or QApplication(sys.argv)
    loader = ILUMLoader(duration)
    loader.show()

    def on_done():
        loader.close()
        
        # Reproducir audio de inicio
        import os
        import sys
        import winsound
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            sound_path = os.path.join(sys._MEIPASS, "IlumInicioRAV.wav")
        else:
            sound_path = os.path.join(os.path.dirname(__file__), "IlumInicioRAV.wav")
            
        if os.path.exists(sound_path):
            try:
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                print(f"[LOADER] Error al reproducir audio de inicio: {e}")
            
        if main_func:
            # Damos un pequeño respiro para el audio antes de lanzar la pesada UI principal
            QTimer.singleShot(100, main_func)

    loader.finished.connect(on_done)
    app.processEvents()
    return app


if __name__ == "__main__":
    def dummy_main():
        print("ILUM iniciado ✓")

    app = show_loader_and_launch(dummy_main, duration=3200)
    sys.exit(app.exec())