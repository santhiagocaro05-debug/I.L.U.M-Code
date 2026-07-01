# -*- coding: utf-8 -*-
"""
playwright_agent.py — Agente Autónomo Avanzado de Navegación Web (Playwright)
Permite a ILUM iniciar sesión, llenar formularios invisibles, interactuar con el DOM
y realizar extracciones de datos profundas.
"""
import os
import sys
import traceback

def playwright_agent(parameters: dict, player=None) -> str:
    """
    Ejecuta un script de Playwright proporcionado por la IA para automatización web.
    """
    code = parameters.get("code", "")
    
    if not code:
        return "Error: No se proporcionó código Playwright para ejecutar."
        
    if player:
        player.write_log("🌐 Iniciando Agente Web Playwright...")
        
    try:
        import playwright
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Error: La librería 'playwright' no está instalada. Usa la terminal para instalarla."

    # Preparamos un entorno seguro para la ejecución
    # La IA proporcionará el código que debe usar 'page' y 'browser'
    # Ejemplo de código esperado de la IA:
    # page.goto('https://example.com')
    # page.fill('#user', 'admin')
    # result_data = page.title()
    
    wrapper_code = f"""
def _execute_playwright(page, browser):
    result_data = None
{chr(10).join(['    ' + line for line in code.split(chr(10))])}
    return result_data
"""
    
    local_env = {}
    try:
        # Compilar la función
        exec(wrapper_code, globals(), local_env)
        _execute = local_env['_execute_playwright']
        
        # Ejecutar Playwright
        with sync_playwright() as p:
            # Usar Chromium
            browser = p.chromium.launch(headless=False) 
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            try:
                result = _execute(page, browser)
                if result is None:
                    result = "Navegación completada con éxito."
                
                # Darle tiempo al usuario para ver si quedó abierta, o cerrar automático
                # En muchos casos el navegador se cerrará al salir del bloque 'with'
                return str(result)
            except Exception as e:
                return f"Error durante la automatización de la página: {str(e)}\nTraza:\n{traceback.format_exc()}"
            finally:
                browser.close()
                
    except Exception as e:
        return f"Error compilando/iniciando Playwright: {str(e)}\nTraza:\n{traceback.format_exc()}"
