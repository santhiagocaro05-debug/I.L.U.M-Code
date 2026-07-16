import sys
import json
import math
import random
from pathlib import Path
from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QBrush, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QPushButton, QCheckBox, QVBoxLayout, QHBoxLayout,
    QFrame, QStyle, QDialog, QGraphicsDropShadowEffect, QGroupBox, QMessageBox
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
RECOVERED_KEY_PATH = CONFIG_DIR / "clave_recuperada.txt"


class Star:
    """Estrella con movimiento orbital suave y parpadeo"""
    def __init__(self, w, h):
        self.w = w
        self.h = h
        # Posición base
        self.base_x = random.uniform(0, w)
        self.base_y = random.uniform(0, h)
        # Posición inicial
        self.x = self.base_x
        self.y = self.base_y
        # Movimiento orbital
        self.orbit_radius = random.uniform(5, 30)
        self.orbit_speed = random.uniform(0.003, 0.015)
        self.orbit_phase = random.uniform(0, 6.283)
        # Tamaño y brillo
        self.radius = random.uniform(0.8, 2.5)
        self.base_opacity = random.uniform(80, 220)
        self.current_opacity = self.base_opacity  # Inicializar aquí
        # Parpadeo
        self.twinkle_speed = random.uniform(0.02, 0.06)
        self.twinkle_phase = random.uniform(0, 6.283)
        
    def update_position(self, tick):
        """Actualiza posición orbital y parpadeo"""
        # Movimiento orbital
        angle = self.orbit_phase + tick * self.orbit_speed * 100
        self.x = self.base_x + math.sin(angle) * self.orbit_radius
        self.y = self.base_y + math.cos(angle * 0.7) * self.orbit_radius * 0.6
        
        # Parpadeo suave
        self.current_opacity = self.base_opacity * (
            0.35 + 0.65 * (0.5 + 0.5 * math.sin(tick * self.twinkle_speed * 30 + self.twinkle_phase))
        )
        self.current_opacity = max(0, min(255, int(self.current_opacity)))


class LoginWindow(QDialog):
    update_status_sig = pyqtSignal(str, bool, bool)
    finish_login_sig = pyqtSignal(str, str)

    def __init__(self, parent_launcher=None):
        super().__init__()
        self.parent_launcher = parent_launcher
        self.drag_position = QPoint()

        self.update_status_sig.connect(self.set_status)
        self.finish_login_sig.connect(self.finish_login)

        self.init_ui()
        self.load_remembered_license()

        # Estrellas de fondo con movimiento
        self.stars = [Star(self.width(), self.height()) for _ in range(90)]
        self._tick = 0.0
        
        # Inicializar posición de las estrellas antes de pintar
        for star in self.stars:
            star.update_position(0)
        
        self.star_timer = QTimer(self)
        self.star_timer.timeout.connect(self.update_stars)
        self.star_timer.start(30)  # 30ms para movimiento fluido

        # Animación de entrada
        self.setWindowOpacity(0)
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(300)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        QTimer.singleShot(20, self.fade_anim.start)

    def init_ui(self):
        self.setWindowTitle("NEXUS — Acceso Seguro")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(820, 500)
        self.setMinimumSize(720, 460)

        self.setStyleSheet("""
            QWidget {
                color: #e8eaed;
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                font-size: 12.5px;
            }
            QFrame#mainFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 20, 28, 220),
                    stop:1 rgba(10, 12, 18, 230));
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 20px;
            }
            QLabel#brandBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4f8fff,
                    stop:1 #2563eb);
                color: #ffffff;
                font-weight: 900;
                font-size: 18px;
                border-radius: 12px;
            }
            QLabel#titleLabel {
                font-size: 20px;
                font-weight: 800;
                color: #ffffff;
                letter-spacing: 1.5px;
            }
            QLabel#subtitleLabel {
                color: rgba(255, 255, 255, 0.35);
                font-size: 10px;
                letter-spacing: 2.5px;
                font-weight: 600;
            }
            QPushButton#btnClose {
                background: transparent;
                border: none;
                color: rgba(255,255,255,0.25);
                font-size: 16px;
                font-weight: 300;
                border-radius: 10px;
                padding: 6px;
            }
            QPushButton#btnClose:hover {
                color: #ffffff;
                background: rgba(255,255,255,0.08);
            }
            QPushButton#btnMinimize {
                background: transparent;
                border: none;
                color: rgba(255,255,255,0.25);
                font-size: 16px;
                font-weight: 300;
                border-radius: 10px;
                padding: 6px;
            }
            QPushButton#btnMinimize:hover {
                color: #ffffff;
                background: rgba(255,255,255,0.08);
            }
            QGroupBox {
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 14px;
                margin-top: 18px;
                padding: 20px 18px 18px 18px;
                background: rgba(255, 255, 255, 0.02);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                top: -3px;
                padding: 0 8px;
                color: #60a5fa;
                font-weight: 700;
                font-size: 10px;
                letter-spacing: 2px;
                background: rgba(10, 12, 18, 0.95);
                border-radius: 4px;
            }
            QLabel#fieldLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 10.5px;
                font-weight: 600;
                letter-spacing: 0.8px;
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1.5px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 11px 14px;
                color: #ffffff;
                font-size: 13px;
                selection-background-color: rgba(96, 165, 250, 0.3);
            }
            QLineEdit:focus {
                border: 1.5px solid #60a5fa;
                background-color: rgba(255, 255, 255, 0.06);
            }
            QLineEdit:hover {
                border: 1.5px solid rgba(255, 255, 255, 0.15);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.2);
            }
            QCheckBox {
                spacing: 10px;
                color: rgba(255, 255, 255, 0.5);
                font-size: 11.5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid rgba(255, 255, 255, 0.15);
                border-radius: 5px;
                background: rgba(255, 255, 255, 0.02);
            }
            QCheckBox::indicator:checked {
                background: #2563eb;
                border: 2px solid #2563eb;
                border-radius: 5px;
            }
            QCheckBox::indicator:hover {
                border: 2px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton#btnPrimary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #16a34a,
                    stop:1 #1cbf57);
                color: #ffffff;
                font-weight: 700;
                border-radius: 10px;
                padding: 12px 24px;
                font-size: 13px;
                border: none;
                letter-spacing: 1px;
            }
            QPushButton#btnPrimary:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1cbf57,
                    stop:1 #22d066);
            }
            QPushButton#btnPrimary:pressed { 
                background: #128a3e;
            }
            QPushButton#btnSecondary {
                background-color: rgba(255, 255, 255, 0.04);
                color: rgba(255, 255, 255, 0.7);
                font-weight: 600;
                border-radius: 10px;
                padding: 12px 18px;
                font-size: 11.5px;
                border: 1.5px solid rgba(255, 255, 255, 0.08);
                letter-spacing: 0.5px;
            }
            QPushButton#btnSecondary:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1.5px solid rgba(255, 255, 255, 0.15);
                color: #ffffff;
            }
            QPushButton#btnOutline {
                background: transparent;
                color: #60a5fa;
                font-weight: 600;
                border-radius: 10px;
                padding: 11px 18px;
                font-size: 11.5px;
                border: 1.5px solid rgba(96, 165, 250, 0.3);
                letter-spacing: 0.5px;
            }
            QPushButton#btnOutline:hover {
                background: rgba(96, 165, 250, 0.08);
                border: 1.5px solid rgba(96, 165, 250, 0.6);
            }
            QLabel#infoBody {
                color: rgba(255, 255, 255, 0.5);
                font-size: 11px;
                line-height: 1.6;
            }
            QLabel#footerLabel {
                color: rgba(255, 255, 255, 0.12);
                font-size: 9px;
                letter-spacing: 1.5px;
            }
            QLabel#statusLabel {
                font-size: 11px;
                font-weight: 500;
            }
        """)

        # Layout principal
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.frame = QFrame(self)
        self.frame.setObjectName("mainFrame")
        shadow = QGraphicsDropShadowEffect(self.frame)
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 15)
        self.frame.setGraphicsEffect(shadow)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(30, 20, 30, 24)
        frame_layout.setSpacing(18)

        # ── Barra de título ──────────────────────────────────────
        title_bar = QHBoxLayout()
        title_bar.setSpacing(14)

        badge = QLabel("◆")
        badge.setObjectName("brandBadge")
        badge.setFixedSize(38, 38)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_bar.addWidget(badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        t1 = QLabel("NEXUS")
        t1.setObjectName("titleLabel")
        t2 = QLabel("Sistema de Acceso y Gestión")
        t2.setObjectName("subtitleLabel")
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        title_bar.addLayout(title_col)

        title_bar.addStretch()

        # Botón minimizar
        self.btn_minimize = QPushButton("─")
        self.btn_minimize.setObjectName("btnMinimize")
        self.btn_minimize.setFixedSize(30, 30)
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.clicked.connect(self.showMinimized)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.close)
        
        title_bar.addWidget(self.btn_minimize)
        title_bar.addWidget(self.btn_close)

        frame_layout.addLayout(title_bar)

        # ── Cuerpo principal ──────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(20)

        # Columna izquierda — formulario
        left_group = QGroupBox("Acceso")
        left_layout = QVBoxLayout(left_group)
        left_layout.setSpacing(12)

        lbl_lic = QLabel("Clave de Licencia")
        lbl_lic.setObjectName("fieldLabel")
        left_layout.addWidget(lbl_lic)
        self.txt_license = QLineEdit()
        self.txt_license.setPlaceholderText("NEXUS-XXXX-XXXX-XXXX")
        left_layout.addWidget(self.txt_license)

        lbl_email = QLabel("Correo Electrónico")
        lbl_email.setObjectName("fieldLabel")
        left_layout.addWidget(lbl_email)
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("usuario@dominio.com")
        left_layout.addWidget(self.txt_email)

        self.chk_remember = QCheckBox("Recordar licencia en este dispositivo")
        left_layout.addWidget(self.chk_remember)

        left_layout.addSpacing(6)

        # Estado
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(18, 18)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_icon)
        status_row.addWidget(self.status_label, 1)
        left_layout.addLayout(status_row)

        left_layout.addStretch()

        # Botones
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_launch = QPushButton("Iniciar Sesión")
        self.btn_launch.setObjectName("btnPrimary")
        self.btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_launch.clicked.connect(self.on_launch_clicked)
        self.btn_reset = QPushButton("Reiniciar HWID")
        self.btn_reset.setObjectName("btnSecondary")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        btn_row.addWidget(self.btn_launch, 2)
        btn_row.addWidget(self.btn_reset, 1)
        left_layout.addLayout(btn_row)

        body.addWidget(left_group, 3)

        # Columna derecha — información
        right_col = QVBoxLayout()
        right_col.setSpacing(18)

        info_group = QGroupBox("Información")
        info_layout = QVBoxLayout(info_group)
        info_text = QLabel(
            "El correo electrónico es obligatorio en los siguientes casos:\n\n"
            "•  Primer inicio de sesión\n"
            "•  Cambio de dispositivo\n"
            "•  Recuperación de clave\n"
            "•  Reinicio de HWID"
        )
        info_text.setObjectName("infoBody")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        right_col.addWidget(info_group)

        recover_group = QGroupBox("Recuperación")
        recover_layout = QVBoxLayout(recover_group)
        recover_layout.setSpacing(12)
        recover_text = QLabel("¿Perdiste tu clave de acceso? Recíbela nuevamente en tu correo registrado.")
        recover_text.setObjectName("infoBody")
        recover_text.setWordWrap(True)
        recover_layout.addWidget(recover_text)
        self.btn_recover = QPushButton("Recuperar Clave")
        self.btn_recover.setObjectName("btnOutline")
        self.btn_recover.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_recover.clicked.connect(self.on_recover_clicked)
        recover_layout.addWidget(self.btn_recover)
        right_col.addWidget(recover_group)

        right_col.addStretch()
        body.addLayout(right_col, 2)

        frame_layout.addLayout(body)

        # Footer
        version_label = QLabel("v2.0.7 · Sistema de Seguridad Avanzado")
        version_label.setObjectName("footerLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(version_label)

        outer.addWidget(self.frame)

    def update_stars(self):
        """Actualiza posición y brillo de las estrellas"""
        self._tick += 0.04
        for star in self.stars:
            star.update_position(self._tick)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fondo degradado
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(12, 14, 22, 255))
        grad.setColorAt(0.5, QColor(8, 10, 16, 255))
        grad.setColorAt(1.0, QColor(5, 6, 10, 255))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 20, 20)

        # Dibujar estrellas con movimiento y brillo
        for star in self.stars:
            alpha = star.current_opacity
            
            if star.radius > 1.8:
                # Brillo exterior para estrellas grandes
                glow_alpha = max(0, int(alpha * 0.2))
                glow_color = QColor(130, 180, 255, glow_alpha)
                painter.setBrush(QBrush(glow_color))
                painter.drawEllipse(QPointF(star.x, star.y), star.radius * 4.0, star.radius * 4.0)
                
                # Brillo interior
                glow_inner = max(0, int(alpha * 0.3))
                glow_inner_color = QColor(200, 220, 255, glow_inner)
                painter.setBrush(QBrush(glow_inner_color))
                painter.drawEllipse(QPointF(star.x, star.y), star.radius * 2.2, star.radius * 2.2)

            # Núcleo de la estrella
            painter.setBrush(QBrush(QColor(255, 255, 255, alpha)))
            painter.drawEllipse(QPointF(star.x, star.y), star.radius, star.radius)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def set_status(self, text: str, is_error: bool = False, is_success: bool = False):
        self.status_label.setText(text)
        if is_error:
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 600; font-size: 11px;")
            pix = self.style().standardPixmap(QStyle.StandardPixmap.SP_MessageBoxCritical)
            self.status_icon.setPixmap(pix.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio))
        elif is_success:
            self.status_label.setStyleSheet("color: #51cf66; font-weight: 600; font-size: 11px;")
            pix = self.style().standardPixmap(QStyle.StandardPixmap.SP_DialogApplyButton)
            self.status_icon.setPixmap(pix.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.status_label.setStyleSheet("color: rgba(255,255,255,0.4); font-weight: 500; font-size: 11px;")
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
        self.set_status("Verificando actualizaciones...")

        def bg_update_worker():
            try:
                import time
                current_ver = "2.0.7"
                update_res = drm_manager.check_for_updates(current_ver)

                if update_res.get("update_available"):
                    url = update_res.get("url")
                    version = update_res.get("version")
                    self.update_status_sig.emit(f"Actualización v{version} disponible. Descargando...", False, False)

                    target_file = "ui.py"
                    if url.endswith(".py"):
                        target_file = url.split("/")[-1]

                    download_res = drm_manager.download_and_apply_patch(url, target_file)

                    if download_res.get("success"):
                        self.update_status_sig.emit("¡Parche aplicado! Iniciando NEXUS...", False, True)
                        time.sleep(1.5)
                        self.finish_login_sig.emit(key, getattr(self, "aes_token", ""))
                    else:
                        err_msg = download_res.get("message", "Error al aplicar la actualización.")
                        self.update_status_sig.emit(f"Error: {err_msg}", True, False)
                        time.sleep(2.0)
                        self.finish_login_sig.emit(key, getattr(self, "aes_token", ""))
                else:
                    self.update_status_sig.emit("Licencia validada correctamente. Iniciando NEXUS...", False, True)
                    time.sleep(1.0)
                    self.finish_login_sig.emit(key, getattr(self, "aes_token", ""))
            except Exception as e:
                print(f"[NEXUS Login] Error en hilo de actualizaciones: {e}. Continuando...")
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
            self.set_status("Para reiniciar HWID necesitas Clave y Correo.", is_error=True)
            return

        self.set_status("Procesando reinicio de HWID...")

        res = drm_manager.reset_hwid(key, email)

        if res.get("success"):
            self.set_status(res.get("message"), is_success=True)
            self.show_request_modal("Reinicio de HWID", 
                                   "La solicitud de reinicio de HWID ha sido enviada exitosamente.\n"
                                   "Revisa la carpeta de instalación de NEXUS para más información.")
        else:
            self.set_status(res.get("message"), is_error=True)

    def on_recover_clicked(self):
        email = self.txt_email.text().strip()
        if not email:
            self.set_status("Por favor, ingresa tu correo para recuperar la clave.", is_error=True)
            return

        self.set_status("Buscando claves asociadas...")

        res = drm_manager.recover_license(email)

        if res.get("success"):
            self.set_status(res.get("message"), is_success=True)
            self.write_recovered_key_file(email, res)
            self.show_request_modal("Clave Recuperada",
                                   "La clave ha sido recuperada exitosamente.\n"
                                   "Revisa la carpeta de instalación de NEXUS para obtener tu clave.")
        else:
            self.set_status(res.get("message"), is_error=True)

    def write_recovered_key_file(self, email: str, res: dict):
        """Guarda la clave recuperada en archivo y muestra notificación"""
        key = res.get("license_key") or res.get("key") or ""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            contenido = f"Correo: {email}\n"
            if key:
                contenido += f"Clave Recuperada: {key}\n"
            else:
                contenido += f"{res.get('message', 'Revisa tu correo, también se envió la clave.')}\n"
            RECOVERED_KEY_PATH.write_text(contenido, encoding="utf-8")
        except Exception as e:
            print(f"Error guardando clave recuperada: {e}")

    def show_request_modal(self, title: str, message: str):
        """Modal informativo para notificar al usuario"""
        QMessageBox.information(
            self,
            title,
            message
        )

    def finish_login(self, verified_key: str, aes_token: str):
        self.accept_code = True

        if self.parent_launcher and hasattr(self.parent_launcher, "on_login_success"):
            self.parent_launcher.on_login_success(verified_key, aes_token)
        else:
            print("[NEXUS Login] Login exitoso. Clave verificada:", verified_key)

        self.accept()


