from paint_rag.rag.documents import (
    Document,
    documents_to_chunks,
    document_to_chunks,
    product_to_documents
)



def test_documents_to_chunks():

    documents = [
        Document(
            product="Грунт PA334",
            variant_id=1,
            text="PA334-9016 100%; HD816 33%; Разбавитель 15–30%.",
        ),
        Document(
            product="Грунт PD",
            variant_id=1,
            text="Грунт PD. Расход 120–140 гр/м².",
        ),
    ]

    chunks = documents_to_chunks(
        documents,
        chunk_size=30,
        overlap=5,
    )

    assert len(chunks) >= 2

    assert any(
        chunk.product == "Грунт PA334"
        for chunk in chunks
    )

    assert any(
        chunk.product == "Грунт PD"
        for chunk in chunks
    )


def test_document_to_chunks_old():

    document = Document(
        product="Грунт PA334",
        variant_id=1,
        text=(
            "PA334-9016 100%; "
            "HD816 33%; "
            "Разбавитель 15–30%. "
            "Расход 120–140 гр/м². "
            "Не более 2 слоев."
        ),
    )

    chunks = document_to_chunks(
        document,
        chunk_size=50,
        overlap=10,
    )

    assert len(chunks) > 1

    assert chunks[0].product == document.product
    assert chunks[0].variant_id == 1
    assert chunks[0].chunk_id == 0

    assert "PA334-9016" in (
        chunks[0].text
        + "".join(chunk.text for chunk in chunks[1:])
    )