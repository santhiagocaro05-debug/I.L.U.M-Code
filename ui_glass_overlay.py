"""ui_glass_overlay.py — ILUM Liquid Glass Runtime Overlay
Applies all Liquid Glass visual upgrades to the existing ui.py classes
at runtime by monkey-patching update_style() methods and installing
a QPropertyAnimation caption fade effect.

Usage — add these TWO lines at the END of IlumUI.__init__, right before the
closing brace (after self._win.show()):

    from ui_glass_overlay import apply_liquid_glass
    apply_liquid_glass(self._win)

That's it. Zero other changes to ui.py.
"""
from __future__ import annotations
from PyQt6.QtCore  import QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QObject
from PyQt6.QtGui   import QColor
from PyQt6.QtWidgets import QGraphicsOpacityEffect

import ui_styles as _s


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_theme():
    try:
        from ui import C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FONT_FAMILY
        return C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FONT_FAMILY
    except Exception:
        return "#f59e0b", "#78350f", "#0f0a02", "rgba(245,158,11,0.45)", "#fde68a", "Century Gothic"


# ─────────────────────────────────────────────────────────────────────────────
# Caption fade animator
# ─────────────────────────────────────────────────────────────────────────────

class _CaptionFader(QObject):
    """Wraps the txt_console QLabel with a smooth opacity fade animation."""

    def __init__(self, label):
        super().__init__(label)
        self._label = label
        self._effect = QGraphicsOpacityEffect(label)
        self._effect.setOpacity(0.0)
        label.setGraphicsEffect(self._effect)

        self._fade_in  = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_in.setDuration(380)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_out.setDuration(600)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade_out)

        # Intercept setText via an event loop hook
        self._original_setText = label.setText
        label.setText = self._animated_set_text

    def _animated_set_text(self, text: str):
        self._original_setText(text)
        if not text.strip():
            self._start_fade_out()
            return
        self._hide_timer.stop()
        self._fade_out.stop()
        self._fade_in.start()
        # Auto-hide after 8 seconds
        self._hide_timer.start(8000)

    def _start_fade_out(self):
        self._fade_in.stop()
        self._fade_out.start()


# ─────────────────────────────────────────────────────────────────────────────
# Per-widget style patches
# ─────────────────────────────────────────────────────────────────────────────

def _patch_spotify(w):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()
    orig = w.update_style

    def _new_style():
        w.setStyleSheet(_s.liquid_glass_widget_style("SpotifyWidget", C_PRI, C_BORDER, C_TEXT))
        if hasattr(w, "lbl_title"):
            w.lbl_title.setStyleSheet(_s.liquid_glass_title_style(C_PRI))
            w.lbl_artist.setStyleSheet(
                f"font-size: 11px; color: rgba(255,255,255,0.55); border: none; background: transparent;"
            )
            for btn, icon, clr in w.buttons_list:
                btn.setStyleSheet(_s.liquid_glass_spotify_btn_style(C_PRI, C_BORDER))

    w.update_style = _new_style
    _new_style()


def _patch_system(w):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    def _new_style():
        w.setStyleSheet(_s.liquid_glass_widget_style("SystemWidget", C_PRI, C_BORDER, C_TEXT))
        if hasattr(w, "lbl_title"):
            w.lbl_title.setStyleSheet(_s.liquid_glass_title_style(C_PRI))
            for bar, _ in w.bars:
                bar.setStyleSheet(_s.liquid_glass_progress_style(C_PRI, C_BORDER))

    w.update_style = _new_style
    _new_style()


def _patch_weather(w):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    def _new_style():
        w.setStyleSheet(_s.liquid_glass_widget_style("WeatherWidget", C_PRI, C_BORDER, C_TEXT))
        if hasattr(w, "lbl_title"):
            w.lbl_title.setStyleSheet(_s.liquid_glass_title_style(C_PRI))
            w.lbl_desc.setStyleSheet(
                f"font-size: 11px; color: rgba(255,255,255,0.70); border: none; background: transparent;"
            )

    w.update_style = _new_style
    _new_style()


def _patch_todo(w):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    def _new_style():
        w.setStyleSheet(_s.liquid_glass_widget_style("TodoWidget", C_PRI, C_BORDER, C_TEXT))
        if hasattr(w, "lbl_title"):
            w.lbl_title.setStyleSheet(_s.liquid_glass_title_style(C_PRI))
            w.txt_task.setStyleSheet(_s.liquid_glass_input_style(C_PRI, C_BORDER))
            w.btn_add.setStyleSheet(_s.liquid_glass_add_btn_style(C_PRI, C_BG))

    w.update_style = _new_style
    _new_style()


def _patch_notes(w):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    def _new_style():
        w.setStyleSheet(_s.liquid_glass_widget_style("NotesWidget", C_PRI, C_BORDER, C_TEXT))
        if hasattr(w, "lbl_title"):
            w.lbl_title.setStyleSheet(_s.liquid_glass_title_style(C_PRI))
            w.txt_notes.setStyleSheet(_s.liquid_glass_textedit_style(C_PRI, C_BORDER))

    w.update_style = _new_style
    _new_style()


def _patch_files(w):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    def _new_style():
        w.setStyleSheet(_s.liquid_glass_widget_style("FilesPanel", C_PRI, C_BORDER, C_TEXT))
        if hasattr(w, "lbl_title"):
            w.lbl_title.setStyleSheet(_s.liquid_glass_title_style(C_PRI))
            w.list_macros.setStyleSheet(
                f"background: rgba(0,0,0,0.22); border: 1px solid rgba(255,255,255,0.10); "
                f"border-radius: 8px; color: {C_TEXT}; font-size: 11px;"
            )

    w.update_style = _new_style
    _new_style()


def _patch_clock(w):
    C_PRI, *_ = _get_theme()

    def _new_style():
        w.setStyleSheet(_s.liquid_glass_clock_container_style(C_PRI))
        if hasattr(w, "lbl_date"):
            w.lbl_date.setStyleSheet(
                f"font-size: 11px; letter-spacing: 1px; color: {C_PRI}; "
                f"border: none; background: transparent; font-weight: bold;"
            )

    w.update_style = _new_style
    _new_style()


# ─────────────────────────────────────────────────────────────────────────────
# Settings dialog patch
# ─────────────────────────────────────────────────────────────────────────────

def _patch_settings_dialog_class():
    """Monkey-patch DeviceSettingsDialog.update_style globally."""
    try:
        import ui as _ui_module

        _orig_init = _ui_module.DeviceSettingsDialog.__init__

        def _new_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            self._apply_glass_style()

        def _apply_glass(self):
            C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()
            self.setStyleSheet(
                _s.liquid_glass_settings_style(C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF)
            )

        _ui_module.DeviceSettingsDialog.__init__ = _new_init
        _ui_module.DeviceSettingsDialog.update_style = _apply_glass
        _ui_module.DeviceSettingsDialog._apply_glass_style = _apply_glass
    except Exception as e:
        print(f"[GLASS] Settings dialog patch skipped: {e}")


def _patch_logs_dialog_class():
    try:
        import ui as _ui_module

        _orig_init = _ui_module.LogsDialog.__init__

        def _new_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            C_PRI, _, C_BG, C_BORDER, *_ = _get_theme()
            self.setStyleSheet(
                _s.liquid_glass_logs_style(C_PRI, C_BG, C_BORDER)
            )

        _ui_module.LogsDialog.__init__ = _new_init
    except Exception as e:
        print(f"[GLASS] Logs dialog patch skipped: {e}")


def _patch_msgbox_class():
    try:
        import ui as _ui_module

        _orig_init = _ui_module.IlumMessageBox.__init__

        def _new_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            C_PRI, _, C_BG, *_ = _get_theme()
            self.setStyleSheet(
                _s.liquid_glass_msgbox_style(C_PRI, C_BG)
            )

        _ui_module.IlumMessageBox.__init__ = _new_init
    except Exception as e:
        print(f"[GLASS] MessageBox patch skipped: {e}")


def _patch_picker_class():
    try:
        import ui as _ui_module

        _orig_init = _ui_module.IlumColorPicker.__init__

        def _new_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            C_PRI, _, C_BG, C_BORDER, C_TEXT, *_ = _get_theme()
            self.setStyleSheet(
                _s.liquid_glass_picker_style(C_PRI, C_BG, C_BORDER, C_TEXT)
            )

        _ui_module.IlumColorPicker.__init__ = _new_init
    except Exception as e:
        print(f"[GLASS] ColorPicker patch skipped: {e}")


def _patch_camera_window_class():
    try:
        import ui as _ui_module

        _orig_init = _ui_module.CameraPreviewWindow.__init__

        def _new_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            C_PRI, *_ = _get_theme()
            # Update the CameraContainer frame style
            for child in self.findChildren(_ui_module.QFrame if False else object):
                try:
                    if hasattr(child, "objectName") and child.objectName() == "CameraContainer":
                        child.setStyleSheet(_s.liquid_glass_camera_container_style(C_PRI))
                except Exception:
                    pass

        _ui_module.CameraPreviewWindow.__init__ = _new_init
    except Exception as e:
        print(f"[GLASS] CameraWindow patch skipped: {e}")


def _patch_student_window_class():
    try:
        import ui as _ui_module

        _orig_update = _ui_module.StudentModeWindow.update_style

        def _new_style(self):
            C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, *_ = _get_theme()
            self.setStyleSheet(
                _s.liquid_glass_student_style(C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT)
            )

        _ui_module.StudentModeWindow.update_style = _new_style
    except Exception as e:
        print(f"[GLASS] StudentWindow patch skipped: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main window caption + central widget
# ─────────────────────────────────────────────────────────────────────────────

def _patch_main_window(win):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    # Caption glass style
    win.txt_console.setStyleSheet(_s.liquid_glass_caption_style(C_PRI))

    # Attach animated fader to txt_console
    try:
        win._caption_fader = _CaptionFader(win.txt_console)
    except Exception as e:
        print(f"[GLASS] Caption fader skipped: {e}")

    # Central widget glass border
    win.central_widget.setStyleSheet(_s.liquid_glass_central_style(C_PRI, C_BG))

    # Chat input glass style
    if hasattr(win, "chat_input"):
        win.chat_input.setStyleSheet(_s.liquid_glass_chat_input_style(C_PRI, C_BORDER))

    # Header buttons glass
    close_style = _s.liquid_glass_close_btn_style()
    btn_style   = _s.liquid_glass_header_btn_style(C_PRI, C_PRI_DIM)
    for btn, icon, cb in win.head_buttons:
        if btn == win.btn_close:
            btn.setStyleSheet(close_style)
        else:
            btn.setStyleSheet(btn_style)


# ─────────────────────────────────────────────────────────────────────────────
# Hook update_theme_styles so glass re-applies on theme change
# ─────────────────────────────────────────────────────────────────────────────

def _hook_update_theme(win):
    _orig = win.update_theme_styles

    def _new_update():
        _orig()
        # Re-apply glass after the original has run
        QTimer.singleShot(0, lambda: _reapply_all(win))

    win.update_theme_styles = _new_update


def _reapply_all(win):
    try:
        _patch_main_window(win)
        for attr, fn in [
            ("spotify_w", _patch_spotify),
            ("system_w",  _patch_system),
            ("weather_w", _patch_weather),
            ("todo_w",    _patch_todo),
            ("notes_w",   _patch_notes),
            ("files_panel", _patch_files),
            ("clock_w",   _patch_clock),
        ]:
            w = getattr(win, attr, None)
            if w:
                fn(w)
    except Exception as e:
        print(f"[GLASS] reapply error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def apply_liquid_glass(main_window):
    """
    Call once with the MainWindow instance to activate all Liquid Glass effects.
    Safe to call from any thread via QTimer.singleShot.
    """
    def _do():
        try:
            # 1. Dialog class patches (safe to run once at startup)
            _patch_settings_dialog_class()
            _patch_logs_dialog_class()
            _patch_msgbox_class()
            _patch_picker_class()
            _patch_camera_window_class()
            _patch_student_window_class()

            # 2. Main window patches
            _patch_main_window(main_window)

            # 3. Bento widget patches
            for attr, fn in [
                ("spotify_w",   _patch_spotify),
                ("system_w",    _patch_system),
                ("weather_w",   _patch_weather),
                ("todo_w",      _patch_todo),
                ("notes_w",     _patch_notes),
                ("files_panel", _patch_files),
                ("clock_w",     _patch_clock),
            ]:
                w = getattr(main_window, attr, None)
                if w:
                    fn(w)

            # 4. Hook theme updates so glass persists after theme changes
            _hook_update_theme(main_window)

            print("[GLASS] Liquid Glass activated successfully.")
        except Exception as e:
            print(f"[GLASS] Activation error: {e}")

    QTimer.singleShot(150, _do)