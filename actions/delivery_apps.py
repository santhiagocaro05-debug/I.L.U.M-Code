"""
Delivery Apps Automation for ILUM
=================================
Módulo para controlar aplicaciones de comida a domicilio.
"""

import webbrowser
import urllib.parse

def delivery_apps(parameters: dict, player=None) -> str:
    app_name = parameters.get("app", "rappi").lower()
    query = parameters.get("query", "")
    
    if not query:
        return f"❌ Por favor dime qué comida o restaurante buscar en {app_name}."

    if "rappi" in app_name:
        url = f"https://www.rappi.com/search?store_type=all&query={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"🍔 Buscando '{query}' en Rappi."
        
    elif "uber" in app_name and "eats" in app_name:
        url = f"https://www.ubereats.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"🍔 Buscando '{query}' en Uber Eats."
        
    elif "pedidos" in app_name:
        url = f"https://www.pedidosya.com/restaurantes?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"🍔 Buscando '{query}' en PedidosYa."
        
    else:
        # Default fallback
        url = f"https://www.rappi.com/search?store_type=all&query={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"🍔 Buscando '{query}' en aplicaciones de delivery."
