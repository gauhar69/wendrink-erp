"""
WENDRINK ERP - Z-REPORT SHIFT 72
Date: 17.01.2026
"""

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from decimal import Decimal

# SHIFT 72 - 17.01.2026
SALES_DATA = [
    (12, 1, 150),      # Доп. Тапиока
    (31, 6, 1800),     # Рожок Микс
    (78, 1, 650),      # Сандэ Про Макс
    (80, 1, 900),      # Орео молочный чай (L)
    (81, 11, 7150),    # Сандэ Орео
    (82, 1, 900),      # Шоколад-кокос
    (86, 1, 700),      # Классический американо
    (106, 4, 3000),    # Двойная маракуйя
    (107, 5, 3000),    # Чёрный с лимоном
    (108, 3, 1200),    # Лимонад
    (109, 1, 600),     # Маракуйя чай
    (112, 5, 4000),    # Малина-Апельсин
    (130, 5, 3250),    # Шоколадный сандэ
    (202, 4, 2400),    # Латте
    (301, 1, 650),     # Боба милкшейк
    (305, 2, 1300),    # Клубничный сандэ
    (306, 2, 1300),    # Клубничный шейк
    (308, 3, 900),     # Рожок сливочный
    (310, 1, 800),     # Манго снежный десерт
    (312, 1, 650),     # Персиковый сандэ
    (314, 4, 2600),    # Орео снежный десерт
    (401, 5, 4500),    # Тапиока чай (L)
    (402, 2, 1400),    # Тапиока чай (M)
    (403, 4, 3600),    # Двойной мол. чай (L)
    (404, 1, 800),     # Классический мол. чай
    (407, 1, 800),     # Двойной мол. чай (M)
]

BUSINESS_DATE = "2026-01-17"
SHIFT_NUMBER = 72


def main():
    conn = sqlite3.connect('wendrink.db')
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    
    print("=" * 70)
    print(f"WENDRINK ERP - Z-REPORT SHIFT {SHIFT_NUMBER}")
    print(f"Date: {BUSINESS_DATE}")
    print("=" * 70)
    
    # Clear previous sales data
    print("\n[1/3] Clearing previous sales data...")
    cursor.execute("DELETE FROM sale_items")
    cursor.execute("DELETE FROM sales")
    # Also clear SALE entries from inventory_ledger
    cursor.execute("DELETE FROM inventory_ledger WHERE event_type = 'SALE'")
    conn.commit()
    print("    Done!")
    
    # Load products and recipes
    cursor.execute("SELECT id, pos_code, name, price FROM products")
    products = {row[1]: {"id": row[0], "name": row[2], "price": row[3]} for row in cursor.fetchall()}
    
    cursor.execute("""
        SELECT r.product_id, r.ingredient_id, r.quantity, i.name
        FROM recipes r
        JOIN ingredients i ON i.id = r.ingredient_id
    """)
    recipes = {}
    for row in cursor.fetchall():
        prod_id, ing_id, qty, ing_name = row
        if prod_id not in recipes:
            recipes[prod_id] = []
        recipes[prod_id].append({"ingredient_id": ing_id, "quantity": qty, "name": ing_name})
    
    # Load WAC
    cursor.execute("""
        SELECT ingredient_id, weighted_average_cost
        FROM inventory_ledger
        WHERE event_type = 'INITIAL_BALANCE'
    """)
    wac_map = {row[0]: row[1] for row in cursor.fetchall()}
    
    print(f"\n[2/3] Processing {len(SALES_DATA)} sale items...")
    
    # Create sale
    sale_id = str(uuid4())
    total_revenue = Decimal("0")
    total_cogs = Decimal("0")
    sales_count = 0
    ingredient_usage = {}
    not_found = []
    
    print("\n" + "-" * 70)
    print(f"{'CODE':>4} | {'PRODUCT':<28} | {'QTY':>3} | {'AMOUNT':>8} | {'COGS':>8}")
    print("-" * 70)
    
    for pos_code, qty, amount in SALES_DATA:
        product = products.get(pos_code)
        if not product:
            not_found.append(pos_code)
            continue
        
        prod_id = product["id"]
        prod_name = product["name"]
        line_total = Decimal(str(amount))
        
        total_revenue += line_total
        sales_count += qty
        
        # Create sale_item
        item_id = str(uuid4())
        unit_price = line_total / qty if qty > 0 else line_total
        
        cursor.execute("""
            INSERT INTO sale_items (id, sale_id, product_id, quantity, unit_price, line_total, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_id, sale_id, prod_id, qty, float(unit_price), float(line_total), now))
        
        # Calculate COGS
        recipe = recipes.get(prod_id, [])
        item_cogs = Decimal("0")
        
        for item in recipe:
            ing_id = item["ingredient_id"]
            ing_qty = Decimal(str(item["quantity"])) * qty
            ing_name = item["name"]
            wac = Decimal(str(wac_map.get(ing_id, 0)))
            
            item_cost = ing_qty * wac
            item_cogs += item_cost
            
            if ing_id not in ingredient_usage:
                ingredient_usage[ing_id] = {"name": ing_name, "qty": Decimal("0"), "cost": Decimal("0")}
            ingredient_usage[ing_id]["qty"] += ing_qty
            ingredient_usage[ing_id]["cost"] += item_cost
            
            # Deduct from inventory
            ledger_id = str(uuid4())
            cursor.execute("""
                INSERT INTO inventory_ledger 
                (id, ingredient_id, event_type, event_id, change_amount, unit_cost, 
                 weighted_average_cost, cost_snapshot, negative_stock, business_date, created_at)
                VALUES (?, ?, 'SALE', ?, ?, ?, ?, ?, 0, ?, ?)
            """, (ledger_id, ing_id, sale_id, -float(ing_qty), float(wac), float(wac), float(item_cost), BUSINESS_DATE, now))
        
        total_cogs += item_cogs
        
        print(f"{pos_code:>4} | {prod_name[:28]:<28} | x{qty:>2} | {amount:>7,} T | {item_cogs:>7,.0f} T")
    
    # Create sale record
    cursor.execute("""
        INSERT INTO sales (id, total_amount, total_cost, business_date, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (sale_id, float(total_revenue), float(total_cogs), BUSINESS_DATE, now))
    
    conn.commit()
    
    if not_found:
        print(f"\n[!] Products not found: {not_found}")
    
    # Calculate totals
    expected_total = sum(s[2] for s in SALES_DATA)
    
    # P&L REPORT
    print("\n" + "=" * 70)
    print("P&L REPORT - SHIFT 72")
    print("=" * 70)
    
    gross_profit = total_revenue - total_cogs
    gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    print(f"""
    REVENUE:               {total_revenue:>12,.0f} T
    COGS:                  {total_cogs:>12,.0f} T
    -----------------------------------------
    GROSS PROFIT:          {gross_profit:>12,.0f} T
    GROSS MARGIN:          {gross_margin:>11.1f} %
    
    Items Sold:            {sales_count:>12} pcs
    Check Total:           {expected_total:>12,} T
    """)
    
    # TOP INGREDIENTS BY COST
    print("=" * 70)
    print("TOP 15 INGREDIENTS BY COST")
    print("=" * 70)
    
    sorted_usage = sorted(ingredient_usage.items(), key=lambda x: x[1]["cost"], reverse=True)[:15]
    
    print(f"{'INGREDIENT':<40} {'USAGE':>10} {'COST':>10}")
    print("-" * 70)
    for ing_id, data in sorted_usage:
        print(f"{data['name'][:40]:<40} {data['qty']:>10.1f} {data['cost']:>9,.0f} T")
    
    # INVENTORY (LOW STOCK WARNING)
    print("\n" + "=" * 70)
    print("INVENTORY - LOW STOCK ALERTS")
    print("=" * 70)
    
    cursor.execute("""
        SELECT i.name, SUM(il.change_amount) as balance
        FROM inventory_ledger il
        JOIN ingredients i ON i.id = il.ingredient_id
        GROUP BY il.ingredient_id
        HAVING balance < 1000
        ORDER BY balance ASC
    """)
    
    print(f"{'INGREDIENT':<40} {'BALANCE':>12} {'STATUS':>10}")
    print("-" * 70)
    for row in cursor.fetchall():
        name, balance = row
        status = "CRITICAL!" if balance < 100 else "LOW" if balance < 500 else "WATCH"
        print(f"{name[:40]:<40} {balance:>12,.1f} {status:>10}")
    
    # Final inventory value
    cursor.execute("SELECT SUM(change_amount * weighted_average_cost) FROM inventory_ledger")
    inventory_value = cursor.fetchone()[0] or 0
    
    print(f"\n{'='*70}")
    print(f"TOTAL INVENTORY VALUE: {inventory_value:>,.0f} T")
    print(f"{'='*70}")
    
    conn.close()
    
    print(f"\nSHIFT {SHIFT_NUMBER} PROCESSED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
