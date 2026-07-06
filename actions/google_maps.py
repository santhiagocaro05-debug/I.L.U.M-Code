"""
Nexus Maps — v2.0
==================
Integración avanzada con Google Maps / Google Earth / Waze / Bing Maps.

Arquitectura
------------
Se reemplazó el bloque if/elif original por un DESPACHADOR de acciones
(`_HANDLERS`). Cada acción es una función independiente `_action_xxx(parameters,
data)` donde `data` es el estado persistente local (favoritos, rutas
favoritas e historial), guardado en `~/.nexus_maps_data.json`.

El punto de entrada público sigue siendo idéntico al original:

    google_maps(parameters: dict, player=None) -> str

por lo que cualquier código que ya invoque `google_maps(...)` sigue
funcionando sin cambios.

Servicios externos usados (todos gratuitos, sin API key)
----------------------------------------------------------
- ip-api.com          -> ubicación aproximada por IP (current_location)
- nominatim (OSM)     -> geocodificación de direcciones/lugares
- router.project-osrm.org -> distancia y tiempo real de una ruta
- open-meteo.com      -> clima actual

Mapeo de las 25 ideas originales -> implementación
----------------------------------------------------
 1. Ubicación actual del dispositivo      -> get_current_location() + "current_location"
 2. Elegir app (waze/bing/google/browser) -> parámetro "app" en directions/roundtrip
 3. Buscar negocios por categoría          -> action="business"
 4. Abrir reseñas de un lugar              -> action="reviews"
 5. Compartir ruta (no solo ubicación)     -> action="share_route"
 6. Distancia entre 2 puntos               -> action="distance"
 7. Tiempo estimado sin abrir Maps         -> action="eta"
 8. Vista satélite/terreno/tráfico/transit -> parámetro "view" en search/directions
 9. Tráfico en tiempo real                 -> action="traffic"
10. Clima de un lugar                      -> action="weather"
11. Favoritos (casa, trabajo, etc.)        -> action="favorite_add/list/remove"
12. Historial de búsquedas/rutas           -> action="history"
13. Ruta ida y vuelta                      -> action="roundtrip"
14. Varias paradas                         -> parámetro "waypoints" en directions
15. Street View directo                    -> action="streetview" (ya existía)
16. Búsqueda por categoría con filtros     -> action="business" (rating/open_now/radio)
17. Pantalla dividida mapa/chat            -> fuera de alcance: es UI, no backend
18. Comandos naturales -> JSON             -> lo resuelve el LLM antes de llamar aquí
19. Navegación por voz (TTS)               -> fuera de alcance: es capa de audio, no Maps
20. Rutas favoritas con nombre             -> action="favorite_route_add/use"
21. Integración con Work Mode              -> action="work_mode"
22. Integración con calendario             -> action="calendar_check" (gancho/stub, requiere OAuth)
23. Estacionamientos (parking)             -> action="parking"
24. Gasolineras                            -> action="gas_station"
25. Estaciones de carga EV                 -> action="ev_charging"
"""

import webbrowser
import urllib.parse
import urllib.request
import json
import os
import math
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime


# ═════════════════════════════════════════════════════════════════════════
# ALMACENAMIENTO LOCAL (favoritos, rutas favoritas, historial)
# ═════════════════════════════════════════════════════════════════════════

DATA_FILE = os.path.expanduser("~/.nexus_maps_data.json")

DEFAULT_DATA = {
    "favorites": {},        # {"casa": {"address": "...", "lat":.., "lng":..}}
    "favorite_routes": {},  # {"casa_trabajo": {"origin":.., "destination":.., "mode":..}}
    "history": {"searches": [], "routes": []},
}


def _load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return json.loads(json.dumps(DEFAULT_DATA))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, value in DEFAULT_DATA.items():
            data.setdefault(key, value)
        return data
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULT_DATA))


def _save_data(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _add_history(kind: str, entry: Any, data: dict) -> None:
    history = data.setdefault("history", {"searches": [], "routes": []})
    bucket = history.setdefault(kind, [])
    bucket.insert(0, {"entry": entry, "timestamp": datetime.now().isoformat(timespec="seconds")})
    del bucket[20:]  # conserva solo los últimos 20 registros


# ═════════════════════════════════════════════════════════════════════════
# SERVICIOS EXTERNOS GRATUITOS (sin API key)
# ═════════════════════════════════════════════════════════════════════════

def _http_get_json(url: str, headers: Optional[dict] = None, timeout: int = 6) -> Optional[Any]:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "NexusMaps/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def get_current_location() -> Optional[Dict[str, Any]]:
    """Ubicación aproximada del dispositivo vía IP (sin GPS, sin API key)."""
    info = _http_get_json("http://ip-api.com/json/")
    if not info or info.get("status") != "success":
        return None
    return {
        "lat": info.get("lat"),
        "lng": info.get("lon"),
        "city": info.get("city"),
        "region": info.get("regionName"),
        "country": info.get("country"),
    }


def geocode(place: str) -> Optional[Tuple[float, float]]:
    """Convierte un nombre de lugar en coordenadas usando Nominatim (OpenStreetMap)."""
    if not place:
        return None
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(place)}&format=json&limit=1"
    result = _http_get_json(url, headers={"User-Agent": "NexusMaps/2.0 (contacto@nexus.local)"})
    if not result:
        return None
    try:
        return (float(result[0]["lat"]), float(result[0]["lon"]))
    except (IndexError, KeyError, ValueError, TypeError):
        return None


_OSRM_PROFILES = {"car": "driving", "walk": "foot", "bike": "bike", "transit": "driving"}


def get_route_info(origin_coords: Tuple[float, float], dest_coords: Tuple[float, float],
                    mode: str = "car") -> Optional[Dict[str, Any]]:
    """Distancia y duración reales de una ruta usando el servidor demo de OSRM (sin API key)."""
    profile = _OSRM_PROFILES.get(mode.lower(), "driving")
    lat1, lng1 = origin_coords
    lat2, lng2 = dest_coords
    url = (f"https://router.project-osrm.org/route/v1/{profile}/"
           f"{lng1},{lat1};{lng2},{lat2}?overview=false")
    result = _http_get_json(url)
    if not result or result.get("code") != "Ok":
        return None
    try:
        route = result["routes"][0]
        return {
            "distance_km": round(route["distance"] / 1000, 2),
            "duration_min": round(route["duration"] / 60, 1),
        }
    except (KeyError, IndexError):
        return None


def get_weather(lat: float, lng: float) -> Optional[Dict[str, Any]]:
    """Clima actual vía Open-Meteo (sin API key)."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current_weather=true"
    result = _http_get_json(url)
    if not result or "current_weather" not in result:
        return None
    cw = result["current_weather"]
    return {"temperature": cw.get("temperature"), "windspeed": cw.get("windspeed")}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia en línea recta entre dos coordenadas (fallback si OSRM falla)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ═════════════════════════════════════════════════════════════════════════
# UTILIDADES INTERNAS
# ═════════════════════════════════════════════════════════════════════════

MODE_MAP = {"car": "driving", "walk": "walking", "bike": "bicycling", "transit": "transit"}

CATEGORY_MAP = {
    "cafeterías": "cafe", "cafeterias": "cafe", "café": "cafe", "cafe": "cafe",
    "hoteles": "lodging", "hotel": "lodging",
    "hospitales": "hospital", "hospital": "hospital",
    "gasolineras": "gas station", "gasolinera": "gas station",
    "farmacias": "pharmacy", "farmacia": "pharmacy",
    "restaurantes": "restaurant", "restaurante": "restaurant",
    "supermercados": "supermarket", "supermercado": "supermarket",
    "bancos": "bank", "banco": "bank",
    "parqueaderos": "parking", "parking": "parking", "estacionamiento": "parking",
    "estaciones de carga": "ev charging station",
}

_NEARBY_ME_ALIASES = ("current_location", "mi ubicación", "mi ubicacion", "aquí", "aqui")


def _open(url: str) -> None:
    webbrowser.open(url)


def _resolve_location_param(value: str, data: dict) -> Tuple[str, Optional[Tuple[float, float]]]:
    """
    Convierte un valor de ubicación en (texto_legible, coordenadas_opcionales).
    Soporta: 'current_location', nombres guardados en favoritos, o texto libre.
    """
    if not value:
        return value, None

    key = value.strip().lower()

    if key in _NEARBY_ME_ALIASES:
        loc = get_current_location()
        if loc:
            return f"{loc['lat']},{loc['lng']}", (loc["lat"], loc["lng"])
        return "mi ubicación actual", None

    fav = data.get("favorites", {}).get(key)
    if fav:
        coords = None
        if fav.get("lat") is not None and fav.get("lng") is not None:
            coords = (fav["lat"], fav["lng"])
        return fav.get("address", value), coords

    return value, None


def _build_directions_url(app: str, origin: str, destination: str, mode: str,
                           dest_coords: Optional[Tuple[float, float]] = None) -> str:
    app = (app or "google_maps").lower()
    g_mode = MODE_MAP.get(mode.lower(), "driving")

    if app == "waze":
        if dest_coords:
            lat, lng = dest_coords
            return f"https://waze.com/ul?ll={lat},{lng}&navigate=yes"
        return f"https://waze.com/ul?q={urllib.parse.quote(destination)}&navigate=yes"

    if app == "bing_maps":
        return (f"https://www.bing.com/maps/directions?rtp=adr.{urllib.parse.quote(origin)}"
                f"~adr.{urllib.parse.quote(destination)}")

    # google_maps / browser (por defecto)
    return (f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin)}"
            f"&destination={urllib.parse.quote(destination)}&travelmode={g_mode}")


def _try_open_app(app_name: str) -> bool:
    """
    Intenta abrir apps web comunes. Apps de escritorio nativas (VS Code, Spotify
    de escritorio, etc.) requerirían integración con el SO (subprocess.Popen),
    fuera del alcance de este módulo enfocado en mapas/navegador.
    """
    web_apps = {
        "spotify": "https://open.spotify.com",
        "chatgpt": "https://chat.openai.com",
        "chrome": "https://www.google.com",
    }
    if app_name.lower() in web_apps:
        webbrowser.open(web_apps[app_name.lower()])
        return True
    return False


# ═════════════════════════════════════════════════════════════════════════
# HANDLERS — ACCIONES ORIGINALES (comportamiento preservado, sin dañar nada)
# ═════════════════════════════════════════════════════════════════════════

def _action_search(parameters: dict, data: dict) -> str:
    query = parameters.get("query") or parameters.get("destination", "")
    if not query:
        return "❌ Por favor, especifica qué buscar en Google Maps."

    place_type = parameters.get("type", "")
    search_query = f"{place_type} en {query}" if place_type else query
    view = parameters.get("view", "")

    url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}/"
    if view:
        url += f"?layer={view}"

    _open(url)
    _add_history("searches", search_query, data)
    return f"🔍 Buscando '{search_query}' en Google Maps."


def _action_directions(parameters: dict, data: dict) -> str:
    destination_raw = parameters.get("destination", "")
    if not destination_raw:
        return "❌ Por favor, especifica un destino para la ruta."

    origin_raw = parameters.get("origin") or "current_location"
    mode = parameters.get("mode", "car")
    app = parameters.get("app", "google_maps")
    avoid = parameters.get("avoid", "")
    waypoints = parameters.get("waypoints", "")
    alternatives = parameters.get("alternatives", False)

    origin_text, origin_coords = _resolve_location_param(origin_raw, data)
    dest_text, dest_coords = _resolve_location_param(destination_raw, data)

    if mode.lower() == "flight":
        url = f"https://www.google.com/flights?q={urllib.parse.quote(dest_text)}"
        _open(url)
        return f"✈️ Abriendo Google Flights hacia {dest_text}."

    url = _build_directions_url(app, origin_text, dest_text, mode, dest_coords)

    if app.lower() in ("google_maps", "browser", ""):
        if avoid:
            url += f"&avoid={avoid}"
        if waypoints:
            url += f"&waypoints={urllib.parse.quote(waypoints)}"
        if alternatives:
            url += "&alternatives=true"
        if parameters.get("view") == "traffic":
            url += "&layer=traffic"

    _open(url)
    _add_history("routes", {"origin": origin_text, "destination": dest_text, "mode": mode}, data)

    eta_note = ""
    if origin_coords and dest_coords:
        route_info = get_route_info(origin_coords, dest_coords, mode)
        if route_info:
            eta_note = f" (~{route_info['distance_km']} km, ~{route_info['duration_min']} min)"

    return f"🗺️ Abriendo ruta de {origin_text} a {dest_text} en modo {mode} vía {app}.{eta_note}"


def _action_earth(parameters: dict, data: dict) -> str:
    query = parameters.get("query", "")
    lat = parameters.get("lat", "")
    lng = parameters.get("lng", "")
    alt = parameters.get("altitude", "1000")
    heading = parameters.get("heading", "0")
    tilt = parameters.get("tilt", "60")

    if lat and lng:
        url = f"https://earth.google.com/web/@{lat},{lng},{alt}a,{heading}h,{tilt}t"
        _open(url)
        return f"🌍 Abriendo Google Earth en las coordenadas {lat}, {lng}."
    elif query:
        url = f"https://earth.google.com/web/search/{urllib.parse.quote(query)}"
        _open(url)
        return f"🌍 Abriendo Google Earth y buscando '{query}'."
    return "❌ Por favor, especifica qué buscar en Google Earth o provee coordenadas."


def _action_place(parameters: dict, data: dict) -> str:
    place_id = parameters.get("place_id", "")
    query = parameters.get("query", "")
    show_reviews = parameters.get("reviews", False)

    if place_id:
        url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    elif query:
        url = f"https://www.google.com/maps/place/{urllib.parse.quote(query)}/"
    else:
        return "❌ Por favor, especifica un lugar o place_id."

    _open(url)
    label = query or place_id
    if show_reviews:
        return f"⭐ Mostrando reseñas de '{label}' en Google Maps."
    return f"📍 Mostrando detalles de '{label}' en Google Maps."


def _action_reviews(parameters: dict, data: dict) -> str:
    merged = dict(parameters)
    merged["reviews"] = True
    return _action_place(merged, data)


def _action_streetview(parameters: dict, data: dict) -> str:
    lat = parameters.get("lat", "")
    lng = parameters.get("lng", "")
    query = parameters.get("query", "")
    heading = parameters.get("heading", 0)
    pitch = parameters.get("pitch", 0)

    if lat and lng:
        url = f"https://www.google.com/maps/@?api=1&map_action=streetview&parameters={lat},{lng}&heading={heading}&pitch={pitch}"
    elif query:
        url = f"https://www.google.com/maps/@?api=1&map_action=streetview&q={urllib.parse.quote(query)}"
    else:
        return "❌ Por favor, especifica coordenadas o un lugar para Street View."

    _open(url)
    return f"📸 Abriendo Street View en {query or f'{lat}, {lng}'}."


def _action_nearby(parameters: dict, data: dict) -> str:
    query = parameters.get("query", "restaurantes")
    lat = parameters.get("lat", "")
    lng = parameters.get("lng", "")
    radius = parameters.get("radius", 1000)

    if not lat or not lng:
        loc = get_current_location()
        if loc:
            lat, lng = loc["lat"], loc["lng"]

    if lat and lng:
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/@{lat},{lng},{radius}m"
    else:
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/"

    _open(url)
    return f"📍 Buscando '{query}' cerca de tu ubicación."


def _action_coordinates(parameters: dict, data: dict) -> str:
    lat = parameters.get("lat", "")
    lng = parameters.get("lng", "")
    zoom = parameters.get("zoom", 15)

    if not lat or not lng:
        return "❌ Por favor, especifica latitud y longitud."
    try:
        float(lat)
        float(lng)
    except ValueError:
        return "❌ Las coordenadas deben ser números válidos."

    url = f"https://www.google.com/maps/@{lat},{lng},{zoom}z"
    _open(url)
    return f"📍 Navegando a coordenadas {lat}, {lng} (zoom {zoom})."


def _action_share(parameters: dict, data: dict) -> str:
    lat = parameters.get("lat", "")
    lng = parameters.get("lng", "")
    query = parameters.get("query", "")

    if lat and lng:
        url = f"https://www.google.com/maps/@{lat},{lng},15z"
    elif query:
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
    else:
        return "❌ Por favor, especifica qué compartir."

    _open(url)
    return f"🔗 Compartiendo ubicación: {url}"


def _action_whats_nearby(parameters: dict, data: dict) -> str:
    place = parameters.get("place", "")
    category = parameters.get("category", "")
    if not place:
        return "❌ Por favor, especifica un lugar de referencia."

    search_query = f"{category} cerca de {place}" if category else f"qué hay cerca de {place}"
    url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}/"
    _open(url)
    return f"🔍 Buscando '{category or 'lugares'}' cerca de {place}."


def _action_timeline(parameters: dict, data: dict) -> str:
    _open("https://www.google.com/maps/timeline")
    return "⏰ Abriendo tu línea de tiempo de Google Maps."


def _action_contributions(parameters: dict, data: dict) -> str:
    _open("https://www.google.com/maps/contrib")
    return "⭐ Abriendo tus contribuciones en Google Maps."


def _action_offline_maps(parameters: dict, data: dict) -> str:
    _open("https://www.google.com/maps/offline")
    return "📥 Abriendo mapas offline de Google Maps."


def _action_saved(parameters: dict, data: dict) -> str:
    _open("https://www.google.com/maps/saved")
    return "⭐ Abriendo tus lugares guardados."


# ═════════════════════════════════════════════════════════════════════════
# HANDLERS — ACCIONES NUEVAS (las 25 ideas)
# ═════════════════════════════════════════════════════════════════════════

def _action_share_route(parameters: dict, data: dict) -> str:
    destination_raw = parameters.get("destination", "")
    if not destination_raw:
        return "❌ Por favor, especifica un destino para compartir la ruta."

    origin_raw = parameters.get("origin") or "current_location"
    mode = parameters.get("mode", "car")
    origin_text, _ = _resolve_location_param(origin_raw, data)
    dest_text, _ = _resolve_location_param(destination_raw, data)
    g_mode = MODE_MAP.get(mode.lower(), "driving")

    url = (f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin_text)}"
           f"&destination={urllib.parse.quote(dest_text)}&travelmode={g_mode}")
    return f"🔗 Enlace de la ruta para compartir ({origin_text} → {dest_text}):\n{url}"


def _action_business(parameters: dict, data: dict) -> str:
    category = parameters.get("category", "")
    place = parameters.get("place") or parameters.get("near", "")
    min_rating = parameters.get("min_rating", "")
    open_now = parameters.get("open_now", False)
    max_distance_km = parameters.get("max_distance_km", "")

    if not category:
        return "❌ Por favor, especifica qué tipo de negocio buscar (cafeterías, hoteles, etc.)."

    normalized = CATEGORY_MAP.get(category.lower(), category)
    terms = [normalized]
    if min_rating:
        terms.append(f"{min_rating}+ estrellas")
    if open_now:
        terms.append("abierto ahora")
    if max_distance_km:
        terms.append(f"a menos de {max_distance_km} km")

    search_query = " ".join(terms)
    if place:
        search_query += f" cerca de {place}"
    else:
        loc = get_current_location()
        if loc and loc.get("city"):
            search_query += f" cerca de {loc['city']}"

    url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}/"
    _open(url)
    _add_history("searches", search_query, data)
    return f"🏪 Buscando '{search_query}' en Google Maps."


def _action_distance(parameters: dict, data: dict) -> str:
    destination_raw = parameters.get("destination", "")
    if not destination_raw:
        return "❌ Por favor, especifica un destino para calcular la distancia."

    origin_raw = parameters.get("origin") or "current_location"
    mode = parameters.get("mode", "car")

    origin_text, origin_coords = _resolve_location_param(origin_raw, data)
    origin_coords = origin_coords or geocode(origin_text)
    dest_text, dest_coords = _resolve_location_param(destination_raw, data)
    dest_coords = dest_coords or geocode(dest_text)

    if not origin_coords or not dest_coords:
        return "❌ No pude ubicar una de las dos direcciones para calcular la distancia."

    route_info = get_route_info(origin_coords, dest_coords, mode)
    if route_info:
        return (f"📏 Distancia de {origin_text} a {dest_text}: "
                f"~{route_info['distance_km']} km, ~{route_info['duration_min']} min en {mode}.")

    straight_km = round(haversine_km(*origin_coords, *dest_coords), 2)
    return (f"📏 Distancia en línea recta de {origin_text} a {dest_text}: ~{straight_km} km "
            f"(no se pudo calcular la ruta real por carretera en este momento).")


def _action_eta(parameters: dict, data: dict) -> str:
    destination_raw = parameters.get("destination", "")
    if not destination_raw:
        return "❌ Por favor, especifica un destino."

    origin_raw = parameters.get("origin") or "current_location"
    mode = parameters.get("mode", "car")

    origin_text, origin_coords = _resolve_location_param(origin_raw, data)
    origin_coords = origin_coords or geocode(origin_text)
    dest_text, dest_coords = _resolve_location_param(destination_raw, data)
    dest_coords = dest_coords or geocode(dest_text)

    if not origin_coords or not dest_coords:
        return "❌ No pude calcular el tiempo estimado, faltan coordenadas válidas."

    route_info = get_route_info(origin_coords, dest_coords, mode)
    if not route_info:
        return "❌ No pude calcular el tiempo estimado en este momento."

    mode_label = {"car": "en carro", "walk": "caminando", "bike": "en bici",
                  "transit": "en transporte público"}.get(mode.lower(), mode)
    return (f"⏱️ Tiempo estimado {mode_label} a {dest_text}: "
            f"~{route_info['duration_min']} minutos ({route_info['distance_km']} km).")


def _action_traffic(parameters: dict, data: dict) -> str:
    place = parameters.get("place") or parameters.get("query", "")
    if place:
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(place)}/?layer=traffic"
        _open(url)
        return f"🚦 Mostrando tráfico en tiempo real cerca de '{place}'."

    loc = get_current_location()
    if loc:
        url = f"https://www.google.com/maps/@{loc['lat']},{loc['lng']},14z/data=!5m1!1e1"
        _open(url)
        return "🚦 Mostrando tráfico en tiempo real cerca de tu ubicación."

    _open("https://www.google.com/maps/@?layer=traffic")
    return "🚦 Abriendo capa de tráfico en Google Maps."


def _action_weather(parameters: dict, data: dict) -> str:
    place = parameters.get("place") or parameters.get("query", "")
    if place:
        coords = geocode(place)
        label = place
    else:
        loc = get_current_location()
        coords = (loc["lat"], loc["lng"]) if loc else None
        label = loc["city"] if loc else "tu ubicación"

    if not coords:
        return f"❌ No pude obtener las coordenadas de '{label}' para consultar el clima."

    weather = get_weather(*coords)
    if not weather:
        return f"❌ No pude obtener el clima de {label} en este momento."

    return f"🌤️ Clima en {label}: {weather['temperature']}°C, viento {weather['windspeed']} km/h."


def _action_favorite_add(parameters: dict, data: dict) -> str:
    name = parameters.get("name", "")
    address = parameters.get("address") or parameters.get("query", "")
    if not name or not address:
        return "❌ Por favor, especifica un nombre (ej. 'casa') y una dirección."

    coords = geocode(address)
    entry = {"address": address}
    if coords:
        entry["lat"], entry["lng"] = coords

    data.setdefault("favorites", {})[name.strip().lower()] = entry
    return f"⭐ Guardado '{name}' como favorito ({address})."


def _action_favorite_list(parameters: dict, data: dict) -> str:
    favorites = data.get("favorites", {})
    if not favorites:
        return "📭 No tienes lugares favoritos guardados todavía."
    lines = [f"• {name.title()}: {info.get('address', '')}" for name, info in favorites.items()]
    return "⭐ Tus lugares favoritos:\n" + "\n".join(lines)


def _action_favorite_remove(parameters: dict, data: dict) -> str:
    name = parameters.get("name", "").strip().lower()
    if name in data.get("favorites", {}):
        del data["favorites"][name]
        return f"🗑️ Favorito '{name}' eliminado."
    return f"❌ No encontré un favorito llamado '{name}'."


def _action_favorite_route_add(parameters: dict, data: dict) -> str:
    name = parameters.get("name", "")
    destination = parameters.get("destination", "")
    if not name or not destination:
        return "❌ Por favor, especifica un nombre y un destino para la ruta favorita."

    data.setdefault("favorite_routes", {})[name.strip().lower()] = {
        "origin": parameters.get("origin", "current_location"),
        "destination": destination,
        "mode": parameters.get("mode", "car"),
    }
    return f"⭐ Ruta favorita '{name}' guardada."


def _action_favorite_route_use(parameters: dict, data: dict) -> str:
    name = parameters.get("name", "").strip().lower()
    route = data.get("favorite_routes", {}).get(name)
    if not route:
        return f"❌ No encontré una ruta favorita llamada '{name}'."

    merged = dict(parameters)
    merged.update(route)  # la ruta guardada tiene prioridad sobre origin/destination/mode
    return _action_directions(merged, data)


def _action_history(parameters: dict, data: dict) -> str:
    if parameters.get("clear"):
        data["history"] = {"searches": [], "routes": []}
        return "🗑️ Historial borrado."

    kind = parameters.get("type", "all")
    history = data.get("history", {"searches": [], "routes": []})
    lines: List[str] = []

    if kind in ("all", "searches"):
        lines.append("🔎 Últimas búsquedas:")
        entries = [f"  • {h['entry']}" for h in history.get("searches", [])[:5]]
        lines += entries or ["  (vacío)"]

    if kind in ("all", "routes"):
        lines.append("🗺️ Últimas rutas:")
        route_entries = history.get("routes", [])[:5]
        if route_entries:
            for h in route_entries:
                r = h["entry"]
                lines.append(f"  • {r.get('origin')} → {r.get('destination')}")
        else:
            lines.append("  (vacío)")

    return "\n".join(lines)


def _action_roundtrip(parameters: dict, data: dict) -> str:
    destination = parameters.get("destination", "")
    if not destination:
        return "❌ Por favor, especifica un destino para el viaje de ida y vuelta."

    origin_raw = parameters.get("origin") or "current_location"
    mode = parameters.get("mode", "car")
    origin_text, _ = _resolve_location_param(origin_raw, data)
    g_mode = MODE_MAP.get(mode.lower(), "driving")

    url = (f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin_text)}"
           f"&destination={urllib.parse.quote(origin_text)}"
           f"&waypoints={urllib.parse.quote(destination)}&travelmode={g_mode}")
    _open(url)
    return f"🔁 Abriendo ruta de ida y vuelta: {origin_text} → {destination} → {origin_text}."


def _action_parking(parameters: dict, data: dict) -> str:
    merged = dict(parameters)
    merged["category"] = "parqueaderos" + (" gratis" if parameters.get("free") else "")
    return _action_business(merged, data)


def _action_gas_station(parameters: dict, data: dict) -> str:
    merged = dict(parameters)
    merged["category"] = "gasolineras" + (" más barata" if parameters.get("cheapest") else "")
    return _action_business(merged, data)


def _action_ev_charging(parameters: dict, data: dict) -> str:
    merged = dict(parameters)
    category = "estaciones de carga eléctrica"
    if parameters.get("brand"):
        category = f"{parameters['brand']} {category}"
    if parameters.get("connector"):
        category += f" conector {parameters['connector']}"
    merged["category"] = category
    return _action_business(merged, data)


def _action_work_mode(parameters: dict, data: dict) -> str:
    apps_to_open = parameters.get("apps", [])
    destination = parameters.get("destination") or data.get("favorites", {}).get("trabajo", {}).get("address", "")
    messages = []

    for app_name in apps_to_open:
        opened = _try_open_app(app_name)
        messages.append(f"✅ {app_name} abierto." if opened else f"⚠️ No pude abrir {app_name} automáticamente.")

    if destination:
        messages.append(_action_directions(
            {"destination": destination, "app": parameters.get("map_app", "google_maps")}, data))
    else:
        messages.append("⚠️ No hay una dirección de 'trabajo' guardada. Usa action='favorite_add' primero.")

    return "🧩 Modo Trabajo activado:\n" + "\n".join(messages)


def _action_calendar_check(parameters: dict, data: dict) -> str:
    """
    Gancho de integración con calendario (idea #22). Conectar un calendario real
    (Google Calendar/Outlook) requiere credenciales OAuth propias del usuario,
    lo cual está fuera del alcance de este módulo de mapas. Esta acción queda
    expuesta para que otro componente de Nexus la complete.
    """
    return ("📅 La integración con calendario requiere conectar una cuenta "
            "(Google Calendar/Outlook) con credenciales OAuth propias. Este módulo "
            "solo expone el punto de entrada (action='calendar_check') para que "
            "otro componente de Nexus lo complete y luego invoque "
            "action='directions' automáticamente antes de cada reunión.")


# ═════════════════════════════════════════════════════════════════════════
# DESPACHADOR
# ═════════════════════════════════════════════════════════════════════════

_HANDLERS = {
    # originales
    "search": _action_search,
    "directions": _action_directions,
    "earth": _action_earth,
    "place": _action_place,
    "streetview": _action_streetview,
    "nearby": _action_nearby,
    "coordinates": _action_coordinates,
    "share": _action_share,
    "whats_nearby": _action_whats_nearby,
    "timeline": _action_timeline,
    "contributions": _action_contributions,
    "offline_maps": _action_offline_maps,
    "saved": _action_saved,
    # nuevas
    "reviews": _action_reviews,
    "share_route": _action_share_route,
    "business": _action_business,
    "distance": _action_distance,
    "eta": _action_eta,
    "traffic": _action_traffic,
    "weather": _action_weather,
    "favorite_add": _action_favorite_add,
    "favorite_list": _action_favorite_list,
    "favorite_remove": _action_favorite_remove,
    "favorite_route_add": _action_favorite_route_add,
    "favorite_route_use": _action_favorite_route_use,
    "history": _action_history,
    "roundtrip": _action_roundtrip,
    "parking": _action_parking,
    "gas_station": _action_gas_station,
    "ev_charging": _action_ev_charging,
    "work_mode": _action_work_mode,
    "calendar_check": _action_calendar_check,
}


def google_maps(parameters: dict, player=None) -> str:
    """
    Abre Google Maps/Earth/Waze/Bing Maps o consulta datos relacionados.
    Punto de entrada único — misma firma que la versión original, por lo que
    es 100% compatible con el código que ya la invoca.
    """
    action = parameters.get("action", "search")
    data = _load_data()
    handler = _HANDLERS.get(action)

    if not handler:
        disponibles = ", ".join(sorted(_HANDLERS.keys()))
        return f"❌ Comando '{action}' no reconocido. Acciones disponibles: {disponibles}"

    try:
        result = handler(parameters, data)
    except Exception as exc:
        return f"❌ Error ejecutando la acción '{action}': {exc}"

    _save_data(data)
    return result