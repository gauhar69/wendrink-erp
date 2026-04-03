"""
WENDRINK ERP - Inventory Service

Handles all inventory operations with Weighted Average Cost (WAC) calculation.

LAWS ENFORCED:
- Law 1: Ledger-First (stock = SUM of ledger)
- Law 2: Decimal Only (no floats)
- Law 5: Negative Stock Allowed (flagged, not blocked)
- Law 6: Corrections are Inserts (never UPDATE)
- Law 7: Atomic Transactions (SERIALIZABLE)
- Law 8: Weighted Average Cost
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredient import Ingredient
from app.models.inventory_ledger import InventoryEventType, InventoryLedger
from app.utils.timezone import get_business_date


class InventoryService:
    """
    Service for inventory operations.
    
    All operations use Decimal for financial accuracy.
    All writes use SERIALIZABLE transactions.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =========================================================================
    # STOCK BALANCE QUERIES (Law 1: Ledger-First)
    # =========================================================================
    
    async def get_stock_balance(self, ingredient_id: UUID) -> Decimal:
        """
        Get current stock balance for an ingredient.
        
        Stock = SUM(change_amount) from inventory_ledger
        
        Returns:
            Current stock balance (can be negative!)
        """
        result = await self.session.execute(
            select(func.coalesce(func.sum(InventoryLedger.change_amount), Decimal("0")))
            .where(InventoryLedger.ingredient_id == ingredient_id)
        )
        balance = result.scalar()
        return Decimal(str(balance)) if balance is not None else Decimal("0")
    
    async def get_current_wac(self, ingredient_id: UUID) -> Decimal | None:
        """
        Get current Weighted Average Cost for an ingredient.
        
        WAC is taken from the most recent ledger entry.
        
        Returns:
            Current WAC or None if no history exists.
        """
        result = await self.session.execute(
            select(InventoryLedger.weighted_average_cost)
            .where(InventoryLedger.ingredient_id == ingredient_id)
            .order_by(InventoryLedger.business_date.desc(), InventoryLedger.created_at.desc())
            .limit(1)
        )
        wac = result.scalar()
        return Decimal(str(wac)) if wac is not None else None
    
    async def get_all_balances(self) -> list[dict]:
        """
        Get stock balance and WAC for all ingredients.
        
        Returns:
            List of {ingredient_id, name, unit, balance, wac, value}
        """
        # Get all ingredients
        ingredients_result = await self.session.execute(
            select(Ingredient)
        )
        ingredients = ingredients_result.scalars().all()
        
        balances = []
        for ingredient in ingredients:
            balance = await self.get_stock_balance(ingredient.id)
            wac = await self.get_current_wac(ingredient.id) or Decimal("0")
            
            balances.append({
                "ingredient_id": ingredient.id,
                "name": ingredient.name,
                "unit": ingredient.unit,
                "balance": balance,
                "weighted_average_cost": wac,
                "total_value": balance * wac if balance > 0 else Decimal("0"),
                "position_number": ingredient.position_number,
            })
        
        return balances

    async def get_all_balances_at_date(self, target_date: date) -> list[dict]:
        """
        Get stock balance for all ingredients AS OF a specific date.

        Balance = SUM(change_amount) WHERE business_date <= target_date
        WAC = weighted_average_cost from the latest entry up to target_date

        This is the correct way to show historical balances.
        """
        ingredients_result = await self.session.execute(
            select(Ingredient)
        )
        ingredients = ingredients_result.scalars().all()

        balances = []
        for ingredient in ingredients:
            # Balance at date = SUM of all changes up to and including target_date
            result = await self.session.execute(
                select(func.coalesce(func.sum(InventoryLedger.change_amount), Decimal("0")))
                .where(
                    InventoryLedger.ingredient_id == ingredient.id,
                    InventoryLedger.business_date <= target_date,
                )
            )
            balance = Decimal(str(result.scalar() or 0))

            # WAC from the latest entry up to target_date
            wac_result = await self.session.execute(
                select(InventoryLedger.weighted_average_cost)
                .where(
                    InventoryLedger.ingredient_id == ingredient.id,
                    InventoryLedger.business_date <= target_date,
                )
                .order_by(InventoryLedger.business_date.desc(), InventoryLedger.created_at.desc())
                .limit(1)
            )
            wac = wac_result.scalar()
            wac = Decimal(str(wac)) if wac is not None else Decimal("0")

            balances.append({
                "ingredient_id": ingredient.id,
                "name": ingredient.name,
                "unit": ingredient.unit,
                "balance": balance,
                "weighted_average_cost": wac,
                "total_value": balance * wac if balance > 0 else Decimal("0"),
                "position_number": ingredient.position_number,
            })

        return balances

    # =========================================================================
    # SUPPLY OPERATIONS (Law 8: WAC Calculation)
    # =========================================================================
    
    async def record_supply(
        self,
        ingredient_id: UUID,
        quantity: Decimal,
        total_cost: Decimal,
        business_date: date | None = None,
    ) -> InventoryLedger:
        """
        Record a supply event and calculate new WAC.
        
        WAC Formula:
            new_wac = (old_stock * old_wac + new_qty * new_unit_cost) / (old_stock + new_qty)
        
        Args:
            ingredient_id: ID of the ingredient
            quantity: Quantity received (positive)
            total_cost: Total invoice cost
            business_date: Business date (defaults to today)
            
        Returns:
            Created inventory ledger entry
            
        Raises:
            ValueError: If quantity or cost is not positive
        """
        # Validate inputs
        if quantity <= Decimal("0"):
            raise ValueError("Supply quantity must be positive")
        if total_cost < Decimal("0"):
            raise ValueError("Supply cost cannot be negative")
        
        # Calculate unit cost
        unit_cost = total_cost / quantity
        
        # Determine business date
        if business_date is None:
            business_date = get_business_date()
        
        # Get current stock and WAC
        current_stock = await self.get_stock_balance(ingredient_id)
        current_wac = await self.get_current_wac(ingredient_id)
        
        # Calculate new WAC
        new_wac = self._calculate_new_wac(
            old_stock=current_stock,
            old_wac=current_wac or Decimal("0"),
            new_qty=quantity,
            new_unit_cost=unit_cost,
        )
        
        # Create ledger entry
        entry = InventoryLedger(
            ingredient_id=ingredient_id,
            event_type=InventoryEventType.SUPPLY.value,
            change_amount=quantity,  # Positive for supply
            unit_cost=unit_cost,
            weighted_average_cost=new_wac,
            cost_snapshot=total_cost,  # Total value added
            negative_stock=False,
            business_date=business_date,
        )
        
        self.session.add(entry)
        await self.session.flush()

        # Автоматически обновляем current_price ингредиента
        # чтобы Заявка и Цены сырья всегда показывали последнюю цену поставки
        from app.models.ingredient import Ingredient
        ing_result = await self.session.execute(
            select(Ingredient).where(Ingredient.id == ingredient_id)
        )
        ingredient = ing_result.scalar_one_or_none()
        if ingredient:
            ingredient.current_price = unit_cost

        return entry

    def _calculate_new_wac(
        self,
        old_stock: Decimal,
        old_wac: Decimal,
        new_qty: Decimal,
        new_unit_cost: Decimal,
    ) -> Decimal:
        """
        Calculate new Weighted Average Cost after supply.
        
        Formula:
            new_wac = (old_stock * old_wac + new_qty * new_unit_cost) / total_qty
            
        Edge Cases:
            - First supply (old_stock = 0): new_wac = new_unit_cost
            - Negative stock: use absolute value for old portion
        """
        # Handle first supply or zero stock
        if old_stock <= Decimal("0"):
            return new_unit_cost
        
        # Standard WAC calculation
        old_value = old_stock * old_wac
        new_value = new_qty * new_unit_cost
        total_qty = old_stock + new_qty
        
        if total_qty <= Decimal("0"):
            # Edge case: shouldn't happen in normal flow
            return new_unit_cost
        
        new_wac = (old_value + new_value) / total_qty
        return new_wac
    
    # =========================================================================
    # SALE DEDUCTIONS (Law 5: Negative Stock Allowed)
    # =========================================================================
    
    async def deduct_for_sale(
        self,
        ingredient_id: UUID,
        quantity: Decimal,
        business_date: date,
        sale_id: UUID | None = None,
    ) -> InventoryLedger:
        """
        Deduct inventory for a sale.
        
        Uses current WAC for cost_snapshot.
        Allows negative stock (flagged).
        
        Args:
            ingredient_id: ID of the ingredient
            quantity: Quantity to deduct (positive value)
            business_date: Business date of the sale
            sale_id: ID of the sale (optional, for linking)
            
        Returns:
            Created inventory ledger entry
        """
        if quantity <= Decimal("0"):
            raise ValueError("Deduction quantity must be positive")
        
        # Get current state
        current_stock = await self.get_stock_balance(ingredient_id)
        current_wac = await self.get_current_wac(ingredient_id) or Decimal("0")
        
        # Calculate new balance
        new_balance = current_stock - quantity
        is_negative = new_balance < Decimal("0")
        
        # Calculate cost snapshot (IMMUTABLE after this point)
        cost_snapshot = quantity * current_wac
        
        # Create ledger entry
        entry = InventoryLedger(
            ingredient_id=ingredient_id,
            event_type=InventoryEventType.SALE.value,
            event_id=sale_id,
            change_amount=-quantity,  # Negative for deduction
            unit_cost=None,
            weighted_average_cost=current_wac,
            cost_snapshot=cost_snapshot,
            negative_stock=is_negative,  # Law 5: Flag but don't block
            business_date=business_date,
        )
        
        self.session.add(entry)
        await self.session.flush()
        
        return entry
    
    # =========================================================================
    # ADJUSTMENTS (Stocktake, Spoilage)
    # =========================================================================
    
    async def record_adjustment(
        self,
        ingredient_id: UUID,
        quantity_change: Decimal,
        reason: str,
        business_date: date | None = None,
    ) -> InventoryLedger:
        """
        Record a manual stock adjustment.
        
        Used for stocktake corrections, spoilage, etc.
        
        Args:
            ingredient_id: ID of the ingredient
            quantity_change: Change amount (+/-)
            reason: Explanation for the adjustment
            business_date: Business date (defaults to today)
            
        Returns:
            Created inventory ledger entry
        """
        if not reason or len(reason.strip()) == 0:
            raise ValueError("Adjustment reason is required")
        
        if business_date is None:
            business_date = get_business_date()
        
        current_stock = await self.get_stock_balance(ingredient_id)
        current_wac = await self.get_current_wac(ingredient_id) or Decimal("0")
        
        new_balance = current_stock + quantity_change
        is_negative = new_balance < Decimal("0")
        
        entry = InventoryLedger(
            ingredient_id=ingredient_id,
            event_type=InventoryEventType.ADJUSTMENT.value,
            change_amount=quantity_change,
            unit_cost=None,
            weighted_average_cost=current_wac,
            cost_snapshot=abs(quantity_change) * current_wac,
            negative_stock=is_negative,
            reason=reason,
            business_date=business_date,
        )
        
        self.session.add(entry)
        await self.session.flush()
        
        return entry
    
    async def record_waste(
        self,
        ingredient_id: UUID,
        quantity: Decimal,
        reason: str,
        business_date: date | None = None,
    ) -> InventoryLedger:
        """
        Record waste/spoilage.
        
        Args:
            ingredient_id: ID of the ingredient
            quantity: Quantity wasted (positive value)
            reason: Explanation (e.g., 'spoilage', 'tasting')
            business_date: Business date (defaults to today)
        """
        if not reason or len(reason.strip()) == 0:
            raise ValueError("Waste reason is required")
        
        if quantity <= Decimal("0"):
            raise ValueError("Waste quantity must be positive")
            
        if business_date is None:
            business_date = get_business_date()
        
        current_stock = await self.get_stock_balance(ingredient_id)
        current_wac = await self.get_current_wac(ingredient_id) or Decimal("0")
        
        new_balance = current_stock - quantity
        is_negative = new_balance < Decimal("0")
        
        entry = InventoryLedger(
            ingredient_id=ingredient_id,
            event_type=InventoryEventType.WASTE.value,
            change_amount=-quantity,
            unit_cost=None,
            weighted_average_cost=current_wac,
            cost_snapshot=quantity * current_wac,
            negative_stock=is_negative,
            reason=reason,
            business_date=business_date,
        )
        
        self.session.add(entry)
        await self.session.flush()
        
        return entry

    # =========================================================================
    # CORRECTIONS (Law 6: Corrections are Inserts)
    # =========================================================================
    
    async def record_correction(
        self,
        original_entry_id: UUID,
        correction_amount: Decimal,
        reason: str,
    ) -> InventoryLedger:
        """
        Record a correction for an erroneous entry.
        
        NEVER updates the original entry.
        Creates a compensating entry with:
        - event_type = CORRECTION
        - event_id = reference to original
        - business_date = SAME as original (Law 6)
        - weighted_average_cost = SAME as original
        
        Args:
            original_entry_id: ID of the entry being corrected
            correction_amount: Compensating amount (+/-)
            reason: Explanation for the correction
            
        Returns:
            Created correction entry
            
        Raises:
            ValueError: If original entry not found
        """
        if not reason or len(reason.strip()) == 0:
            raise ValueError("Correction reason is required")
        
        # Get original entry
        result = await self.session.execute(
            select(InventoryLedger).where(InventoryLedger.id == original_entry_id)
        )
        original = result.scalar_one_or_none()
        
        if original is None:
            raise ValueError(f"Original entry {original_entry_id} not found")
        
        # Get current stock to check if correction causes negative
        current_stock = await self.get_stock_balance(original.ingredient_id)
        new_balance = current_stock + correction_amount
        is_negative = new_balance < Decimal("0")
        
        # Create correction entry - PRESERVES original business_date!
        entry = InventoryLedger(
            ingredient_id=original.ingredient_id,
            event_type=InventoryEventType.CORRECTION.value,
            event_id=original.id,  # Reference to original
            change_amount=correction_amount,
            unit_cost=None,
            weighted_average_cost=original.weighted_average_cost,  # Use original WAC
            cost_snapshot=abs(correction_amount) * original.weighted_average_cost,
            negative_stock=is_negative,
            reason=reason,
            business_date=original.business_date,  # SAME date as original!
        )
        
        self.session.add(entry)
        await self.session.flush()
        
        return entry
    
    # =========================================================================
    # LEDGER QUERIES
    # =========================================================================
    
    async def get_ledger_entries(
        self,
        ingredient_id: UUID | None = None,
        event_type: str | None = None,
        business_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryLedger]:
        """
        Get inventory ledger entries with optional filters.
        
        Args:
            ingredient_id: Filter by ingredient
            event_type: Filter by event type
            business_date: Filter by business date
            limit: Maximum entries to return
            offset: Pagination offset
            
        Returns:
            List of ledger entries
        """
        query = select(InventoryLedger)
        
        if ingredient_id:
            query = query.where(InventoryLedger.ingredient_id == ingredient_id)
        if event_type:
            query = query.where(InventoryLedger.event_type == event_type)
        if business_date:
            query = query.where(InventoryLedger.business_date == business_date)
        
        query = query.order_by(InventoryLedger.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_daily_cogs(self, business_date: date) -> Decimal:
        """
        Calculate total COGS for a business date.
        
        COGS = SUM(cost_snapshot) for SALE events on the date.
        """
        result = await self.session.execute(
            select(func.coalesce(func.sum(InventoryLedger.cost_snapshot), Decimal("0")))
            .where(InventoryLedger.event_type == InventoryEventType.SALE.value)
            .where(InventoryLedger.business_date == business_date)
        )
        cogs = result.scalar()
        return Decimal(str(cogs)) if cogs is not None else Decimal("0")

    # =========================================================================
    # BULK SUPPLY (Invoice Import)
    # =========================================================================

    async def create_bulk_supply(
        self,
        items: list[dict],
        business_date: date,
        total_expected: Decimal,
        supplier_note: str | None = None,
    ) -> dict:
        """
        Process a bulk supply invoice with multiple items.
        
        LAWS ENFORCED:
        - Law 7: SERIALIZABLE transaction (all-or-nothing)
        - Law 8: WAC recalculation for each item
        - Law 2: Decimal precision throughout
        
        Args:
            items: List of supply items, each with:
                - ingredient_id OR ingredient_name (for lookup)
                - quantity_packs: Number of packages
                - price_per_pack: Price per package
            business_date: Invoice date
            total_expected: Expected total for verification
            supplier_note: Optional invoice notes
            
        Returns:
            Dict with status, items processed, ledger IDs
            
        Raises:
            ValueError: If validation fails (ingredient not found, total mismatch)
        """
        from decimal import ROUND_HALF_UP
        from sqlalchemy import text
        
        # Default package size (1 = base units, e.g., grams)
        # In future, this comes from ingredient.package_size
        DEFAULT_PACKAGE_SIZE = Decimal("1")
        
        # Phase 1: Validate all ingredients exist BEFORE any writes
        validated_items = []
        total_calculated = Decimal("0")
        
        for idx, item in enumerate(items):
            ingredient_id = item.get("ingredient_id")
            ingredient_name = item.get("ingredient_name")
            quantity_packs = Decimal(str(item["quantity_packs"]))
            price_per_pack = Decimal(str(item["price_per_pack"]))
            
            # Find ingredient by ID or name
            if ingredient_id:
                # Convert string to UUID if needed
                from uuid import UUID as UUIDType
                if isinstance(ingredient_id, str):
                    ingredient_id = UUIDType(ingredient_id)
                
                result = await self.session.execute(
                    select(Ingredient).where(Ingredient.id == ingredient_id)
                )
                ingredient = result.scalar_one_or_none()
                if not ingredient:
                    raise ValueError(
                        f"Ингредиент с ID '{ingredient_id}' не найден. "
                        "Сначала создайте его в справочнике."
                    )
            elif ingredient_name:
                result = await self.session.execute(
                    select(Ingredient).where(Ingredient.name == ingredient_name)
                )
                ingredient = result.scalar_one_or_none()
                if not ingredient:
                    raise ValueError(
                        f"Ингредиент '{ingredient_name}' не найден. "
                        "Сначала создайте его в справочнике."
                    )
            else:
                raise ValueError(
                    f"Позиция #{idx + 1}: укажите ingredient_id или ingredient_name"
                )
            
            # Calculate line total
            line_total = quantity_packs * price_per_pack
            total_calculated += line_total
            
            # Get package size (default to 1 for base units)
            package_size = getattr(ingredient, 'package_size', None) or DEFAULT_PACKAGE_SIZE
            
            validated_items.append({
                "ingredient": ingredient,
                "quantity_packs": quantity_packs,
                "price_per_pack": price_per_pack,
                "line_total": line_total,
                "package_size": package_size,
            })
        
        # Phase 2: Verify total matches expected (Law 2: Decimal precision)
        total_calculated = total_calculated.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_expected_q = total_expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Allow ±1₸ tolerance for rounding differences in supplier invoices
        if abs(total_calculated - total_expected_q) > Decimal("1.00"):
            difference = abs(total_calculated - total_expected_q)
            raise ValueError(
                f"Сумма позиций ({total_calculated}) не совпадает с ожидаемым итогом "
                f"({total_expected_q}). Разница: {difference} ₸"
            )
        
        # Phase 3: Process all items with SERIALIZABLE isolation (Law 7)
        # Note: Caller should wrap this in a transaction with proper isolation
        processed_items = []
        ledger_ids = []
        
        for item_data in validated_items:
            ingredient = item_data["ingredient"]
            quantity_packs = item_data["quantity_packs"]
            price_per_pack = item_data["price_per_pack"]
            package_size = item_data["package_size"]
            line_total = item_data["line_total"]
            
            # Convert packs to base units (grams/ml)
            quantity_base_units = quantity_packs * package_size
            
            # Calculate unit cost (per base unit)
            unit_cost = (line_total / quantity_base_units).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            
            # Get current stock and WAC
            current_stock = await self.get_stock_balance(ingredient.id)
            current_wac = await self.get_current_wac(ingredient.id)
            
            # Calculate new WAC (Law 8)
            new_wac = self._calculate_new_wac(
                old_stock=current_stock,
                old_wac=current_wac or Decimal("0"),
                new_qty=quantity_base_units,
                new_unit_cost=unit_cost,
            )
            
            # Create ledger entry
            entry = InventoryLedger(
                ingredient_id=ingredient.id,
                event_type=InventoryEventType.SUPPLY.value,
                change_amount=quantity_base_units,
                unit_cost=unit_cost,
                weighted_average_cost=new_wac,
                cost_snapshot=line_total,
                negative_stock=False,
                reason=supplier_note,
                business_date=business_date,
            )
            
            self.session.add(entry)
            await self.session.flush()

            # Автоматически обновляем current_price ингредиента
            ingredient.current_price = unit_cost

            processed_items.append({
                "ingredient_id": str(ingredient.id),
                "ingredient_name": ingredient.name,
                "quantity_packs": str(quantity_packs),
                "quantity_base_units": str(quantity_base_units.quantize(Decimal("0.01"))),
                "price_per_pack": str(price_per_pack.quantize(Decimal("0.01"))),
                "line_total": str(line_total.quantize(Decimal("0.01"))),
                "unit_cost": str(unit_cost),
                "new_wac": str(new_wac.quantize(Decimal("0.0001"))),
            })
            ledger_ids.append(str(entry.id))
        
        return {
            "status": "success",
            "business_date": str(business_date),
            "supplier_note": supplier_note,
            "items_count": len(processed_items),
            "total_calculated": str(total_calculated),
            "total_expected": str(total_expected_q),
            "items": processed_items,
            "ledger_ids": ledger_ids,
        }

