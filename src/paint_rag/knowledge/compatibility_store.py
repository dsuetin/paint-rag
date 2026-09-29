import json
from pathlib import Path

from paint_rag.models.compatibility import CompatibilityRule


class CompatibilityStore:

    def __init__(
        self,
        rules: list[CompatibilityRule],
    ):
        self.rules = rules

    @classmethod
    def from_json(
        cls,
        path: str | Path,
    ) -> "CompatibilityStore":

        path = Path(path)

        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        rules = [
            CompatibilityRule.model_validate(item)
            for item in data
        ]

        return cls(rules)

    def find(
        self,
        base: str,
        top: str,
    ) -> CompatibilityRule | None:

        base = base.upper()
        top = top.upper()

        for rule in self.rules:
            if (
                rule.base == base
                and rule.top == top
            ):
                return rule

        return None

    def all_for_top(self, top: str) -> list[CompatibilityRule]:
        """Все правила, где ``top`` — верхний слой (по химии)."""
        top = top.upper()
        return [r for r in self.rules if r.top == top]


# Backward-compat alias: some older tests/code import the store with a
# ``from_json`` that reads a list OR a {'rules': [...]} dict.
def _normalize_rules(data):
    if isinstance(data, dict):
        data = data.get("rules", data.get("compatibility", []))
    return data