"""
Universal App Control
=====================
Abre cualquier aplicación instalada en Windows usando la tecla Windows y búsqueda.
"""

import time
import subprocess
try:
    import pyautogui
except ImportError:
    pass

def universal_app_control(parameters: dict, player=None) -> str:
    app_name = parameters.get("app_name", "")
    
    if not app_name:
        return "❌ Por favor especifica qué aplicación quieres abrir."
        
    try:
        # Presionar la tecla Windows para abrir el menú inicio
        pyautogui.press("win")
        time.sleep(0.5)
        
        # Escribir el nombre de la app
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.5)
        
        # Presionar Enter para abrir la primera coincidencia
        pyautogui.press("enter")
        
        return f"💻 Abriendo la aplicación '{app_name}' en tu computadora."
        
    except Exception as e:
        if player:
            player.write_log(f"Error abriendo app: {e}")
        return f"❌ Hubo un problema al intentar abrir {app_name}."
