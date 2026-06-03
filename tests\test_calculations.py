from operator_day.calculations import (
    ad_bid_plan,
    ad_savings_effect,
    forecast_money_effect,
    reorder_quantity,
    reprice_money_effect,
    reprice_plan,
    unit_math,
    warehouse_distribution,
)
from operator_day.domain import Platform, ProductSnapshot


def test_unit_math_and_reprice_are_based_on_product_inputs() -> None:
    product = ProductSnapshot(
        Platform.OZON,
        "SKU-1",
        "Товар",
        price=1000,
        stock=3,
        cost=620,
        commission_rate=0.18,
        rating=4.6,
    )

    math = unit_math(product)
    plan = reprice_plan(product, competitor_price=930)

    assert math.gross_margin == 200
    assert math.margin_rate == 0.2
    assert plan.floor_price > math.break_even_price
    assert plan.target_price >= plan.floor_price
    assert reprice_money_effect(product, plan) >= 0


def test_reorder_and_distribution_keep_total_quantity() -> None:
    product = ProductSnapshot(
        Platform.WB,
        "SKU-LOW",
        "Товар с низким остатком",
        price=500,
        stock=2,
        cost=250,
        commission_rate=0.25,
        rating=4.8,
    )

    quantity = reorder_quantity(product)
    distribution = warehouse_distribution(quantity, localization_index=0.7)

    assert quantity > 0
    assert sum(distribution.values()) == quantity
    assert "Коледино" in distribution
    assert forecast_money_effect(product, quantity) > 0


def test_ad_bid_plan_respects_margin_and_target_drr() -> None:
    product = ProductSnapshot(
        Platform.YANDEX,
        "SKU-ADS",
        "Рекламный товар",
        price=1200,
        stock=12,
        cost=560,
        commission_rate=0.16,
        rating=4.7,
    )

    plan = ad_bid_plan(product, bid_before=140, target_drr=0.18, localization_index=0.8)

    assert 10 <= plan.bid_after <= plan.bid_before
    assert 0 < plan.expected_drr < 1
    assert 0 < plan.conversion_probability <= 0.16
    assert ad_savings_effect(plan) >= 0
