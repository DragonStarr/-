export type Task = {
  taskId: string;
  moduleId: string;
  title: string;
  shortText: string;
  actionLabel: string;
  priority: number;
  risk: "safe" | "confirm" | "human" | string;
  status: string;
  score: number;
  moneyEffect: number;
  confidence: number;
  deadlineAt: string | null;
  payload: Record<string, unknown>;
};

export type AccountCapability = {
  accountId: string;
  platform: string;
  title: string;
  capabilities: Record<string, string>;
  limitations: string[];
};

export type Readiness = {
  status: string;
  mode: string;
  moduleCount: number;
  skillsAndPlugins: number;
  checksPerAction: number;
  accounts: number;
  claimDeadlinePolicies: number;
  architectureGatePassed: boolean;
  blockers: string[];
};

export type PluginManifest = {
  pluginId: string;
  label: string;
  surface: string;
  moduleId: string;
  action: string;
  status: string;
  requiresConfirm: boolean;
  inputSchema: Record<string, unknown>;
};
