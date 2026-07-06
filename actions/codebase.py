"""
Codebase Module
===============
Sistema de indexación y búsqueda inteligente de proyectos de código.
Soporta: Python, JavaScript, TypeScript, Java, C++, C#, Go, Rust, PHP, Ruby, Swift, y más.
"""

import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
import threading
import time
import fnmatch
import importlib

try:
    import pygments
    from pygments import lexers
    from pygments.token import Token
except ImportError:
    pygments = None

try:
    whoosh_index = importlib.import_module("whoosh.index")
    create_in = whoosh_index.create_in
    open_dir = whoosh_index.open_dir
    exists_in = whoosh_index.exists_in

    whoosh_fields = importlib.import_module("whoosh.fields")
    Schema = whoosh_fields.Schema
    TEXT = whoosh_fields.TEXT
    ID = whoosh_fields.ID
    KEYWORD = whoosh_fields.KEYWORD
    DATETIME = whoosh_fields.DATETIME
    NUMERIC = whoosh_fields.NUMERIC

    whoosh_qparser = importlib.import_module("whoosh.qparser")
    QueryParser = whoosh_qparser.QueryParser
    MultifieldParser = whoosh_qparser.MultifieldParser

    whoosh_query = importlib.import_module("whoosh.query")
    Term = whoosh_query.Term
    And = whoosh_query.And
    Or = whoosh_query.Or
    FuzzyTerm = whoosh_query.FuzzyTerm
except ImportError:
    whoosh = None
    create_in = open_dir = exists_in = None
    Schema = TEXT = ID = KEYWORD = DATETIME = NUMERIC = None
    QueryParser = MultifieldParser = None
    Term = And = Or = FuzzyTerm = None

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────
CONFIG_DIR = Path("config")
CODEBASE_CONFIG_PATH = CONFIG_DIR / "codebase_config.json"
CODEBASE_INDEX_PATH = CONFIG_DIR / "codebase_index"
CODEBASE_CACHE_PATH = CONFIG_DIR / "codebase_cache"
CODEBASE_INDEX_PATH.mkdir(parents=True, exist_ok=True)
CODEBASE_CACHE_PATH.mkdir(parents=True, exist_ok=True)

# ─── LENGUAJES SOPORTADOS ─────────────────────────────────────────────────
LANGUAGE_MAP = {
    # Python
    ".py": {"language": "Python", "keywords": ["def", "class", "import", "from", "if", "elif", "else", "for", "while", "return", "yield", "try", "except", "finally", "with", "as", "lambda", "global", "nonlocal"]},
    
    # JavaScript
    ".js": {"language": "JavaScript", "keywords": ["function", "var", "let", "const", "if", "else", "for", "while", "return", "class", "import", "export", "default", "new", "this", "super", "extends", "try", "catch", "finally"]},
    ".jsx": {"language": "JavaScript", "keywords": ["function", "var", "let", "const", "if", "else", "for", "while", "return", "class", "import", "export", "default", "new", "this", "super", "extends", "try", "catch"]},
    ".ts": {"language": "TypeScript", "keywords": ["function", "var", "let", "const", "if", "else", "for", "while", "return", "class", "import", "export", "default", "new", "this", "super", "extends", "interface", "type", "enum", "module"]},
    ".tsx": {"language": "TypeScript", "keywords": ["function", "var", "let", "const", "if", "else", "for", "while", "return", "class", "import", "export", "default", "new", "this", "super", "extends", "interface", "type", "enum"]},
    
    # Java
    ".java": {"language": "Java", "keywords": ["public", "private", "protected", "static", "final", "abstract", "class", "interface", "extends", "implements", "new", "this", "super", "return", "void", "try", "catch", "finally", "throw", "throws"]},
    
    # C++
    ".cpp": {"language": "C++", "keywords": ["class", "public", "private", "protected", "virtual", "static", "const", "friend", "inline", "namespace", "template", "typename", "using", "new", "delete", "this", "return"]},
    ".h": {"language": "C++", "keywords": ["class", "public", "private", "protected", "virtual", "static", "const", "friend", "inline", "namespace", "template", "typename", "using", "new", "delete", "this", "return"]},
    ".hpp": {"language": "C++", "keywords": ["class", "public", "private", "protected", "virtual", "static", "const", "friend", "inline", "namespace", "template", "typename", "using", "new", "delete", "this", "return"]},
    
    # C#
    ".cs": {"language": "C#", "keywords": ["public", "private", "protected", "internal", "static", "readonly", "const", "abstract", "virtual", "override", "class", "interface", "struct", "enum", "namespace", "using", "new", "this", "base", "return", "void", "try", "catch", "finally"]},
    
    # Go
    ".go": {"language": "Go", "keywords": ["func", "var", "const", "type", "struct", "interface", "map", "chan", "go", "select", "defer", "return", "if", "else", "for", "range", "switch", "case", "default", "package", "import"]},
    
    # Rust
    ".rs": {"language": "Rust", "keywords": ["fn", "let", "mut", "const", "static", "impl", "trait", "struct", "enum", "type", "mod", "pub", "use", "return", "if", "else", "for", "while", "loop", "match", "match", "async", "await", "move"]},
    
    # PHP
    ".php": {"language": "PHP", "keywords": ["function", "class", "public", "private", "protected", "static", "final", "abstract", "interface", "extends", "implements", "new", "this", "parent", "return", "echo", "print", "if", "else", "for", "foreach", "while", "switch", "case", "break", "continue"]},
    
    # Ruby
    ".rb": {"language": "Ruby", "keywords": ["def", "class", "module", "include", "extend", "attr_reader", "attr_writer", "attr_accessor", "if", "else", "elsif", "unless", "case", "when", "for", "while", "until", "break", "next", "redo", "retry", "return", "yield", "super", "self"]},
    
    # Swift
    ".swift": {"language": "Swift", "keywords": ["func", "class", "struct", "enum", "protocol", "extension", "import", "let", "var", "if", "else", "guard", "switch", "case", "default", "for", "while", "repeat", "return", "break", "continue", "throw", "try", "catch"]},
    
    # Kotlin
    ".kt": {"language": "Kotlin", "keywords": ["fun", "class", "interface", "object", "data", "sealed", "enum", "annotation", "open", "final", "abstract", "override", "private", "protected", "internal", "public", "var", "val", "if", "else", "when", "for", "while", "do", "return", "break", "continue", "throw", "try", "catch", "finally"]},
    
    # SQL
    ".sql": {"language": "SQL", "keywords": ["SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "ON", "GROUP", "BY", "HAVING", "ORDER", "ASC", "DESC", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TABLE", "VIEW", "INDEX", "UNION"]},
    
    # HTML/CSS
    ".html": {"language": "HTML", "keywords": ["html", "head", "body", "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6", "a", "img", "ul", "ol", "li", "table", "tr", "td", "form", "input", "button", "script", "style", "link", "meta"]},
    ".css": {"language": "CSS", "keywords": ["color", "background", "font", "margin", "padding", "border", "display", "position", "float", "flex", "grid", "width", "height", "max", "min", "important", "media", "keyframes", "animation", "transition", "transform"]},
    
    # Shell
    ".sh": {"language": "Shell", "keywords": ["echo", "cat", "grep", "awk", "sed", "ls", "cd", "pwd", "mkdir", "rm", "cp", "mv", "chmod", "chown", "ps", "kill", "tar", "gzip", "gunzip", "find", "xargs", "for", "while", "if", "then", "else", "elif", "fi", "case", "esac", "function", "return", "exit"]},
    ".bash": {"language": "Shell", "keywords": ["echo", "cat", "grep", "awk", "sed", "ls", "cd", "pwd", "mkdir", "rm", "cp", "mv", "chmod", "chown", "ps", "kill", "tar", "gzip", "gunzip", "find", "xargs"]},
}

# ─── INDEXADOR DE CÓDIGO ──────────────────────────────────────────────────
class CodeIndexer:
    """Indexa y busca en proyectos de código."""
    
    def __init__(self):
        self.config = self._load_config()
        self.index = None
        self.writer = None
        self._lock = threading.Lock()
        self._init_index()
    
    def _load_config(self) -> Dict:
        """Carga la configuración."""
        if CODEBASE_CONFIG_PATH.exists():
            try:
                return json.loads(CODEBASE_CONFIG_PATH.read_text(encoding="utf-8"))
            except:
                return {}
        return {
            "projects": {},
            "max_file_size": 1048576,  # 1MB
            "exclude_patterns": [".git", "__pycache__", "node_modules", ".venv", "venv", ".env", "dist", "build", "target", "*.pyc"],
            "index_extensions": [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".sql", ".html", ".css", ".sh", ".bash"]
        }
    
    def _save_config(self):
        """Guarda la configuración."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CODEBASE_CONFIG_PATH.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _init_index(self):
        """Inicializa el índice de búsqueda."""
        if not whoosh:
            return
        
        try:
            schema = Schema(
                id=ID(stored=True, unique=True),
                path=ID(stored=True),
                filename=TEXT(stored=True),
                content=TEXT(stored=True),
                project=TEXT(stored=True),
                language=TEXT(stored=True),
                symbols=TEXT(stored=True),
                modified=DATETIME(stored=True),
                size=NUMERIC(stored=True),
                lines=NUMERIC(stored=True)
            )
            
            if not exists_in(str(CODEBASE_INDEX_PATH)):
                self.index = create_in(str(CODEBASE_INDEX_PATH), schema)
            else:
                self.index = open_dir(str(CODEBASE_INDEX_PATH))
                
            print(f"[Codebase] Índice inicializado en {CODEBASE_INDEX_PATH}")
        except Exception as e:
            print(f"[Codebase] Error inicializando índice: {e}")
            self.index = None
    
    def _should_ignore(self, path: Path) -> bool:
        """Verifica si un archivo debe ser ignorado."""
        # Verificar patrones de exclusión
        for pattern in self.config.get("exclude_patterns", []):
            if path.match(pattern):
                return True
        
        # Verificar extensión
        if path.suffix and path.suffix not in self.config.get("index_extensions", []):
            return True
        
        # Verificar tamaño
        if path.is_file():
            try:
                if path.stat().st_size > self.config.get("max_file_size", 1048576):
                    return True
            except:
                pass
        
        return False
    
    def _extract_symbols(self, content: str, language: str) -> List[str]:
        """Extrae símbolos (funciones, clases, variables) del código."""
        symbols = []
        
        # Patrones según lenguaje
        patterns = {
            "Python": [
                r'def\s+(\w+)\s*\(',  # Funciones
                r'class\s+(\w+)\s*[:\(]',  # Clases
                r'(\w+)\s*=\s*',  # Variables (simplificado)
            ],
            "JavaScript": [
                r'function\s+(\w+)\s*\(',  # Funciones
                r'class\s+(\w+)\s*\{',  # Clases
                r'const\s+(\w+)\s*=',  # Constantes
                r'let\s+(\w+)\s*=',  # Variables
                r'var\s+(\w+)\s*=',  # Variables
            ],
            "Java": [
                r'(public|private|protected)?\s*(static)?\s*(\w+)\s+(\w+)\s*\(',  # Métodos
                r'class\s+(\w+)\s*\{',  # Clases
                r'interface\s+(\w+)\s*\{',  # Interfaces
            ],
            "C++": [
                r'(void|int|char|float|double|bool|auto|(\w+::)?\w+)\s+(\w+)\s*\(',  # Funciones
                r'class\s+(\w+)\s*\{',  # Clases
                r'struct\s+(\w+)\s*\{',  # Structs
            ],
        }
        
        patterns_lang = patterns.get(language, [])
        for pattern in patterns_lang:
            matches = re.findall(pattern, content)
            if matches:
                if isinstance(matches[0], tuple):
                    symbols.extend([m[-1] for m in matches if m[-1]])
                else:
                    symbols.extend(matches)
        
        return list(set(symbols))[:50]  # Limitar a 50 símbolos
    
    def _detect_language(self, file_path: Path) -> str:
        """Detecta el lenguaje de un archivo."""
        ext = file_path.suffix.lower()
        
        # Verificar por extensión
        for lang_ext, info in LANGUAGE_MAP.items():
            if ext == lang_ext:
                return info["language"]
        
        # Detectar por contenido (simplificado)
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")[:500]
            # Buscar palabras clave
            max_matches = 0
            detected_lang = "Unknown"
            
            for lang_info in LANGUAGE_MAP.values():
                lang = lang_info["language"]
                keywords = lang_info.get("keywords", [])
                matches = sum(1 for kw in keywords if kw in content)
                if matches > max_matches:
                    max_matches = matches
                    detected_lang = lang
            
            if max_matches > 2:
                return detected_lang
        except:
            pass
        
        return "Unknown"
    
    def index_project(self, project_path: str, project_name: str = None) -> str:
        """
        Indexa un proyecto de código.
        
        Args:
            project_path: Ruta del proyecto
            project_name: Nombre del proyecto (opcional)
        """
        if not whoosh or not self.index:
            return "❌ Whoosh no está instalado. Instala: pip install whoosh"
        
        path = Path(project_path)
        if not path.exists():
            return f"❌ El proyecto no existe: {project_path}"
        
        if not path.is_dir():
            return f"❌ La ruta debe ser un directorio: {project_path}"
        
        project_name = project_name or path.name
        
        try:
            self._lock.acquire()
            
            # Crear escritor
            writer = self.index.writer()
            
            # Estadísticas
            total_files = 0
            indexed_files = 0
            skipped_files = 0
            errors = []
            
            # Recorrer archivos
            for root, dirs, files in os.walk(path):
                # Excluir directorios
                dirs[:] = [d for d in dirs if not self._should_ignore(Path(d))]
                
                for file in files:
                    file_path = Path(root) / file
                    total_files += 1
                    
                    # Verificar si debe ser indexado
                    if self._should_ignore(file_path):
                        skipped_files += 1
                        continue
                    
                    try:
                        # Leer contenido
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        
                        # Detectar lenguaje
                        language = self._detect_language(file_path)
                        
                        # Extraer símbolos
                        symbols = self._extract_symbols(content, language)
                        
                        # Calcular líneas
                        lines = len(content.splitlines())
                        
                        # Generar ID único
                        file_id = hashlib.md5(f"{project_name}:{file_path}".encode()).hexdigest()
                        
                        # Crear documento
                        doc = {
                            "id": file_id,
                            "path": str(file_path),
                            "filename": file_path.name,
                            "content": content,
                            "project": project_name,
                            "language": language,
                            "symbols": " ".join(symbols),
                            "modified": datetime.now(),
                            "size": file_path.stat().st_size,
                            "lines": lines
                        }
                        
                        # Indexar
                        writer.update_document(**doc)
                        indexed_files += 1
                        
                    except Exception as e:
                        errors.append(f"{file_path}: {e}")
                        skipped_files += 1
            
            # Commit
            writer.commit()
            
            # Guardar configuración
            if project_name not in self.config["projects"]:
                self.config["projects"][project_name] = {
                    "path": str(path),
                    "indexed_at": datetime.now().isoformat(),
                    "files": indexed_files
                }
                self._save_config()
            
            result = [
                f"✅ Proyecto indexado: {project_name}",
                f"📄 Archivos totales: {total_files}",
                f"📥 Archivos indexados: {indexed_files}",
                f"⏭️ Archivos omitidos: {skipped_files}"
            ]
            
            if errors:
                result.append(f"⚠️ Errores: {len(errors)}")
                if len(errors) <= 3:
                    result.extend([f"  • {e}" for e in errors])
            
            return "\n".join(result)
            
        except Exception as e:
            return f"❌ Error indexando proyecto: {e}"
        finally:
            self._lock.release()
    
    def search(self, query: str, project: str = None, limit: int = 20) -> List[Dict]:
        """
        Busca en los proyectos indexados.
        
        Args:
            query: Término de búsqueda
            project: Proyecto específico (opcional)
            limit: Límite de resultados
        
        Returns:
            Lista de resultados
        """
        if not whoosh or not self.index:
            return []
        
        try:
            self._lock.acquire()
            
            # Construir query
            fields = ["content", "filename", "symbols"]
            if project:
                fields.append("project")
            
            parser = MultifieldParser(fields, schema=self.index.schema)
            
            # Agregar filtro de proyecto
            if project:
                query_obj = parser.parse(query)
                project_query = Term("project", project)
                query_obj = And([query_obj, project_query])
            else:
                query_obj = parser.parse(query)
            
            # Buscar
            searcher = self.index.searcher()
            results = searcher.search(query_obj, limit=limit)
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "file": result.get("filename", ""),
                    "path": result.get("path", ""),
                    "project": result.get("project", ""),
                    "language": result.get("language", ""),
                    "lines": result.get("lines", 0),
                    "symbols": result.get("symbols", "").split()[:10],
                    "score": result.score,
                    "content_preview": result.get("content", "")[:200]
                })
            
            searcher.close()
            return formatted_results
            
        except Exception as e:
            print(f"[Codebase] Error en búsqueda: {e}")
            return []
        finally:
            self._lock.release()
    
    def find_symbol(self, symbol: str, project: str = None) -> List[Dict]:
        """
        Busca un símbolo (función, clase, variable).
        
        Args:
            symbol: Nombre del símbolo
            project: Proyecto específico (opcional)
        
        Returns:
            Lista de resultados
        """
        return self.search(f'symbols:"{symbol}"', project, limit=50)
    
    def get_project_info(self, project: str) -> Dict:
        """Obtiene información de un proyecto."""
        info = self.config["projects"].get(project, {})
        
        if info:
            # Obtener estadísticas del índice
            try:
                searcher = self.index.searcher()
                project_query = Term("project", project)
                results = searcher.search(project_query, limit=None)
                info["indexed_files"] = len(results)
                searcher.close()
            except:
                pass
        
        return info
    
    def list_projects(self) -> List[str]:
        """Lista los proyectos indexados."""
        return list(self.config["projects"].keys())
    
    def remove_project(self, project: str) -> bool:
        """Elimina un proyecto del índice."""
        try:
            self._lock.acquire()
            
            if project in self.config["projects"]:
                del self.config["projects"][project]
                self._save_config()
            
            # Eliminar documentos del índice
            if self.index:
                writer = self.index.writer()
                writer.delete_by_term("project", project)
                writer.commit()
            
            return True
            
        except Exception as e:
            print(f"[Codebase] Error eliminando proyecto: {e}")
            return False
        finally:
            self._lock.release()
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del índice."""
        stats = {
            "projects": len(self.config["projects"]),
            "total_files": 0,
            "languages": {}
        }
        
        try:
            if self.index:
                searcher = self.index.searcher()
                # Contar por lenguaje
                for lang in set(LANGUAGE_MAP.values()):
                    lang_name = lang["language"] if isinstance(lang, dict) else lang
                    try:
                        lang_query = Term("language", lang_name)
                        results = searcher.search(lang_query, limit=None)
                        stats["languages"][lang_name] = len(results)
                    except:
                        pass
                
                # Total de archivos
                stats["total_files"] = sum(stats["languages"].values())
                searcher.close()
        except:
            pass
        
        # Proyectos
        for project in self.config["projects"]:
            info = self.config["projects"][project]
            stats["total_files"] += info.get("files", 0)
        
        return stats


# ─── FORMATO DE RESULTADOS ──────────────────────────────────────────────
def format_search_results(results: List[Dict]) -> str:
    """Formatea los resultados de búsqueda."""
    if not results:
        return "🔍 No se encontraron resultados."
    
    lines = [
        f"🔍 Resultados ({len(results)} encontrados):",
        "━" * 50
    ]
    
    for i, result in enumerate(results, 1):
        lines.append(f"{i}. 📄 {result.get('file', 'N/A')}")
        lines.append(f"   📂 {result.get('project', 'N/A')}")
        lines.append(f"   💻 {result.get('language', 'N/A')} | 📏 {result.get('lines', 0)} líneas")
        
        symbols = result.get('symbols', [])
        if symbols:
            lines.append(f"   🔧 Símbolos: {', '.join(symbols[:5])}")
        
        preview = result.get('content_preview', '')[:100]
        if preview:
            lines.append(f"   📝 ...{preview}...")
        
        lines.append("")
    
    return "\n".join(lines)


# ─── INSTANCIA GLOBAL ────────────────────────────────────────────────────
_indexer: Optional[CodeIndexer] = None

def get_indexer() -> CodeIndexer:
    """Obtiene la instancia del indexador de código."""
    global _indexer
    if _indexer is None:
        _indexer = CodeIndexer()
    return _indexer


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────
def codebase(parameters: Dict, player=None) -> str:
    """
    Indexa y busca en proyectos de código.
    
    Args:
        parameters: Diccionario con parámetros
            - action: index | search | find_symbol | list | info | remove | stats
            - path: Ruta del proyecto (para index)
            - name: Nombre del proyecto (para index o info)
            - query: Término de búsqueda
            - symbol: Nombre del símbolo a buscar
            - limit: Límite de resultados
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "search").strip().lower()
    path = p.get("path", "").strip()
    name = p.get("name", "").strip()
    query = p.get("query", "").strip()
    symbol = p.get("symbol", "").strip()
    limit = int(p.get("limit", 20))
    
    indexer = get_indexer()
    
    # ─── INDEXAR ─────────────────────────────────────────────────────────
    if action == "index" or action == "add":
        if not path:
            return "❌ Especifica la ruta del proyecto (path='...')"
        
        return indexer.index_project(path, name)
    
    # ─── BUSCAR ─────────────────────────────────────────────────────────
    elif action == "search":
        if not query:
            return "❌ Especifica un término de búsqueda (query='...')"
        
        results = indexer.search(query, name, limit)
        return format_search_results(results)
    
    # ─── BUSCAR SÍMBOLO ────────────────────────────────────────────────
    elif action == "find_symbol":
        if not symbol:
            return "❌ Especifica el símbolo a buscar (symbol='...')"
        
        results = indexer.find_symbol(symbol, name)
        return format_search_results(results)
    
    # ─── LISTAR PROYECTOS ──────────────────────────────────────────────
    elif action == "list":
        projects = indexer.list_projects()
        
        if not projects:
            return "📭 No hay proyectos indexados."
        
        lines = ["📂 PROYECTOS INDEXADOS", "━" * 40]
        for project in sorted(projects):
            info = indexer.get_project_info(project)
            files = info.get("files", info.get("indexed_files", 0))
            lines.append(f"  • {project} ({files} archivos)")
            if info.get("path"):
                lines.append(f"    📂 {info['path']}")
        
        return "\n".join(lines)
    
    # ─── INFORMACIÓN ────────────────────────────────────────────────────
    elif action == "info":
        if not name:
            return "❌ Especifica el nombre del proyecto (name='...')"
        
        info = indexer.get_project_info(name)
        
        if not info:
            return f"❌ Proyecto '{name}' no encontrado."
        
        lines = [
            f"📊 INFORMACIÓN DEL PROYECTO: {name}",
            "━" * 40,
            f"📂 Ruta: {info.get('path', 'N/A')}",
            f"📄 Archivos: {info.get('files', info.get('indexed_files', 0))}",
            f"📅 Indexado: {info.get('indexed_at', 'N/A')[:16].replace('T', ' ')}"
        ]
        
        return "\n".join(lines)
    
    # ─── ELIMINAR ──────────────────────────────────────────────────────
    elif action == "remove":
        if not name:
            return "❌ Especifica el nombre del proyecto (name='...')"
        
        if indexer.remove_project(name):
            return f"🗑️ Proyecto '{name}' eliminado del índice."
        else:
            return f"❌ Error eliminando proyecto '{name}'."
    
    # ─── ESTADÍSTICAS ──────────────────────────────────────────────────
    elif action == "stats":
        stats = indexer.get_stats()
        
        lines = [
            "📊 ESTADÍSTICAS DEL CODEBASE",
            "━" * 40,
            f"📂 Proyectos: {stats.get('projects', 0)}",
            f"📄 Archivos indexados: {stats.get('total_files', 0)}",
            ""
        ]
        
        languages = stats.get('languages', {})
        if languages:
            lines.append("💻 Lenguajes:")
            sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
            for lang, count in sorted_langs[:10]:
                lines.append(f"  • {lang}: {count} archivos")
        
        return "\n".join(lines)
    
    # ─── AYUDA ──────────────────────────────────────────────────────────
    else:
        return (
            "📖 COMANDOS DE CODEBASE\n"
            "━" * 50 + "\n\n"
            "📥 Indexar proyecto:\n"
            "  {'action':'index','path':'C:/mi-proyecto','name':'mi-proyecto'}\n\n"
            "🔍 Buscar en código:\n"
            "  {'action':'search','query':'función buscar'}\n"
            "  {'action':'search','query':'error','name':'mi-proyecto'}\n\n"
            "🔧 Buscar símbolo:\n"
            "  {'action':'find_symbol','symbol':'class MiClase'}\n"
            "  {'action':'find_symbol','symbol':'def funcion','name':'mi-proyecto'}\n\n"
            "📂 Listar proyectos:\n"
            "  {'action':'list'}\n\n"
            "📊 Información de proyecto:\n"
            "  {'action':'info','name':'mi-proyecto'}\n\n"
            "🗑️ Eliminar proyecto:\n"
            "  {'action':'remove','name':'mi-proyecto'}\n\n"
            "📊 Estadísticas:\n"
            "  {'action':'stats'}\n\n"
            "📌 Ejemplos:\n"
            "  Indexar: {'action':'index','path':'C:/Code/Nexus'}\n"
            "  Buscar: {'action':'search','query':'def start'}"
        )


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
def init_codebase():
    """Inicializa el módulo de codebase."""
    print("[Codebase] Inicializando...")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CODEBASE_INDEX_PATH.mkdir(parents=True, exist_ok=True)
    CODEBASE_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    
    if not whoosh:
        print("[Codebase] ⚠️ Whoosh no instalado - funcionalidad de búsqueda limitada")
        print("[Codebase] Instalar: pip install whoosh")
    
    if not pygments:
        print("[Codebase] ⚠️ Pygments no instalado - resaltado de sintaxis limitado")
    
    print(f"[Codebase] Lenguajes soportados: {len(LANGUAGE_MAP)}")
    print("[Codebase] ✅ Listo")
    return True