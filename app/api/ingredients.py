"""
WENDRINK ERP - Ingredient API Endpoints

CRUD operations for ingredients.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.ingredient import Ingredient
from app.schemas.ingredient import IngredientCreate, IngredientRead, IngredientUpdate

router = APIRouter()


@router.post(
    "",
    response_model=IngredientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Ingredient",
)
async def create_ingredient(
    data: IngredientCreate,
    session: AsyncSession = Depends(get_db),
) -> Ingredient:
    """
    Create a new ingredient.
    
    - **name**: Unique ingredient name
    - **sku**: Stock Keeping Unit (unique identifier)
    - **unit**: Unit of measurement (kg, l, pcs, g, ml)
    - **package_size**: Base units per package (e.g., 24000 for '3KG*8 packs')
    """
    ingredient = Ingredient(
        name=data.name,
        sku=data.sku,
        unit=data.unit,
        package_size=data.package_size,
    )
    
    session.add(ingredient)
    
    try:
        await session.commit()
        await session.refresh(ingredient)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingredient '{data.name}' already exists",
        )
    
    return ingredient


@router.get(
    "",
    response_model=list[IngredientRead],
    summary="List Ingredients",
)
async def list_ingredients(
    session: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> list[Ingredient]:
    """Get all ingredients with pagination."""
    result = await session.execute(
        select(Ingredient)
        .order_by(Ingredient.name)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get(
    "/{ingredient_id}",
    response_model=IngredientRead,
    summary="Get Ingredient",
)
async def get_ingredient(
    ingredient_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> Ingredient:
    """Get an ingredient by ID."""
    result = await session.execute(
        select(Ingredient).where(Ingredient.id == ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    
    if ingredient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} not found",
        )
    
    return ingredient


@router.patch(
    "/{ingredient_id}",
    response_model=IngredientRead,
    summary="Update Ingredient",
)
async def update_ingredient(
    ingredient_id: UUID,
    data: IngredientUpdate,
    session: AsyncSession = Depends(get_db),
) -> Ingredient:
    """
    Update an ingredient.
    
    Only provided fields are updated.
    """
    result = await session.execute(
        select(Ingredient).where(Ingredient.id == ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    
    if ingredient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} not found",
        )
    
    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ingredient, field, value)
    
    try:
        await session.commit()
        await session.refresh(ingredient)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingredient name '{data.name}' already exists",
        )
    
    return ingredient
