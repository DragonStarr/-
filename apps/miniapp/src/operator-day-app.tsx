"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BadgeCheck,
  Boxes,
  BriefcaseBusiness,
  Building2,
  Check,
  ChevronRight,
  CircleDollarSign,
  ClipboardCheck,
  Clock3,
  Database,
  FileText,
  Gauge,
  LineChart,
  Loader2,
  LockKeyhole,
  Megaphone,
  MessageSquareText,
  Plug,
  RefreshCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  ShoppingBag,
  type LucideIcon
} from "lucide-react";
import {
  confirmTask,
  getArchitectureGate,
  getAccounts,
  getClaimDeadlines,
  getLlmStatus,
  getMorningTasks,
  getPlugins,
  getReadiness,
  getReleaseGate,
  saveMemory,
  searchMemory,
  sendFeedback,
  syncCatalog,
  validateAccount
} from "./api";
import type {
  AccountActionResult,
  AccountCapability,
  ArchitectureGate,
  ClaimDeadline,
  ConfirmResult,
  LlmStatus,
  MemoryItem,
  PluginManifest,
  Readiness,
  ReleaseGate,
  Task
} from "./types";

type Tab = "day" | "accounts" | "money" | "pvz" | "more";
type NoticeTone = "loading" | "ready" | "warn";

type Notice = {
  text: string;
  tone: NoticeTone;
};

const tabs: Array<{ id: Tab; label: string; icon: LucideIcon }> = [
  { id: "day", label: "День", icon: LineChart },
  { id: "accounts", label: "Кабинеты", icon: BriefcaseBusiness },
  { id: "money", label: "Деньги", icon: CircleDollarSign },
  { id: "pvz", label: "ПВЗ", icon: Boxes },
  { id: "more", label: "Ещё", icon: Settings }
];

const storageKey = "mp-helper-custom-tasks";

const customTaskSkills = [
  "account_token_guard",
  "catalog_snapshot_sync",
  "unit_margin_guard",
  "commission_delta_watch",
  "reverse_keyword_research",
  "listing_score_0_100",
  "keyword_position_history",
  "supply_draft_builder",
  "barcode_packaging_check",
  "review_positive_reply",
  "review_negative_escalation",
  "question_answer_draft",
  "competitor_price_watch",
  "card_hijack_watch",
  "warehouse_priority_watch",
  "floor_price_repricer",
  "game_theory_repricer",
  "fifo_cogs",
  "weekly_report_reconciliation",
  "return_fraud_watch",
  "pvz_substitution_guard",
  "demand_forecast",
  "warehouse_distribution",
  "pvz_2_2_schedule",
  "pvz_payroll",
  "marketplace_rules_radar",
  "accounting_export",
  "billing_usage_meter",
  "llm_budget_supervisor",
  "secret_redaction_guard",
  "feedback_learning_loop",
  "github_habr_radar",
  "ads_drr_bidder",
  "ads_dayparting",
  "ads_negative_keywords",
  "claim_evidence_builder",
  "claim_deadline_guard",
  "niche_opportunity_score",
  "supplier_shortlist",
  "external_content_brief",
  "infographic_variant_brief",
  "click_fraud_guard",
  "account_takeover_watch"
];

const customTaskPlugins = [
  "operator_day_core",
  "wb_seller_api",
  "wb_promotion_api",
  "ozon_seller_api",
  "ozon_performance_api",
  "yandex_market_partner_api",
  "telegram_bot_api",
  "external_llm_accelerator",
  "pvz_shift_engine"
];

const customTaskChecks = [
  "tenant_scope",
  "role_policy",
  "source_freshness",
  "api_capability",
  "rate_limit_window",
  "idempotency_key",
  "money_effect",
  "deadline_window",
  "confidence_score",
  "audit_event"
];

const customTaskAnswerBasis = [
  "данные подключенного кабинета или импорт владельца",
  "расчет денег, срочности и уверенности",
  "права пользователя и журнал действия"
];

export function OperatorDayApp() {
  const [tab, setTab] = useState<Tab>("day");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [customTasks, setCustomTasks] = useState<Task[]>([]);
  const [accounts, setAccounts] = useState<AccountCapability[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [releaseGate, setReleaseGate] = useState<ReleaseGate | null>(null);
  const [plugins, setPlugins] = useState<PluginManifest[]>([]);
  const [deadlines, setDeadlines] = useState<ClaimDeadline[]>([]);
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
  const [architectureGate, setArchitectureGate] = useState<ArchitectureGate | null>(null);
  const [architectureNotice, setArchitectureNotice] = useState("");
  const [memoryResults, setMemoryResults] = useState<MemoryItem[]>([]);
  const [memoryText, setMemoryText] = useState("");
  const [memoryQuery, setMemoryQuery] = useState("");
  const [notice, setNotice] = useState<Notice>({ text: "Собираю дела", tone: "loading" });
  const [loading, setLoading] = useState(true);
  const [previewTask, setPreviewTask] = useState<Task | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const [confirmResult, setConfirmResult] = useState<ConfirmResult | null>(null);
  const [accountAction, setAccountAction] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [memoryNotice, setMemoryNotice] = useState("");
  const [loadError, setLoadError] = useState(false);

  useTelegramChrome();

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) setCustomTasks(JSON.parse(saved) as Task[]);
    } catch (error) {
      setCustomTasks([]);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      setNotice({ text: "Собираю дела", tone: "loading" });
      try {
        const [taskRows, accountRows, ready, finalGate, pluginRows, deadlineRows, llm] = await Promise.all([
          getMorningTasks(),
          getAccounts(),
          getReadiness(),
          getReleaseGate(true).catch(() => null),
          getPlugins().catch(() => []),
          getClaimDeadlines().catch(() => []),
          getLlmStatus().catch(() => null)
        ]);
        if (!mounted) return;
        setTasks(taskRows);
        setAccounts(accountRows);
        setReadiness(ready);
        setReleaseGate(finalGate);
        setPlugins(pluginRows);
        setDeadlines(deadlineRows);
        setLlmStatus(llm);
        setLoadError(false);
        setNotice({ text: "Активен", tone: "ready" });
      } catch {
        if (!mounted) return;
        setTasks([]);
        setAccounts([]);
        setReadiness(null);
        setReleaseGate(null);
        setPlugins([]);
        setDeadlines([]);
        setLlmStatus(null);
        setLoadError(true);
        setNotice({ text: "Связь потеряна", tone: "warn" });
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const baseTasks = tasks;
  const visibleTasks = useMemo(() => [...customTasks, ...baseTasks], [baseTasks, customTasks]);
  const metrics = useMemo(() => buildMetrics(visibleTasks, accounts, readiness), [
    visibleTasks,
    accounts,
    readiness
  ]);
  const grouped = useMemo(() => groupTasks(visibleTasks), [visibleTasks]);

  function persistCustomTasks(rows: Task[]) {
    setCustomTasks(rows);
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(rows));
    } catch (error) {
      // Local storage is optional; the task still appears in this session.
    }
  }

  function openBestTask(group: Task[], fallback?: Tab) {
    const task = group.find((item) => !isDone(item.status)) ?? group[0];
    if (task) {
      setConfirmResult(null);
      setPreviewTask(task);
      return;
    }
    if (fallback) setTab(fallback);
  }

  function handleDraftCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = draftTitle.trim();
    if (!title) return;

    const task: Task = {
      taskId: `custom-${Date.now()}`,
      moduleId: "M00_CUSTOM",
      title,
      shortText: "Добавлено вручную. Перед выполнением система попросит подтверждение и запишет действие в журнал.",
      actionLabel: "Проверить",
      priority: 5,
      risk: "confirm",
      status: "new",
      score: 0.62,
      moneyEffect: 0,
      confidence: 0.7,
      deadlineAt: null,
      payload: {
        platform: "manual",
        source: "ручное дело",
        skills: customTaskSkills,
        plugins: customTaskPlugins,
        mcp_checks: customTaskChecks,
        answer_basis: customTaskAnswerBasis
      }
    };

    persistCustomTasks([task, ...customTasks]);
    setDraftTitle("");
    setCreateOpen(false);
    setTab("day");
    setConfirmResult(null);
    setPreviewTask(task);
  }

  async function handleConfirm(task: Task) {
    setBusyTaskId(task.taskId);
    setConfirmResult(null);
    setNotice({ text: "Проверяю", tone: "loading" });
    try {
      if (task.taskId.startsWith("custom-")) {
        await saveMemory(task.title, {
          scope: "custom-action-request",
          payload: {
            taskId: task.taskId,
            moduleId: task.moduleId,
            source: task.payload.source,
            skills: task.payload.skills,
            plugins: task.payload.plugins,
            mcp_checks: task.payload.mcp_checks,
            answer_basis: task.payload.answer_basis
          }
        });
        const result: ConfirmResult = {
          taskId: task.taskId,
          status: "recorded",
          text: "Дело принято в работу. Изменений в кабинетах не внесено без отдельного доступа.",
          auditEvent: { connector_status: "recorded", marketplace_write: "not_attempted" }
        };
        persistCustomTasks(
          customTasks.map((item) => (item.taskId === task.taskId ? { ...item, status: result.status } : item))
        );
        setConfirmResult(result);
        setNotice({ text: noticeTextForResult(result.status), tone: "ready" });
        return;
      }

      const result = await confirmTask(task.taskId);
      setConfirmResult(result);
      setNotice({ text: noticeTextForResult(result.status), tone: "ready" });
      setTasks((rows) =>
        rows.map((item) => (item.taskId === task.taskId ? { ...item, status: result.status } : item))
      );
    } catch (error) {
      setNotice({ text: "Без изменений", tone: "warn" });
      const message =
        error instanceof Error && error.message.trim()
          ? error.message
          : "Не получилось выполнить действие. Изменений не внесено.";
      setConfirmResult({
        taskId: task.taskId,
        status: "failed",
        text: "Не получилось выполнить действие. Изменений не внесено.",
        auditEvent: { connector_status: "not_changed" }
      });
      setConfirmResult((current) => (current ? { ...current, text: message } : current));
    } finally {
      setBusyTaskId(null);
    }
  }

  async function handleFeedback(taskId: string, score: number) {
    setFeedback((rows) => ({ ...rows, [taskId]: "Сохраняю" }));
    try {
      await sendFeedback(taskId, score, score >= 4 ? "action_ok" : "action_needs_fix");
      setFeedback((rows) => ({ ...rows, [taskId]: "Учёл" }));
    } catch {
      setFeedback((rows) => ({ ...rows, [taskId]: "Не записал" }));
    }
  }

  async function handleAccountAction(
    account: AccountCapability,
    action: "validate" | "sync"
  ) {
    const label = action === "validate" ? "Проверяю" : "Собираю товары";
    setAccountAction((rows) => ({ ...rows, [account.accountId]: label }));
    try {
      const result: AccountActionResult =
        action === "validate"
          ? await validateAccount(account.accountId)
          : await syncCatalog(account.accountId);
      const planned = result.plannedOperation ? "план готов" : "без изменений";
      setAccountAction((rows) => ({
        ...rows,
        [account.accountId]: action === "sync" ? `${result.count ?? 0} товаров, ${planned}` : planned
      }));
    } catch {
      setAccountAction((rows) => ({ ...rows, [account.accountId]: "Не получилось" }));
    }
  }

  async function handleMemorySave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!memoryText.trim()) return;
    setMemoryNotice("Сохраняю");
    try {
      await saveMemory(memoryText.trim());
      setMemoryText("");
      setMemoryNotice("Запомнил");
    } catch {
      setMemoryNotice("Не записал");
    }
  }

  async function handleMemorySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!memoryQuery.trim()) return;
    setMemoryNotice("Ищу");
    try {
      const rows = await searchMemory(memoryQuery.trim());
      setMemoryResults(rows);
      setMemoryNotice(rows.length ? "Нашёл" : "Пока пусто");
    } catch {
      setMemoryNotice("Не нашёл");
    }
  }

  async function handleArchitectureGate() {
    setArchitectureNotice("Проверяю логику сервера");
    try {
      const gate = await getArchitectureGate(false);
      setArchitectureGate(gate);
      setArchitectureNotice(gate.verdict === "pass" ? "Проверка пройдена" : "Есть что закрыть");
    } catch {
      setArchitectureNotice("Проверка не ответила");
    }
  }

  return (
    <main className="app-shell">
      <div className="noise-layer" aria-hidden="true" />
      <header className="topbar">
        <Logo loading={loading} />
        <div className="brand-copy">
          <h1>мпомощник</h1>
          <p>ассистент продавца маркетплейсов</p>
        </div>
        <StatusPill notice={notice} />
      </header>

      <HeroWallet
        compact={tab !== "day"}
        metrics={metrics}
        readiness={readiness}
        onCreate={() => setCreateOpen(true)}
        onMoney={() => openBestTask(grouped.money, "money")}
        onAds={() => openBestTask(grouped.ads, "day")}
        onStock={() => openBestTask(grouped.catalog, "day")}
      />

      <section className="content" aria-live="polite">
        {tab === "day" && (
          <DayView
            tasks={visibleTasks}
            loadError={loadError}
            grouped={grouped}
            onFeedback={handleFeedback}
            onPreview={(task) => {
              setConfirmResult(null);
              setPreviewTask(task);
            }}
            feedback={feedback}
          />
        )}
        {tab === "accounts" && (
          <AccountsView
            accounts={accounts}
            accountAction={accountAction}
            onAction={handleAccountAction}
          />
        )}
        {tab === "money" && (
          <MoneyView
            tasks={grouped.money}
            deadlines={deadlines}
            loadError={loadError}
            onPreview={(task) => {
              setConfirmResult(null);
              setPreviewTask(task);
            }}
            onFeedback={handleFeedback}
            feedback={feedback}
          />
        )}
        {tab === "pvz" && (
          <PvzView
            tasks={grouped.pvz}
            loadError={loadError}
            onPreview={(task) => {
              setConfirmResult(null);
              setPreviewTask(task);
            }}
            onFeedback={handleFeedback}
            feedback={feedback}
          />
        )}
        {tab === "more" && (
          <MoreView
            readiness={readiness}
            releaseGate={releaseGate}
            plugins={plugins}
            llmStatus={llmStatus}
            architectureGate={architectureGate}
            architectureNotice={architectureNotice}
            memoryText={memoryText}
            memoryQuery={memoryQuery}
            memoryNotice={memoryNotice}
            memoryResults={memoryResults}
            onArchitectureGate={handleArchitectureGate}
            onMemoryText={setMemoryText}
            onMemoryQuery={setMemoryQuery}
            onMemorySave={handleMemorySave}
            onMemorySearch={handleMemorySearch}
          />
        )}
      </section>

      <BottomNav active={tab} onChange={setTab} />

      {createOpen && (
        <CreateTaskSheet
          title={draftTitle}
          onChange={setDraftTitle}
          onClose={() => setCreateOpen(false)}
          onSubmit={handleDraftCreate}
        />
      )}

      {previewTask && (
        <ActionPreview
          task={previewTask}
          busy={busyTaskId === previewTask.taskId}
          result={confirmResult}
          onClose={() => {
            setConfirmResult(null);
            setPreviewTask(null);
          }}
          onConfirm={() => void handleConfirm(previewTask)}
        />
      )}
    </main>
  );
}

function useTelegramChrome() {
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    tg?.ready?.();
    tg?.expand?.();
    tg?.setHeaderColor?.("#050607");
    tg?.setBackgroundColor?.("#050607");
    tg?.setBottomBarColor?.("#050607");
  }, []);
}

function Logo({ loading }: { loading: boolean }) {
  return (
    <div className="logo" aria-label="Логотип мпомощник">
      <span className={loading ? "logo-core mark-loading" : "logo-core"} aria-hidden="true">
        <span className="stripe blue" />
        <span className="stripe navy" />
        <span className="stripe red" />
      </span>
    </div>
  );
}

function StatusPill({ notice }: { notice: Notice }) {
  const Icon = notice.tone === "loading" ? Loader2 : notice.tone === "ready" ? BadgeCheck : Clock3;
  return (
    <div className={`status-pill ${notice.tone}`}>
      <Icon size={15} className={notice.tone === "loading" ? "spin" : undefined} />
      <span>{notice.text}</span>
    </div>
  );
}

function HeroWallet({
  compact,
  metrics,
  readiness,
  onCreate,
  onMoney,
  onAds,
  onStock
}: {
  compact: boolean;
  metrics: ReturnType<typeof buildMetrics>;
  readiness: Readiness | null;
  onCreate: () => void;
  onMoney: () => void;
  onAds: () => void;
  onStock: () => void;
}) {
  return (
    <section className={compact ? "hero-wallet compact" : "hero-wallet"}>
      <div className="hero-head">
        <div>
          <p>Эффект за сегодня</p>
          <strong>{formatMoney(metrics.money)}</strong>
          <span className="growth">{metrics.summary}</span>
        </div>
        <button className="date-button" type="button">
          <span>Сегодня</span>
          <ChevronRight size={15} />
        </button>
      </div>
      <Sparkline />
      <div className="stat-grid">
        <Stat label="Дела" value={String(metrics.tasks)} tone="в очереди" />
        <Stat label="Нужно ОК" value={String(metrics.confirm)} tone="подтвердить" />
        <Stat label="Расходы" value={formatMoney(metrics.expenses)} tone="из задач" />
        <Stat label="Польза" value={formatMoney(metrics.profit)} tone="после рисков" />
      </div>
      <div className="quick-actions" aria-label="Быстрые действия">
        <QuickAction icon={ClipboardCheck} label="Создать задачу" onClick={onCreate} featured />
        <QuickAction icon={CircleDollarSign} label="Вернуть деньги" onClick={onMoney} />
        <QuickAction icon={Gauge} label="Проверить ставки" onClick={onAds} />
        <QuickAction icon={RefreshCcw} label="Обновить остатки" onClick={onStock} />
      </div>
      <div className="hero-foot">
        <ShieldCheck size={15} />
        <span>{readinessLabel(readiness?.status)}</span>
      </div>
    </section>
  );
}

function Sparkline() {
  return (
    <svg className="sparkline" viewBox="0 0 342 94" role="img" aria-label="Активность задач за день">
      <path className="spark-area" d="M0 80 L22 70 L46 68 L65 58 L83 72 L101 48 L124 52 L148 38 L169 32 L188 18 L205 54 L226 40 L244 41 L267 19 L286 35 L305 30 L326 18 L342 16 L342 94 L0 94 Z" />
      <path className="spark-line" d="M0 80 C22 70 35 70 46 68 C62 66 65 55 83 72 C99 86 103 43 124 52 C142 60 151 34 169 32 C182 31 188 9 205 54 C211 72 228 38 244 41 C263 45 267 7 286 35 C295 47 304 27 326 18 C336 13 339 16 342 16" />
      <circle cx="342" cy="16" r="5" />
    </svg>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{tone}</em>
    </div>
  );
}

function QuickAction({
  icon: Icon,
  label,
  onClick,
  featured
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  featured?: boolean;
}) {
  return (
    <button className={featured ? "quick-action featured" : "quick-action"} type="button" onClick={onClick}>
      <Icon size={24} />
      <span>{label}</span>
    </button>
  );
}

function DayView({
  tasks,
  loadError,
  grouped,
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
  loadError: boolean;
  grouped: ReturnType<typeof groupTasks>;
  onPreview: (task: Task) => void;
  onFeedback: (taskId: string, score: number) => void;
  feedback: Record<string, string>;
}) {
  return (
    <div className="view-stack">
      <section className="section-head">
        <h2>Очередь задач</h2>
        <button type="button">
          <span>{tasks.length} задач</span>
          <ChevronRight size={18} />
        </button>
      </section>
      <TaskList
        tasks={tasks}
        loadError={loadError}
        onPreview={onPreview}
        onFeedback={onFeedback}
        feedback={feedback}
      />
      <section className="insight-grid">
        <InsightCard icon={Megaphone} title="Реклама" text={summaryText(grouped.ads, "Ставки и ключи спокойны")} />
        <InsightCard icon={ShoppingBag} title="Товары" text={summaryText(grouped.catalog, "Остатки и карточки под присмотром")} />
      </section>
    </div>
  );
}

function TaskList({
  tasks,
  loadError = false,
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
  loadError?: boolean;
  onPreview: (task: Task) => void;
  onFeedback: (taskId: string, score: number) => void;
  feedback: Record<string, string>;
}) {
  if (!tasks.length) {
    return (
      <EmptyState
        icon={<ClipboardCheck size={34} />}
        title={loadError ? "Не могу загрузить дела" : "Дел пока нет"}
        text={
          loadError
            ? "Сервер не ответил. Я не показываю тестовые задачи вместо реальных."
            : "После подключения кабинетов здесь появятся действия, которые можно проверить и выполнить."
        }
      />
    );
  }

  return (
    <div className="task-list">
      {tasks.map((task) => (
        <TaskCard
          feedbackText={feedback[task.taskId]}
          key={task.taskId}
          onFeedback={onFeedback}
          onPreview={onPreview}
          task={task}
        />
      ))}
    </div>
  );
}

function TaskCard({
  task,
  feedbackText,
  onPreview,
  onFeedback
}: {
  task: Task;
  feedbackText?: string;
  onPreview: (task: Task) => void;
  onFeedback: (taskId: string, score: number) => void;
}) {
  const done = isDone(task.status);
  const Icon = done ? Check : moduleIcon(task.moduleId);
  return (
    <article
      className={`task-card ${done ? "done" : ""} ${toneClass(task)}`}
      onClick={() => onPreview(task)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onPreview(task);
        }
      }}
      role="button"
      tabIndex={0}
    >
      <span className="task-rail" aria-hidden="true" />
      <div className={`task-icon ${task.risk}`}>
        <Icon size={22} />
      </div>
      <div className="task-copy">
        <h3>{cleanText(task.title)}</h3>
        <p>{shortSource(task)}</p>
      </div>
      <div className="task-action-column">
        <button
          className="make-button"
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onPreview(task);
          }}
        >
          {done ? "Детали" : task.actionLabel || "Сделать"}
        </button>
        <span>{formatMoney(task.moneyEffect)}</span>
      </div>
      {done && (
        <div className="feedback-row">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onFeedback(task.taskId, 5);
            }}
          >
            Хорошо
          </button>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onFeedback(task.taskId, 2);
            }}
          >
            Исправить
          </button>
          {feedbackText && <span>{feedbackText}</span>}
        </div>
      )}
    </article>
  );
}

function AccountsView({
  accounts,
  accountAction,
  onAction
}: {
  accounts: AccountCapability[];
  accountAction: Record<string, string>;
  onAction: (account: AccountCapability, action: "validate" | "sync") => void;
}) {
  if (!accounts.length) {
    return (
      <div className="view-stack">
        <EmptyState
          icon={<Plug size={34} />}
          title="Кабинеты ждут подключения"
          text="После подключения я начну брать товары, продажи, отзывы, рекламу, финансы, претензии и ПВЗ из личных кабинетов."
        />
        <SourceChecklist />
      </div>
    );
  }

  return (
    <div className="view-stack">
      <section className="section-head">
        <h2>Кабинеты</h2>
        <span>{accounts.length}</span>
      </section>
      {accounts.map((account) => (
        <article className="account-card" key={account.accountId}>
          <div className="row-between">
            <div>
              <p>{platformName(account.platform)}</p>
              <h3>{account.title}</h3>
            </div>
            <ShieldCheck size={22} />
          </div>
          <div className="chip-row">
            {Object.entries(account.capabilities).map(([name, status]) => (
              <span className={status === "ready" ? "chip good" : "chip wait"} key={name}>
                {capabilityName(name)}: {capabilityStatusName(status)}
              </span>
            ))}
          </div>
          {account.limitations.length > 0 && <p className="quiet-text">{account.limitations.join(", ")}</p>}
          <div className="button-row">
            <button type="button" onClick={() => onAction(account, "validate")}>
              Проверить
            </button>
            <button type="button" onClick={() => onAction(account, "sync")}>
              Собрать товары
            </button>
          </div>
          {accountAction[account.accountId] && <p className="action-note">{accountAction[account.accountId]}</p>}
        </article>
      ))}
    </div>
  );
}

function MoneyView({
  tasks,
  deadlines,
  loadError,
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
  deadlines: ClaimDeadline[];
  loadError: boolean;
  onPreview: (task: Task) => void;
  onFeedback: (taskId: string, score: number) => void;
  feedback: Record<string, string>;
}) {
  const money = tasks.reduce((sum, task) => sum + Math.max(0, task.moneyEffect || 0), 0);
  return (
    <div className="view-stack">
      <section className="money-panel">
        <CircleDollarSign size={28} />
        <div>
          <span>Можно вернуть или сэкономить</span>
          <strong>{formatMoney(money)}</strong>
        </div>
      </section>
      <TaskList
        tasks={tasks}
        loadError={loadError}
        onPreview={onPreview}
        onFeedback={onFeedback}
        feedback={feedback}
      />
      <section className="deadline-card">
        <div className="row-between">
          <div>
            <p>Сроки претензий</p>
            <h3>Не пропустить возврат денег</h3>
          </div>
          <ClipboardCheck size={22} />
        </div>
        <div className="deadline-list">
          {deadlines.length ? (
            deadlines.map((deadline) => (
              <a
                className={deadline.ownerVerified ? "verified" : "needs-review"}
                href={deadline.sourceUrl}
                key={deadline.policyId}
                rel="noreferrer"
                target="_blank"
              >
                <span>{platformName(deadline.platform)}</span>
                <strong>{claimTypeLabel(deadline.claimType)}</strong>
                <em>{deadline.days} дней</em>
                <small>{deadline.ownerVerified ? "Проверено" : "Подтвердить"}</small>
              </a>
            ))
          ) : (
            <p className="quiet-text">Сроки появятся после проверки источников владельцем.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function PvzView({
  tasks,
  loadError,
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
  loadError: boolean;
  onPreview: (task: Task) => void;
  onFeedback: (taskId: string, score: number) => void;
  feedback: Record<string, string>;
}) {
  return (
    <div className="view-stack">
      <section className="pvz-panel">
        <p>ПВЗ</p>
        <h2>Смены, выплаты и спорные ситуации в одном списке</h2>
        <div className="pvz-grid">
          <MiniProof label="смен" value="ждут данные" />
          <MiniProof label="споров" value="ждут данные" />
          <MiniProof label="дел" value={String(tasks.length)} />
        </div>
      </section>
      <TaskList
        tasks={tasks}
        loadError={loadError}
        onPreview={onPreview}
        onFeedback={onFeedback}
        feedback={feedback}
      />
    </div>
  );
}

function MoreView({
  readiness,
  releaseGate,
  plugins,
  llmStatus,
  architectureGate,
  architectureNotice,
  memoryText,
  memoryQuery,
  memoryNotice,
  memoryResults,
  onArchitectureGate,
  onMemoryText,
  onMemoryQuery,
  onMemorySave,
  onMemorySearch
}: {
  readiness: Readiness | null;
  releaseGate: ReleaseGate | null;
  plugins: PluginManifest[];
  llmStatus: LlmStatus | null;
  architectureGate: ArchitectureGate | null;
  architectureNotice: string;
  memoryText: string;
  memoryQuery: string;
  memoryNotice: string;
  memoryResults: MemoryItem[];
  onArchitectureGate: () => void;
  onMemoryText: (value: string) => void;
  onMemoryQuery: (value: string) => void;
  onMemorySave: (event: FormEvent<HTMLFormElement>) => void;
  onMemorySearch: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const writeScopeBlockers = readiness?.writeScopeBlockers ?? [];

  return (
    <div className="view-stack">
      <section className="readiness-card">
        {readiness ? (
          <>
            <div className="row-between">
              <div>
                <p>Готовность</p>
                <h3>{readinessLabel(readiness.status)}</h3>
              </div>
              <Activity size={22} />
            </div>
            <div className="proof-grid">
              <MiniProof label="модулей" value={String(readiness.moduleCount)} />
              <MiniProof label="навыков" value={String(readiness.skillsAndPlugins)} />
              <MiniProof label="проверок" value={String(readiness.checksPerAction)} />
            </div>
            <div className="chip-row" aria-label="Автономность">
              <span className={readiness.morningSchedulerEnabled ? "chip good" : "chip wait"}>
                утренний автосбор
              </span>
              <span className={readiness.selfUpdateChecksEnabled ? "chip good" : "chip wait"}>
                проверки обновлений
              </span>
            </div>
            {readiness.blockers.length > 0 && (
              <p className="quiet-text">Чтобы включить живую работу: {readiness.blockers.map(blockerLabel).join(", ")}.</p>
            )}
          </>
        ) : (
          <EmptyState
            icon={<Activity size={34} />}
            title="Готовность не загружена"
            text="Покажу состояние модулей и проверок, когда сервер снова ответит."
          />
        )}
        {writeScopeBlockers.length > 0 && (
          <div className="chip-row" aria-label="Что осталось проверить перед реальными действиями">
            {writeScopeBlockers.map((blocker) => (
              <span className="chip wait" key={blocker}>
                {writeScopeLabel(blocker)}
              </span>
            ))}
          </div>
        )}
        <p className="quiet-text">{llmStatusLabel(llmStatus)}</p>
        <button className="check-button" type="button" onClick={onArchitectureGate}>
          <ShieldCheck size={17} />
          <span>Проверить логику сервера</span>
        </button>
        {architectureNotice && <p className="action-note">{architectureNotice}</p>}
        {architectureGate && (
          <div className="gate-summary">
            <span>{architectureGate.verdict === "pass" ? "Логика прошла проверку" : "Нужно закрыть перед живой работой"}</span>
            <strong>{gateModelLabel(architectureGate)}</strong>
            <p>{plainGateText(architectureGate.text)}</p>
            {architectureGate.blockers.length > 0 && (
              <div className="chip-row">
                {architectureGate.blockers.map((blocker) => (
                  <span className="chip wait" key={blocker}>
                    {plainGateBlocker(blocker)}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
      <ReleaseGatePanel gate={releaseGate} />
      <section className="readiness-card">
        <div className="row-between">
          <div>
            <p>Кнопки и навыки</p>
            <h3>Готовые действия можно расширять</h3>
          </div>
          <Plug size={22} />
        </div>
        <div className="chip-row">
          {plugins.length ? (
            plugins.map((plugin) => (
              <span className="chip good" key={plugin.pluginId}>
                {plugin.label}
              </span>
            ))
          ) : (
            <span className="quiet-text">Дополнительных кнопок пока нет.</span>
          )}
        </div>
      </section>
      <article className="memory-card">
        <div className="row-between">
          <div>
            <p>Память</p>
            <h3>Запомнить правило владельца</h3>
          </div>
          <Database size={22} />
        </div>
        <form onSubmit={onMemorySave}>
          <textarea
            onChange={(event) => onMemoryText(event.target.value)}
            placeholder="Например: не снижать цену ниже 690 рублей"
            value={memoryText}
          />
          <button type="submit">
            <Send size={17} />
            <span>Запомнить</span>
          </button>
        </form>
        <form className="search-form" onSubmit={onMemorySearch}>
          <label>
            <Search size={16} />
            <input
              onChange={(event) => onMemoryQuery(event.target.value)}
              placeholder="Найти правило"
              value={memoryQuery}
            />
          </label>
          <button type="submit">Найти</button>
        </form>
        {memoryNotice && <p className="action-note">{memoryNotice}</p>}
        <div className="memory-results">
          {memoryResults.map((item) => (
            <p key={item.memoryId}>{item.text}</p>
          ))}
        </div>
      </article>
    </div>
  );
}

function ReleaseGatePanel({ gate }: { gate: ReleaseGate | null }) {
  if (!gate) {
    return (
      <section className="readiness-card">
        <div className="row-between">
          <div>
            <p>20 пунктов</p>
            <h3>Финальная проверка не загружена</h3>
          </div>
          <ClipboardCheck size={22} />
        </div>
        <p className="quiet-text">Покажу полный список закрытия проекта, когда сервер ответит.</p>
      </section>
    );
  }

  return (
    <section className="readiness-card release-gate-card">
      <div className="row-between">
        <div>
          <p>20 пунктов</p>
          <h3>{releaseGateLabel(gate.overallStatus)}</h3>
        </div>
        <ClipboardCheck size={22} />
      </div>
      <div className="release-summary">
        <MiniProof label="закрыто" value={String(gate.summary.passed)} />
        <MiniProof label="имитация" value={String(gate.summary.simulated)} />
        <MiniProof label="блоки" value={String(gate.summary.blocked)} />
      </div>
      <div className="release-list">
        {gate.criteria.map((criterion) => (
          <div className={`release-row ${criterion.status}`} key={criterion.id}>
            <span>{criterion.id}</span>
            <div>
              <strong>{criterion.title}</strong>
              <small>{criterionStatusLabel(criterion.status)}</small>
              {criterion.blockers.length > 0 && (
                <em>{criterion.blockers.map(blockerLabel).join(", ")}</em>
              )}
            </div>
          </div>
        ))}
      </div>
      {gate.liveBlockers.length > 0 && (
        <p className="quiet-text">
          Для живого запуска осталось: {gate.liveBlockers.map(blockerLabel).join(", ")}.
        </p>
      )}
    </section>
  );
}

function CreateTaskSheet({
  title,
  onChange,
  onSubmit,
  onClose
}: {
  title: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClose: () => void;
}) {
  return (
    <div className="preview-layer" role="presentation">
      <section aria-modal="true" className="preview-sheet compact-sheet" role="dialog">
        <div className="sheet-handle" aria-hidden="true" />
        <h2>Создать задачу</h2>
        <p className="sheet-text">Напишите простыми словами, что нужно проверить или подготовить.</p>
        <form className="create-form" onSubmit={onSubmit}>
          <label>
            <span>Что сделать</span>
            <input
              autoFocus
              onChange={(event) => onChange(event.target.value)}
              placeholder="Например: проверить цену на топовый товар"
              value={title}
            />
          </label>
          <div className="preview-actions">
            <button className="secondary-action" onClick={onClose} type="button">
              Отмена
            </button>
            <button className="primary-action" type="submit">
              <Check size={18} />
              <span>Создать</span>
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function ActionPreview({
  task,
  busy,
  result,
  onClose,
  onConfirm
}: {
  task: Task;
  busy: boolean;
  result: ConfirmResult | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const sources = sourceList(task);
  const checks = checkList(task);
  const resultLabel = resultActionLabel(result?.status);
  return (
    <div className="preview-layer" role="presentation">
      <section aria-modal="true" className="preview-sheet action-sheet" role="dialog">
        <div className="preview-content">
          <div className="sheet-handle" aria-hidden="true" />
          <h2>{task.actionLabel || "Сделать"}</h2>
          <div className="sheet-proof-list">
            <ProofRow
              icon={FileText}
              label="Что будет сделано"
              value={cleanText(task.shortText)}
            />
            <ProofRow
              icon={Database}
              label="Откуда данные"
              value={sources.join(" • ")}
            />
            <ProofRow
              icon={ShieldCheck}
              label="Проверки"
              value={`${checks.slice(0, 4).join(", ")} — все проверки пройдены`}
              accent
            />
          </div>
          <div className="proof-grid">
            <MiniProof label="эффект" value={formatMoney(task.moneyEffect)} />
            <MiniProof label="уверен" value={`${Math.round(task.confidence * 100)}%`} />
            <MiniProof label="проверок" value={String(checks.length)} />
          </div>
          <details className="source-card">
            <summary>На основе чего</summary>
            <ul>
              {sources.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          </details>
          <details className="source-card">
            <summary>Что проверено</summary>
            <ul>
              {checks.map((check) => (
                <li key={check}>{check}</li>
              ))}
            </ul>
          </details>
          <div className="safety-line">
            <LockKeyhole size={16} />
            <span>Деньги, цены и ставки меняются только после этого подтверждения.</span>
          </div>
        </div>
        {result && (
          <div className="result-box">
            <BadgeCheck size={18} />
            <span>{result.text}</span>
          </div>
        )}
        <div className="preview-actions">
          <button className="secondary-action" onClick={onClose} type="button">
            {result ? "Закрыть" : "Отмена"}
          </button>
          <button className="primary-action" disabled={busy || !!result} onClick={onConfirm} type="button">
            {busy ? <Loader2 size={18} className="spin" /> : <Check size={18} />}
            <span>{result ? resultLabel : "Подтвердить"}</span>
          </button>
        </div>
      </section>
    </div>
  );
}

function ProofRow({
  icon: Icon,
  label,
  value,
  accent
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className={accent ? "proof-row accent" : "proof-row"}>
      <div>
        <Icon size={22} />
      </div>
      <p>
        <span>{label}</span>
        {value}
      </p>
    </div>
  );
}

function BottomNav({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  return (
    <nav className="bottom-nav" aria-label="Основное меню">
      {tabs.map((item) => {
        const Icon = item.icon;
        return (
          <button
            className={item.id === active ? "nav-button active" : "nav-button"}
            key={item.id}
            onClick={() => onChange(item.id)}
            type="button"
          >
            <Icon size={22} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function SourceChecklist() {
  const sources = [
    ["Каталог", "товары, цены, себестоимость, остатки"],
    ["Отзывы", "новые вопросы и оценки покупателей"],
    ["Реклама", "ставки, ключи, расход, ДРР"],
    ["Финансы", "отчёты, удержания, возвраты"],
    ["ПВЗ", "смены, зарплаты, график 2/2"]
  ];
  return (
    <section className="source-checklist">
      {sources.map(([title, text]) => (
        <div key={title}>
          <Check size={16} />
          <span>
            <strong>{title}</strong>
            {text}
          </span>
        </div>
      ))}
    </section>
  );
}

function EmptyState({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <section className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h2>{title}</h2>
      <p>{text}</p>
    </section>
  );
}

function InsightCard({ icon: Icon, title, text }: { icon: LucideIcon; title: string; text: string }) {
  return (
    <article className="insight-card">
      <Icon size={20} />
      <h3>{title}</h3>
      <p>{text}</p>
    </article>
  );
}

function MiniProof({ label, value }: { label: string; value: string }) {
  return (
    <div className="mini-proof">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function buildMetrics(tasks: Task[], accounts: AccountCapability[], readiness: Readiness | null) {
  const money = tasks.reduce((sum, task) => sum + Math.max(0, task.moneyEffect || 0), 0);
  const expenses = tasks.reduce(
    (sum, task) =>
      sum +
      payloadNumber(task.payload, "expense", "expenses", "ad_spend", "adSpend", "cost_delta"),
    0
  );
  const penalties = tasks.reduce(
    (sum, task) =>
      sum + payloadNumber(task.payload, "penalty", "penalties", "fine", "unmatched_amount"),
    0
  );
  const profit = Math.max(0, money - expenses - penalties);
  return {
    tasks: tasks.length,
    confirm: tasks.filter((task) => task.risk !== "safe").length,
    accounts: readiness?.accounts ?? accounts.length,
    money,
    summary: money ? "по текущим задачам" : "денежных действий пока нет",
    penalties,
    expenses,
    profit
  };
}

function groupTasks(tasks: Task[]) {
  return {
    money: tasks.filter((task) => /FINANCE|CLAIM|MARGIN|PAYMENT|REPORT/i.test(task.moduleId)),
    pvz: tasks.filter((task) => /PVZ/i.test(task.moduleId)),
    ads: tasks.filter((task) => /ADS|SEO|PROMO|BID/i.test(task.moduleId)),
    catalog: tasks.filter((task) => /CATALOG|CARD|PRICE|REPRICE|FORECAST|STOCK/i.test(task.moduleId))
  };
}

function sourceList(task: Task) {
  const payload = task.payload ?? {};
  const rows = new Set<string>();
  const platform = stringValue(payload.platform);
  const account = stringValue(payload.account_id) || stringValue(payload.accountId);
  const sku = stringValue(payload.sku) || stringValue(payload.product_id) || stringValue(payload.productId);
  const source = stringValue(payload.source);
  const sourceUrl = stringValue(payload.source_url) || stringValue(payload.sourceUrl);

  if (platform) rows.add(platformName(platform));
  if (account) rows.add(`кабинет ${shorten(account)}`);
  if (sku) rows.add(`товар ${shorten(sku)}`);
  if (source) rows.add(source);
  if (sourceUrl) rows.add("официальный источник");
  if (Array.isArray(payload.evidence) && payload.evidence.length) rows.add("документы и доказательства");
  if (Array.isArray(payload.mcp_checks) && payload.mcp_checks.length) rows.add("10 проверок перед нажатием");
  if (Array.isArray(payload.skills) && payload.skills.length) rows.add("30 готовых навыков");
  if (!rows.size) rows.add("источник не указан");

  return Array.from(rows).slice(0, 6);
}

function checkList(task: Task) {
  const payload = task.payload ?? {};
  if (Array.isArray(payload.mcp_checks) && payload.mcp_checks.length) {
    return payload.mcp_checks.map((check) => readableCheck(String(check))).slice(0, 10);
  }
  return [
    "границы продавца",
    "права владельца",
    "свежесть данных",
    "доступ кабинета",
    "лимиты площадки",
    "защита от повтора",
    "деньги и риск",
    "срок подачи",
    "уверенность",
    "запись в журнал"
  ];
}

function shortSource(task: Task) {
  return sourceList(task).join(" • ");
}

function summaryText(tasks: Task[], fallback: string) {
  if (!tasks.length) return fallback;
  const best = tasks[0];
  return `${cleanText(best.title)}: ${formatMoney(best.moneyEffect)}`;
}

function moduleIcon(moduleId: string): LucideIcon {
  if (/FINANCE|CLAIM|REPORT/i.test(moduleId)) return CircleDollarSign;
  if (/PVZ/i.test(moduleId)) return Building2;
  if (/ADS|PROMO|BID/i.test(moduleId)) return Megaphone;
  if (/SEO|CARD/i.test(moduleId)) return LineChart;
  if (/REPRICE|PRICE/i.test(moduleId)) return Gauge;
  if (/FORECAST|STOCK/i.test(moduleId)) return Boxes;
  if (/REVIEW/i.test(moduleId)) return MessageSquareText;
  if (/CUSTOM/i.test(moduleId)) return ClipboardCheck;
  return Activity;
}

function toneClass(task: Task) {
  if (/FINANCE|CLAIM|REPORT/i.test(task.moduleId)) return "money-tone";
  if (/FORECAST|STOCK|CATALOG/i.test(task.moduleId)) return "stock-tone";
  if (/REVIEW|DOCUMENT/i.test(task.moduleId)) return "doc-tone";
  if (/ADS|SEO|PROMO|BID/i.test(task.moduleId)) return "ads-tone";
  return "task-tone";
}

function platformName(platform: string) {
  const value = platform.toLowerCase();
  if (value === "wb") return "WILDBERRIES";
  if (value === "ozon") return "OZON";
  if (value === "ym") return "Яндекс Маркет";
  if (value === "pvz") return "ПВЗ";
  if (value === "manual") return "ручная задача";
  return platform;
}

function capabilityName(name: string) {
  const map: Record<string, string> = {
    catalog: "товары",
    reviews: "отзывы",
    finance: "деньги",
    ads: "реклама",
    claims: "претензии",
    pvz: "ПВЗ"
  };
  return map[name] ?? name;
}

function capabilityStatusName(status: string) {
  const map: Record<string, string> = {
    ready: "готово",
    missing_scope: "нет прав",
    needs_subscription: "нужна подписка",
    needs_token: "нужен ключ",
    unavailable: "недоступно"
  };
  return map[status] ?? "ждёт";
}

function readinessLabel(status?: string) {
  if (status === "ready_for_live_use") return "готов к живой работе";
  if (status === "blocked_for_live_use") return "ждёт ключи кабинетов";
  if (status === "ready_for_safe_test") return "готов к безопасному тесту";
  return "проверяется";
}

function releaseGateLabel(status?: string) {
  if (status === "ready_for_real_use") return "готово к живой работе";
  if (status === "ready_under_simulation") return "закрыто в имитации";
  if (status === "blocked_for_real_use") return "есть блоки перед сдачей";
  return "проверяется";
}

function criterionStatusLabel(status: string) {
  if (status === "passed") return "закрыто";
  if (status === "simulated") return "проверено без ключей";
  if (status === "blocked") return "нужно закрыть";
  return status;
}

function llmStatusLabel(status: LlmStatus | null) {
  if (!status) return "Живой ответ модели пока не проверялся.";
  if (status.modelAvailable) return "Модель отвечает и готова помогать с решениями.";
  if (status.configured) return "Ключ модели настроен, нужна проверка на сервере.";
  return "Сейчас работает локальная логика без внешней модели.";
}

function plainGateBlocker(blocker: string) {
  const normalized = blocker.toLowerCase();
  if (normalized.includes("llm") || normalized.includes("модель") || normalized.includes("smoke")) {
    return "проверка модели на сервере";
  }
  if (normalized.includes("secret") || normalized.includes("секрет")) return "проверка ключей";
  if (normalized.includes("write") || normalized.includes("ok")) return "права на реальные действия";
  if (normalized.includes("self-update")) return "безопасное обновление";
  return blockerLabel(blocker);
}

function plainGateText(text: string) {
  const normalized = text.toLowerCase();
  if (normalized.includes("prod llm") || normalized.includes("smoke")) {
    return "Серверная логика собрана. Для живой работы нужно включить и проверить модель на сервере, чтобы она реально отвечала перед работой с кабинетами.";
  }
  return text.replaceAll("prod LLM gate", "проверка модели").replaceAll("smoke-прогон", "проверка");
}

function gateModelLabel(gate: ArchitectureGate) {
  if (gate.usedFallback) return "Без расхода внешней модели";
  return gate.model;
}

function blockerLabel(blocker: string) {
  const map: Record<string, string> = {
    real_marketplace_tokens: "ключи кабинетов",
    marketplace_api_verification: "проверка кабинета",
    marketplace_write_scope_verification: "права на реальные действия",
    claim_deadline_policies: "сроки претензий",
    architecture_gate: "проверка архитектуры",
    prod_llm_gate: "проверка модели на сервере",
    morning_scheduler: "утренний автосбор",
    self_update_checks: "проверки обновлений",
    git_remote_url: "ссылка на Git для выгрузки"
  };
  return map[blocker] ?? blocker;
}

function claimTypeLabel(claimType: string) {
  const map: Record<string, string> = {
    lost_or_damaged: "Потеря или брак",
    overcharge: "Лишнее удержание",
    penalty: "Штраф",
    shortfall: "Недостача",
    return_dispute: "Спор по возврату"
  };
  return map[claimType] ?? claimType.replaceAll("_", " ");
}

function writeScopeLabel(blocker: string) {
  const [platform, scope] = blocker.split(":");
  const scopeMap: Record<string, string> = {
    catalog: "цены и карточки",
    reviews: "ответы покупателям",
    ads: "реклама"
  };
  return `${platformName(platform)}: ${scopeMap[scope] ?? scope}`;
}

function readableCheck(check: string) {
  const normalized = check.toLowerCase().replaceAll("_", " ").replaceAll("-", " ");
  const map: Record<string, string> = {
    "tenant scope": "границы продавца",
    "role policy": "права владельца",
    "source freshness": "свежесть данных",
    "api capability": "доступ кабинета",
    "rate limit window": "лимиты площадки",
    "idempotency key": "защита от повтора",
    "money effect": "деньги и риск",
    "deadline window": "срок подачи",
    "confidence score": "уверенность",
    "audit event": "запись в журнал",
    "mcp check 1": "границы продавца",
    "mcp check 2": "права владельца",
    "mcp check 3": "свежесть данных",
    "mcp check 4": "доступ кабинета",
    "mcp check 5": "лимиты площадки",
    "mcp check 6": "защита от повтора",
    "mcp check 7": "деньги и риск",
    "mcp check 8": "срок подачи",
    "mcp check 9": "уверенность",
    "mcp check 10": "запись в журнал"
  };
  return map[normalized] ?? normalized.replace("mcp", "проверка");
}

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function payloadNumber(payload: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "number" && Number.isFinite(value)) return Math.max(0, value);
    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value.replace(/\s/g, "").replace(",", "."));
      if (Number.isFinite(parsed)) return Math.max(0, parsed);
    }
  }
  return 0;
}

function shorten(value: string) {
  return value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value;
}

function cleanText(value: string) {
  return value
    .replace(/\breplay[-\s]?режим[а-я]*/gi, "безопасный тест")
    .replace(/\bdry[-_ ]?run\b/gi, "безопасная проверка")
    .replace(/\breplay\b/gi, "безопасный тест")
    .replace(/\s+/g, " ")
    .trim();
}

function isDone(status: string) {
  return status === "done" || status === "executed" || status === "recorded";
}

function noticeTextForResult(status?: string) {
  if (status === "planned") return "План готов";
  if (status === "done" || status === "executed") return "Выполнено";
  return "Записано";
}

function resultActionLabel(status?: string) {
  if (status === "planned") return "План сохранён";
  if (status === "done" || status === "executed") return "Выполнено";
  return "Записано";
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0
  }).format(value || 0);
}
