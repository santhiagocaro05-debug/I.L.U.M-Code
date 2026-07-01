"""ui_styles.py — ILUM Liquid Glass Visual Enhancement Module
Provides CSS/QSS stylesheet generators for the Liquid Glass aesthetic.
Zero functional logic — purely visual stylesheet strings.

Usage in ui.py (add at top after imports):
    from ui_styles import (
        liquid_glass_widget_style,
        liquid_glass_caption_style,
        liquid_glass_settings_style,
        liquid_glass_header_style,
        liquid_glass_central_style,
        CAPTION_ANIMATION_JS,
    )
"""
from __future__ import annotations


def _rgba_from_hex(hex_color: str, alpha: float = 0.18) -> str:
    """Convert #rrggbb to rgba(r,g,b,alpha)."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return f"rgba(245,158,11,{alpha})"


def _rgba_from_pri(C_PRI: str, alpha: float) -> str:
    return _rgba_from_hex(C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b", alpha)


# ─────────────────────────────────────────────────────────────────────────────
# LIQUID GLASS WIDGET PANELS
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_widget_style(
    object_name: str,
    C_PRI: str = "#f59e0b",
    C_BORDER: str = "rgba(245,158,11,0.45)",
    C_TEXT: str = "#fde68a",
) -> str:
    """Returns a Liquid Glass QSS block for a named widget panel."""
    glow = _rgba_from_hex(C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b", 0.12)
    border_glow = _rgba_from_hex(C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b", 0.55)
    fill = _rgba_from_hex(C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b", 0.07)
    return f"""
        QWidget#{object_name} {{
            background: qlineargradient(
                x1:0, y1:0, x2:0.8, y2:1,
                stop:0 {fill},
                stop:0.5 rgba(255,255,255,0.02),
                stop:1 rgba(0,0,0,0.15)
            );
            border: 1px solid {border_glow};
            border-top: 1px solid rgba(255,255,255,0.15);
            border-radius: 16px;
        }}
        QWidget#{object_name}:hover {{
            background: qlineargradient(
                x1:0, y1:0, x2:0.8, y2:1,
                stop:0 {_rgba_from_hex(C_PRI.lstrip('#')[:6] if C_PRI.startswith('#') else 'f59e0b', 0.10)},
                stop:0.5 rgba(255,255,255,0.05),
                stop:1 rgba(0,0,0,0.12)
            );
            border: 1px solid {C_PRI};
            border-top: 1px solid rgba(255,255,255,0.25);
        }}
    """


def liquid_glass_title_style(C_PRI: str = "#f59e0b") -> str:
    """Widget section title label style."""
    return (
        f"font-weight: 700; font-size: 10px; letter-spacing: 2.5px; "
        f"color: {C_PRI}; border: none; background: transparent; "
        f"text-transform: uppercase;"
    )


def liquid_glass_progress_style(C_PRI: str = "#f59e0b", C_BORDER: str = "rgba(245,158,11,0.45)") -> str:
    """Progress bar with glowing liquid chunk."""
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return f"""
        QProgressBar {{
            border: 1px solid {C_BORDER};
            border-radius: 7px;
            text-align: center;
            background: rgba(0,0,0,0.30);
            color: rgba(255,255,255,0.85);
            height: 14px;
            font-size: 10px;
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba({r},{g},{b},0.7),
                stop:0.5 rgba({r},{g},{b},1.0),
                stop:1 rgba({min(r+40,255)},{min(g+40,255)},{min(b+40,255)},0.9)
            );
            border-radius: 6px;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# SPEECH CAPTION — animated floating text
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_caption_style(C_PRI: str = "#f59e0b") -> str:
    """
    Caption label style.  The parent Python code should call:
        txt_console.setStyleSheet(liquid_glass_caption_style(C_PRI))
    Subtle white-ish text with a translucent glass pill background.
    """
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return (
        f"QLabel {{"
        f"  color: rgba(255,255,255,0.88);"
        f"  font-size: 15px;"
        f"  font-weight: 500;"
        f"  letter-spacing: 0.4px;"
        f"  background: qlineargradient("
        f"      x1:0,y1:0,x2:1,y2:1,"
        f"      stop:0 rgba({r},{g},{b},0.10),"
        f"      stop:1 rgba(0,0,0,0.45)"
        f"  );"
        f"  border: 1px solid rgba({r},{g},{b},0.30);"
        f"  border-radius: 14px;"
        f"  padding: 8px 20px;"
        f"}}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CENTRAL WIDGET (main window background)
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_central_style(C_PRI: str = "#f59e0b", C_BG: str = "#0f0a02") -> str:
    """Main window central widget — deep dark glass with colored border glow."""
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    bg_hex  = C_BG.lstrip("#")[:6]  if C_BG.startswith("#")  else "0f0a02"
    r, g, b   = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    br,bg_,bb = int(bg_hex[0:2], 16),  int(bg_hex[2:4], 16),  int(bg_hex[4:6], 16)
    return (
        f"QWidget#centralWidget {{"
        f"  background: qlineargradient("
        f"      x1:0,y1:0,x2:0,y2:1,"
        f"      stop:0 rgba({br},{bg_},{bb},0.92),"
        f"      stop:1 rgba({max(0,br-10)},{max(0,bg_-10)},{max(0,bb-10)},0.97)"
        f"  );"
        f"  border: 1.8px solid rgba({r},{g},{b},0.65);"
        f"  border-radius: 20px;"
        f"}}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# HEADER BAR
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_header_btn_style(C_PRI: str = "#f59e0b", C_PRI_DIM: str = "#78350f") -> str:
    """Header icon buttons with glass hover."""
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return f"""
        QPushButton {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba({r},{g},{b},0.25);
            border-radius: 14px;
            padding: 0;
        }}
        QPushButton:hover {{
            background: rgba({r},{g},{b},0.18);
            border: 1px solid rgba({r},{g},{b},0.70);
        }}
        QPushButton:pressed {{
            background: rgba({r},{g},{b},0.30);
        }}
    """


def liquid_glass_close_btn_style() -> str:
    return """
        QPushButton {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(239,68,68,0.40);
            border-radius: 14px;
            padding: 0;
        }
        QPushButton:hover {
            background: rgba(239,68,68,0.25);
            border: 1px solid rgba(239,68,68,0.85);
        }
        QPushButton:pressed {
            background: rgba(239,68,68,0.45);
        }
    """


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS DIALOG — full liquid glass redesign
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_settings_style(
    C_PRI:    str = "#f59e0b",
    C_PRI_DIM:str = "#78350f",
    C_BG:     str = "#0f0a02",
    C_BORDER: str = "rgba(245,158,11,0.45)",
    C_TEXT:   str = "#fde68a",
    FONT_FAMILY: str = "Century Gothic",
) -> str:
    """
    Complete QSS for DeviceSettingsDialog.
    Liquid Glass panels, glowing tabs, polished inputs.
    """
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    bg_hex  = C_BG.lstrip("#")[:6]  if C_BG.startswith("#")  else "0f0a02"
    r,  g,  b  = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    br, bg_, bb= int(bg_hex[0:2],  16),  int(bg_hex[2:4],  16),  int(bg_hex[4:6],  16)

    panel_bg = f"rgba({max(0,br+6)},{max(0,bg_+5)},{max(0,bb+2)},0.94)"
    glass_card = f"rgba({r},{g},{b},0.06)"
    glass_card_hover = f"rgba({r},{g},{b},0.12)"
    border_soft = f"rgba({r},{g},{b},0.30)"
    border_mid  = f"rgba({r},{g},{b},0.55)"
    input_bg    = f"rgba(0,0,0,0.55)"

    return f"""
        /* ── Outer container ── */
        QFrame#settingsContainer {{
            background: qlineargradient(
                x1:0, y1:0, x2:0.8, y2:1,
                stop:0 rgba({max(0,br+18)},{max(0,bg_+15)},{max(0,bb+8)},0.97),
                stop:0.5 {panel_bg},
                stop:1 rgba({br},{bg_},{bb},0.99)
            );
            border: 1px solid rgba(255,255,255,0.1);
            border-top: 1.5px solid rgba(255,255,255,0.25);
            border-bottom: 1.5px solid rgba({r},{g},{b},0.4);
            border-radius: 22px;
        }}

        /* ── Tab pane ── */
        QTabWidget::pane {{
            border: 1px solid {border_soft};
            border-top: 1px solid rgba(255,255,255,0.12);
            background: rgba({br},{bg_},{bb},0.45);
            border-radius: 16px;
            padding: 22px 18px 18px 18px;
        }}

        /* ── Tab bar ── */
        QTabBar::tab {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba({r},{g},{b},0.15);
            color: rgba(255,255,255,0.45);
            font-family: '{FONT_FAMILY}';
            padding: 9px 16px;
            margin-right: 3px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: bold;
            font-size: 9px;
            letter-spacing: 1.4px;
            min-width: 48px;
        }}
        QTabBar::tab:hover {{
            background: rgba({r},{g},{b},0.14);
            color: rgba(255,255,255,0.80);
            border-color: {border_soft};
        }}
        QTabBar::tab:selected {{
            background: qlineargradient(
                x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba({r},{g},{b},0.22),
                stop:1 rgba({r},{g},{b},0.08)
            );
            border: 1px solid {border_mid};
            border-bottom-color: rgba({r},{g},{b},0.08);
            color: {C_PRI};
        }}

        /* ── Labels ── */
        QLabel {{
            color: {C_TEXT};
            font-family: '{FONT_FAMILY}';
            font-weight: 600;
            background: transparent;
            font-size: 11px;
            letter-spacing: 0.7px;
        }}

        /* ── Line edits & combos ── */
        QLineEdit, QComboBox {{
            background: {input_bg};
            border: 1px solid {border_soft};
            color: rgba(255,255,255,0.90);
            font-family: '{FONT_FAMILY}';
            padding: 8px 12px;
            border-radius: 10px;
            font-size: 11px;
            selection-background-color: rgba({r},{g},{b},0.45);
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 1.5px solid {C_PRI};
            background: rgba(0,0,0,0.70);
        }}
        QComboBox::drop-down {{
            border: none;
            padding-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background: rgba({max(0,br+8)},{max(0,bg_+6)},{max(0,bb+2)},0.97);
            color: {C_TEXT};
            selection-background-color: rgba({r},{g},{b},0.35);
            selection-color: white;
            border: 1px solid {border_mid};
            border-radius: 8px;
            padding: 4px;
        }}

        /* ── Checkboxes ── */
        QCheckBox {{
            color: {C_TEXT};
            font-family: '{FONT_FAMILY}';
            font-weight: 600;
            font-size: 11px;
            background: transparent;
            spacing: 10px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1.5px solid {border_mid};
            border-radius: 4px;
            background: rgba(0,0,0,0.40);
        }}
        QCheckBox::indicator:checked {{
            background: {C_PRI};
            border-color: {C_PRI};
        }}
        QCheckBox::indicator:hover {{
            border-color: {C_PRI};
        }}

        /* ── Buttons (generic) ── */
        QPushButton {{
            background: qlineargradient(
                x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba({r},{g},{b},0.14),
                stop:1 rgba({r},{g},{b},0.06)
            );
            color: {C_PRI};
            border: 1px solid {border_mid};
            font-weight: 700;
            padding: 8px 18px;
            border-radius: 10px;
            font-size: 10px;
            letter-spacing: 1px;
            font-family: '{FONT_FAMILY}';
        }}
        QPushButton:hover {{
            background: rgba({r},{g},{b},0.28);
            border: 1px solid {C_PRI};
            color: white;
        }}
        QPushButton:pressed {{
            background: rgba({r},{g},{b},0.40);
        }}
        QPushButton:disabled {{
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.25);
            border: 1px solid rgba(255,255,255,0.08);
        }}

        /* ── Sliders ── */
        QSlider::groove:horizontal {{
            border: none;
            height: 5px;
            background: rgba(255,255,255,0.12);
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background: qlineargradient(
                x1:0,y1:0,x2:1,y2:0,
                stop:0 rgba({r},{g},{b},0.6),
                stop:1 rgba({r},{g},{b},1.0)
            );
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {C_PRI};
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
            border: 2px solid rgba(255,255,255,0.30);
        }}
        QSlider::handle:horizontal:hover {{
            background: white;
            border-color: {C_PRI};
        }}

        /* ── Scrollbars ── */
        QScrollBar:vertical {{
            border: none;
            background: rgba(0,0,0,0.20);
            width: 6px;
            border-radius: 3px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: rgba({r},{g},{b},0.40);
            min-height: 24px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba({r},{g},{b},0.80);
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0; background: none;
        }}

        /* ── Frames (section cards inside tabs) ── */
        QFrame {{
            background: transparent;
            border: none;
        }}
        QFrame[frameShape="4"],
        QFrame[frameShape="5"] {{
            background: rgba(255,255,255,0.07);
            max-height: 1px;
        }}

        /* ── List widgets (macros, etc.) ── */
        QListWidget {{
            background: rgba(0,0,0,0.35);
            border: 1px solid {border_soft};
            border-radius: 10px;
            color: {C_TEXT};
            font-size: 11px;
            padding: 4px;
        }}
        QListWidget::item {{
            padding: 6px 10px;
            border-radius: 6px;
        }}
        QListWidget::item:selected {{
            background: rgba({r},{g},{b},0.25);
            color: white;
        }}
        QListWidget::item:hover {{
            background: rgba({r},{g},{b},0.12);
        }}

        /* ── QMessageBox theming ── */
        QMessageBox {{
            background: rgba({br},{bg_},{bb},0.97);
            border: 2px solid {C_PRI};
        }}
        QMessageBox QLabel {{
            color: {C_TEXT};
            font-weight: 600;
        }}
        QMessageBox QPushButton {{
            background: rgba({r},{g},{b},0.15);
            color: {C_PRI};
            border: 1px solid {border_mid};
            font-weight: 700;
            padding: 6px 18px;
            border-radius: 8px;
            min-width: 80px;
        }}
        QMessageBox QPushButton:hover {{
            background: rgba({r},{g},{b},0.35);
            color: white;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# SPOTIFY WIDGET buttons
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_spotify_btn_style(C_PRI: str = "#f59e0b", C_BORDER: str = "rgba(245,158,11,0.45)") -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return f"""
        QPushButton {{
            background: rgba({r},{g},{b},0.08);
            border: 1px solid rgba({r},{g},{b},0.28);
            border-radius: 15px;
        }}
        QPushButton:hover {{
            background: rgba({r},{g},{b},0.22);
            border: 1px solid {C_PRI};
        }}
        QPushButton:pressed {{
            background: rgba({r},{g},{b},0.38);
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# TODO & NOTES inputs
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_input_style(C_PRI: str = "#f59e0b", C_BORDER: str = "rgba(245,158,11,0.45)") -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return (
        f"QLineEdit {{"
        f"  background: rgba({r},{g},{b},0.07);"
        f"  border: 1px solid rgba({r},{g},{b},0.30);"
        f"  border-radius: 8px;"
        f"  padding: 5px 10px;"
        f"  color: rgba(255,255,255,0.88);"
        f"  font-size: 11px;"
        f"}}"
        f"QLineEdit:focus {{"
        f"  border: 1.5px solid {C_PRI};"
        f"  background: rgba({r},{g},{b},0.12);"
        f"}}"
    )


def liquid_glass_textedit_style(C_PRI: str = "#f59e0b", C_BORDER: str = "rgba(245,158,11,0.45)") -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return (
        f"QTextEdit {{"
        f"  border: none;"
        f"  background: rgba({r},{g},{b},0.06);"
        f"  border-radius: 8px;"
        f"  padding: 8px;"
        f"  color: rgba(255,255,255,0.88);"
        f"  font-size: 12px;"
        f"}}"
        f"QTextEdit:focus {{"
        f"  background: rgba({r},{g},{b},0.10);"
        f"}}"
    )


def liquid_glass_add_btn_style(C_PRI: str = "#f59e0b", C_BG: str = "#0f0a02") -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    bg_hex  = C_BG.lstrip("#")[:6]  if C_BG.startswith("#")  else "0f0a02"
    r, g, b   = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return (
        f"QPushButton {{"
        f"  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f"      stop:0 rgba({r},{g},{b},0.80), stop:1 rgba({r},{g},{b},0.60));"
        f"  color: #{bg_hex};"
        f"  border: 1px solid {C_PRI};"
        f"  font-weight: bold;"
        f"  border-radius: 8px;"
        f"  padding: 5px 12px;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background: {C_PRI};"
        f"}}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CAMERA PREVIEW WINDOW
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_camera_container_style(C_PRI: str = "#f59e0b") -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return f"""
        QFrame#CameraContainer {{
            background: qlineargradient(
                x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba({r},{g},{b},0.10),
                stop:1 rgba(0,0,0,0.80)
            );
            border: 1.5px solid rgba({r},{g},{b},0.60);
            border-radius: 18px;
        }}
        QLabel {{
            color: rgba(255,255,255,0.80);
            font-family: 'Century Gothic', sans-serif;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# CLOCK WIDGET
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_clock_container_style(C_PRI: str = "#f59e0b") -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return f"""
        QWidget#ClockWidget {{
            background: rgba({r},{g},{b},0.06);
            border: 1px solid rgba({r},{g},{b},0.22);
            border-radius: 14px;
            padding: 4px 10px;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# LOGS DIALOG
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_logs_style(
    C_PRI: str = "#f59e0b",
    C_BG:  str = "#0f0a02",
    C_BORDER: str = "rgba(245,158,11,0.45)",
) -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    bg_hex  = C_BG.lstrip("#")[:6]  if C_BG.startswith("#")  else "0f0a02"
    r, g, b   = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    br,bg_,bb = int(bg_hex[0:2],  16),  int(bg_hex[2:4],  16),  int(bg_hex[4:6],  16)
    return f"""
        QWidget#logsContainer {{
            background: qlineargradient(
                x1:0,y1:0,x2:0.1,y2:1,
                stop:0 rgba({max(0,br+10)},{max(0,bg_+8)},{max(0,bb+3)},0.97),
                stop:1 rgba({br},{bg_},{bb},0.99)
            );
            border: 1.8px solid rgba({r},{g},{b},0.70);
            border-radius: 14px;
        }}
        QTextEdit {{
            background: rgba(4,6,9,0.88);
            color: #e2e8f0;
            border: 1px solid rgba({r},{g},{b},0.28);
            border-radius: 10px;
            padding: 10px;
        }}
        QLineEdit {{
            background: rgba(0,0,0,0.55);
            color: white;
            border: 1px solid rgba({r},{g},{b},0.35);
            border-radius: 8px;
            padding: 7px 12px;
            font-size: 11px;
        }}
        QLineEdit:focus {{
            border-color: {C_PRI};
        }}
        QPushButton {{
            background: rgba({r},{g},{b},0.12);
            color: {C_PRI};
            border: 1px solid rgba({r},{g},{b},0.45);
            font-weight: bold;
            border-radius: 7px;
            font-size: 10px;
            letter-spacing: 1px;
            padding: 5px 14px;
        }}
        QPushButton:hover {{
            background: rgba({r},{g},{b},0.28);
            color: white;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# ILUM MESSAGE BOX
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_msgbox_style(
    C_PRI: str = "#f59e0b",
    C_BG:  str = "#0f0a02",
) -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    bg_hex  = C_BG.lstrip("#")[:6]  if C_BG.startswith("#")  else "0f0a02"
    r, g, b   = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    br,bg_,bb = int(bg_hex[0:2],  16),  int(bg_hex[2:4],  16),  int(bg_hex[4:6],  16)
    return f"""
        QWidget#msgContainer {{
            background: qlineargradient(
                x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba({max(0,br+14)},{max(0,bg_+12)},{max(0,bb+4)},0.97),
                stop:1 rgba({br},{bg_},{bb},0.99)
            );
            border: 2px solid rgba({r},{g},{b},0.75);
            border-radius: 14px;
        }}
        QPushButton {{
            background: rgba({r},{g},{b},0.12);
            color: {C_PRI};
            border: 1.5px solid rgba({r},{g},{b},0.55);
            font-weight: bold;
            border-radius: 7px;
        }}
        QPushButton:hover {{
            background: rgba({r},{g},{b},0.30);
            color: white;
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# CHAT INPUT BAR
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_chat_input_style(C_PRI: str = "#f59e0b", C_BORDER: str = "rgba(245,158,11,0.45)") -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    r, g, b = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    return (
        f"QLineEdit#chatInput {{"
        f"  background: rgba({r},{g},{b},0.08);"
        f"  color: rgba(255,255,255,0.90);"
        f"  border: 1px solid rgba({r},{g},{b},0.35);"
        f"  border-radius: 16px;"
        f"  padding: 0px 16px;"
        f"  font-size: 12px;"
        f"}}"
        f"QLineEdit#chatInput:focus {{"
        f"  border: 1.5px solid {C_PRI};"
        f"  background: rgba({r},{g},{b},0.13);"
        f"}}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT MODE WINDOW
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_student_style(
    C_PRI:    str = "#f59e0b",
    C_PRI_DIM:str = "#78350f",
    C_BG:     str = "#0f0a02",
    C_BORDER: str = "rgba(245,158,11,0.45)",
    C_TEXT:   str = "#fde68a",
) -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    bg_hex  = C_BG.lstrip("#")[:6]  if C_BG.startswith("#")  else "0f0a02"
    r, g, b   = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    br,bg_,bb = int(bg_hex[0:2],  16),  int(bg_hex[2:4],  16),  int(bg_hex[4:6],  16)
    return f"""
        #StudentBg {{
            background: qlineargradient(
                x1:0,y1:0,x2:0.1,y2:1,
                stop:0 rgba({max(0,br+12)},{max(0,bg_+10)},{max(0,bb+3)},0.97),
                stop:1 rgba({br},{bg_},{bb},0.99)
            );
            border: 2px solid rgba({r},{g},{b},0.65);
            border-radius: 16px;
        }}
        QLabel {{ color: {C_TEXT}; }}
        QPushButton {{
            background: rgba({r},{g},{b},0.12);
            color: {C_TEXT};
            border: 1px solid rgba({r},{g},{b},0.40);
            border-radius: 9px;
            padding: 10px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: rgba({r},{g},{b},0.28);
            color: white;
        }}
        QPushButton:disabled {{
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.25);
            border: 1px solid rgba(255,255,255,0.08);
        }}
        QTextEdit, QTextBrowser {{
            background: rgba({r},{g},{b},0.06);
            color: rgba(255,255,255,0.90);
            border: 1px solid rgba({r},{g},{b},0.28);
            border-radius: 10px;
            padding: 8px;
            font-size: 13px;
        }}
        QTabWidget::pane {{
            border: 1px solid rgba({r},{g},{b},0.30);
            border-radius: 12px;
            background: rgba({br},{bg_},{bb},0.55);
        }}
        QTabBar::tab {{
            background: rgba({r},{g},{b},0.08);
            color: {C_TEXT};
            padding: 11px 18px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border: 1px solid rgba({r},{g},{b},0.20);
            border-bottom: none;
            margin-right: 3px;
            font-weight: bold;
            font-size: 10px;
        }}
        QTabBar::tab:selected {{
            background: rgba({r},{g},{b},0.22);
            border-bottom: 2px solid {C_PRI};
            color: {C_PRI};
        }}
        QTabBar::tab:hover {{
            background: rgba({r},{g},{b},0.16);
        }}
        QScrollArea {{
            background: transparent;
            border: 1px solid rgba({r},{g},{b},0.18);
            border-radius: 10px;
        }}
        QScrollBar:vertical {{
            border: none;
            background: rgba(0,0,0,0.18);
            width: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba({r},{g},{b},0.40);
            min-height: 20px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba({r},{g},{b},0.80);
        }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# COLOR PICKER DIALOG
# ─────────────────────────────────────────────────────────────────────────────

def liquid_glass_picker_style(
    C_PRI: str = "#f59e0b",
    C_BG:  str = "#0f0a02",
    C_BORDER: str = "rgba(245,158,11,0.45)",
    C_TEXT: str = "#fde68a",
) -> str:
    pri_hex = C_PRI.lstrip("#")[:6] if C_PRI.startswith("#") else "f59e0b"
    bg_hex  = C_BG.lstrip("#")[:6]  if C_BG.startswith("#")  else "0f0a02"
    r, g, b   = int(pri_hex[0:2], 16), int(pri_hex[2:4], 16), int(pri_hex[4:6], 16)
    br,bg_,bb = int(bg_hex[0:2],  16),  int(bg_hex[2:4],  16),  int(bg_hex[4:6],  16)
    return f"""
        QFrame#pickerContainer {{
            background: qlineargradient(
                x1:0,y1:0,x2:0.15,y2:1,
                stop:0 rgba({max(0,br+16)},{max(0,bg_+14)},{max(0,bb+5)},0.97),
                stop:1 rgba({br},{bg_},{bb},0.99)
            );
            border: 2px solid rgba({r},{g},{b},0.72);
            border-radius: 14px;
        }}
        QLabel {{
            color: {C_TEXT};
            font-weight: bold;
            font-size: 11px;
            background: transparent;
        }}
        QLineEdit {{
            background: rgba(0,0,0,0.60);
            border: 1px solid rgba({r},{g},{b},0.35);
            color: white;
            padding: 5px 10px;
            border-radius: 7px;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton {{
            background: rgba({r},{g},{b},0.80);
            color: #{bg_hex};
            border: 1px solid {C_PRI};
            font-weight: bold;
            border-radius: 8px;
            font-size: 11px;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{
            background: {C_PRI};
        }}
        QSlider::groove:horizontal {{
            border: none;
            height: 6px;
            background: rgba(255,255,255,0.10);
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background: rgba({r},{g},{b},0.85);
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {C_PRI};
            width: 15px;
            margin: -5px 0;
            border-radius: 8px;
        }}
    """