import re
import sys

def patch():
    with open("ui.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add Media Monitor import
    content = content.replace(
        "import drm_manager",
        "import drm_manager\nfrom core.media_monitor import MediaMonitorWorker"
    )

    # 2. Add FloatingMediaWidget class right before PillChatBar
    widget_code = """
class FloatingMediaWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MediaFloat")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 90)
        self.drag_position = None
        self._is_playing = False

        self.setStyleSheet('''
QWidget#MediaFloat {
    background: rgba(18,18,22,0.85);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 20px;
}
QLabel {
    background: transparent;
    border: none;
    color: rgba(245,245,250,0.96);
}
QPushButton {
    background: transparent;
    border: none;
}
QPushButton:hover {
    background: rgba(255,255,255,0.06);
    border-radius: 15px;
}
''')
        apply_glass_shadow(self, blur_radius=30, y_offset=6, alpha=150)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.lbl_art = QLabel()
        self.lbl_art.setFixedSize(40, 40)
        self.lbl_art.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 8px;")
        self.lbl_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if HAS_QTA:
            self.lbl_art.setPixmap(qta.icon('fa5b.youtube', color='rgba(255,20,20,0.8)').pixmap(20, 20))
        layout.addWidget(self.lbl_art)

        right = QVBoxLayout()
        right.setSpacing(2)

        self.lbl_track = QLabel("Not Playing")
        self.lbl_track.setStyleSheet("font-size:11px; font-weight:600; color:#ffffff;")
        self.lbl_artist = QLabel("Windows Media")
        self.lbl_artist.setStyleSheet("font-size:10px; color:rgba(200,200,210,0.70);")

        right.addWidget(self.lbl_track)
        right.addWidget(self.lbl_artist)
        
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        ctrl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        if HAS_QTA:
            self.btn_prev = QPushButton()
            self.btn_prev.setFixedSize(24, 24)
            self.btn_prev.setIcon(qta.icon('fa5s.step-backward', color='rgba(220,220,230,0.85)'))
            
            self.btn_play = QPushButton()
            self.btn_play.setFixedSize(28, 28)
            self.btn_play.setIcon(qta.icon('fa5s.play', color='rgba(255,255,255,0.95)'))
            
            self.btn_next = QPushButton()
            self.btn_next.setFixedSize(24, 24)
            self.btn_next.setIcon(qta.icon('fa5s.step-forward', color='rgba(220,220,230,0.85)'))

            ctrl.addWidget(self.btn_prev)
            ctrl.addWidget(self.btn_play)
            ctrl.addWidget(self.btn_next)
            
            self.btn_prev.clicked.connect(lambda: self._press("prevtrack"))
            self.btn_play.clicked.connect(lambda: self._press("playpause"))
            self.btn_next.clicked.connect(lambda: self._press("nexttrack"))

        right.addLayout(ctrl)
        layout.addLayout(right)

        self.hide()
        QTimer.singleShot(100, self.load_position)

    def update_info(self, title, artist, is_playing, thumb):
        if not title:
            self.lbl_track.setText("Not Playing")
            self.lbl_artist.setText("Windows Media")
            if self.isVisible() and hasattr(self.window(), "animate_hide_widget"):
                self.window().animate_hide_widget(self)
            self._is_playing = False
            return

        self._is_playing = is_playing
        name = title[:30] + ("..." if len(title) > 30 else "")
        art = artist[:30] + ("..." if len(artist) > 30 else "")
        self.lbl_track.setText(name)
        self.lbl_artist.setText(art)

        if HAS_QTA:
            icon = 'fa5s.pause' if is_playing else 'fa5s.play'
            self.btn_play.setIcon(qta.icon(icon, color='rgba(255,255,255,0.95)'))

        if not self.isVisible() and hasattr(self.window(), "animate_show_widget"):
            self.window().animate_show_widget(self)

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
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

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

"""
    if "class FloatingMediaWidget(QWidget):" not in content:
        content = content.replace("class PillChatBar(QWidget):", widget_code + "class PillChatBar(QWidget):")

    # 3. Add to Settings (UI side)
    if "self.chk_widget_media" not in content:
        content = content.replace(
            "self.chk_widget_spotify = QCheckBox(\"Mostrar Widget Spotify Flotante\")",
            "self.chk_widget_spotify = QCheckBox(\"Mostrar Widget Spotify Flotante\")\n        self.chk_widget_media = QCheckBox(\"Mostrar Widget YouTube/Medios (Universal)\")"
        )
        content = content.replace(
            "widgets = [self.chk_widget_spotify, self.chk_widget_weather, self.chk_widget_notifications,",
            "widgets = [self.chk_widget_spotify, self.chk_widget_media, self.chk_widget_weather, self.chk_widget_notifications,"
        )

    # 4. Settings Apply config
    if '"show_widget_media": self.chk_widget_media.isChecked()' not in content:
        content = content.replace(
            "self.chk_widget_spotify.setChecked(cfg.get(\"show_widget_spotify\", False))",
            "self.chk_widget_spotify.setChecked(cfg.get(\"show_widget_spotify\", False))\n            self.chk_widget_media.setChecked(cfg.get(\"show_widget_media\", False))"
        )
        content = content.replace(
            "\"show_widget_spotify\": self.chk_widget_spotify.isChecked(),",
            "\"show_widget_spotify\": self.chk_widget_spotify.isChecked(),\n                \"show_widget_media\": self.chk_widget_media.isChecked(),"
        )

    # 5. Add to MainWindow
    if "self.media_float" not in content:
        content = content.replace(
            "self.spotify_float = FloatingSpotifyWidget(self.central_widget)",
            "self.spotify_float = FloatingSpotifyWidget(self.central_widget)\n        self.media_float = FloatingMediaWidget(self.central_widget)"
        )
        # Add positioning
        pos_code = """
            # FloatingMediaWidget
            wx = cfg.get("widget_pos_FloatingMediaWidget_x")
            wy = cfg.get("widget_pos_FloatingMediaWidget_y")
            if wx is not None and wy is not None:
                self.media_float.move(int(wx), int(wy))
            else:
                self.media_float.move((self.width() - 280) // 2 + 80, self.height() // 2)
"""
        content = content.replace(
            "self._spotify_positioned = True",
            "self._spotify_positioned = True\n" + pos_code
        )

        # Worker initialization
        worker_code = """
        # Media Monitor (YouTube)
        self.media_worker = MediaMonitorWorker(self)
        self.media_worker.media_updated.connect(self.media_float.update_info)
        self.media_worker.start()
"""
        content = content.replace(
            "self._apply_widget_visibility()",
            worker_code + "\n        self._apply_widget_visibility()"
        )

    # 6. Apply visibility
    if "self.media_float.hide()" not in content:
        vis_code = """
            if cfg.get("show_widget_media", False):
                # Don't show immediately, wait for media update to trigger show
                pass
            else:
                self.media_float.hide()
"""
        content = content.replace(
            "if cfg.get(\"show_widget_spotify\", False):",
            vis_code + "\n            if cfg.get(\"show_widget_spotify\", False):"
        )

    # 7. Fix Spotify Widget so it DOES NOT aggressively hide when paused
    content = content.replace(
        "if curr and curr.get(\"item\") and curr.get(\"is_playing\"):",
        "if curr and curr.get(\"item\"):"
    )

    with open("ui.py", "w", encoding="utf-8") as f:
        f.write(content)

    print("Patch applied successfully.")

if __name__ == "__main__":
    patch()
