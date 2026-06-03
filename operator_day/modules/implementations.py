from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from operator_day.brain.llm import LlmRouter
from operator_day.brain.review_writer import ReviewDraftService
from operator_day.calculations import (
    ad_bid_plan,
    ad_savings_effect,
    confidence_from_inputs,
    forecast_money_effect,
    listing_quality_score,
    reorder_quantity,
    reprice_money_effect,
    reprice_plan,
    unit_math,
    warehouse_distribution,
)
from operator_day.config import get_settings
from operator_day.connectors.replay import ReplayHub
from operator_day.domain import (
    ActionResult,
    ActionRisk,
    ModuleId,
    Platform,
    TaskAction,
    TenantContext,
)
from operator_day.modules.base import OperatorModule
from operator_day.pvz.shifts import (
    build_two_two_schedule,
    calculate_payroll_by_rate,
)
from operator_day.skills_catalog import enrich_action_payload
from vendor.marketplace_sdk import (
    ozon_price_import,
    ozon_review_answer,
    wb_price_upload,
    wb_question_answer,
    yandex_market_bid_update,
)


def _action(
    module_id: ModuleId,
    title: str,
    text: str,
    label: str,
    priority: int,
    risk: ActionRisk,
    money_effect: float = 0,
    urgency: float = 0.1,
    confidence: float = 0.7,
    deadline_at: datetime | None = None,
    **payload: object,
) -> TaskAction:
    return TaskAction(
        module_id=module_id,
        title=title,
        short_text=text,
        action_label=label,
        payload=enrich_action_payload(module_id, payload),
        priority=priority,
        risk=risk,
        money_effect=money_effect,
        urgency=urgency,
        confidence=confidence,
        deadline_at=deadline_at,
    )


class AccountsModule(OperatorModule):
    module_id = ModuleId.ACCOUNTS
    title = "Кабинеты и каталог"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        low_stock = [p for p in products if p.stock <= 4]
        text = f"Каталог собран: {len(products)} товаров. Мало остатков: {len(low_stock)}."
        return [_action(self.module_id, "Проверить каталог", text, "Показать", 70, ActionRisk.SAFE)]


class UnitEconomicsModule(OperatorModule):
    module_id = ModuleId.UNIT
    title = "Юнит-экономика"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        actions = []
        for product in await replay.products():
            math = unit_math(product)
            if math.gross_margin < 120:
                actions.append(
                    _action(
                        self.module_id,
                        "Товар близко к минусу",
                        (
                            f"{product.name}: маржа около {math.gross_margin:.0f} ₽. "
                            "Подготовить новую цену?"
                        ),
                        "Показать расчет",
                        92,
                        ActionRisk.CONFIRM,
                        sku=product.sku,
                        margin=math.gross_margin,
                        margin_rate=math.margin_rate,
                        break_even_price=math.break_even_price,
                    )
                )
        return actions


class SeoModule(OperatorModule):
    module_id = ModuleId.SEO
    title = "SEO карточек"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        product = (await replay.products())[0]
        return [
            _action(
                self.module_id,
                "Улучшить текст карточки",
                f"{product.name}: готов черновик названия и описания без фото.",
                "Показать текст",
                46,
                ActionRisk.CONFIRM,
                money_effect=900,
                urgency=0.3,
                confidence=0.65,
                sku=product.sku,
                reverse_keywords=["органайзер кухня", "хранение специй"],
                listing_score=listing_quality_score(product),
            )
        ]


class SuppliesModule(OperatorModule):
    module_id = ModuleId.SUPPLIES
    title = "Поставки и штрихкоды"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        low_stock = [p for p in await replay.products() if p.stock <= 4]
        reorder_rows = [
            {"sku": product.sku, "quantity": reorder_quantity(product)}
            for product in low_stock
        ]
        money_effect = sum(
            forecast_money_effect(product, reorder_quantity(product)) for product in low_stock
        )
        return (
            [
                _action(
                    self.module_id,
                    "Подготовить поставку",
                    f"Нашел {len(low_stock)} товара с низким остатком. Сделать черновик поставки?",
                    "Собрать поставку",
                    78,
                    ActionRisk.CONFIRM,
                    money_effect=money_effect,
                    skus=[p.sku for p in low_stock],
                    reorder=reorder_rows,
                )
            ]
            if low_stock
            else []
        )


class ReviewsModule(OperatorModule):
    module_id = ModuleId.REVIEWS
    title = "Отзывы и вопросы"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        actions: list[TaskAction] = []
        for review in await replay.reviews():
            if review.rating <= 3:
                actions.append(
                    _action(
                        self.module_id,
                        "Негативный отзыв",
                        "Есть негативный отзыв. Я подготовлю черновик, но отправит человек.",
                        "Открыть",
                        99,
                        ActionRisk.HUMAN,
                        money_effect=600,
                        urgency=0.8,
                        confidence=0.8,
                        review_id=review.review_id,
                        platform=review.platform.value,
                        sku=review.sku,
                        rating=review.rating,
                        aspect_candidates=["протекает", "возврат"],
                    )
                )
            else:
                actions.append(
                    _action(
                        self.module_id,
                        "Ответить покупателю",
                        "Готов короткий ответ на хороший отзыв. Отправить?",
                        "Отправить",
                        88,
                        ActionRisk.CONFIRM,
                        money_effect=180,
                        urgency=0.4,
                        confidence=0.78,
                        review_id=review.review_id,
                        platform=review.platform.value,
                        sku=review.sku,
                        rating=review.rating,
                        buyer_question=review.buyer_question or "",
                        aspect_candidates=["удобно", "быстрая доставка"],
                    )
                )
        return actions

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        review_id = str(task.payload.get("review_id", ""))
        if task.risk == ActionRisk.HUMAN:
            return ActionResult(
                task_id=task.task_id,
                status=task.status,
                user_text="Передал человеку: негативный отзыв нельзя отправлять автоматически.",
                audit_event={
                    "tenant_id": ctx.tenant_id,
                    "user_id": ctx.user_id,
                    "module": self.module_id.value,
                    "task_id": task.task_id,
                    "review_id": review_id,
                    "action": "review_escalated",
                },
            )

        review = next(item for item in await replay.reviews() if item.review_id == review_id)
        draft = await ReviewDraftService(LlmRouter(get_settings())).draft_positive_answer(review)
        send_result = await replay.send_review_answer(review_id, draft.answer)
        operation_id, operation_payload = _review_answer_operation(review, draft.answer)
        operation_result = await replay.execute_marketplace_operation(
            operation_id,
            operation_payload,
            platform=review.platform,
            idempotency_key=f"{task.task_id}:{operation_id}",
        )
        return ActionResult(
            task_id=task.task_id,
            status=task.status,
            user_text=(
                "Готово. Ответ на отзыв подготовлен, записан "
                "и собран в безопасный план отправки."
            ),
            audit_event={
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "module": self.module_id.value,
                "task_id": task.task_id,
                "review_id": review_id,
                "action": "review_answer_sent",
                "llm_model": draft.model,
                "llm_used_fallback": draft.used_fallback,
                "llm_tokens_estimate": draft.tokens_estimate,
                "connector_status": send_result["status"],
                "operation_id": operation_id,
                "marketplace_operation": operation_result,
            },
        )


def _review_answer_operation(review, answer: str) -> tuple[str, dict[str, object]]:
    if review.platform == Platform.WB:
        return wb_question_answer(question_id=review.review_id, text=answer)
    return ozon_review_answer(review_id=review.review_id, text=answer)


class CompetitorsModule(OperatorModule):
    module_id = ModuleId.COMPETITORS
    title = "Конкуренты"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Проверить конкурентов",
                "Публичные цены обновлены в replay-режиме.",
                "Показать",
                35,
                ActionRisk.SAFE,
                money_effect=350,
                urgency=0.2,
                confidence=0.55,
                hijack_watch=True,
            )
        ]


class RepricerModule(OperatorModule):
    module_id = ModuleId.REPRICER
    title = "Репрайс"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        product = next(
            (item for item in products if item.platform == Platform.OZON),
            min(products, key=lambda item: item.stock),
        )
        plan = reprice_plan(product, competitor_price=product.price * 0.97)
        return [
            _action(
                self.module_id,
                "Цена под вопросом",
                f"{product.name}: новая цена будет только после ОК.",
                "Проверить цену",
                65,
                ActionRisk.CONFIRM,
                money_effect=reprice_money_effect(product, plan),
                urgency=0.5,
                confidence=0.62,
                sku=product.sku,
                platform=Platform.YANDEX.value,
                current_price=plan.current_price,
                target_price=plan.target_price,
                hard_floor=plan.floor_price,
                expected_margin=plan.expected_margin,
                game_theory_mode="hold_margin",
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        platform = Platform(str(task.payload.get("platform") or Platform.OZON.value))
        operation_id, payload = _price_update_operation(
            platform,
            sku=str(task.payload.get("sku") or ""),
            price=float(task.payload.get("target_price") or 0),
        )
        operation_result = await replay.execute_marketplace_operation(
            operation_id,
            payload,
            platform=platform,
            idempotency_key=f"{task.task_id}:{operation_id}",
        )
        return ActionResult(
            task_id=task.task_id,
            status=task.status,
            user_text="Готово. Новая цена собрана в безопасный план и ждёт live-режима кабинета.",
            audit_event={
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "module": self.module_id.value,
                "task_id": task.task_id,
                "action": "price_update_planned",
                "operation_id": operation_id,
                "sku": task.payload.get("sku"),
                "target_price": task.payload.get("target_price"),
                "marketplace_operation": operation_result,
            },
        )


def _price_update_operation(
    platform: Platform,
    *,
    sku: str,
    price: float,
) -> tuple[str, dict[str, object]]:
    if platform == Platform.WB:
        return wb_price_upload(vendor_code=sku, price=price)
    return ozon_price_import(offer_id=sku, price=price)


class FinanceModule(OperatorModule):
    module_id = ModuleId.FINANCE
    title = "Финмонитор"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Сверить удержание",
                "Replay нашел расхождение 430 ₽. Подготовить спор?",
                "Подготовить",
                55,
                ActionRisk.HUMAN,
                money_effect=430,
                urgency=0.6,
                confidence=0.7,
                deadline_at=datetime.now(UTC) + timedelta(days=2),
                amount=430,
                fifo_batch="replay-batch-7",
            )
        ]


class AntifraudModule(OperatorModule):
    module_id = ModuleId.ANTIFRAUD
    title = "Антифрод"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Риск возврата",
                "Проверь при клиенте: возможна подмена у дорогого товара.",
                "Показать",
                60,
                ActionRisk.HUMAN,
            )
        ]


class ForecastModule(OperatorModule):
    module_id = ModuleId.FORECAST
    title = "Прогноз запасов"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        product = min(await replay.products(), key=lambda p: p.stock)
        quantity = reorder_quantity(product)
        distribution = warehouse_distribution(quantity, localization_index=0.72)
        return [
            _action(
                self.module_id,
                "Пора пополнить",
                f"{product.name}: остатка мало. Заказать {quantity} шт?",
                "Собрать",
                80,
                ActionRisk.CONFIRM,
                money_effect=forecast_money_effect(product, quantity),
                urgency=0.75,
                confidence=0.72,
                sku=product.sku,
                quantity=quantity,
                warehouse_distribution=distribution,
            )
        ]


class PvzModule(OperatorModule):
    module_id = ModuleId.PVZ
    title = "ПВЗ"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        actions: list[TaskAction] = []
        for point in (await replay.pvz_points())[:3]:
            employees = list(point.employees)
            if len(employees) < 2:
                actions.append(
                    _action(
                        self.module_id,
                        "Не хватает людей в ПВЗ",
                        f"{point.title}: для графика 2/2 нужны минимум два сотрудника.",
                        "Проверить штат",
                        88,
                        ActionRisk.HUMAN,
                        point_id=point.point_id,
                        point_title=point.title,
                        employees=len(employees),
                    )
                )
                continue
            names = [employee.name for employee in employees]
            schedule = build_two_two_schedule(names, days=14)
            payroll = calculate_payroll_by_rate(
                schedule,
                hourly_rates={employee.name: employee.hourly_rate for employee in employees},
                hours_per_shift=12,
            )
            actions.append(
                _action(
                    self.module_id,
                    "График ПВЗ готов",
                    (
                        f"{point.title}: график 2/2 на 14 дней готов. "
                        f"ЗП по сменам: {int(sum(payroll.values()))} ₽."
                    ),
                    "Утвердить",
                    86,
                    ActionRisk.CONFIRM,
                    point_id=point.point_id,
                    point_title=point.title,
                    monthly_turnover=point.monthly_turnover,
                    schedule=schedule,
                    payroll=payroll,
                )
            )
        return actions


class RulesModule(OperatorModule):
    module_id = ModuleId.RULES
    title = "Радар правил"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Проверить тариф",
                "Есть черновик изменения тарифа. Пересчитать маржу?",
                "Пересчитать",
                74,
                ActionRisk.CONFIRM,
            )
        ]


class AccountingModule(OperatorModule):
    module_id = ModuleId.ACCOUNTING
    title = "Касса и учет"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Сводка для учета",
                "Сводка операций ПВЗ готова для бухгалтера.",
                "Скачать",
                30,
                ActionRisk.SAFE,
            )
        ]


class BillingModule(OperatorModule):
    module_id = ModuleId.BILLING
    title = "Оплата"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Использование модулей",
                "Сегодня работали 6 модулей. Оплата в пилоте отключена.",
                "Показать",
                20,
                ActionRisk.SAFE,
            )
        ]


class SupervisorModule(OperatorModule):
    module_id = ModuleId.SUPERVISOR
    title = "ИИ-надзиратель"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Проверка безопасности",
                "Лимиты и секреты проверены. Утечек в replay нет.",
                "Открыть",
                95,
                ActionRisk.SAFE,
            )
        ]


class LearningModule(OperatorModule):
    module_id = ModuleId.LEARNING
    title = "Обучение"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Учесть оценки",
                "Можно оценить ответы, чтобы я писал точнее.",
                "Оценить",
                25,
                ActionRisk.SAFE,
            )
        ]


class RadarModule(OperatorModule):
    module_id = ModuleId.RADAR
    title = "Новинки"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Свежие изменения",
                "Найдено 4 свежих источника GitHub/Habr. Добавить в знания?",
                "Показать",
                45,
                ActionRisk.CONFIRM,
                money_effect=500,
                urgency=0.3,
                confidence=0.6,
            )
        ]


class AdsModule(OperatorModule):
    module_id = ModuleId.ADS
    title = "Реклама"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        product = next((item for item in products if item.platform == Platform.YANDEX), products[0])
        bid = ad_bid_plan(
            product,
            bid_before=120,
            target_drr=0.18,
            localization_index=0.74,
        )
        return [
            _action(
                self.module_id,
                "Ставка съедает бюджет",
                "По ключу растут расходы. Я подготовил снижение ставки в рамках лимита.",
                "Проверить ставку",
                84,
                ActionRisk.CONFIRM,
                money_effect=ad_savings_effect(bid),
                urgency=0.8,
                confidence=0.58,
                sku=product.sku,
                platform=product.platform.value,
                target_drr=0.18,
                bid_before=bid.bid_before,
                bid_after=bid.bid_after,
                expected_drr=bid.expected_drr,
                conversion_probability=bid.conversion_probability,
                localization_index=bid.localization_index,
                campaign_id="dry-run-campaign",
                needs_api_verification=True,
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        platform = Platform(str(task.payload.get("platform") or Platform.YANDEX.value))
        operation_id, payload = _ads_bid_operation(
            platform,
            sku=str(task.payload.get("sku") or ""),
            bid=int(task.payload.get("bid_after") or 0),
            campaign_id=str(task.payload.get("campaign_id") or "dry-run-campaign"),
        )
        operation_result = await replay.execute_marketplace_operation(
            operation_id,
            payload,
            platform=platform,
            idempotency_key=f"{task.task_id}:{operation_id}",
        )
        return ActionResult(
            task_id=task.task_id,
            status=task.status,
            user_text="Готово. Ставка собрана в безопасный план обновления через кабинет.",
            audit_event={
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "module": self.module_id.value,
                "task_id": task.task_id,
                "action": "ads_bid_update_planned",
                "operation_id": operation_id,
                "sku": task.payload.get("sku"),
                "bid_before": task.payload.get("bid_before"),
                "bid_after": task.payload.get("bid_after"),
                "expected_drr": task.payload.get("expected_drr"),
                "marketplace_operation": operation_result,
            },
        )


def _ads_bid_operation(
    platform: Platform,
    *,
    sku: str,
    bid: int,
    campaign_id: str,
) -> tuple[str, dict[str, object]]:
    if platform != Platform.YANDEX:
        platform = Platform.YANDEX
    return yandex_market_bid_update(
        campaign_id=campaign_id,
        offer_id=sku,
        bid=bid,
    )


class ClaimsModule(OperatorModule):
    module_id = ModuleId.CLAIMS
    title = "Возмещения"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        candidates = sorted(
            await replay.claim_candidates(),
            key=lambda item: (item.amount, item.discovered_at),
            reverse=True,
        )
        if not candidates:
            return []
        policies = {
            (policy.platform.value, policy.claim_type): policy
            for policy in await replay.claim_deadline_policies()
        }
        actions: list[TaskAction] = []
        for candidate in candidates[:3]:
            policy = policies.get((candidate.platform.value, candidate.claim_type))
            deadline_needs_verification = policy is None
            deadline_at = (
                candidate.discovered_at + timedelta(days=policy.days)
                if policy
                else datetime.now(UTC) + timedelta(hours=18)
            )
            evidence = list(candidate.evidence) or ["отгрузка", "остатки", "финотчет"]
            amount_text = f"{candidate.amount:,.0f}".replace(",", " ")
            actions.append(
                _action(
                    self.module_id,
                    "Вернуть деньги по претензии",
                    (
                        f"Нашел {amount_text} ₽ к возврату: {candidate.reason} "
                        "Собрал черновик претензии и доказательства."
                    ),
                    "Открыть претензию",
                    91,
                    ActionRisk.HUMAN,
                    money_effect=candidate.amount,
                    urgency=0.95 if task_deadline_is_near(deadline_at) else 0.75,
                    confidence=confidence_from_inputs(
                        source_count=len(evidence),
                        has_verified_policy=policy is not None,
                    ),
                    deadline_at=deadline_at,
                    platform=candidate.platform.value,
                    sku=candidate.sku,
                    claim_id=candidate.claim_id,
                    claim_type=candidate.claim_type,
                    claim_amount=candidate.amount,
                    claim_deadline_needs_verification=deadline_needs_verification,
                    claim_deadline_days=policy.days if policy else None,
                    claim_deadline_source_url=policy.source_url if policy else "",
                    evidence=evidence,
                )
            )
        return actions


def task_deadline_is_near(deadline_at: datetime) -> bool:
    return (deadline_at - datetime.now(UTC)).total_seconds() <= 24 * 60 * 60


class NicheDiscoveryModule(OperatorModule):
    module_id = ModuleId.NICHES
    title = "Ниши"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Ниша растет",
                "Спрос растет, конкуренция умеренная. Я собрал 3 идеи товаров и поставщиков.",
                "Показать идеи",
                52,
                ActionRisk.SAFE,
                money_effect=7000,
                urgency=0.35,
                confidence=0.5,
                niche="организация кухни",
                demand_trend="растет",
                suppliers=["1688 supplier replay", "local supplier replay"],
            )
        ]


class ContentModule(OperatorModule):
    module_id = ModuleId.CONTENT
    title = "Контент карточек"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        product = (await replay.products())[0]
        return [
            _action(
                self.module_id,
                "Собрать инфографику",
                "Готово задание для сервиса контента: 5 вариантов без своего генератора картинок.",
                "Отправить в сервис",
                48,
                ActionRisk.CONFIRM,
                money_effect=1100,
                urgency=0.3,
                confidence=0.52,
                sku=product.sku,
                service_mode="external_subscription",
                image_generation_in_house=False,
            )
        ]


class AccountGuardModule(OperatorModule):
    module_id = ModuleId.ACCOUNT_GUARD
    title = "Защита аккаунта"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        return [
            _action(
                self.module_id,
                "Риск слива рекламы",
                "Похожий на скликивание всплеск. Я подготовил остановку кампании до проверки.",
                "Остановить",
                97,
                ActionRisk.CONFIRM,
                money_effect=5000,
                urgency=1.0,
                confidence=0.62,
                deadline_at=datetime.now(UTC) + timedelta(hours=4),
                platform=Platform.OZON.value,
                campaign_id="dry-run-campaign",
                risk_type="click_fraud",
                whitehat_only=True,
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        operation_result = await replay.execute_marketplace_operation(
            "Campaign_Stop",
            {"campaign_id": str(task.payload.get("campaign_id") or "dry-run-campaign")},
            platform=Platform.OZON,
            idempotency_key=f"{task.task_id}:Campaign_Stop",
        )
        return ActionResult(
            task_id=task.task_id,
            status=task.status,
            user_text=(
                "Готово. Остановка кампании собрана в безопасный план, "
                "live-запись ждёт проверенный рекламный кабинет."
            ),
            audit_event={
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "module": self.module_id.value,
                "task_id": task.task_id,
                "action": "campaign_stop_planned",
                "operation_id": "Campaign_Stop",
                "risk_type": task.payload.get("risk_type"),
                "marketplace_operation": operation_result,
            },
        )


@dataclass(frozen=True)
class ModuleRegistry:
    modules: tuple[OperatorModule, ...]

    @classmethod
    def default(cls) -> ModuleRegistry:
        return cls(
            (
                AccountsModule(),
                UnitEconomicsModule(),
                SeoModule(),
                SuppliesModule(),
                ReviewsModule(),
                CompetitorsModule(),
                RepricerModule(),
                FinanceModule(),
                AntifraudModule(),
                ForecastModule(),
                PvzModule(),
                RulesModule(),
                AccountingModule(),
                BillingModule(),
                SupervisorModule(),
                LearningModule(),
                RadarModule(),
                AdsModule(),
                ClaimsModule(),
                NicheDiscoveryModule(),
                ContentModule(),
                AccountGuardModule(),
            )
        )
