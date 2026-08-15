from __future__ import annotations

import re

from paint_rag.rag.documents import Document, Chunk


def tokenize(text: str) -> set[str]:
    return set(
        re.findall(
            r"[a-zа-яё0-9-]+",
            text.lower(),
        )
    )


class Retriever:

    def __init__(
        self,
        documents: list[Document],
    ):
        self.documents = documents

        self.chunks: list[Chunk] = []

        for document in documents:
            self.chunks.extend(
                document.chunks
            )

    @classmethod
    def from_documents(
        cls,
        documents: list[Document],
    ) -> "Retriever":
        return cls(documents)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[Chunk]:

        query_tokens = tokenize(query)

        scored: list[tuple[float, Chunk]] = []

        for chunk in self.chunks:

            chunk_tokens = tokenize(
                chunk.text
            )

            if not chunk_tokens:
                continue

            matched = (
                query_tokens
                & chunk_tokens
            )

            if not matched:
                continue

            score = (
                len(matched)
                / len(query_tokens)
            )

            scored.append(
                (score, chunk)
            )

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            chunk
            for _, chunk in scored[:top_k]
        ]