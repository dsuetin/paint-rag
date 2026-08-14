from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.knowledge.compatibility_store import (
    CompatibilityStore,
)
from paint_rag.router import classify_question
from paint_rag.tools.calculator import (
    calculate_consumption,
)


PRODUCTS = Path(
    "data/knowledge/products.json"
)

COMPATIBILITY = Path(
    "data/knowledge/compatibility.json"
)


def print_variants(product):

    print(
        f"\nПродукт: {product.name}"
    )

    if not product.variants:
        print("Варианты отсутствуют")
        return

    for variant in product.variants:

        print(
            f"\nВариант {variant.variant_id}"
        )

        if variant.price is not None:
            print(
                f"Цена: {variant.price}"
            )

        if variant.coverage:
            print(
                f"Расход: "
                f"{variant.coverage.value} "
                f"{variant.coverage.unit}"
            )

        if variant.mixing:

            mixing = variant.mixing

            print(
                f"Основа: "
                f"{mixing.base_percent}%"
            )

            if mixing.hardener:
                print(
                    f"Отвердитель: "
                    f"{mixing.hardener.name} "
                    f"— "
                    f"{mixing.hardener.percent}%"
                )

            if mixing.thinner:
                print(
                    f"Разбавитель: "
                    f"{mixing.thinner.percent}%"
                )


def main():

    products = ProductStore.from_json(
        PRODUCTS
    )

    compatibility = (
        CompatibilityStore.from_json(
            COMPATIBILITY
        )
    )

    print("Paint RAG v0.1")
    print("Введите вопрос или exit")

    while True:

        question = input("\n> ")

        if question.lower() == "exit":
            break

        question_type = classify_question(
            question
        )

        print(
            f"Тип вопроса: "
            f"{question_type.value}"
        )

        found = products.find(question)

        if not found:

            print(
                "Продукт не найден"
            )

            continue

        product = found[0]

        # -------------------------
        # MIXING
        # -------------------------

        if question_type.value == "mixing":

            print_variants(product)

        # -------------------------
        # CALCULATION
        # -------------------------

        elif question_type.value == "calculation":

            if not product.variants:

                print(
                    "У продукта нет вариантов."
                )

                continue

            variant = product.variants[0]

            if not variant.coverage:

                print(
                    "Для продукта нет данных "
                    "о расходе."
                )

                continue

            coverage = variant.coverage.value

            result = calculate_consumption(
                area_m2=50,
                layers=2,
                consumption_min=coverage,
                consumption_max=coverage,
            )

            print(
                f"Продукт: "
                f"{product.name}"
            )

            print(
                f"Вариант: "
                f"{variant.variant_id}"
            )

            print(
                f"Расход: "
                f"{result.min_kg:.2f}"
                f"–"
                f"{result.max_kg:.2f}"
                f" кг"
            )

        # -------------------------
        # GENERAL
        # -------------------------

        else:

            print(
                f"\n{product.name}"
            )

            if product.technology:
                print(
                    f"Технология: "
                    f"{product.technology}"
                )

            print_variants(product)


if __name__ == "__main__":
    main()