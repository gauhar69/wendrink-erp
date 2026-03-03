"""
WENDRINK ERP - Product API Endpoints

CRUD operations for products.
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.product import Product
from app.models.recipe import Recipe
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.schemas.recipe import RecipeRead

router = APIRouter()


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_db),
) -> Product:
    """
    Create a new product.
    
    - **name**: Unique product name
    - **price**: Selling price in KZT (Decimal)
    - **is_active**: Whether product is available for sale
    """
    product = Product(
        name=data.name,
        price=data.price,
        is_active=data.is_active,
    )
    
    session.add(product)
    
    try:
        await session.commit()
        await session.refresh(product)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product '{data.name}' already exists",
        )
    
    return product


@router.get(
    "",
    response_model=list[ProductRead],
    summary="List Products",
)
async def list_products(
    session: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
) -> list[Product]:
    """Get all products with pagination."""
    query = select(Product).order_by(Product.name).offset(skip).limit(limit)
    
    if active_only:
        query = query.where(Product.is_active == True)
    
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Get Product",
)
async def get_product(
    product_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> Product:
    """Get a product by ID."""
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    return product


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    summary="Update Product",
)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    session: AsyncSession = Depends(get_db),
) -> Product:
    """
    Update a product.
    
    Only provided fields are updated.
    """
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    try:
        await session.commit()
        await session.refresh(product)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product name '{data.name}' already exists",
        )
    
    return product


@router.get(
    "/{product_id}/recipe",
    response_model=list[RecipeRead],
    summary="Get Product Recipe",
)
async def get_product_recipe(
    product_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[Recipe]:
    """Get the full recipe for a product."""
    # Verify product exists
    product_result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    if product_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    # Get recipes
    result = await session.execute(
        select(Recipe)
        .where(Recipe.product_id == product_id)
        .order_by(Recipe.created_at)
    )
    return list(result.scalars().all())
