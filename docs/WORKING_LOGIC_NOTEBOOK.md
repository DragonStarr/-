# Рабочий блокнот логики, 2026-06-03

Источник: новое ТЗ и живой блокнот добавлений из временного RAR. Этот файл нужен, чтобы дополнения не терялись между итерациями.

## Главный вывод

Проект ведем как 23-модульный автономный продукт: M1-M18 из старого ТЗ, M19 реклама, M20 претензии, M21 ниши, M22 контент через внешние сервисы, M23 защита аккаунта. Поставка включает backend/API, Telegram-бота, Next.js Mini App/PWA, локальный LLM-шлюз, семантическую память, self-update контур, CI, backup/restore и инфраструктуру.

## Принято в реализацию

- M19 `AdsModule`: готовит изменение ставки, не пишет в API без ОК, хранит `needs_api_verification`.
- M20 `ClaimsModule`: готовит претензию и доказательства, сроки не хардкодим как истину без источника.
- M21 `NicheDiscoveryModule`: дает идеи ниш/поставщиков с confidence.
- M22 `ContentModule`: только оркестрация внешних сервисов, свой генератор изображений не пишем.
- M23 `AccountGuardModule`: белая защита от скликивания/самовыкупов, без серых схем.
- M13: ранжирование по формуле `money + urgency + risk + confidence`; дедлайн меньше 24 часов идет наверх.
- M16: бюджет LLM и token usage нужен поверх FreeModel; LiteLLM подтвержден как хороший слой бюджетов, но не обязателен для первой трассирующей пули.
- API-контекст больше не общий demo: `X-Tenant-Id`, `X-User-Id`, `X-Role` дают server-side tenant/user/role для пилота.
- Подключение кабинетов хранит только encrypted token и fingerprint; capabilities показывают, что готово, где нужны credentials, а где нужна API verification.
- Проверка кабинета отделена от подключения: `/api/accounts/{account_id}/validate` делает safe read-probe или dry-run плана; только live-успех переводит account status в `validated`.
- Каждое действие несет полный набор 30+ `skills`/`plugins`, 10 `mcp_checks` и `answer_basis`: бот обязан объяснять основу решения, а не просто предлагать кнопку.
- Подтверждение действия идемпотентно по tenant/user/task/key и пишет `action_executions`, `audit_log`, `token_usage`.
- Telegram bot создает изолированный tenant по Telegram ID и сохраняет утренние дела в БД.
- Telegram bot в разделе `Кабинеты` показывает inline-кнопки `Проверить кабинет` и `Обновить данные`; пользователь не вводит команды руками.
- Celery `operator_day.collect_morning` реально собирает и сохраняет дела, с retry/backoff.
- Добавлен `connectors.catalog`: Ozon seller/performance operations описаны через `operation_id`, endpoint, safety и rate-limit key; live-клиент должен использовать этот каталог, а не произвольные строки.
- Добавлен `connectors.transport`: HTTPX async transport, routing по host платформы/операции, path params, safety до сети, retry на 429/5xx, `Retry-After`, redaction ошибок.
- Добавлен safe dry-run для marketplace operations: write/destructive можно показать как план без сетевого вызова и без подтверждения, но реальный write по-прежнему требует `confirm_write`.
- Readiness теперь считает `marketplace_api_verification` блокером по статусу account validation, а не по всем optional capability-флагам отдельных модулей; статус разделяет `ready_for_safe_pilot`, `blocked_for_live_pilot` и `ready_for_live_pilot`.
- Добавлен `connectors.pagination`: Ozon `last_id` pagination с защитой от повторного cursor.
- Добавлен `OzonCatalogSync`: первая точка live-sync для каталога Ozon поверх transport/pagination.
- Добавлен `plan_catalog_sync_for_account`, API `/api/accounts/{account_id}/sync/catalog`, общий `sync_catalog_for_account` и Celery `operator_day.sync_catalog`: live-sync WB/Ozon/Яндекс берёт encrypted account token, расшифровывает только внутри сервиса, пишет audit без секрета.
- Live-sync каталога сохраняет строки в `products`; `DatabaseReplayHub` в API/Telegram берет tenant-данные из БД, а при пустой БД возвращает setup/empty state без подстановки фиктивных товаров.
- Добавлен owner-only `/api/catalog/import`: пилотный селлер может загрузить товары вручную, если API кабинета ещё не проверен или временно не отдаёт каталог; импорт пишет `products`, `audit_log` и сразу кормит утренние дела бота.
- Добавлен `/api/reviews/import` и DB-backed M5: отзывы и вопросы берутся из `reviews`, сохраняют платформу/source/buyer question, положительный ответ подтверждается через `confirm`, негатив остается human-only.
- Добавлены WB/Yandex операции в connector catalog на основе свежих GitHub/официальных источников.
- Добавлены source-linked `claim_deadline_policies`: сроки претензий не хардкодим, owner записывает источник.
- Добавлен `/api/claims/import` и DB-backed M20: претензии берутся из `claims`, сверяются с `claim_deadline_policies`, в payload явно пишется сумма, доказательства, источник срока и флаг `claim_deadline_needs_verification`.
- Добавлен `/api/pvz/import` и DB-backed M11: точки и сотрудники берутся из `pvz_points`/`pvz_employees`, график 2/2 и payroll считаются по индивидуальным ставкам, оператор ПВЗ не может менять штат.
- Внешние `pointId`/`employeeId` из ПВЗ-импорта не используются как глобальные primary key: внутри БД они scoped по tenant/point hash, а наружу и в задачи возвращается исходный ID. Это защищает пилот от конфликта двух владельцев с одинаковыми ID из своих ЛК/таблиц.
- Добавлен owner-only `/api/brain/architecture-review`: LLM проверяет дерево ЛК/API -> transport -> workers -> БД -> orchestrator -> Telegram.
- Добавлен owner-only `/api/brain/architecture-gate`: backend отдает machine-readable topology по ЛК/API, серверам, workers, БД, коннекторам и readiness gates; локальный LLM является базовым ревьюером, внешний провайдер запускается только при `?live=true`, ключе в env и `LLM_SMOKE_ENABLED=true`, иначе возвращается безопасный offline/fallback результат без расхода токенов.
- LLM router работает через локальный/offline режим и OpenAI-compatible внешний endpoint из env; он сверяет фактически возвращенный `model/provider`, чтобы подмена модели не считалась успешным live gate.
- Readiness учитывает `llm_architecture_gate`: live-пилот не считается готовым, пока успешный architecture gate не записан в `audit_log` как `architecture_gate_passed`.
- Добавлен owner-only `/api/brain/llm-status`: доступность модели проверяется без раскрытия ключа; live model-list smoke запускается только при `LLM_SMOKE_ENABLED=true`, чтобы не тратить лимит случайным открытием endpoint.
- Добавлен `bind_tenant_scope`: PostgreSQL-сессия выставляет `app.tenant_id` перед tenant-bound операциями, чтобы RLS политики работали не только в миграции.
- Исправлена схема: `stocks` получил `tenant_id`; Alembic initial schema теперь покрывает все ORM tables, включая `reviews`, `audit_log`, `action_executions`, `claim_deadline_policies`.
- Добавлен production guard: `APP_ENV=production` не стартует без `TOKEN_ENCRYPTION_KEY`.
- Добавлен owner-only `/api/operational-data/import`: пилотный владелец может загрузить живые строки по правилам, кассе, студии, инцидентам, оценкам и новостям, если внешний API или crawler еще не подключены. Импорт пишет tenant-scoped JSON records и audit без чужих данных.
- M12/M14/M15/M16/M17/M18 теперь DB-backed: `DatabaseReplayHub.operational_records()` берет `rule_changes`, `cash_ops`, `receipts`, `studio_specs`, `studio_builds`, `incidents`, `alerts`, `eval_runs`, `source_changes`, `knowledge_proposals`; фиктивный fallback доступен только в локальных тестах при явном `ALLOW_DEMO_FIXTURES=true`.
- M12 `RulesModule`: пересчитывает влияние правила из `rule_changes`, сохраняет `rule_versions`, показывает source URL/confidence и не применяет правило автоматически.
- M14 `AccountingModule`: сверяет `cash_ops` и `receipts`, считает несостыкованную сумму, сохраняет `receipts` как accounting export и эскалирует расхождение по деньгам.
- M15 `BillingModule`: берет пользовательскую заявку из `studio_specs`, делает безопасный sandbox build в `studio_builds`, не выкатывает новый код в прод без ревью.
- M16 `SupervisorModule`: берет `incidents` и `alerts`, поднимает critical/high случаи в утренний список, но пишет только надзорный артефакт без изменения ЛК.
- M17 `LearningModule`: берет `eval_runs`, предлагает update только при низком score, сохраняет `eval_runs` как обучающий артефакт и не превращает пользовательский текст в системную инструкцию.
- M18 `RadarModule`: берет `source_changes`, сохраняет `knowledge_proposals`, показывает источник/diff/confidence и требует человека при низком доверии.
- Readiness разделяет чтение кабинета и реальные write-действия: `/api/accounts/{account_id}/write-scopes` owner-only фиксирует подтвержденные `catalog`/`reviews`/`ads` с source URL/evidence, а `/api/readiness` возвращает `writeScopeBlockers` для Mini App простым языком.
- Telegram-бот в разделе `Кабинеты` теперь показывает те же live-блокеры простым русским: что осталось проверить по write-действиям, срокам претензий, кабинету и модели; слово `replay` пользователю не показывается.

## Проверено

- `eslazarev/wildberries-sdk`, `salacoste/ozon-daytona-seller-api`, `TelegramUI`, `StatsForecast`, `crawl4ai`, `LiteLLM`, `302_ecom_image_generator`, `seo-keyword-research-tool` существуют.
- Lazyweb-паттерны для бота: preview before confirm, one primary action, bottom navigation, task cards.
- FastAPI: `Annotated[..., Depends(...)]` и lifespan остаются актуальными.
- aiogram: callback query + inline keyboard builder/handlers актуальны.
- Celery: `autoretry_for`, `retry_backoff`, `retry_kwargs` актуальны для задач внешних API.
- Ozon Performance API: официальный help указывает новый host `api-performance.ozon.ru`; старый `performance.ozon.ru` не использовать.
- Yandex Market Partner API: bidding endpoints существуют, scope/лимиты проверять перед write.
- GitHub 2026: `PCDCK/ozon-mcp` полезен как паттерн safety/subscription/rate-limit/auto-pagination для Ozon, но не вендорится.
- GitHub 2026: `Jerardx/wildberries-mcp-server` подтверждает OpenAPI catalog, dry-run default, allow_write, rate-limit, retry/429 как полезный WB-паттерн; не вендорится.
- GitHub 2026: `yandex-market/yandex-market-partner-api` официальный repo, updated 2026-06-02; path files подтверждают bids/offer-prices/orders/returns endpoints.

## Не подтверждено полностью

- Точные WB bid endpoints/лимиты из блокнота не подтверждены быстрым поиском. Не хардкодить в live-клиент без официальной проверки.
- Ozon Performance docs доступны в поиске, но fetch вернул anti-bot/403. Методы и лимиты проверять через ЛК/доки при доступе.
- `lyagadev/ozon-seller-sdk`, `dhruvi002/demand-forecast-inventory-optimizer`, `misha345a/E-commerce_Reviews_Classifier` точным GitHub-поиском не найдены в этом прогоне.

## Правило для кода

Если источник не подтвержден, действие можно показать как черновик, но в `payload` должен быть флаг `needs_api_verification` или аналогичный. Бот не должен выдавать неподтвержденный endpoint/срок за факт.
