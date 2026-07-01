# -*- coding: utf-8 -*-
"""
inventory_manager.py — Gestión de Inventario para Empresas
Permite crear bases de datos locales para empresas, sumar/restar stock, y hacer cálculos de valor.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INVENTORY_DIR = BASE_DIR / "config" / "inventories"

def _load_inventory(name: str) -> dict:
    file_path = INVENTORY_DIR / f"{name.lower()}.json"
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def _save_inventory(name: str, data: dict):
    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    file_path = INVENTORY_DIR / f"{name.lower()}.json"
    file_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

def inventory_manager(parameters: dict, player=None) -> str:
    """
    Herramienta para gestión de inventarios locales de empresas.
    """
    action = parameters.get("action", "").lower()
    inv_name = parameters.get("inventory_name", "principal")
    product = parameters.get("product", "")
    quantity = parameters.get("quantity", 0)
    price = parameters.get("price", 0.0)
    
    inventory = _load_inventory(inv_name)
    
    if action == "add":
        if not product:
            return "Error: Especifica un producto a agregar."
        if product in inventory:
            inventory[product]["quantity"] += quantity
            if price > 0:
                inventory[product]["price"] = price # Update price if provided
        else:
            inventory[product] = {"quantity": quantity, "price": price}
        _save_inventory(inv_name, inventory)
        return f"Inventario '{inv_name}': Se agregaron {quantity} unidades de '{product}'."
        
    elif action == "remove":
        if not product or product not in inventory:
            return f"Error: Producto '{product}' no encontrado en el inventario '{inv_name}'."
        inventory[product]["quantity"] -= quantity
        if inventory[product]["quantity"] < 0:
            inventory[product]["quantity"] = 0
        _save_inventory(inv_name, inventory)
        return f"Inventario '{inv_name}': Se restaron {quantity} unidades de '{product}'. Stock actual: {inventory[product]['quantity']}."

    elif action == "delete_product":
        if product in inventory:
            del inventory[product]
            _save_inventory(inv_name, inventory)
            return f"Producto '{product}' eliminado del inventario '{inv_name}'."
        return f"Producto '{product}' no encontrado."
        
    elif action == "query":
        if product:
            if product in inventory:
                data = inventory[product]
                return f"Stock de '{product}': {data['quantity']} unidades. (Precio: ${data['price']})"
            return f"El producto '{product}' no está en el inventario '{inv_name}'."
        else:
            if not inventory:
                return f"El inventario '{inv_name}' está vacío."
            res = f"--- Inventario '{inv_name}' ---\n"
            for k, v in inventory.items():
                res += f"• {k}: {v['quantity']} unidades (${v['price']} c/u)\n"
            return res
            
    elif action == "calculate_value":
        total_value = sum(v["quantity"] * v["price"] for v in inventory.values())
        return f"El valor total calculado del inventario '{inv_name}' es de ${total_value:,.2f}."

    else:
        return f"Acción de inventario '{action}' no soportada. (Usa add, remove, query, delete_product, calculate_value)"
