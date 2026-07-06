import sys
import os
import math
import random
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QRadialGradient, QIcon

class StarField(QWidget):
    """Fondo animado con estrellas flotantes"""

    class Star:
        def __init__(self, w, h):
            self.reset(w, h, initial=True)

        def reset(self, w, h, initial=False):
            self.x = random.uniform(0, w)
            self.y = random.uniform(0, h) if initial else random.uniform(-10, 0)
            self.size = random.uniform(0.7, 2.6)
            self.speed = random.uniform(0.12, 0.50)
            self.opacity = random.uniform(0.25, 0.92)
            self.twinkle_speed = random.uniform(0.01, 0.04)
            self.twinkle_phase = random.uniform(0, math.pi * 2)
            self.drift = random.uniform(-0.07, 0.07)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._tick = 0
        self._stars = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(30)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        count = max(int((w * h) / 3000), 55)
        self._stars = [self.Star(w, h) for _ in range(count)]

    def _update(self):
        self._tick += 1
        w, h = self.width(), self.height()
        for s in self._stars:
            s.y += s.speed
            s.x += s.drift
            s.twinkle_phase += s.twinkle_speed
            if s.y > h + 5:
                s.reset(w, h)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor("#080b14"))

        for cx, cy, col in [
            (0, 0, QColor(10, 28, 55, 16)),
            (w, h, QColor(8, 35, 18, 13)),
            (w // 2, h // 2, QColor(5, 18, 40, 9)),
        ]:
            grad = QRadialGradient(QPointF(cx, cy), w * 0.65)
            grad.setColorAt(0, col)
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - w * 0.65, cy - w * 0.65, w * 1.3, w * 1.3))

        for s in self._stars:
            twinkle = 0.5 + 0.5 * math.sin(s.twinkle_phase)
            alpha = max(18, min(int(s.opacity * twinkle * 215), 225))

            if s.size > 2.0:
                color = QColor(175, 215, 255, alpha)
            elif s.size > 1.4:
                color = QColor(205, 230, 255, alpha)
            else:
                color = QColor(238, 243, 255, alpha)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QRectF(s.x - s.size / 2, s.y - s.size / 2, s.size, s.size))

            if s.size > 1.9:
                glow = QColor(color)
                glow.setAlpha(alpha // 5)
                pen = QPen(glow)
                pen.setWidthF(0.55)
                painter.setPen(pen)
                l = s.size * 2.0
                painter.drawLine(QPointF(s.x - l, s.y), QPointF(s.x + l, s.y))
                painter.drawLine(QPointF(s.x, s.y - l), QPointF(s.x, s.y + l))
        painter.end()


class UpdateWindow(QWidget):
    def __init__(self, check_info: dict, download_callback, skip_callback):
        super().__init__()
        self.check_info = check_info
        self.download_callback = download_callback
        self.skip_callback = skip_callback
        
        self.setWindowTitle("NEXUS AI - Actualización")
        self.setFixedSize(580, 460)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.starfield = StarField(self)
        self.starfield.setGeometry(0, 0, 580, 460)

        self.container = QWidget(self)
        self.container.setObjectName("mainContainer")
        self.container.setGeometry(25, 25, 530, 410)

        self.setup_style()
        self.init_ui()

        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(350)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_in.start()

        QTimer.singleShot(500, self.prompt_update)

    def setup_style(self):
        self.container.setStyleSheet("""
            QWidget#mainContainer {
                background-color: rgba(8, 12, 22, 0.90);
                border-radius: 18px;
                border: 1px solid rgba(82, 160, 90, 0.22);
            }
            QLabel#appTitle {
                font-size: 26px;
                font-weight: 600;
                color: #c0dd97;
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                letter-spacing: 1px;
            }
            QLabel#appSubtitle {
                font-size: 12px;
                color: rgba(160, 190, 165, 0.45);
                font-family: 'Segoe UI', sans-serif;
                letter-spacing: 0.3px;
            }
            QFrame#statusCard {
                background: rgba(12, 18, 34, 0.75);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.055);
            }
            QLabel#statusIcon { font-size: 40px; }
            QLabel#statusText {
                font-size: 17px;
                font-weight: 500;
                color: #d4edd6;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel#statusDetails {
                font-size: 12px;
                color: rgba(168, 200, 172, 0.50);
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton {
                background: rgba(52, 120, 58, 0.75);
                border: 1px solid rgba(82, 160, 90, 0.40);
                border-radius: 10px;
                padding: 11px 26px;
                color: #d4edd6;
                font-weight: 500;
                font-size: 12px;
                font-family: 'Segoe UI', sans-serif;
                letter-spacing: 0.8px;
                min-width: 130px;
            }
            QPushButton:hover {
                background: rgba(62, 140, 68, 0.88);
                border-color: rgba(100, 190, 110, 0.60);
                color: #e8f5e9;
            }
            QPushButton:pressed { background: rgba(40, 100, 46, 0.95); }
            QPushButton#secondaryBtn {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.09);
                color: rgba(255, 140, 140, 0.65);
            }
            QPushButton#secondaryBtn:hover {
                background: rgba(200, 60, 60, 0.09);
                border-color: rgba(200, 80, 80, 0.28);
                color: rgba(255, 130, 130, 0.90);
            }
            QProgressBar {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                border: none;
                max-height: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b6d11, stop:1 #97c459);
                border-radius: 4px;
            }
            QLabel#versionLabel {
                color: rgba(120, 145, 125, 0.28);
                font-size: 10px;
                font-family: 'Segoe UI', sans-serif;
                letter-spacing: 0.4px;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(28, 18, 28, 18)
        main_layout.setSpacing(12)

        header = QHBoxLayout()
        header.addStretch()
        main_layout.addLayout(header)

        self.title_label = QLabel("NEXUS AI")
        self.title_label.setObjectName("appTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Actualización Disponible")
        self.subtitle_label.setObjectName("appSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.subtitle_label)

        main_layout.addSpacing(6)

        self.status_card = QFrame()
        self.status_card.setObjectName("statusCard")
        card_layout = QVBoxLayout(self.status_card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(6)

        self.icon_label = QLabel("✨")
        self.icon_label.setObjectName("statusIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Preparando...")
        self.status_label.setObjectName("statusText")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.details_label = QLabel("Obteniendo detalles...")
        self.details_label.setObjectName("statusDetails")
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()

        card_layout.addWidget(self.icon_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.details_label)
        card_layout.addSpacing(4)
        card_layout.addWidget(self.progress_bar)

        main_layout.addWidget(self.status_card)
        main_layout.addSpacing(6)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.skip_btn = QPushButton("Omitir por ahora")
        self.skip_btn.setObjectName("secondaryBtn")
        self.skip_btn.clicked.connect(self.start_main_app)

        self.check_btn = QPushButton("ACTUALIZAR AHORA")
        self.check_btn.clicked.connect(self.start_download)
        self.check_btn.setEnabled(False)

        button_layout.addWidget(self.skip_btn)
        button_layout.addWidget(self.check_btn)
        main_layout.addLayout(button_layout)

        self.version_label = QLabel("NEXUS Auto-Updater")
        self.version_label.setObjectName("versionLabel")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.version_label)

        self.center_window()
        self.drag_position = None
        self.container.mousePressEvent = self.mousePressEvent
        self.container.mouseMoveEvent = self.mouseMoveEvent

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_position)
            self.drag_position = event.globalPosition().toPoint()

    def update_status(self, icon, text, details):
        self.icon_label.setText(icon)
        self.status_label.setText(text)
        self.details_label.setText(details)

    def prompt_update(self):
        version = self.check_info.get("version", "desconocida")
        changelog = self.check_info.get("changelog", "Mejoras y correcciones.")
        
        self.update_status("✨", "Actualización Disponible", f"Versión {version}\n\nNovedades:\n{changelog[:100]}...")
        self.check_btn.setEnabled(True)

    def start_download(self):
        self.update_status("📥", "Descargando e Instalando...", "Aplicando parche de actualización en segundo plano...")
        self.check_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.show()
        
        # Start the heavy download in a separate thread so UI doesn't freeze
        import threading
        t = threading.Thread(target=self._run_download, daemon=True)
        t.start()
        
    def _run_download(self):
        try:
            self.download_callback()
            # Once download is done and .bat is launched, we exit the application to let .bat run.
            QTimer.singleShot(100, lambda: QApplication.quit())
        except Exception as e:
            print(f"Error during download: {e}")
            QTimer.singleShot(100, self.start_main_app)
            
    def start_main_app(self):
        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.setDuration(250)
        self._fade_out.setStartValue(1)
        self._fade_out.setEndValue(0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self._finish_and_skip)
        self._fade_out.start()
        
    def _finish_and_skip(self):
        self.close()
        self.skip_callback()
