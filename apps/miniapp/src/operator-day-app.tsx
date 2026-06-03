"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BadgeCheck,
  Boxes,
  BriefcaseBusiness,
  Building2,
  Check,
  CircleDollarSign,
  Loader2,
  Plug,
  Settings,
  ShieldCheck,
  Sparkles,
  WalletCards,
  type LucideIcon
} from "lucide-react";
import { confirmTask, getAccounts, getMorningTasks, getPlugins, getReadiness } from "./api";
import type { AccountCapability, PluginManifest, Readiness, Task } from "./types";

type Tab = "tasks" | "accounts" | "finance" | "pvz" | "settings";

const tabs: Array<{ id: Tab; label: string; icon: LucideIcon }> = [
  { id: "tasks", label: "Дела", icon: BriefcaseBusiness },
  { id: "accounts", label: "Кабинеты", icon: Boxes },
  { id: "finance", label: "Финансы", icon: CircleDollarSign },
  { id: "pvz", label: "ПВЗ", icon: Building2 },
  { id: "settings", label: "Ещё", icon: Settings }
];

export function OperatorDayApp() {
  const [tab, setTab] = useState<Tab>("tasks");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [accounts, setAccounts] = useState<AccountCapability[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [plugins, setPlugins] = useState<PluginManifest[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("Собираю дела");
  const [previewTask, setPreviewTask] = useState<Task | null>(null);

  useTelegramChrome();

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const [taskRows, accountRows, ready, pluginRows] = await Promise.all([
          getMorningTasks(),
          getAccounts(),
          getReadiness(),
          getPlugins().catch(() => [])
        ]);
        if (!mounted) return;
        setTasks(taskRows);
        setAccounts(accountRows);
        setReadiness(ready);
        setPlugins(pluginRows);
        setNotice("Готово");
      } catch {
        if (!mounted) return;
        setNotice("Показываю демо");
        setTasks(demoTasks);
        setAccounts([]);
        setReadiness(demoReadiness);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const money = useMemo(
    () => tasks.reduce((sum, task) => sum + Math.max(0, task.moneyEffect || 0), 0),
    [tasks]
  );
  const urgent = tasks.filter((task) => task.risk !== "safe").length;

  async function handleConfirm(task: Task) {
    setNotice("Делаю");
    setPreviewTask(null);
    try {
      await confirmTask(task.taskId);
      setNotice("Записано");
      setTasks((rows) =>
        rows.map((item) => (item.taskId === task.taskId ? { ...item, status: "done" } : item))
      );
    } catch {
      setNotice("Не получилось. Ничего не изменил.");
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <Logo />
        <div>
          <p className="muted">мпомощник</p>
          <h1>Оператор дня</h1>
        </div>
        <div className="status-pill">
          {loading ? <Loader2 size={16} className="spin" /> : <BadgeCheck size={16} />}
          <span>{notice}</span>
        </div>
      </header>

      <section className="hero-band">
        <div>
          <p className="eyeless">Сегодня</p>
          <strong>{tasks.length || 5} дел</strong>
          <span>закрыть первыми</span>
        </div>
        <div>
          <p className="eyeless">Эффект</p>
          <strong>{formatMoney(money || 18400)}</strong>
          <span>по действиям</span>
        </div>
        <div>
          <p className="eyeless">ОК</p>
          <strong>{urgent || 2}</strong>
          <span>подтвердить</span>
        </div>
      </section>

      <section className="content">
        {tab === "tasks" && <TaskList tasks={tasks} onConfirm={setPreviewTask} />}
        {tab === "accounts" && <Accounts accounts={accounts} />}
        {tab === "finance" && <Finance tasks={tasks} />}
        {tab === "pvz" && <Pvz tasks={tasks} />}
        {tab === "settings" && (
          <SettingsView readiness={readiness} plugins={plugins} loading={loading} />
        )}
      </section>

      <nav className="bottom-nav" aria-label="Основное меню">
        {tabs.map((item) => {
          const Icon = item.icon;
          const active = item.id === tab;
          return (
            <button
              className={active ? "nav-button active" : "nav-button"}
              key={item.id}
              onClick={() => setTab(item.id)}
              type="button"
            >
              <Icon size={20} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {previewTask && (
        <ActionPreview
          task={previewTask}
          onClose={() => setPreviewTask(null)}
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
    tg?.setHeaderColor?.("#eef3ef");
    tg?.setBackgroundColor?.("#eef3ef");
  }, []);
}

function Logo() {
  return (
    <div className="logo" aria-label="Логотип">
      <span className="stripe blue" />
      <span className="stripe navy" />
      <span className="stripe red" />
      <span className="logo-dot">М</span>
    </div>
  );
}

function TaskList({ tasks, onConfirm }: { tasks: Task[]; onConfirm: (task: Task) => void }) {
  const rows = tasks.length ? tasks : demoTasks;
  return (
    <div className="stack">
      {rows.map((task, index) => (
        <article className="task-row" key={task.taskId}>
          <div className="emoji" style={{ animationDelay: `${index * 90}ms` }}>
            {task.status === "done" ? "✅" : task.risk === "safe" ? "🟢" : "⚡"}
          </div>
          <div className="task-body">
            <div className="row-head">
              <h2>{task.title}</h2>
              <span>{task.confidence < 0.5 ? "проверить" : "можно"}</span>
            </div>
            <p>{task.shortText}</p>
            <div className="mini-stats">
              <span>{formatMoney(task.moneyEffect)}</span>
              <span>{task.actionLabel}</span>
            </div>
          </div>
          <button
            aria-label={task.actionLabel}
            className="round-action"
            onClick={() => onConfirm(task)}
            type="button"
          >
            {task.status === "done" ? <Check size={20} /> : <Sparkles size={20} />}
          </button>
        </article>
      ))}
    </div>
  );
}

function ActionPreview({
  task,
  onClose,
  onConfirm
}: {
  task: Task;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="preview-layer" role="presentation">
      <section aria-modal="true" className="preview-sheet" role="dialog">
        <div className="row-head">
          <h2>{task.actionLabel}</h2>
          <span>{task.risk === "safe" ? "безопасно" : "нужен ОК"}</span>
        </div>
        <p>{task.shortText}</p>
        <div className="proof-grid">
          <MiniProof label="Эффект" value={formatMoney(task.moneyEffect)} />
          <MiniProof label="Уверен" value={`${Math.round(task.confidence * 100)}%`} />
          <MiniProof label="Модуль" value={task.moduleId.split("_")[0]} />
        </div>
        <div className="preview-actions">
          <button className="secondary-action" onClick={onClose} type="button">
            Отмена
          </button>
          <button className="primary-action" onClick={onConfirm} type="button">
            Сделать
          </button>
        </div>
      </section>
    </div>
  );
}

function Accounts({ accounts }: { accounts: AccountCapability[] }) {
  if (!accounts.length) {
    return (
      <EmptyState
        icon={<Plug size={34} />}
        title="Кабинеты ждут"
        text="После подключения я буду брать реальные товары, отзывы, деньги и претензии."
      />
    );
  }
  return (
    <div className="stack">
      {accounts.map((account) => (
        <article className="soft-panel" key={account.accountId}>
          <div className="row-head">
            <h2>{account.title}</h2>
            <span>{account.platform.toUpperCase()}</span>
          </div>
          <div className="chips">
            {Object.entries(account.capabilities).map(([name, status]) => (
              <span key={name} className={status === "ready" ? "chip good" : "chip wait"}>
                {capabilityName(name)}: {status === "ready" ? "готово" : "проверить"}
              </span>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function Finance({ tasks }: { tasks: Task[] }) {
  const rows = tasks.filter(
    (task) => task.moduleId.includes("FINANCE") || task.moduleId.includes("CLAIMS")
  );
  return (
    <div className="stack">
      <section className="money-panel">
        <WalletCards size={28} />
        <div>
          <span>Деньги под контролем</span>
          <strong>
            {formatMoney(rows.reduce((sum, task) => sum + Math.max(0, task.moneyEffect), 0) || 9200)}
          </strong>
        </div>
      </section>
      <TaskList tasks={rows.length ? rows : demoTasks.slice(0, 2)} onConfirm={() => undefined} />
    </div>
  );
}

function Pvz({ tasks }: { tasks: Task[] }) {
  const rows = tasks.filter((task) => task.moduleId.includes("PVZ"));
  return <TaskList tasks={rows.length ? rows : demoTasks.slice(2, 4)} onConfirm={() => undefined} />;
}

function SettingsView({
  readiness,
  plugins,
  loading
}: {
  readiness: Readiness | null;
  plugins: PluginManifest[];
  loading: boolean;
}) {
  return (
    <div className="stack">
      <article className="soft-panel">
        <div className="row-head">
          <h2>Готовность</h2>
          <span>{loading ? "проверяю" : readinessLabel(readiness?.status)}</span>
        </div>
        <div className="proof-grid">
          <MiniProof label="Модулей" value={String(readiness?.moduleCount ?? 23)} />
          <MiniProof label="Навыков" value={String(readiness?.skillsAndPlugins ?? 30)} />
          <MiniProof label="Проверок" value={String(readiness?.checksPerAction ?? 10)} />
        </div>
      </article>
      <article className="soft-panel">
        <div className="row-head">
          <h2>Кнопки</h2>
          <span>{plugins.length ? `${plugins.length} шт.` : "можно добавить"}</span>
        </div>
        <p className="plain">Новые кнопки добавляются по манифесту. Код пользователя не запускается.</p>
      </article>
      <article className="soft-panel safe">
        <ShieldCheck size={24} />
        <p>Опасные действия идут только после ОК, всё пишется в журнал.</p>
      </article>
    </div>
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

function EmptyState({
  icon,
  title,
  text
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0
  }).format(value || 0);
}

function capabilityName(name: string) {
  const map: Record<string, string> = {
    catalog: "Каталог",
    reviews: "Отзывы",
    finance: "Финансы",
    ads: "Реклама",
    claims: "Претензии",
    pvz: "ПВЗ"
  };
  return map[name] ?? name;
}

function readinessLabel(status?: string) {
  if (status === "ready_for_live_pilot") return "готово";
  if (status === "blocked_for_live_pilot") return "ждёт ключи";
  if (status === "ready_for_replay_pilot") return "демо готово";
  return "проверяется";
}

const demoReadiness: Readiness = {
  status: "ready_for_replay_pilot",
  mode: "replay",
  moduleCount: 23,
  skillsAndPlugins: 30,
  checksPerAction: 10,
  accounts: 0,
  claimDeadlinePolicies: 0,
  architectureGatePassed: false,
  blockers: ["real_marketplace_tokens"]
};

const demoTasks: Task[] = [
  {
    taskId: "demo-margin",
    moduleId: "M08_FINANCE",
    title: "Вернуть удержание",
    shortText: "Нашёл лишнее списание. Подготовил претензию и сумму к возврату.",
    actionLabel: "Отправить",
    priority: 9,
    risk: "confirm",
    status: "new",
    score: 0.91,
    moneyEffect: 8400,
    confidence: 0.82,
    deadlineAt: null,
    payload: {}
  },
  {
    taskId: "demo-review",
    moduleId: "M05_REVIEWS",
    title: "Ответить на отзыв",
    shortText: "Покупатель доволен. Ответ безопасный, без лишних обещаний.",
    actionLabel: "Ответить",
    priority: 6,
    risk: "safe",
    status: "new",
    score: 0.72,
    moneyEffect: 0,
    confidence: 0.92,
    deadlineAt: null,
    payload: {}
  },
  {
    taskId: "demo-pvz",
    moduleId: "M11_PVZ",
    title: "Закрыть смену",
    shortText: "График 2/2 сходится. Зарплата посчитана, спорных смен нет.",
    actionLabel: "Закрыть",
    priority: 7,
    risk: "confirm",
    status: "new",
    score: 0.81,
    moneyEffect: 0,
    confidence: 0.88,
    deadlineAt: null,
    payload: {}
  },
  {
    taskId: "demo-stock",
    moduleId: "M10_FORECAST",
    title: "Пополнить остатки",
    shortText: "На складе осталось на 5 дней. Подготовил безопасную поставку.",
    actionLabel: "Показать",
    priority: 8,
    risk: "confirm",
    status: "new",
    score: 0.84,
    moneyEffect: 10000,
    confidence: 0.76,
    deadlineAt: null,
    payload: {}
  }
];
