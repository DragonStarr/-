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
  { id: "day", label: "День", icon: BriefcaseBusiness },
  { id: "accounts", label: "Кабинеты", icon: Boxes },
  { id: "money", label: "Деньги", icon: CircleDollarSign },
  { id: "pvz", label: "ПВЗ", icon: Building2 },
  { id: "more", label: "Ещё", icon: Settings }
];

export function OperatorDayApp() {
  const [tab, setTab] = useState<Tab>("day");
  const [tasks, setTasks] = useState<Task[]>([]);
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
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const [confirmResult, setConfirmResult] = useState<ConfirmResult | null>(null);
  const [accountAction, setAccountAction] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [memoryNotice, setMemoryNotice] = useState("");

  useTelegramChrome();

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
        setNotice({ text: "Готово", tone: "ready" });
      } catch {
        if (!mounted) return;
        setTasks(demoTasks);
        setAccounts([]);
        setReadiness(demoReadiness);
        setPlugins(demoPlugins);
        setDeadlines(demoDeadlines);
        setLlmStatus(demoLlmStatus);
        setNotice({ text: "Показываю безопасный режим", tone: "warn" });
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const visibleTasks = tasks.length ? tasks : demoTasks;
  const metrics = useMemo(() => buildMetrics(visibleTasks, accounts, readiness), [
    visibleTasks,
    accounts,
    readiness
  ]);
  const grouped = useMemo(() => groupTasks(visibleTasks), [visibleTasks]);

  async function handleConfirm(task: Task) {
    setBusyTaskId(task.taskId);
    setConfirmResult(null);
    setNotice({ text: "Делаю", tone: "loading" });
    try {
      const result = await confirmTask(task.taskId);
      setConfirmResult(result);
      setNotice({ text: "Записано", tone: "ready" });
      setTasks((rows) =>
        rows.map((item) => (item.taskId === task.taskId ? { ...item, status: result.status } : item))
      );
    } catch {
      setNotice({ text: "Ничего не изменил", tone: "warn" });
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
      <div className="app-backplate" aria-hidden="true" />
      <header className="topbar">
        <Logo loading={loading} />
        <div className="brand-copy">
          <p>мпомощник</p>
          <h1>Оператор дня</h1>
        </div>
        <StatusPill notice={notice} />
      </header>

      <HeroWallet
        metrics={metrics}
        readiness={readiness}
        onSelectMoney={() => setTab("money")}
        onSelectAccounts={() => setTab("accounts")}
        onSelectMore={() => setTab("more")}
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
    tg?.setHeaderColor?.("#10151c");
    tg?.setBackgroundColor?.("#10151c");
    tg?.setBottomBarColor?.("#ffffff");
  }, []);
}

function Logo({ loading }: { loading: boolean }) {
  return (
    <div className={loading ? "logo mark-loading" : "logo"} aria-label="Логотип мпомощник">
      <span className="stripe blue" />
      <span className="stripe navy" />
      <span className="stripe red" />
      <span className="logo-core">М</span>
    </div>
  );
}

function StatusPill({ notice }: { notice: Notice }) {
  const Icon = notice.tone === "loading" ? Loader2 : notice.tone === "ready" ? BadgeCheck : Clock3;
  return (
    <div className={`status-pill ${notice.tone}`}>
      <Icon size={16} className={notice.tone === "loading" ? "spin" : undefined} />
      <span>{notice.text}</span>
    </div>
  );
}

function HeroWallet({
  metrics,
  readiness,
  onSelectMoney,
  onSelectAccounts,
  onSelectMore
}: {
  metrics: ReturnType<typeof buildMetrics>;
  readiness: Readiness | null;
  onSelectMoney: () => void;
  onSelectAccounts: () => void;
  onSelectMore: () => void;
}) {
  return (
    <section className="hero-wallet">
      <div className="hero-stripes" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="hero-top">
        <div>
          <p>Сегодня можно вернуть или сэкономить</p>
          <strong>{formatMoney(metrics.money)}</strong>
        </div>
        <div className="mode-chip">
          <ShieldCheck size={15} />
          <span>{readinessLabel(readiness?.status)}</span>
        </div>
      </div>
      <div className="metric-row">
        <Metric label="Дел" value={String(metrics.tasks)} />
        <Metric label="Нужен ОК" value={String(metrics.confirm)} />
        <Metric label="Кабинетов" value={String(metrics.accounts)} />
      </div>
      <div className="quick-actions" aria-label="Быстрые действия">
        <QuickAction icon={CircleDollarSign} label="Деньги" onClick={onSelectMoney} />
        <QuickAction icon={Plug} label="Кабинеты" onClick={onSelectAccounts} />
        <QuickAction icon={Database} label="Память" onClick={onSelectMore} />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function QuickAction({
  icon: Icon,
  label,
  onClick
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className="quick-action" type="button" onClick={onClick}>
      <Icon size={18} />
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
        <div>
          <p>Очередь дня</p>
          <h2>Сначала деньги, риски и срочные ответы</h2>
        </div>
        <span>{tasks.length} дел</span>
      </section>
      <TaskList tasks={tasks} onPreview={onPreview} onFeedback={onFeedback} feedback={feedback} />
      <section className="insight-grid">
        <InsightCard icon={Megaphone} title="Реклама" text={summaryText(grouped.ads, "Ставки и ключи спокойны")} />
        <InsightCard icon={ShoppingBag} title="Товары" text={summaryText(grouped.catalog, "Карточки без срочных провалов")} />
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
  const rows = tasks.length ? tasks : demoTasks.slice(0, 3);
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
  const Icon = moduleIcon(task.moduleId);
  return (
    <article className={`task-card ${done ? "done" : ""}`}>
      <div className="task-main">
        <div className={`task-icon ${task.risk}`}>
          {done ? <Check size={20} /> : <Icon size={20} />}
        </div>
        <div className="task-copy">
          <div className="task-title-row">
            <h3>{cleanText(task.title)}</h3>
            <RiskBadge risk={task.risk} status={task.status} />
          </div>
          <p>{cleanText(task.shortText)}</p>
          <div className="data-line">
            <span>{moduleLabel(task.moduleId)}</span>
            <span>{formatMoney(task.moneyEffect)}</span>
            <span>{Math.round(task.confidence * 100)}% уверен</span>
          </div>
        </div>
      </div>
      <div className="task-bottom">
        <div className="source-mini">
          <Database size={14} />
          <span>{shortSource(task)}</span>
        </div>
        <div className="task-buttons">
          {done && (
            <>
              <button type="button" onClick={() => onFeedback(task.taskId, 5)}>
                Хорошо
              </button>
              <button type="button" onClick={() => onFeedback(task.taskId, 2)}>
                Плохо
              </button>
            </>
          )}
          {feedbackText && <span className="feedback-note">{feedbackText}</span>}
          <button className="make-button" type="button" onClick={() => onPreview(task)}>
            <span>{done ? "Детали" : task.actionLabel || "Сделать"}</span>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </article>
  );
}

function RiskBadge({ risk, status }: { risk: string; status: string }) {
  if (isDone(status)) {
    return <span className="risk-badge good">записано</span>;
  }
  if (risk === "safe") return <span className="risk-badge good">можно</span>;
  if (risk === "human") return <span className="risk-badge warn">человек</span>;
  return <span className="risk-badge">нужен ОК</span>;
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
          icon={<Plug size={36} />}
          title="Кабинеты ждут подключения"
          text="После подключения я начну брать реальные товары, продажи, отзывы, рекламу, финансы, претензии и ПВЗ из личных кабинетов."
        />
        <SourceChecklist />
      </div>
    );
  }

  return (
    <div className="view-stack">
      <section className="section-head">
        <div>
          <p>Источники данных</p>
          <h2>Каждый кабинет проверяется перед действием</h2>
        </div>
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
                {capabilityName(name)}: {status === "ready" ? "готово" : "проверить"}
              </span>
            ))}
          </div>
          {!!account.limitations.length && (
            <p className="quiet-text">{account.limitations.join(", ")}</p>
          )}
          <div className="button-row">
            <button type="button" onClick={() => onAction(account, "validate")}>
              Проверить
            </button>
            <button type="button" onClick={() => onAction(account, "sync")}>
              Обновить товары
            </button>
          </div>
          {accountAction[account.accountId] && (
            <p className="action-note">{accountAction[account.accountId]}</p>
          )}
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
  const money = tasks.reduce((sum, task) => sum + Math.max(0, task.moneyEffect), 0);
  return (
    <div className="view-stack">
      <section className="money-panel">
        <CircleDollarSign size={28} />
        <div>
          <span>В работе по деньгам</span>
          <strong>{formatMoney(money || 9200)}</strong>
        </div>
      </section>
      <TaskList
        tasks={tasks.length ? tasks : demoTasks.slice(0, 2)}
        onPreview={onPreview}
        onFeedback={onFeedback}
        feedback={feedback}
      />
      <section className="deadline-card">
        <div className="row-between">
          <div>
            <p>Возвраты и претензии</p>
            <h3>Сроки не теряются</h3>
          </div>
          <FileText size={22} />
        </div>
        <div className="deadline-list">
          {deadlines.slice(0, 4).map((deadline) => (
            <a
              href={deadline.sourceUrl}
              key={deadline.policyId}
              rel="noreferrer"
              target="_blank"
            >
              <span>{platformName(deadline.platform)}</span>
              <strong>{deadline.claimType}</strong>
              <em>{deadline.days} дн.</em>
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
        <div>
          <p>Пункт выдачи</p>
          <h2>Смены, зарплата и спорные дни в одном месте</h2>
        </div>
        <div className="pvz-grid">
          <Metric label="График" value="2/2" />
          <Metric label="Смены" value="14" />
          <Metric label="Споры" value="0" />
        </div>
      </section>
      <TaskList
        tasks={tasks.length ? tasks : demoTasks.slice(2, 4)}
        onPreview={onPreview}
        onFeedback={onFeedback}
        feedback={feedback}
      />
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
      <article className="readiness-card">
        <div className="row-between">
          <div>
            <p>Готовность</p>
            <h3>{readinessLabel(readiness.status)}</h3>
          </div>
          <Gauge size={24} />
        </div>
        <div className="proof-grid">
          <MiniProof label="модулей" value={String(readiness.moduleCount)} />
          <MiniProof label="навыков" value={String(readiness.skillsAndPlugins)} />
          <MiniProof label="проверок" value={String(readiness.checksPerAction)} />
        </div>
        {!!readiness.blockers.length && (
          <p className="quiet-text">Ждёт: {readiness.blockers.map(blockerLabel).join(", ")}</p>
        )}
      </article>
      <article className="readiness-card">
        <div className="row-between">
          <div>
            <p>ИИ на сервере</p>
            <h3>{llmStatusLabel(llmStatus)}</h3>
          </div>
          <Activity size={24} />
        </div>
        <p className="quiet-text">
          Логика действия сначала собирает данные и проверки, потом готовит решение, а опасные шаги
          ждут подтверждения.
        </p>
      </article>
      <article className="readiness-card">
        <div className="row-between">
          <div>
            <p>Кнопки и навыки</p>
            <h3>{plugins.length ? `${plugins.length} подключено` : "можно добавлять"}</h3>
          </div>
          <ClipboardCheck size={24} />
        </div>
        <p className="quiet-text">
          Новую кнопку можно добавить заявкой: без запуска чужого кода и с подтверждением
          действий.
        </p>
      </article>
      <article className="memory-card">
        <div className="row-between">
          <div>
            <p>Память</p>
            <h3>Запоминает правила владельца</h3>
          </div>
          <Database size={24} />
        </div>
        <form onSubmit={onMemorySave}>
          <textarea
            aria-label="Что запомнить"
            onChange={(event) => onMemoryText(event.target.value)}
            placeholder="Например: не снижать цену ниже 1180 рублей без моего ОК"
            value={memoryText}
          />
          <button type="submit">
            <Send size={16} />
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
        <div className="row-between">
          <div>
            <p>{moduleLabel(task.moduleId)}</p>
            <h2>{task.actionLabel || "Сделать"}</h2>
          </div>
          <RiskBadge risk={task.risk} status={task.status} />
        </div>
        <p className="sheet-text">{cleanText(task.shortText)}</p>
        <div className="proof-grid">
          <MiniProof label="эффект" value={formatMoney(task.moneyEffect)} />
          <MiniProof label="уверен" value={`${Math.round(task.confidence * 100)}%`} />
          <MiniProof label="проверок" value={String(checks.length)} />
        </div>
        <section className="source-card">
          <h3>На основе чего</h3>
          <ul>
            {sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </section>
        <section className="source-card">
          <h3>Что проверено</h3>
          <ul>
            {checks.map((check) => (
              <li key={check}>{check}</li>
            ))}
          </ul>
        </section>
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
            Закрыть
          </button>
          <button className="primary-action" disabled={busy || !!result} onClick={onConfirm} type="button">
            {busy ? <Loader2 size={18} className="spin" /> : <Sparkles size={18} />}
            <span>{result ? "Готово" : "Сделать"}</span>
          </button>
        </div>
      </section>
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
            <Icon size={20} />
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
      <Icon size={19} />
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
  return {
    tasks: tasks.length,
    confirm: tasks.filter((task) => task.risk !== "safe").length,
    accounts: readiness?.accounts ?? accounts.length,
    money: tasks.reduce((sum, task) => sum + Math.max(0, task.moneyEffect || 0), 0) || 18400
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

  if (platform) rows.add(`кабинет ${platformName(platform)}`);
  if (account) rows.add(`аккаунт ${shorten(account)}`);
  if (sku) rows.add(`товар ${shorten(sku)}`);
  if (source) rows.add(`источник ${source}`);
  if (Array.isArray(payload.evidence) && payload.evidence.length) rows.add("документы и доказательства");
  if (Array.isArray(payload.mcp_checks) && payload.mcp_checks.length) rows.add("10 внутренних проверок");
  if (Array.isArray(payload.skills) && payload.skills.length) rows.add("30 навыков и кнопок");
  if (!rows.size) rows.add("безопасный тестовый набор данных");

  return Array.from(rows).slice(0, 5);
}

function checkList(task: Task) {
  const payload = task.payload ?? {};
  if (Array.isArray(payload.mcp_checks) && payload.mcp_checks.length) {
    return payload.mcp_checks.map((check) => readableCheck(String(check))).slice(0, 10);
  }
  return [
    "права кабинета",
    "свежесть данных",
    "лимиты площадки",
    "риск денег",
    "повтор действия",
    "журнал изменений",
    "откат",
    "правило владельца",
    "безопасный текст",
    "итоговая проверка"
  ];
}

function shortSource(task: Task) {
  return sourceList(task)[0] ?? "данные готовы";
}

function summaryText(tasks: Task[], fallback: string) {
  if (!tasks.length) return fallback;
  const best = tasks[0];
  return `${cleanText(best.title)}: ${formatMoney(best.moneyEffect)}`;
}

function moduleLabel(moduleId: string) {
  if (/FINANCE|CLAIM|REPORT/i.test(moduleId)) return "деньги";
  if (/PVZ/i.test(moduleId)) return "ПВЗ";
  if (/ADS|PROMO|BID/i.test(moduleId)) return "реклама";
  if (/SEO|CARD/i.test(moduleId)) return "карточка";
  if (/REPRICE|PRICE/i.test(moduleId)) return "цены";
  if (/FORECAST|STOCK/i.test(moduleId)) return "остатки";
  if (/REVIEW/i.test(moduleId)) return "отзывы";
  return "задача";
}

function moduleIcon(moduleId: string): LucideIcon {
  if (/FINANCE|CLAIM|REPORT/i.test(moduleId)) return CircleDollarSign;
  if (/PVZ/i.test(moduleId)) return Building2;
  if (/ADS|PROMO|BID/i.test(moduleId)) return Megaphone;
  if (/SEO|CARD/i.test(moduleId)) return LineChart;
  if (/REPRICE|PRICE/i.test(moduleId)) return Gauge;
  if (/FORECAST|STOCK/i.test(moduleId)) return Boxes;
  if (/REVIEW/i.test(moduleId)) return MessageSquareText;
  return Sparkles;
}

function platformName(platform: string) {
  const value = platform.toLowerCase();
  if (value === "wb") return "WB";
  if (value === "ozon") return "Ozon";
  if (value === "ym") return "Яндекс Маркет";
  if (value === "pvz") return "ПВЗ";
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
  if (!status) return "без живой проверки";
  if (status.modelAvailable) return "модель отвечает";
  if (status.configured) return "ключ настроен";
  return "локальная логика";
}

function blockerLabel(blocker: string) {
  const map: Record<string, string> = {
    real_marketplace_tokens: "ключи кабинетов",
    marketplace_api_verification: "проверка кабинета",
    claim_deadline_policies: "сроки претензий",
    architecture_gate: "архитектурная проверка",
    prod_llm_gate: "проверка ИИ на сервере"
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
    "audit event": "запись в журнал"
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
    shortText: "Покупатель доволен. Ответ безопасный, без лишних обещаний и без спорных формулировок.",
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
