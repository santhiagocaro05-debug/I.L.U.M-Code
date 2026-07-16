"""
shop.py — ILUM Store  v2
Productos · Métodos de pago múltiples · Diseño mejorado
"""

import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QGridLayout, QDialog,
    QLineEdit, QGraphicsDropShadowEffect, QSizePolicy,
    QButtonGroup, QStackedWidget, QAbstractButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QBrush, QPen, QFont, QCursor, QDesktopServices
from PyQt6.QtWidgets import QProgressBar

try:
    import qtawesome as qta
    HAS_QTA = True
except ImportError:
    HAS_QTA = False

# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════
def apply_glass_shadow(widget, blur_radius=20, y_offset=4, alpha=100):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)

UNLOCK_FILE = os.path.join(os.path.expanduser("~"), ".ilum_unlocks.json")

def load_unlocks() -> dict:
    if os.path.exists(UNLOCK_FILE):
        try:
            with open(UNLOCK_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_unlocks(data: dict):
    try:
        with open(UNLOCK_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
#  Catálogo
# ══════════════════════════════════════════════════════════════════════════════
PRODUCTS = [
    {
        "id": "neon_color",
        "name": "Color Neón",
        "subtitle": "Acento de interfaz personalizable",
        "description": "Elige el color de acento de toda tu interfaz ILUM. Soporte para cualquier tono: neón, pastel o clásico. El cambio se aplica instantáneamente.",
        "price": 0.00,
        "price_label": "GRATIS",
        "icon": "fa5s.palette",
        "icon_color": "#b48aff",
        "accent": "#b48aff",
        "badge": "FREE",
        "badge_color": "#27ae60",
        "glow": "rgba(180,138,255,0.25)",
        "gradient": ("rgba(80,40,160,0.45)", "rgba(40,15,90,0.30)"),
    },
    {
        "id": "gif_wallpaper",
        "name": "GIF Wallpaper",
        "subtitle": "Fondos de pantalla animados",
        "description": "Carga cualquier GIF como fondo de pantalla. Compatible con alta resolución y looping infinito. Incluye 10 fondos premium al activar.",
        "price": 4.00,
        "price_label": "USD $4",
        "icon": "fa5s.film",
        "icon_color": "#ff6eb4",
        "accent": "#ff6eb4",
        "badge": "$4",
        "badge_color": "#e91e8c",
        "glow": "rgba(255,110,180,0.25)",
        "gradient": ("rgba(160,20,100,0.45)", "rgba(80,5,55,0.30)"),
    },
    {
        "id": "custom_fonts",
        "name": "Fuentes Premium",
        "subtitle": "Tipografías exclusivas para tu UI",
        "description": "Más de 50 fuentes premium: tech, monospace y creativas. Instala tus propias fuentes desde el sistema de archivos.",
        "price": 2.99,
        "price_label": "USD $2.99",
        "icon": "fa5s.font",
        "icon_color": "#4fc3f7",
        "accent": "#4fc3f7",
        "badge": "$2.99",
        "badge_color": "#0288d1",
        "glow": "rgba(79,195,247,0.25)",
        "gradient": ("rgba(10,70,140,0.45)", "rgba(5,30,80,0.30)"),
    },
    {
        "id": "widget_customization",
        "name": "Widgets PRO",
        "subtitle": "Estilos y colores personalizados para widgets",
        "description": "Aplica fondos holográficos y bordes neón a todos los widgets del panel principal sin perder rendimiento.",
        "price": 0.00,
        "price_label": "GRATIS",
        "icon": "fa5s.th-large",
        "icon_color": "#00ffcc",
        "accent": "#00ffcc",
        "badge": "PRO",
        "badge_color": "#00e6b8",
        "glow": "rgba(0,255,204,0.25)",
        "gradient": ("rgba(0,120,100,0.45)", "rgba(0,60,50,0.30)"),
    }
]

# ── métodos de pago ──────────────────────────────────────────────────────────
PAYMENT_METHODS = [
    {
        "id": "paypal",
        "label": "PayPal",
        "icon": "fa5b.paypal",
        "color": "#009cde",
        "bg":    "rgba(0,156,222,0.12)",
        "border":"rgba(0,156,222,0.35)",
        "url": "https://paypal.me/ilumstore/{price}"
    },
    {
        "id": "dolarapp",
        "label": "DolarApp",
        "icon": "fa5s.dollar-sign",
        "color": "#00d09c",
        "bg":    "rgba(0,208,156,0.12)",
        "border":"rgba(0,208,156,0.35)",
        "url": "https://dolarapp.com/pay/ilum?amount={price}&note={product_id}"
    },
    {
        "id": "crypto",
        "label": "Cripto",
        "icon": "fa5b.bitcoin",
        "color": "#f7931a",
        "bg":    "rgba(247,147,26,0.12)",
        "border":"rgba(247,147,26,0.35)",
        "url": "https://commerce.coinbase.com/checkout/ilum"
    },
    {
        "id": "discord",
        "label": "Discord",
        "icon": "fa5b.discord",
        "color": "#5865f2",
        "bg":    "rgba(88,101,242,0.12)",
        "border":"rgba(88,101,242,0.35)",
        "url": "https://discord.gg/ilum"
    },
]

PAYMENT_INSTRUCTIONS = {
    "paypal":   "Se abrirá PayPal para enviar {price} USD. Nota: {product_id}",
    "dolarapp": "Se abrirá DolarApp para enviar {price} USD. Nota: {product_id}",
    "crypto":   "Transfiere {price} USD a la Wallet oficial de ILUM.",
    "discord":  "Únete a Discord, abre un ticket !comprar {product_id}",
}

# ══════════════════════════════════════════════════════════════════════════════
#  Botón de método de pago
# ══════════════════════════════════════════════════════════════════════════════
class PaymentMethodBtn(QAbstractButton):
    def __init__(self, method: dict, parent=None):
        super().__init__(parent)
        self.method = method
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = self.method

        # fondo
        if self.isChecked():
            bg = QColor(m["color"])
            bg.setAlpha(50)
            border = QColor(m["color"])
            border.setAlpha(200)
        else:
            bg = QColor(255, 255, 255, 10)
            border = QColor(255, 255, 255, 25)

        rect = self.rect().adjusted(1, 1, -1, -1)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, 1.5))
        p.drawRoundedRect(rect, 12, 12)

        # icono
        if HAS_QTA:
            icon_color = m["color"] if self.isChecked() else "rgba(255,255,255,0.50)"
            pix = qta.icon(m["icon"], color=icon_color).pixmap(18, 18)
            p.drawPixmap(14, (self.height() - 18) // 2, pix)

        # label
        font = QFont()
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold if self.isChecked() else QFont.Weight.Normal)
        p.setFont(font)
        lc = QColor(m["color"]) if self.isChecked() else QColor(255, 255, 255, 160)
        p.setPen(QPen(lc))
        p.drawText(QRect(40, 0, self.width() - 50, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, m["label"])

        # check dot
        if self.isChecked():
            cx = self.width() - 18
            cy = self.height() // 2
            p.setBrush(QBrush(QColor(m["color"])))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(cx, cy), 5, 5)

        p.end()

    def sizeHint(self):
        return self.size()

# ══════════════════════════════════════════════════════════════════════════════
#  Modal de compra rediseñado
# ══════════════════════════════════════════════════════════════════════════════
class PurchaseModal(QDialog):
    purchase_confirmed = pyqtSignal(str)

    def __init__(self, product: dict, parent=None):
        super().__init__(parent)
        self.product = product
        self.selected_method: str | None = None
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(480)
        self.setMaximumWidth(520)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(22,14,48,0.99),
                    stop:1 rgba(12,8,28,0.99));
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 28px;
            }
        """)
        apply_glass_shadow(card, blur_radius=80, y_offset=20, alpha=220)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(32, 28, 32, 28)
        cl.setSpacing(0)

        # ── header con gradiente de acento ────────────────────────────────────
        accent = self.product["accent"]
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {accent}22, stop:1 transparent);
                border: none;
                border-radius: 16px;
                padding: 4px;
            }}
        """)
        hf_layout = QHBoxLayout(header_frame)
        hf_layout.setContentsMargins(14, 14, 14, 14)

        if HAS_QTA:
            icon_bg = QFrame()
            icon_bg.setFixedSize(52, 52)
            icon_bg.setStyleSheet(f"""
                QFrame {{
                    background: {accent}22;
                    border: 1px solid {accent}44;
                    border-radius: 14px;
                }}
            """)
            icon_inner = QVBoxLayout(icon_bg)
            icon_inner.setContentsMargins(0, 0, 0, 0)
            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setPixmap(qta.icon(self.product["icon"], color=accent).pixmap(26, 26))
            icon_inner.addWidget(icon_lbl)
            hf_layout.addWidget(icon_bg)
            hf_layout.addSpacing(14)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        name_l = QLabel(self.product["name"])
        name_l.setStyleSheet(f"color: #fff; font-size: 19px; font-weight: 700; background:transparent; border:none;")
        sub_l = QLabel(self.product["subtitle"])
        sub_l.setStyleSheet("color: rgba(255,255,255,0.40); font-size: 12px; background:transparent; border:none;")
        info_col.addWidget(name_l)
        info_col.addWidget(sub_l)
        hf_layout.addLayout(info_col)
        hf_layout.addStretch()

        price_col = QVBoxLayout()
        price_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        price_val = QLabel(self.product["price_label"])
        price_color = "#27ae60" if self.product["price"] == 0 else accent
        price_val.setStyleSheet(f"color: {price_color}; font-size: 22px; font-weight: 800; background:transparent; border:none;")
        price_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        price_col.addWidget(price_val)
        hf_layout.addLayout(price_col)
        cl.addWidget(header_frame)
        cl.addSpacing(20)

        # ── descripción ───────────────────────────────────────────────────────
        desc_l = QLabel(self.product["description"])
        desc_l.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 13px; line-height:1.6; background:transparent; border:none;")
        desc_l.setWordWrap(True)
        cl.addWidget(desc_l)
        cl.addSpacing(22)

        # ── sección de pago (solo si cuesta algo) ─────────────────────────────
        if self.product["price"] > 0:
            pay_label = QLabel("MÉTODO DE PAGO")
            pay_label.setStyleSheet(
                "color: rgba(255,255,255,0.30); font-size: 10px; font-weight: 700;"
                " letter-spacing: 3px; background:transparent; border:none;"
            )
            cl.addWidget(pay_label)
            cl.addSpacing(10)

            # grid 2×2 de métodos
            method_grid = QGridLayout()
            method_grid.setSpacing(10)
            self.method_group = QButtonGroup(self)
            self.method_group.setExclusive(True)
            self.pay_btns: list[PaymentMethodBtn] = []

            for i, m in enumerate(PAYMENT_METHODS):
                btn = PaymentMethodBtn(m)
                self.method_group.addButton(btn, i)
                row, col = divmod(i, 2)
                method_grid.addWidget(btn, row, col)
                self.pay_btns.append(btn)

            self.method_group.idToggled.connect(self._on_method_changed)
            cl.addLayout(method_grid)
            cl.addSpacing(16)

            # instrucciones dinámicas
            self.instr_frame = QFrame()
            self.instr_frame.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: 14px;
                }
            """)
            instr_lay = QVBoxLayout(self.instr_frame)
            instr_lay.setContentsMargins(16, 14, 16, 14)
            self.instr_lbl = QLabel("← Selecciona un método de pago")
            self.instr_lbl.setStyleSheet(
                "color: rgba(255,255,255,0.30); font-size: 13px;"
                " background:transparent; border:none;"
            )
            self.instr_lbl.setWordWrap(True)
            self.instr_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            instr_lay.addWidget(self.instr_lbl)
            self.instr_frame.hide()
            cl.addWidget(self.instr_frame)
            cl.addSpacing(6)

        cl.addSpacing(18)

        # ── separador ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.06); border:none;")
        cl.addWidget(sep)
        cl.addSpacing(18)

        # ── botones ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 13px;
                color: rgba(255,255,255,0.40);
                font-size: 14px;
                padding: 13px 28px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.09);
                color: rgba(255,255,255,0.75);
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        action_lbl = "Activar gratis" if self.product["price"] == 0 else "Ya pagué →"
        btn_accent = "#27ae60" if self.product["price"] == 0 else accent
        btn_accent_h = "#2ecc71" if self.product["price"] == 0 else f"{accent}cc"

        self.pay_now_btn = QPushButton("PAGAR AHORA")
        self.pay_now_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.pay_now_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.08);
                border: 1px solid {btn_accent};
                border-radius: 13px;
                color: #fff;
                font-size: 14px;
                font-weight: 700;
                padding: 13px 36px;
            }}
            QPushButton:hover {{
                background: {btn_accent}55;
            }}
            QPushButton:disabled {{
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.25);
                border-color: rgba(255,255,255,0.1);
            }}
        """)
        self.pay_now_btn.clicked.connect(self._on_pay_now)
        if self.product["price"] == 0:
            self.pay_now_btn.hide()
        else:
            self.pay_now_btn.setEnabled(False)

        self.confirm_btn = QPushButton(action_lbl)
        self.confirm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {btn_accent}, stop:1 {btn_accent_h});
                border: none;
                border-radius: 13px;
                color: #fff;
                font-size: 14px;
                font-weight: 700;
                padding: 13px 36px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {btn_accent_h}, stop:1 {btn_accent});
            }}
            QPushButton:disabled {{
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.25);
            }}
        """)
        if self.product["price"] > 0:
            self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._on_confirm)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.pay_now_btn)
        btn_row.addWidget(self.confirm_btn)
        cl.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 8px;
                background: rgba(0,0,0,0.4);
                height: 18px;
                text-align: center;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }}
            QProgressBar::chunk {{
                background: {btn_accent_h};
                border-radius: 7px;
            }}
        """)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        cl.addSpacing(15)
        cl.addWidget(self.progress_bar)

        outer.addWidget(card)

    def _on_method_changed(self, btn_id: int, checked: bool):
        if not checked:
            return
        m = PAYMENT_METHODS[btn_id]
        self.selected_method = m["id"]
        raw = PAYMENT_INSTRUCTIONS[m["id"]].format(product_id=self.product["id"], price=self.product["price"])
        color = m["color"]
        self.instr_lbl.setStyleSheet(
            f"color: {color}cc; font-size: 13px; background:transparent; border:none;"
        )
        self.instr_lbl.setText(raw)
        self.instr_frame.show()
        
        self.current_pay_url = m["url"].format(price=self.product["price"], product_id=self.product["id"])
        self.pay_now_btn.setEnabled(True)
        # repintar botones
        for btn in self.pay_btns:
            btn.update()

    def _on_pay_now(self):
        QDesktopServices.openUrl(QUrl(self.current_pay_url))
        self.confirm_btn.setEnabled(True)

    def _on_confirm(self):
        if self.product["price"] > 0:
            self.confirm_btn.setEnabled(False)
            self.pay_now_btn.setEnabled(False)
            self.progress_bar.show()
            self.progress_bar.setFormat("Conectando con pasarela...")
            self.progress_value = 0
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_progress)
            self.timer.start(150)
        else:
            self.purchase_confirmed.emit(self.product["id"])
            self.accept()

    def _update_progress(self):
        self.progress_value += 4
        self.progress_bar.setValue(min(self.progress_value, 100))
        
        if self.progress_value == 28:
            self.progress_bar.setFormat("Verificando transacción...")
        elif self.progress_value == 60:
            self.progress_bar.setFormat("Validando comprobante...")
        elif self.progress_value >= 100:
            self.timer.stop()
            self.progress_bar.setFormat("Pago Validado ✓")
            
            self.finish_timer = QTimer(self)
            self.finish_timer.setSingleShot(True)
            self.finish_timer.timeout.connect(self._finish_purchase)
            self.finish_timer.start(800)

    def _finish_purchase(self):
        self.purchase_confirmed.emit(self.product["id"])
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════
#  Tarjeta de producto rediseñada
# ══════════════════════════════════════════════════════════════════════════════
class ProductCard(QFrame):
    buy_requested = pyqtSignal(dict)

    def __init__(self, product: dict, unlocked: bool = False, parent=None):
        super().__init__(parent)
        self.product = product
        self.unlocked = unlocked
        self.setMinimumWidth(220)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build_ui()
        apply_glass_shadow(self, blur_radius=45, y_offset=12, alpha=160)

    def _build_ui(self):
        g1, g2 = self.product["gradient"]
        accent = self.product["accent"]
        glow = self.product["glow"]

        self.setStyleSheet(f"""
            ProductCard {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {g1}, stop:1 {g2});
                border: 1px solid {accent}33;
                border-radius: 24px;
            }}
            ProductCard:hover {{
                border: 1px solid {accent}77;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(0)

        # ── top row: icono + badge ─────────────────────────────────────────────
        top = QHBoxLayout()

        if HAS_QTA:
            icon_bg = QFrame()
            icon_bg.setFixedSize(46, 46)
            icon_bg.setStyleSheet(f"""
                QFrame {{
                    background: {accent}18;
                    border: 1px solid {accent}33;
                    border-radius: 13px;
                }}
            """)
            ib_lay = QVBoxLayout(icon_bg)
            ib_lay.setContentsMargins(0, 0, 0, 0)
            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic = "#2ecc71" if self.unlocked else accent
            icon_lbl.setPixmap(qta.icon(self.product["icon"], color=ic).pixmap(22, 22))
            ib_lay.addWidget(icon_lbl)
            top.addWidget(icon_bg)

        top.addStretch()

        if self.unlocked:
            badge = QLabel("✓ ACTIVO")
            badge.setStyleSheet(
                "background: rgba(39,174,96,0.20); color: #2ecc71;"
                " font-size: 10px; font-weight: 700; letter-spacing: 2px;"
                " padding: 5px 12px; border-radius: 20px;"
                " border: 1px solid rgba(46,204,113,0.30);"
            )
        else:
            bc = self.product["badge_color"]
            badge = QLabel(self.product["badge"])
            badge.setStyleSheet(
                f"background: {bc}22; color: {bc};"
                " font-size: 10px; font-weight: 700; letter-spacing: 1px;"
                f" padding: 5px 12px; border-radius: 20px; border: 1px solid {bc}44;"
            )
        top.addWidget(badge)
        layout.addLayout(top)
        layout.addSpacing(16)

        # ── nombre ────────────────────────────────────────────────────────────
        name_lbl = QLabel(self.product["name"])
        name_lbl.setStyleSheet(
            "color: #fff; font-size: 17px; font-weight: 700;"
            " background:transparent; border:none;"
        )
        layout.addWidget(name_lbl)
        layout.addSpacing(4)

        sub_lbl = QLabel(self.product["subtitle"])
        sub_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.40); font-size: 12px;"
            " background:transparent; border:none;"
        )
        sub_lbl.setWordWrap(True)
        layout.addWidget(sub_lbl)
        layout.addSpacing(14)

        # ── separador delgado ─────────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {accent}22; border:none;")
        layout.addWidget(sep)
        layout.addSpacing(14)

        # ── descripción corta ─────────────────────────────────────────────────
        desc_lbl = QLabel(self.product["description"])
        desc_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.38); font-size: 12px;"
            " background:transparent; border:none; line-height:1.5;"
        )
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        layout.addSpacing(18)

        # ── íconos de métodos de pago aceptados ───────────────────────────────
        if self.product["price"] > 0 and not self.unlocked:
            pm_row = QHBoxLayout()
            pm_row.setSpacing(6)
            if HAS_QTA:
                for m in PAYMENT_METHODS:
                    pill = QFrame()
                    pill.setFixedSize(28, 28)
                    pill.setStyleSheet(f"""
                        QFrame {{
                            background: {m['bg']};
                            border: 1px solid {m['border']};
                            border-radius: 8px;
                        }}
                    """)
                    pill_lay = QVBoxLayout(pill)
                    pill_lay.setContentsMargins(0, 0, 0, 0)
                    pm_icon = QLabel()
                    pm_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    pm_icon.setPixmap(qta.icon(m["icon"], color=m["color"]).pixmap(14, 14))
                    pill_lay.addWidget(pm_icon)
                    pm_row.addWidget(pill)
            pm_row.addStretch()
            layout.addLayout(pm_row)
            layout.addSpacing(12)

        # ── precio + botón ────────────────────────────────────────────────────
        bottom = QHBoxLayout()
        price_lbl = QLabel(self.product["price_label"])
        pc = "#2ecc71" if self.product["price"] == 0 else "#fff"
        price_lbl.setStyleSheet(
            f"color: {pc}; font-size: 18px; font-weight: 800;"
            " background:transparent; border:none;"
        )
        bottom.addWidget(price_lbl)
        bottom.addStretch()

        if self.unlocked:
            btn = QPushButton("En uso")
            btn.setEnabled(False)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(46,204,113,0.12);
                    border: 1px solid rgba(46,204,113,0.28);
                    border-radius: 11px;
                    color: #2ecc71;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 9px 20px;
                }
            """)
        else:
            lbl = "Activar" if self.product["price"] == 0 else "Comprar"
            a = accent
            btn = QPushButton(lbl)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {a}33, stop:1 {a}18);
                    border: 1px solid {a}66;
                    border-radius: 11px;
                    color: {a};
                    font-size: 12px;
                    font-weight: 700;
                    padding: 9px 22px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {a}55, stop:1 {a}33);
                    border-color: {a};
                }}
                QPushButton:pressed {{
                    background: {a}44;
                }}
            """)
            btn.clicked.connect(lambda: self.buy_requested.emit(self.product))

        bottom.addWidget(btn)
        layout.addLayout(bottom)


# ══════════════════════════════════════════════════════════════════════════════
#  Widget principal de la tienda
# ══════════════════════════════════════════════════════════════════════════════
class ShopWidget(QWidget):
    item_unlocked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.unlocks: dict = load_unlocks()
        self.cards: dict[str, ProductCard] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { background: rgba(0,0,0,0.2); width: 10px; margin: 0; border-radius: 5px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.25); border-radius: 5px; min-height: 40px; }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.45); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(32)

        cl.addLayout(self._build_header())

        # grid
        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(grid_w)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(18)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)

        for i, product in enumerate(PRODUCTS):
            unlocked = self.unlocks.get(product["id"], False)
            card = ProductCard(product, unlocked=unlocked)
            card.buy_requested.connect(self._open_modal)
            row, col = divmod(i, 2)
            self.grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop)
            self.cards[product["id"]] = card

        cl.addWidget(grid_w)
        cl.addLayout(self._build_footer())
        cl.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

    def _build_header(self) -> QVBoxLayout:
        h = QVBoxLayout()
        h.setSpacing(6)

        row = QHBoxLayout()
        if HAS_QTA:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(
                qta.icon("fa5s.store", color="rgba(180,138,255,0.75)").pixmap(28, 28)
            )
            row.addWidget(icon_lbl)
            row.addSpacing(10)

        title = QLabel("NEXUS STORE")
        title.setStyleSheet(
            "color: #fff; font-size: 28px; font-weight: 800;"
            " letter-spacing: 5px; background:transparent; border:none;"
        )
        row.addWidget(title)
        row.addStretch()

        # total desbloqueados
        total = sum(1 for p in PRODUCTS if self.unlocks.get(p["id"], False))
        if total:
            owned_lbl = QLabel(f"  {total} / {len(PRODUCTS)} activos  ")
            owned_lbl.setStyleSheet(
                "background: rgba(39,174,96,0.15); color: #2ecc71;"
                " font-size: 12px; font-weight: 600; letter-spacing: 1px;"
                " padding: 6px 14px; border-radius: 20px;"
                " border: 1px solid rgba(46,204,113,0.25);"
            )
            row.addWidget(owned_lbl)

        h.addLayout(row)

        sub = QLabel("Complementos exclusivos para personalizar tu experiencia")
        sub.setStyleSheet(
            "color: rgba(255,255,255,0.30); font-size: 13px;"
            " background:transparent; border:none;"
        )
        h.addWidget(sub)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.06); border:none;")
        h.addSpacing(6)
        h.addWidget(sep)
        return h

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)

        # métodos aceptados
        if HAS_QTA:
            methods_lbl = QLabel("Pagos:")
            methods_lbl.setStyleSheet(
                "color: rgba(255,255,255,0.20); font-size: 11px; background:transparent; border:none;"
            )
            row.addWidget(methods_lbl)
            for m in PAYMENT_METHODS:
                ic = QLabel()
                ic.setPixmap(qta.icon(m["icon"], color=m["color"] + "88").pixmap(16, 16))
                row.addWidget(ic)

        row.addStretch()

        if HAS_QTA:
            lock_ic = QLabel()
            lock_ic.setPixmap(qta.icon("fa5s.lock", color="rgba(255,255,255,0.18)").pixmap(12, 12))
            row.addWidget(lock_ic)

        note = QLabel("Desbloqueos permanentes · Guardados en tu perfil")
        note.setStyleSheet(
            "color: rgba(255,255,255,0.18); font-size: 11px; background:transparent; border:none;"
        )
        row.addWidget(note)
        return row

    def _open_modal(self, product: dict):
        modal = PurchaseModal(product, parent=self)
        modal.purchase_confirmed.connect(self._on_purchase)
        modal.exec()

    def _on_purchase(self, product_id: str):
        self.unlocks[product_id] = True
        save_unlocks(self.unlocks)

        if product_id in self.cards:
            idx = next((i for i, p in enumerate(PRODUCTS) if p["id"] == product_id), None)
            if idx is not None:
                r, c = divmod(idx, 2)
                prod = next(p for p in PRODUCTS if p["id"] == product_id)
                old = self.cards[product_id]
                new_card = ProductCard(prod, unlocked=True)
                new_card.buy_requested.connect(self._open_modal)
                self.grid_layout.removeWidget(old)
                old.deleteLater()
                self.grid_layout.addWidget(new_card, r, c)
                self.cards[product_id] = new_card

        self.item_unlocked.emit(product_id)
        self._show_toast(product_id)

    def _show_toast(self, product_id: str):
        name = next((p["name"] for p in PRODUCTS if p["id"] == product_id), product_id)
        accent = next((p["accent"] for p in PRODUCTS if p["id"] == product_id), "#27ae60")
        toast = QLabel(f"  ✓  {name} activado  ", self.window())
        toast.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {accent}dd, stop:1 {accent}99);
            color: #fff;
            font-size: 13px;
            font-weight: 700;
            border-radius: 14px;
            padding: 12px 22px;
        """)
        toast.adjustSize()
        win = self.window()
        toast.move(win.width() - toast.width() - 28, win.height() - toast.height() - 28)
        toast.show()
        toast.raise_()
        QTimer.singleShot(3000, toast.deleteLater)

    def is_unlocked(self, product_id: str) -> bool:
        return self.unlocks.get(product_id, False)