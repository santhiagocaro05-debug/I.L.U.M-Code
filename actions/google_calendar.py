"""
Google Calendar Control
=======================
Automatización de Calendario usando Deep Links.
"""

import webbrowser
import urllib.parse

def google_calendar(parameters: dict, player=None) -> str:
    action = parameters.get("action", "view").lower()
    
    if action == "view":
        webbrowser.open("https://calendar.google.com/calendar/u/0/r")
        return "📅 Abriendo tu Google Calendar."
        
    elif action == "add":
        title = parameters.get("title", "Nuevo Evento")
        details = parameters.get("details", "")
        location = parameters.get("location", "")
        
        # No ponemos fechas exactas por ahora para que el usuario pueda ajustarlas en la UI,
        # pero llenamos todo el resto del formulario mágicamente.
        url = f"https://calendar.google.com/calendar/u/0/r/eventedit?text={urllib.parse.quote(title)}"
        if details:
            url += f"&details={urllib.parse.quote(details)}"
        if location:
            url += f"&location={urllib.parse.quote(location)}"
            
        webbrowser.open(url)
        return f"📅 Evento '{title}' preparado en Google Calendar. Solo falta que confirmes la hora."
        
    return "📅 Acción de calendario no reconocida."
