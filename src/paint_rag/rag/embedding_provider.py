import hashlib

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...


class FakeEmbeddingProvider(EmbeddingProvider):

    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be > 0")
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        embedding: list[float] = []
        block = 0
        while len(embedding) < self.dimension:
            digest = hashlib.sha256(
                f"{text}:{block}".encode("utf-8")
            ).digest()
            for byte in digest:
                embedding.append(byte / 255.0 * 2.0 - 1.0)
                if len(embedding) == self.dimension:
                    break
            block += 1
        return embedding
