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
    # Product-часть: для standalone-документов ``product``/``article``/
    # ``variant_id`` не заданы (это самостоятельное знание, не Product).
    product: str | None = None
    variant_id: int = 0
    article: str | None = None
    chunk_id: int
    technology: str | None = None
    technical_data: dict[str, Any] | None = None
    source: dict[str, Any] | None = None
    compatibility: list[dict[str, Any]] | None = None
    alternatives: list[dict[str, Any]] | None = None
    relation_sources: list[dict[str, Any]] | None = None
    application_order: list[dict[str, Any]] | None = None
    chemical_system: dict[str, Any] | None = None
    application_roles: list[str] | None = None
    application_scope: str | None = None
    # Standalone-часть (методический документ, не Product).
    doc_type: str | None = None
    title: str | None = None
    related_products: list[str] | None = None
    related_articles: list[str] | None = None