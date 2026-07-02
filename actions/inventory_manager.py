# -*- coding: utf-8 -*-
"""
inventory_manager.py — Gestión Avanzada de Inventario para Empresas (V3)
Permite gestionar compras, ventas, historial, gastos y ganancias.
"""
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
INVENTORY_DIR = BASE_DIR / "config" / "inventories"

def _load_inventory(name: str) -> dict:
    file_path = INVENTORY_DIR / f"{name.lower()}.json"
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except:
            return {"products": {}, "history": [], "finances": {"revenue": 0, "expenses": 0}}
    return {"products": {}, "history": [], "finances": {"revenue": 0, "expenses": 0}}

def _save_inventory(name: str, data: dict):
    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    file_path = INVENTORY_DIR / f"{name.lower()}.json"
    file_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

def inventory_manager(parameters: dict, player=None) -> str:
    """
    Herramienta avanzada para gestión de inventarios locales de empresas.
    """
    action = parameters.get("action", "").lower()
    inv_name = parameters.get("inventory_name", "principal")
    product = parameters.get("product", "")
    quantity = parameters.get("quantity", 0)
    price = parameters.get("price", 0.0)
    cost = parameters.get("cost", 0.0) # Costo de adquisición
    
    data = _load_inventory(inv_name)
    products = data.setdefault("products", {})
    history = data.setdefault("history", [])
    finances = data.setdefault("finances", {"revenue": 0, "expenses": 0})
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if action == "add_stock":
        if not product: return "Error: Especifica un producto a agregar."
        if product in products:
            products[product]["quantity"] += quantity
            if price > 0: products[product]["price"] = price
            if cost > 0: products[product]["cost"] = cost
        else:
            products[product] = {"quantity": quantity, "price": price, "cost": cost}
        
        total_expense = quantity * (cost if cost > 0 else products[product].get("cost", 0))
        finances["expenses"] += total_expense
        history.append({"time": timestamp, "type": "RESTOCK", "product": product, "qty": quantity, "expense": total_expense})
        
        _save_inventory(inv_name, data)
        return f"Inventario '{inv_name}': Se compraron/agregaron {quantity} de '{product}'. Gasto registrado: ${total_expense:,.2f}"
        
    elif action == "sell_stock":
        if not product or product not in products:
            return f"Error: Producto '{product}' no encontrado."
        if products[product]["quantity"] < quantity:
            return f"Error: Stock insuficiente de '{product}'. Tienes {products[product]['quantity']}."
            
        products[product]["quantity"] -= quantity
        total_revenue = quantity * products[product]["price"]
        finances["revenue"] += total_revenue
        history.append({"time": timestamp, "type": "SALE", "product": product, "qty": quantity, "revenue": total_revenue})
        
        _save_inventory(inv_name, data)
        return f"Venta registrada: {quantity}x '{product}'. Ingreso: ${total_revenue:,.2f}. Stock restante: {products[product]['quantity']}."

    elif action == "delete_product":
        if product in products:
            del products[product]
            _save_inventory(inv_name, data)
            return f"Producto '{product}' eliminado permanentemente del inventario."
        return f"Producto '{product}' no encontrado."
        
    elif action == "query":
        if product:
            if product in products:
                p = products[product]
                return f"Stock de '{product}': {p['quantity']} unidades. (Precio Venta: ${p.get('price',0)}, Costo: ${p.get('cost',0)})"
            return f"El producto '{product}' no está registrado."
        else:
            if not products:
                return f"El inventario '{inv_name}' está vacío."
            res = f"--- Inventario '{inv_name}' ---\n"
            for k, v in products.items():
                alert = " [ALERTA: BAJO STOCK]" if v['quantity'] < 5 else ""
                res += f"• {k}: {v['quantity']} unidades (Venta: ${v.get('price',0)}){alert}\n"
            return res
            
    elif action == "report":
        rev = finances.get('revenue', 0)
        exp = finances.get('expenses', 0)
        profit = rev - exp
        inv_value = sum(v["quantity"] * v.get("price", 0) for v in products.values())
        
        report = (
            f"=== REPORTE FINANCIERO: '{inv_name}' ===\n"
            f"Ingresos Totales (Ventas): ${rev:,.2f}\n"
            f"Gastos Totales (Compras): ${exp:,.2f}\n"
            f"Ganancia Neta: ${profit:,.2f}\n"
            f"Valor actual del inventario almacenado: ${inv_value:,.2f}\n"
            f"Stock Bajo: {', '.join([k for k,v in products.items() if v['quantity'] < 5]) or 'Ninguno'}"
        )
        return report

    else:
        return f"Acción '{action}' no soportada. (add_stock, sell_stock, query, delete_product, report)"
