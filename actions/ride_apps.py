"""
Ride Hailing Apps Automation for ILUM
=====================================
Módulo para controlar aplicaciones de transporte (Uber, DiDi).
"""

import webbrowser
import urllib.parse
import os

def ride_apps(parameters: dict, player=None) -> str:
    app_name = parameters.get("app", "uber").lower()
    destination = parameters.get("destination", "")
    
    if not destination:
        return f"❌ Por favor dime a dónde quieres ir usando {app_name}."

    if "uber" in app_name:
        # Intentamos usar el URI Scheme de Uber que lanza la app nativa en Windows/Móvil
        # o abre la web para pedir el viaje si no está la app.
        pickup = "my_location"
        dropoff = urllib.parse.quote(destination)
        url = f"https://m.uber.com/ul/?action=setPickup&pickup={pickup}&dropoff[formatted_address]={dropoff}"
        webbrowser.open(url)
        return f"🚗 Preparando viaje a '{destination}' en Uber."
        
    elif "didi" in app_name:
        # DiDi no tiene un URI universal de escritorio tan robusto como Uber, abrimos web o app genérica
        # didi:// no siempre funciona en Windows, usaremos web search
        url = "https://global.didiglobal.com/"
        try:
            os.startfile("didi://")
        except:
            webbrowser.open(url)
        return f"🚗 Abriendo DiDi para viajar a '{destination}'."
        
    else:
        # Default a Uber
        pickup = "my_location"
        dropoff = urllib.parse.quote(destination)
        url = f"https://m.uber.com/ul/?action=setPickup&pickup={pickup}&dropoff[formatted_address]={dropoff}"
        webbrowser.open(url)
        return f"🚗 Preparando viaje a '{destination}' en aplicación de transporte."
