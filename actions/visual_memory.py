"""
Visual Memory & Desktop Context
===============================
Sistema avanzado de memoria visual que registra ventanas activas,
contexto de escritorio y permite búsquedas inteligentes.
"""

import json
import time
import threading
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import deque

try:
    import pygetwindow as gw
    import pyautogui
except ImportError:
    gw = None
    pyautogui = None

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

# Configuración
MEMORY_FILE = Path("config/visual_memory.json")
CONTEXT_FILE = Path("config/context_history.json")
SCREENSHOT_DIR = Path("config/screenshots")
MAX_ENTRIES = 5000
MAX_SCREENSHOTS = 50
MEMORY_INTERVAL = 15  # Segundos entre registros
CLEANUP_INTERVAL = 300  # 5 minutos

_memory_thread = None
_running = False


class VisualMemory:
    """Gestor de memoria visual y contexto de escritorio."""
    
    def __init__(self):
        self.entries: deque = deque(maxlen=MAX_ENTRIES)
        self.last_title = ""
        self.last_window = None
        self.context_cache = {}
        self._load()
    
    def _load(self):
        """Carga la memoria desde disco."""
        if MEMORY_FILE.exists():
            try:
                data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.entries = deque(data, maxlen=MAX_ENTRIES)
                    if self.entries:
                        self.last_title = self.entries[-1].get("title", "")
            except Exception:
                pass
    
    def _save(self):
        """Guarda la memoria en disco."""
        try:
            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            MEMORY_FILE.write_text(
                json.dumps(list(self.entries), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            return True
        except Exception:
            return False
    
    def add_entry(self, title: str, window_info: Optional[Dict] = None):
        """Añade una entrada a la memoria."""
        if not title or title == self.last_title:
            return
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "title": title,
            "window_info": window_info or {},
            "context": self._get_context()
        }
        
        self.entries.append(entry)
        self.last_title = title
        self._save()
        
        # Limpieza periódica
        if len(self.entries) % 100 == 0:
            self._cleanup()
    
    def _get_context(self) -> Dict:
        """Obtiene contexto adicional del sistema."""
        context = {
            "time": datetime.now().strftime("%H:%M"),
            "day": datetime.now().strftime("%A"),
            "session_start": self._get_session_start()
        }
        
        # Detectar modo de trabajo
        if "visual studio" in self.last_title.lower() or "vscode" in self.last_title.lower():
            context["mode"] = "development"
        elif "excel" in self.last_title.lower() or "word" in self.last_title.lower():
            context["mode"] = "office"
        elif "chrome" in self.last_title.lower() or "firefox" in self.last_title.lower():
            context["mode"] = "browsing"
        elif "notion" in self.last_title.lower() or "obsidian" in self.last_title.lower():
            context["mode"] = "notes"
        
        return context
    
    def _get_session_start(self) -> str:
        """Obtiene el inicio de la sesión actual."""
        if self.entries:
            first = self.entries[0]
            return first.get("timestamp", datetime.now().isoformat())
        return datetime.now().isoformat()
    
    def _cleanup(self):
        """Limpia entradas antiguas y duplicadas."""
        # Eliminar entradas duplicadas consecutivas
        cleaned = []
        last_title = ""
        for entry in self.entries:
            if entry["title"] != last_title:
                cleaned.append(entry)
                last_title = entry["title"]
        
        # Mantener solo las últimas MAX_ENTRIES
        if len(cleaned) > MAX_ENTRIES:
            cleaned = cleaned[-MAX_ENTRIES:]
        
        self.entries = deque(cleaned, maxlen=MAX_ENTRIES)
        self._save()
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca entradas que coincidan con la consulta."""
        if not query:
            return list(self.entries)[-limit:]
        
        results = []
        query_lower = query.lower()
        query_words = query_lower.split()
        
        for entry in reversed(self.entries):
            title = entry.get("title", "").lower()
            context = str(entry.get("context", {})).lower()
            
            # Búsqueda por palabra clave
            score = 0
            for word in query_words:
                if word in title:
                    score += 2
                if word in context:
                    score += 1
            
            if score > 0 or query_lower in title:
                results.append((score, entry))
                if len(results) >= limit * 2:  # Recoger más para filtrar
                    break
        
        # Ordenar por relevancia
        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:limit]]
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de la memoria."""
        if not self.entries:
            return {"total": 0}
        
        # Contar aplicaciones más usadas
        app_counter = {}
        for entry in self.entries:
            title = entry.get("title", "")
            # Extraer nombre de la aplicación
            app = title.split(" - ")[-1] if " - " in title else title[:30]
            app_counter[app] = app_counter.get(app, 0) + 1
        
        # Top apps
        top_apps = sorted(app_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Calcular tiempo entre entradas
        timestamps = [entry.get("timestamp") for entry in self.entries if entry.get("timestamp")]
        if len(timestamps) > 1:
            try:
                times = [datetime.fromisoformat(ts) for ts in timestamps if ts]
                diffs = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
                avg_switch = sum(diffs) / len(diffs) if diffs else 0
            except:
                avg_switch = 0
        else:
            avg_switch = 0
        
        return {
            "total": len(self.entries),
            "unique_apps": len(app_counter),
            "top_apps": top_apps,
            "avg_switch_seconds": round(avg_switch, 1),
            "session_start": self._get_session_start() if self.entries else None,
            "last_entry": self.entries[-1].get("title") if self.entries else None
        }
    
    def get_timeline(self, hours: int = 24) -> List[Dict]:
        """Obtiene la línea de tiempo de las últimas horas."""
        cutoff = datetime.now() - timedelta(hours=hours)
        result = []
        for entry in reversed(self.entries):
            try:
                ts = datetime.fromisoformat(entry.get("timestamp", ""))
                if ts > cutoff:
                    result.append(entry)
                else:
                    break
            except:
                continue
        return result
    
    def take_screenshot(self) -> Optional[str]:
        """Toma una captura de pantalla y la guarda."""
        if not ImageGrab:
            return None
        
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = SCREENSHOT_DIR / f"context_{timestamp}.png"
            
            screenshot = ImageGrab.grab()
            screenshot.save(filename)
            
            # Limpiar capturas antiguas
            self._cleanup_screenshots()
            
            return str(filename)
        except Exception:
            return None
    
    def _cleanup_screenshots(self):
        """Mantiene solo las últimas MAX_SCREENSHOTS capturas."""
        try:
            screenshots = sorted(SCREENSHOT_DIR.glob("context_*.png"))
            if len(screenshots) > MAX_SCREENSHOTS:
                for old in screenshots[:-MAX_SCREENSHOTS]:
                    old.unlink()
        except Exception:
            pass


# Instancia global
_memory = VisualMemory()


def _memory_loop():
    """Bucle principal de la memoria visual."""
    last_screenshot = 0
    screenshot_interval = 300  # Cada 5 minutos
    
    while _running:
        try:
            if gw:
                active_window = gw.getActiveWindow()
                if active_window and active_window.title:
                    title = active_window.title.strip()
                    if title:
                        # Obtener información de la ventana
                        window_info = {
                            "x": active_window.left,
                            "y": active_window.top,
                            "width": active_window.width,
                            "height": active_window.height,
                            "is_minimized": active_window.isMinimized
                        } if hasattr(active_window, 'left') else {}
                        
                        _memory.add_entry(title, window_info)
                        
                        # Captura de pantalla periódica
                        current_time = time.time()
                        if current_time - last_screenshot > screenshot_interval:
                            _memory.take_screenshot()
                            last_screenshot = current_time
                        
        except Exception:
            pass
        
        time.sleep(MEMORY_INTERVAL)


def start_visual_memory():
    """Inicia el servicio de memoria visual."""
    global _memory_thread, _running
    if not _running:
        _running = True
        _memory_thread = threading.Thread(target=_memory_loop, daemon=True)
        _memory_thread.start()
        return True
    return False


def stop_visual_memory():
    """Detiene el servicio de memoria visual."""
    global _running
    _running = False
    if _memory_thread:
        _memory_thread.join(timeout=2)
    return True


def visual_memory(parameters: Dict[str, Any], player=None) -> str:
    """
    Gestor de memoria visual y contexto de escritorio.
    
    Args:
        parameters: Diccionario con parámetros:
            - action: "search", "stats", "timeline", "screenshot", 
                      "start", "stop", "status", "clean"
            - query: Término de búsqueda
            - limit: Límite de resultados
            - hours: Horas para timeline
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "search").lower()
    query = p.get("query", "").strip()
    limit = int(p.get("limit", 10))
    hours = int(p.get("hours", 24))
    
    # ─── INICIAR ──────────────────────────────────────────────
    if action == "start":
        if start_visual_memory():
            return "👁️ Memoria Visual iniciada en segundo plano."
        return "❌ Error al iniciar la memoria visual."
    
    # ─── DETENER ──────────────────────────────────────────────
    elif action == "stop":
        if stop_visual_memory():
            return "⏹️ Memoria Visual detenida."
        return "❌ Error al detener la memoria visual."
    
    # ─── ESTADO ──────────────────────────────────────────────
    elif action == "status":
        status = "🟢 Activo" if _running else "🔴 Inactivo"
        total = len(_memory.entries)
        return f"📊 Memoria Visual: {status}\nEntradas: {total}"
    
    # ─── BUSCAR ──────────────────────────────────────────────
    elif action == "search" or action == "find":
        if not _memory.entries:
            return "❌ No hay memoria visual guardada aún."
        
        if not query:
            # Mostrar últimas entradas
            recent = list(_memory.entries)[-5:]
            lines = [f"🕐 {e.get('timestamp', '')[:19]}: {e.get('title', '')}" 
                    for e in reversed(recent)]
            return "🕰️ Últimas actividades:\n" + "\n".join(lines)
        
        results = _memory.search(query, limit)
        
        if results:
            lines = []
            for entry in results:
                timestamp = entry.get('timestamp', '')[:19]
                title = entry.get('title', '')
                context = entry.get('context', {})
                mode = context.get('mode', '')
                mode_emoji = {
                    'development': '💻',
                    'office': '📊',
                    'browsing': '🌐',
                    'notes': '📝'
                }.get(mode, '')
                
                lines.append(f"{mode_emoji} {timestamp}: {title}")
            
            return f"🧠 Resultados para '{query}':\n" + "\n".join(lines)
        else:
            return f"🧠 No recuerdo haber visto nada relacionado con '{query}'."
    
    # ─── ESTADÍSTICAS ─────────────────────────────────────────
    elif action == "stats" or action == "statistics":
        stats = _memory.get_stats()
        if stats["total"] == 0:
            return "📊 No hay datos estadísticos disponibles."
        
        lines = [
            f"📊 Estadísticas de Memoria Visual",
            f"📝 Total de entradas: {stats['total']}",
            f"🔄 Apps únicas: {stats['unique_apps']}",
            f"⏱️ Cambio promedio: {stats['avg_switch_seconds']}s",
            f"📅 Sesión iniciada: {stats.get('session_start', 'N/A')[:16]}",
            f"📌 Última actividad: {stats.get('last_entry', 'N/A')[:50]}",
            "",
            "🏆 Top 5 aplicaciones:"
        ]
        
        for i, (app, count) in enumerate(stats.get('top_apps', [])[:5], 1):
            lines.append(f"  {i}. {app} ({count} veces)")
        
        return "\n".join(lines)
    
    # ─── LÍNEA DE TIEMPO ──────────────────────────────────────
    elif action == "timeline":
        timeline = _memory.get_timeline(hours)
        if not timeline:
            return f"📅 No hay actividad en las últimas {hours} horas."
        
        # Agrupar por hora
        grouped = {}
        for entry in timeline:
            try:
                ts = datetime.fromisoformat(entry.get('timestamp', ''))
                hour_key = ts.strftime("%H:00")
                if hour_key not in grouped:
                    grouped[hour_key] = []
                grouped[hour_key].append(entry.get('title', ''))
            except:
                continue
        
        lines = [f"📅 Línea de tiempo (últimas {hours} horas):"]
        for hour, titles in sorted(grouped.items()):
            lines.append(f"\n⏰ {hour}")
            for title in titles[:3]:  # Mostrar máximo 3 por hora
                lines.append(f"  • {title[:60]}")
            if len(titles) > 3:
                lines.append(f"  • ... y {len(titles)-3} más")
        
        return "\n".join(lines)
    
    # ─── CAPTURA DE PANTALLA ──────────────────────────────────
    elif action == "screenshot" or action == "capture":
        if not ImageGrab:
            return "❌ PIL/Pillow no instalado. No se pueden tomar capturas."
        
        filename = _memory.take_screenshot()
        if filename:
            return f"📸 Captura de pantalla guardada: {filename}"
        else:
            return "❌ Error al tomar captura de pantalla."
    
    # ─── LIMPIAR ──────────────────────────────────────────────
    elif action == "clean" or action == "clear":
        _memory.entries.clear()
        _memory.last_title = ""
        _memory._save()
        return "🧹 Memoria visual limpiada."
    
    # ─── EXPORTAR ─────────────────────────────────────────────
    elif action == "export":
        if not _memory.entries:
            return "❌ No hay datos para exportar."
        
        try:
            export_file = Path(f"config/visual_memory_export_{datetime.now().strftime('%Y%m%d')}.json")
            export_file.write_text(
                json.dumps(list(_memory.entries), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            return f"💾 Memoria exportada a: {export_file}"
        except Exception as e:
            return f"❌ Error al exportar: {e}"
    
    # ─── SUGERIR CONTEXTO ─────────────────────────────────────
    elif action == "context" or action == "suggest":
        if not _memory.entries:
            return "❌ No hay contexto disponible."
        
        # Analizar patrón actual
        last_entries = list(_memory.entries)[-10:]
        apps = [e.get('title', '').split(' - ')[-1] if ' - ' in e.get('title', '') else e.get('title', '')[:30] 
                for e in last_entries]
        
        # Detectar patrón
        if len(set(apps)) == 1:
            return f"🔍 Parece que estás enfocado en: {apps[0]}"
        elif len(set(apps)) > 5:
            return "🔄 Estás cambiando mucho de contexto. ¿Necesitas concentrarte?"
        else:
            return f"📋 Contexto actual: múltiples aplicaciones ({len(set(apps))} activas)"
    
    # ─── AYUDA ──────────────────────────────────────────────────
    else:
        return (
            "📖 Comandos de Memoria Visual:\n\n"
            "🔹 Iniciar/Detener:\n"
            "  action='start' - Inicia el servicio\n"
            "  action='stop' - Detiene el servicio\n"
            "  action='status' - Ver estado\n\n"
            "🔹 Buscar:\n"
            "  action='search' [query='término'] - Buscar en memoria\n"
            "  action='search' - Ver últimas actividades\n\n"
            "🔹 Estadísticas:\n"
            "  action='stats' - Ver estadísticas\n"
            "  action='timeline' [hours=24] - Línea de tiempo\n\n"
            "🔹 Utilidades:\n"
            "  action='screenshot' - Tomar captura\n"
            "  action='clean' - Limpiar memoria\n"
            "  action='export' - Exportar datos\n"
            "  action='context' - Sugerir contexto\n\n"
            "📌 Ejemplos:\n"
            "  {'action':'search','query':'visual studio'}\n"
            "  {'action':'stats'}\n"
            "  {'action':'timeline','hours':8}"
        )


# Iniciar automáticamente si se importa
if __name__ != "__main__":
    # Iniciar en segundo plano con un pequeño retraso
    threading.Timer(2.0, start_visual_memory).start()