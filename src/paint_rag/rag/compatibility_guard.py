"""Task 7 — детерминированный post-hoc guard для утверждений о совместимости.

Правило (ТЗ §2, §3):
- Утверждение «A совместим с B» допустимо ТОЛЬКО если в
  structured compatibility data существует CONFIRMED relation
  {base, top}, и оба кода A, B присутствуют как пара (независимо от
  направления «под/поверх»).
- Если CONFIRMED relation для пары НЕТ → UNKNOWN → ответ ОТКАЗ.
- FORBIDDEN relation — НЕ блокируется guard'ом (запрет допустимо
  сообщать).
- Альтернативы ≠ совместимость; coating system ≠ пара.
- Никогда НЕ выводим CONFIRMED из химического класса, назначения,
  общей системы, похожего артикула или альтернативы.

Подход (общий, без привязки к конкретным вопросам):
  Разбиваем ответ на строки. Строка — «утверждение совместимости»,
  если использует глагольную/причастную форму «совместим(а/о/ы/ый/ая)
  с|к|под|поверх» (или «совместимо») БЕЗ отрицания (не совместим,
  нет подтверждения, не указано, …) и без существительного
  «совместимость». Для каждой такой строки собираем множество
  известных артикулов (KB). Строка подтверждена, если:
    (a) хотя бы одна CONFIRMED-пара полностью присутствует в строке; или
    (b) ровно один известный артикул в строке и он — endpoint
        CONFIRMED-связи. Если ни (a), ни (b) — строка неподтверждена.
  Ответ НЕДОПУСТИМ, если хотя бы одна строка-утверждение
  неподтверждена. Консервативно: лучше лишний UNKNOWN-отказ, чем
  непроверенная совместимость.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from paint_rag.knowledge.product_store import ProductStore


# ------------------------------------------------------------------
# Result types
# ------------------------------------------------------------------


@dataclass
class GuardFinding:
    """Строка ответа с неподтверждённым утверждением совместимости."""

    snippet: str
    codes_in_line: list[str] = field(default_factory=list)
    reason: str = "no_confirmed_relation_in_kb"


@dataclass
class GuardResult:
    is_violation: bool = False
    findings: list[GuardFinding] = field(default_factory=list)
    confirmed_pairs_in_answer: list[list[str]] = field(default_factory=list)


# ------------------------------------------------------------------
# Normalisation
# ------------------------------------------------------------------


def _norm(v: str) -> str:
    """Строгая нормализация: только alphanum, верхний регистр.
    «A-PS130» → «APS130», «ICL 203.02.05» → «ICL2030205»."""
    return re.sub(r"[^A-Za-z0-9]", "", v).upper()


#: Минимальная длина нормализованного кода, который guard рассматривает как
#: «артикул/знак продукта» в ответе. Короткие «коды» (1–3 символа типа
#: ``5``, ``01``, ``092``, ``2K``, ``PU``) получаются из описательных
#: алиасов («Лак 5 глянец», «PU грунт-изолятор»), а не из настоящих
#: артикулов, и никогда не являются endpoint'ами CONFIRMED-связи. Их
#: подстрока ложно совпадает с настоящими значениями — «RAL 9005» даёт
#: ``9005``/``5``, артикул ``480555`` даёт ``5``/``8``/``1`` и т.п. — и
#: превращает безобидный ответ в ложный REFUSED. Настоящие артикулы и все
#: endpoint'ы CONFIRMED-пар имеют длину ≥ 4, поэтому порог безопасен.
MIN_CODE_LEN = 4


# ------------------------------------------------------------------
# KB extraction
# ------------------------------------------------------------------


def _build_kb(store: ProductStore):
    all_codes: set[str] = set()          # все известные коды
    confirmed_pairs: set[frozenset] = set()
    confirmed_endpoints: set[str] = set()

    for p in store.all():
        for a in [p.article, *p.aliases]:
            if a:
                all_codes.add(_norm(a))
        for v in p.variants:
            if v.article:
                all_codes.add(_norm(v.article))

        relations = list(p.compatibility or [])
        for v in p.variants:
            relations.extend(list(v.compatibility or []))

        for r in relations:
            b, t = _norm(r.base), _norm(r.top)
            if b:
                all_codes.add(b)
            if t:
                all_codes.add(t)
            if r.status == "CONFIRMED":
                confirmed_pairs.add(frozenset((b, t)))
                if b:
                    confirmed_endpoints.add(b)
                if t:
                    confirmed_endpoints.add(t)

    return (
        frozenset(c for c in all_codes if c),
        confirmed_pairs,
        confirmed_endpoints,
    )


# ------------------------------------------------------------------
# Claim-line detection (positive assertion of compatibility)
# ------------------------------------------------------------------

# Положительная формa: «совместим/совместима/совместимо/совместимый ... с|к|под|поверх»
# или «наносить под/поверх/на». НЕ включает существительное «совместимость».
_ASSERT_RE = re.compile(
    r"совместим[а-яё]*\s+(?:к|с|под|поверх)\b"
    r"|\bсовместимо\b"
    r"|наносит(?:ь|ы|ся)?\s+(?:к|с|под|поверх|на)\b"
    r"|нанес(?:ь|ен|ены|еным)\s+(?:к|с|под|поверх|на)\b",
    flags=re.IGNORECASE | re.UNICODE,
)

# Отрицание / не-утверждение — такие строки НЕ блокируются (FORBIDDEN,
# UNKNOWN, «совместимо, если…», перечисление «совместим(а/ы), …»).
_NONRE_RE = re.compile(
    r"совместимость"
    r"|несовместим"
    r"|совместим[а-яё]*\s+[,;]"
    r"|не\s+совместим"
    r"|нет\s+подтвержд"
    r"|не\s+подтвержд"
    r"|не\s+указан"
    r"|совместимо\s+если"
    r"|совместимо\s+при",
    flags=re.IGNORECASE | re.UNICODE,
)


def _is_claim_line(line: str) -> bool:
    if _NONRE_RE.search(line):
        return False
    return bool(_ASSERT_RE.search(line))


def _kb_codes_in(line: str, all_codes: frozenset[str]) -> set[str]:
    ns = _norm(line)
    return {
        c
        for c in all_codes
        if len(c) >= MIN_CODE_LEN and c in ns
    }


def _line_supported(
    line: str,
    all_codes: frozenset[str],
    confirmed_pairs: set[frozenset],
    confirmed_endpoints: set[str],
) -> tuple[bool, set[str]]:
    K = _kb_codes_in(line, all_codes)
    if not K:
        return True, K  # нет известных кодов — не пара конкретных продуктов
    if any(cp <= set(K) for cp in confirmed_pairs):
        return True, K
    if len(K) == 1:
        only = next(iter(K))
        return (only in confirmed_endpoints), K
    return False, K


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def guard_compat_answer(answer: str, store: ProductStore) -> GuardResult:
    """Проверка LLM-ответа на неподтверждённые утверждения совместимости.

    Возвращает :class:`GuardResult`. ``is_violation=True`` — если хотя
    бы одна строка утверждает совместимость конкретных продуктов, для
    которых в KB нет CONFIRMED-связи. Вызывающий код обязан вернуть
    отказ UNKNOWN (не подменяя на другую пару и не создавая relation).
    """
    result = GuardResult()
    if not answer or not answer.strip():
        return result

    all_codes, confirmed_pairs, confirmed_endpoints = _build_kb(store)

    for raw in re.split(r"[.!;:?]\s+|\n", answer):
        line = raw.strip()
        if not line:
            continue
        if not _is_claim_line(line):
            continue
        supported, K = _line_supported(
            line, all_codes, confirmed_pairs, confirmed_endpoints
        )
        if not K:
            continue
        if supported:
            for cp in confirmed_pairs:
                if cp <= set(K):
                    pair = sorted(cp)
                    if pair not in result.confirmed_pairs_in_answer:
                        result.confirmed_pairs_in_answer.append(pair)
            continue
        result.is_violation = True
        result.findings.append(
            GuardFinding(
                snippet=line[:180],
                codes_in_line=sorted(K),
            )
        )
    return result


__all__ = [
    "GuardFinding",
    "GuardResult",
    "guard_compat_answer",
]
