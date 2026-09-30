"""StainWood chemical-system classification models.

Each product gets an optional :pydata:`chemical_system` field that records:
- **code** — one of ``NC | AC | PU | PE | UV | WB | UNKNOWN``.
- **provenance** — the STAINWOOD document (file + page/section + quote)
  from which the class was extracted.

``code`` is the ONLY field that participates in matrix resolution logic.
``provenance`` is required for auditing and RAG transparency.

The :data:`CHEMICAL_CLASSES` frozenset defines the closed set of codes.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

#: Closed set of allowed chemical-system codes.
#: ``NC`` – nitrocellulose          ``AC`` – acid-cure (alkyd)
#: ``PU`` – polyurethane            ``PE`` – polyester
#: ``UV`` – UV-cure                 ``WB`` – water-based
CHEMICAL_CLASSES: frozenset[str] = frozenset(
    {"NC", "AC", "PU", "PE", "UV", "WB"}
)

#: Sentinel for "no explicit evidence found" (not an error, not a guess).
UNKNOWN = "UNKNOWN"

#: All codes including the sentinel.
ALL_CODES: frozenset[str] = CHEMICAL_CLASSES | {UNKNOWN}


class ChemicalSystemProvenance(BaseModel):
    """Source location and raw quote backing a chemical-system assignment."""

    file: str
    """Absolute or relative path to the STAINWOOD document."""

    page: int | None = None
    """Page number (1-based) if the evidence is on a specific page."""

    section: str | None = None
    """Section heading / table name (e.g. «Тип Материала», designation line)."""

    quote: str | None = None
    """Raw text from the TDS (max 200 chars) that explicitly states the class."""

    @model_validator(mode="after")
    def _file_nonempty(self):
        if not self.file or not self.file.strip():
            raise ValueError("provenance.file must be non-empty")
        return self


class ChemicalSystem(BaseModel):
    """Product → chemical-system mapping with mandatory provenance.

    A valid assignment has ``code`` in :data:`CHEMICAL_CLASSES` and
    non-empty :attr:`provenance.file`.

    ``code == UNKNOWN`` is valid and does NOT require provenance; it
    signals "no explicit evidence found" — the safest state.

    Never inferred from product name, role, folder structure, or
    chemical similarity.  Only from explicit TDS text.
    """

    code: str = UNKNOWN
    """NC | AC | PU | PE | UV | WB | UNKNOWN."""

    provenance: ChemicalSystemProvenance | None = None
    """Mandatory when code is a real class (in CHEMICAL_CLASSES);
    optional for UNKNOWN (no evidence to cite)."""

    @model_validator(mode="after")
    def _code_valid(self) -> "ChemicalSystem":
        if self.code not in ALL_CODES:
            raise ValueError(
                f"chemical_system.code must be one of {sorted(ALL_CODES)}, "
                f"got {self.code!r}"
            )
        if self.code in CHEMICAL_CLASSES:
            if self.provenance is None:
                raise ValueError(
                    "chemical_system.provenance is required when "
                    f"code={self.code!r} (must be proven from a STAINWOOD "
                    "document; cannot be guessed from name or role)"
                )
        return self

    # Convenience
    @property
    def is_known(self) -> bool:
        return self.code in CHEMICAL_CLASSES

    def __repr__(self) -> str:
        return f"ChemicalSystem(code={self.code!r}, file={self.provenance and self.provenance.file!r})"


__all__ = [
    "ChemicalSystem",
    "ChemicalSystemProvenance",
    "CHEMICAL_CLASSES",
    "UNKNOWN",
    "ALL_CODES",
]
