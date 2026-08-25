from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.models.product import Product, TechnicalData

DATA = Path("data/knowledge/products.json")


def test_product_without_technical_data_still_validates():

    product = Product(
        name="Тестовый продукт"
    )

    assert product.technical_data is None


def test_product_with_technical_data_validates():

    product = Product(
        name="Лак Т1",
        technical_data=TechnicalData(
            gloss="10±3, 20±3",
            dry_residue="54±2%",
            density="1,00±0,05 г/см³",
        ),
    )

    td = product.technical_data
    assert td is not None
    assert td.gloss == "10±3, 20±3"
    assert td.dry_residue == "54±2%"
    assert td.density == "1,00±0,05 г/см³"


def test_range_preserved_without_loss():

    td = TechnicalData(
        gloss="15–30",
        application="Пневматический краскопульт",
    )

    product = Product(
        name="Лак Т2",
        technical_data=td,
    )

    assert (
        product.technical_data.gloss
        == "15–30"
    )


def test_textual_value_preserved():

    product = Product(
        name="Лак Т3",
        technical_data=TechnicalData(
            pot_life="3 часа",
            drying="до 12 часов",
        ),
    )

    td = product.technical_data
    assert td.pot_life == "3 часа"
    assert td.drying == "до 12 часов"


def test_json_round_trip_keeps_technical_data():

    product = Product(
        name="Лак Т4",
        technical_data=TechnicalData(
            gloss="100±3",
            dry_residue="56±2%",
            density="1,00±0,05 г/см³",
            application="Пневматический краскопульт",
            description=(
                "Высокоглянцевый прозрачный "
                "полиуретановый 2K лак"
            ),
            usage=(
                "отделка мебели из шпона "
                "и массива"
            ),
        ),
    )

    dumped = product.model_dump(
        mode="json"
    )

    restored = Product.model_validate(
        dumped
    )

    assert restored.name == "Лак Т4"

    orig = product.technical_data
    new = restored.technical_data

    assert new is not None
    assert new.gloss == orig.gloss
    assert new.dry_residue == orig.dry_residue
    assert new.density == orig.density
    assert new.application == orig.application
    assert new.description == orig.description
    assert new.usage == orig.usage


def test_partial_technical_data_defaults_to_none():

    td = TechnicalData(
        gloss="20±3"
    )

    assert td.dry_residue is None
    assert td.viscosity is None
    assert td.pot_life is None
    assert td.drying is None
    assert td.shelf_life is None
    assert td.application is None
    assert td.description is None
    assert td.usage is None


def test_existing_products_still_load():

    store = ProductStore.from_json(DATA)

    assert len(store.products) > 0

    for product in store.products:
        assert product.technical_data is None
