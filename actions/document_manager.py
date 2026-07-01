import os
import json
import traceback
from pathlib import Path

def document_manager(parameters: dict, player=None) -> str:
    """
    Manages documents (PDF, Word, Excel, Text).
    Supports opening them in their native apps, reading their text, or editing them.
    """
    action = parameters.get("action", "").lower()
    file_path_str = parameters.get("path", "")
    content = parameters.get("content", "")

    if not action or not file_path_str:
        return "Error: Faltan parámetros requeridos ('action' o 'path')."

    # Resolve paths (desktop, documents, downloads, etc)
    path_lower = file_path_str.lower()
    home_dir = Path.home()
    if path_lower.startswith("desktop"):
        file_path = home_dir / "Desktop" / file_path_str[len("desktop"):].lstrip("\\/")
    elif path_lower.startswith("documents"):
        file_path = home_dir / "Documents" / file_path_str[len("documents"):].lstrip("\\/")
    elif path_lower.startswith("downloads"):
        file_path = home_dir / "Downloads" / file_path_str[len("downloads"):].lstrip("\\/")
    else:
        file_path = Path(file_path_str)

    if not file_path.exists() and action not in ["edit"]:
        # Let's try searching on Desktop as fallback if not absolute
        if not file_path.is_absolute():
            file_path = home_dir / "Desktop" / file_path_str
            if not file_path.exists():
                return f"Error: No se encontró el archivo '{file_path_str}'."

    try:
        if action == "open":
            os.startfile(str(file_path))
            return f"He abierto el documento '{file_path.name}' en pantalla."

        elif action == "read" or action == "view":
            ext = file_path.suffix.lower()
            if ext in [".txt", ".md", ".json", ".csv", ".py", ".js", ".html", ".log"]:
                text = file_path.read_text(encoding="utf-8", errors="replace")
                return f"Contenido de '{file_path.name}':\n\n{text[:2000]}"
            elif ext == ".docx":
                try:
                    import docx
                    doc = docx.Document(file_path)
                    text = "\n".join([p.text for p in doc.paragraphs])
                    return f"Contenido de '{file_path.name}' (Word):\n\n{text[:2000]}"
                except ImportError:
                    return "Error: La librería python-docx no está instalada."
            elif ext == ".xlsx":
                try:
                    import pandas as pd
                    df = pd.read_excel(file_path)
                    return f"Resumen de '{file_path.name}' (Excel):\n\nColumnas: {list(df.columns)}\nFilas totales: {len(df)}\n\nPrimeras filas:\n{df.head(5).to_string()}"
                except ImportError:
                    return "Error: Las librerías openpyxl o pandas no están instaladas."
            else:
                return f"Error: No puedo leer directamente archivos de extensión '{ext}'. Usa la acción 'open' para verlo."

        elif action == "edit" or action == "create":
            ext = file_path.suffix.lower()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not content and action == "edit":
                os.startfile(str(file_path))
                return f"He abierto el archivo '{file_path.name}' para que lo edites manualmente."
                
            if ext == ".docx":
                try:
                    import docx
                    if file_path.exists() and action == "edit":
                        doc = docx.Document(file_path)
                    else:
                        doc = docx.Document()
                    doc.add_paragraph(content)
                    doc.save(file_path)
                    return f"El documento Word '{file_path.name}' ha sido modificado y guardado con éxito."
                except Exception as e:
                    return f"Error al procesar Word: {e}"
            elif ext == ".xlsx":
                try:
                    import pandas as pd
                    # Si mandan contenido en JSON o CSV simple, lo convertimos a dataframe
                    # Para simplificar, si no es estructurado, lo abrimos manualmente.
                    if content.startswith("{") or content.startswith("["):
                        df = pd.read_json(content)
                        if file_path.exists() and action == "edit":
                            existing_df = pd.read_excel(file_path)
                            df = pd.concat([existing_df, df], ignore_index=True)
                        df.to_excel(file_path, index=False)
                        return f"El documento Excel '{file_path.name}' ha sido actualizado."
                    else:
                        return "Para editar Excel automáticamente, el 'content' debe ser un JSON estructurado. Abriendo archivo..."
                except Exception as e:
                    return f"Error al procesar Excel: {e}"
            else:
                if content:
                    file_path.write_text(content, encoding="utf-8")
                    return f"El archivo '{file_path.name}' ha sido guardado con éxito."
                else:
                    os.startfile(str(file_path))
                    return f"He abierto el archivo '{file_path.name}'."
                
        else:
            return f"Error: Acción '{action}' no reconocida en document_manager."

    except Exception as e:
        return f"Error en document_manager: {str(e)}\n{traceback.format_exc()}"
