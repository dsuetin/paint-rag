"""StandaloneDocument — самостоятельный методический документ STAINWOOD.

Это НЕ Product: документ о дереве, шлифовке, МДФ, растворителях, системах
нанесения, дефектах, безопасности и т. п. Он не принадлежит одному продукту
у него нет обязательных ``article``/``product``.

Правила:
- ``text`` + full provenance (``source_file`` + ``page``/``sheet``/``section``)
  обязательны для осмысленного индекса (chunk без источника — запрещён).
- ``related_products`` / ``related_articles`` — опциональная связь, только
  если она явно определена в источнике; никогда не выводятся автоматически.
- StandaloneDocument не превращает документ в Product и не создаёт
  structured compatibility relations.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class StandaloneDocument(BaseModel):
    """Текст методического документа с полным provenance."""

    # Провенанс (обязателен: chunk без источника не создаём).
    source_file: str
    kind: str = "text"  # txt | pdf | docx | doc | xlsx
    title: str | None = None
    page: int | None = None
    sheet: str | None = None
    section: str | None = None

    # Содержание.
    text: str

    # Опциональная связанность (только если явно задана в источнике).
    related_products: list[str] = Field(default_factory=list)
    related_articles: list[str] = Field(default_factory=list)

    # Дополнительный metadata (brand, автор, размер и пр.) — необязательно.
    metadata: dict[str, object] = Field(default_factory=dict)
