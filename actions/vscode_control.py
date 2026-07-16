"""
vs_code_control.py — Control avanzado de Visual Studio Code
Soporta: abrir proyectos, instalar extensiones, gestionar archivos, ejecutar comandos

Compatible con Windows, macOS y Linux. Para que las acciones que usan el CLI
funcionen (install_extension, list_extensions, build, run, etc.) VS Code debe
estar instalado; si el comando 'code' no está en el PATH, este módulo cae
automáticamente al ejecutable de la instalación (Code.exe / el binario dentro
del .app / el binario en /usr/bin, etc.).
"""

import os
import json
import platform
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List

TIMEOUT = 15  # segundos máximos para cualquier comando que espera respuesta


# ──────────────────────────────────────────────────────────────────────────
#  DETECCIÓN DE VS CODE
# ──────────────────────────────────────────────────────────────────────────

def _gui_candidate_paths() -> List[str]:
    """Rutas típicas de instalación de VS Code según el sistema operativo."""
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Windows":
        return [
            "C:\\Program Files\\Microsoft VS Code\\Code.exe",
            "C:\\Program Files (x86)\\Microsoft VS Code\\Code.exe",
            os.path.join(home, "AppData", "Local", "Programs", "Microsoft VS Code", "Code.exe"),
        ]
    elif system == "Darwin":
        return [
            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
            os.path.join(home, "Applications", "Visual Studio Code.app",
                         "Contents", "Resources", "app", "bin", "code"),
        ]
    else:  # Linux y otros Unix
        return [
            "/usr/bin/code",
            "/usr/local/bin/code",
            "/snap/bin/code",
        ]


def get_vscode_cli() -> Optional[str]:
    """
    Devuelve el comando a usar para hablar con VS Code: 'code' si está en el
    PATH, o si no, la ruta completa al ejecutable encontrado en el sistema.
    El resultado se cachea para no repetir la búsqueda en cada llamada.
    """
    if get_vscode_cli._cached is not None:
        return get_vscode_cli._cached or None

    found = shutil.which("code") or shutil.which("code.cmd")
    if found:
        get_vscode_cli._cached = found
        return found

    for path in _gui_candidate_paths():
        if os.path.exists(path):
            get_vscode_cli._cached = path
            return path

    get_vscode_cli._cached = ""
    return None


get_vscode_cli._cached = None


def get_vscode_path() -> Optional[str]:
    """Alias retrocompatible de get_vscode_cli()."""
    return get_vscode_cli()


def is_vscode_running() -> bool:
    """Verifica si VS Code está en ejecución (Windows/macOS/Linux)."""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Code.exe"],
                capture_output=True, text=True, timeout=TIMEOUT,
            )
            return "Code.exe" in result.stdout
        else:
            result = subprocess.run(
                ["pgrep", "-f", "Visual Studio Code|code"],
                capture_output=True, text=True, timeout=TIMEOUT,
            )
            return bool(result.stdout.strip())
    except Exception:
        return False


def _run_cli(args: List[str], timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    """Ejecuta el CLI de VS Code y espera el resultado (para comandos que devuelven texto)."""
    cli = get_vscode_cli()
    if not cli:
        raise FileNotFoundError("No se encontró el comando 'code' de Visual Studio Code.")
    return subprocess.run([cli] + args, capture_output=True, text=True, timeout=timeout)


def _popen_cli(args: List[str]) -> None:
    """Lanza el CLI de VS Code en segundo plano (para abrir ventanas/archivos/comandos)."""
    cli = get_vscode_cli()
    if not cli:
        raise FileNotFoundError("No se encontró el comando 'code' de Visual Studio Code.")
    subprocess.Popen([cli] + args)


# ──────────────────────────────────────────────────────────────────────────
#  FUNCIONES PRINCIPALES
# ──────────────────────────────────────────────────────────────────────────

def vscode_control(parameters: dict, player=None) -> str:
    """
    Control avanzado de Visual Studio Code.

    Acciones:
    - open: Abre VS Code (opcionalmente con un proyecto/carpeta)
    - open_project: Abre un proyecto específico
    - install_extension: Instala una extensión desde el marketplace
    - uninstall_extension: Desinstala una extensión
    - list_extensions: Lista las extensiones instaladas
    - search_extensions: Busca extensiones en el marketplace
    - open_file: Abre un archivo específico
    - create_file: Crea un nuevo archivo
    - run_command: Ejecuta un comando interno de VS Code
    - toggle_terminal: Abre/cierra la terminal integrada
    - build: Ejecuta el build del proyecto
    - run: Ejecuta el proyecto
    - close: Cierra VS Code
    - status: Estado de VS Code
    """
    action = (parameters.get("action") or "").lower().strip()

    if action in ("", "help"):
        return _help_text()

    # search_extensions solo necesita internet, no VS Code instalado localmente
    if action == "search_extensions":
        return _search_extensions(parameters.get("query", ""))

    vscode_cli = get_vscode_cli()
    if not vscode_cli:
        return (
            "❌ No se encontró Visual Studio Code en el sistema. Verifica que esté instalado "
            "y que el comando 'code' esté en el PATH (Ctrl+Shift+P → "
            "'Shell Command: Install \\'code\\' command in PATH')."
        )

    try:
        # 1. ABRIR VS CODE
        if action == "open":
            project_path = parameters.get("project_path", "")
            if project_path:
                if not os.path.exists(project_path):
                    return f"❌ La ruta '{project_path}' no existe."
                _popen_cli([project_path])
                return f"✅ VS Code abierto con el proyecto: {project_path}"
            _popen_cli([])
            return "✅ VS Code abierto."

        # 2. ABRIR PROYECTO
        elif action == "open_project":
            project_path = parameters.get("project_path", "")
            if not project_path:
                return "❌ Se requiere 'project_path' para abrir un proyecto."
            if not os.path.exists(project_path):
                return f"❌ La ruta '{project_path}' no existe."
            _popen_cli([project_path])
            return f"✅ Proyecto abierto: {project_path}"

        # 3. INSTALAR EXTENSIÓN
        elif action == "install_extension":
            extension = parameters.get("extension", "")
            if not extension:
                return "❌ Se requiere 'extension' (ej: 'ms-python.python')"
            result = _run_cli(["--install-extension", extension, "--force"])
            if result.returncode == 0:
                return f"✅ Extensión '{extension}' instalada correctamente."
            return f"❌ Error instalando '{extension}': {(result.stderr or result.stdout).strip()}"

        # 4. DESINSTALAR EXTENSIÓN
        elif action == "uninstall_extension":
            extension = parameters.get("extension", "")
            if not extension:
                return "❌ Se requiere 'extension'"
            result = _run_cli(["--uninstall-extension", extension])
            if result.returncode == 0:
                return f"✅ Extensión '{extension}' desinstalada."
            return f"❌ Error desinstalando '{extension}': {(result.stderr or result.stdout).strip()}"

        # 5. LISTAR EXTENSIONES
        elif action == "list_extensions":
            result = _run_cli(["--list-extensions"])
            if result.returncode != 0:
                return f"❌ Error listando extensiones: {result.stderr.strip()}"
            extensions = [e for e in result.stdout.strip().split("\n") if e]
            if extensions:
                return f"📦 Extensiones instaladas ({len(extensions)}):\n- " + "\n- ".join(extensions)
            return "📦 No hay extensiones instaladas."

        # 6. (search_extensions ya se maneja arriba, antes del chequeo de vscode_cli)

        # 7. ABRIR ARCHIVO
        elif action == "open_file":
            file_path = parameters.get("file_path", "")
            if not file_path:
                return "❌ Se requiere 'file_path'"
            if not os.path.exists(file_path):
                return f"❌ El archivo '{file_path}' no existe."
            _popen_cli([file_path])
            return f"✅ Archivo abierto: {file_path}"

        # 8. CREAR ARCHIVO
        elif action == "create_file":
            file_path = parameters.get("file_path", "")
            content = parameters.get("content", "")
            if not file_path:
                return "❌ Se requiere 'file_path'"
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            _popen_cli([file_path])
            return f"✅ Archivo creado y abierto: {file_path}"

        # 9. EJECUTAR COMANDO INTERNO
        elif action == "run_command":
            command = parameters.get("command", "")
            if not command:
                return "❌ Se requiere 'command' (ej: 'workbench.action.terminal.toggle')"
            _popen_cli(["--command", command])
            return f"✅ Comando ejecutado: {command}"

        # 10. TOGGLE TERMINAL
        elif action == "toggle_terminal":
            return vscode_control(
                {"action": "run_command", "command": "workbench.action.terminal.toggle"}, player
            )

        # 11. BUILD
        elif action == "build":
            _popen_cli(["--command", "workbench.action.tasks.build"])
            return "✅ Build iniciado en VS Code."

        # 12. RUN
        elif action == "run":
            _popen_cli(["--command", "workbench.action.debug.start"])
            return "✅ Ejecución iniciada en VS Code."

        # 13. CERRAR VS CODE
        elif action == "close":
            return _close_vscode()

        # 14. ESTADO
        elif action == "status":
            return _status(vscode_cli)

        # ── ACCIÓN DESCONOCIDA ──────────────────────────────────────────
        else:
            return f"❓ Acción desconocida: '{action}'.\n\n" + _help_text()

    except FileNotFoundError as e:
        return f"❌ {e}"
    except subprocess.TimeoutExpired:
        return f"❌ El comando '{action}' tardó demasiado en responder (timeout de {TIMEOUT}s)."
    except Exception as e:
        return f"❌ Error inesperado ejecutando '{action}': {e}"


# ──────────────────────────────────────────────────────────────────────────
#  HELPERS INTERNOS
# ──────────────────────────────────────────────────────────────────────────

def _search_extensions(query: str) -> str:
    """Busca extensiones en el marketplace de VS Code (no requiere VS Code local)."""
    if not query:
        return "❌ Se requiere 'query' para buscar (ej: 'python')"

    url = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
    payload = {
        "filters": [{
            "criteria": [{"filterType": 8, "value": query}],
            "pageNumber": 1,
            "pageSize": 10,
        }],
        "flags": 103,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json;api-version=3.0-preview.1",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            results = json.loads(response.read().decode())
    except urllib.error.URLError as e:
        return f"❌ Error de red buscando extensiones: {e}"
    except Exception as e:
        return f"❌ Error buscando extensiones: {e}"

    result_groups = results.get("results") or []
    raw_extensions = result_groups[0].get("extensions", []) if result_groups else []
    if not raw_extensions:
        return f"🔍 No se encontraron extensiones para '{query}'"

    lines = []
    for ext in raw_extensions[:10]:
        name = ext.get("extensionName", "")
        publisher = ext.get("publisher", {}).get("publisherName", "")
        display_name = ext.get("displayName", name)
        lines.append(f"• {publisher}.{name} → {display_name}")

    return f"🔍 Resultados para '{query}':\n" + "\n".join(lines)


def _close_vscode() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "Code.exe"],
                            capture_output=True, timeout=TIMEOUT)
        else:
            subprocess.run(["pkill", "-f", "Visual Studio Code"],
                            capture_output=True, timeout=TIMEOUT)
        return "✅ VS Code cerrado."
    except Exception as e:
        return f"❌ Error cerrando VS Code: {e}"


def _status(vscode_cli: str) -> str:
    running = is_vscode_running()
    status_label = "🟢 En ejecución" if running else "🔴 Cerrado"

    ext_count = "? (abre VS Code para ver)"
    if running:
        try:
            result = _run_cli(["--list-extensions"])
            if result.returncode == 0:
                ext_count = str(len([e for e in result.stdout.strip().split("\n") if e]))
            else:
                ext_count = "? (no se pudo consultar)"
        except Exception:
            ext_count = "? (no se pudo consultar)"

    return (
        "📊 Estado de Visual Studio Code:\n"
        f"- VS Code: {status_label}\n"
        f"- Ruta/comando: {vscode_cli}\n"
        f"- Extensiones instaladas: {ext_count}"
    )


def _help_text() -> str:
    return """
🎯 VS Code Control - Comandos disponibles:

📁 Proyectos:
  • open_project → Abre una carpeta/proyecto
  • open_file → Abre un archivo específico
  • create_file → Crea y abre un nuevo archivo

📦 Extensiones:
  • install_extension → Instala una extensión
  • uninstall_extension → Desinstala una extensión
  • list_extensions → Lista extensiones instaladas
  • search_extensions → Busca extensiones en el marketplace

⚡ Ejecución:
  • build → Ejecuta el build del proyecto
  • run → Ejecuta el proyecto (debug)
  • toggle_terminal → Abre/cierra la terminal
  • run_command → Ejecuta un comando interno de VS Code

🔧 Otros:
  • open → Abre VS Code (opcional con proyecto)
  • close → Cierra VS Code
  • status → Muestra el estado de VS Code

📝 Ejemplos:
  {"action": "open_project", "project_path": "C:/Users/tu_usuario/proyecto"}
  {"action": "install_extension", "extension": "ms-python.python"}
  {"action": "list_extensions"}
  {"action": "search_extensions", "query": "python"}
  {"action": "create_file", "file_path": "C:/Users/tu_usuario/proyecto/main.py", "content": "print('Hola')"}
"""


# ──────────────────────────────────────────────────────────────────────────
#  FUNCIONES AUXILIARES PARA EXTENSIONES POPULARES
# ──────────────────────────────────────────────────────────────────────────

def install_python_extension(player=None):
    """Instala la extensión de Python."""
    return vscode_control({"action": "install_extension", "extension": "ms-python.python"}, player)


def install_prettier_extension(player=None):
    """Instala la extensión de Prettier."""
    return vscode_control({"action": "install_extension", "extension": "esbenp.prettier-vscode"}, player)


def install_docker_extension(player=None):
    """Instala la extensión de Docker."""
    return vscode_control({"action": "install_extension", "extension": "ms-azuretools.vscode-docker"}, player)


def install_gitlens_extension(player=None):
    """Instala la extensión de GitLens."""
    return vscode_control({"action": "install_extension", "extension": "eamodio.gitlens"}, player)


# ─── Mapeo de extensiones populares ──────────────────────────────────────
POPULAR_EXTENSIONS = {
    "python": "ms-python.python",
    "prettier": "esbenp.prettier-vscode",
    "docker": "ms-azuretools.vscode-docker",
    "gitlens": "eamodio.gitlens",
    "typescript": "ms-vscode.vscode-typescript-next",
    "javascript": "ms-vscode.vscode-typescript-next",
    "react": "dsznajder.es7-react-js-snippets",
    "vue": "Vue.volar",
    "angular": "Angular.ng-template",
    "csharp": "ms-dotnettools.csharp",
    "go": "golang.Go",
    "rust": "rust-lang.rust-analyzer",
    "flutter": "Dart-Code.flutter",
    "solidity": "JuanBlanco.solidity",
    "tailwind": "bradlc.vscode-tailwindcss",
    "eslint": "dbaeumer.vscode-eslint",
    "editorconfig": "EditorConfig.EditorConfig",
    "gitgraph": "mhutchie.git-graph",
    "markdown": "yzhang.markdown-all-in-one",
    "todo": "Gruntfuggly.todo-tree",
    "material": "PKief.material-icon-theme",
    "dracula": "dracula-theme.theme-dracula",
}