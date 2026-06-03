from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from operator_day.domain import ProductSnapshot


@dataclass(frozen=True)
class UnitMath:
    revenue: float
    commission: float
    gross_margin: float
    margin_rate: float
    break_even_price: float


@dataclass(frozen=True)
class RepricePlan:
    sku: str
    current_price: float
    floor_price: float
    target_price: float
    expected_margin: float


@dataclass(frozen=True)
class BidPlan:
    sku: str
    bid_before: int
    bid_after: int
    expected_drr: float
    conversion_probability: float
    localization_index: float


def unit_math(product: ProductSnapshot) -> UnitMath:
    commission = max(product.price, 0) * _clamp(product.commission_rate, 0, 0.95)
    gross_margin = max(product.price, 0) - commission - max(product.cost, 0)
    margin_rate = gross_margin / product.price if product.price > 0 else 0
    break_even_price = product.cost / max(1 - _clamp(product.commission_rate, 0, 0.95), 0.01)
    return UnitMath(
        revenue=round(product.price, 2),
        commission=round(commission, 2),
        gross_margin=round(gross_margin, 2),
        margin_rate=round(margin_rate, 4),
        break_even_price=round(break_even_price, 2),
    )


def listing_quality_score(product: ProductSnapshot) -> int:
    title_score = min(len(product.name.strip()) / 80, 1) * 30
    rating_score = _clamp(product.rating / 5, 0, 1) * 30
    stock_score = _clamp(product.stock / 30, 0, 1) * 20
    margin_score = _clamp(unit_math(product).margin_rate / 0.35, 0, 1) * 20
    return round(title_score + rating_score + stock_score + margin_score)


def estimate_daily_sales(product: ProductSnapshot) -> float:
    price_factor = _clamp(1000 / max(product.price, 1), 0.35, 2.5)
    rating_factor = _clamp(product.rating / 4.5 if product.rating else 0.75, 0.5, 1.2)
    stock_pressure = 1.6 if product.stock <= 4 else 1.0
    return round(max(0.4, price_factor * rating_factor * stock_pressure), 2)


def reorder_quantity(
    product: ProductSnapshot,
    *,
    cover_days: int = 28,
    safety_stock_days: int = 5,
) -> int:
    demand = estimate_daily_sales(product)
    target_stock = ceil(demand * max(cover_days + safety_stock_days, 1))
    return max(0, target_stock - max(product.stock, 0))


def warehouse_distribution(quantity: int, *, localization_index: float = 0.72) -> dict[str, int]:
    quantity = max(int(quantity), 0)
    if quantity == 0:
        return {}
    local_weight = _clamp(localization_index, 0.45, 0.9)
    weights = {
        "Коледино": local_weight,
        "Казань": (1 - local_weight) * 0.58,
        "Краснодар": (1 - local_weight) * 0.42,
    }
    raw = {name: quantity * weight / sum(weights.values()) for name, weight in weights.items()}
    distribution = {name: int(value) for name, value in raw.items()}
    remainder = quantity - sum(distribution.values())
    for name in sorted(raw, key=lambda item: raw[item] - int(raw[item]), reverse=True)[:remainder]:
        distribution[name] += 1
    return {name: count for name, count in distribution.items() if count > 0}


def reprice_plan(
    product: ProductSnapshot,
    *,
    competitor_price: float | None = None,
    min_margin_rate: float = 0.16,
) -> RepricePlan:
    math = unit_math(product)
    floor_price = math.break_even_price / max(1 - min_margin_rate, 0.01)
    reference_price = (
        competitor_price if competitor_price and competitor_price > 0 else product.price
    )
    target_price = max(floor_price, reference_price * 0.985)
    target_price = round(target_price / 10) * 10
    expected_margin = target_price * (1 - product.commission_rate) - product.cost
    return RepricePlan(
        sku=product.sku,
        current_price=round(product.price, 2),
        floor_price=round(floor_price, 2),
        target_price=round(target_price, 2),
        expected_margin=round(expected_margin, 2),
    )


def ad_bid_plan(
    product: ProductSnapshot,
    *,
    bid_before: int,
    target_drr: float,
    localization_index: float,
) -> BidPlan:
    math = unit_math(product)
    stock_factor = _clamp(product.stock / 30, 0.25, 1)
    conversion_probability = _clamp(
        0.015 + (product.rating / 5) * 0.055 + math.margin_rate * 0.08,
        0.01,
        0.16,
    )
    affordable_click = (
        max(math.gross_margin, 0)
        * _clamp(target_drr, 0.03, 0.7)
        * conversion_probability
    )
    locality_factor = _clamp(localization_index, 0.45, 1.1)
    bid_after = (
        round(max(10, min(bid_before, affordable_click * locality_factor * stock_factor)) / 2)
        * 2
    )
    expected_drr = bid_after / max(math.gross_margin * conversion_probability, 1)
    return BidPlan(
        sku=product.sku,
        bid_before=int(bid_before),
        bid_after=int(bid_after),
        expected_drr=round(expected_drr, 4),
        conversion_probability=round(conversion_probability, 4),
        localization_index=round(locality_factor, 4),
    )


def forecast_money_effect(product: ProductSnapshot, quantity: int) -> float:
    math = unit_math(product)
    realistic_units = min(max(quantity, 0), 45)
    return round(max(math.gross_margin, 0) * realistic_units, 2)


def reprice_money_effect(product: ProductSnapshot, plan: RepricePlan) -> float:
    current_margin = unit_math(product).gross_margin
    margin_delta = max(plan.expected_margin - current_margin, 0)
    affected_units = max(min(product.stock, 30), 1)
    return round(margin_delta * affected_units, 2)


def ad_savings_effect(plan: BidPlan, *, expected_clicks_per_day: int = 80, days: int = 7) -> float:
    saved_per_click = max(plan.bid_before - plan.bid_after, 0)
    expected_clicks = max(expected_clicks_per_day, 0) * max(days, 1)
    return round(saved_per_click * expected_clicks / 100, 2)


def confidence_from_inputs(
    *,
    source_count: int,
    has_verified_policy: bool = False,
    uses_live_account: bool = False,
) -> float:
    score = 0.46 + min(max(source_count, 0), 6) * 0.055
    if has_verified_policy:
        score += 0.12
    if uses_live_account:
        score += 0.14
    return round(_clamp(score, 0.35, 0.92), 2)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
