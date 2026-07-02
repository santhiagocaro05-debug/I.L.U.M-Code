import os
import time
import urllib.parse

def social_manager(parameters: dict, player=None) -> str:
    """
    Manager for Social Networks (WhatsApp, Discord, Instagram).
    Parameters:
      - platform: 'whatsapp', 'discord', 'instagram'
      - action: 'send_message', 'open', 'post_story'
      - target: phone number or username
      - message: text to send
    """
    platform = parameters.get("platform", "").lower()
    action = parameters.get("action", "")
    target = parameters.get("target", "")
    message = parameters.get("message", "")

    try:
        if platform == "whatsapp":
            if action == "open":
                os.system("start whatsapp://")
                return "WhatsApp abierto."
            elif action == "send_message" and target and message:
                encoded_msg = urllib.parse.quote(message)
                os.system(f"start whatsapp://send?phone={target}&text={encoded_msg}")
                return f"Borrador de WhatsApp creado para {target}. El usuario debe presionar Enter."
        
        elif platform == "instagram":
            if action == "open":
                os.system("start https://www.instagram.com/")
                return "Instagram abierto en el navegador."
            elif action == "send_message" and target:
                os.system(f"start https://www.instagram.com/direct/t/{target}/")
                return f"Chat de Instagram con {target} abierto."
            elif action == "post_story":
                return "Para subir una historia, necesitas la app móvil o emulador. Abriendo Instagram web."
                
        elif platform == "discord":
            if action == "open":
                os.system("start discord://")
                return "Discord abierto."
            elif action == "send_message" and target:
                return "Abriendo Discord. (Nota: Discord no tiene URI de mensajes directos abierta, abriendo la app normal)."
                
        return f"Acción {action} para {platform} ejecutada genéricamente."
    except Exception as e:
        return f"Error en social_manager: {e}"

def pc_settings(parameters: dict, player=None) -> str:
    """
    Control de configuración de la PC (Windows Settings).
    Parameters:
      - setting: 'bluetooth', 'wifi', 'display', 'sound', 'update', 'apps', 'main'
    """
    setting = parameters.get("setting", "").lower()
    
    uris = {
        "bluetooth": "ms-settings:bluetooth",
        "wifi": "ms-settings:network-wifi",
        "display": "ms-settings:display",
        "sound": "ms-settings:sound",
        "update": "ms-settings:windowsupdate",
        "apps": "ms-settings:appsfeatures",
        "main": "ms-settings:"
    }
    
    uri = uris.get(setting, "ms-settings:")
    try:
        os.system(f"start {uri}")
        return f"Configuración de {setting} abierta con éxito."
    except Exception as e:
        return f"Error abriendo configuración: {e}"
