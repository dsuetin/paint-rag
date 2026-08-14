# src/paint_rag/tools/product_lookup.py

from paint_rag.models.product import Product


class ProductStore:

    def __init__(self, products: list[Product]):
        self.products = products

    def find(self, query: str) -> list[Product]:
        query = query.lower()

        return [
            product
            for product in self.products
            if (
                query in product.name.lower()
                or (
                    product.article
                    and query in product.article.lower()
                )
            )
        ]