"""
Delivery Apps Automation for ILUM
=================================
Módulo profesional con arquitectura de plugins, NLP y soporte multi-navegador.
"""

import os
import json
import logging
import webbrowser
import urllib.parse
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod
import importlib
import sys

# ─── CONFIGURACIÓN DE LOGGING ───────────────────────────────────────

LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "delivery.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── CONSTANTES ──────────────────────────────────────────────────────

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
HISTORY_FILE = CONFIG_DIR / "delivery_history.json"
SETTINGS_FILE = CONFIG_DIR / "delivery_settings.json"
PLUGINS_DIR = Path(__file__).parent / "delivery_plugins"

# Asegurar que los plugins puedan importar delivery_plugin_base desde su carpeta
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

# ─── MODELOS DE DATOS ──────────────────────────────────────────────

@dataclass
class DeliverySettings:
    """Configuración del sistema"""
    default_app: str = "rappi"
    country: str = "colombia"
    browser: str = "default"
    open_native: bool = False
    open_multiple: bool = False
    history_limit: int = 50
    use_ranking: bool = True
    nlp_enabled: bool = True

@dataclass
class DeliveryHistory:
    """Entrada de historial"""
    app: str
    query: str
    category: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class DeliveryIntent:
    """Intención del usuario parseada por NLP"""
    action: str  # search, open_app, repeat, nearby
    app: Optional[str] = None
    query: Optional[str] = None
    category: Optional[str] = None
    nearby: bool = False
    price: Optional[str] = None  # low, medium, high
    time: Optional[str] = None  # now, later

# ─── PLUGIN BASE ────────────────────────────────────────────────────

class DeliveryPlugin(ABC):
    """Clase base para plugins de delivery"""
    
    @abstractmethod
    def get_name(self) -> str:
        """Nombre del plugin"""
        pass
    
    @abstractmethod
    def get_aliases(self) -> List[str]:
        """Alias del plugin"""
        pass
    
    @abstractmethod
    def get_search_url(self, query: str, category: Optional[str] = None) -> str:
        """URL de búsqueda"""
        pass
    
    @abstractmethod
    def get_app_scheme(self) -> Optional[str]:
        """Scheme para app nativa"""
        pass
    
    def get_priority(self) -> int:
        """Prioridad del plugin (mayor = más importante)"""
        return 5
    
    def is_available(self, country: str) -> bool:
        """Verifica si está disponible en el país"""
        return True
    
    def get_countries(self) -> List[str]:
        """Países donde está disponible"""
        return []

# ─── PLUGIN MANAGER ─────────────────────────────────────────────────

class PluginManager:
    """Gestor de plugins de delivery"""
    
    def __init__(self):
        self.plugins: Dict[str, DeliveryPlugin] = {}
        self._load_plugins()
        
    def _load_plugins(self):
        """Carga plugins desde el directorio de plugins"""
        if not PLUGINS_DIR.exists():
            PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
            self._create_default_plugins()
        
        # Cargar plugins
        for file_path in PLUGINS_DIR.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            
            try:
                # Importar módulo
                module_name = f"delivery_plugins.{file_path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    # Buscar clases que hereden de DeliveryPlugin
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, DeliveryPlugin) and 
                            attr != DeliveryPlugin):
                            plugin = attr()
                            self.plugins[plugin.get_name().lower()] = plugin
                            logger.info(f"Plugin cargado: {plugin.get_name()}")
            except Exception as e:
                logger.error(f"Error cargando plugin {file_path.name}: {e}")
    
    def _create_default_plugins(self):
        """Crea plugins por defecto"""
        default_plugins = {
            "rappi.py": """
from delivery_plugin_base import DeliveryPlugin

class RappiPlugin(DeliveryPlugin):
    def get_name(self): return "Rappi"
    def get_aliases(self): return ["rappi", "rapi", "rp"]
    def get_search_url(self, query, category=None):
        if category:
            query = f"{category} {query}"
        return f"https://www.rappi.com/search?store_type=all&query={urllib.parse.quote(query)}"
    def get_app_scheme(self): return "rappi://"
    def get_priority(self): return 10
    def get_countries(self): return ["colombia", "mexico", "argentina", "chile", "peru", "brasil", "españa"]
""",
            "uber_eats.py": """
from delivery_plugin_base import DeliveryPlugin

class UberEatsPlugin(DeliveryPlugin):
    def get_name(self): return "Uber Eats"
    def get_aliases(self): return ["uber", "ubereats", "uber eats", "ue"]
    def get_search_url(self, query, category=None):
        if category:
            query = f"{category} {query}"
        return f"https://www.ubereats.com/search?q={urllib.parse.quote(query)}"
    def get_app_scheme(self): return "ubereats://"
    def get_priority(self): return 9
    def get_countries(self): return ["colombia", "mexico", "argentina", "chile", "peru", "brasil", "españa", "usa", "uk"]
""",
            "pedidos_ya.py": """
from delivery_plugin_base import DeliveryPlugin

class PedidosYaPlugin(DeliveryPlugin):
    def get_name(self): return "PedidosYa"
    def get_aliases(self): return ["pedidos", "pedidosya", "pedido ya", "py"]
    def get_search_url(self, query, category=None):
        if category:
            query = f"{category} {query}"
        return f"https://www.pedidosya.com/restaurantes?q={urllib.parse.quote(query)}"
    def get_app_scheme(self): return "pedidosya://"
    def get_priority(self): return 8
    def get_countries(self): return ["colombia", "argentina", "chile", "peru", "mexico", "uruguay"]
""",
            "glovo.py": """
from delivery_plugin_base import DeliveryPlugin

class GlovoPlugin(DeliveryPlugin):
    def get_name(self): return "Glovo"
    def get_aliases(self): return ["glovo"]
    def get_search_url(self, query, category=None):
        if category:
            query = f"{category} {query}"
        return f"https://glovoapp.com/es/search?q={urllib.parse.quote(query)}"
    def get_app_scheme(self): return "glovo://"
    def get_priority(self): return 8
    def get_countries(self): return ["españa", "mexico", "argentina", "chile", "peru", "colombia", "portugal"]
""",
            "ifood.py": """
from delivery_plugin_base import DeliveryPlugin

class IfoodPlugin(DeliveryPlugin):
    def get_name(self): return "iFood"
    def get_aliases(self): return ["ifood", "i food"]
    def get_search_url(self, query, category=None):
        if category:
            query = f"{category} {query}"
        return f"https://www.ifood.com.br/busca?q={urllib.parse.quote(query)}"
    def get_app_scheme(self): return "ifood://"
    def get_priority(self): return 9
    def get_countries(self): return ["brasil"]
""",
            "doordash.py": """
from delivery_plugin_base import DeliveryPlugin

class DoorDashPlugin(DeliveryPlugin):
    def get_name(self): return "DoorDash"
    def get_aliases(self): return ["doordash", "dash"]
    def get_search_url(self, query, category=None):
        if category:
            query = f"{category} {query}"
        return f"https://www.doordash.com/search?q={urllib.parse.quote(query)}"
    def get_app_scheme(self): return "doordash://"
    def get_priority(self): return 8
    def get_countries(self): return ["usa", "australia", "canada"]
"""
        }
        
        # Crear archivos de plugins
        for filename, content in default_plugins.items():
            file_path = PLUGINS_DIR / filename
            if not file_path.exists():
                file_path.write_text(content, encoding="utf-8")
        
        # Crear archivo base
        base_file = PLUGINS_DIR / "delivery_plugin_base.py"
        if not base_file.exists():
            base_file.write_text("""
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Optional

class DeliveryPlugin(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass
    
    @abstractmethod
    def get_aliases(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_search_url(self, query: str, category: Optional[str] = None) -> str:
        pass
    
    @abstractmethod
    def get_app_scheme(self) -> Optional[str]:
        pass
    
    def get_priority(self) -> int:
        return 5
    
    def is_available(self, country: str) -> bool:
        return True
    
    def get_countries(self) -> List[str]:
        return []
""", encoding="utf-8")
    
    def get_plugin(self, name: str) -> Optional[DeliveryPlugin]:
        """Obtiene un plugin por nombre"""
        name = name.lower()
        if name in self.plugins:
            return self.plugins[name]
        
        # Buscar por alias
        for plugin in self.plugins.values():
            if name in [alias.lower() for alias in plugin.get_aliases()]:
                return plugin
        
        return None
    
    def get_plugins_by_country(self, country: str) -> List[DeliveryPlugin]:
        """Obtiene plugins disponibles en un país"""
        country = country.lower()
        available = []
        for plugin in self.plugins.values():
            if country in plugin.get_countries() or not plugin.get_countries():
                available.append(plugin)
        return sorted(available, key=lambda x: x.get_priority(), reverse=True)

# ─── NAVEGADOR MANAGER ──────────────────────────────────────────────

class BrowserManager:
    """Gestor de navegadores"""
    
    def __init__(self):
        self.browsers = {
            "default": self._open_default,
            "chrome": self._open_chrome,
            "edge": self._open_edge,
            "firefox": self._open_firefox,
            "opera": self._open_opera,
            "brave": self._open_brave
        }
        self.default_browser = "default"
        
    def _open_default(self, url: str) -> bool:
        """Abre en navegador predeterminado"""
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            logger.error(f"Error abriendo navegador: {e}")
            return False
    
    def _open_chrome(self, url: str) -> bool:
        """Abre en Chrome"""
        try:
            if os.name == 'nt':
                os.startfile(f"chrome {url}")
            else:
                import subprocess
                subprocess.Popen(["google-chrome", url])
            return True
        except:
            return self._open_default(url)
    
    def _open_edge(self, url: str) -> bool:
        """Abre en Edge"""
        try:
            if os.name == 'nt':
                os.startfile(f"microsoft-edge:{url}")
            else:
                import subprocess
                subprocess.Popen(["microsoft-edge", url])
            return True
        except:
            return self._open_default(url)
    
    def _open_firefox(self, url: str) -> bool:
        """Abre en Firefox"""
        try:
            if os.name == 'nt':
                os.startfile(f"firefox {url}")
            else:
                import subprocess
                subprocess.Popen(["firefox", url])
            return True
        except:
            return self._open_default(url)
    
    def _open_opera(self, url: str) -> bool:
        """Abre en Opera"""
        try:
            if os.name == 'nt':
                os.startfile(f"opera {url}")
            else:
                import subprocess
                subprocess.Popen(["opera", url])
            return True
        except:
            return self._open_default(url)
    
    def _open_brave(self, url: str) -> bool:
        """Abre en Brave"""
        try:
            if os.name == 'nt':
                os.startfile(f"brave {url}")
            else:
                import subprocess
                subprocess.Popen(["brave-browser", url])
            return True
        except:
            return self._open_default(url)
    
    def open(self, url: str, browser: Optional[str] = None) -> bool:
        """Abre URL en el navegador especificado"""
        browser_name = browser or self.default_browser
        browser_name = browser_name.lower()
        
        if browser_name in self.browsers:
            return self.browsers[browser_name](url)
        else:
            return self._open_default(url)
    
    def set_default(self, browser: str):
        """Establece navegador predeterminado"""
        if browser.lower() in self.browsers:
            self.default_browser = browser.lower()

# ─── NLP PARSER ─────────────────────────────────────────────────────

class NLPParser:
    """Parser de lenguaje natural para comandos de delivery"""
    
    def __init__(self):
        self.intent_patterns = {
            "open_app": [
                r"abre\s+(\w+)",
                r"open\s+(\w+)",
                r"(\w+)\s+por favor",
                r"quiero\s+(\w+)",
            ],
            "search": [
                r"busca\s+(.+)",
                r"quiero\s+(.+)",
                r"buscame\s+(.+)",
                r"comida\s+(.+)",
                r"(pizza|hamburguesa|sushi|pollo|tacos|pasta|helado|cafeteria)",
                r"(tengo hambre|quiero comer|necesito comer)",
            ],
            "nearby": [
                r"cerca\s+de\s+(.+)",
                r"(?:cerca|about)\s+(.+)",
                r"donde\s+hay\s+(.+)",
            ],
            "repeat": [
                r"repite",
                r"repetir",
                r"otra vez",
                r"lo mismo",
            ],
            "favorite": [
                r"favorito",
                r"favoritos",
            ],
        }
        
        self.category_patterns = {
            "pizza": ["pizza", "pizzas", "pizzeria"],
            "hamburguesa": ["hamburguesa", "burger", "hamburger", "hamburguesas"],
            "pollo": ["pollo", "pollito", "fried chicken", "pollo frito"],
            "sushi": ["sushi", "sashimi", "japonesa"],
            "mexicana": ["mexicana", "tacos", "taco", "mexicano"],
            "italiana": ["italiana", "pasta", "spaghetti"],
            "china": ["china", "chino", "chop suey", "wantán"],
            "coreana": ["coreana", "korean", "bbq coreano"],
            "tailandesa": ["tailandesa", "thai", "tailandés"],
            "asiatica": ["asiatica", "asia", "asiático"],
            "indiana": ["indiana", "indio", "curry"],
            "vegana": ["vegana", "vegan", "vegetariana", "vegetarian"],
            "helados": ["helados", "ice cream", "nieve"],
            "cafeteria": ["cafeteria", "coffee", "cafe", "café"],
            "postres": ["postres", "dessert", "dulces"],
            "ensaladas": ["ensaladas", "salad", "ensalada"],
            "comida rapida": ["comida rapida", "fast food", "rapida", "rápida"],
            "mariscos": ["mariscos", "seafood", "pescado"],
            "sandwiches": ["sandwiches", "sandwich", "bocadillo"],
            "barbacoa": ["barbacoa", "bbq", "barbecue"],
        }
        
        self.price_patterns = {
            "low": ["barato", "económico", "low", "cheap", "económico"],
            "medium": ["normal", "medio", "medium", "regular"],
            "high": ["caro", "premium", "expensive", "high"]
        }
    
    def parse(self, text: str) -> DeliveryIntent:
        """Parsea texto y devuelve una intención"""
        text = text.lower().strip()
        intent = DeliveryIntent(action="search")
        
        # Buscar acción
        for action, patterns in self.intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    intent.action = action
                    if action == "open_app":
                        intent.app = match.group(1)
                        return intent
                    elif action == "search":
                        # Extraer query
                        if match.group(1):
                            query = match.group(1)
                            intent.query = query
                            # Detectar categoría
                            intent.category = self._detect_category(query)
                            # Detectar precio
                            intent.price = self._detect_price(query)
                            # Detectar si es cerca
                            if "cerca" in text or "near" in text:
                                intent.nearby = True
                        else:
                            intent.query = "comida"
                        return intent
                    elif action == "nearby":
                        if match.group(1):
                            query = match.group(1)
                            intent.query = query
                            intent.nearby = True
                            intent.category = self._detect_category(query)
                        return intent
                    elif action == "repeat":
                        intent.action = "repeat"
                        return intent
                    elif action == "favorite":
                        intent.action = "favorite"
                        return intent
        
        # Si no hay match, buscar directamente categoría
        category = self._detect_category(text)
        if category:
            intent.query = category
            intent.category = category
        else:
            intent.query = text
        
        return intent
    
    def _detect_category(self, text: str) -> Optional[str]:
        """Detecta categoría en el texto"""
        text = text.lower()
        for category, keywords in self.category_patterns.items():
            for keyword in keywords:
                if keyword in text:
                    return category
        return None
    
    def _detect_price(self, text: str) -> Optional[str]:
        """Detecta precio en el texto"""
        text = text.lower()
        for price, keywords in self.price_patterns.items():
            for keyword in keywords:
                if keyword in text:
                    return price
        return None

# ─── GESTOR PRINCIPAL ──────────────────────────────────────────────

class DeliveryManager:
    """Gestor profesional de aplicaciones de delivery"""
    
    def __init__(self):
        self.plugin_manager = PluginManager()
        self.browser_manager = BrowserManager()
        self.nlp_parser = NLPParser()
        self.settings = self._load_settings()
        self.history = self._load_history()
        self.ranking = self._load_ranking()
        self.country = self.settings.country
        
    def _load_settings(self) -> DeliverySettings:
        """Carga la configuración"""
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                return DeliverySettings(**data)
            except:
                pass
        return DeliverySettings()
    
    def _save_settings(self):
        """Guarda la configuración"""
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self.settings), indent=4, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _load_history(self) -> List[DeliveryHistory]:
        """Carga el historial"""
        if HISTORY_FILE.exists():
            try:
                data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                return [DeliveryHistory(**entry) for entry in data]
            except:
                pass
        return []
    
    def _save_history(self):
        """Guarda el historial"""
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(entry) for entry in self.history]
        HISTORY_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    
    def _load_ranking(self) -> Dict[str, int]:
        """Carga el ranking"""
        ranking_file = CONFIG_DIR / "delivery_ranking.json"
        if ranking_file.exists():
            try:
                return json.loads(ranking_file.read_text(encoding="utf-8"))
            except:
                pass
        return {}
    
    def _save_ranking(self):
        """Guarda el ranking"""
        ranking_file = CONFIG_DIR / "delivery_ranking.json"
        ranking_file.parent.mkdir(parents=True, exist_ok=True)
        ranking_file.write_text(json.dumps(self.ranking, indent=4, ensure_ascii=False), encoding="utf-8")
    
    def _add_to_history(self, app: str, query: str, category: Optional[str] = None):
        """Añade al historial y ranking"""
        entry = DeliveryHistory(app=app, query=query, category=category)
        self.history.insert(0, entry)
        self.history = self.history[:self.settings.history_limit]
        self._save_history()
        
        if app in self.ranking:
            self.ranking[app] += 1
        else:
            self.ranking[app] = 1
        self._save_ranking()
    
    def _get_best_app(self, query: str, category: Optional[str] = None) -> Optional[str]:
        """Obtiene la mejor app usando ranking"""
        if not self.settings.use_ranking:
            return self.settings.default_app
        
        available_plugins = self.plugin_manager.get_plugins_by_country(self.country)
        
        if not available_plugins:
            return self.settings.default_app
        
        # Ordenar por ranking
        ranked_plugins = []
        for plugin in available_plugins:
            name = plugin.get_name().lower()
            score = self.ranking.get(name, 0) + plugin.get_priority()
            ranked_plugins.append((plugin, score))
        
        ranked_plugins.sort(key=lambda x: x[1], reverse=True)
        
        if ranked_plugins:
            return ranked_plugins[0][0].get_name().lower()
        
        return self.settings.default_app
    
    def _open_plugin(self, plugin: DeliveryPlugin, query: str, category: Optional[str] = None) -> bool:
        """Abre un plugin específico"""
        url = plugin.get_search_url(query, category)
        
        # Intentar app nativa
        if self.settings.open_native and plugin.get_app_scheme():
            try:
                scheme = plugin.get_app_scheme()
                app_url = f"{scheme}?q={urllib.parse.quote(query)}"
                if os.name == 'nt':
                    os.startfile(app_url)
                else:
                    import subprocess
                    subprocess.Popen(["open", app_url])
                return True
            except:
                pass
        
        # Navegador
        browser = self.settings.browser
        return self.browser_manager.open(url, browser)
    
    def process_natural(self, text: str) -> str:
        """Procesa lenguaje natural"""
        if not self.settings.nlp_enabled:
            return self._process_manual(text)
        
        intent = self.nlp_parser.parse(text)
        
        if intent.action == "open_app":
            return self.open_app(intent.app)
        
        elif intent.action == "repeat":
            return self.repeat_last()
        
        elif intent.action == "nearby":
            return self.search(intent.query or "comida", intent.app, intent.category, nearby=True)
        
        elif intent.action == "favorite":
            return self.get_favorites()
        
        else:  # search
            return self.search(intent.query or "comida", intent.app, intent.category, 
                             nearby=intent.nearby, price=intent.price)
    
    def _process_manual(self, text: str) -> str:
        """Procesa texto manualmente (fallback)"""
        text = text.lower()
        
        # Detectar comandos simples
        if "abre" in text or "open" in text:
            for word in text.split():
                if word in ["rappi", "uber", "pedidos", "glovo", "ifood"]:
                    return self.open_app(word)
        
        return self.search(text)
    
    def search(self, query: str, app_name: Optional[str] = None,
               category: Optional[str] = None,
               nearby: bool = False,
               price: Optional[str] = None,
               open_multiple: Optional[bool] = None) -> str:
        """Búsqueda principal"""
        query = query.strip()
        if not query:
            return "❌ ¿Qué comida te gustaría buscar?"
        
        # Si es cerca, añadir a query
        if nearby:
            query = f"{query} cerca de mi ubicación"
        
        # Determinar app
        if app_name:
            plugin = self.plugin_manager.get_plugin(app_name)
            if not plugin:
                return f"❌ App '{app_name}' no encontrada"
        else:
            best_app = self._get_best_app(query, category)
            plugin = self.plugin_manager.get_plugin(best_app) if best_app else None
            if not plugin:
                return "❌ No hay apps disponibles en tu país"
        
        # Abrir múltiples
        should_open_multiple = open_multiple if open_multiple is not None else self.settings.open_multiple
        
        if should_open_multiple:
            return self._search_multiple(query, category)
        
        # Abrir app
        success = self._open_plugin(plugin, query, category)
        
        if success:
            self._add_to_history(plugin.get_name().lower(), query, category)
            category_msg = f" (categoría: {category})" if category else ""
            price_msg = f" - {price}" if price else ""
            return f"🍔 Buscando '{query}' en {plugin.get_name()}{category_msg}{price_msg}"
        else:
            return f"❌ Error al abrir {plugin.get_name()}"
    
    def _search_multiple(self, query: str, category: Optional[str] = None) -> str:
        """Busca en múltiples apps"""
        plugins = self.plugin_manager.get_plugins_by_country(self.country)[:5]
        
        opened = []
        failed = []
        
        def open_plugin(plugin):
            try:
                if self._open_plugin(plugin, query, category):
                    opened.append(plugin.get_name())
                else:
                    failed.append(plugin.get_name())
            except Exception as e:
                logger.error(f"Error abriendo {plugin.get_name()}: {e}")
                failed.append(plugin.get_name())
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(open_plugin, plugins)
        
        self._add_to_history("multiple", query, category)
        
        result = f"🍔 Buscando '{query}' en múltiples apps:\n"
        if opened:
            result += "✅ " + ", ".join(opened) + "\n"
        if failed:
            result += "❌ " + ", ".join(failed)
        
        return result
    
    def open_app(self, app_name: str) -> str:
        """Abre una app específica"""
        plugin = self.plugin_manager.get_plugin(app_name)
        if not plugin:
            return f"❌ App '{app_name}' no encontrada"
        
        # Abrir app (sin búsqueda)
        try:
            if self.settings.open_native and plugin.get_app_scheme():
                scheme = plugin.get_app_scheme()
                if os.name == 'nt':
                    os.startfile(scheme)
                else:
                    import subprocess
                    subprocess.Popen(["open", scheme])
                return f"📱 Abriendo {plugin.get_name()}"
            else:
                # Abrir página principal
                url = plugin.get_search_url("")
                self.browser_manager.open(url, self.settings.browser)
                return f"🌐 Abriendo {plugin.get_name()}"
        except Exception as e:
            return f"❌ Error al abrir {plugin.get_name()}: {e}"
    
    def repeat_last(self) -> str:
        """Repite la última búsqueda"""
        if not self.history:
            return "📭 No hay búsquedas anteriores."
        
        last = self.history[0]
        return self.search(last.query, last.app, last.category)
    
    def get_history(self, limit: int = 10) -> str:
        """Obtiene el historial"""
        if not self.history:
            return "📭 No hay historial de búsquedas."
        
        result = "📜 **Historial de búsquedas:**\n\n"
        for i, entry in enumerate(self.history[:limit], 1):
            date = entry.timestamp.split("T")[0] if entry.timestamp else "N/A"
            category = f" ({entry.category})" if entry.category else ""
            result += f"{i}. [{date}] {entry.app}: {entry.query}{category}\n"
        
        return result
    
    def clear_history(self) -> str:
        """Limpia el historial"""
        self.history = []
        self._save_history()
        return "🗑️ Historial limpiado."
    
    def get_favorites(self) -> str:
        """Obtiene apps favoritas por ranking"""
        if not self.ranking:
            return "📊 No hay datos de favoritos aún."
        
        sorted_ranking = sorted(self.ranking.items(), key=lambda x: x[1], reverse=True)
        
        result = "⭐ **Tus apps favoritas:**\n\n"
        for i, (app, count) in enumerate(sorted_ranking[:5], 1):
            stars = "⭐" * min(5, max(1, count // 5 + 1))
            result += f"{i}. {app.title()} {stars} ({count} búsquedas)\n"
        
        return result
    
    def set_default_app(self, app_name: str) -> str:
        """Establece app predeterminada"""
        plugin = self.plugin_manager.get_plugin(app_name)
        if not plugin:
            return f"❌ App '{app_name}' no encontrada"
        
        self.settings.default_app = plugin.get_name().lower()
        self._save_settings()
        return f"✅ App predeterminada: {plugin.get_name()}"
    
    def set_country(self, country: str) -> str:
        """Establece el país"""
        self.settings.country = country.lower()
        self.country = country.lower()
        self._save_settings()
        
        plugins = self.plugin_manager.get_plugins_by_country(country)
        app_names = [p.get_name() for p in plugins[:5]]
        
        return f"✅ País: {country.title()}\nApps disponibles: {', '.join(app_names)}"
    
    def set_browser(self, browser: str) -> str:
        """Establece navegador"""
        if browser.lower() in ["default", "chrome", "edge", "firefox", "opera", "brave"]:
            self.settings.browser = browser.lower()
            self.browser_manager.set_default(browser)
            self._save_settings()
            return f"✅ Navegador: {browser.title()}"
        return f"❌ Navegador '{browser}' no soportado"
    
    def set_native(self, enabled: bool) -> str:
        """Configura apps nativas"""
        self.settings.open_native = enabled
        self._save_settings()
        return f"✅ Apps nativas: {'Activado' if enabled else 'Desactivado'}"
    
    def set_multiple(self, enabled: bool) -> str:
        """Configura múltiples apps"""
        self.settings.open_multiple = enabled
        self._save_settings()
        return f"✅ Múltiples apps: {'Activado' if enabled else 'Desactivado'}"
    
    def set_nlp(self, enabled: bool) -> str:
        """Configura NLP"""
        self.settings.nlp_enabled = enabled
        self._save_settings()
        return f"✅ NLP: {'Activado' if enabled else 'Desactivado'}"
    
    def list_apps(self) -> str:
        """Lista todas las apps"""
        plugins = self.plugin_manager.get_plugins_by_country(self.country)
        
        if not plugins:
            return "📭 No hay apps disponibles en tu país"
        
        result = "📋 **Apps disponibles:**\n\n"
        for plugin in plugins:
            aliases = ", ".join(plugin.get_aliases())
            result += f"  • {plugin.get_name()}\n"
            if aliases:
                result += f"    Aliases: {aliases}\n"
        
        return result
    
    def get_status(self) -> str:
        """Estado del sistema"""
        result = "📊 **Estado del sistema:**\n\n"
        result += f"País: {self.country.title()}\n"
        result += f"Navegador: {self.settings.browser.title()}\n"
        result += f"Apps nativas: {'✅' if self.settings.open_native else '❌'}\n"
        result += f"Múltiples apps: {'✅' if self.settings.open_multiple else '❌'}\n"
        result += f"NLP: {'✅' if self.settings.nlp_enabled else '❌'}\n"
        result += f"Ranking: {'✅' if self.settings.use_ranking else '❌'}\n"
        result += f"Historial: {len(self.history)} búsquedas\n"
        result += f"Plugins: {len(self.plugin_manager.plugins)}\n"
        
        if self.history:
            last = self.history[0]
            result += f"\n📌 Última búsqueda:\n"
            result += f"  App: {last.app}\n"
            result += f"  Query: {last.query}\n"
        
        return result

# ─── INSTANCIA GLOBAL ──────────────────────────────────────────────

_MANAGER = DeliveryManager()

# ─── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────

def delivery_apps(parameters: dict, player=None) -> str:
    """
    Controlador de aplicaciones de comida a domicilio con soporte NLP.
    
    Modo de uso:
    - Puede recibir comandos estructurados (JSON)
    - O lenguaje natural directamente
    
    Ejemplos de lenguaje natural:
    - "tengo hambre"
    - "quiero pizza"
    - "abre rappi"
    - "busca sushi cerca"
    - "repite la última"
    - "comida mexicana barata"
    """
    
    manager = _MANAGER
    
    # Si es lenguaje natural (sin action)
    if "action" not in parameters:
        # Si hay query, procesar como NLP
        if "query" in parameters:
            return manager.process_natural(parameters["query"])
        # Si no, error
        return "❌ ¿Qué comida te gustaría buscar?"
    
    action = parameters.get("action", "").lower()
    
    if player:
        logger.info(f"Delivery action: {action}")
    
    # ─── Acciones estructuradas ────────────────────────────────────
    
    if action == "search":
        return manager.search(
            parameters.get("query", ""),
            parameters.get("app"),
            parameters.get("category"),
            parameters.get("nearby", False),
            parameters.get("price"),
            parameters.get("open_multiple")
        )
    
    elif action == "open_app":
        return manager.open_app(parameters.get("app", ""))
    
    elif action == "repeat":
        return manager.repeat_last()
    
    elif action == "history":
        return manager.get_history(parameters.get("limit", 10))
    
    elif action == "clear_history":
        return manager.clear_history()
    
    elif action == "favorites":
        return manager.get_favorites()
    
    elif action == "set_default":
        return manager.set_default_app(parameters.get("app", ""))
    
    elif action == "set_country":
        return manager.set_country(parameters.get("country", ""))
    
    elif action == "set_browser":
        return manager.set_browser(parameters.get("browser", "default"))
    
    elif action == "set_native":
        return manager.set_native(parameters.get("enabled", True))
    
    elif action == "set_multiple":
        return manager.set_multiple(parameters.get("enabled", True))
    
    elif action == "set_nlp":
        return manager.set_nlp(parameters.get("enabled", True))
    
    elif action == "list_apps":
        return manager.list_apps()
    
    elif action == "status":
        return manager.get_status()
    
    elif action == "nlp":
        return manager.process_natural(parameters.get("text", ""))
    
    else:
        return f"""❌ Acción '{action}' no reconocida.

📋 **Acciones disponibles:**
search, open_app, repeat, history, clear_history, favorites,
set_default, set_country, set_browser, set_native, set_multiple,
set_nlp, list_apps, status, nlp

🗣️ **Lenguaje natural (sin action):**
- "tengo hambre"
- "quiero pizza"
- "abre rappi"
- "busca sushi cerca"
- "repite la última"
- "comida mexicana barata"

📝 **Ejemplos estructurados:**
1. Buscar:
   {{"action": "search", "query": "pizza", "nearby": true}}

2. Abrir app:
   {{"action": "open_app", "app": "rappi"}}

3. Configurar navegador:
   {{"action": "set_browser", "browser": "chrome"}}

4. NLP directo:
   {{"action": "nlp", "text": "quiero hamburguesa"}}
"""

# ─── FUNCIONES DE AYUDA ────────────────────────────────────────────

def get_available_apps() -> List[str]:
    """Retorna apps disponibles"""
    plugins = _MANAGER.plugin_manager.get_plugins_by_country(_MANAGER.country)
    return [p.get_name().lower() for p in plugins]

def get_browsers() -> List[str]:
    """Retorna navegadores soportados"""
    return ["default", "chrome", "edge", "firefox", "opera", "brave"]

def get_countries() -> List[str]:
    """Retorna países soportados"""
    return ["colombia", "brasil", "españa", "mexico", "argentina", 
            "chile", "peru", "usa", "uk", "alemania", "francia", 
            "italia", "portugal", "polonia", "suecia", "australia"]