import json
from pathlib import Path

from paint_rag.models.product import (
    Product,
    ProductVariant,
)


class ProductStore:

    def __init__(self, products: list[Product]):
        self.products = products

    @classmethod
    def from_json(
        cls,
        path: str | Path,
    ) -> "ProductStore":

        path = Path(path)

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        products = [
            Product.model_validate(item)
            for item in data
        ]

        return cls(products)

    def all(self) -> list[Product]:
        return self.products

    def get(
        self,
        name: str,
    ) -> Product | None:

        name = name.lower().strip()

        for product in self.products:

            if product.name.lower() == name:
                return product

            if any(
                alias.lower() == name
                for alias in product.aliases
            ):
                return product

        return None

    def find(self, query: str) -> list[Product]:

        query = query.lower().strip()

        result = []

        for product in self.products:

            values = [
                product.name,
                product.article or "",
                *product.aliases,
            ]

            # Также ищем в вариантах
            for variant in product.variants:
                values.extend([
                    variant.article or "",
                ])

            if any(
                query in value.lower()
                for value in values
            ):
                result.append(product)

        return result


    def get_by_article(
        self,
        article: str,
    ) -> Product | None:

        article = article.lower().strip()

        for product in self.products:

            if (
                product.article
                and product.article.lower() == article
            ):
                return product

            for variant in product.variants:

                if (
                    variant.article
                    and variant.article.lower()
                    == article
                ):
                    return product

        return None
    
    def get_variant_by_article(
        self,
        article: str,
    ) -> tuple[Product, ProductVariant] | None:

        article = article.lower().strip()

        if not article:
            return None

        for product in self.products:

            for variant in product.variants:

                if (
                    variant.article
                    and variant.article.lower() == article
                ):
                    return (product, variant)

        for product in self.products:

            if (
                product.article
                and product.article.lower() == article
            ) and product.variants:
                return (product, product.variants[0])

        return None

    def find_variant(
        self,
        query: str,
    ) -> list[tuple[Product, ProductVariant]]:

        products = self.find(query)

        result = []

        for product in products:

            for variant in product.variants:

                result.append(
                    (product, variant)
                )

        return result