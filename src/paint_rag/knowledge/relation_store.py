"""RelationStore: product-level совместимость (по артикулам).

Здесь хранятся правила, у которых ``base`` и ``top`` — артикулы
(``PD155``, ``SC-T470``, ``2675-755251`` …). Отдельно от
:class:`paint_rag.knowledge.compatibility_store.CompatibilityStore`
(который — химии: NC/AC/PU/PE/UV/WB).

Оба store вместе используются
:class:`paint_rag.knowledge.compatibility_resolver.CompatibilityResolver`.
"""
from __future__ import annotations

import json
from pathlib import Path

from paint_rag.models.product_relation import ProductRelation


class RelationStore:
    def __init__(self, relations: list[ProductRelation]) -> None:
        self.relations = relations

    @classmethod
    def from_json(cls, path: str | Path) -> "RelationStore":
        path = Path(path)
        if not path.exists():
            return cls([])
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # Поддерживаем {'relations': [...]} и raw list.
            data = data.get("relations", [])
        rels = [ProductRelation.model_validate(x) for x in data]
        return cls(rels)

    def find(
        self,
        base: str,
        top: str,
    ) -> ProductRelation | None:
        base_n = self._n(base)
        top_n = self._n(top)
        for r in self.relations:
            if self._n(r.base) == base_n and self._n(r.top) == top_n:
                return r
        return None

    def all_for_top(self, top: str) -> list[ProductRelation]:
        top_n = self._n(top)
        return [r for r in self.relations if self._n(r.top) == top_n]

    def all_for_base(self, base: str) -> list[ProductRelation]:
        base_n = self._n(base)
        return [r for r in self.relations if self._n(r.base) == base_n]

    @staticmethod
    def _n(value: str) -> str:
        return value.strip().upper()
