"""CompatiblityResolver / SystemResolver — детерминированный слой
«совместимости» и «систем покрытия», стоящий **над** Retriever/LLM.

Ключевые принципы (ТЗ §3, §4, §8, §16):

* LLM НЕ устанавливает совместимость сама. Совместимость — это
  структурированный результат с одним из трёх статусов:

  - ``CONFIRMED`` — явная связь в источнике (артикул/артикул,
    или химия/химия, с провенансом);
  - ``FORBIDDEN`` — явное запрещение в источнике;
  - ``UNKNOWN``   — в документации нет ни подтверждения, ни запрета.

* **Отсутствие правила ≠ FORBIDDEN.** Для отсутствующих пар
  возвращается ``UNKNOWN``.

* Совместимость **не выводится** по химической основе
  («оба полиуретановые → совместимы» — ЗАПРЕЩЕНО, ТЗ §8).

Источники (все с провенансом), в порядке приоритета:
1. :class:`paint_rag.models.Product.compatibility` — встроено в
   Product (первичный источник истины; см. scripts/migrate_compatibility.py);
2. ``data/knowledge/product_relations.json`` — отдельные relations
   уровня артикулов (source обязателен);
3. ``data/knowledge/compatibility.json`` — legacy химическая матрица
   NC/AC/PU/PE/UV/WB (без ``source`` — помечается ``legacy=True``);
4. ``data/knowledge/coating_systems.json`` — именованные coating systems
   (Excel «Системы нанесения» T1/T2/T3 + PDF «Примеры систем под кисть»).

Результат передаётся LLM через блок «STRUCTURED RESULT» в prompt —
LLM обязана цитировать статус и **не переопределять** его.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from paint_rag.knowledge.compatibility_store import CompatibilityStore
from paint_rag.knowledge.relation_store import RelationStore
from paint_rag.knowledge.systems_store import SystemsStore


# ----------------------------------------------------------------------
# Product ref
# ----------------------------------------------------------------------


class ProductRef(BaseModel):
    """Указатель на продукт (артикул + опц. химия)."""
    article: str | None = None
    name: str | None = None
    chemistry: str | None = None  # NC / AC / PU / PE / UV / WB


# ----------------------------------------------------------------------
# Structured finding / result
# ----------------------------------------------------------------------


class CompatibilityFinding(BaseModel):
    """Одна связь совместимости с полным провенансом."""
    base_article: str | None = None
    top_article: str | None = None

    base_chemistry: str | None = None
    top_chemistry: str | None = None

    relation: str | None = None
    allowed: bool | None = None
    status: str = "UNKNOWN"
    reason: str | None = None
    conditions: list[str] = Field(default_factory=list)
    source: dict | None = None
    legacy: bool = False


class StructuredResult(BaseModel):
    """Итог работы resolver-ов на конкретный вопрос.

    Вставляется в prompt как «STRUCTURED RESULT»; LLM обязана
    цитировать статус и не переопределять.
    """
    status: str = "UNKNOWN"
    relation: str | None = None
    findings: list[CompatibilityFinding] = Field(default_factory=list)
    system_name: str | None = None
    system_substrate: str | None = None
    system_layers: list[str] = Field(default_factory=list)
    reason: str | None = None
    note: str | None = None

    def to_prompt_dict(self) -> dict:
        d: dict = {
            "status": self.status,
            "relation": self.relation,
            "findings": [f.model_dump() for f in (self.findings or [])],
            "reason": self.reason,
            "note": self.note,
            "system": None,
        }
        if self.system_name is not None:
            d["system"] = {
                "name": self.system_name,
                "status": (
                    "CONFIRMED"
                    if self.status in ("CONFIRMED", "UNKNOWN", "FORBIDDEN")
                    and self.system_name
                    else self.status
                ),
                "substrate": self.system_substrate,
                "layers": list(self.system_layers or []),
            }
        return d


# ----------------------------------------------------------------------
# Resolvers
# ----------------------------------------------------------------------


class CompatibilityResolver:
    """Детерминированный поиск совместимости «base под top».

    ``top`` — продукт (артикул), НАД которым идёт вопрос.
    ``base`` — продукт (артикул), ПОД которым идёт вопрос.

    Порядок поиска:
    1. Product-level: ``Product.compatibility`` (внутри модели
       продукта — источник истины после миграции, ТЗ задача 3).
    2. Файл ``product_relations.json`` (если ``Product.compatibility``
       пустое) — CONFIRMED/FORBIDDEN.
    3. Chemistry-level (``compatibility.json``, legacy) — помечается
       ``legacy=True``; НЕ является доказательством совместимости.
    4. UNKNOWN — пары нет ни там, ни там (отсутствие ≠ FORBIDDEN).
    """

    def __init__(
        self,
        chemistry: CompatibilityStore | None = None,
        relations: RelationStore | None = None,
        products: list = None,
    ) -> None:
        self.chemistry = chemistry or CompatibilityStore(rules=[])
        self.relations = relations or RelationStore(relations=[])
        self.products = list(products or [])

    # ------------------------------------------------------------------
    def _find_in_products(
        self,
        base_article: str,
        top_article: str,
    ):
        base_n = self._n(base_article)
        top_n = self._n(top_article)
        for product in self.products:
            for rel in (getattr(product, "compatibility", None) or []):
                if (
                    self._n(rel.base) == base_n
                    and self._n(rel.top) == top_n
                ):
                    return rel
        return None

    @staticmethod
    def _n(value: str) -> str:
        return value.strip().upper()

    # ------------------------------------------------------------------
    def resolve(
        self,
        base: ProductRef,
        top: ProductRef,
    ) -> StructuredResult:
        # 1) Product-level: сначала в Product.compatibility (source of truth),
        #    затем в product_relations.json (файл).
        if base.article and top.article:
            rule = self._find_in_products(base.article, top.article)
            in_product = rule is not None
            if rule is None:
                rule = self.relations.find(base=base.article, top=top.article)
            if rule is not None:
                f = CompatibilityFinding(
                    base_article=base.article,
                    top_article=top.article,
                    relation="topcoat_on",
                    allowed=rule.allowed,
                    status=rule.status,
                    reason=rule.reason,
                    conditions=list(rule.conditions),
                    legacy=False,
                    source=(
                        rule.source.as_dict()
                        if rule.source.has_provenance
                        else None
                    ),
                )
                return StructuredResult(
                    status=rule.status,
                    relation="topcoat_on",
                    findings=[f],
                    note=(
                        "Правило найдено в Product.compatibility "
                        "(источник истины, после миграции задачи 3)."
                        if in_product
                        else "Правило найдено в product_relations.json "
                        "(уровень артикулов, с исходником)."
                    ),
                )

        # 2) Chemistry-level.
        if base.chemistry and top.chemistry:
            rule = self.chemistry.find(
                base=base.chemistry,
                top=top.chemistry,
            )
            if rule is not None:
                f = CompatibilityFinding(
                    base_chemistry=base.chemistry,
                    top_chemistry=top.chemistry,
                    relation="topcoat_on",
                    allowed=rule.allowed,
                    status=rule.status,
                    reason=rule.reason,
                    conditions=list(rule.conditions or []),
                    legacy=not (rule.source.file or rule.source.sheet),
                    source=(
                        {
                            "file": rule.source.file,
                            "sheet": rule.source.sheet,
                            "page": rule.source.page,
                            "note": rule.source.note,
                        }
                        if rule.source and (
                            rule.source.file
                            or rule.source.sheet
                            or rule.source.page
                        )
                        else None
                    ),
                )
                return StructuredResult(
                    status=rule.status,
                    relation="topcoat_on",
                    findings=[f],
                    note=(
                        "Правило найдено в compatibility.json "
                        "(уровень химии base→top)."
                    ),
                )

        # 3) UNKNOWN (no inferred «same-chemistry => compatible»).
        return StructuredResult(
            status="UNKNOWN",
            relation="topcoat_on",
            reason=(
                "В предоставленной документации нет ни подтверждения, "
                "ни запрета совместимости этих конкретных продуктов. "
                "Отсутствие правила не означает, что они несовместимы."
            ),
            note="нет правила ни на уровне артикулов, ни на уровне химии",
        )

    def find_primers_for(self, top: ProductRef) -> list[CompatibilityFinding]:
        """Все base-продукты, допустимые под ``top`` (для Q7).

        Показывает только явные правила (product-level и chemistry-level),
        не додумывает недостающие.
        """
        findings: list[CompatibilityFinding] = []
        seen_bases: set[str] = set()

        # 1) Product.compatibility (source of truth после миграции).
        if top.article:
            for product in self.products:
                for rule in (getattr(product, "compatibility", None) or []):
                    if rule.top.strip().upper() != top.article.strip().upper():
                        continue
                    key = rule.base.strip().upper()
                    if key in seen_bases:
                        continue
                    seen_bases.add(key)
                    findings.append(
                        CompatibilityFinding(
                            base_article=rule.base,
                            top_article=top.article,
                            relation="primer_under",
                            allowed=rule.allowed,
                            status=rule.status,
                            reason=rule.reason,
                            conditions=list(rule.conditions),
                            legacy=False,
                            source=(
                                rule.source.as_dict()
                                if rule.source.has_provenance
                                else None
                            ),
                        )
                    )

        # 2) Файл product_relations.json (дубль, если не в Product).
        if top.article:
            for r in self.relations.all_for_top(top.article):
                key = r.base.strip().upper()
                if key in seen_bases:
                    continue
                seen_bases.add(key)
                findings.append(
                    CompatibilityFinding(
                        base_article=r.base,
                        top_article=top.article,
                        relation="primer_under",
                        allowed=r.allowed,
                        status=r.status,
                        reason=r.reason,
                        conditions=list(r.conditions),
                        legacy=False,
                        source=(
                            r.source.as_dict()
                            if r.source.has_provenance
                            else None
                        ),
                    )
                )

        # 3) Chemistry-level (legacy).
        if top.chemistry:
            for r in self.chemistry.all_for_top(top.chemistry):
                findings.append(
                    CompatibilityFinding(
                        base_chemistry=r.base,
                        top_chemistry=top.chemistry,
                        relation="primer_under",
                        allowed=r.allowed,
                        status=r.status,
                        reason=r.reason,
                        conditions=list(r.conditions or []),
                        legacy=not (r.source.file or r.source.sheet),
                    )
                )
        return findings


class SystemResolver:
    """Детерминированный поиск coating system для подложки.

    Результат — список ``StructuredResult`` (один на каждую подтверждённую
    систему). Для подложки, где системы не описаны в KB, возвращается
    один ``UNKNOWN``.
    """

    def __init__(self, systems: SystemsStore) -> None:
        self.systems = systems

    def for_substrate(self, substrate_raw: str) -> list[StructuredResult]:
        from paint_rag.knowledge.systems_store import normalize_substrate

        normalized = normalize_substrate(substrate_raw)
        found = self.systems.find_by_substrate(normalized)

        if not found:
            return [
                StructuredResult(
                    status="UNKNOWN",
                    relation="system_for_substrate",
                    system_substrate=normalized,
                    reason=(
                        f"В предоставленной документации нет "
                        f"подтверждённой системы покрытия для подложки "
                        f"«{substrate_raw}». Это НЕ означает запрет — "
                        f"просто нет данных."
                    ),
                )
            ]

        results = []
        for s in found:
            slayers = [
                f"{layer.role}: {layer.name}" if layer.name else layer.role
                for layer in (s.layers or [])
            ]
            results.append(
                StructuredResult(
                    status="CONFIRMED",
                    relation="system_for_substrate",
                    system_name=s.name,
                    system_substrate=normalized,
                    system_layers=slayers,
                    reason=(
                        f"Система «{s.name}» описана в "
                        f"«{s.source.sheet if s.source else ''}» "
                        f"с подложками: "
                        f"{', '.join(s.substrates)!r}."
                    ),
                    note="CONFIRMED: система описана с источником в ТД.",
                )
            )
        return results


# ----------------------------------------------------------------------
# Convenience: build structured result for a query (optional)
# ----------------------------------------------------------------------


def build_structured_result(
    *,
    resolver: CompatibilityResolver,
    base_ref: ProductRef | None = None,
    top_ref: ProductRef | None = None,
    systems: SystemsStore | None = None,
    substrate: str | None = None,
) -> list[StructuredResult]:
    """Вернуть список ``StructuredResult`` для вопроса.

    - если заданы ``base_ref`` и ``top_ref`` → результат совместимости;
    - если задан ``substrate`` → системное решение;
    - иначе → ``[]`` (не вставлять в prompt).

    Этот слой **не требует LLM** — всё детерминированное.
    """
    out: list[StructuredResult] = []
    if base_ref is not None and top_ref is not None:
        out.append(resolver.resolve(base=base_ref, top=top_ref))
    if substrate is not None and systems is not None:
        out.extend(SystemResolver(systems).for_substrate(substrate))
    return out


def make_resolver_from_products(
    products: list,
    *,
    chemistry: CompatibilityStore | None = None,
    relations: RelationStore | None = None,
    systems: SystemsStore | None = None,
) -> CompatibilityResolver:
    """Собрать :class:`CompatibilityResolver` вокруг продуктов с
    встроенной ``Product.compatibility``.

    По умолчанию — пустые stores: единственный источник истины —
    ``Product.compatibility`` (задача 3). Legacy
    ``compatibility.json`` / ``product_relations.json`` подключаются
    явной передачей.
    """
    resolver = CompatibilityResolver(
        chemistry=chemistry or CompatibilityStore(rules=[]),
        relations=relations or RelationStore(relations=[]),
        products=list(products),
    )
    return resolver
