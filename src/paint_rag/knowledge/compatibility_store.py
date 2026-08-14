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