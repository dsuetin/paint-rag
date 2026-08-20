from paint_rag.rag.embedding_store import EmbeddingStore


def test_add_and_get():
    store = EmbeddingStore()
    store.add("chunk:0", [1.0, 2.0, 3.0])
    assert store.get("chunk:0") == [1.0, 2.0, 3.0]


def test_get_missing_returns_none():
    store = EmbeddingStore()
    assert store.get("unknown") is None


def test_readd_replaces():
    store = EmbeddingStore()
    store.add("chunk:0", [1.0, 2.0])
    store.add("chunk:0", [9.0, 9.0])
    assert store.get("chunk:0") == [9.0, 9.0]
    assert len(store) == 1


def test_all_returns_all():
    store = EmbeddingStore()
    store.add("a", [1.0])
    store.add("b", [2.0])
    assert store.all() == {"a": [1.0], "b": [2.0]}


def test_all_is_copy():
    store = EmbeddingStore()
    store.add("a", [1.0])
    snapshot = store.all()
    snapshot["extra"] = [0.0]
    assert "extra" not in store.all()


def test_len():
    store = EmbeddingStore()
    assert len(store) == 0
    store.add("a", [1.0])
    assert len(store) == 1
    store.add("b", [2.0])
    assert len(store) == 2


def test_init_with_embeddings():
    store = EmbeddingStore({"a": [1.0], "b": [2.0]})
    assert len(store) == 2
    assert store.get("a") == [1.0]
