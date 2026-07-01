"""
Discord Automation Module for ILUM
==================================
Permite enviar mensajes en Discord usando atajos de teclado nativos (Ctrl+K).
"""

import time
import subprocess
try:
    import pyautogui
except ImportError:
    pyautogui = None

def discord_control(parameters: dict, player=None) -> str:
    """
    Control de automatización real para Discord Desktop.
    Acciones: send
    """
    action = parameters.get("action", "send").lower()
    receiver = parameters.get("receiver", "")
    message = parameters.get("message", "")

    if not pyautogui:
        return "❌ Error: PyAutoGUI no está instalado."

    if action == "send":
        if not receiver or not message:
            return "❌ Error: Faltan parámetros (receiver o message)."
            
        if player: player.write_log(f"🎮 Abriendo Discord para mensajear a {receiver}...")
        
        # Abrir Discord nativo
        pyautogui.press('win')
        time.sleep(1)
        pyautogui.write('discord', interval=0.05)
        time.sleep(1)
        pyautogui.press('enter')
        
        time.sleep(8) # Esperamos a que Discord cargue por completo
        
        # Atajo nativo de Discord para buscar canales o usuarios: Ctrl + K
        pyautogui.hotkey('ctrl', 'k')
        time.sleep(2)
        
        # Escribir el nombre del usuario o canal
        pyautogui.write(receiver, interval=0.05)
        time.sleep(3) # Esperar resultados de busqueda
        
        # Enter para seleccionar el primer resultado
        pyautogui.press('enter')
        time.sleep(2) # Esperar a que se abra el chat
        
        # Escribir el mensaje
        pyautogui.write(message, interval=0.02)
        time.sleep(1)
        
        # Enviar
        pyautogui.press('enter')
        
        return f"✅ Mensaje enviado a {receiver} en Discord."
        
    return "❌ Acción no reconocida en Discord."
