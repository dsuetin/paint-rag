"""Customer Golden Questions — постоянный evaluation-контур Paint RAG.

Состав пакета:

- :mod:`evaluation.questions` — загрузка/валидация golden-вопросов;
- :mod:`evaluation.runner` — прогон реального RAG-пайплайна и сохранение
  результатов (JSON-файл на итерацию);
- :mod:`evaluation.comparison` — сравнение двух итераций и детекция
  объективных регрессий/изменений.

CLI-точки входа (запуск как скрипты):

- ``evaluation/run_customer_questions.py``;
- ``evaluation/compare_customer_questions.py``.

Импорт из пакета: ``from evaluation.questions import load_questions``.
"""
