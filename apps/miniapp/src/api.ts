import type { AccountCapability, PluginManifest, Readiness, Task } from "./types";

const headers = {
  "X-Tenant-Id": "demo-seller",
  "X-User-Id": "demo-owner",
  "X-Role": "owner"
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...headers,
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
  return request<Task[]>("/api/tasks/morning?limit=5");
}

export async function confirmTask(taskId: string): Promise<{ text: string; status: string }> {
  return request(`/api/tasks/${taskId}/confirm`, {
    method: "POST",
    headers: { "X-Idempotency-Key": `miniapp-${taskId}` },
    body: "{}"
  });
}

export async function getAccounts(): Promise<AccountCapability[]> {
  return request<AccountCapability[]>("/api/accounts/capabilities");
}

export async function getReadiness(): Promise<Readiness> {
  return request<Readiness>("/api/readiness");
}

export async function getPlugins(): Promise<PluginManifest[]> {
  return request<PluginManifest[]>("/api/plugins");
}
