# -*- coding: utf-8 -*-
import webbrowser
import urllib.parse
import urllib.request
import json

def unified_communications(parameters: dict, player=None) -> str:
    """
    Centraliza el envío y consulta de mensajes en múltiples plataformas (WhatsApp, Telegram, Discord, Gmail).
    """
    platform = parameters.get("platform", "").lower()
    action = parameters.get("action", "").lower()
    recipient = parameters.get("recipient", "")  # Número, email, ID de chat, webhook URL
    message = parameters.get("message", "")
    
    if not platform:
        return "Error: Debes especificar una plataforma de comunicación (whatsapp, telegram, discord, gmail)."

    if platform == "whatsapp":
        # Extendemos el soporte de WhatsApp
        if not recipient or not message:
            return "Error: WhatsApp requiere un 'recipient' (número o contacto) y un 'message'."
        
        encoded_msg = urllib.parse.quote(message)
        phone = "".join(filter(str.isdigit, recipient))
        
        if phone:
            url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}"
        else:
            url = f"https://web.whatsapp.com/send?text={encoded_msg}"
            
        webbrowser.open(url)
        return f"Abriendo chat de WhatsApp Web con {recipient} para enviar el mensaje: '{message}'."

    elif platform == "telegram":
        # Envío simplificado a Telegram usando Bot API HTTP
        token = parameters.get("token") or "TELEGRAM_BOT_TOKEN_PLACEHOLDER"
        chat_id = recipient or "TELEGRAM_CHAT_ID_PLACEHOLDER"
        
        if token == "TELEGRAM_BOT_TOKEN_PLACEHOLDER" or chat_id == "TELEGRAM_CHAT_ID_PLACEHOLDER":
            return (
                "Para enviar vía Telegram de forma nativa, configura tu Token de Bot y Chat ID. "
                "Abriendo Telegram Web en su lugar..."
            )
            webbrowser.open("https://web.telegram.org")
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message
        }
        
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("ok"):
                    return f"Mensaje de Telegram enviado con éxito al ID {chat_id}."
                return f"Telegram respondió con error: {res.get('description')}"
        except Exception as e:
            return f"No se pudo enviar a Telegram automáticamente: {e}. Abriendo Telegram Web."
            webbrowser.open("https://web.telegram.org")

    elif platform == "discord":
        # Native Discord Desktop Control
        if not recipient or not message:
            return "Error: Discord requiere un 'recipient' y un 'message'."
            
        import os
        import time
        try:
            import pyautogui
            import pygetwindow as gw
        except ImportError:
            return "Error: Faltan las librerías 'pyautogui' y 'pygetwindow' para controlar Discord de Escritorio."
            
        if player: 
            player.write_log(f"🎮 Abriendo Discord de Escritorio para enviar a {recipient}...")
            
        try:
            # Check if Discord is already running
            discord_windows = [w for w in gw.getWindowsWithTitle("Discord") if w.title != ""]
            if not discord_windows:
                # Try to launch discord
                os.startfile(os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe") + " --processStart Discord.exe")
                time.sleep(6) # Wait for it to open
                discord_windows = [w for w in gw.getWindowsWithTitle("Discord") if w.title != ""]
                
            if discord_windows:
                window = discord_windows[0]
                if not window.isActive:
                    try:
                        window.restore()
                        window.activate()
                    except Exception:
                        pass
                time.sleep(1)
                
                # Use Quick Switcher (Ctrl+K)
                pyautogui.hotkey('ctrl', 'k')
                time.sleep(1)
                
                # Type recipient name
                pyautogui.write(recipient, interval=0.01)
                time.sleep(2)
                
                # Press enter to select the top result
                pyautogui.press('enter')
                time.sleep(1)
                
                # Type message and send
                pyautogui.write(message, interval=0.01)
                time.sleep(0.5)
                pyautogui.press('enter')
                
                return f"Mensaje enviado exitosamente a '{recipient}' en Discord de Escritorio."
            else:
                return "Error: No se pudo abrir o encontrar la ventana de Discord de Escritorio."
                
        except Exception as e:
            return f"Error controlando Discord de Escritorio: {str(e)}"

    elif platform == "gmail":
        # Envío de correo usando mailto o API ligera
        subject = parameters.get("subject", "Mensaje de ILUM AI")
        if not recipient or not message:
            return "Error: Gmail requiere un 'recipient' (email de destino) y un 'message'."
            
        encoded_subject = urllib.parse.quote(subject)
        encoded_body = urllib.parse.quote(message)
        mailto_url = f"mailto:{recipient}?subject={encoded_subject}&body={encoded_body}"
        
        try:
            webbrowser.open(mailto_url)
            return f"Abriendo cliente de correo predeterminado (Gmail) para enviar email a {recipient}."
        except Exception as e:
            return f"Error abriendo cliente de correo: {e}"

    else:
        return f"Plataforma '{platform}' no soportada actualmente por la central de comunicaciones."
