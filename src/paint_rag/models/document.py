from typing import Any, Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    product: str
    variant_id: int
    text: str

    article: Optional[str] = None
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )
    
class Chunk(BaseModel):
    text: str

    product: str
    variant_id: int

    chunk_id: int