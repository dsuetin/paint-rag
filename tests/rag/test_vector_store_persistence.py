"""Task 16 — VectorStore JSON persistence (no external deps)."""
from pathlib import Path

from paint_rag.models.document import Chunk
from paint_rag.rag.vector_store import VectorStore


def _chunk(text: str, article: str) -> Chunk:
    return Chunk(
        id=f"{article}:1:0",
        text=text,
        product="Лак PV210",
        variant_id=1,
        article=article,
        chunk_id=0,
    )


def test_save_load_roundtrip(tmp_path: Path):
    vs = VectorStore()
    vs.add(
        [_chunk("Сухой остаток 54±2%", "PV210")],
        [[0.1, 0.2, 0.3]],
    )
    path = tmp_path / "vs.json"
    vs.save(path)
    assert path.exists()

    vs2 = VectorStore.load(path)
    assert len(vs2) == 1
    chunks = vs2.all_chunks()
    assert chunks[0].article == "PV210"
    assert chunks[0].text == "Сухой остаток 54±2%"
    assert vs2.all_vectors() == [[0.1, 0.2, 0.3]]


def test_saved_file_is_plain_json(tmp_path: Path):
    vs = VectorStore()
    vs.add(
        [_chunk("x", "PA777-9016")],
        [[1.0]],
    )
    path = tmp_path / "vs.json"
    vs.save(path)
    text = path.read_text(encoding="utf-8")
    import json
    data = json.loads(text)
    assert isinstance(data, list)
    assert len(data) == 1
    chunk_dict, vec = data[0]
    assert isinstance(chunk_dict, dict)
    assert vec == [1.0]


def test_search_still_works_after_reload(tmp_path: Path):
    vs = VectorStore()
    vs.add(
        [
            _chunk("Грунт", "PA334-9016"),
            _chunk("Лак", "PV210"),
        ],
        [
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )
    path = tmp_path / "vs.json"
    vs.save(path)
    vs2 = VectorStore.load(path)

    # «Грунт» ближе к вектору [1,0].
    results = vs2.search([1.0, 0.0], top_k=1)
    assert len(results) == 1
    assert results[0][0].article == "PA334-9016"
    assert results[0][1] == 1.0


def test_metadata_preserved_after_reload(tmp_path: Path):
    vs = VectorStore()
    ch = Chunk(
        id="PV290-99:1:0",
        text="Текст",
        product="Лак PV290",
        variant_id=1,
        article="PV290-99",
        chunk_id=0,
        technology="Rupa",
        technical_data={"gloss": "100±3", "dry_residue": "56±2%"},
        source={"sheet": "Rupa", "file": "Rupa_PV290_99.pdf", "page": 1},
    )
    vs.add([ch], [[0.5, 0.5]])
    path = tmp_path / "vs.json"
    vs.save(path)
    vs2 = VectorStore.load(path)
    ch2 = vs2.all_chunks()[0]
    assert ch2.technology == "Rupa"
    assert ch2.technical_data == {"gloss": "100±3", "dry_residue": "56±2%"}
    assert ch2.source == {"sheet": "Rupa", "file": "Rupa_PV290_99.pdf", "page": 1}
