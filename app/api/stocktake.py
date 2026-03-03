"""
WENDRINK ERP - Stocktake API Endpoints

API для проведения инвентаризации склада.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.stocktake import StocktakeService


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class StocktakeItemInput(BaseModel):
    """Input for stocktake item update."""
    ingredient_id: str = Field(..., description="UUID ингредиента")
    actual_quantity: Decimal = Field(..., ge=0, description="Реальный остаток")
    notes: Optional[str] = Field(None, description="Комментарий")


class CreateStocktakeRequest(BaseModel):
    """Request to create stocktake."""
    business_date: Optional[date] = Field(None, description="Дата инвентаризации")
    conducted_by: Optional[str] = Field(None, description="Кто проводит")
    notes: Optional[str] = Field(None, description="Комментарий")


class UpdateStocktakeRequest(BaseModel):
    """Request to update stocktake items."""
    items: list[StocktakeItemInput] = Field(..., description="Позиции инвентаризации")


class StocktakeItemResponse(BaseModel):
    """Stocktake item response."""
    ingredient_id: str
    ingredient_name: str
    unit: str
    expected_quantity: str
    actual_quantity: Optional[str]
    variance_quantity: Optional[str]
    unit_cost: str
    variance_value: Optional[str]
    notes: Optional[str]


class StocktakeResponse(BaseModel):
    """Stocktake response."""
    id: str
    business_date: str
    status: str
    conducted_by: Optional[str]
    notes: Optional[str]
    total_expected_value: Optional[str]
    total_actual_value: Optional[str]
    total_variance_value: Optional[str]
    items_count: int
    created_at: str
    completed_at: Optional[str]


class StocktakeDetailResponse(BaseModel):
    """Stocktake detail response with items."""
    id: str
    business_date: str
    status: str
    conducted_by: Optional[str]
    notes: Optional[str]
    items: list[StocktakeItemResponse]
    created_at: str


class StocktakeReportResponse(BaseModel):
    """Stocktake report response."""
    stocktake_id: str
    business_date: str
    status: str
    conducted_by: Optional[str]
    completed_at: Optional[str]
    summary: dict
    shortages: list[dict]
    surpluses: list[dict]
    matches: list[dict]


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=StocktakeDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stocktake",
    description="""
    📋 **СОЗДАТЬ ИНВЕНТАРИЗАЦИЮ**
    
    Автоматически:
    - Создаёт позиции для всех 55 ингредиентов
    - Заполняет ожидаемые остатки из системы
    - Ставит статус DRAFT (черновик)
    
    После создания нужно заполнить реальные остатки через PUT.
    """,
)
async def create_stocktake(
    data: CreateStocktakeRequest,
    db: AsyncSession = Depends(get_db),
) -> StocktakeDetailResponse:
    """Create new stocktake."""
    service = StocktakeService(db)
    
    stocktake = await service.create_stocktake(
        business_date=data.business_date,
        conducted_by=data.conducted_by,
        notes=data.notes,
    )
    
    await db.commit()
    stocktake = await service.get_stocktake(stocktake.id)
    
    return StocktakeDetailResponse(
        id=str(stocktake.id),
        business_date=str(stocktake.business_date),
        status=stocktake.status,
        conducted_by=stocktake.conducted_by,
        notes=stocktake.notes,
        items=[
            StocktakeItemResponse(
                ingredient_id=str(item.ingredient_id),
                ingredient_name=item.ingredient.name,
                unit=item.ingredient.unit,
                expected_quantity=str(item.expected_quantity),
                actual_quantity=str(item.actual_quantity) if item.actual_quantity else None,
                variance_quantity=str(item.variance_quantity) if item.variance_quantity else None,
                unit_cost=str(item.unit_cost),
                variance_value=str(item.variance_value) if item.variance_value else None,
                notes=item.notes,
            )
            for item in stocktake.items
        ],
        created_at=stocktake.created_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[StocktakeResponse],
    summary="List Stocktakes",
)
async def list_stocktakes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StocktakeResponse]:
    """List all stocktakes."""
    service = StocktakeService(db)
    stocktakes = await service.list_stocktakes(limit=limit, offset=offset)
    
    return [
        StocktakeResponse(
            id=str(s.id),
            business_date=str(s.business_date),
            status=s.status,
            conducted_by=s.conducted_by,
            notes=s.notes,
            total_expected_value=str(s.total_expected_value) if s.total_expected_value else None,
            total_actual_value=str(s.total_actual_value) if s.total_actual_value else None,
            total_variance_value=str(s.total_variance_value) if s.total_variance_value else None,
            items_count=len(s.items) if hasattr(s, 'items') else 0,
            created_at=s.created_at.isoformat(),
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
        )
        for s in stocktakes
    ]


@router.get(
    "/{stocktake_id}",
    response_model=StocktakeDetailResponse,
    summary="Get Stocktake",
)
async def get_stocktake(
    stocktake_id: str,
    db: AsyncSession = Depends(get_db),
) -> StocktakeDetailResponse:
    """Get stocktake by ID."""
    service = StocktakeService(db)
    
    try:
        stocktake_uuid = UUID(stocktake_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stocktake ID")
    
    stocktake = await service.get_stocktake(stocktake_uuid)
    if stocktake is None:
        raise HTTPException(status_code=404, detail="Stocktake not found")
    
    return StocktakeDetailResponse(
        id=str(stocktake.id),
        business_date=str(stocktake.business_date),
        status=stocktake.status,
        conducted_by=stocktake.conducted_by,
        notes=stocktake.notes,
        items=[
            StocktakeItemResponse(
                ingredient_id=str(item.ingredient_id),
                ingredient_name=item.ingredient.name,
                unit=item.ingredient.unit,
                expected_quantity=str(item.expected_quantity),
                actual_quantity=str(item.actual_quantity) if item.actual_quantity else None,
                variance_quantity=str(item.variance_quantity) if item.variance_quantity else None,
                unit_cost=str(item.unit_cost),
                variance_value=str(item.variance_value) if item.variance_value else None,
                notes=item.notes,
            )
            for item in stocktake.items
        ],
        created_at=stocktake.created_at.isoformat(),
    )


@router.put(
    "/{stocktake_id}",
    response_model=StocktakeDetailResponse,
    summary="Update Stocktake Items",
    description="""
    ✏️ **ЗАПОЛНИТЬ РЕАЛЬНЫЕ ОСТАТКИ**
    
    Принимает список позиций с реальными остатками.
    Автоматически рассчитывает расхождения.
    
    **Пример:**
    ```json
    {
      "items": [
        {"ingredient_id": "...", "actual_quantity": 85000},
        {"ingredient_id": "...", "actual_quantity": 12500}
      ]
    }
    ```
    """,
)
async def update_stocktake(
    stocktake_id: str,
    data: UpdateStocktakeRequest,
    db: AsyncSession = Depends(get_db),
) -> StocktakeDetailResponse:
    """Update stocktake items with actual quantities."""
    service = StocktakeService(db)
    
    try:
        stocktake_uuid = UUID(stocktake_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stocktake ID")
    
    try:
        items = [
            {
                "ingredient_id": item.ingredient_id,
                "actual_quantity": item.actual_quantity,
                "notes": item.notes,
            }
            for item in data.items
        ]
        stocktake = await service.update_all_items(stocktake_uuid, items)
        await db.commit()
        stocktake = await service.get_stocktake(stocktake_uuid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return StocktakeDetailResponse(
        id=str(stocktake.id),
        business_date=str(stocktake.business_date),
        status=stocktake.status,
        conducted_by=stocktake.conducted_by,
        notes=stocktake.notes,
        items=[
            StocktakeItemResponse(
                ingredient_id=str(item.ingredient_id),
                ingredient_name=item.ingredient.name,
                unit=item.ingredient.unit,
                expected_quantity=str(item.expected_quantity),
                actual_quantity=str(item.actual_quantity) if item.actual_quantity else None,
                variance_quantity=str(item.variance_quantity) if item.variance_quantity else None,
                unit_cost=str(item.unit_cost),
                variance_value=str(item.variance_value) if item.variance_value else None,
                notes=item.notes,
            )
            for item in stocktake.items
        ],
        created_at=stocktake.created_at.isoformat(),
    )


@router.delete(
    "/{stocktake_id}",
    summary="Delete Stocktake",
)
async def delete_stocktake(
    stocktake_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a draft stocktake."""
    from sqlalchemy import text
    try:
        stocktake_uuid = UUID(stocktake_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stocktake ID")

    result = await db.execute(
        text("SELECT id, status FROM stocktakes WHERE id = :id"),
        {"id": str(stocktake_uuid)}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Stocktake not found")
    if row[1] == "completed":
        raise HTTPException(status_code=400, detail="Cannot delete completed stocktake")

    await db.execute(
        text("DELETE FROM stocktake_items WHERE stocktake_id = :id"),
        {"id": str(stocktake_uuid)}
    )
    await db.execute(
        text("DELETE FROM stocktakes WHERE id = :id"),
        {"id": str(stocktake_uuid)}
    )
    await db.commit()
    return {"message": "Deleted"}


@router.post(
    "/{stocktake_id}/complete",
    response_model=StocktakeReportResponse,
    summary="Complete Stocktake",
    description="""
    ✅ **ЗАВЕРШИТЬ ИНВЕНТАРИЗАЦИЮ**
    
    - Проверяет что все позиции заполнены
    - Рассчитывает итоги
    - Создаёт ADJUSTMENT события в ledger
    - Приводит системные остатки в соответствие с реальными
    - Возвращает отчёт по расхождениям
    """,
)
async def complete_stocktake(
    stocktake_id: str,
    db: AsyncSession = Depends(get_db),
) -> StocktakeReportResponse:
    """Complete stocktake and apply adjustments."""
    service = StocktakeService(db)
    
    try:
        stocktake_uuid = UUID(stocktake_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stocktake ID")
    
    try:
        await service.complete_stocktake(stocktake_uuid, apply_adjustments=True)
        await db.commit()
        report = await service.get_report(stocktake_uuid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return StocktakeReportResponse(**report)


@router.get(
    "/{stocktake_id}/report",
    response_model=StocktakeReportResponse,
    summary="Get Stocktake Report",
    description="""
    📊 **ОТЧЁТ ПО ИНВЕНТАРИЗАЦИИ**
    
    Показывает:
    - Недостачи (убытки)
    - Излишки
    - Совпадения
    - Общую сумму расхождений
    """,
)
async def get_stocktake_report(
    stocktake_id: str,
    db: AsyncSession = Depends(get_db),
) -> StocktakeReportResponse:
    """Get stocktake report."""
    service = StocktakeService(db)
    
    try:
        stocktake_uuid = UUID(stocktake_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stocktake ID")
    
    try:
        report = await service.get_report(stocktake_uuid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    return StocktakeReportResponse(**report)


# ============================================================================
# Quick Reset Endpoint (for initial setup)
# ============================================================================

class QuickResetRequest(BaseModel):
    """Request for quick inventory reset."""
    items: list[StocktakeItemInput]
    notes: Optional[str] = "Начальная инвентаризация"


@router.post(
    "/quick-reset",
    response_model=StocktakeReportResponse,
    summary="Quick Inventory Reset",
    description="""
    🔄 **БЫСТРЫЙ СБРОС ОСТАТКОВ**
    
    Используется при первом запуске системы для установки
    РЕАЛЬНЫХ остатков вместо тестовых данных.
    
    Одним запросом:
    1. Создаёт инвентаризацию
    2. Заполняет реальные остатки
    3. Завершает и применяет коррекции
    
    После этого система будет работать с правильными остатками!
    """,
)
async def quick_reset(
    data: QuickResetRequest,
    db: AsyncSession = Depends(get_db),
) -> StocktakeReportResponse:
    """Quick inventory reset for initial setup."""
    service = StocktakeService(db)
    
    try:
        items = [
            {
                "ingredient_id": item.ingredient_id,
                "actual_quantity": item.actual_quantity,
                "notes": item.notes,
            }
            for item in data.items
        ]
        stocktake = await service.reset_to_actual(items, notes=data.notes)
        await db.commit()
        report = await service.get_report(stocktake.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return StocktakeReportResponse(**report)
