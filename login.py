import sys
import json
import random
from pathlib import Path
from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QPen, QBrush, QLinearGradient, QFontDatabase, QRadialGradient, QConicalGradient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, 
    QCheckBox, QVBoxLayout, QHBoxLayout, QFrame, QStyle, QMessageBox, QDialog,
    QGraphicsDropShadowEffect
)

import drm_manager
import ctypes

# Anti-Debugging Check
if sys.platform == "win32" and ctypes.windll.kernel32.IsDebuggerPresent():
    sys.exit(1)

# Paths
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
LICENSE_INFO_PATH = CONFIG_DIR / "license.json"

class Particle:
    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.vx = random.uniform(-0.8, 0.8)
        self.vy = random.uniform(-0.8, 0.8)
        self.radius = random.uniform(1.0, 3.5)
        self.opacity = random.randint(60, 180)
        self.target_opacity = random.randint(60, 180)
        self.pulse_speed = random.uniform(0.015, 0.035)
        self.color_variant = random.choice([0, 1, 2])  # 0=azul, 1=púrpura, 2=blanco

class ArcReactorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)
        self.angle = 0
        self.pulse = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)
        
    def update_animation(self):
        self.angle = (self.angle + 3.0) % 360
        self.pulse += 0.05
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        pulse_val = 0.80 + 0.20 * abs((self.pulse % 3.14) - 1.57) / 1.57
        
        # Outer glow with gradient
        glow_radius = 30 * pulse_val
        glow = QRadialGradient(center_x, center_y, glow_radius)
        glow.setColorAt(0.0, QColor(0, 180, 255, 20))
        glow.setColorAt(0.5, QColor(100, 80, 255, 10))
        glow.setColorAt(1.0, QColor(0, 180, 255, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), glow_radius, glow_radius)
        
        # Outer ring with gradient
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen()
        pen.setWidth(2)
        ring_grad = QConicalGradient(center_x, center_y, self.angle)
        ring_grad.setColorAt(0.0, QColor(0, 180, 255, 200))
        ring_grad.setColorAt(0.3, QColor(120, 100, 255, 180))
        ring_grad.setColorAt(0.6, QColor(0, 180, 255, 200))
        ring_grad.setColorAt(1.0, QColor(0, 180, 255, 200))
        pen.setBrush(QBrush(ring_grad))
        painter.setPen(pen)
        painter.drawEllipse(QPointF(center_x, center_y), 20, 20)
        
        # Inner ring glow
        pen.setColor(QColor(100, 80, 255, 40))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(center_x, center_y), 16, 16)
        
        # Rotating blades
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.angle)
        
        # Outer dashed ring
        pen = QPen(QColor(100, 200, 255, 150), 1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(0, 0), 12, 12)
        
        # Blades with gradient (6 blades instead of 8 for cleaner look)
        for i in range(6):
            painter.save()
            painter.rotate(i * 60)
            
            grad = QLinearGradient(0, 4, 0, 13)
            grad.setColorAt(0.0, QColor(0, 180, 255, 220))
            grad.setColorAt(0.5, QColor(120, 100, 255, 180))
            grad.setColorAt(1.0, QColor(0, 180, 255, 40))
            painter.setPen(QPen(grad, 1.8))
            painter.drawLine(0, 5, 0, 13)
            
            painter.restore()
        
        painter.restore()
        
        # Inner core with pulse and glow
        core_radius = 4.5 * pulse_val
        core_grad = QRadialGradient(center_x, center_y, core_radius)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        core_grad.setColorAt(0.3, QColor(200, 230, 255, 240))
        core_grad.setColorAt(0.7, QColor(100, 180, 255, 200))
        core_grad.setColorAt(1.0, QColor(80, 60, 255, 120))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), core_radius, core_radius)
        
        # Inner sparkle
        sparkle_radius = 1.5 * pulse_val
        painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
        painter.drawEllipse(QPointF(center_x - core_radius * 0.3, center_y - core_radius * 0.3), 
                           sparkle_radius, sparkle_radius)

class LoginWindow(QDialog):
    update_status_sig = pyqtSignal(str, bool, bool)
    finish_login_sig = pyqtSignal(str, str)

    def __init__(self, parent_launcher=None):
        super().__init__()
        self.parent_launcher = parent_launcher
        self.drag_position = QPoint()
        
        self.update_status_sig.connect(self.set_status)
        self.finish_login_sig.connect(self.finish_login)
        
        # Setup background floating particles
        self.particles = [Particle(500, 540) for _ in range(55)]
        
        self.init_ui()
        self.load_remembered_license()
        
        # Start particle update timer
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_particles)
        self.animation_timer.start(16)
        
        # Fade in animation
        self.setWindowOpacity(0)
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(800)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        QTimer.singleShot(100, self.fade_anim.start)

    def init_ui(self):
        # Frameless and translucent window setup
        self.setWindowTitle("NEXUS ACCESS")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(500, 560)
        self.setMinimumSize(420, 480)

        # Enhanced Stylesheets with premium glass effect - SIN warnings
        self.setStyleSheet("""
            QWidget {
                color: #ffffff;
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#mainFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(255, 255, 255, 0.06),
                    stop: 0.5 rgba(255, 255, 255, 0.03),
                    stop: 1 rgba(255, 255, 255, 0.01)
                );
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 28px;
            }
            QFrame#mainFrame:hover {
                border: 1px solid rgba(255, 255, 255, 0.16);
            }
            QLabel#titleLabel {
                font-family: 'Segoe UI Semibold', Arial;
                font-size: 26px;
                font-weight: 700;
                color: #ffffff;
                letter-spacing: 5px;
                background: transparent;
            }
            QLabel#subtitleLabel {
                color: rgba(255, 255, 255, 0.35);
                font-size: 10px;
                letter-spacing: 4px;
                font-weight: 600;
            }
            QLabel#sectionLabel {
                font-weight: 600;
                color: rgba(255, 255, 255, 0.65);
                font-size: 11px;
                letter-spacing: 1.5px;
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1.5px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 14px 18px;
                color: #ffffff;
                font-size: 13px;
                selection-background-color: rgba(100, 200, 255, 0.25);
            }
            QLineEdit:focus {
                border: 1.5px solid rgba(100, 200, 255, 0.40);
                background-color: rgba(255, 255, 255, 0.07);
            }
            QLineEdit:hover {
                border: 1.5px solid rgba(255, 255, 255, 0.18);
            }
            QCheckBox {
                spacing: 12px;
                color: rgba(255, 255, 255, 0.60);
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid rgba(255, 255, 255, 0.20);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.03);
            }
            QCheckBox::indicator:checked {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0077ff,
                    stop: 1 #00b4ff
                );
                border: 2px solid #00b4ff;
            }
            QCheckBox::indicator:hover {
                border: 2px solid rgba(255, 255, 255, 0.40);
            }
            QPushButton#btnPrimary {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0077ff,
                    stop: 1 #00b4ff
                );
                color: #ffffff;
                font-weight: 700;
                border-radius: 16px;
                padding: 16px 28px;
                font-size: 14px;
                border: none;
                letter-spacing: 1.5px;
            }
            QPushButton#btnPrimary:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0088ff,
                    stop: 1 #00ccff
                );
            }
            QPushButton#btnPrimary:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0066dd,
                    stop: 1 #0099dd
                );
            }
            QPushButton#btnSecondary {
                background-color: rgba(255, 255, 255, 0.04);
                color: rgba(255, 255, 255, 0.70);
                font-weight: 600;
                border-radius: 16px;
                padding: 16px 20px;
                font-size: 12px;
                border: 1.5px solid rgba(255, 255, 255, 0.10);
                letter-spacing: 0.5px;
            }
            QPushButton#btnSecondary:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1.5px solid rgba(255, 255, 255, 0.20);
                color: #ffffff;
            }
            QPushButton#btnLink {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.35);
                border: none;
                font-size: 11px;
                padding: 8px;
                text-decoration: none;
            }
            QPushButton#btnLink:hover {
                color: rgba(255, 255, 255, 0.70);
            }
            QPushButton#btnClose {
                background: transparent;
                border: none;
                padding: 6px;
                color: rgba(255,255,255,0.30);
                font-size: 16px;
                font-weight: 300;
            }
            QPushButton#btnClose:hover {
                color: rgba(255,255,255,0.80);
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
            }
        """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Translucent Container Frame
        self.frame = QFrame(self)
        self.frame.setObjectName("mainFrame")
        
        # Glass shadow
        shadow = QGraphicsDropShadowEffect(self.frame)
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 12)
        self.frame.setGraphicsEffect(shadow)
        
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(28, 20, 28, 30)
        frame_layout.setSpacing(18)

        # --- CUSTOM TITLE BAR ---
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(14)
        
        # Arc Reactor
        self.arc_reactor = ArcReactorWidget()
        title_bar_layout.addWidget(self.arc_reactor)

        # Title
        self.lbl_title = QLabel("NEXUS")
        self.lbl_title.setObjectName("titleLabel")
        title_bar_layout.addWidget(self.lbl_title)
        
        title_bar_layout.addStretch()

        # Close button only (cleaner)
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.clicked.connect(self.close)
        title_bar_layout.addWidget(self.btn_close)

        frame_layout.addLayout(title_bar_layout)

        # Subtle divider with glow
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("""
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 transparent,
                stop: 0.3 rgba(100, 200, 255, 0.10),
                stop: 0.5 rgba(100, 200, 255, 0.15),
                stop: 0.7 rgba(100, 200, 255, 0.10),
                stop: 1 transparent
            );
            max-height: 1px;
            border: none;
        """)
        frame_layout.addWidget(sep)

        # --- BODY ---
        
        # Subtitle
        self.subtitle = QLabel("ACCESO SEGURO")
        self.subtitle.setObjectName("subtitleLabel")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.subtitle)
        
        frame_layout.addSpacing(4)
        
        # License key field
        self.lbl_license = QLabel("CLAVE DE LICENCIA")
        self.lbl_license.setObjectName("sectionLabel")
        frame_layout.addWidget(self.lbl_license)

        self.txt_license = QLineEdit()
        self.txt_license.setPlaceholderText("NEXUS-XXXX-XXXX-XXXX")
        frame_layout.addWidget(self.txt_license)

        # Email field
        self.lbl_email = QLabel("CORREO ELECTRÓNICO")
        self.lbl_email.setObjectName("sectionLabel")
        frame_layout.addWidget(self.lbl_email)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("tu@correo.com")
        frame_layout.addWidget(self.txt_email)

        # Remember license checkbox
        self.chk_remember = QCheckBox("Recordar en este dispositivo")
        frame_layout.addWidget(self.chk_remember)

        # Status output with icon
        self.status_container = QHBoxLayout()
        self.status_container.setSpacing(12)
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(18, 18)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: rgba(255,255,255,0.60); font-weight: 500; font-size: 12px;")
        self.status_label.setWordWrap(True)
        
        self.status_container.addWidget(self.status_icon)
        self.status_container.addWidget(self.status_label, 1)
        frame_layout.addLayout(self.status_container)

        # Action Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(16)

        self.btn_launch = QPushButton("INICIAR")
        self.btn_launch.setObjectName("btnPrimary")
        self.btn_launch.clicked.connect(self.on_launch_clicked)
        buttons_layout.addWidget(self.btn_launch, 2)

        self.btn_reset = QPushButton("REINICIAR")
        self.btn_reset.setObjectName("btnSecondary")
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        buttons_layout.addWidget(self.btn_reset, 1)

        frame_layout.addLayout(buttons_layout)

        # Recovery link
        self.btn_recover = QPushButton("¿Olvidaste tu clave?")
        self.btn_recover.setObjectName("btnLink")
        self.btn_recover.clicked.connect(self.on_recover_clicked)
        frame_layout.addWidget(self.btn_recover, 0, Qt.AlignmentFlag.AlignCenter)

        # Footer version
        version_label = QLabel("v1.0.4 · Sistema de Seguridad Avanzado")
        version_label.setStyleSheet("color: rgba(255,255,255,0.15); font-size: 9px; letter-spacing: 1px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(version_label)

        main_layout.addWidget(self.frame)

    # --- PARTICLE VECTOR ANIMATION LOOP ---
    def update_particles(self):
        width, height = self.width(), self.height()
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            
            padding = 30
            if p.x < -padding: p.x = width + padding
            elif p.x > width + padding: p.x = -padding
            if p.y < -padding: p.y = height + padding
            elif p.y > height + padding: p.y = -padding
            
            p.opacity += p.pulse_speed * (p.target_opacity - p.opacity) * 0.02
            
        self.update()

    # --- GLOWING BACKGROUND & CONSTELLATION PAINT ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background gradient - deeper and richer
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(8, 10, 20, 250))
        grad.setColorAt(0.5, QColor(5, 6, 14, 252))
        grad.setColorAt(1.0, QColor(2, 3, 8, 255))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 28, 28)
        
        # Paint particles with different colors
        for p in self.particles:
            alpha = int(p.opacity)
            if p.color_variant == 0:
                color = QColor(80, 180, 255, alpha)
            elif p.color_variant == 1:
                color = QColor(150, 100, 255, alpha)
            else:
                color = QColor(200, 220, 255, alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)
            
        # Constellation lines
        for i in range(len(self.particles)):
            for j in range(i + 1, len(self.particles)):
                p1 = self.particles[i]
                p2 = self.particles[j]
                dx = p1.x - p2.x
                dy = p1.y - p2.y
                dist = (dx*dx + dy*dy) ** 0.5
                if dist < 75:
                    alpha = int((1.0 - (dist / 75.0)) * 35)
                    if alpha > 3:
                        pen = QPen(QColor(120, 180, 255, alpha), 0.6)
                        painter.setPen(pen)
                        painter.drawLine(QPointF(p1.x, p1.y), QPointF(p2.x, p2.y))

    # --- WINDOW DRAGGING ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    # --- BUSINESS LOGIC --- (TODAS LAS FUNCIONES ORIGINALES SIN CAMBIOS)
    
    def set_status(self, text: str, is_error: bool = False, is_success: bool = False):
        self.status_label.setText(text)
        if is_error:
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 500; font-size: 12px;")
            pix = self.style().standardPixmap(QStyle.StandardPixmap.SP_MessageBoxCritical)
            self.status_icon.setPixmap(pix.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio))
        elif is_success:
            self.status_label.setStyleSheet("color: #51cf66; font-weight: 500; font-size: 12px;")
            pix = self.style().standardPixmap(QStyle.StandardPixmap.SP_DialogApplyButton)
            self.status_icon.setPixmap(pix.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.status_label.setStyleSheet("color: rgba(255,255,255,0.60); font-weight: 500; font-size: 12px;")
            self.status_icon.clear()

    def load_remembered_license(self):
        if LICENSE_INFO_PATH.exists():
            try:
                data = json.loads(LICENSE_INFO_PATH.read_text(encoding="utf-8"))
                key = data.get("license_key", "")
                if key:
                    self.txt_license.setText(key)
                    self.chk_remember.setChecked(True)
            except Exception:
                pass

    def save_license_locally(self, key: str, email: str = "", days_remaining=None, created_at=None):
        if self.chk_remember.isChecked():
            try:
                data = {
                    "license_key": key,
                    "email": email,
                    "days_remaining": days_remaining,
                    "created_at": created_at
                }
                LICENSE_INFO_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")
            except Exception:
                pass
        else:
            if LICENSE_INFO_PATH.exists():
                try:
                    LICENSE_INFO_PATH.unlink()
                except Exception:
                    pass

    def start_update_verification(self, key):
        import threading
        self.set_status("Buscando actualizaciones...")
        
        def bg_update_worker():
            try:
                import time
                current_ver = "1.0.4"
                update_res = drm_manager.check_for_updates(current_ver)
                
                if update_res.get("update_available"):
                    url = update_res.get("url")
                    version = update_res.get("version")
                    self.update_status_sig.emit(f"Actualización v{version} encontrada. Descargando...", False, False)
                    
                    target_file = "ui.py"
                    if url.endswith(".py"):
                        target_file = url.split("/")[-1]
                        
                    download_res = drm_manager.download_and_apply_patch(url, target_file)
                    
                    if download_res.get("success"):
                        self.update_status_sig.emit("¡Parche aplicado! Iniciando...", False, True)
                        time.sleep(1.5)
                        self.finish_login_sig.emit(key, getattr(self, "aes_token", ""))
                    else:
                        err_msg = download_res.get("message", "Error al aplicar actualización.")
                        self.update_status_sig.emit(f"Error actualización: {err_msg}", True, False)
                        time.sleep(2.0)
                        self.finish_login_sig.emit(key, getattr(self, "aes_token", ""))
                else:
                    self.update_status_sig.emit("Licencia validada con éxito. Iniciando...", False, True)
                    time.sleep(1.0)
                    self.finish_login_sig.emit(key, getattr(self, "aes_token", ""))
            except Exception as e:
                print(f"[NEXUS Login] Error en hilo de actualizaciones: {e}. Accediendo directamente...")
                self.finish_login_sig.emit(key, getattr(self, "aes_token", ""))
                
        threading.Thread(target=bg_update_worker, daemon=True).start()

    def on_launch_clicked(self):
        key = self.txt_license.text().strip()
        if not key:
            self.set_status("Por favor, ingresa tu Clave de Licencia.", is_error=True)
            return

        self.set_status("Validando licencia...")
        
        res = drm_manager.validate_license(key)
        
        if res.get("success"):
            import hashlib
            sig = res.get("signature", "FALLBACK_SIG")
            self.aes_token = hashlib.sha256(f"NEXUS_AES_TOKEN_{sig}_{key}".encode()).hexdigest()
            
            self.save_license_locally(
                key,
                res.get("email", ""),
                days_remaining=res.get("days_remaining"),
                created_at=res.get("created_at")
            )
            self.start_update_verification(key)
        else:
            self.set_status(res.get("message"), is_error=True)

    def on_reset_clicked(self):
        key = self.txt_license.text().strip()
        email = self.txt_email.text().strip()
        
        if not key or not email:
            self.set_status("Para restablecer HWID necesitas ingresar Clave y Correo.", is_error=True)
            return

        self.set_status("Procesando reinicio de HWID...")
        
        res = drm_manager.reset_hwid(key, email)
        
        if res.get("success"):
            self.set_status(res.get("message"), is_success=True)
        else:
            self.set_status(res.get("message"), is_error=True)

    def on_recover_clicked(self):
        email = self.txt_email.text().strip()
        if not email:
            self.set_status("Por favor, ingresa tu correo en el campo correspondiente.", is_error=True)
            return

        self.set_status("Buscando claves...")
        
        res = drm_manager.recover_license(email)
        
        if res.get("success"):
            self.set_status(res.get("message"), is_success=True)
        else:
            self.set_status(res.get("message"), is_error=True)

    def finish_login(self, verified_key: str, aes_token: str):
        self.accept_code = True
        
        if self.parent_launcher and hasattr(self.parent_launcher, "on_login_success"):
            self.parent_launcher.on_login_success(verified_key, aes_token)
        else:
            print("[NEXUS Login] Login exitoso. Clave verificada:", verified_key)
            
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LoginWindow()
    win.show()
    sys.exit(app.exec())