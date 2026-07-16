import re

def patch_arduino_ui():
    with open('ui.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add Arduino to tab_names
    tab_names_orig = """        tab_names = [
            ("General", "fa5s.cog"),
            ("Inteligencia", "fa5s.brain"),
            ("Personalidad", "fa5s.user-astronaut"),
            ("Dispositivos", "fa5s.laptop-house"),
            ("Automatización", "fa5s.robot"),
            ("Macros", "fa5s.keyboard"),
            ("Tienda", "fa5s.store")
        ]"""
    tab_names_new = """        tab_names = [
            ("General", "fa5s.cog"),
            ("Inteligencia", "fa5s.brain"),
            ("Personalidad", "fa5s.user-astronaut"),
            ("Dispositivos", "fa5s.laptop-house"),
            ("Automatización", "fa5s.robot"),
            ("Macros", "fa5s.keyboard"),
            ("Tienda", "fa5s.store"),
            ("Arduino", "fa5s.microchip")
        ]"""
    content = content.replace(tab_names_orig, tab_names_new)

    # 2. Add self._build_tab_arduino() call
    build_calls_orig = """        self._build_tab_macros()
        self._build_tab_store()"""
    build_calls_new = """        self._build_tab_macros()
        self._build_tab_store()
        self._build_tab_arduino()"""
    content = content.replace(build_calls_orig, build_calls_new)

    # 3. Add _build_tab_arduino method definition after _build_tab_store
    
    # We will search for a place to insert `def _build_tab_arduino(self):`
    # We can put it right before `def _build_tab_general(self):`
    build_general_idx = content.find("    def _build_tab_general(self):")
    
    arduino_tab_code = """
    def _build_tab_arduino(self):
        tab = self._create_tab_widget()
        card = tab.add_card("🚀 CONEXIÓN ARDUINO", col_span=2)
        layout = card.content_layout
        
        # Puertos COM
        lbl_port = QLabel("🔌 Puerto COM:")
        lbl_port.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: 600; font-size: 12px;")
        layout.addWidget(lbl_port, 0, 0)
        
        self.cmb_arduino_port = QComboBox()
        self.cmb_arduino_port.setMinimumHeight(42)
        self.cmb_arduino_port.setStyleSheet(self.cmb_ai_provider.styleSheet())
        layout.addWidget(self.cmb_arduino_port, 0, 1)
        
        self.btn_refresh_ports = QPushButton("🔄 ACTUALIZAR")
        self.btn_refresh_ports.setFixedHeight(42)
        self.btn_refresh_ports.clicked.connect(self._refresh_arduino_ports)
        layout.addWidget(self.btn_refresh_ports, 0, 2)
        
        # Botón Conectar
        self.btn_connect_arduino = QPushButton("CONECTAR")
        self.btn_connect_arduino.setFixedHeight(42)
        self.btn_connect_arduino.clicked.connect(self._toggle_arduino_connection)
        layout.addWidget(self.btn_connect_arduino, 1, 0, 1, 3)
        
        # Enviar Comandos
        self.inp_arduino_cmd = QLineEdit()
        self.inp_arduino_cmd.setPlaceholderText("Comando a enviar (ej: 1, 0, ON, OFF)")
        self.inp_arduino_cmd.setMinimumHeight(42)
        self.inp_arduino_cmd.setStyleSheet(self.inp_gemini.styleSheet())
        layout.addWidget(self.inp_arduino_cmd, 2, 0, 1, 2)
        
        self.btn_send_cmd = QPushButton("ENVIAR")
        self.btn_send_cmd.setFixedHeight(42)
        self.btn_send_cmd.clicked.connect(self._send_arduino_cmd)
        layout.addWidget(self.btn_send_cmd, 2, 2)
        
        # Consola
        self.arduino_console = QTextEdit()
        self.arduino_console.setReadOnly(True)
        self.arduino_console.setMinimumHeight(150)
        self.arduino_console.setStyleSheet(\"\"\"
            QTextEdit {
                background: rgba(0,0,0,0.5);
                color: #00ff00;
                font-family: Consolas, monospace;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 8px;
            }
        \"\"\")
        layout.addWidget(self.arduino_console, 3, 0, 1, 3)
        
        self.stacked_widget.addWidget(tab)
        self._refresh_arduino_ports()
        
    def _refresh_arduino_ports(self):
        self.cmb_arduino_port.clear()
        try:
            from core.arduino_manager import arduino
            ports = arduino.get_available_ports()
            for p in ports:
                self.cmb_arduino_port.addItem(p)
            if not ports:
                self.cmb_arduino_port.addItem("No hay puertos")
        except:
            self.cmb_arduino_port.addItem("Error cargando puertos")
            
    def _toggle_arduino_connection(self):
        try:
            from core.arduino_manager import arduino
            if arduino.is_connected:
                arduino.disconnect()
                self.btn_connect_arduino.setText("CONECTAR")
                self.arduino_console.append("[Sistema] Desconectado.")
            else:
                port = self.cmb_arduino_port.currentText()
                if "No hay" in port or "Error" in port:
                    return
                ok, msg = arduino.connect(port)
                self.arduino_console.append(f"[Sistema] {msg}")
                if ok:
                    self.btn_connect_arduino.setText("DESCONECTAR")
                    arduino.on_message_received = self._arduino_msg_received
        except Exception as e:
            self.arduino_console.append(f"[Error] {e}")
            
    def _send_arduino_cmd(self):
        cmd = self.inp_arduino_cmd.text().strip()
        if not cmd: return
        try:
            from core.arduino_manager import arduino
            ok, msg = arduino.send_command(cmd)
            self.arduino_console.append(f"> {msg}")
            self.inp_arduino_cmd.clear()
        except Exception as e:
            self.arduino_console.append(f"[Error] {e}")
            
    def _arduino_msg_received(self, msg):
        # We need to use a signal or QMetaObject.invokeMethod to update GUI from thread
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(self.arduino_console, "append", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"< {msg}"))

"""
    content = content[:build_general_idx] + arduino_tab_code + content[build_general_idx:]

    with open('ui.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_arduino_ui()
