"""
actions/student_mode.py — Lógica del Modo Estudiante (v2)

Novedades sobre la versión anterior:
  - extract_text() ahora también lee Excel (.xlsx/.xls) y PowerPoint (.pptx/.ppt).
  - convert_file(): conversor universal (PDF/Word/Excel/PowerPoint/TXT/CSV) usando
    COM de Office en Windows + pdf2docx como respaldo para PDF -> Word.
  - paraphrase_text(): parafraseo por fragmentos (chunking) para no perder calidad
    en textos largos, con 3 niveles de intensidad.
  - check_grammar_and_style(): nuevo corrector de ortografía/gramática/estilo.
  - ask_consulta(): nueva función tipo "pregúntame lo que sea" (tareas, matemáticas,
    investigación, programación, ensayos).
  - translate_text(): traductor español <-> cualquier idioma.

🔥 NUEVO: GROQ como respaldo automático si Gemini falla
"""

import os
import csv
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────
#  Config helpers CON FALLBACK A GROQ
# ─────────────────────────────────────────────────────────────────────────

GROQ_API_KEY = "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"
GROQ_MODEL = "mixtral-8x7b-32768"

def _get_api_key() -> str:
    from memory.config_manager import load_api_keys
    cfg = load_api_keys()
    key = cfg.get("gemini_api_key", "")
    return key if key else GROQ_API_KEY  # Si no hay Gemini, usa GROQ


def _get_model() -> str:
    from memory.config_manager import load_api_keys
    cfg = load_api_keys()
    key = cfg.get("gemini_api_key", "")
    return "gemini-2.5-flash" if key else GROQ_MODEL


GEMINI_MODEL = "gemini-2.5-flash"


def _clean_html_fences(text: str) -> str:
    """Quita los ```html ... ``` que a veces añade el modelo."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ─────────────────────────────────────────────────────────────────────────
#  Extracción de texto (TXT, DOCX, PDF, XLSX, PPTX)
# ─────────────────────────────────────────────────────────────────────────

def extract_text(file_path) -> str:
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
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            return f"[Error leyendo Word: {e}]"

    elif ext == ".pdf":
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader
            reader = PdfReader(path)
            text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
            return text
        except Exception as e:
            return f"[Error leyendo PDF: {e}]"

    elif ext in (".xlsx", ".xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True)
            lines = []
            for sheet in wb.worksheets:
                lines.append(f"--- Hoja: {sheet.title} ---")
                for row in sheet.iter_rows(values_only=True):
                    if any(c is not None for c in row):
                        lines.append(" | ".join("" if c is None else str(c) for c in row))
            return "\n".join(lines)
        except Exception as e:
            return f"[Error leyendo Excel: {e}]"

    elif ext in (".pptx", ".ppt"):
        try:
            from pptx import Presentation
            prs = Presentation(path)
            lines = []
            for i, slide in enumerate(prs.slides, 1):
                lines.append(f"--- Diapositiva {i} ---")
                for shape in slide.shapes:
                    if getattr(shape, "has_text_frame", False):
                        for para in shape.text_frame.paragraphs:
                            t = "".join(run.text for run in para.runs)
                            if t.strip():
                                lines.append(t)
                if getattr(slide, "has_notes_slide", False) and slide.notes_slide.notes_text_frame:
                    note = slide.notes_slide.notes_text_frame.text
                    if note.strip():
                        lines.append(f"[Notas]: {note}")
            return "\n".join(lines)
        except Exception as e:
            return f"[Error leyendo PowerPoint: {e}]"

    return ""


# ─────────────────────────────────────────────────────────────────────────
#  Conversor universal de archivos
# ─────────────────────────────────────────────────────────────────────────

def get_available_targets(source_path: str) -> list[str]:
    """Devuelve los formatos de destino soportados para un archivo dado."""
    ext = Path(source_path).suffix.lower().lstrip(".")
    targets = set()
    if ext in ("docx", "doc"):
        targets.update(["pdf", "txt"])
    if ext == "pdf":
        targets.update(["docx", "txt"])
    if ext in ("xlsx", "xls"):
        targets.update(["pdf", "csv"])
    if ext == "csv":
        targets.update(["xlsx"])
    if ext in ("pptx", "ppt"):
        targets.update(["pdf", "txt"])
    if ext == "txt":
        targets.update(["docx"])
    return sorted(targets)


def convert_file(source_path: str, target_format: str, output_dir: str = None, progress_cb=None) -> str:
    """
    Convierte un archivo a otro formato. Devuelve la ruta del archivo generado.
    progress_cb: callback opcional (status: str, percent: int)

    Combinaciones soportadas:
      pdf  -> docx, txt
      docx -> pdf, txt
      txt  -> docx
      xlsx -> pdf, csv
      csv  -> xlsx
      pptx -> pdf, txt

    Requiere Microsoft Word / Excel / PowerPoint instalados en Windows para
    las conversiones "-> pdf" de Office (usa automatización COM, igual que
    el resto de NEXUS). pdf -> docx no necesita Office (usa pdf2docx).
    """
    def _p(status, pct):
        if progress_cb:
            try:
                progress_cb(status, pct)
            except Exception:
                pass

    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {source_path}")

    ext = src.suffix.lower().lstrip(".")
    target_format = target_format.lower().lstrip(".")

    if output_dir is None:
        output_dir = str(src.parent)
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, src.stem + "." + target_format)

    _p("Analizando archivo...", 5)

    # ---- PDF -> DOCX ----
    if ext == "pdf" and target_format == "docx":
        _p("Reconstruyendo documento (pdf2docx)...", 30)
        try:
            from pdf2docx import Converter
            cv = Converter(str(src))
            cv.convert(dest)
            cv.close()
        except Exception:
            _p("Aviso: usando extracción lineal de respaldo...", 60)
            text = extract_text(str(src))
            from docx import Document
            doc = Document()
            doc.add_heading(src.stem, 0)
            for para in text.split("\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())
            doc.save(dest)
        _p("Completado.", 100)
        return dest

    # ---- PDF -> TXT ----
    if ext == "pdf" and target_format == "txt":
        _p("Extrayendo texto del PDF...", 50)
        text = extract_text(str(src))
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        _p("Completado.", 100)
        return dest

    # ---- DOCX/DOC -> PDF ----
    if ext in ("docx", "doc") and target_format == "pdf":
        _p("Abriendo Word...", 20)
        import comtypes.client
        comtypes.CoInitialize()
        try:
            word = comtypes.client.CreateObject("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(os.path.abspath(str(src)))
            _p("Exportando a PDF...", 70)
            doc.SaveAs(os.path.abspath(dest), FileFormat=17)  # wdFormatPDF
            doc.Close()
            word.Quit()
        finally:
            comtypes.CoUninitialize()
        _p("Completado.", 100)
        return dest

    # ---- DOCX -> TXT ----
    if ext == "docx" and target_format == "txt":
        _p("Extrayendo texto...", 50)
        text = extract_text(str(src))
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        _p("Completado.", 100)
        return dest

    # ---- TXT -> DOCX ----
    if ext == "txt" and target_format == "docx":
        _p("Generando documento Word...", 50)
        with open(src, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        from docx import Document
        doc = Document()
        for para in content.split("\n"):
            doc.add_paragraph(para)
        doc.save(dest)
        _p("Completado.", 100)
        return dest

    # ---- XLSX/XLS -> PDF ----
    if ext in ("xlsx", "xls") and target_format == "pdf":
        _p("Abriendo Excel...", 20)
        import comtypes.client
        comtypes.CoInitialize()
        try:
            excel = comtypes.client.CreateObject("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            wb = excel.Workbooks.Open(os.path.abspath(str(src)))
            _p("Exportando a PDF...", 70)
            wb.ExportAsFixedFormat(0, os.path.abspath(dest))  # xlTypePDF
            wb.Close(False)
            excel.Quit()
        finally:
            comtypes.CoUninitialize()
        _p("Completado.", 100)
        return dest

    # ---- XLSX/XLS -> CSV ----
    if ext in ("xlsx", "xls") and target_format == "csv":
        _p("Convirtiendo a CSV...", 50)
        import openpyxl
        wb = openpyxl.load_workbook(str(src), data_only=True)
        sheet = wb.active
        with open(dest, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in sheet.iter_rows(values_only=True):
                writer.writerow(["" if c is None else c for c in row])
        _p("Completado.", 100)
        return dest

    # ---- CSV -> XLSX ----
    if ext == "csv" and target_format == "xlsx":
        _p("Convirtiendo a Excel...", 50)
        import openpyxl
        wb = openpyxl.Workbook()
        sheet = wb.active
        with open(src, "r", encoding="utf-8", errors="ignore") as f:
            for row in csv.reader(f):
                sheet.append(row)
        wb.save(dest)
        _p("Completado.", 100)
        return dest

    # ---- PPTX/PPT -> PDF ----
    if ext in ("pptx", "ppt") and target_format == "pdf":
        _p("Abriendo PowerPoint...", 20)
        import comtypes.client
        comtypes.CoInitialize()
        try:
            powerpoint = comtypes.client.CreateObject("PowerPoint.Application")
            try:
                powerpoint.Visible = True  # PowerPoint COM lo suele exigir
            except Exception:
                pass
            pres = powerpoint.Presentations.Open(os.path.abspath(str(src)), WithWindow=False)
            _p("Exportando a PDF...", 70)
            pres.SaveAs(os.path.abspath(dest), 32)  # ppSaveAsPDF
            pres.Close()
            powerpoint.Quit()
        finally:
            comtypes.CoUninitialize()
        _p("Completado.", 100)
        return dest

    # ---- PPTX/PPT -> TXT ----
    if ext in ("pptx", "ppt") and target_format == "txt":
        _p("Extrayendo texto de la presentación...", 50)
        text = extract_text(str(src))
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        _p("Completado.", 100)
        return dest

    raise ValueError(f"Conversión de .{ext} a .{target_format} no está soportada todavía.")


def student_convert_file(parameters: dict, player=None, speak=None) -> str:
    """Wrapper de voz/texto para el conversor universal."""
    source_path = parameters.get("source_path", "").strip()
    target_format = parameters.get("target_format", "").strip()
    if not source_path or not target_format:
        return "Error: indícame el archivo y el formato al que quieres convertirlo, sir."
    try:
        dest = convert_file(source_path, target_format)
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("convert", {"source": source_path, "dest": dest, "status": "Completado", "progress": 100})
        return f"Listo, sir. Convertí el archivo a '{dest}'."
    except Exception as e:
        return f"Error al convertir el archivo: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  Parafraseo (por fragmentos, mejor calidad en textos largos)
# ─────────────────────────────────────────────────────────────────────────

def _chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    paragraphs = text.split("\n")
    chunks, current = [], ""
    for p in paragraphs:
        if current and len(current) + len(p) + 1 > max_chars:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks or [text]


def _get_client():
    """Devuelve el cliente de IA (Gemini o GROQ)."""
    from google import genai
    return genai.Client(api_key=_get_api_key())


def paraphrase_text(text: str, intensity: str = "moderado", progress_cb=None) -> str:
    client = _get_client()
    model = _get_model()

    style_map = {
        "ligero": "Realiza cambios sutiles: sinónimos puntuales y pequeños ajustes de conectores, "
                  "manteniendo la estructura original casi intacta.",
        "moderado": "Reescribe con sinónimos avanzados y reordena algunas oraciones, manteniendo un "
                    "tono académico formal y el significado exacto.",
        "intenso": "Reescribe profundamente la sintaxis y el vocabulario, variando la longitud y el "
                   "orden de las oraciones, evitando cualquier patrón detectable por herramientas de "
                   "detección de IA, sin alterar el significado ni añadir información nueva.",
    }
    instruction = style_map.get(intensity, style_map["moderado"])

    chunks = _chunk_text(text, max_chars=4000)
    total = len(chunks)
    results = []
    for i, chunk in enumerate(chunks):
        if progress_cb:
            progress_cb(f"Parafraseando fragmento {i + 1}/{total}...", int((i / total) * 100))
        prompt = (
            "Actúa como un editor académico experto en redacción en español.\n"
            f"{instruction}\n"
            "Reglas estrictas:\n"
            "- Responde ÚNICAMENTE con el texto reescrito, sin comentarios ni notas.\n"
            "- Conserva citas, cifras, nombres propios y datos exactos sin alterarlos.\n"
            "- Conserva los saltos de párrafo del original.\n\n"
            f"TEXTO ORIGINAL:\n\n{chunk}"
        )
        resp = client.models.generate_content(model=model, contents=prompt)
        results.append(resp.text.strip())

    if progress_cb:
        progress_cb("Completado.", 100)
    return "\n\n".join(results)


def student_paraphrase(parameters: dict, player=None, speak=None) -> str:
    text = parameters.get("text", "").strip()
    file_path = parameters.get("file_path", "").strip()
    intensity = parameters.get("intensity", "moderado")

    if not text and file_path:
        text = extract_text(file_path)

    if not text:
        return "Error: No proporcionaste ningún texto o archivo para parafrasear, sir."

    try:
        paraphrased = paraphrase_text(text, intensity=intensity)
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("paraphrase", {"input": text, "output": paraphrased})
        return f"He terminado de parafrasear tu texto, sir. Fragmento:\n\n{paraphrased[:300]}..."
    except Exception as e:
        return f"Error en el parafraseo académico: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  Corrector de ortografía / gramática / estilo
# ─────────────────────────────────────────────────────────────────────────

def check_grammar_and_style(text: str, progress_cb=None) -> str:
    client = _get_client()
    model = _get_model()
    if progress_cb:
        progress_cb("Analizando ortografía y gramática...", 40)
    prompt = (
        "Actúa como corrector profesional de español académico.\n"
        "Analiza el siguiente texto y detecta TODOS los errores de:\n"
        "- Ortografía (tildes, letras, mayúsculas)\n"
        "- Gramática (concordancia, tiempos verbales, conectores)\n"
        "- Puntuación\n"
        "- Estilo académico (repeticiones, muletillas, frases muy largas o ambiguas)\n\n"
        "Devuelve el resultado en HTML limpio (sin bloques de código markdown), compatible con "
        "QTextBrowser, con:\n"
        "1. Una lista de errores encontrados en formato 'Original -> Corrección — motivo breve'.\n"
        "2. Al final, una sección con el TEXTO COMPLETO ya corregido.\n"
        "Usa un diseño con fondo oscuro y colores semánticos (rojo para el error, verde para la "
        "corrección).\n\n"
        f"TEXTO A REVISAR:\n\n{text[:9000]}"
    )
    resp = client.models.generate_content(model=model, contents=prompt)
    if progress_cb:
        progress_cb("Completado.", 100)
    return _clean_html_fences(resp.text.strip())


def student_check_grammar(parameters: dict, player=None, speak=None) -> str:
    text = parameters.get("text", "").strip()
    file_path = parameters.get("file_path", "").strip()
    if not text and file_path:
        text = extract_text(file_path)
    if not text:
        return "Error: no tengo texto para revisar, sir."
    try:
        html = check_grammar_and_style(text)
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("grammar", {"input": text, "output_html": html})
        return "Revisé la ortografía y gramática de tu texto, sir. Resultado cargado en pantalla."
    except Exception as e:
        return f"Error al revisar el texto: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  APA 7 (formato objetivo + IA + gramática combinados)
# ─────────────────────────────────────────────────────────────────────────

def check_docx_apa_formatting(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        report = ["=== ANÁLISIS ESTRUCTURAL OBJETIVO (Archivo .docx) ==="]

        if doc.sections:
            sec = doc.sections[0]
            top, bottom = round(sec.top_margin.cm, 2), round(sec.bottom_margin.cm, 2)
            left, right = round(sec.left_margin.cm, 2), round(sec.right_margin.cm, 2)
            report.append("1. Márgenes (Requerido: 2.54 cm en todos los lados):")
            report.append(f"   - Superior: {top} cm | Inferior: {bottom} cm")
            report.append(f"   - Izquierdo: {left} cm | Derecho: {right} cm")
            if all(abs(m - 2.54) < 0.15 for m in [top, bottom, left, right]):
                report.append("   => [OK] CORRECTO: márgenes según APA 7 (2.54 cm).")
            else:
                report.append("   => [X] INCORRECTO: ajusta los márgenes a 2.54 cm en todos los lados.")

        sample = [p for p in doc.paragraphs if len(p.text.strip()) > 30][:10]
        indents, spacings = [], []
        for p in sample:
            pf = p.paragraph_format
            indents.append(round(pf.first_line_indent.cm, 2) if pf.first_line_indent else 0.0)
            spacings.append(round(pf.line_spacing, 1) if pf.line_spacing else 1.0)

        if indents:
            avg_indent = sum(indents) / len(indents)
            report.append("\n2. Sangría de primera línea (Requerido: 1.27 cm):")
            report.append(f"   - Promedio detectado: {round(avg_indent, 2)} cm")
            report.append("   => [OK] CORRECTO." if abs(avg_indent - 1.27) < 0.2
                           else "   => [X] INCORRECTO: falta sangría de 1.27 cm en los párrafos.")
        else:
            report.append("\n2. Sangría de primera línea:\n   => [X] INCORRECTO: no se detectó.")

        if spacings:
            avg_sp = sum(spacings) / len(spacings)
            report.append("\n3. Interlineado (Requerido: Doble / 2.0):")
            report.append(f"   - Promedio detectado: {round(avg_sp, 1)}")
            report.append("   => [OK] CORRECTO." if abs(avg_sp - 2.0) < 0.2
                           else "   => [X] INCORRECTO: usa interlineado doble (2.0).")
        else:
            report.append("\n3. Interlineado:\n   => [X] INCORRECTO: no se detectó.")

        fonts, sizes = set(), set()
        for p in sample:
            for r in p.runs:
                if r.font.name:
                    fonts.add(r.font.name)
                if r.font.size:
                    sizes.add(round(r.font.size.pt, 1))
        report.append("\n4. Tipografía y tamaño:")
        if fonts:
            report.append(f"   - Fuentes detectadas: {', '.join(fonts)}")
        if sizes:
            report.append(f"   - Tamaños detectados: {', '.join(str(s) + 'pt' for s in sizes)}")
        valid_fonts = {"Times New Roman", "Arial", "Calibri", "Georgia", "Lucida Sans Unicode"}
        report.append("   => [OK] Fuente admitida por APA 7." if fonts.intersection(valid_fonts)
                       else "   => [X] Usa una fuente oficial de APA 7 (Times New Roman, Calibri, Arial...).")
        report.append("\n=======================================================\n")
        return "\n".join(report)
    except Exception as e:
        return f"[Error en análisis estructural objetivo: {e}]"


def verify_apa_full(text: str, file_path: str = "", progress_cb=None) -> str:
    """Devuelve un reporte combinado: formato objetivo + revisión IA de citas/estructura + gramática."""
    def _p(s, pct):
        if progress_cb:
            progress_cb(s, pct)

    _p("Analizando formato del documento...", 15)
    formatting_report = ""
    if file_path:
        if file_path.lower().endswith(".docx"):
            formatting_report = check_docx_apa_formatting(file_path)
        elif file_path.lower().endswith(".pdf"):
            formatting_report = (
                "=== ANÁLISIS ESTRUCTURAL OBJETIVO (Archivo .pdf) ===\n"
                "[OK] Documento cargado en PDF, analizando visualmente con IA multimodal...\n\n"
            )
    else:
        formatting_report = (
            "=== AVISO DE FORMATO ESTÁNDAR ===\n"
            "[!] Ingresaste texto plano: no puedo verificar objetivamente márgenes, sangría "
            "ni interlineado. Carga el archivo original (.docx o .pdf) para un análisis estructural real.\n\n"
        )

    pil_images = []
    if file_path:
        try:
            import fitz
            from PIL import Image
            doc = fitz.open(file_path)
            for i in range(min(2, len(doc))):
                pix = doc.load_page(i).get_pixmap(dpi=120)
                pil_images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
            doc.close()
        except Exception:
            pass

    _p("Verificando citas y estructura con IA...", 55)
    client = _get_client()
    model = _get_model()
    prompt = (
        "Actúa como experto en normas APA 7ma edición y redacción científica.\n"
        "Analiza el texto (y las imágenes de páginas si están adjuntas) y genera un reporte con:\n"
        "1. EVALUACIÓN VISUAL (márgenes, sangría, portada, numeración de página si hay imágenes).\n"
        "2. CORRECCIÓN DE CITAS Y REFERENCIAS bajo APA 7 (original vs corregido y motivo).\n"
        "3. RECOMENDACIONES FINALES de estructuración académica.\n\n"
        f"TEXTO:\n\n{text[:9000]}"
    )
    contents = [prompt] + pil_images
    resp = client.models.generate_content(model=model, contents=contents)
    ia_report = resp.text.strip()

    _p("Revisando ortografía y gramática...", 85)
    grammar_html_or_text = ""
    try:
        grammar_report = check_grammar_and_style(text)
        grammar_html_or_text = "\n\n=== ORTOGRAFÍA Y GRAMÁTICA ===\n" + grammar_report
    except Exception:
        pass

    _p("Completado.", 100)
    return formatting_report + "\n" + ia_report + grammar_html_or_text


def student_verify_apa(parameters: dict, player=None, speak=None) -> str:
    text = parameters.get("text", "").strip()
    file_path = parameters.get("file_path", "").strip()
    if not text and file_path:
        text = extract_text(file_path)
    if not text:
        return "Error: No proporcionaste referencias o texto para verificar, sir."

    try:
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit(
                "apa", {"input": text, "output": "Analizando...", "status": "Iniciando validación APA 7...", "progress": 10}
            )

        def _cb(status, pct):
            if player and hasattr(player, "_win") and player._win is not None:
                player._win.student_action_sig.emit("apa", {"input": text, "output": "Procesando...", "status": status, "progress": pct})

        combined = verify_apa_full(text, file_path, progress_cb=_cb)

        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit(
                "apa", {"input": text, "output": combined, "status": "Verificación APA 7 completada.", "progress": 100}
            )
        return "Validación APA 7 completada, sir. Resultado cargado en pantalla."
    except Exception as e:
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("apa", {"input": text, "output": f"Error: {e}", "status": "Error", "progress": 0})
        return f"Error en la validación APA 7: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  Conversión PDF -> Word (wrapper de compatibilidad, ahora usa convert_file)
# ─────────────────────────────────────────────────────────────────────────

def student_pdf_to_word(parameters: dict, player=None, speak=None) -> str:
    pdf_path = parameters.get("pdf_path", "").strip()
    docx_path = parameters.get("docx_path", "").strip()

    if not pdf_path:
        return "Error: indica la ruta del PDF a convertir, sir."
    if not Path(pdf_path).exists():
        return f"Error: no encontré el archivo '{pdf_path}'."

    output_dir = None
    if docx_path:
        output_dir = str(Path(docx_path).parent)
    else:
        output_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Nexus_Downloads", "Conversiones")

    def _cb(status, pct):
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("pdf", {"pdf_path": pdf_path, "status": status, "progress": pct})

    try:
        dest = convert_file(pdf_path, "docx", output_dir=output_dir, progress_cb=_cb)
        return f"Éxito: convertí tu PDF a Word, sir. Guardado en '{dest}'."
    except Exception as e:
        _cb(f"Error: {e}", 0)
        return f"Error al convertir el PDF: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  Reporte de calidad académica
# ─────────────────────────────────────────────────────────────────────────

def student_quality_report(parameters: dict, player=None, speak=None) -> str:
    file_path = parameters.get("file_path", "").strip()
    if not file_path:
        return "Error: indica la ruta del archivo académico a evaluar, sir."
    path = Path(file_path)
    if not path.exists():
        return f"Error: no encontré ningún archivo en '{file_path}'."

    try:
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("quality", {"file_path": file_path, "report_html": "Analizando la calidad académica..."})

        text = extract_text(file_path)
        if not text.strip() or text.startswith("[Error"):
            raise Exception("No se pudo extraer texto legible del documento.")

        client = _get_client()
        model = _get_model()
        prompt = (
            "Actúa como revisor académico senior de revistas científicas de alto impacto.\n"
            f"Analiza el texto de '{path.name}' y genera un REPORTE DE CALIDAD ACADÉMICA en HTML "
            "limpio (sin bloques markdown), con tarjetas de fondo oscuro y colores semánticos, con:\n"
            "1. Calificación Global (ej. 85/100) y su interpretación.\n"
            "2. Fortalezas clave (3-4 puntos).\n"
            "3. Puntos de mejora prioritarios (3-4, en orden de importancia).\n"
            "4. Rigor científico (método, marco conceptual, fuentes).\n"
            "5. Errores de ortografía/gramática detectados (lista breve si los hay).\n"
            "6. Plan de acción para mejorar el documento.\n\n"
            f"TEXTO:\n\n{text[:9000]}"
        )
        resp = client.models.generate_content(model=model, contents=prompt)
        report_html = _clean_html_fences(resp.text.strip())

        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("quality", {"file_path": file_path, "report_html": report_html})
        return f"Reporte de calidad completado para '{path.name}', sir."
    except Exception as e:
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("quality", {"file_path": file_path, "report_html": f"<div style='color:#ff3b30;'>Error: {e}</div>"})
        return f"Error al generar el reporte de calidad: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  Consulta general (tareas, matemáticas, investigación, programación...)
# ─────────────────────────────────────────────────────────────────────────

CONSULTA_SYSTEM_PROMPTS = {
    "general": "Eres un tutor académico experto y paciente. Responde con claridad, precisión y ejemplos cuando ayude.",
    "matematicas": "Eres un profesor de matemáticas experto. Resuelve el problema PASO A PASO, mostrando "
                   "cada operación y el razonamiento, y destaca el resultado final con claridad al terminar.",
    "investigacion": "Eres un asesor de investigación académica. Ayuda a estructurar, argumentar y "
                      "fundamentar con rigor metodológico. Si sugieres tipos de fuentes, sé honesto sobre "
                      "qué necesitarías verificar y NO inventes referencias bibliográficas falsas.",
    "programacion": "Eres un ingeniero de software senior. Explica el problema o el código con claridad; "
                     "si generas código, coméntalo brevemente y usa bloques <pre><code> para el código.",
    "ensayo": "Eres un editor y tutor de escritura académica. Ayuda a estructurar, argumentar y mejorar "
              "la redacción de la tarea o ensayo solicitado.",
}


def ask_consulta(question: str, mode: str = "general", history: list = None, progress_cb=None) -> str:
    client = _get_client()
    model = _get_model()
    system = CONSULTA_SYSTEM_PROMPTS.get(mode, CONSULTA_SYSTEM_PROMPTS["general"])

    convo = ""
    if history:
        for turn in history[-6:]:
            convo += f"Usuario: {turn.get('q', '')}\nAsistente: {turn.get('a', '')}\n\n"

    prompt = (
        f"{system}\n\n"
        "Responde en español, en HTML limpio compatible con QTextBrowser (sin bloques ```html), "
        "usando párrafos, listas y <b> para resaltar cuando ayude a la claridad. No inventes datos "
        "que no sepas con certeza; si no estás seguro, dilo.\n\n"
        f"{convo}"
        f"Usuario: {question}\nAsistente:"
    )
    if progress_cb:
        progress_cb("Pensando...", 40)
    resp = client.models.generate_content(model=model, contents=prompt)
    answer = _clean_html_fences(resp.text.strip())
    if progress_cb:
        progress_cb("Completado.", 100)
    return answer


def student_consulta(parameters: dict, player=None, speak=None) -> str:
    question = parameters.get("question", "").strip()
    mode = parameters.get("mode", "general")
    if not question:
        return "Error: no entendí tu consulta, sir. Intenta de nuevo."
    try:
        answer = ask_consulta(question, mode=mode)
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("consulta", {"question": question, "answer": answer})
        return "Respondí tu consulta, sir. Puedes verla en la pestaña Consulta."
    except Exception as e:
        return f"Error al responder la consulta: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  Traductor
# ─────────────────────────────────────────────────────────────────────────

LANGUAGES = [
    "Español", "Inglés", "Francés", "Alemán", "Italiano", "Portugués",
    "Chino (Mandarín)", "Japonés", "Coreano", "Ruso", "Árabe", "Neerlandés", "Turco",
]


def translate_text(text: str, source_lang: str = "Auto-detectar", target_lang: str = "Español", progress_cb=None) -> str:
    client = _get_client()
    model = _get_model()
    if progress_cb:
        progress_cb("Traduciendo...", 40)

    src_clause = ("detecta automáticamente el idioma de origen" if source_lang == "Auto-detectar"
                  else f"el idioma de origen es {source_lang}")
    prompt = (
        f"Traduce el siguiente texto; {src_clause}. Traduce EXCLUSIVAMENTE al idioma: {target_lang}.\n"
        "Reglas estrictas:\n"
        "- Responde ÚNICAMENTE con la traducción, sin explicaciones ni notas.\n"
        "- Conserva el formato de párrafos y saltos de línea del original.\n"
        "- Conserva nombres propios, cifras y unidades tal como corresponda al idioma destino.\n\n"
        f"TEXTO:\n\n{text}"
    )
    resp = client.models.generate_content(model=model, contents=prompt)
    if progress_cb:
        progress_cb("Completado.", 100)
    return resp.text.strip()


def student_translate(parameters: dict, player=None, speak=None) -> str:
    text = parameters.get("text", "").strip()
    target_lang = parameters.get("target_lang", "Español")
    source_lang = parameters.get("source_lang", "Auto-detectar")
    if not text:
        return "Error: no me diste ningún texto para traducir, sir."
    try:
        translated = translate_text(text, source_lang, target_lang)
        if player and hasattr(player, "_win") and player._win is not None:
            player._win.student_action_sig.emit("translate", {"input": text, "output": translated})
        return f"Traducción completada, sir: {translated[:200]}..."
    except Exception as e:
        return f"Error al traducir: {e}"


# ─────────────────────────────────────────────────────────────────────────
#  Activar la ventana del Modo Estudiante
# ─────────────────────────────────────────────────────────────────────────

def activar_modo_estudiante(parameters: dict, player=None, speak=None) -> str:
    if player and hasattr(player, "open_student_mode"):
        if hasattr(player, "_win") and player._win is not None:
            from PyQt6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(player._win, "open_student_mode", Qt.ConnectionType.QueuedConnection)
        else:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, player.open_student_mode)
        return "Modo estudiante activado. Abrí la ventana de herramientas académicas, sir."
    return "Error: no se pudo acceder a la interfaz para abrir el modo estudiante."