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

export type ConfirmResult = {
  taskId: string;
  status: string;
  text: string;
  auditEvent: Record<string, unknown>;
};

export type AccountCapability = {
  accountId: string;
  platform: string;
  title: string;
  capabilities: Record<string, string>;
  limitations: string[];
};

export type AccountActionResult = {
  accountId: string;
  source: string;
  status?: string;
  dryRun: boolean;
  count?: number;
  plannedOperation: Record<string, unknown> | null;
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
  morningSchedulerEnabled: boolean;
  selfUpdateChecksEnabled: boolean;
  writeScopeBlockers: string[];
  blockers: string[];
};

export type ReleaseCriterion = {
  id: number;
  title: string;
  status: "passed" | "simulated" | "blocked" | string;
  evidence: string[];
  blockers: string[];
};

export type ReleaseGate = {
  overallStatus: string;
  simulation: boolean;
  criteria: ReleaseCriterion[];
  liveBlockers: string[];
  summary: {
    total: number;
    passed: number;
    simulated: number;
    blocked: number;
  };
  proof: Record<string, number | boolean | string>;
};

export type WriteScopeVerificationResult = {
  accountId: string;
  scopes: string[];
  status: string;
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

export type ClaimDeadline = {
  policyId: string;
  platform: string;
  claimType: string;
  days: number;
  sourceUrl: string;
  note: string;
  sourceKind: string;
  ownerVerified: boolean;
  needsOwnerVerification: boolean;
};

export type LlmStatus = {
  configured: boolean;
  model: string;
  primaryProvider: string;
  primaryModel: string;
  externalEnabled: boolean;
  smokeEnabled: boolean;
  liveCheckRequested: boolean;
  liveCheckRan: boolean;
  modelAvailable: boolean | null;
  status: string;
};

export type ArchitectureGate = {
  topology: Record<string, unknown>;
  verdict: string;
  text: string;
  blockers: string[];
  model: string;
  usedFallback: boolean;
  tokensEstimate: number;
};

export type MemoryItem = {
  memoryId: string;
  scope: string;
  title: string;
  text: string;
  textHash: string;
  embeddingModel: string;
  score: number;
  payload: Record<string, unknown>;
};
