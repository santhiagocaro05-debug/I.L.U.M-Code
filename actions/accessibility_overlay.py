"""
accessibility_overlay.py — Barra flotante de accesibilidad para ILUM
"""
import os
import sys
from pathlib import Path


def accessibility_overlay(parameters: dict, player=None) -> str:
    """
    Muestra, oculta o alterna la barra flotante de accesibilidad ILUM sobre el escritorio.
    
    Parámetros:
    - action: "show" | "hide" | "toggle" | "status"
    """
    action = parameters.get("action", "toggle").lower()
    
    # Intentar importar la barra de accesibilidad
    try:
        # Buscar si existe el módulo de la barra flotante
        from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtGui import QFont
        
        # Verificar si ya existe una instancia de la barra
        if not hasattr(accessibility_overlay, "_overlay_instance"):
            accessibility_overlay._overlay_instance = None
        
        if action == "show" or action == "toggle":
            if accessibility_overlay._overlay_instance is None or not accessibility_overlay._overlay_instance.isVisible():
                # Crear la barra flotante
                overlay = QWidget()
                overlay.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint | 
                    Qt.WindowType.WindowStaysOnTopHint |
                    Qt.WindowType.Tool
                )
                overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                overlay.setFixedSize(280, 50)
                
                # Estilo de la barra
                overlay.setStyleSheet("""
                    QWidget {
                        background: rgba(15, 10, 5, 0.88);
                        border: 1.5px solid rgba(245, 158, 11, 0.4);
                        border-radius: 12px;
                    }
                    QPushButton {
                        background: rgba(245, 158, 11, 0.15);
                        color: #fde68a;
                        border: 1px solid rgba(245, 158, 11, 0.3);
                        border-radius: 6px;
                        font-weight: bold;
                        padding: 4px 8px;
                        font-size: 10px;
                    }
                    QPushButton:hover {
                        background: rgba(245, 158, 11, 0.3);
                    }
                    QLabel {
                        color: #fde68a;
                        font-weight: bold;
                        font-size: 11px;
                    }
                """)
                
                layout = QHBoxLayout(overlay)
                layout.setContentsMargins(12, 8, 12, 8)
                layout.setSpacing(10)
                
                # Icono
                icon_lbl = QLabel("♿")
                icon_lbl.setStyleSheet("font-size: 18px; background: transparent; border: none;")
                layout.addWidget(icon_lbl)
                
                # Título
                title_lbl = QLabel("ILUM Accesibilidad")
                title_lbl.setStyleSheet("font-weight: bold; font-size: 11px; background: transparent; border: none;")
                layout.addWidget(title_lbl)
                
                layout.addStretch()
                
                # Botones de accesibilidad
                btn_reader = QPushButton("🔊 Lector")
                btn_reader.setToolTip("Activar lector de pantalla")
                btn_reader.clicked.connect(lambda: _toggle_screen_reader(player))
                layout.addWidget(btn_reader)
                
                btn_contrast = QPushButton("🎨 Contraste")
                btn_contrast.setToolTip("Activar alto contraste")
                btn_contrast.clicked.connect(lambda: _toggle_high_contrast(player))
                layout.addWidget(btn_contrast)
                
                btn_magnify = QPushButton("🔍 Lupa")
                btn_magnify.setToolTip("Activar lupa")
                btn_magnify.clicked.connect(lambda: _toggle_magnifier(player))
                layout.addWidget(btn_magnify)
                
                # Botón cerrar
                btn_close = QPushButton("✕")
                btn_close.setFixedSize(24, 24)
                btn_close.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: rgba(255, 255, 255, 0.5);
                        border: none;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        color: #ff3b30;
                    }
                """)
                btn_close.clicked.connect(lambda: accessibility_overlay({"action": "hide"}, player))
                layout.addWidget(btn_close)
                
                # Posicionar en la esquina superior derecha
                screen = QApplication.primaryScreen()
                screen_geo = screen.availableGeometry()
                overlay.move(screen_geo.width() - overlay.width() - 20, 20)
                
                overlay.show()
                accessibility_overlay._overlay_instance = overlay
                
                msg = "♿ Barra de accesibilidad mostrada"
                if player:
                    player.write_log(msg)
                return msg
            else:
                # Si está visible y es toggle, ocultar
                if action == "toggle":
                    return accessibility_overlay({"action": "hide"}, player)
                else:
                    return "♿ La barra de accesibilidad ya está visible"
        
        elif action == "hide":
            if accessibility_overlay._overlay_instance is not None:
                accessibility_overlay._overlay_instance.hide()
                accessibility_overlay._overlay_instance.deleteLater()
                accessibility_overlay._overlay_instance = None
                msg = "♿ Barra de accesibilidad ocultada"
                if player:
                    player.write_log(msg)
                return msg
            else:
                return "♿ La barra de accesibilidad no estaba visible"
        
        elif action == "status":
            if accessibility_overlay._overlay_instance is not None and accessibility_overlay._overlay_instance.isVisible():
                return "♿ Barra de accesibilidad: ACTIVA (visible)"
            else:
                return "♿ Barra de accesibilidad: INACTIVA (oculta)"
        
        else:
            return f"♿ Acción desconocida: {action}. Usa show, hide, toggle o status"
            
    except Exception as e:
        error_msg = f"❌ Error al mostrar barra de accesibilidad: {e}"
        if player:
            player.write_log(error_msg)
        return error_msg


def _toggle_screen_reader(player=None):
    """Activa/desactiva el lector de pantalla"""
    try:
        import subprocess
        import os
        
        if os.name == 'nt':
            # Verificar si Narrator está corriendo
            result = subprocess.run(
                ["powershell", "-Command", "Get-Process -Name Narrator -ErrorAction SilentlyContinue"],
                capture_output=True, text=True
            )
            
            if "Narrator" in result.stdout:
                # Apagar
                subprocess.Popen(["powershell", "-Command", "Stop-Process -Name Narrator -Force"],
                                shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                msg = "🔊 Lector de pantalla desactivado"
            else:
                # Encender
                subprocess.Popen(["powershell", "-Command", "Start-Process Narrator"],
                                shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                msg = "🔊 Lector de pantalla activado"
            
            if player:
                player.write_log(msg)
        else:
            # Linux - Orca
            subprocess.Popen(["orca"], shell=True)
            msg = "🔊 Lector de pantalla (Orca) activado"
            if player:
                player.write_log(msg)
                
    except Exception as e:
        if player:
            player.write_log(f"❌ Error: {e}")


def _toggle_high_contrast(player=None):
    """Activa/desactiva el alto contraste"""
    try:
        import subprocess
        import os
        
        if os.name == 'nt':
            # Abrir configuración de alto contraste
            subprocess.Popen([
                "powershell", "-Command",
                "Start-Process ms-settings:easeofaccess-highcontrast"
            ], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            msg = "🎨 Abriendo configuración de alto contraste"
            if player:
                player.write_log(msg)
            
    except Exception as e:
        if player:
            player.write_log(f"❌ Error: {e}")


def _toggle_magnifier(player=None):
    """Activa/desactiva la lupa"""
    try:
        import subprocess
        import os
        
        if os.name == 'nt':
            # Verificar si Magnify está corriendo
            result = subprocess.run(
                ["powershell", "-Command", "Get-Process -Name Magnify -ErrorAction SilentlyContinue"],
                capture_output=True, text=True
            )
            
            if "Magnify" in result.stdout:
                # Apagar
                subprocess.Popen(["powershell", "-Command", "Stop-Process -Name Magnify -Force"],
                                shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                msg = "🔍 Lupa desactivada"
            else:
                # Encender
                subprocess.Popen(["powershell", "-Command", "Start-Process Magnify"],
                                shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                msg = "🔍 Lupa activada"
            
            if player:
                player.write_log(msg)
            
    except Exception as e:
        if player:
            player.write_log(f"❌ Error: {e}")