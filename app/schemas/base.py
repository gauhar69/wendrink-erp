"""
WENDRINK ERP - Base Schema Configuration

Provides base configuration for all Pydantic models:
- Decimal serialized as string in JSON
- UUID serialized as string in JSON
- Strict validation
"""

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


class BaseSchema(BaseModel):
    """
    Base schema with standard configuration.
    
    All schemas inherit from this to ensure:
    - Decimal → string serialization (Law 2 compliance)
    - UUID → string serialization
    - Strict mode for type safety
    """
    
    model_config = ConfigDict(
        from_attributes=True,  # Allow ORM model conversion
        strict=True,           # Strict type checking
        validate_default=True, # Validate default values
        extra="forbid",        # Forbid extra fields
    )

    @field_serializer("*", mode="wrap")
    @classmethod
    def serialize_special_types(cls, value: Any, handler: Any) -> Any:
        """Serialize Decimal and UUID as strings."""
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, UUID):
            return str(value)
        return handler(value)


# Type aliases for consistent decimal handling
# Use these in schema fields for money/quantity
DecimalStr = Annotated[Decimal, "Decimal that serializes as string"]
