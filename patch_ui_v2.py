import re

def patch():
    with open("ui.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add seek_requested signal to FloatingMediaWidget
    if "seek_requested = pyqtSignal(int)" not in content:
        content = content.replace(
            "class FloatingMediaWidget(QWidget):",
            "class FloatingMediaWidget(QWidget):\n    seek_requested = pyqtSignal(int)"
        )

    # 2. Add progress bar to FloatingMediaWidget
    if "self.prog_bar = QProgressBar()" not in content.split("class FloatingMediaWidget")[1]:
        prog_bar_code = """
        # Progress Bar
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(3)
        self.prog_bar.setStyleSheet('''
        QProgressBar { background: rgba(255,255,255,0.08); border: none; border-radius: 2px; }
        QProgressBar::chunk { background: rgba(255,255,255,0.85); border-radius: 2px; }
        ''')
        self.prog_bar.mousePressEvent = self._on_prog_click
        self._dur = 0
        
        self.lbl_time_l = QLabel("0:00")
        self.lbl_time_l.setStyleSheet("font-size:8px;color:rgba(200,200,210,0.55);")
        self.lbl_time_r = QLabel("0:00")
        self.lbl_time_r.setStyleSheet("font-size:8px;color:rgba(200,200,210,0.55);")
        
        prog_row = QHBoxLayout()
        prog_row.setSpacing(4)
        prog_row.addWidget(self.lbl_time_l)
        prog_row.addWidget(self.prog_bar, 1)
        prog_row.addWidget(self.lbl_time_r)
        
        right.addLayout(prog_row)
"""
        content = content.replace(
            "ctrl = QHBoxLayout()",
            prog_bar_code + "\n        ctrl = QHBoxLayout()"
        )

    # 3. Add update_timeline and _on_prog_click methods
    if "def update_timeline(self, pos, dur):" not in content:
        methods_code = """
    def update_timeline(self, pos, dur):
        self._dur = dur
        self.prog_bar.setValue(int(pos / dur * 100) if dur else 0)
        self.lbl_time_l.setText(f"{pos//60}:{pos%60:02d}")
        self.lbl_time_r.setText(f"{dur//60}:{dur%60:02d}")

    def _on_prog_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dur > 0:
            val = int(event.position().x() / self.prog_bar.width() * self._dur)
            self.seek_requested.emit(val)

"""
        content = content.replace(
            "    def update_info(self, title, artist, is_playing, thumb):",
            methods_code + "    def update_info(self, title, artist, is_playing, thumb):"
        )

    # 4. Connect signals in MainWindow
    if "self.media_worker.timeline_updated.connect(self.media_float.update_timeline)" not in content:
        content = content.replace(
            "self.media_worker.media_updated.connect(self.media_float.update_info)",
            "self.media_worker.media_updated.connect(self.media_float.update_info)\n        self.media_worker.timeline_updated.connect(self.media_float.update_timeline)\n        self.media_float.seek_requested.connect(self.media_worker.seek)"
        )

    with open("ui.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("Patch V2 applied")

if __name__ == "__main__":
    patch()
