from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_sct470_article_mixing_consumption():
    store = _store()
    p = store.get_by_article("SC-T470")
    assert p is not None
    assert p.name == "Эмаль SC-T470"
    assert "HPU 6205" in p.mixing.raw
    assert p.mixing.hardener_ratio.min == 50
    assert p.mixing.thinner_ratio.min == 10
    assert p.mixing.thinner_ratio.max == 30
    assert p.consumption_min == 100.0
    assert p.consumption_max == 140.0


def test_cetol_567_article_consumption():
    store = _store()
    p = store.get_by_article("5048-004001")
    assert p is not None
    assert p.name == "Антисептик Cetol 567 BDP"
    assert "Cetol WP 567 BPD" in p.aliases
    assert p.consumption_min == 50.0
    assert p.consumption_max == 160.0
    assert p.consumption_unit == "ml_per_m2"


def test_wf761_article_consumption():
    store = _store()
    p = store.get_by_article("WF 761")
    assert p is not None
    assert "Cetol WF 761" in p.aliases
    assert p.consumption_min == 60.0
    assert p.consumption_max == 80.0


def test_wf771_article_consumption():
    store = _store()
    p = store.get_by_article("WF 771")
    assert p is not None
    assert "Cetol WF 771" in p.aliases
    assert p.consumption_min == 100.0
    assert p.consumption_max == 150.0


def test_rubbol_3310_article_consumption():
    store = _store()
    p = store.get_by_article("WF 3310-03-xx")
    assert p is not None
    assert "Rubbol WF 3310-03-xx" in p.aliases
    assert p.consumption_min == 150.0
    assert p.consumption_max == 250.0


def test_owald_wt420_wt090_wt892_wt894_winflex():
    store = _store()

    wt420 = store.get_by_article("WT 420")
    assert wt420 is not None
    assert "BIO SEALER WT 420" in wt420.aliases
    assert wt420.consumption_min == 60.0
    assert wt420.consumption_max == 80.0

    wt090 = store.get_by_article("WT 090")
    assert wt090 is not None
    assert "HYDRAOIL WT 090" in wt090.aliases
    assert wt090.consumption_min == 50.0
    assert wt090.consumption_max == 90.0

    wt892 = store.get_by_article("WT 892")
    assert wt892 is not None
    assert wt892.consumption_min == 80.0
    assert wt892.consumption_max == 140.0

    wt894 = store.get_by_article("WT 894")
    assert wt894 is not None
    assert "NATURA WOOD WT 894" in wt894.aliases
    assert wt894.consumption_min == 80.0
    assert wt894.consumption_max == 150.0

    winf = store.get_by_article("WINFLEX 695 / WMA 695")
    assert winf is not None
    assert "WINFLEX 695" in winf.aliases
    assert winf.consumption_min == 80.0
    assert winf.consumption_max == 150.0
