import re

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Reemplazar MainWindow.__init__
new_init = """    def __init__(self, ui, face_path):
        super().__init__()
        self.ui = ui
        self.ui._win = self
        self.camera_window = None
        self.student_action_sig.connect(self.handle_student_action, Qt.ConnectionType.QueuedConnection)
        
        self.resize(1150, 760)
        self.setMinimumSize(800, 600)
        self.setWindowTitle("ILUM-AI-HUD")
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)
        
        # Initialize background image label and floating sticker label with click-through enabled
        self.lbl_bg_image = QLabel(self.central_widget)
        self.lbl_bg_image.lower()
        self.lbl_bg_image.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_bg_image.setStyleSheet("background: transparent;")
        
        self.lbl_sticker = QLabel(self.central_widget)
        self.lbl_sticker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_sticker.setStyleSheet("background: transparent;")
        
        from memory.config_manager import load_api_keys
        cfg = load_api_keys()
        custom_icon = cfg.get("ilum_app_icon", "")
        if custom_icon and Path(custom_icon).exists():
            self.setWindowIcon(QIcon(custom_icon))
        else:
            icon_path = get_bundled_path("assets", "ilum_icono.ico")
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                
        # NEW: Central Brand Logo
        self.lbl_brand_center = QLabel("I.L.U.M", self.central_widget)
        font_brand = QFont(FONT_FAMILY, 90, QFont.Weight.Bold)
        font_brand.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 25.0)
        self.lbl_brand_center.setFont(font_brand)
        self.lbl_brand_center.setStyleSheet(f"color: white; background: transparent; border: none;")
        self.lbl_brand_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_brand_center.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        apply_glass_shadow(self.lbl_brand_center, blur_radius=60, x_offset=0, y_offset=0, alpha=200)

        # WebGL Orb (Audio Waveform)
        self.orb = CustomParticleOrb(self.ui, self.central_widget)
        
        # Buttons Setup (Hidden standard buttons, exposed as icons)
        self.btn_edit_hud = QPushButton()
        self.btn_settings = QPushButton()
        self.btn_camera = QPushButton()
        self.btn_play = QPushButton()
        self.btn_suspend = QPushButton()
        self.btn_folder = QPushButton()
        self.btn_min = QPushButton()
        self.btn_close = QPushButton()
        
        # NEW: Top Right System Monitor
        self.lbl_sys_monitor = QLabel("RAM 65% | TEM 15°C", self.central_widget)
        self.lbl_sys_monitor.setStyleSheet(f"color: {C_TEXT}; font-size: 11px; background: transparent; border: none; font-weight: bold;")
        self.lbl_sys_monitor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.lbl_sys_monitor.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # NEW: I.L.U.M Pro Label Bottom Right
        self.lbl_pro = QLabel("I.L.U.M <b>Pro</b>", self.central_widget)
        self.lbl_pro.setStyleSheet(f"color: {C_TEXT}; font-size: 14px; background: transparent; border: none;")
        self.lbl_pro.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.lbl_pro.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Left/Center Button Arrays
        self.head_buttons = [
            (self.btn_settings, 'fa5s.bars', self._open_settings),
            (self.btn_folder, 'fa5s.folder', self._open_folder),
            (self.btn_play, 'fa5s.bell', self._open_diagnostic_logs),
            (self.btn_suspend, 'fa5s.moon', self._toggle_suspend),
            (self.btn_camera, 'fa5s.video', self._toggle_camera_gestures),
            (self.btn_edit_hud, 'fa5s.comment-dots', self.toggle_hud_edit_mode),
        ]
        
        if HAS_QTA:
            for btn, icon, cb in self.head_buttons:
                btn.setIcon(qta.icon(icon, color='white'))
                btn.clicked.connect(cb)
                btn.setFixedSize(38, 38)
                btn.setStyleSheet("background: transparent; border: none;")
                btn.setParent(self.central_widget)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Hidden Bento Widgets
        self.system_w = SystemWidget(self.central_widget)
        self.todo_w = TodoWidget(self.central_widget)
        self.notes_w = NotesWidget(self.central_widget)
        self.files_panel = FilesPanel(self.ui)
        self.files_panel.setParent(self.central_widget)
        
        self.system_w.hide()
        self.todo_w.hide()
        self.notes_w.hide()
        self.files_panel.hide()

        # Spotify is now small floating widget
        self.spotify_w = SpotifyWidget(self.central_widget)
        self.spotify_w.setFixedSize(280, 90)

        # Weather is small floating widget
        self.weather_w = WeatherWidget(self.central_widget)
        self.weather_w.setFixedSize(280, 100)
        self.weather_w.hide() # Hidden initially or floating somewhere? We will float it left

        # Clock
        self.clock_w = ClockWidget(self.central_widget)
        
        # Console
        self.txt_console = QLabel(self.central_widget)
        self.txt_console.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self.txt_console.setWordWrap(True)
        self.txt_console.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Hidden compat containers
        self.header_container = QWidget(self.central_widget)
        self.header_container.hide()
        self.bento_container = QWidget(self.central_widget)
        self.bento_container.hide()

        self._force_close = False
        self.tray_icon = None
        self._setup_tray_icon()
        
        self.ui.is_sleeping = False
        
        self.update_theme_styles()
        self._drag_pos = None
        self._shutdown_sig.connect(self._handle_shutdown)
        self.update_widgets_visibility()
        
        try:
            wx = cfg.get("window_x")
            wy = cfg.get("window_y")
            if wx is not None and wy is not None:
                self.move(int(wx), int(wy))
        except Exception:
            pass

"""

new_resize = """    def resizeEvent(self, event):
        if event is not None:
            super().resizeEvent(event)
        W = self.central_widget.width()
        H = self.central_widget.height()
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, W, H), 20.0, 20.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        
        if hasattr(self, "lbl_bg_image") and self.lbl_bg_image.isVisible() and hasattr(self, "_bg_image_path") and self._bg_image_path:
            self.lbl_bg_image.setGeometry(0, 0, W, H)
            if Path(self._bg_image_path).exists():
                from PyQt6.QtGui import QPixmap
                pix = QPixmap(self._bg_image_path)
                if not pix.isNull():
                    scaled_pix = pix.scaled(W, H, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    self.lbl_bg_image.setPixmap(scaled_pix)
            self.lbl_bg_image.lower()
            
        # Top Left Clock
        self.clock_w.setGeometry(30, 20, 300, 80)
        
        # Top Right Stats & Menu
        self.lbl_sys_monitor.setGeometry(W - 200, 40, 140, 30)
        self.btn_settings.setGeometry(W - 50, 35, 38, 38)
        
        # Center Logo & Wave
        self.lbl_brand_center.setGeometry(0, H//2 - 200, W, 150)
        self.orb.setGeometry(0, H//2 - 50, W, 100)
        
        # Floating Spotify
        self.spotify_w.setGeometry(W//2 - 140, H//2 + 70, 280, 90)
        
        # Bottom Left Tools (Campana, Carpeta, Calendario)
        self.btn_play.setGeometry(40, H - 70, 38, 38)
        self.btn_folder.setGeometry(90, H - 70, 38, 38)
        
        # Bottom Center Tools (Camara, Luna, Chat)
        self.btn_camera.setGeometry(W//2 - 80, H - 60, 38, 38)
        self.btn_suspend.setGeometry(W//2 - 20, H - 60, 38, 38)
        self.btn_edit_hud.setGeometry(W//2 + 40, H - 60, 38, 38)
        
        # Bottom Right Pro
        self.lbl_pro.setGeometry(W - 150, H - 50, 120, 30)
        
        # Chat Console text slightly above center buttons
        self.txt_console.setGeometry(30, H - 180, W - 60, 80)
        
        if hasattr(self, "widget_bar_container") and not self.widget_bar_container.isHidden():
            self.widget_bar_container.setGeometry(W//2 - 250, H - 100, 500, 35)

        self.lbl_brand_center.raise_()
        self.orb.raise_()
        self.spotify_w.raise_()
        if hasattr(self, "weather_w"):
            self.weather_w.setGeometry(40, H - 180, 240, 100)
            self.weather_w.raise_()
        self.clock_w.raise_()
        self.lbl_sys_monitor.raise_()
        for btn in [self.btn_settings, self.btn_play, self.btn_folder, self.btn_camera, self.btn_suspend, self.btn_edit_hud]:
            btn.raise_()

"""

new_spotify_style = """    def update_style(self):
        try:
            from ui_styles import liquid_glass_widget_style
            self.setStyleSheet(liquid_glass_widget_style("SpotifyWidget", C_PRI, C_BORDER, C_TEXT))
        except ImportError:
            self.setStyleSheet(f\"\"\"
                QWidget#SpotifyWidget {{
                    background: rgba(10, 10, 10, 0.65);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 15px;
                }}
            \"\"\")
        if hasattr(self, 'lbl_title'): self.lbl_title.hide()
        self.lbl_track.setStyleSheet(f"font-size: 11px; font-weight: bold; border: none; background: transparent; color: white;")
        self.lbl_artist.setStyleSheet(f"font-size: 9px; color: {C_TEXT}; border: none; background: transparent;")
        for btn, _, _ in getattr(self, "buttons_list", []):
            btn.setStyleSheet("background: transparent; border: none; padding: 2px;")
        apply_glass_shadow(self, blur_radius=20, alpha=100)"""

import re
# Patch __init__
pattern_init = re.compile(r'    def __init__\(self, ui, face_path\):.*?    def update_widgets_visibility\(self\):', re.DOTALL)
content = pattern_init.sub(new_init + "\n    def update_widgets_visibility(self):", content)

# Patch resizeEvent
pattern_resize = re.compile(r'    def resizeEvent\(self, event\):.*?    def _open_settings\(self\):', re.DOTALL)
content = pattern_resize.sub(new_resize + "\n    def _open_settings(self):", content)

# Patch SpotifyWidget style
pattern_spotify = re.compile(r'    def update_style\(self\):.*?        apply_glass_shadow\(self\)', re.DOTALL)
content = pattern_spotify.sub(new_spotify_style, content, count=1)

with open('ui.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch applied to ui.py!")
