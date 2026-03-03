"""
WENDRINK ERP - Full P&L Report
Shows: Revenue, COGS, OPEX, Net Profit
"""
import sqlite3
from decimal import Decimal
import sys

def get_daily_pnl(business_date: str):
    conn = sqlite3.connect('wendrink.db')
    c = conn.cursor()
    
    print("=" * 70)
    print(f"P&L REPORT - {business_date}")
    print("=" * 70)
    
    # 1. REVENUE
    c.execute("""
        SELECT COALESCE(SUM(total_amount), 0) 
        FROM sales 
        WHERE business_date = ?
    """, (business_date,))
    revenue = Decimal(str(c.fetchone()[0]))
    
    # 2. COGS
    c.execute("""
        SELECT COALESCE(SUM(cost_snapshot), 0) 
        FROM inventory_ledger 
        WHERE event_type = 'SALE' AND business_date = ?
    """, (business_date,))
    cogs = Decimal(str(c.fetchone()[0]))
    
    # 3. OPEX by category
    c.execute("""
        SELECT category, SUM(amount) 
        FROM finance_ledger 
        WHERE business_date = ?
        GROUP BY category
        ORDER BY SUM(amount) DESC
    """, (business_date,))
    opex_items = c.fetchall()
    total_opex = sum(Decimal(str(row[1])) for row in opex_items)
    
    # Separate PAYROLL from other OPEX
    payroll = Decimal("0")
    other_opex = Decimal("0")
    for cat, amt in opex_items:
        if cat == "PAYROLL":
            payroll = Decimal(str(amt))
        else:
            other_opex += Decimal(str(amt))
    
    # Calculations
    gross_profit = revenue - cogs
    gross_margin = (gross_profit / revenue * 100) if revenue > 0 else Decimal("0")
    
    operating_profit = gross_profit - total_opex
    operating_margin = (operating_profit / revenue * 100) if revenue > 0 else Decimal("0")
    
    # Print report
    print(f"""
    REVENUE:                      {revenue:>12,.0f} T   (100.0%)
    
    COGS (Cost of Goods Sold):    {cogs:>12,.0f} T   ({cogs/revenue*100 if revenue else 0:>5.1f}%)
    ----------------------------------------------------------
    GROSS PROFIT:                 {gross_profit:>12,.0f} T   ({gross_margin:>5.1f}%)
    """)
    
    print("    OPERATING EXPENSES:")
    for cat, amt in opex_items:
        pct = Decimal(str(amt)) / revenue * 100 if revenue > 0 else 0
        print(f"      {cat:20}:     {amt:>10,.0f} T   ({pct:>5.1f}%)")
    print(f"      {'-' * 50}")
    print(f"      TOTAL OPEX:               {total_opex:>10,.0f} T   ({total_opex/revenue*100 if revenue else 0:>5.1f}%)")
    
    print(f"""
    ----------------------------------------------------------
    OPERATING PROFIT:             {operating_profit:>12,.0f} T   ({operating_margin:>5.1f}%)
    ==========================================================
    """)
    
    # Summary
    if operating_profit > 0:
        print(f"    [OK] PROFITABLE DAY!")
    else:
        print(f"    [!] LOSS DAY - need {abs(operating_profit):,.0f} T more revenue to break even")
    
    conn.close()
    
    return {
        "date": business_date,
        "revenue": float(revenue),
        "cogs": float(cogs),
        "gross_profit": float(gross_profit),
        "gross_margin": float(gross_margin),
        "opex": float(total_opex),
        "payroll": float(payroll),
        "other_opex": float(other_opex),
        "operating_profit": float(operating_profit),
        "operating_margin": float(operating_margin),
    }


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-01-06"
    get_daily_pnl(date)
