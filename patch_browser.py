import re

def inject_embedded_browser():
    with open("ui.py", "r", encoding="utf-8") as f:
        code = f.read()

    if "class EmbeddedBrowserDialog" in code:
        print("Already injected")
        return

    # Add the class before MainWindow
    class_def = """
class EmbeddedBrowserDialog(QDialog):
    def __init__(self, parent=None, url="https://google.com"):
        super().__init__(parent)
        self.setWindowTitle("ILUM Web")
        self.setFixedSize(1200, 800)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Contenedor principal con fondo redondeado
        container = QFrame(self)
        container.setObjectName("WebContainer")
        container.setStyleSheet('''
            #WebContainer {
                background: rgba(15, 15, 20, 0.95);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
            }
        ''')
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(5, 5, 5, 5)

        # Barra superior con botón de cierre
        top_bar = QHBoxLayout()
        title = QLabel("ILUM BROWSER")
        title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 14px; font-weight: bold; font-family: 'Segoe UI';")
        
        btn_close = QPushButton("YZ")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet('''
            QPushButton {
                background: rgba(255, 60, 60, 0.8);
                color: white;
                border-radius: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 60, 60, 1);
            }
        ''')
        btn_close.clicked.connect(self.close)

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(btn_close)
        
        c_layout.addLayout(top_bar)

        # Vista Web
        self.web = QWebEngineView()
        self.web.setUrl(QUrl(url))
        c_layout.addWidget(self.web)

        layout.addWidget(container)

"""
    
    # Insert before class MainWindow
    code = code.replace("class MainWindow(QMainWindow):", class_def + "\nclass MainWindow(QMainWindow):")
    
    # Now add open_embedded_browser to IlumUI
    method_def = """
    def open_embedded_browser(self, url):
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(self._win, "_do_open_browser", Qt.ConnectionType.QueuedConnection, Q_ARG(str, url))
"""
    code = code.replace("def update_music_widget(self, current_track_info: dict):", method_def + "\n    def update_music_widget(self, current_track_info: dict):")
    
    # And add _do_open_browser to MainWindow
    mw_method = """
    @pyqtSlot(str)
    def _do_open_browser(self, url):
        self.browser = EmbeddedBrowserDialog(self, url)
        self.browser.show()
"""
    code = code.replace("    @pyqtSlot(dict)\n    def _do_update_music_widget(self, track_info: dict):", mw_method + "\n    @pyqtSlot(dict)\n    def _do_update_music_widget(self, track_info: dict):")

    with open("ui.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("Injected EmbeddedBrowserDialog")

if __name__ == "__main__":
    inject_embedded_browser()
