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

    chunks: list["Chunk"] = Field(
        default_factory=list
    )


class Chunk(BaseModel):
    id: str
    text: str
    product: str
    variant_id: int
    article: str | None = None
    chunk_id: int
    technology: str | None = None
    technical_data: dict[str, Any] | None = None
    source: dict[str, Any] | None = None