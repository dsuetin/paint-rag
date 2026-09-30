#!/usr/bin/env python3
"""Миграция подтверждённой совместимости ВНУТРЬ Product.

Цель (задача 3): «compatibility.json» перестаёт быть источником истины.
Только подтверждённые связи (есть первичный источник —
``product_relations.json``, который сам из ТД PDF) переносятся в поле
``Product.compatibility`` в ``data/knowledge/products.json``.

Правила:
* legacy ``data/knowledge/compatibility.json`` (матрица NC/AC/PU/PE/UV/WB)
  НЕ переносится: первичный источник не найден, происхождение —
  ручной ввод в INITIAL-коммите. Все 25 правил остаются legacy/UNKNOWN.
* Переносится только запись со ``status == CONFIRMED``/``FORBIDDEN``
  и заполненным ``source`` (RelationSource.has_provenance).
* Связь хранится в списке ``compatibility`` продукта-base (на стороне
  того, под которым лежит top). Каждый элемент — ``ProductRelation``
  (base+top+status+source).

Запуск::

    python scripts/migrate_compatibility.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "data" / "knowledge"
PRODUCTS = KNOWLEDGE / "products.json"
RELATIONS = KNOWLEDGE / "product_relations.json"
LEGACY = KNOWLEDGE / "compatibility.json"


def _norm(value: str) -> str:
    return (value or "").replace("-", "").replace(" ", "").lower()


def _product_candidates(product: dict) -> list[str]:
    out = [product.get("article") or ""]
    out += [a for a in (product.get("aliases") or []) if a]
    if product.get("name"):
        out.append(product["name"])
    return out


def _match(product: dict, ref: str) -> bool:
    target = _norm(ref)
    return any(_norm(c) == target for c in _product_candidates(product) if c)


def migrate(dry_run: bool = False) -> int:
    products = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    relations = json.loads(RELATIONS.read_text(encoding="utf-8"))

    summary = {
        "migrated": 0,
        "skipped_no_source": 0,
        "skipped_base_not_found": 0,
        "skipped_duplicate": 0,
        "skipped_other_status": 0,
    }

    for rel in relations:
        source = rel.get("source") or {}
        has_prov = bool(source.get("file") or source.get("sheet")
                        or source.get("row") is not None or source.get("note"))
        status = rel.get("status", "CONFIRMED")
        base_ref = rel.get("base")
        top_ref = rel.get("top")

        if status not in ("CONFIRMED", "FORBIDDEN"):
            summary["skipped_other_status"] += 1
            continue
        if not has_prov:
            summary["skipped_no_source"] += 1
            print(f"SKIP (нет source) {base_ref}->{top_ref}", file=sys.stderr)
            continue

        base_product = next((p for p in products if _match(p, base_ref)), None)
        if base_product is None:
            summary["skipped_base_not_found"] += 1
            print(f"SKIP (base не найден) {base_ref}->{top_ref}", file=sys.stderr)
            continue

        entry = {
            "base": rel["base"],
            "top": rel["top"],
            "allowed": rel.get("allowed", status == "CONFIRMED"),
            "status": status,
            "reason": rel.get("reason"),
            "conditions": list(rel.get("conditions") or []),
            "source": dict(source),
        }

        existing = base_product.get("compatibility") or []
        if any(
            _norm(e.get("base")) == _norm(entry["base"])
            and _norm(e.get("top")) == _norm(entry["top"])
            for e in existing
        ):
            summary["skipped_duplicate"] += 1
            continue

        if not dry_run:
            base_product["compatibility"] = existing + [entry]
        summary["migrated"] += 1
        print(f"migrated: base={base_ref} top={top_ref} status={status}")

    if not dry_run:
        PRODUCTS.write_text(
            json.dumps(products, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    legacy = json.loads(LEGACY.read_text(encoding="utf-8"))
    print(
        f"\nsummary: {json.dumps(summary, ensure_ascii=False)} "
        f"legacy_rules_not_migrated={len(legacy)} (UNKNOWN)"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(migrate(dry_run=args.dry_run))
