"""
Gmail Control
=============
Automatización de Gmail usando Deep Links para redactar y buscar correos.
"""

import webbrowser
import urllib.parse
import time
try:
    import pyautogui
except ImportError:
    pass

def gmail_control(parameters: dict, player=None) -> str:
    action = parameters.get("action", "read").lower()
    
    if action == "read":
        # Abre Gmail buscando correos no leídos
        url = "https://mail.google.com/mail/u/0/#search/is%3Aunread"
        webbrowser.open(url)
        return "📧 Abriendo Gmail para leer tus correos no leídos."
        
    elif action == "send":
        to = parameters.get("to", "")
        subject = parameters.get("subject", "")
        body = parameters.get("body", "")
        
        # Deep link para redactar un correo
        url = f"https://mail.google.com/mail/u/0/?view=cm&fs=1"
        if to:
            url += f"&to={urllib.parse.quote(to)}"
        if subject:
            url += f"&su={urllib.parse.quote(subject)}"
        if body:
            url += f"&body={urllib.parse.quote(body)}"
            
        webbrowser.open(url)
        
        # Opcionalmente, si el usuario quiere que se envíe solo, podríamos usar pyautogui, 
        # pero es más seguro dejarlo listo para que el usuario confirme.
        return f"📧 Borrador de correo creado en Gmail para {to if to else 'un destinatario'}."
        
    else:
        webbrowser.open("https://mail.google.com/")
        return "📧 Abriendo la bandeja principal de Gmail."
