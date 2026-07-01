"""rules_engine.py — Clean phrase-based automation and rules subsystem."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = BASE_DIR / "config" / "rules.json"

def rules_engine(parameters: dict, player=None) -> str:
    """Process dynamic rules settings."""
    action = parameters.get("action", "").lower()
    if action == "list":
        rules = _load_rules()
        return f"Currently registered rules: {json.dumps(rules)}"
    elif action == "create":
        rules = _load_rules()
        import uuid
        rule_id = parameters.get("rule_id", str(uuid.uuid4())[:8])
        new_rule = {
            "id": rule_id,
            "name": parameters.get("name", "Unnamed Rule"),
            "condition": parameters.get("condition", {}),
            "action": parameters.get("action_def", {})
        }
        # If it's a phrase rule without a phrase key but has a trigger, map it
        if new_rule["condition"].get("type") == "phrase" and "trigger" in new_rule["condition"]:
            new_rule["phrase"] = new_rule["condition"]["trigger"]
            
        rules.append(new_rule)
        _save_rules(rules)
        if player: player.write_log(f"⚙️ Automatización creada: {new_rule['name']}")
        return f"Rule created successfully with ID: {rule_id}"
    elif action == "delete":
        rules = _load_rules()
        rule_id = parameters.get("rule_id", "")
        name_query = parameters.get("name", "").lower()
        original_count = len(rules)
        
        if rule_id:
            rules = [r for r in rules if r.get("id") != rule_id]
        elif name_query:
            rules = [r for r in rules if name_query not in r.get("name", "").lower()]
            
        if len(rules) < original_count:
            _save_rules(rules)
            if player: player.write_log(f"⚙️ Automatización eliminada.")
            return "Rule(s) deleted successfully."
        return "No matching rule found to delete."
        
    return "Rules engine action processed."

def _save_rules(rules: list[dict]) -> None:
    try:
        RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        RULES_PATH.write_text(json.dumps({"rules": rules}, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[RulesEngine] Error saving rules: {e}")

def start_rules_runner(player=None, speak=None) -> None:
    """Start background rules listener thread (optional stub)."""
    pass

def _load_rules() -> list[dict]:
    if not RULES_PATH.exists():
        return []
    try:
        data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("rules", [])
        return data if isinstance(data, list) else []
    except Exception:
        return []

def check_phrase_triggers(text: str) -> list[dict]:
    """Check text input against phrase triggers and return matching rule definitions."""
    rules = _load_rules()
    triggered = []
    text_lower = text.lower().strip()
    
    for rule in rules:
        trigger = rule.get("phrase", "").lower().strip()
        if trigger and trigger in text_lower:
            triggered.append(rule)
            
    return triggered

def _run_action(action: dict) -> None:
    """Execute action block of a matching rule in background."""
    print(f"[RulesEngine] Executing rule action: {action}")
