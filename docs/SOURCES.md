# Проверенные источники на 2026-06-04

## Официальные документы

- FastAPI lifespan/dependencies/tests: https://fastapi.tiangolo.com/advanced/events/
- HTTPX custom/mock transports and request patterns: https://www.python-httpx.org/advanced/transports/
- aiogram webhook/routers/callbacks: https://docs.aiogram.dev/en/v3.27.0/dispatcher/webhook.html
- SQLAlchemy 2 asyncio/session patterns: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- WB API portal: https://dev.wildberries.ru/en/openapi/api-information
- WB API authorization: https://dev.wildberries.ru/knowledge-base/articles/019d49a1-0d73-71e9-be3e-b2c44567470c/sistema-avtorizatsii-wb-api
- WB feedback/questions: https://dev.wildberries.ru/en/docs/openapi/user-communication
- WB MCP/OpenAPI-driven signal: https://github.com/Jerardx/wildberries-mcp-server
- Ozon Seller API: https://api-seller.ozon.ru/apiref/en/
- Ozon API help: https://docs.ozon.ru/global/en/api/
- Ozon Performance API help: https://docs.ozon.com/global/api/perfomance-api/
- Yandex Market Partner API: https://yandex.ru/dev/market/partner-api/doc/en/
- Yandex Market bids API: https://yandex.ru/dev/market/partner-api/doc/ru/reference/bids/getBidsInfoForCampaign
- Official Yandex Market Partner API repo: https://github.com/yandex-market/yandex-market-partner-api
- pgvector repository and HNSW/halfvec reference: https://github.com/pgvector/pgvector
- Next.js App Router manifest/rewrite documentation: https://nextjs.org/docs/app/api-reference/file-conventions/metadata/manifest
- Telegram UI React components: https://github.com/Telegram-Mini-Apps/TelegramUI
- Telegram Mini Apps SDK/tooling: https://github.com/Telegram-Mini-Apps/telegram-apps
- FreeModel/OpenAI-compatible model list: https://freemodel.dev/v1/models

## GitHub checks used for recommendations

- Ozon Python client candidate: `a-ulianov/OzonAPI` - fresh Python async client.
- Ozon TS SDK candidate: `salacoste/ozon-daytona-seller-api` - broad method coverage.
- WB references: `Jerardx/wildberries-mcp-server`, `Gueriero/wb_wildberries_api_swagger`, `dapi/wbcli`, `Refusned/wb-price-tracker-bot`.
- Yandex official OpenAPI repo: `yandex-market/yandex-market-partner-api`, updated on 2026-06-02 in GitHub search.
- Yandex official OpenAPI repo rechecked on 2026-06-04 through GitHub structure: repo updated/pushed on 2026-06-04 and contains `openapi/paths/v2_campaigns_campaignId_offer-prices.yaml`, `openapi/paths/v2_businesses_businessId_bids.yaml`, `openapi/paths/v2_businesses_businessId_bids_info.yaml`.
- Ozon price write endpoint rechecked on 2026-06-04 through official Ozon help/search results: `POST /v1/product/import/prices` remains the source-linked price update operation; live use still requires seller credential validation and dry-run plan first.
- WB promotion endpoints rechecked on 2026-06-04 through `dev.wildberries.ru/ru/openapi/promotion`: campaign list/count and pause paths include `/adv/v1/promotion/count` and `/adv/v0/pause`; live ad writes remain blocked until account scopes and limits are verified.
- aiogram/FastAPI references: `m-xim/aiogram-webhook`, `bralbral/fastapi_aiogram_template`.
- LLM gateway: `BerriAI/litellm`.
- Memory references: `pgvector/pgvector`, `smaramwbc/statewave`, `alibaizhanov/mengram`.
- 2026 Ozon MCP signal: `PCDCK/ozon-mcp` confirms a useful split between Seller API and Performance API, subscription-aware method access, safety classification, rate-limit metadata and auto-pagination patterns. We use this as architectural input, not as a vendored dependency.

## Habr context

- Ozon Seller API product view: https://habr.com/ru/companies/ozontech/articles/970848/
- Marketplace automation and rollback risks: https://habr.com/ru/articles/1001180/
- Marketplace repricing: https://habr.com/ru/articles/899508/
- aiogram/FastAPI webhook practice: https://habr.com/ru/companies/amvera/articles/882878/

## Design references translated into bot behavior

- Crypto wallets: preview before confirmation, one primary action, balance/risk shown before action.
- Task apps: short task list, visible status, one next step, clear done/approved state.
- Telegram bot constraints: the bot remains button-first; Mini App mirrors the same actions with bottom navigation and plain Russian labels.

## 2026-06-03 notebook verification

- Living TZ notebook now defines 23 modules: M22 content orchestration and M23 account guard were added after the earlier 21-module TZ.
- Confirmed fresh: `eslazarev/wildberries-sdk`, `salacoste/ozon-daytona-seller-api`, `telegram-mini-apps-dev/TelegramUI`, `Nixtla/statsforecast`, `unclecode/crawl4ai`, `BerriAI/litellm`, `302ai/302_ecom_image_generator`, `chukhraiartur/seo-keyword-research-tool`.
- Weak/unconfirmed exact names: `lyagadev/ozon-seller-sdk`, `dhruvi002/demand-forecast-inventory-optimizer`, `misha345a/E-commerce_Reviews_Classifier` were not found by exact GitHub repository search in this run; keep as leads until package/repo URLs are confirmed.
- WB promotion API exists officially, but exact bid endpoints/limits from the notebook were not confirmed by search in this run. Treat endpoint names as connector metadata, not hardcoded truth.
- Ozon Performance API official help says the old `performance.ozon.ru` host stopped working from 2025-01-15 and API work moved to `api-performance.ozon.ru`; account-level request limits and exact methods must still be checked from seller access before enabling live ad writes.
- Yandex Market Partner API exposes bidding flows and campaign bid info; the documented bid-info page notes access scopes and current/legacy limits, so ЯМ ads actions should validate campaign access and scope before write.
- `PCDCK/ozon-mcp` and `Jerardx/wildberries-mcp-server` independently support the same connector pattern: operation catalog, dry-run/read-write safety, rate-limit metadata, retry/429 handling and large-response discipline.
- Runtime now uses local vendored payload builders in `vendor/marketplace_sdk/`; GitHub repositories and official docs are update inputs only, not runtime dependencies.
- FlagEmbedding/BGE-M3 and OpenAI-compatible embedding APIs are used as memory architecture references; runtime keeps a local deterministic fallback so safe tests and live operation do not depend on a third-party embedding service being online.
- LangGraph durable execution patterns are used as architecture input for checkpointed action lifecycles, human confirmation and rollback hints; runtime keeps this as local lifecycle metadata until a production workflow engine is connected.
- Claim deadlines from the notebook must stay configurable and source-linked (`claim_deadlines`) until official WB/Ozon/YM rules are verified.
