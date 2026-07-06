"""
knowledge_base.py — "Segundo cerebro" de NEXUS.
Sistema de gestión de conocimiento con persistencia JSON.
Soporta: CRUD, búsqueda avanzada, etiquetado, estadísticas y exportación.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from memory.config_manager import BASE_DIR
except ImportError:
    import sys
    BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent

# Constantes
KB_PATH = BASE_DIR / "config" / "knowledge_base.json"
VALID_TYPES = {"note", "idea", "snippet", "reference", "fact", "task", "question"}
MAX_DISPLAY = 20  # Máximo de resultados a mostrar en listados
PREVIEW_LENGTH = 60  # Longitud máxima del preview


class KnowledgeBaseError(Exception):
    """Excepción personalizada para errores de la base de conocimiento."""
    pass


def _load() -> Dict[str, Any]:
    """
    Carga la base de conocimiento desde disco.
    Nunca lanza excepción, siempre retorna un dict válido.
    """
    if not KB_PATH.exists():
        return {"entries": {}}
    
    try:
        data = json.loads(KB_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "entries" not in data:
            return {"entries": {}}
        return data
    except (json.JSONDecodeError, OSError):
        return {"entries": {}}


def _save(data: Dict[str, Any]) -> bool:
    """
    Guarda la base de conocimiento en disco.
    Retorna True si fue exitoso, False en caso de error.
    """
    try:
        KB_PATH.parent.mkdir(parents=True, exist_ok=True)
        KB_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8"
        )
        return True
    except OSError as e:
        print(f"[knowledge_base] Error de escritura: {e}")
        return False


def _generate_id() -> str:
    """Genera un ID corto único usando UUID."""
    return uuid.uuid4().hex[:8]


def _format_entry(eid: str, entry: Dict[str, Any], full: bool = False) -> str:
    """
    Formatea una entrada para su presentación.
    
    Args:
        eid: ID de la entrada
        entry: Diccionario con los datos de la entrada
        full: Si es True, muestra el contenido completo
    
    Returns:
        String formateado
    """
    title = entry.get("title", "Sin título")
    etype = entry.get("type", "note")
    tags = entry.get("tags", "")
    created = entry.get("created_at", "")[:16].replace("T", " ")
    
    if full:
        content = entry.get("content", "")
        tag_str = f" | Tags: {tags}" if tags else ""
        return f"[{eid}] {title} ({etype}){tag_str}\nCreado: {created}\n{content}"
    
    content = entry.get("content", "")
    preview = content[:PREVIEW_LENGTH]
    if len(content) > PREVIEW_LENGTH:
        preview += "…"
    return f"[{eid}] {title} ({etype}) — {preview}"


def _search_entries(entries: Dict[str, Any], query: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Busca entradas que coincidan con la consulta.
    Busca en título, contenido y tags.
    """
    query_lower = query.lower()
    results = []
    
    for eid, entry in entries.items():
        # Crear un texto de búsqueda combinando todos los campos relevantes
        search_text = " ".join([
            entry.get("title", ""),
            entry.get("content", ""),
            entry.get("tags", "")
        ]).lower()
        
        if query_lower in search_text:
            results.append((eid, entry))
    
    # Ordenar por fecha de creación (más reciente primero)
    results.sort(
        key=lambda x: x[1].get("created_at", ""),
        reverse=True
    )
    return results


def knowledge_base(parameters: dict, player=None) -> str:
    """
    Función principal de la base de conocimiento.
    Maneja todas las acciones disponibles.
    
    Args:
        parameters: Diccionario con los parámetros de la acción
        player: Objeto player (no usado actualmente)
    
    Returns:
        Mensaje de respuesta formateado
    """
    # Normalizar parámetros
    p = parameters or {}
    
    # Manejar acción con posibles slashes (ej: "add/save/store")
    action_raw = p.get("action", "").strip().lower()
    if "/" in action_raw:
        # Tomar el primer elemento antes del slash
        action = action_raw.split("/")[0].strip()
    else:
        action = action_raw
    
    # Cargar datos
    data = _load()
    entries = data["entries"]
    
    try:
        # ─── ACCIÓN: Guardar ────────────────────────────────────────────
        if action in ("add", "save", "store"):
            title = p.get("title", "").strip()
            content = p.get("content", "").strip()
            entry_type = p.get("type", "note").strip().lower()
            tags = p.get("tags", "").strip()
            
            if not content and not title:
                return "⚠️ No se especificó contenido ni título para guardar."
            
            if entry_type not in VALID_TYPES:
                entry_type = "note"
            
            if not title:
                title = content[:40] + "…" if len(content) > 40 else content
            
            entry_id = _generate_id()
            entries[entry_id] = {
                "title": title,
                "content": content,
                "type": entry_type,
                "tags": tags,
                "created_at": datetime.now().isoformat()
            }
            
            if not _save(data):
                return "❌ Error al guardar en la base de conocimiento (fallo de disco)."
            
            return f"✅ Guardado en la base de conocimiento [{entry_id}]: {title}"
        
        # ─── ACCIÓN: Buscar ────────────────────────────────────────────
        elif action in ("search", "find"):
            query = p.get("query", "").strip()
            
            if not query:
                return "ℹ️ Especificá un término de búsqueda."
            
            results = _search_entries(entries, query)
            
            if not results:
                return f"🔍 No se encontraron resultados para '{query}'."
            
            # Mostrar hasta MAX_DISPLAY resultados
            display_results = results[:MAX_DISPLAY]
            lines = [_format_entry(eid, entry) for eid, entry in display_results]
            
            total = len(results)
            suffix = f"\n… y {total - MAX_DISPLAY} más." if total > MAX_DISPLAY else ""
            
            return f"🔍 Resultados para '{query}' ({total} encontrados):\n" + "\n".join(lines) + suffix
        
        # ─── ACCIÓN: Listar ─────────────────────────────────────────────
        elif action == "list":
            if not entries:
                return "📭 La base de conocimiento está vacía."
            
            # Ordenar por fecha de creación (más reciente primero)
            items = sorted(
                entries.items(),
                key=lambda x: x[1].get("created_at", ""),
                reverse=True
            )
            
            # Mostrar hasta MAX_DISPLAY entradas
            display_items = items[:MAX_DISPLAY]
            lines = [_format_entry(eid, entry) for eid, entry in display_items]
            
            suffix = f"\n… y {len(items) - MAX_DISPLAY} más." if len(items) > MAX_DISPLAY else ""
            
            return f"📚 Entradas guardadas ({len(entries)} total):\n" + "\n".join(lines) + suffix
        
        # ─── ACCIÓN: Ver entrada ────────────────────────────────────────
        elif action in ("get", "read", "view"):
            entry_id = p.get("entry_id", "").strip()
            
            if not entry_id or entry_id not in entries:
                return f"❌ No se encontró la entrada con ID '{entry_id}'."
            
            return _format_entry(entry_id, entries[entry_id], full=True)
        
        # ─── ACCIÓN: Actualizar ─────────────────────────────────────────
        elif action == "update":
            entry_id = p.get("entry_id", "").strip()
            
            if not entry_id or entry_id not in entries:
                return f"❌ No se encontró la entrada con ID '{entry_id}'."
            
            entry = entries[entry_id]
            updated = False
            
            # Actualizar campos según lo proporcionado
            if p.get("title"):
                entry["title"] = p["title"].strip()
                updated = True
            
            if p.get("content"):
                entry["content"] = p["content"].strip()
                updated = True
            
            if p.get("type") and p["type"].strip().lower() in VALID_TYPES:
                entry["type"] = p["type"].strip().lower()
                updated = True
            
            if p.get("tags") is not None:
                entry["tags"] = p["tags"].strip()
                updated = True
            
            if not updated:
                return "ℹ️ No se proporcionaron campos para actualizar."
            
            entry["updated_at"] = datetime.now().isoformat()
            
            if not _save(data):
                return "❌ Error al actualizar (fallo de disco)."
            
            return f"✅ Entrada [{entry_id}] actualizada: {entry['title']}"
        
        # ─── ACCIÓN: Eliminar ───────────────────────────────────────────
        elif action == "delete":
            entry_id = p.get("entry_id", "").strip()
            
            if not entry_id or entry_id not in entries:
                return f"❌ No se encontró la entrada con ID '{entry_id}'."
            
            title = entries[entry_id].get("title", "Sin título")
            del entries[entry_id]
            
            if not _save(data):
                return "❌ Error al eliminar (fallo de disco)."
            
            return f"🗑️ Entrada eliminada: {title}"
        
        # ─── ACCIÓN: Estadísticas ──────────────────────────────────────
        elif action == "stats":
            if not entries:
                return "📊 La base de conocimiento está vacía."
            
            # Estadísticas por tipo
            by_type = {}
            for entry in entries.values():
                entry_type = entry.get("type", "note")
                by_type[entry_type] = by_type.get(entry_type, 0) + 1
            
            # Ordenar por cantidad descendente
            breakdown = ", ".join(
                f"{k}: {v}" for k, v in sorted(by_type.items(), key=lambda x: -x[1])
            )
            
            # Calcular tamaño del archivo
            file_size = KB_PATH.stat().st_size if KB_PATH.exists() else 0
            size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
            
            return (
                f"📊 Estadísticas de la base de conocimiento:\n"
                f"Total de entradas: {len(entries)}\n"
                f"Por tipo: {breakdown}\n"
                f"Archivo: {KB_PATH} ({size_str})"
            )
        
        # ─── ACCIÓN: Exportar ──────────────────────────────────────────
        elif action == "export":
            dest_path = p.get("path", "").strip()
            
            if not dest_path:
                # Ruta por defecto: descargas
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = str(Path.home() / "Downloads" / f"nexus_knowledge_{timestamp}.json")
            
            try:
                dest = Path(dest_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8"
                )
                return f"💾 Base de conocimiento exportada a: {dest_path}"
            except OSError as e:
                return f"❌ Error al exportar: {e}"
        
        # ─── ACCIÓN: Ayuda ─────────────────────────────────────────────
        else:
            return (
                f"📖 Acción desconocida: '{action}'\n\n"
                "Acciones disponibles:\n"
                "• add (o save, store) - Guardar nueva entrada\n"
                "• search (o find) - Buscar entradas\n"
                "• list - Listar todas las entradas\n"
                "• get (o read, view) - Ver entrada específica\n"
                "• update - Actualizar entrada\n"
                "• delete - Eliminar entrada\n"
                "• stats - Ver estadísticas\n"
                "• export - Exportar a JSON\n\n"
                "Ejemplos:\n"
                '  add: action="add" title="Mi nota" content="Contenido" type="note" tags="python,ia"\n'
                '  search: action="search" query="python"\n'
                '  update: action="update" entry_id="abc123" content="Nuevo contenido"'
            )
    
    except Exception as e:
        # Capturar cualquier error inesperado
        return f"⚠️ Error inesperado: {str(e)}"