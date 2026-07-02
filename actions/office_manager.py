import os
import sys

def office_manager(parameters: dict, player=None) -> str:
    """
    Office Automator (1000k Mastery).
    Parameters:
      - action: 'excel_new', 'excel_open', 'word_new', 'ppt_new', 'execute_script'
      - filepath: path to file if opening
      - script: raw python code to execute (for custom win32com scripts)
    """
    action = parameters.get("action", "")
    filepath = parameters.get("filepath", "")
    script = parameters.get("script", "")
    
    try:
        import win32com.client
    except ImportError:
        return "Error: pywin32 module is not installed. Use 'pip install pywin32' to enable Office automation."

    try:
        if action == "excel_new":
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            wb = excel.Workbooks.Add()
            return "Excel abierto y nuevo libro creado con éxito."
            
        elif action == "excel_open" and filepath:
            if not os.path.exists(filepath):
                return f"El archivo no existe: {filepath}"
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            wb = excel.Workbooks.Open(filepath)
            return f"Excel abierto con el archivo: {filepath}"
            
        elif action == "word_new":
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = True
            doc = word.Documents.Add()
            return "Word abierto y nuevo documento creado con éxito."
            
        elif action == "ppt_new":
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            ppt.Visible = True
            pres = ppt.Presentations.Add()
            return "PowerPoint abierto y nueva presentación creada con éxito."
            
        elif action == "execute_script" and script:
            # Ejecución dinámica para control "Nivel Dios" de Office
            # PRECAUCIÓN: Esto evalúa código en tiempo de ejecución
            local_vars = {"win32com": win32com}
            exec(script, globals(), local_vars)
            result = local_vars.get("result", "Script ejecutado sin devolver un resultado específico.")
            return f"Ejecución exitosa. Resultado:\n{result}"
            
        else:
            return "Acción no reconocida o parámetros faltantes."

    except Exception as e:
        return f"Error al interactuar con Office: {e}"
