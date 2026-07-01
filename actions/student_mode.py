import os
import json
import traceback
from pathlib import Path
from PyQt6.QtCore import Qt

def _get_api_key() -> str:
    from memory.config_manager import load_api_keys
    cfg = load_api_keys()
    return cfg.get("gemini_api_key", "")

def extract_text(file_path):
    path = Path(file_path)
    if not path.exists():
        return ""
    ext = path.suffix.lower()
    if ext == ".txt":
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"[Error leyendo TXT: {e}]"
    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            return f"[Error leyendo Word: {e}]"
    elif ext == ".pdf":
        try:
            try:
                from pypdf import PdfReader
                reader = PdfReader(path)
                text = ""
                for page in reader.pages:
                    t = page.extract_text()
                    if t: text += t + "\n"
                return text
            except ImportError:
                from PyPDF2 import PdfReader
                reader = PdfReader(path)
                text = ""
                for page in reader.pages:
                    t = page.extract_text()
                    if t: text += t + "\n"
                return text
        except Exception as e:
            return f"[Error leyendo PDF: {e}]"
    return ""

def check_docx_apa_formatting(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        report = []
        report.append("=== ANÁLISIS ESTRUCTURAL OBJETIVO (Archivo .docx) ===")
        
        # 1. Verificar Márgenes
        if doc.sections:
            sec = doc.sections[0]
            top = round(sec.top_margin.cm, 2)
            bottom = round(sec.bottom_margin.cm, 2)
            left = round(sec.left_margin.cm, 2)
            right = round(sec.right_margin.cm, 2)
            
            report.append("1. Márgenes (Requerido: 2.54 cm en todos los lados):")
            report.append(f"   - Superior: {top} cm | Inferior: {bottom} cm")
            report.append(f"   - Izquierdo: {left} cm | Derecho: {right} cm")
            if all(abs(m - 2.54) < 0.15 for m in [top, bottom, left, right]):
                report.append("   => [✓] CORRECTO: Todos los márgenes cumplen con la norma APA 7 (2.54 cm).")
            else:
                report.append("   => [✗] INCORRECTO: Los márgenes no están configurados a 2.54 cm en todos los lados. Por favor, ajústalos en tu procesador de textos.")
        
        # 2. Verificar Sangría y Espaciado
        sample_paragraphs = [p for p in doc.paragraphs if len(p.text.strip()) > 30][:10]
        
        indent_checks = []
        spacing_checks = []
        
        for p in sample_paragraphs:
            pf = p.paragraph_format
            first_indent = pf.first_line_indent
            if first_indent:
                first_cm = round(first_indent.cm, 2)
                indent_checks.append(first_cm)
            else:
                indent_checks.append(0.0)
                
            spacing = pf.line_spacing
            if spacing:
                spacing_checks.append(round(spacing, 1))
            else:
                spacing_checks.append(1.0)
                
        if indent_checks:
            avg_indent = sum(indent_checks) / len(indent_checks)
            report.append("\n2. Sangría de Primera Línea (Requerido: 1.27 cm):")
            report.append(f"   - Sangría promedio detectada en párrafos: {round(avg_indent, 2)} cm")
            if abs(avg_indent - 1.27) < 0.2:
                report.append("   => [✓] CORRECTO: La sangría promedio de primera línea cumple con APA 7 (1.27 cm).")
            else:
                report.append("   => [✗] INCORRECTO: No se detectó sangría de primera línea de 1.27 cm en los párrafos ordinarios.")
        else:
            report.append("\n2. Sangría de Primera Línea:")
            report.append("   => [✗] INCORRECTO: No se detectó sangría de primera línea de 1.27 cm. Párrafos planos detectados.")
            
        if spacing_checks:
            avg_spacing = sum(spacing_checks) / len(spacing_checks)
            report.append("\n3. Interlineado / Espaciado (Requerido: Doble / 2.0):")
            report.append(f"   - Interlineado promedio detectado: {round(avg_spacing, 1)}")
            if abs(avg_spacing - 2.0) < 0.2:
                report.append("   => [✓] CORRECTO: Interlineado doble (2.0) validado con éxito.")
            else:
                report.append("   => [✗] INCORRECTO: El interlineado promedio no es doble. Se recomienda cambiar el formato de párrafo a Interlineado Doble.")
        else:
            report.append("\n3. Interlineado / Espaciado:")
            report.append("   => [✗] INCORRECTO: No se detectó interlineado doble (2.0) en el documento.")
            
        # 3. Tipografía
        fonts = set()
        font_sizes = set()
        for p in sample_paragraphs:
            for r in p.runs:
                if r.font.name:
                    fonts.add(r.font.name)
                if r.font.size:
                    font_sizes.add(round(r.font.size.pt, 1))
                    
        report.append("\n4. Tipografía y Tamaño:")
        if fonts:
            report.append(f"   - Fuentes detectadas: {', '.join(fonts)}")
        if font_sizes:
            report.append(f"   - Tamaños detectados: {', '.join(str(s) + 'pt' for s in font_sizes)}")
            
        valid_fonts = {"Times New Roman", "Arial", "Calibri", "Georgia", "Lucida Sans Unicode", "Computer Modern"}
        if fonts.intersection(valid_fonts):
            report.append("   => [✓] CORRECTO: Se están utilizando fuentes admitidas por APA 7 (como Times New Roman, Calibri, Arial).")
        else:
            report.append("   => [✗] INCORRECTO o No Reconocido: Se recomienda utilizar fuentes oficiales de APA 7.")
            
        report.append("\n=======================================================\n")
        return "\n".join(report)
        
    except Exception as e:
        return f"[Error en análisis estructural objetivo: {e}]"

def activar_modo_estudiante(parameters: dict, player=None, speak=None) -> str:
    """Activa la interfaz del Modo Estudiante y muestra sus herramientas."""
    if player and hasattr(player, 'open_student_mode'):
        if hasattr(player, '_win') and player._win is not None:
            from PyQt6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(player._win, "open_student_mode", Qt.ConnectionType.QueuedConnection)
        else:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, player.open_student_mode)
        return "Modo estudiante activado. He abierto la ventana de herramientas académicas en tu pantalla."
    return "Error: No se pudo acceder a la interfaz de usuario para abrir el modo estudiante."

def student_paraphrase(parameters: dict, player=None, speak=None) -> str:
    """Parafrasea un texto académico o archivo y actualiza el panel Ghost de forma interactiva."""
    text = parameters.get("text", "").strip()
    file_path = parameters.get("file_path", "").strip()
    
    if not text and file_path:
        text = extract_text(file_path)
        
    if not text:
        return "Error: No proporcionaste ningún texto o archivo para parafrasear, sir."
        
    try:
        from google import genai
        client = genai.Client(api_key=_get_api_key())
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=(
                "Actúa como un reescritor y parafraseador de nivel académico extremadamente sofisticado.\n"
                "Reescribe el siguiente texto con un tono académico riguroso y formal, pero con una estructura que evite de forma absoluta cualquier patrón de detección por Inteligencias Artificiales (como GPTZero o Turnitin).\n"
                "Conserva el significado exacto de las ideas pero utiliza sinónimos avanzados y variaciones de sintaxis complejas:\n\n"
                f"{text}"
            )
        )
        paraphrased = resp.text.strip()
        
        # Actualizar UI mediante señales seguras
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("paraphrase", {"input": text, "output": paraphrased})
            
        return f"He terminado de parafrasear tu texto académicamente, sir. Lo he cargado en la interfaz Ghost. Aquí tienes un fragmento:\n\n{paraphrased[:300]}..."
    except Exception as e:
        return f"Error en el parafraseo académico: {e}"

def student_verify_apa(parameters: dict, player=None, speak=None) -> str:
    """Revisa y formatea citas o textos académicos con la norma APA 7ma Edición."""
    text = parameters.get("text", "").strip()
    file_path = parameters.get("file_path", "").strip()
    
    if not text and file_path:
        text = extract_text(file_path)
        
    if not text:
        return "Error: No proporcionaste referencias o texto para verificar, sir."
        
    try:
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("apa", {"input": text, "output": "Analizando...", "status": "Iniciando validación APA 7...", "progress": 20})
            
        formatting_report = ""
        if file_path:
            if file_path.lower().endswith(".docx"):
                formatting_report = check_docx_apa_formatting(file_path)
            elif file_path.lower().endswith(".pdf"):
                formatting_report = (
                    "=== ANÁLISIS ESTRUCTURAL OBJETIVO (Archivo .pdf) ===\n"
                    "[✓] Documento cargado exitosamente en formato PDF.\n"
                    "[✓] Analizando estructura visualmente con Artemisa Multimodal...\n\n"
                )
        else:
            formatting_report = (
                "=== AVISO DE FORMATO ESTÁNDAR ===\n"
                "[!] Has ingresado el texto en formato plano. No es posible analizar objetivamente "
                "la sangría de primera línea (1.27 cm), márgenes del documento (2.54 cm) ni el interlineado original (2.0) desde el panel de texto plano.\n"
                "Para una evaluación estructural objetiva y realista de tu documento, por favor carga el archivo original "
                "en formato Word (.docx) o PDF usando la orden de voz para el archivo correspondiente, sir.\n\n"
            )
            
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("apa", {"input": text, "output": "Llamando a Artemisa...", "status": "Verificando estructura de citas y bibliografía...", "progress": 60})
            
        pil_images = []
        if file_path:
            try:
                import fitz
                from PIL import Image
                doc = fitz.open(file_path)
                if len(doc) > 0:
                    p = doc.load_page(0)
                    pix = p.get_pixmap(dpi=120)
                    pil_images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
                if len(doc) > 1:
                    p = doc.load_page(1)
                    pix = p.get_pixmap(dpi=120)
                    pil_images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
                doc.close()
            except Exception as img_err:
                print(f"Error loading PIL images for Gemini multimodal in action: {img_err}")
                
        prompt = (
            "Actúa como un experto en redacción científica y normas de publicación internacional.\n"
            "Analiza el siguiente texto académico y formatea/corrige todo estrictamente bajo las Normas APA 7ma Edición (citas, bibliografía, referencias, redacción científica).\n"
            "Si hay imágenes de páginas del documento adjuntas, ANALÍZALAS VISUALMENTE para comprobar el diseño estético de alta fidelidad:\n"
            "- Verifica los márgenes (deben ser de 2.54 cm / 1 pulgada en todos los lados).\n"
            "- Verifica si la sangría de primera línea está aplicada visualmente (1.27 cm / 0.5 pulgadas) en los párrafos de cuerpo.\n"
            "- Revisa si la Portada (título en negrita, centrado, datos institucionales, etc.) está correctamente estructurada según APA 7 (primera hoja).\n"
            "- Verifica si los números de página aparecen en la esquina superior derecha del encabezado.\n"
            "- Verifica que el interlineado sea doble (2.0).\n\n"
            "Devuelve un reporte sumamente estructurado con:\n"
            "1. EVALUACIÓN Y ANÁLISIS DE DISEÑO VISUAL (si hay imágenes adjuntas, sé sumamente detallado, específico y constructivo sobre los márgenes, sangrías y portada observados en las fotos).\n"
            "2. CORRECCIONES DE CITAS Y TEXTO (muestra los textos originales vs corregidos y su justificación).\n"
            "3. RECOMENDACIONES FINALES DE ESTRUCTURACIÓN ACADÉMICA.\n\n"
            f"TEXTO DEL DOCUMENTO:\n\n{text}"
        )
        
        contents = [prompt]
        contents.extend(pil_images)
        
        from google import genai
        client = genai.Client(api_key=_get_api_key())
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents
        )
        verified = resp.text.strip()
        
        combined_result = formatting_report + "\n" + verified
        
        if player and hasattr(player, '_win') and player._win is not None:
            # Enviar actualización completa
            player._win.student_action_sig.emit("apa", {
                "input": text, 
                "output": combined_result,
                "status": "Verificación APA 7 completada con éxito.",
                "progress": 100
            })
            
        return f"Validación de citas APA 7 completada con éxito, sir. He cargado los resultados estructurales y del contenido en tu pantalla."
    except Exception as e:
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("apa", {"input": text, "output": f"Error: {e}", "status": "Error en validación APA 7", "progress": 0})
        return f"Error en la validación APA 7: {e}"

def student_pdf_to_word(parameters: dict, player=None, speak=None) -> str:
    """Convierte un PDF del sistema a documento Word .docx y lo abre en la UI."""
    pdf_path = parameters.get("pdf_path", "").strip()
    docx_path = parameters.get("docx_path", "").strip()
    
    if not pdf_path:
        return "Error: Por favor, indica la ruta del archivo PDF que deseas convertir, sir."
        
    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.exists():
        return f"Error: No se encontró el archivo PDF en la ruta '{pdf_path}'."
        
    if not docx_path:
        base_descargas = os.path.join(os.path.expanduser("~"), "Downloads", "Ilum_Downloads", "Conversiones")
        os.makedirs(base_descargas, exist_ok=True)
        docx_path = os.path.join(base_descargas, pdf_path_obj.with_suffix(".docx").name)
        
    try:
        # Enviar estado a la UI
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("pdf", {"pdf_path": pdf_path, "status": "Iniciando conversión de alta fidelidad...", "progress": 10})
            
        try:
            # Intento de alta fidelidad usando pdf2docx
            if player and hasattr(player, '_win') and player._win is not None:
                player._win.student_action_sig.emit("pdf", {"pdf_path": pdf_path, "status": "Reconstruyendo estructura, tablas y diseño (pdf2docx)...", "progress": 40})
            from pdf2docx import Converter
            cv = Converter(pdf_path)
            cv.convert(docx_path)
            cv.close()
        except Exception as conv_err:
            # Fallback a la extracción lineal si pdf2docx falla
            if player and hasattr(player, '_win') and player._win is not None:
                player._win.student_action_sig.emit("pdf", {"pdf_path": pdf_path, "status": "Error en pdf2docx. Usando fallback de extracción lineal...", "progress": 50})
            
            text = extract_text(pdf_path)
            if text.startswith("[Error"):
                raise Exception(f"Conversión de alta fidelidad fallida ({conv_err}) y fallo en extracción lineal: {text}")
                
            from docx import Document
            doc = Document()
            doc.add_heading(pdf_path_obj.stem, 0)
            for p in text.split("\n\n"):
                if p.strip():
                    doc.add_paragraph(p.strip())
            doc.save(docx_path)
        
        # Enviar éxito a la UI
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("pdf", {"pdf_path": pdf_path, "status": "Conversión completada con éxito.", "progress": 100})
            
        return f"Éxito: He convertido tu PDF a Word con éxito, sir. Guardado en '{docx_path}'."
    except Exception as e:
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("pdf", {"pdf_path": pdf_path, "status": f"Error: {e}", "progress": 0})
        return f"Error al convertir el PDF: {e}"

def student_quality_report(parameters: dict, player=None, speak=None) -> str:
    """Genera un reporte de calidad académica y rigor estructural para un archivo académico."""
    file_path = parameters.get("file_path", "").strip()
    
    if not file_path:
        return "Error: Por favor, indica la ruta del archivo académico para evaluar, sir."
        
    path = Path(file_path)
    if not path.exists():
        return f"Error: No encontré ningún archivo en la ruta '{file_path}'."
        
    try:
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("quality", {"file_path": file_path, "report_html": "Artemisa está analizando la calidad académica de tu documento..."})
            
        text = extract_text(file_path)
        if not text.strip() or text.startswith("[Error"):
            raise Exception("No se pudo extraer texto legible del documento seleccionado.")
            
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=_get_api_key())
        
        prompt = (
            "Actúa como un revisor académico senior de revistas científicas de alto impacto.\n"
            f"Analiza el siguiente texto extraído del documento '{path.name}' y genera un REPORTE DE CALIDAD ACADÉMICA formal y estructurado en formato HTML estilizado.\n\n"
            "La respuesta DEBE ser únicamente código HTML (sin bloques de código markdown como ```html o similares) que use etiquetas limpias de estructura. Debe contener los siguientes apartados estructurados de forma atractiva y eficiente:\n"
            "1. Calificación Global (por ejemplo, 85/100) con explicación breve de su rango de calidad (Excelente, Aceptable, Regular o Crítico).\n"
            "2. Fortalezas Clave (3-4 puntos estructurados de forma concisa).\n"
            "3. Puntos de Mejora Prioritarios (3-4 aspectos en orden de importancia).\n"
            "4. Evaluación del Rigor Científico (método, marco conceptual, fuentes bibliográficas).\n"
            "5. Plan de Acción Académico Eficiente (pasos ordenados para optimizar el documento).\n\n"
            "Diseña el HTML de forma sobria y moderna, usando bloques/tarjetas estilizados con fondos oscuros translúcidos, bordes finos de color de acento, fuentes legibles y colores semánticos (verde/cyan para fortalezas, ámbar/rojo para debilidades). No uses estilos externos ni JS complejo. Asegura que sea compatible con QTextEdit de Qt.\n\n"
            f"TEXTO DEL DOCUMENTO A EVALUAR:\n\n{text[:9000]}"
        )
        
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        report_html = resp.text.strip()
        if report_html.startswith("```"):
            lines = report_html.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            report_html = "\n".join(lines).strip()
            
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("quality", {"file_path": file_path, "report_html": report_html})
            
        return f"Reporte de Calidad Académica completado para '{path.name}', sir. Lo he cargado en la pestaña correspondiente de tu pantalla."
    except Exception as e:
        if player and hasattr(player, '_win') and player._win is not None:
            player._win.student_action_sig.emit("quality", {"file_path": file_path, "report_html": f"<div style='color:#ff3b30;'>Error: {e}</div>"})
        return f"Error al generar el reporte de calidad: {e}"
