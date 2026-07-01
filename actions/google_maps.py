import webbrowser
import urllib.parse
from typing import Optional, Dict, Any


def google_maps(parameters: dict, player=None) -> str:
    """
    Abre Google Maps o Google Earth en el navegador con múltiples funcionalidades.
    
    Funciones soportadas:
    - search: Buscar lugares
    - directions: Obtener direcciones/rutas
    - earth: Google Earth
    - place: Ver detalles de un lugar
    - streetview: Street View
    - nearby: Lugares cercanos
    - coordinates: Ir a coordenadas específicas
    - share: Compartir ubicación
    """
    action = parameters.get("action", "search")
    
    # ─── SEARCH ──────────────────────────────────────────────────────
    if action == "search":
        query = parameters.get("query", "")
        if not query:
            query = parameters.get("destination", "")
        
        if not query:
            return "❌ Por favor, especifica qué buscar en Google Maps."
        
        # Opciones de búsqueda avanzada
        radius = parameters.get("radius", "")  # en metros
        place_type = parameters.get("type", "")  # restaurant, cafe, park, etc.
        
        base_url = "https://www.google.com/maps/search/"
        search_query = query
        
        # Si hay tipo de lugar, añadirlo a la búsqueda
        if place_type:
            search_query = f"{place_type} en {query}"
        
        # Si hay radio, añadirlo a la URL (funciona con búsqueda de lugares cercanos)
        if radius and radius.isdigit():
            # Usar formato de búsqueda con radio
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}/@{parameters.get('lat', '')},{parameters.get('lng', '')},{radius}z"
        else:
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}/"
        
        webbrowser.open(url)
        return f"🔍 Buscando '{search_query}' en Google Maps."
    
    # ─── DIRECTIONS ─────────────────────────────────────────────────
    elif action == "directions":
        origin = parameters.get("origin", "mi ubicación")
        destination = parameters.get("destination", "")
        
        if not destination:
            return "❌ Por favor, especifica un destino para la ruta."
        
        mode = parameters.get("mode", "car")
        avoid = parameters.get("avoid", "")  # tolls, highways, ferries, etc.
        waypoints = parameters.get("waypoints", "")  # puntos intermedios
        
        # Mapeo de modos de transporte
        mode_map = {
            "car": "driving",
            "walk": "walking",
            "bike": "bicycling",
            "transit": "transit",
            "flight": "flying"
        }
        g_mode = mode_map.get(mode.lower(), "driving")
        
        # Si es "mi ubicación", no codificar
        origin_encoded = urllib.parse.quote(origin) if origin != "mi ubicación" else "mi+ubicación"
        
        base_url = "https://www.google.com/maps/dir/?api=1"
        url = f"{base_url}&origin={origin_encoded}&destination={urllib.parse.quote(destination)}&travelmode={g_mode}"
        
        # Añadir evasión de peajes/carreteras
        if avoid:
            url += f"&avoid={avoid}"
        
        # Añadir waypoints
        if waypoints:
            url += f"&waypoints={urllib.parse.quote(waypoints)}"
        
        # Añadir opción de ruta alternativa
        if parameters.get("alternatives", False):
            url += "&alternatives=true"
        
        # Si es modo vuelo, abrir Google Flights
        if g_mode == "flying":
            url = f"https://www.google.com/flights?q={urllib.parse.quote(destination)}"
        
        webbrowser.open(url)
        return f"🗺️ Abriendo ruta de {origin} a {destination} en modo {mode}."
    
    # ─── EARTH ──────────────────────────────────────────────────────
    elif action == "earth":
        query = parameters.get("query", "")
        lat = parameters.get("lat", "")
        lng = parameters.get("lng", "")
        alt = parameters.get("altitude", "1000") # meters
        heading = parameters.get("heading", "0")
        tilt = parameters.get("tilt", "60")
        
        if lat and lng:
            url = f"https://earth.google.com/web/@{lat},{lng},{alt}a,{heading}h,{tilt}t"
            webbrowser.open(url)
            return f"🌍 Abriendo Google Earth en las coordenadas {lat}, {lng}."
        elif query:
            url = f"https://earth.google.com/web/search/{urllib.parse.quote(query)}"
            webbrowser.open(url)
            return f"🌍 Abriendo Google Earth y buscando '{query}'."
        else:
            return "❌ Por favor, especifica qué buscar en Google Earth o provee coordenadas."
    
    # ─── PLACE ──────────────────────────────────────────────────────
    elif action == "place":
        place_id = parameters.get("place_id", "")
        query = parameters.get("query", "")
        
        if place_id:
            # Usar Place ID directamente
            url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        elif query:
            # Buscar por nombre
            url = f"https://www.google.com/maps/place/{urllib.parse.quote(query)}/"
        else:
            return "❌ Por favor, especifica un lugar o place_id."
        
        webbrowser.open(url)
        return f"📍 Mostrando detalles de '{query or place_id}' en Google Maps."
    
    # ─── STREET VIEW ──────────────────────────────────────────────
    elif action == "streetview":
        lat = parameters.get("lat", "")
        lng = parameters.get("lng", "")
        query = parameters.get("query", "")
        heading = parameters.get("heading", 0)  # 0-360 grados
        pitch = parameters.get("pitch", 0)  # -90 a 90 grados
        
        if lat and lng:
            # Usar coordenadas
            url = f"https://www.google.com/maps/@?api=1&map_action=streetview&parameters={lat},{lng}&heading={heading}&pitch={pitch}"
        elif query:
            # Buscar lugar
            url = f"https://www.google.com/maps/@?api=1&map_action=streetview&q={urllib.parse.quote(query)}"
        else:
            return "❌ Por favor, especifica coordenadas o un lugar para Street View."
        
        webbrowser.open(url)
        return f"📸 Abriendo Street View en {query or f'{lat}, {lng}'}."
    
    # ─── NEARBY ────────────────────────────────────────────────────
    elif action == "nearby":
        query = parameters.get("query", "restaurantes")
        lat = parameters.get("lat", "")
        lng = parameters.get("lng", "")
        radius = parameters.get("radius", 1000)  # metros
        # No usar location= como parámetro para evitar error
        # Simplemente usar el formato de búsqueda

        if lat and lng:
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/@{lat},{lng},{radius}m"
        else:
            # Buscar sin coordenadas específicas
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/"
        
        webbrowser.open(url)
        return f"📍 Buscando '{query}' cerca de tu ubicación."
    
    # ─── COORDINATES ──────────────────────────────────────────────
    elif action == "coordinates":
        lat = parameters.get("lat", "")
        lng = parameters.get("lng", "")
        zoom = parameters.get("zoom", 15)
        
        if not lat or not lng:
            return "❌ Por favor, especifica latitud y longitud."
        
        try:
            # Validar que son números
            float(lat)
            float(lng)
            url = f"https://www.google.com/maps/@{lat},{lng},{zoom}z"
            webbrowser.open(url)
            return f"📍 Navegando a coordenadas {lat}, {lng} (zoom {zoom})."
        except ValueError:
            return "❌ Las coordenadas deben ser números válidos."
    
    # ─── SHARE ─────────────────────────────────────────────────────
    elif action == "share":
        lat = parameters.get("lat", "")
        lng = parameters.get("lng", "")
        query = parameters.get("query", "")
        
        if lat and lng:
            # Compartir ubicación por coordenadas
            url = f"https://www.google.com/maps/@{lat},{lng},15z"
        elif query:
            # Compartir búsqueda de lugar
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
        else:
            return "❌ Por favor, especifica qué compartir."
        
        webbrowser.open(url)
        return f"🔗 Compartiendo ubicación: {url}"
    
    # ─── WHATS NEARBY ─────────────────────────────────────────────
    elif action == "whats_nearby":
        place = parameters.get("place", "")
        category = parameters.get("category", "")
        
        if not place:
            return "❌ Por favor, especifica un lugar de referencia."
        
        if category:
            search_query = f"{category} cerca de {place}"
        else:
            search_query = f"qué hay cerca de {place}"
        
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}/"
        webbrowser.open(url)
        return f"🔍 Buscando '{category or 'lugares'}' cerca de {place}."
    
    # ─── TIMELINE ──────────────────────────────────────────────────
    elif action == "timeline":
        url = "https://www.google.com/maps/timeline"
        webbrowser.open(url)
        return "⏰ Abriendo tu línea de tiempo de Google Maps."
    
    # ─── CONTRIBUTIONS ────────────────────────────────────────────
    elif action == "contributions":
        url = "https://www.google.com/maps/contrib"
        webbrowser.open(url)
        return "⭐ Abriendo tus contribuciones en Google Maps."
    
    # ─── OFFLINE MAPS ─────────────────────────────────────────────
    elif action == "offline_maps":
        url = "https://www.google.com/maps/offline"
        webbrowser.open(url)
        return "📥 Abriendo mapas offline de Google Maps."
    
    # ─── SAVED PLACES ─────────────────────────────────────────────
    elif action == "saved":
        url = "https://www.google.com/maps/saved"
        webbrowser.open(url)
        return "⭐ Abriendo tus lugares guardados."
    
    # ─── COMANDO NO RECONOCIDO ────────────────────────────────────
    else:
        return f"❌ Comando '{action}' no reconocido. Acciones disponibles: search, directions, earth, place, streetview, nearby, coordinates, share, whats_nearby, timeline, contributions, offline_maps, saved"


