"""weather_report.py — Clean weather forecasting action."""
import urllib.request
import urllib.parse
import json

def weather_action(parameters: dict, player=None) -> str:
    """Fetch current weather report from wttr.in in clean text format."""
    city = parameters.get("city", "").strip()
    if not city:
        try:
            import json
            from pathlib import Path
            cfg_path = Path(__file__).parent.parent / "config" / "api_keys.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                tz = cfg.get("timezone", "America/Lima")
                tz_map = {
                    "America/Mexico_City": "Ciudad de Mexico",
                    "America/Bogota": "Bogota",
                    "America/Argentina/Buenos_Aires": "Buenos Aires",
                    "America/Santiago": "Santiago",
                    "America/Caracas": "Caracas",
                    "Europe/Madrid": "Madrid",
                    "America/New_York": "New York",
                    "America/Lima": "Lima"
                }
                city = tz_map.get(tz, "Lima")
            else:
                city = "Lima"
        except Exception:
            city = "Lima"
            
    if not city:
        city = "Lima"
        
    try:
        # Request text/json format from wttr.in
        encoded_city = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded_city}?format=%C+%t+%h+%w"
        
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "curl"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = response.read().decode("utf-8").strip()
            
        report = f"Current weather in {city}: {data}"
        if player:
            player.write_log(f"🌤️ {report}")
        return report
    except Exception as e:
        # Fallback response
        msg = f"Unable to fetch real-time weather details for {city}: {e}"
        if player:
            player.write_log(f"⚠️ {msg}")
        return f"Sir, I'm having trouble connecting to the weather service right now. However, I can search online if you wish."
