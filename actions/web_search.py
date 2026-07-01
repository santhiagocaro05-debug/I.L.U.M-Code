"""web_search.py - Advanced Real-Time Web Scraping for ILUM"""
import urllib.request
import urllib.parse
from html.parser import HTMLParser

class DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.in_result = False
        self.current_item = {}
        self.current_tag = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a" and "result__url" in attrs_dict.get("class", ""):
            self.in_result = True
            self.current_item = {"url": attrs_dict.get("href", ""), "title": "", "snippet": ""}
            self.current_tag = "a"
        elif self.in_result and tag == "a" and "result__snippet" in attrs_dict.get("class", ""):
            self.current_tag = "snippet"

    def handle_data(self, data):
        if self.in_result:
            text = data.strip()
            if not text: return
            if self.current_tag == "a":
                self.current_item["title"] += text + " "
            elif self.current_tag == "snippet":
                self.current_item["snippet"] += text + " "

    def handle_endtag(self, tag):
        if self.in_result:
            if tag == "a" and self.current_tag == "snippet":
                # Fin de un resultado
                if self.current_item["title"] or self.current_item["snippet"]:
                    self.results.append(self.current_item.copy())
                self.in_result = False
                self.current_item = {}
            self.current_tag = ""


def web_search(parameters: dict, player=None) -> str:
    """
    Busca información en la web en tiempo real usando DuckDuckGo Lite (HTML).
    """
    query = parameters.get("query", "")
    if not query:
        return "Error: No se proporcionó un término de búsqueda."

    if player:
        player.write_log(f"🌐 Buscando en la web profunda: '{query}'...")

    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
        }
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8")
            
        parser = DuckDuckGoParser()
        parser.feed(html)
        
        if not parser.results:
            return "No encontré resultados concretos, pero puedes intentar otra búsqueda."
            
        # Tomar los top 3 resultados
        top_results = parser.results[:3]
        
        output = f"RESULTADOS DE BÚSQUEDA WEB PARA '{query}':\n\n"
        for i, res in enumerate(top_results, 1):
            output += f"{i}. TÍTULO: {res.get('title', '').strip()}\n"
            output += f"   RESUMEN: {res.get('snippet', '').strip()}\n"
            output += f"   FUENTE: {res.get('url', '').strip()}\n\n"
            
        output += "INSTRUCCIÓN PARA ILUM: Lee estos resultados y formula una respuesta experta, verídica y natural en español al usuario. ¡Usa esta información para responder su pregunta original!"
        
        return output

    except Exception as e:
        return f"Error al intentar buscar en la web: {str(e)}"
