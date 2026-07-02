import sys
import json
import random
from pathlib import Path
from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QPen, QBrush, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, 
    QCheckBox, QVBoxLayout, QHBoxLayout, QFrame, QStyle, QMessageBox, QDialog
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
        self.vx = random.uniform(-0.4, 0.4)
        self.vy = random.uniform(-0.4, 0.4)
        self.radius = random.uniform(1.2, 3.2)
        self.opacity = random.randint(100, 220)

class ArcReactorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(25) # ~40 FPS animation for rotation
        
    def update_angle(self):
        self.angle = (self.angle + 2) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        
        # Soft outer white glow
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 20), 4))
        painter.drawEllipse(QPointF(center_x, center_y), 24, 24)
        
        # Outer solid ring
        painter.setPen(QPen(QColor(255, 255, 255, 130), 1.5))
        painter.drawEllipse(QPointF(center_x, center_y), 20, 20)
        
        # Save state, translate and rotate for spinning blades
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.angle)
        
        # Rotating dashed ring
        pen = QPen(QColor(255, 255, 255, 220), 2.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(0, 0), 14, 14)
        
        # Arc Reactor blades (8 segments)
        painter.setPen(QPen(QColor(255, 255, 255, 140), 1.5))
        for _ in range(8):
            painter.rotate(45)
            painter.drawLine(0, 7, 0, 14)
            
        painter.restore()
        
        # Inner glowing power core
        painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
        painter.setPen(QPen(QColor(255, 255, 255, 255), 1.5))
        painter.drawEllipse(QPointF(center_x, center_y), 6, 6)

class LoginWindow(QDialog):
    update_status_sig = pyqtSignal(str, bool, bool)
    finish_login_sig = pyqtSignal(str, str)

    def __init__(self, parent_launcher=None):
        super().__init__()
        self.parent_launcher = parent_launcher
        self.drag_position = QPoint()
        
        self.update_status_sig.connect(self.set_status)
        self.finish_login_sig.connect(self.finish_login)
        
        # Setup background floating particles (neural constellation)
        self.particles = [Particle(450, 480) for _ in range(35)]
        
        self.init_ui()
        self.load_remembered_license()
        
        # Start particle update timer (60 FPS animation loop)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_particles)
        self.animation_timer.start(16)

    def init_ui(self):
        # Frameless and translucent window setup
        self.setWindowTitle("ILUM ACCESS")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(450, 480)

        # Enhanced Stylesheets with liquid glass effect and white colors
        self.setStyleSheet("""
            QWidget {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#mainFrame {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1.5px solid rgba(255, 255, 255, 0.25);
                border-radius: 20px;
            }
            QLabel#titleLabel {
                font-family: 'Marske', 'Segoe UI Semibold', Arial;
                font-size: 22px;
                font-weight: bold;
                color: #ffffff;
                letter-spacing: 3px;
            }
            QLabel#sectionLabel {
                font-weight: bold;
                color: rgba(255, 255, 255, 0.85);
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1.5px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                padding: 9px 12px;
                color: #ffffff;
                font-size: 13px;
                selection-background-color: rgba(255, 255, 255, 0.3);
            }
            QLineEdit:focus {
                border: 1.5px solid rgba(255, 255, 255, 0.6);
                background-color: rgba(255, 255, 255, 0.15);
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1.5px solid rgba(255, 255, 255, 0.4);
                border-radius: 4px;
                background: rgba(255, 255, 255, 0.1);
            }
            QCheckBox::indicator:checked {
                background: rgba(255, 255, 255, 0.8);
                border: 1.5px solid rgba(255, 255, 255, 0.8);
            }
            QPushButton#btnPrimary {
                background-color: rgba(255, 255, 255, 0.9);
                color: #000000;
                font-weight: bold;
                border-radius: 12px;
                padding: 11px 20px;
                font-size: 13px;
                border: none;
            }
            QPushButton#btnPrimary:hover {
                background-color: #ffffff;
            }
            QPushButton#btnPrimary:pressed {
                background-color: rgba(255, 255, 255, 0.7);
            }
            QPushButton#btnSecondary {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                font-weight: bold;
                border-radius: 12px;
                padding: 11px 20px;
                font-size: 13px;
                border: 1.5px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton#btnSecondary:hover {
                background-color: rgba(255, 255, 255, 0.18);
                border: 1.5px solid rgba(255, 255, 255, 0.5);
            }
            QPushButton#btnLink {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                text-decoration: underline;
                font-size: 12px;
                padding: 6px;
            }
            QPushButton#btnLink:hover {
                color: #ffffff;
            }
        """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Translucent Container Frame with liquid glass effect
        self.frame = QFrame(self)
        self.frame.setObjectName("mainFrame")
        
        # Add liquid glass shadow effect
        self.frame.setGraphicsEffect(None)
        
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(20, 15, 20, 25)
        frame_layout.setSpacing(15)

        # --- CUSTOM TITLE BAR ---
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Rotating Arc Reactor Logo Widget
        self.arc_reactor = ArcReactorWidget()
        title_bar_layout.addWidget(self.arc_reactor)

        # Spacing
        title_bar_layout.addSpacing(5)

        self.lbl_title = QLabel("ILUM ACCESS")
        self.lbl_title.setObjectName("titleLabel")
        title_bar_layout.addWidget(self.lbl_title)
        
        title_bar_layout.addStretch()

        # Minimize Button
        self.btn_min = QPushButton()
        self.btn_min.setFixedSize(28, 28)
        self.btn_min.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMinButton))
        self.btn_min.setStyleSheet("background: transparent; border: none; padding: 2px; color: white;")
        self.btn_min.clicked.connect(self.showMinimized)
        title_bar_layout.addWidget(self.btn_min)

        # Close Button
        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        self.btn_close.setStyleSheet("background: transparent; border: none; padding: 2px; color: white;")
        self.btn_close.clicked.connect(self.close)
        title_bar_layout.addWidget(self.btn_close)

        frame_layout.addLayout(title_bar_layout)

        # Glowing divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); max-height: 1.2px; border: none;")
        frame_layout.addWidget(sep)

        # --- BODY ---
        
        # License key field
        self.lbl_license = QLabel("Clave de Licencia:")
        self.lbl_license.setObjectName("sectionLabel")
        frame_layout.addWidget(self.lbl_license)

        self.txt_license = QLineEdit()
        self.txt_license.setPlaceholderText("ILUM-XXXX-XXXX-XXXX")
        frame_layout.addWidget(self.txt_license)

        # Email field (Only needed for Reset and Recovery)
        self.lbl_email = QLabel("Correo Electrónico (Solo para Resetear o Recuperar):")
        self.lbl_email.setObjectName("sectionLabel")
        frame_layout.addWidget(self.lbl_email)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("comprador@correo.com")
        frame_layout.addWidget(self.txt_email)

        # Remember license checkbox
        self.chk_remember = QCheckBox("Recordar clave en este dispositivo")
        frame_layout.addWidget(self.chk_remember)

        # Status output
        self.status_container = QHBoxLayout()
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(20, 20)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #ffffff; font-weight: 500;")
        self.status_label.setWordWrap(True)
        
        self.status_container.addWidget(self.status_icon)
        self.status_container.addWidget(self.status_label, 1)
        frame_layout.addLayout(self.status_container)

        # Action Buttons Layout (Iniciar & Resetear)
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.btn_launch = QPushButton("Iniciar Asistente")
        self.btn_launch.setObjectName("btnPrimary")
        self.btn_launch.clicked.connect(self.on_launch_clicked)
        buttons_layout.addWidget(self.btn_launch)

        self.btn_reset = QPushButton("Resetear HWID")
        self.btn_reset.setObjectName("btnSecondary")
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        buttons_layout.addWidget(self.btn_reset)

        frame_layout.addLayout(buttons_layout)

        # Recovery link button
        self.btn_recover = QPushButton("¿Olvidaste tu clave? Recuperar mi clave")
        self.btn_recover.setObjectName("btnLink")
        self.btn_recover.clicked.connect(self.on_recover_clicked)
        frame_layout.addWidget(self.btn_recover, 0, Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(self.frame)

    # --- PARTICLE VECTOR ANIMATION LOOP ---
    def update_particles(self):
        width, height = self.width(), self.height()
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            
            # Wrap-around boundary check
            if p.x < 0: p.x = width
            elif p.x > width: p.x = 0
            if p.y < 0: p.y = height
            elif p.y > height: p.y = 0
            
        self.update() # Triggers paintEvent

    # --- GLOWING BACKGROUND & CONSTELLATION PAINT ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Paint dark glass background gradient
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(20, 20, 30, 245))
        grad.setColorAt(1.0, QColor(10, 10, 15, 252))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 20, 20)
        
        # 2. Paint floating particles (Neural Nodes)
        for p in self.particles:
            painter.setBrush(QBrush(QColor(255, 255, 255, p.opacity)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)
            
        # 3. Paint linking constellation lines (Neural Net)
        for i in range(len(self.particles)):
            for j in range(i + 1, len(self.particles)):
                p1 = self.particles[i]
                p2 = self.particles[j]
                dx = p1.x - p2.x
                dy = p1.y - p2.y
                dist = (dx*dx + dy*dy) ** 0.5
                if dist < 65:
                    # Fade opacity proportional to distance (closer = brighter)
                    alpha = int((1.0 - (dist / 65.0)) * 55)
                    pen = QPen(QColor(255, 255, 255, alpha), 1)
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

    # --- BUSINESS LOGIC ---
    
    def set_status(self, text: str, is_error: bool = False, is_success: bool = False):
        self.status_label.setText(text)
        if is_error:
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            pix = self.style().standardPixmap(QStyle.StandardPixmap.SP_MessageBoxCritical)
            self.status_icon.setPixmap(pix.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
        elif is_success:
            self.status_label.setStyleSheet("color: #51cf66; font-weight: bold;")
            pix = self.style().standardPixmap(QStyle.StandardPixmap.SP_DialogApplyButton)
            self.status_icon.setPixmap(pix.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.status_label.setStyleSheet("color: #ffffff; font-weight: 500;")
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
                current_ver = "1.0.0"
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
                print(f"[ILUM Login] Error en hilo de actualizaciones: {e}. Accediendo directamente...")
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
            # Generar token de descifrado AES a partir de la firma (evita memory hooking del booleano)
            import hashlib
            sig = res.get("signature", "FALLBACK_SIG")
            self.aes_token = hashlib.sha256(f"ILUM_AES_TOKEN_{sig}_{key}".encode()).hexdigest()
            
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
        
        # Signal success
        if self.parent_launcher and hasattr(self.parent_launcher, "on_login_success"):
            self.parent_launcher.on_login_success(verified_key, aes_token)
        else:
            print("[ILUM Login] Login exitoso. Clave verificada:", verified_key)
            
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LoginWindow()
    win.show()
    sys.exit(app.exec())