from pathlib import Path

from paint_rag.knowledge.compatibility_store import (
    CompatibilityStore,
)


DATA = Path(
    "data/knowledge/compatibility.json"
)


def test_pu_on_wb_is_forbidden():

    store = CompatibilityStore.from_json(DATA)

    rule = store.find(
        base="WB",
        top="PU",
    )

    assert rule is not None
    assert rule.allowed is True


def test_nc_on_wb_is_forbidden():

    store = CompatibilityStore.from_json(DATA)

    rule = store.find(
        base="WB",
        top="NC",
    )

    assert rule is not None
    assert rule.allowed is True


def test_pu_on_nc_is_forbidden():

    store = CompatibilityStore.from_json(DATA)

    rule = store.find(
        base="NC",
        top="PU",
    )

    assert rule is not None
    assert rule.allowed is True