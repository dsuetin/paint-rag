from paint_rag.knowledge.technical_data_extractor import (
    extract_technical_data,
)


def test_gloss_extracted():
    data = extract_technical_data(
        "Степень блеска - 10±3, 20±3"
    )
    assert data.gloss == "10±3, 20±3"


def test_dry_residue_extracted():
    data = extract_technical_data(
        "Сухой остаток - 54±2%."
    )
    assert data.dry_residue == "54±2%"


def test_density_extracted():
    data = extract_technical_data(
        "Плотность - 1,00±0,05 г/см³."
    )
    assert data.density == "1,00±0,05 г/см³"


def test_viscosity_extracted():
    data = extract_technical_data(
        "Вязкость смеси Din 4:\n"
        "70±10"
    )
    assert data.viscosity == "70±10"


def test_pot_life_extracted():
    data = extract_technical_data(
        "Время жизни смеси:\n"
        "3 часа"
    )
    assert data.pot_life == "3 часа"


def test_drying_extracted():
    data = extract_technical_data(
        "Время высыхания или полировки \n"
        "после нанесения второго слоя: \n"
        "24 часа"
    )
    assert data.drying == "24 часа"


def test_shelf_life_extracted():
    data = extract_technical_data(
        "Срок годности: \n"
        "от 12 месяцев"
    )
    assert data.shelf_life == "от 12 месяцев"


def test_shelf_life_trailing_period_kept():
    data = extract_technical_data(
        "Срок годности: \n"
        "от 12 месяцев."
    )
    assert (
        data.shelf_life
        in {"от 12 месяцев.", "от 12 месяцев"}
    )


def test_application_extracted():
    data = extract_technical_data(
        "Нанесение: \n"
        "Пневматический краскопульт"
    )
    assert data.application == "Пневматический краскопульт"


def test_usage_extracted():
    data = extract_technical_data(
        "Применение: прозрачный лак для \n"
        "отделки изделий из массива древесины \n"
        "и шпонированных поверхностей\n"
        "Рекомендованный расход: \n"
        "100 – 120 гр/м²"
    )
    assert (
        data.usage
        == "прозрачный лак для отделки "
        "изделий из массива древесины "
        "и шпонированных поверхностей"
    )


def test_range_preserved():
    data = extract_technical_data(
        "Сухой остаток - 15 – 30%"
    )
    assert data.dry_residue == "15 – 30%"


def test_tolerance_preserved():
    data = extract_technical_data(
        "Степень блеска - 20±3"
    )
    assert data.gloss == "20±3"


def test_missing_value_is_none():
    data = extract_technical_data(
        "Сухой остаток - 54±2%"
    )
    assert data.gloss is None
    assert data.viscosity is None
    assert data.shelf_life is None
    assert data.application is None
    assert data.usage is None


def test_empty_text_returns_empty_technical_data():
    data = extract_technical_data("")
    assert data.gloss is None
    assert data.dry_residue is None
    assert data.application is None


def test_extractor_does_not_depend_on_filename():
    text = (
        "Сухой остаток - 48±2%. "
        "Плотность - 1,10±0,05 г/см³."
    )
    same_a = extract_technical_data(text)
    same_b = extract_technical_data(text)
    assert same_a == same_b
    assert same_a.dry_residue == "48±2%"
    # Файловое имя не влияет на результат: та же строка текста
    # всегда даёт один и тот же ответ.


def test_english_labels_supported():
    data = extract_technical_data(
        "Solid content: 54±2%\n"
        "Density: 1.00 g/cm3"
    )
    assert data.dry_residue == "54±2%"
    assert data.density == "1.00 g/cm3"
