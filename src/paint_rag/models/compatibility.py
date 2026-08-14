from pydantic import BaseModel


class CompatibilityRule(BaseModel):
    base: str
    top: str

    allowed: bool

    reason: str | None = None

    conditions: list[str] = []
    exceptions: list[str] = []