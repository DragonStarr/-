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
from operator_day.claim_deadlines import requires_owner_verification
from operator_day.config import get_settings
from operator_day.connectors.replay import ReplayHub
from operator_day.domain import (
    ActionResult,
    ActionRisk,
    ModuleId,
    Platform,
    TaskAction,
    TaskStatus,
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

_ARTIFACT_BY_MODULE = {
    ModuleId.ACCOUNTS: "catalog_summary",
    ModuleId.UNIT: "unit_economics",
    ModuleId.SEO: "seo_draft",
    ModuleId.SUPPLIES: "supply_plan",
    ModuleId.REVIEWS: "review_reply_draft",
    ModuleId.COMPETITORS: "competitor_watch",
    ModuleId.REPRICER: "repricer_plan",
    ModuleId.FINANCE: "finance_reconciliation",
    ModuleId.ANTIFRAUD: "antifraud_case",
    ModuleId.FORECAST: "forecast_plan",
    ModuleId.PVZ: "pvz_shift_plan",
    ModuleId.RULES: "rule_recalculation",
    ModuleId.ACCOUNTING: "accounting_export",
    ModuleId.BILLING: "studio_build",
    ModuleId.SUPERVISOR: "supervisor_check",
    ModuleId.LEARNING: "learning_update",
    ModuleId.RADAR: "knowledge_proposal",
    ModuleId.ADS: "ad_bid_plan",
    ModuleId.CLAIMS: "claim_draft",
    ModuleId.NICHES: "niche_snapshot",
    ModuleId.CONTENT: "content_brief",
    ModuleId.ACCOUNT_GUARD: "account_guard_case",
}


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
    payload.setdefault("artifact_type", _ARTIFACT_BY_MODULE.get(module_id, "operator_plan"))
    payload.setdefault("artifact_source", module_id.value)
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


async def _record_internal_result(
    *,
    ctx: TenantContext,
    replay: ReplayHub,
    module_id: ModuleId,
    task: TaskAction,
    action: str,
    user_text: str,
) -> ActionResult:
    artifact = await replay.record_operator_artifact(
        ctx,
        task.payload,
        module_id=module_id.value,
        task_id=task.task_id,
    )
    honest_user_text = _honest_local_text(user_text)
    status = TaskStatus.ESCALATED if task.risk == ActionRisk.HUMAN else TaskStatus.DONE
    return ActionResult(
        task_id=task.task_id,
        status=status,
        user_text=honest_user_text,
        audit_event={
            "tenant_id": ctx.tenant_id,
            "user_id": ctx.user_id,
            "module": module_id.value,
            "task_id": task.task_id,
            "payload": task.payload,
            "action": action,
            "connector_status": artifact["status"],
            "artifact": artifact,
            "marketplace_write": "not_attempted",
        },
    )


def _honest_local_text(text: str) -> str:
    normalized = text
    if normalized.startswith("Готово. "):
        normalized = "Записал. " + normalized.removeprefix("Готово. ")
    elif normalized.startswith("Готово "):
        normalized = "Записал " + normalized.removeprefix("Готово ")
    if "кабинет" not in normalized.lower() and "ЛК" not in normalized:
        normalized = f"{normalized} Внешние кабинеты не менял."
    return normalized


def _operation_result_text(
    operation_result: dict[str, object],
    *,
    live_text: str,
    planned_text: str,
) -> str:
    return live_text if operation_result.get("live") is True else planned_text


def _operation_status(operation_result: dict[str, object]) -> TaskStatus:
    return TaskStatus.DONE if operation_result.get("live") is True else TaskStatus.PLANNED


def _has_stock(product) -> bool:
    return product.stock is not None


def _record_text(record: dict, *keys: str, default: str = "") -> str:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
        if payload and payload.get(key) not in (None, ""):
            return str(payload[key])
    return default


def _record_number(record: dict, *keys: str, default: float = 0) -> float:
    raw = _record_text(record, *keys, default=str(default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _is_antifraud_event(record: dict) -> bool:
    risk_type = _record_text(record, "risk_type", "type", default="")
    severity = _record_text(record, "severity", default="info")
    return risk_type in {"substitution", "return_risk", "fraud"} or severity in {
        "high",
        "critical",
    }


class AccountsModule(OperatorModule):
    module_id = ModuleId.ACCOUNTS
    title = "Кабинеты и каталог"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        if not products:
            return [
                _action(
                    self.module_id,
                    "Подключить данные",
                    (
                        "Я пока не вижу товаров, остатков и продаж. "
                        "Подключите кабинет или загрузите импорт, и я соберу реальные дела."
                    ),
                    "Открыть кабинеты",
                    100,
                    ActionRisk.SAFE,
                    confidence=0.9,
                    missing_data=["catalog", "stocks", "sales"],
                )
            ]
        low_stock = [p for p in products if _has_stock(p) and p.stock <= 4]
        text = f"Каталог собран: {len(products)} товаров. Мало остатков: {len(low_stock)}."
        return [_action(self.module_id, "Проверить каталог", text, "Показать", 70, ActionRisk.SAFE)]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="catalog_summary_recorded",
            user_text="Готово. Сводка кабинетов и каталога записана в рабочую очередь.",
        )


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

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="unit_economics_recorded",
            user_text="Готово. Расчет маржи и точки безубыточности сохранен для проверки цены.",
        )


class SeoModule(OperatorModule):
    module_id = ModuleId.SEO
    title = "SEO карточек"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        if not products:
            return []
        product = products[0]
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

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="seo_draft_recorded",
            user_text="Готово. SEO-черновик и оценка карточки сохранены без автопубликации.",
        )


class SuppliesModule(OperatorModule):
    module_id = ModuleId.SUPPLIES
    title = "Поставки и штрихкоды"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        low_stock = [p for p in await replay.products() if _has_stock(p) and p.stock <= 4]
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

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="supply_plan_recorded",
            user_text=(
                "Готово. Черновик поставки и пополнения остатков записан; "
                "ЛК не изменялся без подтвержденного write-доступа."
            ),
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
            return await _record_internal_result(
                ctx=ctx,
                replay=replay,
                module_id=self.module_id,
                task=task,
                action="review_escalation_recorded",
                user_text=(
                    "Передал человеку: негативный отзыв нельзя отправлять автоматически. "
                    "Сохранил черновик и внешние кабинеты не менял."
                ),
            )
        review = next(item for item in await replay.reviews() if item.review_id == review_id)
        draft = await ReviewDraftService(LlmRouter(get_settings())).draft_positive_answer(review)
        operation_id, operation_payload = _review_answer_operation(review, draft.answer)
        operation_result = await replay.execute_marketplace_operation(
            operation_id,
            operation_payload,
            platform=review.platform,
            idempotency_key=f"{task.task_id}:{operation_id}",
        )
        send_result = await replay.send_review_answer(review_id, draft.answer)
        return ActionResult(
            task_id=task.task_id,
            status=_operation_status(operation_result),
            user_text=_operation_result_text(
                operation_result,
                live_text="Ответ отправлен в кабинет и записан в журнал.",
                planned_text=(
                    "Ответ подготовлен и записан в безопасный план отправки; "
                    "внешний кабинет не менял."
                ),
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
        products = await replay.products()
        if not products:
            return []
        return [
            _action(
                self.module_id,
                "Проверить конкурентов",
                (
                    f"{products[0].name}: есть карточка для проверки цены "
                    "и позиции рядом с конкурентами."
                ),
                "Показать",
                35,
                ActionRisk.SAFE,
                money_effect=350,
                urgency=0.2,
                confidence=0.55,
                hijack_watch=True,
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="competitor_watch_recorded",
            user_text=(
                "Готово. Наблюдение по конкурентам сохранено как сигнал "
                "для проверки цены и карточки."
            ),
        )


class RepricerModule(OperatorModule):
    module_id = ModuleId.REPRICER
    title = "Репрайс"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        if not products:
            return []
        product = next(
            (
                item
                for item in sorted(
                    products,
                    key=lambda item: item.stock if item.stock is not None else 10**9,
                )
                if item.platform in {Platform.OZON, Platform.WB}
            ),
            None,
        )
        if product is None:
            return []
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
                platform=product.platform.value,
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
            status=_operation_status(operation_result),
            user_text=_operation_result_text(
                operation_result,
                live_text="Новую цену отправил в кабинет и записал в журнал.",
                planned_text=(
                    "Новую цену собрал в безопасный план; внешний кабинет не менял."
                ),
            ),
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
        cash_ops = await replay.operational_records("cash_ops")
        receipts = await replay.operational_records("receipts")
        if not cash_ops and not receipts:
            return []
        cash = cash_ops[0] if cash_ops else {}
        amount = _record_number(cash, "unmatched_amount", "diff", "amount", default=430)
        return [
            _action(
                self.module_id,
                "Сверить удержание",
                f"Нашел расхождение {amount:.0f} ₽. Подготовить спор?",
                "Подготовить",
                55,
                ActionRisk.HUMAN,
                money_effect=amount,
                urgency=0.6,
                confidence=confidence_from_inputs(source_count=len(cash_ops) + len(receipts)),
                deadline_at=datetime.now(UTC) + timedelta(days=2),
                amount=amount,
                cash_operation_id=_record_text(cash, "id"),
                receipts_count=len(receipts),
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="finance_reconciliation_recorded",
            user_text="Передал человеку. Сверка удержаний и доказательства сохранены для спора.",
        )


class AntifraudModule(OperatorModule):
    module_id = ModuleId.ANTIFRAUD
    title = "Антифрод"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        incidents = await replay.operational_records("incidents")
        alerts = await replay.operational_records("alerts")
        event = next(
            (
                item
                for item in [*incidents, *alerts]
                if _is_antifraud_event(item)
            ),
            {},
        )
        if not event:
            return []
        return [
            _action(
                self.module_id,
                "Риск возврата",
                _record_text(
                    event,
                    "title",
                    default="Проверь при клиенте: возможна подмена у дорогого товара.",
                ),
                "Показать",
                60,
                ActionRisk.HUMAN,
                incident_id=_record_text(event, "id"),
                severity=_record_text(event, "severity", default="high"),
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="antifraud_case_recorded",
            user_text=(
                "Передал человеку. Антифрод-сигнал сохранен, "
                "автоматических действий с покупателем нет."
            ),
        )


class ForecastModule(OperatorModule):
    module_id = ModuleId.FORECAST
    title = "Прогноз запасов"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        if not products:
            return []
        products = [product for product in products if _has_stock(product)]
        if not products:
            return []
        product = min(products, key=lambda p: p.stock or 0)
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

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="forecast_plan_recorded",
            user_text=(
                "Готово. Прогноз пополнения и распределение по складам "
                "записаны в план поставки."
            ),
        )


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

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="pvz_shift_plan_recorded",
            user_text="Готово. График ПВЗ и расчет смен сохранены для владельца.",
        )


class RulesModule(OperatorModule):
    module_id = ModuleId.RULES
    title = "Радар правил"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        records = await replay.operational_records("rule_changes")
        if not records:
            return []
        change = records[0] if records else {}
        source_url = _record_text(change, "source_url", "url")
        affected_revenue = _record_number(change, "affected_revenue", "money_effect", "amount")
        change_title = _record_text(change, "title", "name", default="Изменился тариф площадки")
        return [
            _action(
                self.module_id,
                "Проверить тариф",
                f"{change_title}. Пересчитать цены и маржу?",
                "Пересчитать",
                74,
                ActionRisk.CONFIRM,
                money_effect=affected_revenue,
                urgency=0.66 if source_url else 0.45,
                confidence=confidence_from_inputs(
                    source_count=2 if source_url else 1,
                    has_verified_policy=bool(source_url),
                ),
                rule_change_id=_record_text(change, "id", default="pilot-rule"),
                rule_title=change_title,
                source_url=source_url,
                impact=_record_text(change, "impact", default="margin"),
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="rule_recalculation_recorded",
            user_text="Готово. Пересчёт по изменению правил записан и ждёт применения в ценах.",
        )


class AccountingModule(OperatorModule):
    module_id = ModuleId.ACCOUNTING
    title = "Касса и учет"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        cash_ops = await replay.operational_records("cash_ops")
        receipts = await replay.operational_records("receipts")
        if not cash_ops and not receipts:
            return []
        cash = cash_ops[0] if cash_ops else {}
        unmatched = _record_number(cash, "unmatched_amount", "diff", "amount")
        title = _record_text(cash, "title", default="Сводка операций ПВЗ готова")
        return [
            _action(
                self.module_id,
                "Сводка для учета",
                (
                    f"{title}. "
                    f"Несведённая сумма: {unmatched:.0f} ₽."
                    if unmatched
                    else f"{title} для бухгалтера."
                ),
                "Собрать выгрузку",
                30,
                ActionRisk.CONFIRM if unmatched else ActionRisk.SAFE,
                money_effect=unmatched,
                urgency=0.58 if unmatched else 0.2,
                confidence=confidence_from_inputs(source_count=len(cash_ops) + len(receipts)),
                cash_operation_id=_record_text(cash, "id", default="pilot-cash"),
                receipts_count=len(receipts),
                amount=_record_number(cash, "amount"),
                source=_record_text(cash, "source", default="manual"),
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="accounting_export_recorded",
            user_text="Готово. Выгрузка для учёта собрана в системе; касса и ЛК не менялись.",
        )


class BillingModule(OperatorModule):
    module_id = ModuleId.BILLING
    title = "Оплата"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        specs = await replay.operational_records("studio_specs")
        builds = await replay.operational_records("studio_builds")
        spec = specs[0] if specs else {}
        if spec:
            title = _record_text(spec, "title", default="Новая кнопка от пользователя")
            return [
                _action(
                    self.module_id,
                    "Собрать доработку",
                    f"{title}. Подготовить безопасную сборку через студию?",
                    "Собрать",
                    67,
                    ActionRisk.CONFIRM,
                    urgency=0.62,
                    confidence=confidence_from_inputs(source_count=1 + len(builds)),
                    studio_spec_id=_record_text(spec, "id", default="pilot-studio"),
                    target_module=_record_text(spec, "module_id", "moduleId", default="custom"),
                    existing_builds=len(builds),
                )
            ]
        return []

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="studio_build_recorded",
            user_text=(
                "Готово. Заявка на доработку записана "
                "как безопасная сборка без автоприменения."
            ),
        )


class SupervisorModule(OperatorModule):
    module_id = ModuleId.SUPERVISOR
    title = "ИИ-надзиратель"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        incidents = await replay.operational_records("incidents")
        alerts = await replay.operational_records("alerts")
        if not incidents and not alerts:
            return []
        incident = next(
            (
                item
                for item in [*incidents, *alerts]
                if _record_text(item, "status", default="ok") not in {"ok", "passed", "closed"}
            ),
            incidents[0] if incidents else {},
        )
        status = _record_text(incident, "status", default="ok")
        severity = _record_text(incident, "severity", default="info")
        title = _record_text(incident, "title", default="Лимиты и секреты проверены")
        return [
            _action(
                self.module_id,
                "Проверка безопасности",
                f"{title}. Статус: {status}.",
                "Проверить",
                95 if status != "ok" else 40,
                ActionRisk.HUMAN if severity in {"critical", "high"} else ActionRisk.SAFE,
                urgency=1.0 if severity in {"critical", "high"} else 0.35,
                confidence=confidence_from_inputs(source_count=len(incidents) + len(alerts)),
                incident_id=_record_text(incident, "id", default="pilot-supervisor"),
                severity=severity,
                status=status,
                source=_record_text(incident, "source", default="health"),
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="supervisor_check_recorded",
            user_text="Готово. Проверка надзора записана; критичные случаи остаются на человеке.",
        )


class LearningModule(OperatorModule):
    module_id = ModuleId.LEARNING
    title = "Обучение"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        evals = await replay.operational_records("eval_runs")
        if not evals:
            return []
        eval_row = evals[0] if evals else {}
        score = _record_number(eval_row, "score", default=0.82)
        title = _record_text(eval_row, "title", default="Проверка качества ответов")
        return [
            _action(
                self.module_id,
                "Улучшить ответы",
                f"{title}: качество {round(score * 100)}%. Обновить правило ответа?",
                "Обновить",
                25,
                ActionRisk.CONFIRM if score < 0.9 else ActionRisk.SAFE,
                urgency=0.48 if score < 0.9 else 0.2,
                confidence=confidence_from_inputs(source_count=len(evals)),
                eval_run_id=_record_text(eval_row, "id", default="pilot-eval"),
                eval_score=score,
                prompt_version=_record_text(
                    eval_row,
                    "prompt_version",
                    "promptVersion",
                    default="current",
                ),
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="learning_update_recorded",
            user_text="Готово. Обновление правила обучения записано и доступно для отката.",
        )


class RadarModule(OperatorModule):
    module_id = ModuleId.RADAR
    title = "Новинки"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        source_changes = await replay.operational_records("source_changes")
        proposals = await replay.operational_records("knowledge_proposals")
        if not source_changes and not proposals:
            return []
        change = source_changes[0] if source_changes else {}
        title = _record_text(change, "title", default="Найден свежий источник")
        return [
            _action(
                self.module_id,
                "Свежие изменения",
                f"{title}. Добавить в знания как предложение?",
                "Добавить",
                45,
                ActionRisk.CONFIRM,
                money_effect=500,
                urgency=0.3,
                confidence=confidence_from_inputs(
                    source_count=len(source_changes) + len(proposals),
                    has_verified_policy=bool(_record_text(change, "source_url", "url")),
                ),
                source_change_id=_record_text(change, "id", default="pilot-source"),
                source_url=_record_text(change, "source_url", "url"),
                proposal_count=len(proposals),
                source=_record_text(change, "source", default="github-radar"),
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="knowledge_proposal_recorded",
            user_text=(
                "Готово. Источник добавлен как предложение; "
                "автоприменение отключено до проверки."
            ),
        )


class AdsModule(OperatorModule):
    module_id = ModuleId.ADS
    title = "Реклама"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        if not products:
            return []
        product = next(
            (
                item
                for item in products
                if item.platform == Platform.YANDEX and item.data_sources.get("business_id")
            ),
            None,
        )
        if product is None:
            return []
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
                business_id=product.data_sources["business_id"],
                needs_api_verification=True,
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        platform = Platform(str(task.payload.get("platform") or Platform.YANDEX.value))
        business_id = str(task.payload.get("business_id") or "").strip()
        if not business_id:
            return ActionResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                user_text=(
                    "Не могу отправить ставку: в данных кабинета нет business ID. "
                    "Подключите рекламный кабинет и повторите проверку."
                ),
                audit_event={
                    "tenant_id": ctx.tenant_id,
                    "user_id": ctx.user_id,
                    "module": self.module_id.value,
                    "task_id": task.task_id,
                    "action": "ads_bid_update_blocked",
                    "reason": "missing_business_id",
                    "marketplace_write": "blocked",
                },
            )
        operation_id, payload = _ads_bid_operation(
            platform,
            sku=str(task.payload.get("sku") or ""),
            bid=int(task.payload.get("bid_after") or 0),
            business_id=business_id,
        )
        operation_result = await replay.execute_marketplace_operation(
            operation_id,
            payload,
            platform=platform,
            idempotency_key=f"{task.task_id}:{operation_id}",
        )
        return ActionResult(
            task_id=task.task_id,
            status=_operation_status(operation_result),
            user_text=_operation_result_text(
                operation_result,
                live_text="Ставку отправил в кабинет и записал в журнал.",
                planned_text="Ставку собрал в безопасный план; внешний кабинет не менял.",
            ),
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
    business_id: str,
) -> tuple[str, dict[str, object]]:
    if platform != Platform.YANDEX:
        platform = Platform.YANDEX
    return yandex_market_bid_update(
        business_id=business_id,
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
            deadline_needs_verification = policy is None or requires_owner_verification(policy)
            deadline_at = (
                candidate.discovered_at + timedelta(days=policy.days)
                if policy and not deadline_needs_verification
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

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="claim_draft_recorded",
            user_text=(
                "Передал человеку. Черновик претензии, сумма и доказательства "
                "сохранены; отправка в ЛК не выполнялась автоматически."
            ),
        )


def task_deadline_is_near(deadline_at: datetime) -> bool:
    return (deadline_at - datetime.now(UTC)).total_seconds() <= 24 * 60 * 60


class NicheDiscoveryModule(OperatorModule):
    module_id = ModuleId.NICHES
    title = "Ниши"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        if not products:
            return []
        product = products[0]
        return [
            _action(
                self.module_id,
                "Ниша растет",
                f"{product.name}: можно проверить соседние ниши по спросу и марже.",
                "Показать идеи",
                52,
                ActionRisk.SAFE,
                money_effect=0,
                urgency=0.35,
                confidence=0.48,
                sku=product.sku,
                niche=product.name,
                demand_trend="needs_market_research",
                suppliers=[],
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="niche_snapshot_recorded",
            user_text="Готово. Снимок ниши, спроса и идей товаров сохранен для проверки закупки.",
        )


class ContentModule(OperatorModule):
    module_id = ModuleId.CONTENT
    title = "Контент карточек"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        products = await replay.products()
        if not products:
            return []
        product = products[0]
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

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        return await _record_internal_result(
            ctx=ctx,
            replay=replay,
            module_id=self.module_id,
            task=task,
            action="content_brief_recorded",
            user_text=(
                "Готово. Задание для внешнего сервиса контента сохранено "
                "без генерации картинок внутри системы."
            ),
        )


class AccountGuardModule(OperatorModule):
    module_id = ModuleId.ACCOUNT_GUARD
    title = "Защита аккаунта"

    async def collect_actions(self, ctx: TenantContext, replay: ReplayHub) -> list[TaskAction]:
        alerts = await replay.operational_records("alerts")
        alert = next(
            (
                item
                for item in alerts
                if _record_text(item, "risk_type", "type", default="")
                in {"click_fraud", "ad_spend_spike", "campaign_risk"}
            ),
            {},
        )
        if not alert or not _record_text(alert, "campaign_id", "campaignId"):
            return []
        return [
            _action(
                self.module_id,
                "Риск слива рекламы",
                _record_text(
                    alert,
                    "title",
                    default=(
                        "Похожий на скликивание всплеск. "
                        "Я подготовил остановку кампании до проверки."
                    ),
                ),
                "Остановить",
                97,
                ActionRisk.CONFIRM,
                money_effect=5000,
                urgency=1.0,
                confidence=0.62,
                deadline_at=datetime.now(UTC) + timedelta(hours=4),
                platform=Platform.OZON.value,
                campaign_id=_record_text(alert, "campaign_id", "campaignId", default=""),
                risk_type=_record_text(alert, "risk_type", "type", default="click_fraud"),
                whitehat_only=True,
            )
        ]

    async def execute(
        self, ctx: TenantContext, task: TaskAction, replay: ReplayHub
    ) -> ActionResult:
        campaign_id = str(task.payload.get("campaign_id") or "").strip()
        if not campaign_id:
            return ActionResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                user_text=(
                    "Не могу остановить кампанию: в данных нет campaign ID. "
                    "Сначала синхронизируйте рекламный кабинет."
                ),
                audit_event={
                    "tenant_id": ctx.tenant_id,
                    "user_id": ctx.user_id,
                    "module": self.module_id.value,
                    "task_id": task.task_id,
                    "action": "campaign_stop_blocked",
                    "reason": "missing_campaign_id",
                    "marketplace_write": "blocked",
                },
            )
        operation_result = await replay.execute_marketplace_operation(
            "Campaign_Stop",
            {"campaign_id": campaign_id},
            platform=Platform.OZON,
            idempotency_key=f"{task.task_id}:Campaign_Stop",
        )
        return ActionResult(
            task_id=task.task_id,
            status=_operation_status(operation_result),
            user_text=_operation_result_text(
                operation_result,
                live_text="Кампанию остановил в рекламном кабинете и записал в журнал.",
                planned_text=(
                    "Остановку кампании собрал в безопасный план; "
                    "рекламный кабинет не менял."
                ),
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
