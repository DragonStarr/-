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

const demoHeaders = {
  "X-Tenant-Id": "demo-seller",
  "X-User-Id": "demo-owner",
  "X-Role": "owner"
};

function authHeaders() {
  if (typeof window !== "undefined") {
    const initData = window.Telegram?.WebApp?.initData;
    if (initData) {
      return { "X-Telegram-Init-Data": initData };
    }
  }
  return demoHeaders;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
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

export async function getPlugins(): Promise<PluginManifest[]> {
  return request<PluginManifest[]>("/api/plugins");
}

export async function getClaimDeadlines(): Promise<ClaimDeadline[]> {
  return request<ClaimDeadline[]>("/api/claim-deadlines");
}

export async function getLlmStatus(): Promise<LlmStatus> {
  return request<LlmStatus>("/api/brain/llm-status");
}

export async function saveMemory(text: string): Promise<MemoryItem> {
  return request<MemoryItem>("/api/memory", {
    method: "POST",
    body: JSON.stringify({
      scope: "seller-note",
      title: "Заметка владельца",
      text,
      payload: { surface: "miniapp" }
    })
  });
}

export async function searchMemory(query: string): Promise<MemoryItem[]> {
  return request<MemoryItem[]>("/api/memory/search", {
    method: "POST",
    body: JSON.stringify({ scope: "seller-note", query, limit: 5 })
  });
}
