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
  Task,
  WriteScopeVerificationResult
} from "./types";

type AuthSession = {
  accessToken: string;
  expiresIn: number;
  tenantId: string;
  userId: string;
  role: string;
};

const demoHeaders = {
  "X-Tenant-Id": "demo-seller",
  "X-User-Id": "demo-owner",
  "X-Role": "owner"
};

let cachedSession: { initData: string; token: string; expiresAt: number } | null = null;
let pendingSession: Promise<string> | null = null;

async function authHeaders() {
  if (typeof window !== "undefined") {
    const initData = window.Telegram?.WebApp?.initData;
    if (initData) {
      return { Authorization: `Bearer ${await sessionToken(initData)}` };
    }
  }
  return demoHeaders;
}

async function sessionToken(initData: string) {
  const now = Date.now();
  if (cachedSession?.initData === initData && cachedSession.expiresAt - now > 30_000) {
    return cachedSession.token;
  }
  if (pendingSession) return pendingSession;

  pendingSession = fetch("/api/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData })
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`auth failed: ${response.status}`);
      return (await response.json()) as AuthSession;
    })
    .then((session) => {
      cachedSession = {
        initData,
        token: session.accessToken,
        expiresAt: Date.now() + Math.max(60, session.expiresIn - 30) * 1000
      };
      return session.accessToken;
    })
    .finally(() => {
      pendingSession = null;
    });

  return pendingSession;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(await authHeaders()),
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    let message = `request failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.trim()) {
        message = body.detail.trim();
      }
    } catch {
      // Keep the status-only error when the server returns a non-JSON response.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function getMorningTasks(): Promise<Task[]> {
  return request<Task[]>("/api/tasks/morning?limit=10");
}

export async function confirmTask(taskId: string): Promise<ConfirmResult> {
  return request<ConfirmResult>(`/api/tasks/${taskId}/confirm`, {
    method: "POST",
    headers: { "X-Idempotency-Key": `miniapp-${taskId}` },
    body: "{}"
  });
}

export async function sendFeedback(
  taskId: string,
  score: number,
  comment: string
): Promise<{ status: string }> {
  return request<{ status: string }>("/api/feedback", {
    method: "POST",
    body: JSON.stringify({ taskId, score, comment })
  });
}

export async function getAccounts(): Promise<AccountCapability[]> {
  return request<AccountCapability[]>("/api/accounts/capabilities");
}

export async function validateAccount(accountId: string): Promise<AccountActionResult> {
  return request<AccountActionResult>(`/api/accounts/${accountId}/validate`, {
    method: "POST",
    body: JSON.stringify({ dryRun: true })
  });
}

export async function syncCatalog(accountId: string): Promise<AccountActionResult> {
  return request<AccountActionResult>(`/api/accounts/${accountId}/sync/catalog`, {
    method: "POST",
    body: JSON.stringify({ dryRun: true })
  });
}

export async function getReadiness(): Promise<Readiness> {
  return request<Readiness>("/api/readiness");
}

export async function verifyWriteScopes(
  accountId: string,
  scopes: string[],
  sourceUrl: string,
  evidence: string
): Promise<WriteScopeVerificationResult> {
  return request<WriteScopeVerificationResult>(`/api/accounts/${accountId}/write-scopes`, {
    method: "POST",
    body: JSON.stringify({ scopes, sourceUrl, evidence })
  });
}

export async function getPlugins(): Promise<PluginManifest[]> {
  return request<PluginManifest[]>("/api/plugins");
}

export async function getClaimDeadlines(): Promise<ClaimDeadline[]> {
  return request<ClaimDeadline[]>("/api/claim-deadlines");
}

export async function getLlmStatus(): Promise<LlmStatus> {
  return request<LlmStatus>("/api/brain/llm-status");
}

export async function getArchitectureGate(live = false): Promise<ArchitectureGate> {
  return request<ArchitectureGate>(`/api/brain/architecture-gate${live ? "?live=true" : ""}`);
}

export async function saveMemory(
  text: string,
  options?: {
    scope?: string;
    title?: string;
    payload?: Record<string, unknown>;
  }
): Promise<MemoryItem> {
  return request<MemoryItem>("/api/memory", {
    method: "POST",
    body: JSON.stringify({
      scope: options?.scope ?? "seller-note",
      title: "Заметка владельца",
      text,
      payload: { surface: "miniapp", ...(options?.payload ?? {}) }
    })
  });
}

export async function searchMemory(query: string): Promise<MemoryItem[]> {
  return request<MemoryItem[]>("/api/memory/search", {
    method: "POST",
    body: JSON.stringify({ scope: "seller-note", query, limit: 5 })
  });
}
