import os
from src.importers.pdf_ingestion import parse_pdf_to_product
from src.models import Product

FIXTURE = 'data/knowledge/2575-001251-200 Д-Дур лак.pdf'


def test_pdf_parsing():
    product = parse_pdf_to_product(FIXTURE)
    
    assert product is not None
    assert product.article == '2575-001251'
    assert product.name == 'Лак Д-ДУР'
    assert product.mixing.base_percent == 100
    assert product.mixing.hardener_ratio['min'] == 30
    assert product.mixing.thinner_ratio['min'] == 30
    assert product.max_layers == 3
    assert '2575-001251-200' in product.source['file']