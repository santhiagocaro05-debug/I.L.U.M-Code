"""
Game Companion Pro
===================
Módulo avanzado de visión y análisis para videojuegos.
Reconoce juegos populares y da consejos tácticos en tiempo real.
Soporta: LoL, Valorant, CS:GO, Dota 2, Fortnite, Apex, Overwatch, etc.
"""

import re
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

from actions.screen_vision import screen_vision

# ─── BASE DE CONOCIMIENTO DE JUEGOS ─────────────────────────────────────
GAME_DATABASE = {
    "league of legends": {
        "aliases": ["lol", "league", "liga de leyendas"],
        "type": "moba",
        "advice_templates": [
            "Revisa el minimapa - {enemies} enemigos visibles cerca de tu línea",
            "Tu {role} debería estar farmeando en {lane} ahora",
            "El objetivo {objective} está disponible - considera rotar",
            "Tu oponente usó {summoner} - tienes {cooldown} segundos de ventaja",
            "La visión en {location} está caída - coloca un ward",
            "El jungla enemigo está en {side} - ten cuidado",
            "Torre {tower} está baja - puedes presionar",
            "Tu {item} está listo - úsalo en la siguiente pelea",
            "El enemigo tiene {items} - necesitas {counter_item}",
            "La composición enemiga es {comp} - juega {playstyle}"
        ],
        "critical_elements": ["minimapa", "vida", "maná", "objetivos", "torres", "items"],
        "roles": {"top", "jungla", "mid", "adc", "support"}
    },
    "valorant": {
        "aliases": ["valo", "valorant"],
        "type": "fps",
        "advice_templates": [
            "Enemigos en {location} - {count} jugadores",
            "Tu salud es {health} - necesitas curarte",
            "La bomba está en {bomb_site} - {action}",
            "Usa tu habilidad {ability} - está disponible",
            "El enemigo tiene {weapon} - juega con {playstyle}",
            "El agente {agent} enemigo usó {ability} - espera {cooldown}s",
            "El tiempo se acaba - {action} rápido",
            "Escuchaste pasos en {direction} - prepárate",
            "Tu ultimate está {status} - {advice}",
            "El enemigo está en {position} - {action}"
        ],
        "critical_elements": ["vida", "escudo", "habilidades", "bomba", "enemigos"],
        "agents": ["jett", "raze", "phoenix", "sova", "sage", "omen", "brimstone", "viper"]
    },
    "counter strike": {
        "aliases": ["cs", "csgo", "cs:go", "counter-strike"],
        "type": "fps",
        "advice_templates": [
            "Enemigos en {location} - {count} jugadores",
            "Tu dinero: ${money} - puedes comprar {weapon}",
            "La bomba está en {bomb_site} - {action}",
            "Tienes {health} HP - cuidado con los headshots",
            "El enemigo tiene AWP - usa {counter}",
            "Quedan {rounds} rondas - {strategy}",
            "Flashbang disponible - úsala para entrar a {location}",
            "El enemigo está eco - puedes presionar",
            "Tu equipo tiene ventaja numérica - {action}",
            "El enemigo tiene {weapon} - juega {playstyle}"
        ],
        "critical_elements": ["dinero", "vida", "bomba", "rondas", "armas"],
        "maps": ["dust2", "mirage", "inferno", "nuke", "overpass", "vertigo"]
    },
    "fortnite": {
        "aliases": ["fort", "fortnite"],
        "type": "battle_royale",
        "advice_templates": [
            "El círculo se cierra en {direction} - corre",
            "Materiales: {materials} - necesitas {advice}",
            "Enemigos en {location} - {action}",
            "Tu salud: {health} - {advice}",
            "El enemigo tiene {weapon} - construye {structure}",
            "Lluvia de suministros en {location} - ve por ella",
            "El storm se acerca - tienes {time} segundos",
            "Enemigos cerca de {location} - {action}",
            "Tu construcción es {advice} - mejora",
            "El enemigo está en {height} - {action}"
        ],
        "critical_elements": ["círculo", "materiales", "vida", "escudo", "construcciones"],
        "weapons": ["shotgun", "sniper", "assault", "smg", "pistol"]
    },
    "dota 2": {
        "aliases": ["dota", "dota2"],
        "type": "moba",
        "advice_templates": [
            "Roshan está disponible - considera hacerlo",
            "El enemigo tiene {items} - necesitas {counter_item}",
            "Tu {role} debe {action} ahora",
            "El courier está {status} - {action}",
            "La runa {rune} está disponible en {location}",
            "El enemigo usó {ability} - tienes {cooldown}s",
            "Tu team está en {location} - únete",
            "La torre {tower} está siendo atacada - {action}",
            "El enemigo tiene {team_comp} - juega {playstyle}",
            "El Aegis está en {location} - {action}"
        ],
        "critical_elements": ["torres", "ros han", "runas", "courier", "items"],
        "roles": {"carry", "mid", "offlane", "support", "hard_support"}
    },
    "overwatch": {
        "aliases": ["ow", "overwatch"],
        "type": "fps",
        "advice_templates": [
            "El enemigo tiene {hero} - cambia a {counter}",
            "Tu ultimate está {status} - {advice}",
            "El punto está siendo capturado - {action}",
            "El enemigo está en {location} - {action}",
            "Tu salud: {health} - necesitas {advice}",
            "El tiempo se acaba - {action} rápido",
            "El enemigo tiene {advantage} - juega {playstyle}",
            "Tu equipo necesita {role} - cambia",
            "El payload está en {progress} - {action}",
            "El enemigo está ultimando - {action}"
        ],
        "critical_elements": ["punto", "payload", "ultimate", "vida", "heroes"],
        "heroes": ["tracer", "genji", "hanzo", "widow", "mercy", "rein", "zarya", "dva"]
    },
    "apex legends": {
        "aliases": ["apex", "apex legends"],
        "type": "battle_royale",
        "advice_templates": [
            "Enemigos en {location} - {action}",
            "Tu salud: {health} - {advice}",
            "El círculo se cierra en {direction} - corre",
            "Tu legend {legend} tiene {ability} disponible - úsala",
            "El enemigo tiene {weapon} - juega {playstyle}",
            "El botín en {location} - ve por él",
            "El ring se acerca - {time} segundos",
            "El enemigo está en {height} - {action}",
            "Tu equipo está {status} - {action}",
            "El care package está en {location} - ve por él"
        ],
        "critical_elements": ["círculo", "vida", "escudo", "botín", "leyendas"],
        "legends": ["wraith", "bloodhound", "lifeline", "gibraltar", "pathfinder", "octane"]
    },
    "minecraft": {
        "aliases": ["minecraft", "mc"],
        "type": "sandbox",
        "advice_templates": [
            "Tu hambre: {hunger} - necesitas comer",
            "Nivel {level} - puedes mejorar {advice}",
            "El bioma es {biome} - encuentra {resources}",
            "Hay {mobs} cerca - {action}",
            "Tu inventario está lleno - organiza",
            "La noche se acerca - {action}",
            "Tienes {armor} - necesitas {advice}",
            "Hay {resource} en {location} - mina",
            "Puedes hacer {craft} - te ayudará",
            "El enemigo {mob} está cerca - {action}"
        ],
        "critical_elements": ["hambre", "vida", "armadura", "herramientas", "recursos"],
        "mobs": ["zombie", "skeleton", "creeper", "spider", "enderman"]
    },
    "gta v": {
        "aliases": ["gta", "gta v", "gta 5"],
        "type": "action",
        "advice_templates": [
            "La policía está en {level} - {action}",
            "Tu vehículo está {status} - necesitas {advice}",
            "El objetivo está en {location} - ve",
            "Tu salud: {health} - {advice}",
            "Hay {enemies} enemigos - {action}",
            "El tiempo se acaba - {action} rápido",
            "Tu arma {weapon} tiene {ammo} balas - recarga",
            "El enemigo está en {position} - {action}",
            "Tu misión es {mission} - {advice}",
            "El dinero: ${money} - puedes {action}"
        ],
        "critical_elements": ["policía", "vehículos", "armas", "vida", "misión"]
    }
}

# ─── DETECTOR DE JUEGOS ───────────────────────────────────────────────────
class GameDetector:
    """Detecta el juego actual basado en la ventana activa."""
    
    @staticmethod
    def detect_current_game() -> Optional[Dict]:
        """
        Detecta el juego actual basado en la ventana activa.
        
        Returns:
            Dict con información del juego o None si no se detecta
        """
        if not gw:
            return None
        
        try:
            # Obtener ventana activa
            window = gw.getActiveWindow()
            if not window:
                return None
            
            title = window.title.lower()
            process_name = window._hWnd if hasattr(window, '_hWnd') else ""
            
            # Buscar en la base de datos
            for game_name, game_info in GAME_DATABASE.items():
                # Verificar alias
                for alias in game_info.get("aliases", []):
                    if alias in title:
                        return {
                            "name": game_name,
                            "title": title,
                            "window": window,
                            "info": game_info
                        }
                
                # Verificar nombre del juego
                if game_name in title:
                    return {
                        "name": game_name,
                        "title": title,
                        "window": window,
                        "info": game_info
                    }
            
            # No se detectó ningún juego conocido
            return None
            
        except Exception as e:
            print(f"[GameCompanion] Error detectando juego: {e}")
            return None
    
    @staticmethod
    def detect_from_screenshot() -> Optional[str]:
        """
        Detecta el juego analizando una captura de pantalla.
        Usa elementos visuales característicos.
        """
        try:
            if not pyautogui:
                return None
            
            # Tomar captura
            screenshot = pyautogui.screenshot()
            
            # Detectar colores/patrones característicos
            # Por ahora, esto es un placeholder para análisis visual avanzado
            # En producción, usaría OpenCV o un modelo de IA
            
            return None
            
        except:
            return None


# ─── GENERADOR DE CONSEJOS ──────────────────────────────────────────────
class AdviceGenerator:
    """Genera consejos tácticos para diferentes juegos."""
    
    @staticmethod
    def generate_advice(game_name: str, game_info: Dict, context: Dict) -> str:
        """
        Genera un consejo táctico basado en el juego y el contexto.
        
        Args:
            game_name: Nombre del juego
            game_info: Información del juego
            context: Contexto detectado (salud, posición, etc.)
        
        Returns:
            Consejo táctico
        """
        templates = game_info.get("advice_templates", [])
        if not templates:
            return "Analizando tu juego... Consejo en breve."
        
        # Seleccionar una plantilla aleatoria
        import random
        template = random.choice(templates)
        
        # Rellenar la plantilla con el contexto
        advice = template.format(**context) if context else template
        
        # Limpiar y formatear
        advice = advice.replace("_", " ").strip()
        advice = advice[0].upper() + advice[1:] if advice else advice
        
        return advice
    
    @staticmethod
    def get_critical_advice(game_name: str, game_info: Dict, context: Dict) -> str:
        """
        Obtiene consejos críticos basados en elementos importantes del juego.
        """
        critical_elements = game_info.get("critical_elements", [])
        advice = []
        
        # Verificar elementos críticos en el contexto
        for element in critical_elements:
            if element in context:
                if element == "vida" and context.get("vida", 100) < 30:
                    advice.append("⚠️ ¡Salud crítica! Busca cobertura.")
                elif element == "salud" and context.get("salud", 100) < 30:
                    advice.append("⚠️ ¡Salud crítica! Cúrate.")
                elif element == "dinero" and context.get("dinero", 0) < 5000:
                    advice.append("💰 Poco dinero - ahorra para la próxima ronda.")
                elif element == "materiales" and context.get("materiales", 0) < 100:
                    advice.append("🧱 Pocos materiales - construye con cuidado.")
                elif element == "hambre" and context.get("hambre", 20) < 10:
                    advice.append("🍖 ¡Hambre baja! Necesitas comer.")
                elif element == "escudo" and context.get("escudo", 100) < 30:
                    advice.append("🛡️ Escudo bajo - busca recarga.")
        
        if advice:
            return "\n".join(advice)
        return None


# ─── ANALIZADOR DE JUEGOS ──────────────────────────────────────────────
class GameAnalyzer:
    """Analiza el juego actual y extrae contexto."""
    
    @staticmethod
    def analyze_game_with_vision(game_name: str, player=None) -> Dict:
        """
        Usa visión para analizar el juego actual y extraer contexto.
        """
        context = {
            "location": "la pantalla",
            "action": "mantente alerta",
            "advice": "sigue jugando"
        }
        
        try:
            # Construir prompt específico para el juego
            prompts = {
                "league of legends": """
                    Analiza esta pantalla de League of Legends y extrae:
                    - Vida aproximada del jugador (baja/media/alta)
                    - Maná disponible (bajo/medio/alto)
                    - ¿Hay enemigos visibles en el minimapa? (sí/no/cuantos)
                    - ¿Está el jugador en línea o en base?
                    - ¿Hay objetivos disponibles? (Dragón/Barón/Heraldo)
                    - ¿Cómo está la torre? (baja/media/alta)
                    - ¿Tiene visión en el río?
                    Responde en español.
                """,
                "valorant": """
                    Analiza esta pantalla de Valorant y extrae:
                    - Vida del jugador (baja/media/alta)
                    - ¿Tiene escudo? (sí/no)
                    - ¿Está la bomba plantada? (sí/no/dónde)
                    - ¿Hay enemigos visibles? (sí/no/cuantos)
                    - ¿Tiene ulti disponible? (sí/no)
                    - ¿Está en el sitio o en rotación?
                    Responde en español.
                """,
                "counter strike": """
                    Analiza esta pantalla de CS:GO/CS2 y extrae:
                    - Vida del jugador (baja/media/alta)
                    - Dinero disponible (bajo/medio/alto)
                    - ¿Está la bomba plantada? (sí/no)
                    - ¿Hay enemigos visibles? (sí/no/cuantos)
                    - ¿Qué ronda es? (eco/semi/arma)
                    - ¿Tiene utilidad? (flash/smoke/molotov)
                    Responde en español.
                """,
                "fortnite": """
                    Analiza esta pantalla de Fortnite y extrae:
                    - Vida del jugador (baja/media/alta)
                    - Escudo (bajo/medio/alto)
                    - Materiales (pocos/muchos)
                    - ¿Está en el círculo? (sí/no)
                    - ¿Hay enemigos cerca? (sí/no)
                    - ¿Tiene buena posición? (alta/baja)
                    Responde en español.
                """,
                "minecraft": """
                    Analiza esta pantalla de Minecraft y extrae:
                    - Vida (baja/media/alta)
                    - Hambre (baja/media/alta)
                    - Nivel de experiencia
                    - ¿Es de día o noche?
                    - ¿Hay mobs cerca? (sí/no)
                    - ¿Qué bioma parece?
                    Responde en español.
                """
            }
            
            # Usar el prompt específico del juego o uno genérico
            prompt = prompts.get(game_name, f"""
                Analiza esta pantalla del juego {game_name} y extrae:
                - Estado del jugador (vida, recursos)
                - Situación actual (posición, enemigos)
                - Información útil para dar un consejo táctico
                Responde en español.
            """)
            
            # Llamar a screen_vision
            vision_params = {
                "action": "describe",
                "query": prompt
            }
            
            if player:
                player.write_log(f"🎮 Analizando {game_name} con visión...")
            
            response = screen_vision(vision_params, player)
            
            # Intentar extraer contexto del análisis
            context = GameAnalyzer._extract_context_from_vision(response, game_name)
            
            return context
            
        except Exception as e:
            print(f"[GameCompanion] Error en análisis visual: {e}")
            return context
    
    @staticmethod
    def _extract_context_from_vision(response: str, game_name: str) -> Dict:
        """Extrae contexto de la respuesta de visión."""
        context = {
            "location": "la pantalla",
            "action": "mantente alerta",
            "advice": "sigue jugando"
        }
        
        # Extraer información de la respuesta
        response_lower = response.lower()
        
        # Salud
        if "baja" in response_lower or "crítica" in response_lower:
            if "vida" in response_lower or "salud" in response_lower:
                context["health"] = "baja"
                context["vida"] = "baja"
        elif "alta" in response_lower or "llena" in response_lower:
            if "vida" in response_lower or "salud" in response_lower:
                context["health"] = "alta"
                context["vida"] = "alta"
        else:
            context["health"] = "media"
            context["vida"] = "media"
        
        # Enemigos
        if "enemigo" in response_lower or "enemigos" in response_lower:
            numbers = re.findall(r'\d+', response_lower)
            if numbers:
                context["enemies"] = numbers[0]
                context["count"] = numbers[0]
            else:
                context["enemies"] = "varios"
                context["count"] = "varios"
        else:
            context["enemies"] = "ninguno"
            context["count"] = "ninguno"
        
        # Posición
        if "línea" in response_lower or "lane" in response_lower:
            context["location"] = "tu línea"
        elif "base" in response_lower:
            context["location"] = "la base"
        elif "torre" in response_lower or "tower" in response_lower:
            context["location"] = "cerca de torre"
        elif "río" in response_lower or "river" in response_lower:
            context["location"] = "el río"
        elif "jungla" in response_lower:
            context["location"] = "la jungla"
        
        return context


# ─── CLASE PRINCIPAL ─────────────────────────────────────────────────────
class GameCompanionPro:
    """Asistente táctico para videojuegos."""
    
    def __init__(self):
        self.current_game = None
        self.detector = GameDetector()
        self.analyzer = GameAnalyzer()
        self.generator = AdviceGenerator()
        self.advice_history = []
        self.last_advice = ""
    
    def analyze_current_game(self, player=None) -> str:
        """
        Analiza el juego actual y genera un consejo táctico.
        """
        # 1. Detectar el juego
        game = self.detector.detect_current_game()
        
        if not game:
            # Intentar detectar por screenshot
            detected = self.detector.detect_from_screenshot()
            if detected:
                game = {
                    "name": detected,
                    "info": GAME_DATABASE.get(detected, {}),
                    "title": "desconocido",
                    "window": None
                }
        
        if not game:
            return "🎮 No detecté ningún juego conocido en tu pantalla.\n\n" \
                   "💡 Juegos soportados:\n" \
                   "• League of Legends\n" \
                   "• Valorant\n" \
                   "• CS:GO / CS2\n" \
                   "• Fortnite\n" \
                   "• Dota 2\n" \
                   "• Overwatch\n" \
                   "• Apex Legends\n" \
                   "• Minecraft\n" \
                   "• GTA V"
        
        self.current_game = game
        
        # 2. Analizar con visión
        game_name = game.get("name")
        game_info = game.get("info", {})
        
        if player:
            player.write_log(f"🎮 {game_name} detectado - Analizando...")
        
        # Obtener contexto
        context = self.analyzer.analyze_game_with_vision(game_name, player)
        
        # 3. Generar consejo
        advice = self.generator.generate_advice(game_name, game_info, context)
        
        # 4. Verificar elementos críticos
        critical = self.generator.get_critical_advice(game_name, game_info, context)
        if critical:
            advice += "\n" + critical
        
        # Guardar historial
        self.advice_history.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "game": game_name,
            "advice": advice,
            "context": context
        })
        
        # Limitar historial
        if len(self.advice_history) > 50:
            self.advice_history = self.advice_history[-50:]
        
        self.last_advice = advice
        
        # 5. Formatear respuesta
        response = f"🎮 {game_name.upper()}\n"
        response += "━" * 40 + "\n"
        response += f"💡 Consejo: {advice}\n"
        
        # Añadir contexto detectado
        if context:
            response += "\n📊 Contexto detectado:\n"
            for key, value in context.items():
                if key not in ["advice", "action"]:
                    response += f"  • {key}: {value}\n"
        
        return response
    
    def get_advice_history(self, limit: int = 5) -> str:
        """Obtiene el historial de consejos."""
        if not self.advice_history:
            return "📭 No hay consejos en el historial."
        
        recent = self.advice_history[-limit:]
        lines = [f"📋 Historial de consejos (últimos {len(recent)})", "━" * 40]
        
        for entry in recent:
            lines.append(f"🕐 {entry.get('timestamp')} - {entry.get('game')}")
            lines.append(f"💡 {entry.get('advice')[:80]}...")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_current_context(self) -> str:
        """Obtiene el contexto actual del juego."""
        if not self.current_game:
            return "🎮 No hay juego activo."
        
        context = self.analyzer.analyze_game_with_vision(
            self.current_game.get("name", "desconocido")
        )
        
        lines = [f"📊 CONTEXTO ACTUAL ({self.current_game.get('name', 'desconocido').upper()})", "━" * 40]
        for key, value in context.items():
            if key not in ["advice", "action"]:
                lines.append(f"  • {key}: {value}")
        
        return "\n".join(lines)


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_companion: Optional[GameCompanionPro] = None

def get_companion() -> GameCompanionPro:
    """Obtiene la instancia del Game Companion."""
    global _companion
    if _companion is None:
        _companion = GameCompanionPro()
    return _companion


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def game_companion(parameters: Dict, player=None) -> str:
    """
    Asistente táctico para videojuegos con análisis visual.
    
    Args:
        parameters: Diccionario con parámetros
            - action: analyze | history | context | games
            - game_name: Nombre del juego (opcional)
            - force: Forzar análisis
    
    Returns:
        Consejo táctico o información del juego
    """
    p = parameters or {}
    action = p.get("action", "analyze").strip().lower()
    game_name = p.get("game_name", "").strip()
    force = p.get("force", False)
    
    companion = get_companion()
    
    # ─── ANALIZAR ──────────────────────────────────────────────────────
    if action == "analyze":
        # Si se especifica un juego, forzar detección
        if game_name:
            # Buscar en la base de datos
            game_found = None
            for name, info in GAME_DATABASE.items():
                if game_name.lower() in name or game_name.lower() in [a for a in info.get("aliases", [])]:
                    game_found = {
                        "name": name,
                        "info": info,
                        "title": game_name,
                        "window": None
                    }
                    break
            
            if game_found:
                companion.current_game = game_found
        
        # Si no hay juego detectado, intentar detectar
        if not companion.current_game and not game_name:
            return companion.analyze_current_game(player)
        
        # Analizar el juego actual
        result = companion.analyze_current_game(player)
        
        # Añadir opciones adicionales
        result += "\n\n" + "━" * 40 + "\n"
        result += "💡 Comandos disponibles:\n"
        result += "  • action='analyze' - Nuevo consejo\n"
        result += "  • action='history' - Ver historial\n"
        result += "  • action='context' - Ver contexto actual\n"
        result += "  • action='games' - Ver juegos soportados"
        
        return result
    
    # ─── HISTORIAL ────────────────────────────────────────────────────
    elif action == "history":
        limit = int(p.get("limit", 5))
        return companion.get_advice_history(limit)
    
    # ─── CONTEXTO ────────────────────────────────────────────────────
    elif action == "context":
        return companion.get_current_context()
    
    # ─── JUEGOS SOPORTADOS ──────────────────────────────────────────
    elif action == "games":
        lines = ["🎮 JUEGOS SOPORTADOS", "━" * 40]
        
        for game_name, game_info in GAME_DATABASE.items():
            aliases = game_info.get("aliases", [])
            lines.append(f"  🎯 {game_name.title()}")
            if aliases:
                lines.append(f"     • Alias: {', '.join(aliases[:3])}")
            lines.append(f"     • Tipo: {game_info.get('type', 'N/A')}")
        
        lines.append("")
        lines.append("💡 Usa game_name='nombre' para analizar un juego específico")
        
        return "\n".join(lines)
    
    # ─── AYUDA ──────────────────────────────────────────────────────
    else:
        return (
            "🎮 GAME COMPANION PRO\n"
            "━" * 40 + "\n\n"
            "📖 Comandos disponibles:\n\n"
            "🔍 analyze - Analizar juego actual\n"
            "   Ejemplo: {'action':'analyze'}\n"
            "   Específico: {'action':'analyze','game_name':'valorant'}\n\n"
            "📋 history - Ver historial de consejos\n"
            "   Ejemplo: {'action':'history','limit':5}\n\n"
            "📊 context - Ver contexto actual\n"
            "   Ejemplo: {'action':'context'}\n\n"
            "🎮 games - Ver juegos soportados\n"
            "   Ejemplo: {'action':'games'}\n\n"
            "💡 Los consejos se generan en tiempo real usando visión por IA.\n"
            "   El sistema detecta automáticamente el juego en pantalla."
        )


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_game_companion():
    """Inicializa el Game Companion."""
    print("[GameCompanion] Inicializando...")
    print("[GameCompanion] ✅ Listo")
    return True