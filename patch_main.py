import re

def patch_main():
    with open("main.py", "r", encoding="utf-8") as f:
        code = f.read()

    # 1. Add tools to TOOL_DECLARATIONS
    if '"name": "office_manager"' not in code:
        new_tools = """
    {
        "name": "office_manager",
        "description": "Control Nivel Dios de Office (Excel, Word, PowerPoint).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": { "type": "STRING", "description": "excel_new, excel_open, word_new, ppt_new, execute_script" },
                "filepath": { "type": "STRING", "description": "Ruta si se abre archivo" },
                "script": { "type": "STRING", "description": "Código Python win32com a ejecutar (para manipular celdas, graficas, etc)" }
            },
            "required": ["action"]
        }
    },
    {
        "name": "social_manager",
        "description": "Manejo de redes sociales como Whatsapp, Instagram y Discord.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "platform": { "type": "STRING", "description": "whatsapp, instagram, discord" },
                "action": { "type": "STRING", "description": "open, send_message, post_story" },
                "target": { "type": "STRING", "description": "numero de telefono o usuario" },
                "message": { "type": "STRING", "description": "mensaje a enviar" }
            },
            "required": ["platform", "action"]
        }
    },
    {
        "name": "pc_settings",
        "description": "Manejo de ajustes de PC (Windows).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "setting": { "type": "STRING", "description": "bluetooth, wifi, display, sound, update, apps, main" }
            },
            "required": ["setting"]
        }
    },
    {
        "name": "work_mode",
        "description": "Inicia o edita el Modo Trabajo (abre aplicaciones en lote).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": { "type": "STRING", "description": "start, add_app, remove_app, list_apps" },
                "app_path": { "type": "STRING", "description": "Ruta de la app o url" }
            },
            "required": ["action"]
        }
    },
    {
        "name": "embedded_browser",
        "description": "Abre el navegador web INCRUSTADO de ILUM en vez de Chrome. Usalo para youtube o google si el usuario no especifica.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": { "type": "STRING", "description": "URL a abrir (ej. https://youtube.com)" }
            },
            "required": ["url"]
        }
    },
"""
        code = code.replace("TOOL_DECLARATIONS = [", "TOOL_DECLARATIONS = [\n" + new_tools)
        print("Tools added to declarations.")

    # 2. Add imports
    imports = """from actions.office_manager import office_manager
from actions.social_manager import social_manager, pc_settings
from actions.work_mode import work_mode
"""
    if "from actions.office_manager" not in code:
        code = code.replace("from actions.spotify import spotify_action", "from actions.spotify import spotify_action\n" + imports)

    # 3. Add handlers
    handlers = """
                elif name == "office_manager":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: office_manager(parameters=args, player=self.ui))
                elif name == "social_manager":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: social_manager(parameters=args, player=self.ui))
                elif name == "pc_settings":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: pc_settings(parameters=args, player=self.ui))
                elif name == "work_mode":
                    r = await loop.run_in_executor(_TOOL_EXECUTOR, lambda: work_mode(parameters=args, player=self.ui))
                elif name == "embedded_browser":
                    url = args.get("url", "")
                    self.ui.open_embedded_browser(url)
                    r = f"Navegador emergente de ILUM abierto en: {url}"
"""
    if 'elif name == "office_manager":' not in code:
        code = code.replace('elif name == "spotify":', handlers + '                elif name == "spotify":')
        print("Handlers added.")

    with open("main.py", "w", encoding="utf-8") as f:
        f.write(code)

if __name__ == "__main__":
    patch_main()
