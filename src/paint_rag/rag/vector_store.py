import json
import math
from pathlib import Path

from paint_rag.rag.documents import Chunk


class VectorStore:

    def __init__(self):
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def all_vectors(self) -> list[list[float]]:
        return [list(v) for v in self._vectors]

    def add(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:

        if len(chunks) != len(vectors):
            raise ValueError(
                "Number of chunks and vectors must match"
            )

        self._chunks.extend(chunks)
        self._vectors.extend(vectors)

    def save(self, path: str | Path) -> None:
        """Сохранить chunks и векторы в JSON-файл (без внешних
        зависимостей).  Возвращаемая структура: список пар
        [chunk_dict, vector]."""
        path = Path(path)
        payload = [
            [chunk.model_dump(mode="json"), list(vector)]
            for chunk, vector in zip(
                self._chunks,
                self._vectors,
            )
        ]
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "VectorStore":
        path = Path(path)
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
        store = cls()
        for item in payload:
            chunk_dict, vector = item
            store._chunks.append(
                Chunk.model_validate(chunk_dict)
            )
            store._vectors.append(list(vector))
        return store

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]:

        if not self._chunks:
            return []

        results = []

        for chunk, vector in zip(
            self._chunks,
            self._vectors,
        ):
            score = self._cosine_similarity(
                query_vector,
                vector,
            )

            results.append(
                (chunk, score)
            )

        results.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return results[:top_k]

    @staticmethod
    def _cosine_similarity(
        a: list[float],
        b: list[float],
    ) -> float:

        if len(a) != len(b):
            raise ValueError(
                "Vector dimensions must match"
            )

        dot = sum(
            x * y
            for x, y in zip(a, b)
        )

        norm_a = math.sqrt(
            sum(x * x for x in a)
        )

        norm_b = math.sqrt(
            sum(x * x for x in b)
        )

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (
            norm_a * norm_b
        )