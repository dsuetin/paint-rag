from paint_rag.tools.calculator import (
    calculate_from_reference,
)


REFERENCE = {
    "base": {
        "kg": 0.09259259259259259,
        "cost": 46.11111111111111,
    },
    "hardener": {
        "kg": 0.0462962962962963,
        "cost": 38.56481481481482,
    },
    "thinner": {
        "kg": 0.027777777777777776,
        "cost": 7.388888888888888,
    },
}


def test_ground_pd_1m2():

    result = calculate_from_reference(
        area_m2=1,
        layers=1,
        reference=REFERENCE,
    )

    assert abs(
        result.base.kg
        - 0.09259259259259259
    ) < 1e-9

    assert abs(
        result.hardener.kg
        - 0.0462962962962963
    ) < 1e-9

    assert abs(
        result.thinner.kg
        - 0.027777777777777776
    ) < 1e-9

    assert abs(
        result.total_cost
        - 92.06481481481481
    ) < 1e-9


def test_ground_pd_50m2_2_layers():

    result = calculate_from_reference(
        area_m2=50,
        layers=2,
        reference=REFERENCE,
    )

    assert abs(
        result.base.kg
        - 9.259259259259259
    ) < 1e-9

    assert abs(
        result.hardener.kg
        - 4.62962962962963
    ) < 1e-9

    assert abs(
        result.thinner.kg
        - 2.7777777777777777
    ) < 1e-9

    assert abs(
        result.total_kg
        - 16.666666666666668
    ) < 1e-9

    assert abs(
        result.total_cost
        - 9206.481481481482
    ) < 1e-9