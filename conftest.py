"""Корневой conftest для pytest.

Добавляет корень проекта в ``sys.path``, чтобы тестовые модули можно было
импортировать как пакет (``tests.rag.test_real_retrieval`` и т. д.).

``pyproject.toml`` уже добавляет ``src/``; здесь добавляется сам корень
проекта. Это позволяет кросс-импортам между тестовыми модулями (например
``BENCHMARK`` в ``test_hybrid_retrieval`` из ``test_real_retrieval``)
работать независимо от того, из какой директории запущен pytest.
"""
import os
import sys

_ROOT = os.path.abspath(os.path.dirname(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
