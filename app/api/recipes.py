"""
WENDRINK ERP - Recipe API Endpoints

CRUD operations for recipes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, cast, Integer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.recipe import Recipe
from app.schemas.recipe import RecipeCreate, RecipeRead

router = APIRouter()


@router.post(
    "",
    response_model=RecipeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Recipe Entry",
)
async def create_recipe(
    data: RecipeCreate,
    session: AsyncSession = Depends(get_db),
) -> Recipe:
    """
    Add an ingredient to a product's recipe.
    
    - **product_id**: Product this recipe belongs to
    - **ingredient_id**: Ingredient used in the recipe
    - **quantity**: Amount of ingredient per product unit
    """
    # Verify product exists
    product_result = await session.execute(
        select(Product).where(Product.id == data.product_id)
    )
    if product_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {data.product_id} not found",
        )
    
    # Verify ingredient exists
    ingredient_result = await session.execute(
        select(Ingredient).where(Ingredient.id == data.ingredient_id)
    )
    if ingredient_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {data.ingredient_id} not found",
        )
    
    recipe = Recipe(
        product_id=data.product_id,
        ingredient_id=data.ingredient_id,
        quantity=data.quantity,
    )
    
    session.add(recipe)
    
    try:
        await session.commit()
        await session.refresh(recipe)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This ingredient is already in the recipe for this product",
        )
    
    return recipe


@router.get(
    "",
    response_model=list[RecipeRead],
    summary="List All Recipes",
)
async def list_recipes(
    session: AsyncSession = Depends(get_db),
    product_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Recipe]:
    """Get all recipes with optional product filter."""
    query = (
        select(Recipe)
        .join(Product, Recipe.product_id == Product.id)
        .order_by(cast(Product.pos_code, Integer), Recipe.created_at)
        .offset(skip)
        .limit(limit)
    )
    
    if product_id:
        query = query.where(Recipe.product_id == product_id)
    
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get(
    "/{recipe_id}",
    response_model=RecipeRead,
    summary="Get Recipe Entry",
)
async def get_recipe(
    recipe_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> Recipe:
    """Get a recipe entry by ID."""
    result = await session.execute(
        select(Recipe).where(Recipe.id == recipe_id)
    )
    recipe = result.scalar_one_or_none()
    
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe entry {recipe_id} not found",
        )
    
    return recipe


@router.delete(
    "/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Recipe Entry",
)
async def delete_recipe(
    recipe_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove an ingredient from a product's recipe."""
    result = await session.execute(
        select(Recipe).where(Recipe.id == recipe_id)
    )
    recipe = result.scalar_one_or_none()
    
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe entry {recipe_id} not found",
        )
    
    await session.delete(recipe)
    await session.commit()
