"""ui_glass_overlay.py — ILUM Liquid Glass Runtime Overlay (fixed)

Applies Liquid Glass visual upgrades to ui.py classes at runtime by
monkey-patching update_style() methods. Fully defensive: every widget/
attribute access is guarded with hasattr(), so a mismatch between this
file and the current ui.py can never crash mid-patch or leave the
window in a half-styled state.

Usage (unchanged):
    from ui_glass_overlay import apply_liquid_glass
    apply_liquid_glass(self._win)
"""
from __future__ import annotations
from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, QObject
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


def _safe(label, fn_name=""):
    """Decorator-ish helper: run fn, swallow + log any error instead of propagating."""
    def _wrap(fn):
        try:
            fn()
        except Exception as e:
            print(f"[GLASS] {fn_name or getattr(fn, '__name__', '?')} skipped: {e}")
    return _wrap


# ─────────────────────────────────────────────────────────────────────────────
# Caption fade animator
# ─────────────────────────────────────────────────────────────────────────────

class _CaptionFader(QObject):
    """Wraps the txt_console QLabel with a smooth opacity fade animation."""

    def __init__(self, label):
        super().__init__(label)
        self._label = label
        self._effect = QGraphicsOpacityEffect(label)
        self._effect.setOpacity(1.0)  # start visible — don't hide content by default
        label.setGraphicsEffect(self._effect)

        self._fade_in = QPropertyAnimation(self._effect, b"opacity", self)
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
        self._hide_timer.start(8000)

    def _start_fade_out(self):
        self._fade_in.stop()
        self._fade_out.start()


# ─────────────────────────────────────────────────────────────────────────────
# Per-widget style patches — every one guarded, uses REAL ui.py attribute names
# ─────────────────────────────────────────────────────────────────────────────

def _patch_spotify(w):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    def _new_style():
        try:
            # FloatingSpotifyWidget paints its own background in paintEvent;
            # only touch text labels that actually exist.
            if hasattr(w, "lbl_track"):
                w.lbl_track.setStyleSheet(
                    f"font-size:14px;font-weight:700;color: rgba(255,255,255,0.95); border:none; background:transparent;"
                )
            if hasattr(w, "lbl_artist"):
                w.lbl_artist.setStyleSheet(
                    f"font-size:11px;font-weight:600;color: rgba(190,210,255,0.90); border:none; background:transparent;"
                )
        except Exception as e:
            print(f"[GLASS] spotify style skipped: {e}")

    w.update_style = _new_style if hasattr(w, "update_style") else getattr(w, "update_style", _new_style)
    _new_style()


def _patch_system(w):
    def _new_style():
        try:
            if hasattr(w, "apply_theme"):
                w.apply_theme()
        except Exception as e:
            print(f"[GLASS] system monitor style skipped: {e}")
    _new_style()


def _patch_weather(w):
    C_PRI, *_ = _get_theme()

    def _new_style():
        try:
            if hasattr(w, "lbl_desc"):
                w.lbl_desc.setStyleSheet("font-size:10px; color:rgba(220,220,230,0.75); border:none; background:transparent;")
        except Exception as e:
            print(f"[GLASS] weather style skipped: {e}")
    _new_style()


def _patch_todo(w):
    def _new_style():
        try:
            if hasattr(w, "update_style"):
                w.update_style()
        except Exception as e:
            print(f"[GLASS] todo style skipped: {e}")
    _new_style()


def _patch_notes(w):
    def _new_style():
        pass  # NotesWidget already paints its own glass background — nothing to add safely
    _new_style()


def _patch_files(w):
    def _new_style():
        pass  # FilesPanel already paints its own glass background — nothing to add safely
    _new_style()


def _patch_clock(w):
    def _new_style():
        try:
            if hasattr(w, "apply_theme"):
                w.apply_theme()
        except Exception as e:
            print(f"[GLASS] clock style skipped: {e}")
    _new_style()


# ─────────────────────────────────────────────────────────────────────────────
# Dialog class patches — use REAL class names from ui.py
# ─────────────────────────────────────────────────────────────────────────────

def _patch_settings_dialog_class():
    try:
        import ui as _ui_module
        if not hasattr(_ui_module, "DeviceSettingsDialog"):
            return
        # DeviceSettingsDialog already has a rich update_style() in ui.py —
        # don't override it wholesale, that's what caused past breakage.
        # Nothing to do here safely; skip.
    except Exception as e:
        print(f"[GLASS] Settings dialog patch skipped: {e}")


def _patch_logs_dialog_class():
    try:
        import ui as _ui_module
        if not hasattr(_ui_module, "LogsDialog"):
            return
        # LogsDialog already themes itself using C_PRI/C_BG in ui.py — skip.
    except Exception as e:
        print(f"[GLASS] Logs dialog patch skipped: {e}")


def _patch_msgbox_class():
    try:
        import ui as _ui_module
        cls = getattr(_ui_module, "NexusMessageBox", None)
        if cls is None:
            print("[GLASS] MessageBox patch skipped: NexusMessageBox not found")
            return
        # Already themed in ui.py using live C_PRI/C_BG — nothing extra needed.
    except Exception as e:
        print(f"[GLASS] MessageBox patch skipped: {e}")


def _patch_picker_class():
    try:
        import ui as _ui_module
        cls = getattr(_ui_module, "NexusColorPicker", None)
        if cls is None:
            print("[GLASS] ColorPicker patch skipped: NexusColorPicker not found")
            return
        # Already themed in ui.py — nothing extra needed.
    except Exception as e:
        print(f"[GLASS] ColorPicker patch skipped: {e}")


def _patch_camera_window_class():
    try:
        import ui as _ui_module
        if not hasattr(_ui_module, "CameraPreviewWindow"):
            return
        # Already themed with C_PRI in ui.py — skip.
    except Exception as e:
        print(f"[GLASS] CameraWindow patch skipped: {e}")


def _patch_student_window_class():
    try:
        import ui as _ui_module
        if not hasattr(_ui_module, "StudentModeWindow"):
            return
        # Already themed via its own update_style() in ui.py — skip.
    except Exception as e:
        print(f"[GLASS] StudentWindow patch skipped: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main window caption — ONLY touches things that actually exist
# ─────────────────────────────────────────────────────────────────────────────

def _patch_main_window(win):
    C_PRI, C_PRI_DIM, C_BG, C_BORDER, C_TEXT, FF = _get_theme()

    # Caption fader — txt_console exists in current MainWindow
    if hasattr(win, "txt_console"):
        try:
            if not hasattr(win, "_caption_fader"):
                win._caption_fader = _CaptionFader(win.txt_console)
        except Exception as e:
            print(f"[GLASS] Caption fader skipped: {e}")

    # DO NOT touch central_widget stylesheet here — update_theme_styles()
    # already sets the correct opaque gradient background for the HUD.
    # Overwriting it with an unknown ui_styles.liquid_glass_central_style()
    # is what caused the see-through/unclickable HUD bug previously.

    # Chat bar — real attribute is chat_bar, not chat_input
    if hasattr(win, "chat_bar"):
        pass  # PillChatBar already paints its own glass pill in paintEvent

    # Header buttons — win.head_buttons never existed on MainWindow; the real
    # dots/hamburger live on win.top_right_dock. Nothing safe to add here
    # since TopRightDock already themes its own dots. Skip entirely.


# ─────────────────────────────────────────────────────────────────────────────
# Hook update_theme_styles so glass re-applies on theme change
# ─────────────────────────────────────────────────────────────────────────────

def _hook_update_theme(win):
    if getattr(win, "_glass_theme_hooked", False):
        return
    _orig = win.update_theme_styles

    def _new_update():
        _orig()
        QTimer.singleShot(0, lambda: _reapply_all(win))

    win.update_theme_styles = _new_update
    win._glass_theme_hooked = True


def _reapply_all(win):
    try:
        _patch_main_window(win)
        for attr, fn in [
            ("spotify_float", _patch_spotify),
            ("sys_monitor",   _patch_system),
            ("weather_widget", _patch_weather),
            ("todo_w",        _patch_todo),
            ("notes_w",       _patch_notes),
            ("files_panel",   _patch_files),
            ("clock_w",       _patch_clock),
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
    Call once with the MainWindow instance to activate Liquid Glass effects.
    Fully defensive — cannot crash mid-patch, cannot leave the HUD in a
    half-styled or click-through state.
    """
    def _do():
        try:
            _patch_settings_dialog_class()
            _patch_logs_dialog_class()
            _patch_msgbox_class()
            _patch_picker_class()
            _patch_camera_window_class()
            _patch_student_window_class()

            _patch_main_window(main_window)

            for attr, fn in [
                ("spotify_float",  _patch_spotify),
                ("sys_monitor",    _patch_system),
                ("weather_widget", _patch_weather),
                ("todo_w",         _patch_todo),
                ("notes_w",        _patch_notes),
                ("files_panel",    _patch_files),
                ("clock_w",        _patch_clock),
            ]:
                w = getattr(main_window, attr, None)
                if w:
                    fn(w)

            _hook_update_theme(main_window)

            print("[GLASS] Liquid Glass activated successfully.")
        except Exception as e:
            print(f"[GLASS] Activation error: {e}")

    QTimer.singleShot(150, _do)