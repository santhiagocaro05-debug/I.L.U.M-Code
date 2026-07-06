"""
Flight Finder Module
====================
Buscador de vuelos con múltiples fuentes: Google Flights, Skyscanner, Kiwi, etc.
Soporta búsqueda por ciudad, fechas, pasajeros, clase y alertas de precio.
"""

import json
import re
import time
import webbrowser
import importlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import threading

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

search = None
try:
    _googlesearch = importlib.import_module("googlesearch")
    search = getattr(_googlesearch, "search", None)
except ImportError:
    search = None

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────
CONFIG_DIR = Path("config")
FLIGHTS_CONFIG_PATH = CONFIG_DIR / "flights_config.json"
FLIGHTS_CACHE_DIR = CONFIG_DIR / "flights_cache"
FLIGHTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─── BASE DE DATOS DE CIUDADES ───────────────────────────────────────────
CITIES_DATABASE = {
    # America Latina
    "lima": {"code": "LIM", "country": "Perú", "timezone": "America/Lima"},
    "bogota": {"code": "BOG", "country": "Colombia", "timezone": "America/Bogota"},
    "medellin": {"code": "MDE", "country": "Colombia", "timezone": "America/Bogota"},
    "buenos aires": {"code": "EZE", "country": "Argentina", "timezone": "America/Argentina/Buenos_Aires"},
    "santiago": {"code": "SCL", "country": "Chile", "timezone": "America/Santiago"},
    "sao paulo": {"code": "GRU", "country": "Brasil", "timezone": "America/Sao_Paulo"},
    "rio de janeiro": {"code": "GIG", "country": "Brasil", "timezone": "America/Sao_Paulo"},
    "mexico city": {"code": "MEX", "country": "México", "timezone": "America/Mexico_City"},
    "cancun": {"code": "CUN", "country": "México", "timezone": "America/Cancun"},
    "panama": {"code": "PTY", "country": "Panamá", "timezone": "America/Panama"},
    "san jose": {"code": "SJO", "country": "Costa Rica", "timezone": "America/Costa_Rica"},
    "quito": {"code": "UIO", "country": "Ecuador", "timezone": "America/Guayaquil"},
    "guayaquil": {"code": "GYE", "country": "Ecuador", "timezone": "America/Guayaquil"},
    "caracas": {"code": "CCS", "country": "Venezuela", "timezone": "America/Caracas"},
    "montevideo": {"code": "MVD", "country": "Uruguay", "timezone": "America/Montevideo"},
    "asuncion": {"code": "ASU", "country": "Paraguay", "timezone": "America/Asuncion"},
    "la paz": {"code": "LPB", "country": "Bolivia", "timezone": "America/La_Paz"},
    "sucre": {"code": "SRE", "country": "Bolivia", "timezone": "America/La_Paz"},
    
    # Europa
    "madrid": {"code": "MAD", "country": "España", "timezone": "Europe/Madrid"},
    "barcelona": {"code": "BCN", "country": "España", "timezone": "Europe/Madrid"},
    "london": {"code": "LHR", "country": "Reino Unido", "timezone": "Europe/London"},
    "paris": {"code": "CDG", "country": "Francia", "timezone": "Europe/Paris"},
    "rome": {"code": "FCO", "country": "Italia", "timezone": "Europe/Rome"},
    "berlin": {"code": "BER", "country": "Alemania", "timezone": "Europe/Berlin"},
    "amsterdam": {"code": "AMS", "country": "Países Bajos", "timezone": "Europe/Amsterdam"},
    
    # USA
    "new york": {"code": "JFK", "country": "USA", "timezone": "America/New_York"},
    "miami": {"code": "MIA", "country": "USA", "timezone": "America/New_York"},
    "los angeles": {"code": "LAX", "country": "USA", "timezone": "America/Los_Angeles"},
    "chicago": {"code": "ORD", "country": "USA", "timezone": "America/Chicago"},
    "houston": {"code": "IAH", "country": "USA", "timezone": "America/Chicago"},
    "orlando": {"code": "MCO", "country": "USA", "timezone": "America/New_York"},
    "las vegas": {"code": "LAS", "country": "USA", "timezone": "America/Los_Angeles"},
    "san francisco": {"code": "SFO", "country": "USA", "timezone": "America/Los_Angeles"},
    "seattle": {"code": "SEA", "country": "USA", "timezone": "America/Los_Angeles"},
    "boston": {"code": "BOS", "country": "USA", "timezone": "America/New_York"},
    "washington": {"code": "IAD", "country": "USA", "timezone": "America/New_York"},
    "dallas": {"code": "DFW", "country": "USA", "timezone": "America/Chicago"},
    "atlanta": {"code": "ATL", "country": "USA", "timezone": "America/New_York"},
    "denver": {"code": "DEN", "country": "USA", "timezone": "America/Denver"},
    "phoenix": {"code": "PHX", "country": "USA", "timezone": "America/Phoenix"},
    
    # Asia
    "tokyo": {"code": "NRT", "country": "Japón", "timezone": "Asia/Tokyo"},
    "seoul": {"code": "ICN", "country": "Corea del Sur", "timezone": "Asia/Seoul"},
    "dubai": {"code": "DXB", "country": "UAE", "timezone": "Asia/Dubai"},
    "singapore": {"code": "SIN", "country": "Singapur", "timezone": "Asia/Singapore"},
}

# ─── GESTOR DE CONFIGURACIÓN ─────────────────────────────────────────────
class FlightsConfig:
    """Gestor de configuración de vuelos."""
    
    def __init__(self):
        self.config = self._load()
    
    def _load(self) -> Dict:
        """Carga la configuración."""
        if FLIGHTS_CONFIG_PATH.exists():
            try:
                return json.loads(FLIGHTS_CONFIG_PATH.read_text(encoding="utf-8"))
            except:
                return {}
        return {
            "preferred_airlines": [],
            "max_stops": 2,
            "max_price": None,
            "currency": "USD",
            "adults": 1,
            "children": 0,
            "infants": 0,
            "cabin_class": "economy",
            "alerts_enabled": True,
            "email_notifications": False
        }
    
    def save(self):
        """Guarda la configuración."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        FLIGHTS_CONFIG_PATH.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def get(self, key: str, default=None):
        """Obtiene un valor de configuración."""
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        """Establece un valor de configuración."""
        self.config[key] = value
        self.save()


# ─── BUSCADOR DE VUELOS ──────────────────────────────────────────────────
class FlightSearcher:
    """Busca vuelos en múltiples fuentes."""
    
    def __init__(self):
        self.config = FlightsConfig()
        self._cache = {}
        self._session = requests.Session() if requests else None
        self._setup_session()
    
    def _setup_session(self):
        """Configura la sesión HTTP."""
        if not self._session:
            return
        
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
        })
    
    def _get_city_code(self, city: str) -> Optional[str]:
        """Obtiene el código IATA de una ciudad."""
        city_lower = city.lower().strip()
        
        # Buscar en la base de datos
        if city_lower in CITIES_DATABASE:
            return CITIES_DATABASE[city_lower]["code"]
        
        # Buscar por coincidencia parcial
        for name, info in CITIES_DATABASE.items():
            if city_lower in name or name in city_lower:
                return info["code"]
        
        # Si es un código IATA (3 letras mayúsculas)
        if re.match(r'^[A-Z]{3}$', city):
            return city.upper()
        
        return None
    
    def _get_city_info(self, city: str) -> Optional[Dict]:
        """Obtiene información de una ciudad."""
        city_lower = city.lower().strip()
        
        if city_lower in CITIES_DATABASE:
            return CITIES_DATABASE[city_lower]
        
        for name, info in CITIES_DATABASE.items():
            if city_lower in name or name in city_lower:
                return info
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parsea una fecha en formato YYYY-MM-DD."""
        try:
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 3:
                    # DD/MM/YYYY o MM/DD/YYYY
                    if len(parts[0]) == 4:
                        return f"{parts[0]}-{parts[1]:02d}-{parts[2]:02d}"
                    else:
                        return f"{parts[2]}-{parts[1]:02d}-{parts[0]:02d}"
            elif "-" in date_str:
                parts = date_str.split("-")
                if len(parts) == 3:
                    if len(parts[0]) == 4:
                        return date_str
                    else:
                        return f"{parts[2]}-{parts[1]:02d}-{parts[0]:02d}"
            
            # Intentar parsear con datetime
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except:
                    continue
            
            return date_str
        except:
            return date_str
    
    def _format_price(self, price: float, currency: str = "USD") -> str:
        """Formatea un precio."""
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "COP": "$",
            "ARS": "$",
            "MXN": "$",
            "PEN": "S/",
        }
        symbol = symbols.get(currency, currency)
        return f"{symbol}{price:,.0f}"
    
    # ─── GOOGLE FLIGHTS ──────────────────────────────────────────────────
    def search_google_flights(self, origin: str, destination: str, date: str,
                              return_date: str = None, passengers: int = 1,
                              cabin: str = "economy") -> List[Dict]:
        """
        Busca vuelos usando Google Flights.
        """
        results = []
        
        try:
            # Construir URL
            origin_code = self._get_city_code(origin)
            dest_code = self._get_city_code(destination)
            
            if not origin_code or not dest_code:
                return results
            
            # URL de Google Flights
            base_url = "https://www.google.com/travel/flights"
            url = f"{base_url}/search?tfs=CBwQAhgCagcIARID{origin_code}EgIIARoLCgIIARID{dest_code}"
            url += f"&tfl=CBwQAhgCagcIARID{dest_code}EgIIARoLCgIIARID{origin_code}"
            
            if date:
                url += f"&departure={date}"
            if return_date:
                url += f"&return={return_date}"
            
            cabin_map = {
                "economy": "c",
                "premium": "d",
                "business": "e",
                "first": "f"
            }
            cabin_code = cabin_map.get(cabin, "c")
            url += f"&cabin={cabin_code}"
            
            if passengers > 1:
                url += f"&adults={passengers}"
            
            # Abrir en navegador
            webbrowser.open(url)
            
            # Intentar obtener datos (simplificado)
            # En producción, usaría scraping con Selenium
            results.append({
                "airline": "Google Flights",
                "price": "Ver en navegador",
                "duration": "N/A",
                "stops": 0,
                "departure": date,
                "arrival": "N/A",
                "currency": "USD",
                "url": url,
                "source": "google_flights"
            })
            
        except Exception as e:
            print(f"[FlightFinder] Error en Google Flights: {e}")
        
        return results
    
    # ─── SKYSCANNER ──────────────────────────────────────────────────────
    def search_skyscanner(self, origin: str, destination: str, date: str,
                          return_date: str = None, passengers: int = 1) -> List[Dict]:
        """
        Busca vuelos usando Skyscanner.
        """
        results = []
        
        try:
            origin_code = self._get_city_code(origin)
            dest_code = self._get_city_code(destination)
            
            if not origin_code or not dest_code:
                return results
            
            # URL de Skyscanner
            url = f"https://www.skyscanner.com/transport/flights/{origin_code.lower()}/{dest_code.lower()}/{date}"
            
            if return_date:
                url += f"/{return_date}"
            
            if passengers > 1:
                url += f"?adults={passengers}"
            
            webbrowser.open(url)
            
            results.append({
                "airline": "Skyscanner",
                "price": "Ver en navegador",
                "duration": "N/A",
                "stops": 0,
                "departure": date,
                "arrival": "N/A",
                "currency": "USD",
                "url": url,
                "source": "skyscanner"
            })
            
        except Exception as e:
            print(f"[FlightFinder] Error en Skyscanner: {e}")
        
        return results
    
    # ─── KIWI ─────────────────────────────────────────────────────────────
    def search_kiwi(self, origin: str, destination: str, date: str,
                    return_date: str = None, passengers: int = 1) -> List[Dict]:
        """
        Busca vuelos usando Kiwi.com.
        """
        results = []
        
        try:
            origin_code = self._get_city_code(origin)
            dest_code = self._get_city_code(destination)
            
            if not origin_code or not dest_code:
                return results
            
            url = f"https://www.kiwi.com/es/search/results/{origin_code}/{dest_code}/{date}"
            
            if return_date:
                url += f"/{return_date}"
            
            webbrowser.open(url)
            
            results.append({
                "airline": "Kiwi.com",
                "price": "Ver en navegador",
                "duration": "N/A",
                "stops": 0,
                "departure": date,
                "arrival": "N/A",
                "currency": "USD",
                "url": url,
                "source": "kiwi"
            })
            
        except Exception as e:
            print(f"[FlightFinder] Error en Kiwi: {e}")
        
        return results
    
    # ─── BÚSQUEDA COMBINADA ─────────────────────────────────────────────
    def search_all(self, origin: str, destination: str, date: str,
                   return_date: str = None, passengers: int = 1,
                   cabin: str = "economy", save: bool = False) -> List[Dict]:
        """
        Busca en todas las fuentes disponibles.
        """
        all_results = []
        
        # Google Flights
        google_results = self.search_google_flights(
            origin, destination, date, return_date, passengers, cabin
        )
        all_results.extend(google_results)
        
        # Skyscanner
        skyscanner_results = self.search_skyscanner(
            origin, destination, date, return_date, passengers
        )
        all_results.extend(skyscanner_results)
        
        # Kiwi
        kiwi_results = self.search_kiwi(
            origin, destination, date, return_date, passengers
        )
        all_results.extend(kiwi_results)
        
        # Guardar resultados si se solicita
        if save and all_results:
            self._save_results(origin, destination, date, all_results)
        
        return all_results
    
    def _save_results(self, origin: str, destination: str, date: str, results: List[Dict]):
        """Guarda los resultados de búsqueda."""
        try:
            filename = f"flights_{origin}_{destination}_{date}_{int(time.time())}.json"
            filepath = FLIGHTS_CACHE_DIR / filename
            filepath.write_text(
                json.dumps({
                    "origin": origin,
                    "destination": destination,
                    "date": date,
                    "timestamp": datetime.now().isoformat(),
                    "results": results
                }, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[FlightFinder] Error guardando resultados: {e}")
    
    def get_recent_searches(self, limit: int = 5) -> List[Dict]:
        """Obtiene las búsquedas recientes."""
        searches = []
        
        try:
            files = sorted(FLIGHTS_CACHE_DIR.glob("flights_*.json"), 
                         key=lambda x: x.stat().st_mtime, reverse=True)
            
            for filepath in files[:limit]:
                try:
                    data = json.loads(filepath.read_text(encoding="utf-8"))
                    searches.append({
                        "file": filepath.name,
                        "data": data
                    })
                except:
                    continue
            
        except Exception as e:
            print(f"[FlightFinder] Error obteniendo búsquedas recientes: {e}")
        
        return searches


# ─── FORMATO DE RESULTADOS ──────────────────────────────────────────────
def format_flight_results(results: List[Dict], origin: str, destination: str) -> str:
    """Formatea los resultados de vuelos."""
    if not results:
        return "❌ No se encontraron vuelos para esa ruta."
    
    lines = [
        f"✈️ VUELOS DE {origin.upper()} A {destination.upper()}",
        "━" * 50,
        f"🔍 {len(results)} fuentes consultadas",
        ""
    ]
    
    for i, result in enumerate(results, 1):
        source = result.get('source', 'desconocido')
        airline = result.get('airline', 'N/A')
        price = result.get('price', 'N/A')
        duration = result.get('duration', 'N/A')
        stops = result.get('stops', 0)
        departure = result.get('departure', 'N/A')
        url = result.get('url', '')
        currency = result.get('currency', 'USD')
        
        lines.append(f"🔹 {i}. {source.upper()}")
        lines.append(f"   ✈️ {airline}")
        lines.append(f"   💰 {price} {currency}")
        lines.append(f"   ⏱️ {duration}")
        lines.append(f"   🛑 {stops} escalas")
        lines.append(f"   📅 {departure}")
        if url:
            lines.append(f"   🔗 {url}")
        lines.append("")
    
    lines.append("━" * 50)
    lines.append("💡 Las pestañas del navegador se han abierto con los detalles.")
    lines.append("   Haz clic en los enlaces para ver precios exactos y reservar.")
    
    return "\n".join(lines)


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_searcher: Optional[FlightSearcher] = None

def get_searcher() -> FlightSearcher:
    """Obtiene la instancia del buscador de vuelos."""
    global _searcher
    if _searcher is None:
        _searcher = FlightSearcher()
    return _searcher


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def flight_finder(parameters: Dict, player=None) -> str:
    """
    Busca vuelos en múltiples fuentes.
    
    Args:
        parameters: Diccionario con parámetros
            - origin: Ciudad de origen
            - destination: Ciudad de destino
            - date: Fecha de salida (YYYY-MM-DD)
            - return_date: Fecha de regreso (opcional)
            - passengers: Número de pasajeros (default: 1)
            - cabin: economy | premium | business | first (default: economy)
            - source: google | skyscanner | kiwi | all (default: all)
            - save: Guardar resultados (default: false)
            - recent: Ver búsquedas recientes
            - config: Ver/editar configuración
    
    Returns:
        Resultados de la búsqueda de vuelos
    """
    p = parameters or {}
    action = p.get("action", "search").strip().lower()
    
    searcher = get_searcher()
    
    # ─── BÚSQUEDA RECIENTE ──────────────────────────────────────────────
    if action == "recent":
        recent = searcher.get_recent_searches()
        
        if not recent:
            return "📭 No hay búsquedas recientes."
        
        lines = ["📋 BÚSQUEDAS RECIENTES", "━" * 40]
        for r in recent:
            data = r.get("data", {})
            lines.append(f"  • {data.get('origin', 'N/A')} → {data.get('destination', 'N/A')}")
            lines.append(f"    📅 {data.get('date', 'N/A')}")
            lines.append(f"    🕐 {data.get('timestamp', 'N/A')[:16]}")
            lines.append("")
        
        return "\n".join(lines)
    
    # ─── CONFIGURACIÓN ──────────────────────────────────────────────────
    elif action == "config":
        config = searcher.config
        
        if p.get("set"):
            key = p.get("key")
            value = p.get("value")
            if key and value is not None:
                config.set(key, value)
                return f"✅ Configuración actualizada: {key} = {value}"
        
        lines = [
            "⚙️ CONFIGURACIÓN DE VUELOS",
            "━" * 40,
            f"  • Aerolíneas preferidas: {config.get('preferred_airlines', [])}",
            f"  • Máximo de escalas: {config.get('max_stops', 2)}",
            f"  • Precio máximo: {config.get('max_price', 'Sin límite')}",
            f"  • Moneda: {config.get('currency', 'USD')}",
            f"  • Pasajeros: {config.get('adults', 1)}",
            f"  • Clase: {config.get('cabin_class', 'economy')}",
            f"  • Alertas: {'✅' if config.get('alerts_enabled') else '❌'}",
            "",
            "💡 Para cambiar: {'action':'config','set':True,'key':'max_stops','value':1}"
        ]
        return "\n".join(lines)
    
    # ─── BÚSQUEDA ──────────────────────────────────────────────────────
    elif action == "search":
        origin = p.get("origin", "").strip()
        destination = p.get("destination", "").strip()
        date = p.get("date", "").strip()
        return_date = p.get("return_date", "").strip()
        passengers = int(p.get("passengers", 1))
        cabin = p.get("cabin", "economy").lower()
        source = p.get("source", "all").lower()
        save = p.get("save", False)
        
        # Validar parámetros
        if not origin or not destination:
            return "❌ Error: Especifica origen y destino."
        
        if not date:
            # Fecha por defecto: mañana
            tomorrow = datetime.now() + timedelta(days=1)
            date = tomorrow.strftime("%Y-%m-%d")
        
        # Parsear fechas
        date = searcher._parse_date(date)
        if return_date:
            return_date = searcher._parse_date(return_date)
        
        # Validar pasajeros
        if passengers < 1 or passengers > 9:
            return "❌ Error: Número de pasajeros debe ser entre 1 y 9."
        
        # Validar clase
        valid_cabins = ["economy", "premium", "business", "first"]
        if cabin not in valid_cabins:
            cabin = "economy"
        
        # Mensaje de búsqueda
        origin_info = searcher._get_city_info(origin)
        dest_info = searcher._get_city_info(destination)
        
        origin_display = origin_info.get("code", origin.upper()) if origin_info else origin.upper()
        dest_display = dest_info.get("code", destination.upper()) if dest_info else destination.upper()
        
        if player:
            player.write_log(f"✈️ Buscando vuelos de {origin_display} a {dest_display}...")
        
        # Realizar búsqueda
        if source == "google":
            results = searcher.search_google_flights(
                origin, destination, date, return_date, passengers, cabin
            )
        elif source == "skyscanner":
            results = searcher.search_skyscanner(
                origin, destination, date, return_date, passengers
            )
        elif source == "kiwi":
            results = searcher.search_kiwi(
                origin, destination, date, return_date, passengers
            )
        else:
            results = searcher.search_all(
                origin, destination, date, return_date, passengers, cabin, save
            )
        
        # Mostrar resultados
        return format_flight_results(results, origin, destination)
    
    # ─── CIUDADES ──────────────────────────────────────────────────────
    elif action == "cities":
        query = p.get("query", "").strip()
        
        if query:
            found = []
            for name, info in CITIES_DATABASE.items():
                if query.lower() in name or query.lower() in info["code"].lower():
                    found.append((name, info))
            
            if found:
                lines = ["🌍 CIUDADES ENCONTRADAS", "━" * 40]
                for name, info in found:
                    lines.append(f"  • {name.title()} ({info['code']}) - {info['country']}")
                return "\n".join(lines)
            else:
                return f"❌ No se encontró '{query}' en la base de datos."
        else:
            # Mostrar ciudades principales
            lines = ["🌍 CIUDADES PRINCIPALES", "━" * 40]
            major_cities = ["lima", "bogota", "buenos aires", "santiago", "mexico city", 
                           "new york", "miami", "los angeles", "madrid", "london", "paris"]
            
            for city in major_cities:
                if city in CITIES_DATABASE:
                    info = CITIES_DATABASE[city]
                    lines.append(f"  • {city.title()} ({info['code']}) - {info['country']}")
            
            lines.append("")
            lines.append("💡 Usa query='ciudad' para buscar específicamente")
            return "\n".join(lines)
    
    # ─── AYUDA ──────────────────────────────────────────────────────────
    else:
        return (
            "✈️ FLIGHT FINDER - COMANDOS\n"
            "━" * 50 + "\n\n"
            "🔍 Buscar vuelos:\n"
            "  {'action':'search','origin':'Lima','destination':'Madrid','date':'2026-01-15'}\n\n"
            "🔄 Búsqueda con regreso:\n"
            "  {'action':'search','origin':'Lima','destination':'Bogota','date':'2026-01-10','return_date':'2026-01-20'}\n\n"
            "👥 Múltiples pasajeros:\n"
            "  {'action':'search','origin':'Lima','destination':'Cancun','passengers':3}\n\n"
            "💺 Clase específica:\n"
            "  {'action':'search','origin':'Lima','destination':'New York','cabin':'business'}\n\n"
            "📋 Búsquedas recientes:\n"
            "  {'action':'recent'}\n\n"
            "🌍 Listar ciudades:\n"
            "  {'action':'cities','query':'Lima'}\n\n"
            "⚙️ Configuración:\n"
            "  {'action':'config'}\n"
            "  {'action':'config','set':True,'key':'max_stops','value':1}\n\n"
            "📌 Fuentes disponibles:\n"
            "  • Google Flights (default)\n"
            "  • Skyscanner\n"
            "  • Kiwi.com\n"
            "  • all (todas)"
        )


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_flight_finder():
    """Inicializa el módulo de búsqueda de vuelos."""
    print("[FlightFinder] Inicializando...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    FLIGHTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    if not requests:
        print("[FlightFinder] ⚠️ requests no instalado - funcionalidad limitada")
    if not BeautifulSoup:
        print("[FlightFinder] ⚠️ BeautifulSoup no instalado - scraping limitado")
    
    print(f"[FlightFinder] {len(CITIES_DATABASE)} ciudades en base de datos")
    print("[FlightFinder] ✅ Listo")
    return True