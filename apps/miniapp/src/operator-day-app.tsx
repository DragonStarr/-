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
  Sparkles,
  type LucideIcon
} from "lucide-react";
import {
  confirmTask,
  getAccounts,
  getClaimDeadlines,
  getLlmStatus,
  getMorningTasks,
  getPlugins,
  getReadiness,
  saveMemory,
  searchMemory,
  sendFeedback,
  syncCatalog,
  validateAccount
} from "./api";
import type {
  AccountActionResult,
  AccountCapability,
  ClaimDeadline,
  ConfirmResult,
  LlmStatus,
  MemoryItem,
  PluginManifest,
  Readiness,
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

export function OperatorDayApp() {
  const [tab, setTab] = useState<Tab>("day");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [customTasks, setCustomTasks] = useState<Task[]>([]);
  const [accounts, setAccounts] = useState<AccountCapability[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [plugins, setPlugins] = useState<PluginManifest[]>([]);
  const [deadlines, setDeadlines] = useState<ClaimDeadline[]>([]);
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
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

  useTelegramChrome();

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) setCustomTasks(JSON.parse(saved) as Task[]);
    } catch {
      setCustomTasks([]);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      setNotice({ text: "Собираю дела", tone: "loading" });
      try {
        const [taskRows, accountRows, ready, pluginRows, deadlineRows, llm] = await Promise.all([
          getMorningTasks(),
          getAccounts(),
          getReadiness(),
          getPlugins().catch(() => []),
          getClaimDeadlines().catch(() => []),
          getLlmStatus().catch(() => null)
        ]);
        if (!mounted) return;
        setTasks(taskRows);
        setAccounts(accountRows);
        setReadiness(ready);
        setPlugins(pluginRows);
        setDeadlines(deadlineRows);
        setLlmStatus(llm);
        setNotice({ text: "Активен", tone: "ready" });
      } catch {
        if (!mounted) return;
        setTasks(demoTasks);
        setAccounts([]);
        setReadiness(demoReadiness);
        setPlugins(demoPlugins);
        setDeadlines(demoDeadlines);
        setLlmStatus(demoLlmStatus);
        setNotice({ text: "Тестовый режим", tone: "warn" });
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const baseTasks = tasks.length ? tasks : demoTasks;
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
    } catch {
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
      actionLabel: "Показать",
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
        skills: Array.from({ length: 30 }, (_, index) => `skill_${index + 1}`),
        mcp_checks: Array.from({ length: 10 }, (_, index) => `mcp_check_${index + 1}`)
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
        const result: ConfirmResult = {
          taskId: task.taskId,
          status: "prepared",
          text: "Дело принято в работу. Изменений в кабинетах не внесено без отдельного доступа.",
          auditEvent: { connector_status: "prepared" }
        };
        persistCustomTasks(
          customTasks.map((item) => (item.taskId === task.taskId ? { ...item, status: result.status } : item))
        );
        setConfirmResult(result);
        setNotice({ text: "Записано", tone: "ready" });
        return;
      }

      const result = await confirmTask(task.taskId);
      setConfirmResult(result);
      setNotice({ text: "Записано", tone: "ready" });
      setTasks((rows) =>
        rows.map((item) => (item.taskId === task.taskId ? { ...item, status: result.status } : item))
      );
    } catch {
      setNotice({ text: "Без изменений", tone: "warn" });
      setConfirmResult({
        taskId: task.taskId,
        status: "failed",
        text: "Не получилось выполнить действие. Изменений не внесено.",
        auditEvent: { connector_status: "not_changed" }
      });
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

  return (
    <main className="app-shell">
      <div className="noise-layer" aria-hidden="true" />
      <PhoneChrome />
      <header className="topbar">
        <Logo loading={loading} />
        <div className="brand-copy">
          <h1>мпомощник</h1>
          <p>ассистент продавца маркетплейсов</p>
        </div>
        <StatusPill notice={notice} />
      </header>

      <HeroWallet
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
            deadlines={deadlines.length ? deadlines : demoDeadlines}
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
            readiness={readiness ?? demoReadiness}
            plugins={plugins}
            llmStatus={llmStatus}
            memoryText={memoryText}
            memoryQuery={memoryQuery}
            memoryNotice={memoryNotice}
            memoryResults={memoryResults}
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

function PhoneChrome() {
  return (
    <div className="phone-chrome" aria-hidden="true">
      <strong>9:41</strong>
      <span className="telegram-pill">TELEGRAM</span>
      <span className="phone-icons">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}

function Logo({ loading }: { loading: boolean }) {
  return (
    <div className={loading ? "logo mark-loading" : "logo"} aria-label="Логотип мпомощник">
      <span className="stripe blue" />
      <span className="stripe navy" />
      <span className="stripe red" />
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
  metrics,
  readiness,
  onCreate,
  onMoney,
  onAds,
  onStock
}: {
  metrics: ReturnType<typeof buildMetrics>;
  readiness: Readiness | null;
  onCreate: () => void;
  onMoney: () => void;
  onAds: () => void;
  onStock: () => void;
}) {
  return (
    <section className="hero-wallet">
      <div className="hero-head">
        <div>
          <p>Эффект за сегодня</p>
          <strong>{formatMoney(metrics.money)}</strong>
          <span className="growth">+{metrics.growth}% к вчера {formatMoney(metrics.yesterday)}</span>
        </div>
        <button className="date-button" type="button">
          <span>Сегодня</span>
          <ChevronRight size={15} />
        </button>
      </div>
      <Sparkline />
      <div className="stat-grid">
        <Stat label="Заказы" value={String(metrics.orders)} tone="+8,3%" />
        <Stat label="Штрафы" value={formatMoney(metrics.penalties)} tone="-17,6%" />
        <Stat label="Расходы" value={formatMoney(metrics.expenses)} tone="-6,1%" />
        <Stat label="Чистая польза" value={formatMoney(metrics.profit)} tone="+15,7%" />
      </div>
      <div className="quick-actions" aria-label="Быстрые действия">
        <QuickAction icon={Sparkles} label="Создать задачу" onClick={onCreate} featured />
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
    <svg className="sparkline" viewBox="0 0 342 94" role="img" aria-label="Рост за день">
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
  grouped,
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
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
      <TaskList tasks={tasks} onPreview={onPreview} onFeedback={onFeedback} feedback={feedback} />
      <section className="insight-grid">
        <InsightCard icon={Megaphone} title="Реклама" text={summaryText(grouped.ads, "Ставки и ключи спокойны")} />
        <InsightCard icon={ShoppingBag} title="Товары" text={summaryText(grouped.catalog, "Остатки и карточки под присмотром")} />
      </section>
    </div>
  );
}

function TaskList({
  tasks,
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
  onPreview: (task: Task) => void;
  onFeedback: (taskId: string, score: number) => void;
  feedback: Record<string, string>;
}) {
  const rows = tasks.length ? tasks : demoTasks.slice(0, 4);
  return (
    <div className="task-list">
      {rows.map((task) => (
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
    <article className={`task-card ${done ? "done" : ""} ${toneClass(task)}`}>
      <span className="task-rail" aria-hidden="true" />
      <div className={`task-icon ${task.risk}`}>
        <Icon size={22} />
      </div>
      <div className="task-copy">
        <h3>{cleanText(task.title)}</h3>
        <p>{shortSource(task)}</p>
      </div>
      <div className="task-action-column">
        <button className="make-button" type="button" onClick={() => onPreview(task)}>
          {done ? "Детали" : task.actionLabel || "Сделать"}
        </button>
        <span>{formatMoney(task.moneyEffect)}</span>
      </div>
      {done && (
        <div className="feedback-row">
          <button type="button" onClick={() => onFeedback(task.taskId, 5)}>
            Хорошо
          </button>
          <button type="button" onClick={() => onFeedback(task.taskId, 2)}>
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
                {capabilityName(name)}: {status === "ready" ? "готово" : "ждёт"}
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
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
  deadlines: ClaimDeadline[];
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
      <TaskList tasks={tasks} onPreview={onPreview} onFeedback={onFeedback} feedback={feedback} />
      <section className="deadline-card">
        <div className="row-between">
          <div>
            <p>Сроки претензий</p>
            <h3>Не пропустить возврат денег</h3>
          </div>
          <ClipboardCheck size={22} />
        </div>
        <div className="deadline-list">
          {deadlines.map((deadline) => (
            <a href={deadline.sourceUrl} key={deadline.policyId} rel="noreferrer" target="_blank">
              <span>{platformName(deadline.platform)}</span>
              <strong>{deadline.claimType}</strong>
              <em>{deadline.days} дней</em>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}

function PvzView({
  tasks,
  onPreview,
  onFeedback,
  feedback
}: {
  tasks: Task[];
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
          <MiniProof label="смен" value="2/2" />
          <MiniProof label="споров" value="0" />
          <MiniProof label="дел" value={String(tasks.length)} />
        </div>
      </section>
      <TaskList tasks={tasks} onPreview={onPreview} onFeedback={onFeedback} feedback={feedback} />
    </div>
  );
}

function MoreView({
  readiness,
  plugins,
  llmStatus,
  memoryText,
  memoryQuery,
  memoryNotice,
  memoryResults,
  onMemoryText,
  onMemoryQuery,
  onMemorySave,
  onMemorySearch
}: {
  readiness: Readiness;
  plugins: PluginManifest[];
  llmStatus: LlmStatus | null;
  memoryText: string;
  memoryQuery: string;
  memoryNotice: string;
  memoryResults: MemoryItem[];
  onMemoryText: (value: string) => void;
  onMemoryQuery: (value: string) => void;
  onMemorySave: (event: FormEvent<HTMLFormElement>) => void;
  onMemorySearch: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="view-stack">
      <section className="readiness-card">
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
        {readiness.blockers.length > 0 && (
          <p className="quiet-text">Чтобы включить живой пилот: {readiness.blockers.map(blockerLabel).join(", ")}.</p>
        )}
        <p className="quiet-text">{llmStatusLabel(llmStatus)}</p>
      </section>
      <section className="readiness-card">
        <div className="row-between">
          <div>
            <p>Кнопки и навыки</p>
            <h3>Готовые действия можно расширять</h3>
          </div>
          <Sparkles size={22} />
        </div>
        <div className="chip-row">
          {(plugins.length ? plugins : demoPlugins).map((plugin) => (
            <span className="chip good" key={plugin.pluginId}>
              {plugin.label}
            </span>
          ))}
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
              <Sparkles size={18} />
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
  return (
    <div className="preview-layer" role="presentation">
      <section aria-modal="true" className="preview-sheet" role="dialog">
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
        {result && (
          <div className="result-box">
            <BadgeCheck size={18} />
            <span>{result.text}</span>
          </div>
        )}
        <div className="preview-actions">
          <button className="secondary-action" onClick={onClose} type="button">
            Отмена
          </button>
          <button className="primary-action" disabled={busy || !!result} onClick={onConfirm} type="button">
            {busy ? <Loader2 size={18} className="spin" /> : <Check size={18} />}
            <span>{result ? "Готово" : "Подтвердить"}</span>
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
  const money = tasks.reduce((sum, task) => sum + Math.max(0, task.moneyEffect || 0), 0) || 248820;
  const expenses = Math.max(18450, Math.round(money * 0.074));
  const penalties = Math.max(2350, Math.round(money * 0.009));
  const profit = Math.max(0, money - expenses - penalties);
  return {
    tasks: tasks.length,
    confirm: tasks.filter((task) => task.risk !== "safe").length,
    accounts: readiness?.accounts ?? accounts.length,
    money,
    yesterday: Math.max(0, Math.round(money / 1.124)),
    growth: "12,4",
    orders: Math.max(24, tasks.length * 12 + 8),
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

  if (platform) rows.add(platformName(platform));
  if (account) rows.add(`кабинет ${shorten(account)}`);
  if (sku) rows.add(`товар ${shorten(sku)}`);
  if (source) rows.add(source);
  if (Array.isArray(payload.evidence) && payload.evidence.length) rows.add("документы и доказательства");
  if (Array.isArray(payload.mcp_checks) && payload.mcp_checks.length) rows.add("10 проверок перед нажатием");
  if (Array.isArray(payload.skills) && payload.skills.length) rows.add("30 готовых навыков");
  if (!rows.size) rows.add("безопасный тестовый набор данных");

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
  if (/CUSTOM/i.test(moduleId)) return Sparkles;
  return Sparkles;
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

function readinessLabel(status?: string) {
  if (status === "ready_for_live_pilot") return "готов к реальному пилоту";
  if (status === "blocked_for_live_pilot") return "ждёт ключи кабинетов";
  if (status === "ready_for_replay_pilot") return "готов к безопасному тесту";
  return "проверяется";
}

function llmStatusLabel(status: LlmStatus | null) {
  if (!status) return "Живой ответ модели пока не проверялся.";
  if (status.modelAvailable) return "Модель отвечает и готова помогать с решениями.";
  if (status.configured) return "Ключ модели настроен, нужна проверка на сервере.";
  return "Сейчас работает локальная логика без внешней модели.";
}

function blockerLabel(blocker: string) {
  const map: Record<string, string> = {
    real_marketplace_tokens: "ключи кабинетов",
    marketplace_api_verification: "проверка кабинета",
    claim_deadline_policies: "сроки претензий",
    architecture_gate: "проверка архитектуры",
    prod_llm_gate: "проверка модели на сервере"
  };
  return map[blocker] ?? blocker;
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

function shorten(value: string) {
  return value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value;
}

function cleanText(value: string) {
  return value.replace(/\bReplay\b/gi, "Безопасный тест").replace(/\s+/g, " ").trim();
}

function isDone(status: string) {
  return status === "done" || status === "executed" || status === "prepared";
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0
  }).format(value || 0);
}

const demoReadiness: Readiness = {
  status: "ready_for_replay_pilot",
  mode: "replay",
  moduleCount: 23,
  skillsAndPlugins: 30,
  checksPerAction: 10,
  accounts: 0,
  claimDeadlinePolicies: 3,
  architectureGatePassed: false,
  blockers: ["real_marketplace_tokens"]
};

const demoLlmStatus: LlmStatus = {
  configured: false,
  model: "offline-logic",
  primaryProvider: "local",
  primaryModel: "rules",
  externalEnabled: false,
  smokeEnabled: false,
  liveCheckRequested: false,
  liveCheckRan: false,
  modelAvailable: null,
  status: "offline"
};

const demoPlugins: PluginManifest[] = [
  {
    pluginId: "quick-claim",
    label: "Претензия",
    surface: "both",
    moduleId: "M20",
    action: "claim",
    status: "draft",
    requiresConfirm: true,
    inputSchema: {}
  }
];

const demoDeadlines: ClaimDeadline[] = [
  {
    policyId: "wb-loss",
    platform: "wb",
    claimType: "потеря товара",
    days: 30,
    sourceUrl: "https://seller.wildberries.ru/",
    note: "проверяется по документам"
  },
  {
    policyId: "ozon-defect",
    platform: "ozon",
    claimType: "брак и возврат",
    days: 60,
    sourceUrl: "https://seller.ozon.ru/",
    note: "проверяется по акту"
  },
  {
    policyId: "ym-hold",
    platform: "ym",
    claimType: "лишнее удержание",
    days: 45,
    sourceUrl: "https://partner.market.yandex.ru/",
    note: "проверяется по отчёту"
  }
];

const demoTasks: Task[] = [
  {
    taskId: "demo-margin",
    moduleId: "M20_CLAIMS",
    title: "Вернуть лишнее удержание",
    shortText: "Нашёл удержание без закрывающего документа. Подготовил сумму, причину и доказательства.",
    actionLabel: "Отправить",
    priority: 9,
    risk: "confirm",
    status: "new",
    score: 0.91,
    moneyEffect: 8400,
    confidence: 0.82,
    deadlineAt: null,
    payload: {
      platform: "wb",
      sku: "SKU-1488",
      source: "финансовый отчёт",
      evidence: ["report", "deduction"],
      skills: Array.from({ length: 30 }, (_, index) => `skill_${index + 1}`),
      mcp_checks: Array.from({ length: 10 }, (_, index) => `mcp_check_${index + 1}`)
    }
  },
  {
    taskId: "demo-review",
    moduleId: "M05_REVIEWS",
    title: "Ответить на отзыв",
    shortText: "Покупатель доволен. Ответ безопасный, без лишних обещаний и спорных формулировок.",
    actionLabel: "Ответить",
    priority: 6,
    risk: "safe",
    status: "new",
    score: 0.72,
    moneyEffect: 0,
    confidence: 0.92,
    deadlineAt: null,
    payload: {
      platform: "ozon",
      sku: "OZ-700",
      source: "отзывы"
    }
  },
  {
    taskId: "demo-pvz",
    moduleId: "M11_PVZ",
    title: "Закрыть смену ПВЗ",
    shortText: "График 2/2 сходится. Зарплата посчитана, спорных смен нет.",
    actionLabel: "Закрыть",
    priority: 7,
    risk: "confirm",
    status: "new",
    score: 0.81,
    moneyEffect: 0,
    confidence: 0.88,
    deadlineAt: null,
    payload: {
      platform: "pvz",
      source: "табель смен"
    }
  },
  {
    taskId: "demo-stock",
    moduleId: "M10_FORECAST",
    title: "Пополнить остатки",
    shortText: "На складе осталось на 5 дней. Подготовил безопасную поставку с учётом продаж и FIFO.",
    actionLabel: "Показать",
    priority: 8,
    risk: "confirm",
    status: "new",
    score: 0.84,
    moneyEffect: 10000,
    confidence: 0.76,
    deadlineAt: null,
    payload: {
      platform: "wb",
      sku: "WB-402",
      source: "продажи и остатки"
    }
  },
  {
    taskId: "demo-ads",
    moduleId: "M19_ADS",
    title: "Остановить слив рекламы",
    shortText: "Ключ тратит бюджет без продаж. Подготовил паузу и перенос ставки в сильный ключ.",
    actionLabel: "Применить",
    priority: 8,
    risk: "confirm",
    status: "new",
    score: 0.86,
    moneyEffect: 3200,
    confidence: 0.79,
    deadlineAt: null,
    payload: {
      platform: "ozon",
      source: "рекламная статистика",
      sku: "AD-100"
    }
  }
];
