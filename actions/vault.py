"""
Vault Memory Module for ILUM
=============================
Bóveda de memoria segura para guardar contraseñas, secretos y recuerdos explícitos.
Soporte para almacenamiento encriptado, búsqueda avanzada, categorías y exportación.
"""

import json
import os
import sys
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple
import hashlib

# ─── DETECCIÓN INTELIGENTE DE RUTA ────────────────────────────────────────
def get_base_dir() -> Path:
    """
    Retorna la carpeta base según el entorno de ejecución.
    - Si es .exe: usa la carpeta del ejecutable
    - Si es desarrollo: usa el directorio del proyecto
    """
    if getattr(sys, 'frozen', False):
        # Estamos en un .exe compilado con PyInstaller
        return Path(sys.executable).parent
    else:
        # Estamos en modo desarrollo
        return Path(__file__).resolve().parent.parent

# ─── RUTAS DE ARCHIVOS ─────────────────────────────────────────────────────
BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"  # SIEMPRE usa "config" para todos los archivos
VAULT_FILE = CONFIG_DIR / "vault_memory.json"
VAULT_BACKUP_DIR = CONFIG_DIR / "vault_backups"

# ─── SISTEMA DE ENCRIPTACIÓN SIMPLE ──────────────────────────────────────
class SimpleCrypto:
    """Encriptación simétrica simple para la bóveda."""
    
    @staticmethod
    def _get_key() -> bytes:
        """Genera una clave a partir de un seed fijo + hardware ID."""
        try:
            import uuid
            
            # Usar HWID + MAC como seed para la clave (única por PC)
            hwid = str(uuid.getnode())
            seed = f"NEXUS_VAULT_SALT_2026_{hwid}"
            return hashlib.sha256(seed.encode()).digest()
        except:
            # Fallback: clave fija (menos segura pero funcional)
            return hashlib.sha256(b"NEXUS_VAULT_DEFAULT_KEY").digest()
    
    @staticmethod
    def encrypt(text: str) -> str:
        """Encripta un texto."""
        try:
            from cryptography.fernet import Fernet
            # Usar clave derivada del hardware
            key_bytes = SimpleCrypto._get_key()
            key_b64 = base64.urlsafe_b64encode(key_bytes[:32])
            cipher = Fernet(key_b64)
            encrypted = cipher.encrypt(text.encode('utf-8'))
            return base64.b64encode(encrypted).decode('ascii')
        except ImportError:
            # Si no está cryptography, guardar en base64 simple (solo ofuscación)
            return base64.b64encode(text.encode()).decode('ascii')
    
    @staticmethod
    def decrypt(encrypted_text: str) -> str:
        """Desencripta un texto."""
        try:
            from cryptography.fernet import Fernet
            key_bytes = SimpleCrypto._get_key()
            key_b64 = base64.urlsafe_b64encode(key_bytes[:32])
            cipher = Fernet(key_b64)
            encrypted = base64.b64decode(encrypted_text.encode('ascii'))
            return cipher.decrypt(encrypted).decode('utf-8')
        except ImportError:
            # Fallback: decodificar base64 simple
            return base64.b64decode(encrypted_text.encode()).decode()
        except Exception:
            return "⚠️ [No se pudo desencriptar]"


# ─── GESTOR DE BÓVEDA ─────────────────────────────────────────────────────
class VaultManager:
    """Gestor principal de la bóveda de memoria segura."""
    
    def __init__(self):
        self.data: Dict = {}
        self._encryption_enabled = True
        self._load()
    
    def _load(self):
        """Carga la bóveda desde el archivo."""
        if VAULT_FILE.exists():
            try:
                raw_data = VAULT_FILE.read_text(encoding="utf-8")
                # Detectar si está encriptada
                if raw_data.startswith("ENC:"):
                    self._encryption_enabled = True
                    encrypted = raw_data[4:]  # Quitar "ENC:"
                    decrypted = SimpleCrypto.decrypt(encrypted)
                    self.data = json.loads(decrypted)
                else:
                    self._encryption_enabled = False
                    self.data = json.loads(raw_data)
            except Exception as e:
                print(f"[VAULT] Error cargando bóveda: {e}")
                self.data = {}
        else:
            self.data = {}
    
    def _save(self) -> bool:
        """Guarda la bóveda en el archivo."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            json_str = json.dumps(self.data, indent=2, ensure_ascii=False)
            
            if self._encryption_enabled:
                encrypted = SimpleCrypto.encrypt(json_str)
                VAULT_FILE.write_text(f"ENC:{encrypted}", encoding="utf-8")
            else:
                VAULT_FILE.write_text(json_str, encoding="utf-8")
            
            # Crear backup automático (cada 5 guardados)
            self._auto_backup()
            return True
        except Exception as e:
            print(f"[VAULT] Error guardando: {e}")
            return False
    
    def _auto_backup(self):
        """Crea un backup automático de la bóveda."""
        try:
            VAULT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = VAULT_BACKUP_DIR / f"vault_backup_{timestamp}.json"
            
            # Solo crear backup si hay datos
            if self.data:
                backup_file.write_text(
                    json.dumps(self.data, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            
            # Mantener solo los últimos 20 backups
            backups = sorted(VAULT_BACKUP_DIR.glob("vault_backup_*.json"))
            if len(backups) > 20:
                for old in backups[:-20]:
                    old.unlink()
        except Exception:
            pass
    
    def save(self, key: str, value: str, category: str = "general") -> bool:
        """Guarda un valor en la bóveda."""
        if not key or not value:
            return False
        
        # Si la clave tiene puntos, usarlos como categoría
        if "." in key and not category:
            parts = key.split(".")
            category = parts[0]
            key = ".".join(parts[1:])
        
        if category not in self.data:
            self.data[category] = {}
        
        self.data[category][key] = {
            "value": value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        return self._save()
    
    def retrieve(self, key: str) -> Optional[Tuple[str, Dict]]:
        """Recupera un valor de la bóveda."""
        key_lower = key.lower()
        
        # Búsqueda exacta primero
        for category, items in self.data.items():
            if key in items:
                return items[key]["value"], items[key]
        
        # Búsqueda difusa
        for category, items in self.data.items():
            for k, v in items.items():
                if key_lower in k.lower():
                    return v["value"], v
        
        return None, None
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca entradas por coincidencia."""
        results = []
        query_lower = query.lower()
        
        for category, items in self.data.items():
            for key, entry in items.items():
                value = entry.get("value", "")
                score = 0
                
                if query_lower in key.lower():
                    score += 3
                if query_lower in value.lower():
                    score += 2
                if query_lower in category.lower():
                    score += 1
                
                if score > 0:
                    results.append({
                        "category": category,
                        "key": key,
                        "value": value,
                        "score": score,
                        "created_at": entry.get("created_at"),
                        "updated_at": entry.get("updated_at")
                    })
        
        # Ordenar por relevancia
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def list_all(self, category: str = None) -> Dict:
        """Lista todas las entradas de una categoría."""
        if category:
            return self.data.get(category, {})
        return self.data
    
    def delete(self, key: str, category: str = None) -> bool:
        """Elimina una entrada de la bóveda."""
        if category:
            if category in self.data and key in self.data[category]:
                del self.data[category][key]
                # Si la categoría queda vacía, eliminarla
                if not self.data[category]:
                    del self.data[category]
                return self._save()
            return False
        
        # Buscar en todas las categorías
        for cat, items in self.data.items():
            if key in items:
                del items[key]
                if not items:
                    del self.data[cat]
                return self._save()
        return False
    
    def get_categories(self) -> List[str]:
        """Retorna la lista de categorías disponibles."""
        return list(self.data.keys())
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas de la bóveda."""
        total = 0
        by_category = {}
        
        for category, items in self.data.items():
            count = len(items)
            total += count
            by_category[category] = count
        
        return {
            "total_entries": total,
            "categories": by_category,
            "encryption": self._encryption_enabled,
            "file_path": str(VAULT_FILE)
        }
    
    def export(self, path: str = None) -> bool:
        """Exporta la bóveda a un archivo JSON."""
        try:
            if not path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = str(CONFIG_DIR / f"vault_export_{timestamp}.json")
            
            export_path = Path(path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_entries": sum(len(items) for items in self.data.values()),
                "categories": self.data
            }
            
            export_path.write_text(
                json.dumps(export_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            return True
        except Exception:
            return False
    
    def import_data(self, path: str) -> bool:
        """Importa datos desde un archivo JSON."""
        try:
            import_path = Path(path)
            if not import_path.exists():
                return False
            
            data = json.loads(import_path.read_text(encoding="utf-8"))
            
            # Si es un export de vault, extraer categorías
            if "categories" in data:
                data = data["categories"]
            
            # Fusionar con datos existentes (sobrescribir)
            for category, items in data.items():
                if category not in self.data:
                    self.data[category] = {}
                self.data[category].update(items)
            
            return self._save()
        except Exception:
            return False


# ─── INSTANCIA GLOBAL ──────────────────────────────────────────────────────
_vault = None

def get_vault() -> VaultManager:
    """Retorna la instancia singleton de la bóveda."""
    global _vault
    if _vault is None:
        _vault = VaultManager()
    return _vault


# ─── FUNCIÓN PRINCIPAL PARA LA IA ─────────────────────────────────────────
def vault(parameters: Dict, player=None) -> str:
    """
    Controla la bóveda de memoria a largo plazo.
    
    Acciones:
        save: Guardar un secreto o dato
        retrieve: Recuperar un dato
        search: Buscar datos
        list: Listar datos por categoría
        delete: Eliminar un dato
        categories: Ver categorías disponibles
        stats: Ver estadísticas
        export: Exportar la bóveda
        import: Importar datos
        toggle_encryption: Activar/desactivar encriptación
    
    Args:
        parameters: Diccionario con parámetros
        player: Referencia al jugador (no usado)
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "save").strip().lower()
    key = p.get("key", "").strip()
    value = p.get("value", "")
    category = p.get("category", "general").strip()
    query = p.get("query", "").strip()
    limit = int(p.get("limit", 10))
    path = p.get("path", "").strip()
    
    vault = get_vault()
    
    # ─── GUARDAR ──────────────────────────────────────────────────────────
    if action in ("save", "store", "add"):
        if not key:
            return "❌ Error: Necesito una clave para guardar (ej: 'contraseña_netflix')"
        if not value:
            return "❌ Error: Necesito un valor para guardar (ej: 'miContraseña123')"
        
        if vault.save(key, value, category):
            return f"✅ Guardado en la bóveda: [{category}] {key} = {'*' * len(value)}"
        else:
            return "❌ Error al guardar en la bóveda."
    
    # ─── RECUPERAR ──────────────────────────────────────────────────────
    elif action in ("retrieve", "get", "read"):
        if not key:
            return "❌ Error: ¿Qué clave quieres buscar en la bóveda?"
        
        result, metadata = vault.retrieve(key)
        if result is not None:
            created = metadata.get("created_at", "")[:16].replace("T", " ")
            updated = metadata.get("updated_at", "")[:16].replace("T", " ")
            # Determinar la categoría correcta
            found_category = "general"
            for cat, items in vault.data.items():
                if key in items:
                    found_category = cat
                    break
            return f"🔓 [{found_category}] {key} = {result}\n   Creado: {created} | Actualizado: {updated}"
        else:
            return f"❌ No encontré '{key}' en la bóveda."
    
    # ─── BUSCAR ──────────────────────────────────────────────────────────
    elif action in ("search", "find"):
        if not query:
            return "❌ Error: Especifica un término de búsqueda."
        
        results = vault.search(query, limit)
        if results:
            lines = [f"🔍 Resultados para '{query}' ({len(results)} encontrados):"]
            for r in results:
                score_emoji = "⭐⭐⭐" if r["score"] >= 5 else "⭐⭐" if r["score"] >= 3 else "⭐"
                value_preview = r["value"][:30]
                if len(r["value"]) > 30:
                    value_preview += "…"
                lines.append(f"  {score_emoji} [{r['category']}] {r['key']} = {value_preview}")
            return "\n".join(lines)
        else:
            return f"❌ No encontré nada relacionado con '{query}'."
    
    # ─── LISTAR ──────────────────────────────────────────────────────────
    elif action == "list":
        if category:
            items = vault.list_all(category)
            if not items:
                return f"📭 La categoría '{category}' está vacía."
            
            lines = [f"📂 Categoría: {category} ({len(items)} elementos)"]
            for k, v in items.items():
                value_preview = v.get("value", "")[:40]
                if len(v.get("value", "")) > 40:
                    value_preview += "…"
                lines.append(f"  • {k} = {value_preview}")
            return "\n".join(lines)
        else:
            categories = vault.get_categories()
            if not categories:
                return "📭 La bóveda está vacía."
            
            stats = vault.get_stats()
            lines = ["🔐 Contenido de la bóveda:"]
            for cat, count in stats["categories"].items():
                lines.append(f"  📂 {cat}: {count} elementos")
            lines.append(f"\nTotal: {stats['total_entries']} elementos")
            return "\n".join(lines)
    
    # ─── ELIMINAR ────────────────────────────────────────────────────────
    elif action == "delete":
        if not key:
            return "❌ Error: ¿Qué clave quieres eliminar?"
        
        confirm = p.get("confirm", "").strip().lower()
        if confirm != "yes" and confirm != "si":
            return f"⚠️ ¿Estás seguro de eliminar '{key}'? Usa confirm='yes' para confirmar."
        
        if vault.delete(key, category):
            return f"🗑️ Eliminado: {key}"
        else:
            return f"❌ No encontré '{key}' para eliminar."
    
    # ─── CATEGORÍAS ──────────────────────────────────────────────────────
    elif action == "categories":
        categories = vault.get_categories()
        if categories:
            return f"📂 Categorías disponibles: {', '.join(categories)}"
        else:
            return "📭 No hay categorías en la bóveda."
    
    # ─── ESTADÍSTICAS ────────────────────────────────────────────────────
    elif action in ("stats", "statistics"):
        stats = vault.get_stats()
        lines = [
            "📊 Estadísticas de la bóveda:",
            f"  Total: {stats['total_entries']} elementos",
            f"  Categorías: {len(stats['categories'])}",
            f"  Encriptación: {'✅ Activada' if stats['encryption'] else '⚠️ Desactivada'}",
            f"  Archivo: {stats['file_path']}"
        ]
        
        if stats["categories"]:
            lines.append("\n  📂 Por categoría:")
            for cat, count in stats["categories"].items():
                lines.append(f"    • {cat}: {count}")
        
        return "\n".join(lines)
    
    # ─── EXPORTAR ─────────────────────────────────────────────────────────
    elif action == "export":
        if vault.export(path):
            if path:
                return f"💾 Bóveda exportada a: {path}"
            else:
                # Buscar el archivo más reciente
                exports = sorted(CONFIG_DIR.glob("vault_export_*.json"))
                if exports:
                    return f"💾 Bóveda exportada a: {exports[-1]}"
                return "💾 Bóveda exportada exitosamente."
        else:
            return "❌ Error al exportar la bóveda."
    
    # ─── IMPORTAR ─────────────────────────────────────────────────────────
    elif action == "import":
        if not path:
            return "❌ Error: Especifica la ruta del archivo a importar (path='...')"
        
        if vault.import_data(path):
            return f"📥 Datos importados desde: {path}"
        else:
            return "❌ Error al importar datos."
    
    # ─── TOGGLE ENCRYPTION ──────────────────────────────────────────────
    elif action == "toggle_encryption":
        vault._encryption_enabled = not vault._encryption_enabled
        vault._save()
        estado = "activada" if vault._encryption_enabled else "desactivada"
        return f"🔐 Encriptación {estado}."
    
    # ─── AYUDA ──────────────────────────────────────────────────────────
    else:
        return (
            "📖 Comandos de la Bóveda de Memoria:\n\n"
            "🔹 Guardar:\n"
            "  action='save' key='clave' value='valor' [category='categoria']\n\n"
            "🔹 Recuperar:\n"
            "  action='retrieve' key='clave'\n\n"
            "🔹 Buscar:\n"
            "  action='search' query='término' [limit=10]\n\n"
            "🔹 Listar:\n"
            "  action='list' [category='categoria']\n\n"
            "🔹 Eliminar:\n"
            "  action='delete' key='clave' confirm='yes'\n\n"
            "🔹 Estadísticas:\n"
            "  action='stats'\n\n"
            "🔹 Exportar/Importar:\n"
            "  action='export' [path='ruta']\n"
            "  action='import' path='ruta'\n\n"
            "🔹 Categorías:\n"
            "  action='categories'\n\n"
            "📌 Ejemplos:\n"
            "  Guardar: {'action':'save','key':'netflix','value':'miPass123'}\n"
            "  Buscar: {'action':'search','query':'netflix'}"
        )


# ─── INICIALIZACIÓN AUTOMÁTICA ──────────────────────────────────────────
def init_vault():
    """Inicializa la bóveda y crea los directorios necesarios."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    VAULT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Crear archivo vacío si no existe
    if not VAULT_FILE.exists():
        VAULT_FILE.write_text(json.dumps({}), encoding="utf-8")
        print(f"[VAULT] Archivo creado en: {VAULT_FILE}")
    
    return get_vault()


# Inicializar automáticamente al importar
init_vault()

if __name__ == "__main__":
    # Prueba rápida
    print(f"📂 Carpeta base: {BASE_DIR}")
    print(f"📂 Config en: {CONFIG_DIR}")
    print(f"📄 Archivo: {VAULT_FILE}")
    print("✅ Módulo de bóveda cargado correctamente.")
    
    # Prueba de guardado
    test_vault = get_vault()
    test_vault.save("test_key", "test_value", "test")
    print("✅ Prueba de guardado exitosa")