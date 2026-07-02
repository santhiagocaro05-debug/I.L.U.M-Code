def clean():
    with open("ui.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    bad_code = """        # Y"S PROGRESS
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(3)
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
        
        right.addLayout(prog_row)"""

    good_code = """        # PROGRESS
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setFixedHeight(3)
        self.prog_bar.setStyleSheet('''
        QProgressBar {
            background: rgba(255,255,255,0.08);
            border: none;
            border-radius: 2px;
        }
        QProgressBar::chunk {
            background: rgba(255,255,255,0.85);
            border-radius: 2px;
        }
        ''')

        self.lbl_time_l = QLabel("0:00")
        self.lbl_time_l.setStyleSheet("font-size:8px;color:rgba(200,200,210,0.55);")

        self.lbl_time_r = QLabel("0:00")
        self.lbl_time_r.setStyleSheet("font-size:8px;color:rgba(200,200,210,0.55);")

        prog_row = QHBoxLayout()
        prog_row.setSpacing(4)
        prog_row.addWidget(self.lbl_time_l)
        prog_row.addWidget(self.prog_bar, 1)
        prog_row.addWidget(self.lbl_time_r)

        right.addLayout(prog_row)"""
        
    content = content.replace(bad_code, good_code)
    
    with open("ui.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    clean()
