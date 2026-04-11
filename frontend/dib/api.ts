/**
 * Typed API client.
 *
 * Frontend mock mode:
 * - Enabled when NEXT_PUBLIC_USE_MOCK is not set to "false".
 * - Set NEXT_PUBLIC_USE_MOCK=false to use the real backend again.
 */

import {
  FEATURE_LABELS,
  GSTIN_TASK_MAP,
  MOCK_API_KEYS,
  MOCK_AUDIT_LOG,
  MOCK_BANKS,
  MOCK_DISPUTES,
  MOCK_FRAUD_ALERTS,
  MOCK_GLOBAL_GRAPH,
  MOCK_GRAPH_TEXTILEZONE,
  MOCK_HEALTH_OK,
  MOCK_KEY_001_USAGE,
  MOCK_LOAN_REQUESTS,
  MOCK_NOTIFICATIONS,
  MOCK_PERMISSIONS,
  MOCK_REMINDERS,
  MOCK_RISK_THRESHOLDS,
  MOCK_SCORE_HISTORY,
  MOCK_SCORES,
  MOCK_USERS,
} from "@/dib/mockData";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";
const MOCK_DELAY_MS = Number(process.env.NEXT_PUBLIC_MOCK_DELAY_MS ?? 120);

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("msme_token");
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const DEMO_ONLY_USERS = [
  {
    id: "usr_001",
    name: "Priya Sharma",
    email: "priya@bakerycraft.in",
    role: "msme",
    gstin: "19HLPRM4249Z3Z1",
    status: "active",
  },
  {
    id: "usr_002",
    name: "Rahul Desai",
    email: "rahul@boltautomotive.in",
    role: "msme",
    gstin: "09EXVAF9205D6Z0",
    status: "active",
  },
];

const mockState = {
  users: deepClone([...DEMO_ONLY_USERS, ...MOCK_USERS]) as any[],
  banks: deepClone(MOCK_BANKS) as any[],
  loans: deepClone(MOCK_LOAN_REQUESTS) as any[],
  permissions: deepClone(MOCK_PERMISSIONS) as any[],
  disputes: deepClone(MOCK_DISPUTES) as any[],
  reminders: deepClone(MOCK_REMINDERS) as Record<string, any[]>,
  notifications: deepClone(MOCK_NOTIFICATIONS) as Record<string, any[]>,
  riskThresholds: deepClone({
    ...MOCK_RISK_THRESHOLDS,
    amnesty_config: {
      active: false,
      quarter: 1,
      year: 2025,
      filing_penalty_multiplier: 0,
      description:
        "GST amnesty: late filings in selected quarter will not be penalised in credit scoring",
    },
  }),
  apiKeys: deepClone(MOCK_API_KEYS) as any[],
  auditLog: deepClone(MOCK_AUDIT_LOG) as any[],
  fraudAlerts: deepClone(MOCK_FRAUD_ALERTS) as any[],
  scores: deepClone(MOCK_SCORES) as Record<string, any>,
  scoreHistory: deepClone(MOCK_SCORE_HISTORY) as Record<string, any[]>,
  submittedTasks: {} as Record<string, { gstin: string; status: string; created_at: string }>,
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseBody(options: RequestInit): Record<string, any> {
  if (!options.body) return {};
  try {
    return JSON.parse(String(options.body));
  } catch {
    return {};
  }
}

function parsePath(path: string): { pathname: string; query: URLSearchParams } {
  const [pathname, qs] = path.split("?");
  return { pathname, query: new URLSearchParams(qs ?? "") };
}

function parseMockToken(token: string | null): string | null {
  if (!token) return null;
  if (!token.startsWith("mock-token-")) return null;
  return token.replace("mock-token-", "");
}

function getCurrentMockUser(token: string | null) {
  const uid = parseMockToken(token);
  if (!uid) return null;
  return mockState.users.find((u: any) => u.id === uid) ?? null;
}

function normalizeShap(score: any) {
  const shap = score?.shap_waterfall ?? [];
  return shap.map((s: any) => {
    const feature = s.feature_name ?? s.feature ?? "unknown_feature";
    const shapValue = s.shap_value ?? s.value ?? 0;
    const absMagnitude = s.abs_magnitude ?? Math.abs(shapValue);
    return {
      feature_name: feature,
      shap_value: shapValue,
      abs_magnitude: absMagnitude,
      direction: s.direction ?? (shapValue < 0 ? "decreases_risk" : "increases_risk"),
      label: FEATURE_LABELS[feature] ?? feature,
    };
  });
}

function normalizeScore(taskId: string, score: any) {
  return {
    ...score,
    task_id: score.task_id ?? taskId,
    status: score.status ?? "complete",
    shap_waterfall: normalizeShap(score),
  };
}

function profileTypeFromRisk(riskBand: string): string {
  if (riskBand === "high_risk") return "FRAUD_SHELL";
  if (riskBand === "medium_risk") return "STRUGGLING_MSME";
  return "HEALTHY_MSME";
}

function nameFromGstin(gstin: string): string {
  const foundUser = mockState.users.find((u: any) => u.gstin === gstin);
  if (foundUser) return foundUser.name;
  return `MSME ${gstin.slice(0, 6)}`;
}

function getScoreForGstin(gstin: string): any | null {
  const taskId = GSTIN_TASK_MAP[gstin];
  if (taskId && mockState.scores[taskId]) {
    return normalizeScore(taskId, { ...mockState.scores[taskId], gstin });
  }

  const dynamicTask = Object.keys(mockState.submittedTasks).find(
    (tid) => mockState.submittedTasks[tid].gstin === gstin,
  );
  if (dynamicTask && mockState.scores[dynamicTask]) {
    return normalizeScore(dynamicTask, { ...mockState.scores[dynamicTask], gstin });
  }

  return null;
}

function generateExplorerDetails(gstin: string) {
  const score = getScoreForGstin(gstin);
  const riskBand = score?.risk_band ?? "low_risk";
  const profileType = profileTypeFromRisk(riskBand);
  const base = riskBand === "high_risk" ? 60000 : riskBand === "medium_risk" ? 90000 : 140000;

  const timeline = Array.from({ length: 14 }).map((_, idx) => {
    const month = new Date(2025, idx, 1).toLocaleDateString("en-IN", {
      month: "short",
      year: "2-digit",
    });
    return {
      date: month,
      daily_volume: Math.round(base + idx * 2200 + (idx % 3) * 1700),
      daily_count: 18 + idx,
      daily_ewb_volume: Math.round(base * 0.75 + idx * 1800 + (idx % 2) * 1200),
      daily_ewb_count: 9 + idx,
    };
  });

  return {
    info: {
      gstin,
      business_name: nameFromGstin(gstin),
      profile_type: profileType,
      state_code: gstin.slice(0, 2),
      business_age_months: 12 + (gstin.charCodeAt(0) % 36),
    },
    upi_timeline: timeline.map((t) => ({ date: t.date, daily_volume: t.daily_volume, daily_count: t.daily_count })),
    ewb_timeline: timeline.map((t) => ({ date: t.date, daily_ewb_volume: t.daily_ewb_volume, daily_ewb_count: t.daily_ewb_count })),
    recent_upi: timeline.slice(-8).map((t, i) => ({
      txn_id: `UPI_${gstin.slice(0, 4)}_${i}`,
      amount: t.daily_volume,
      date: t.date,
      direction: i % 2 === 0 ? "inbound" : "outbound",
    })),
    recent_ewb: timeline.slice(-8).map((t, i) => ({
      ewb_no: `EWB_${gstin.slice(0, 4)}_${i}`,
      declared_value: t.daily_ewb_volume,
      date: t.date,
      hsn: `100${i}`,
    })),
  };
}

async function mockFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  await sleep(MOCK_DELAY_MS);

  const token = getToken();
  const method = (options.method ?? "GET").toUpperCase();
  const body = parseBody(options);
  const { pathname, query } = parsePath(path);

  const authError = () => {
    throw new Error("Unauthorized");
  };

  if (pathname === "/auth/login" && method === "POST") {
    const email = String(body.email ?? "").toLowerCase().trim();
    const password = String(body.password ?? "");
    if (!email || !password) throw new Error("Email and password are required");
    if (password !== "demo") throw new Error("Invalid credentials");

    const found = mockState.users.find((u: any) => u.email.toLowerCase() === email);
    if (!found) throw new Error("User not found");
    return { token: `mock-token-${found.id}`, user: found } as T;
  }

  if (pathname === "/auth/logout") {
    return { ok: true } as T;
  }

  if (pathname === "/auth/me") {
    const user = getCurrentMockUser(token);
    if (!user) authError();
    return user as T;
  }

  if (pathname === "/health") {
    return deepClone(MOCK_HEALTH_OK) as T;
  }

  if (pathname === "/score" && method === "POST") {
    const gstin = String(body.gstin ?? "").toUpperCase().trim();
    if (!gstin) throw new Error("GSTIN is required");

    const existingTask = GSTIN_TASK_MAP[gstin];
    const taskId = existingTask ?? `task_mock_${Date.now()}`;

    if (!mockState.scores[taskId]) {
      mockState.scores[taskId] = {
        ...deepClone(MOCK_SCORES.task_abc002),
        task_id: taskId,
        gstin,
        status: "complete",
      };
    }

    mockState.submittedTasks[taskId] = {
      gstin,
      status: "processing",
      created_at: new Date().toISOString(),
    };

    return { task_id: taskId, status: "processing" } as T;
  }

  if (pathname.startsWith("/score/") && method === "GET") {
    const taskId = pathname.replace("/score/", "");
    const submitted = mockState.submittedTasks[taskId];
    const score = mockState.scores[taskId];
    if (!submitted && !score) throw new Error("Task not found");

    if (submitted && submitted.status === "processing") {
      submitted.status = "complete";
    }

    const baseScore = score ?? deepClone(MOCK_SCORES.task_abc002);
    return normalizeScore(taskId, {
      ...baseScore,
      gstin: submitted?.gstin ?? baseScore.gstin,
      status: submitted?.status ?? "complete",
    }) as T;
  }

  if (pathname.startsWith("/score/") && pathname.endsWith("/chat") && method === "POST") {
    return { reply: "Mock score assistant response." } as T;
  }

  if (pathname === "/loan-requests" && method === "GET") {
    let data = [...mockState.loans];
    const gstin = query.get("gstin");
    const bankId = query.get("bank_id");
    const status = query.get("status");
    if (gstin) data = data.filter((l: any) => l.gstin === gstin);
    if (bankId) data = data.filter((l: any) => l.bank_id === bankId);
    if (status) data = data.filter((l: any) => l.status === status);
    return data as T;
  }

  if (pathname === "/loan-requests" && method === "POST") {
    const created = {
      id: `lr_${Date.now()}`,
      status: "submitted",
      denial_reason: null,
      amount_offered: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      ...body,
      gstin_masked: `${String(body.gstin ?? "").slice(0, 2)}****${String(body.gstin ?? "").slice(-4)}`,
      bank_name: mockState.banks.find((b: any) => b.id === body.bank_id)?.name ?? "Unknown Bank",
    };
    mockState.loans.unshift(created);
    return created as T;
  }

  const loanScoreMatch = pathname.match(/^\/loan-requests\/([^/]+)\/score$/);
  if (loanScoreMatch && method === "GET") {
    const lid = loanScoreMatch[1];
    const loan = mockState.loans.find((l: any) => l.id === lid);
    if (!loan) throw new Error("Loan request not found");
    const score = getScoreForGstin(loan.gstin);
    if (!score) throw new Error("Score unavailable");
    return score as T;
  }

  const loanDecisionMatch = pathname.match(/^\/loan-requests\/([^/]+)\/decision$/);
  if (loanDecisionMatch && method === "PUT") {
    const lid = loanDecisionMatch[1];
    const loan = mockState.loans.find((l: any) => l.id === lid);
    if (!loan) throw new Error("Loan request not found");

    const action = body.action === "approved" ? "approved" : "denied";
    loan.status = action;
    loan.updated_at = new Date().toISOString();
    loan.denial_reason = body.denial_reason ?? null;
    loan.amount_offered = body.amount_offered ?? null;
    return deepClone(loan) as T;
  }

  const loanByIdMatch = pathname.match(/^\/loan-requests\/([^/]+)$/);
  if (loanByIdMatch && method === "GET") {
    const loan = mockState.loans.find((l: any) => l.id === loanByIdMatch[1]);
    if (!loan) throw new Error("Loan request not found");
    return deepClone(loan) as T;
  }

  if (pathname === "/permissions" && method === "GET") {
    let data = [...mockState.permissions];
    const gstin = query.get("gstin");
    const status = query.get("status");
    if (gstin) data = data.filter((p: any) => p.gstin === gstin);
    if (status) data = data.filter((p: any) => p.status === status);
    return data as T;
  }

  if (pathname === "/permissions" && method === "POST") {
    const created: any = {
      id: `perm_${Date.now()}`,
      status: "pending",
      requested_at: new Date().toISOString(),
      responded_at: null,
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      ...body,
      bank_name: mockState.banks.find((b: any) => b.id === body.bank_id)?.name ?? "Unknown Bank",
    };
    mockState.permissions.unshift(created);

    const loan = mockState.loans.find((l: any) => l.id === created.loan_request_id);
    if (loan) loan.status = "permission_requested";

    return created as T;
  }

  const permUpdateMatch = pathname.match(/^\/permissions\/([^/]+)$/);
  if (permUpdateMatch && method === "PUT") {
    const perm = mockState.permissions.find((p: any) => p.id === permUpdateMatch[1]);
    if (!perm) throw new Error("Permission request not found");

    const action = body.action === "approve" ? "granted" : "revoked";
    perm.status = action;
    perm.responded_at = new Date().toISOString();

    const loan = mockState.loans.find((l: any) => l.id === perm.loan_request_id);
    if (loan) loan.status = action === "granted" ? "data_shared" : "denied";

    return deepClone(perm) as T;
  }

  if (pathname === "/disputes" && method === "GET") {
    let data = [...mockState.disputes];
    const gstin = query.get("gstin");
    if (gstin) data = data.filter((d: any) => d.gstin === gstin);
    return data as T;
  }

  if (pathname === "/disputes" && method === "POST") {
    const created = {
      id: `disp_${Date.now()}`,
      gstin: body.gstin,
      msme_name: nameFromGstin(String(body.gstin ?? "")),
      description: body.description ?? "",
      status: "open",
      analyst_id: null,
      analyst_name: null,
      resolution_note: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    mockState.disputes.unshift(created);
    return created as T;
  }

  const disputeAssignMatch = pathname.match(/^\/disputes\/([^/]+)\/assign$/);
  if (disputeAssignMatch && method === "PUT") {
    const dispute = mockState.disputes.find((d: any) => d.id === disputeAssignMatch[1]);
    if (!dispute) throw new Error("Dispute not found");
    dispute.status = "under_review";
    dispute.analyst_id = "usr_005";
    dispute.analyst_name = "Vikram Nair";
    dispute.updated_at = new Date().toISOString();
    return deepClone(dispute) as T;
  }

  const disputeResolveMatch = pathname.match(/^\/disputes\/([^/]+)\/resolve$/);
  if (disputeResolveMatch && method === "PUT") {
    const dispute = mockState.disputes.find((d: any) => d.id === disputeResolveMatch[1]);
    if (!dispute) throw new Error("Dispute not found");
    dispute.status = "resolved";
    dispute.resolution_note = body.resolution_note ?? "Resolved";
    dispute.updated_at = new Date().toISOString();
    return deepClone(dispute) as T;
  }

  if (pathname === "/reminders" && method === "GET") {
    const gstin = query.get("gstin");
    if (!gstin) return [] as T;
    return deepClone(mockState.reminders[gstin] ?? []) as T;
  }

  const reminderCompleteMatch = pathname.match(/^\/reminders\/([^/]+)\/complete$/);
  if (reminderCompleteMatch && method === "PUT") {
    const rid = reminderCompleteMatch[1];
    for (const key of Object.keys(mockState.reminders)) {
      const entry = mockState.reminders[key].find((r: any) => r.id === rid);
      if (entry) {
        entry.status = "completed";
        return deepClone(entry) as T;
      }
    }
    throw new Error("Reminder not found");
  }

  if (pathname === "/banks" && method === "GET") {
    return deepClone(mockState.banks) as T;
  }

  if (pathname === "/banks" && method === "POST") {
    const created = {
      id: `bank_${Date.now()}`,
      officer_count: 0,
      api_key_count: 0,
      created_at: new Date().toISOString(),
      status: "active",
      ...body,
    };
    mockState.banks.unshift(created);
    return created as T;
  }

  const bankUpdateMatch = pathname.match(/^\/banks\/([^/]+)$/);
  if (bankUpdateMatch && method === "PUT") {
    const bank = mockState.banks.find((b: any) => b.id === bankUpdateMatch[1]);
    if (!bank) throw new Error("Bank not found");
    Object.assign(bank, body);
    return deepClone(bank) as T;
  }

  if (pathname === "/users" && method === "GET") {
    return deepClone(mockState.users) as T;
  }

  if (pathname === "/users" && method === "POST") {
    const created = {
      id: `usr_${Date.now()}`,
      status: "active",
      created_at: new Date().toISOString(),
      ...body,
    };
    mockState.users.unshift(created);
    return created as T;
  }

  const userUpdateMatch = pathname.match(/^\/users\/([^/]+)$/);
  if (userUpdateMatch && method === "PUT") {
    const u = mockState.users.find((x: any) => x.id === userUpdateMatch[1]);
    if (!u) throw new Error("User not found");
    Object.assign(u, body);
    return deepClone(u) as T;
  }

  const userResetPwdMatch = pathname.match(/^\/users\/([^/]+)\/reset-password$/);
  if (userResetPwdMatch && method === "POST") {
    return { temp_password: "demo123", ok: true } as T;
  }

  if (pathname === "/api-keys" && method === "GET") {
    return deepClone(mockState.apiKeys) as T;
  }

  if (pathname === "/api-keys" && method === "POST") {
    const created = {
      id: `key_${Date.now()}`,
      key_prefix: `sk_${String(body.bank_id ?? "bank").slice(0, 4)}_...${Math.random().toString(36).slice(2, 6)}`,
      status: "active",
      usage_today: 0,
      quota_per_day: body.quota_per_day ?? 300,
      created_at: new Date().toISOString(),
      last_used_at: null,
      revoked_at: null,
      ...body,
      bank_name: mockState.banks.find((b: any) => b.id === body.bank_id)?.name ?? "Unknown Bank",
    };
    mockState.apiKeys.unshift(created);
    return { ...created, secret_key: `sk_live_${Math.random().toString(36).slice(2)}` } as T;
  }

  const apiKeyRevokeMatch = pathname.match(/^\/api-keys\/([^/]+)\/revoke$/);
  if (apiKeyRevokeMatch && method === "PUT") {
    const key = mockState.apiKeys.find((k: any) => k.id === apiKeyRevokeMatch[1]);
    if (!key) throw new Error("API key not found");
    key.status = "revoked";
    key.revoked_at = new Date().toISOString();
    return deepClone(key) as T;
  }

  const apiKeyRotateMatch = pathname.match(/^\/api-keys\/([^/]+)\/rotate$/);
  if (apiKeyRotateMatch && method === "PUT") {
    const key = mockState.apiKeys.find((k: any) => k.id === apiKeyRotateMatch[1]);
    if (!key) throw new Error("API key not found");
    key.last_used_at = new Date().toISOString();
    return {
      ...deepClone(key),
      secret_key: `sk_live_${Math.random().toString(36).slice(2)}`,
    } as T;
  }

  const apiKeyUsageMatch = pathname.match(/^\/api-keys\/([^/]+)\/usage$/);
  if (apiKeyUsageMatch && method === "GET") {
    return { key_id: apiKeyUsageMatch[1], usage: deepClone(MOCK_KEY_001_USAGE) } as T;
  }

  if (pathname === "/audit-log" && method === "GET") {
    return deepClone(mockState.auditLog) as T;
  }

  if (pathname === "/audit/replay" && method === "POST") {
    return {
      ok: true,
      replay_id: `replay_${Date.now()}`,
      summary: "Mock replay completed",
      input: body,
    } as T;
  }

  if (pathname === "/fraud-alerts" && method === "GET") {
    return deepClone(mockState.fraudAlerts) as T;
  }

  const fraudAlertMatch = pathname.match(/^\/fraud-alerts\/([^/]+)$/);
  if (fraudAlertMatch && method === "GET") {
    const alert = mockState.fraudAlerts.find((f: any) => f.gstin === fraudAlertMatch[1]);
    if (!alert) throw new Error("Fraud alert not found");
    return deepClone(alert) as T;
  }

  if (pathname === "/risk-thresholds" && method === "GET") {
    return deepClone(mockState.riskThresholds) as T;
  }

  if (pathname === "/risk-thresholds" && method === "PUT") {
    mockState.riskThresholds = { ...mockState.riskThresholds, ...body };
    return deepClone(mockState.riskThresholds) as T;
  }

  if (pathname === "/score-history" && method === "GET") {
    const gstin = query.get("gstin") ?? "";
    return deepClone(mockState.scoreHistory[gstin] ?? []) as T;
  }

  if (pathname === "/transactions/graph" && method === "GET") {
    const nodes = (MOCK_GLOBAL_GRAPH.nodes as any[]).map((n) => ({
      ...n,
      pagerank_score: typeof n.total_volume_inr === "number" ? n.total_volume_inr / 10000000 : 0.05,
    }));
    return { nodes, edges: deepClone(MOCK_GLOBAL_GRAPH.edges) } as T;
  }

  const gstinGraphMatch = pathname.match(/^\/transactions\/([^/]+)\/graph$/);
  if (gstinGraphMatch && method === "GET") {
    return deepClone(MOCK_GRAPH_TEXTILEZONE) as T;
  }

  const ewbDistributionMatch = pathname.match(/^\/transactions\/([^/]+)\/ewb-distribution$/);
  if (ewbDistributionMatch && method === "GET") {
    return {
      smurfing_index: 0.34,
      buckets: [
        { bucket: "0-10k", count: 6, smurf_band: false },
        { bucket: "10k-20k", count: 12, smurf_band: false },
        { bucket: "20k-30k", count: 16, smurf_band: false },
        { bucket: "30k-40k", count: 22, smurf_band: false },
        { bucket: "40k-45k", count: 18, smurf_band: false },
        { bucket: "45k-49.9k", count: 31, smurf_band: true },
        { bucket: "50k-70k", count: 14, smurf_band: false },
      ],
    } as T;
  }

  const receivablesGapMatch = pathname.match(/^\/transactions\/([^/]+)\/receivables-gap$/);
  if (receivablesGapMatch && method === "GET") {
    return {
      monthly: [
        { month: "Nov 25", gst_invoiced: 980000, upi_inbound: 910000 },
        { month: "Dec 25", gst_invoiced: 1020000, upi_inbound: 960000 },
        { month: "Jan 26", gst_invoiced: 1080000, upi_inbound: 990000 },
        { month: "Feb 26", gst_invoiced: 1120000, upi_inbound: 1010000 },
        { month: "Mar 26", gst_invoiced: 1210000, upi_inbound: 1065000 },
      ],
    } as T;
  }

  if (pathname === "/explorer/gstins" && method === "GET") {
    const out = Object.keys(GSTIN_TASK_MAP).map((gstin) => {
      const score = getScoreForGstin(gstin);
      return {
        gstin,
        business_name: nameFromGstin(gstin),
        profile_type: profileTypeFromRisk(score?.risk_band ?? "low_risk"),
        state_code: gstin.slice(0, 2),
        business_age_months: 12 + (gstin.charCodeAt(0) % 36),
      };
    });
    return out as T;
  }

  const explorerDetailsMatch = pathname.match(/^\/explorer\/([^/]+)\/details$/);
  if (explorerDetailsMatch && method === "GET") {
    return generateExplorerDetails(explorerDetailsMatch[1]) as T;
  }

  if (pathname === "/notifications" && method === "GET") {
    const current = getCurrentMockUser(token);
    if (!current) return [] as T;
    const onlyUnread = query.get("unread") === "true";
    const data = deepClone(mockState.notifications[current.id] ?? []);
    return (onlyUnread ? data.filter((n: any) => !n.read) : data) as T;
  }

  const markReadMatch = pathname.match(/^\/notifications\/([^/]+)\/read$/);
  if (markReadMatch && method === "PUT") {
    const current = getCurrentMockUser(token);
    if (!current) return { ok: true } as T;
    const list = mockState.notifications[current.id] ?? [];
    const found = list.find((n: any) => n.id === markReadMatch[1]);
    if (found) found.read = true;
    return { ok: true } as T;
  }

  if (pathname === "/notifications/read-all" && method === "PUT") {
    const current = getCurrentMockUser(token);
    if (!current) return { ok: true } as T;
    (mockState.notifications[current.id] ?? []).forEach((n: any) => {
      n.read = true;
    });
    return { ok: true } as T;
  }

  if (pathname === "/chat" && method === "POST") {
    return {
      answer:
        "Mock assistant: keep GST filing timely, maintain healthy UPI inflow consistency, and reduce concentration risk to improve score.",
    } as T;
  }

  if (pathname === "/guide-topics" && method === "GET") {
    return [
      { id: "score", title: "Understanding Your Score", video_url: "https://www.youtube.com/watch?v=GuyecpBm2Qs" },
      { id: "improve", title: "How to Improve Your Score", video_url: "https://www.youtube.com/watch?v=ka2raSNBPIs" },
      { id: "loan", title: "Applying for a Loan", video_url: "https://www.youtube.com/watch?v=cYCGs0DNAyw" },
    ] as T;
  }

  if (pathname === "/analytics/cohort-median" && method === "GET") {
    return {
      filing_compliance_rate: 0.86,
      gst_revenue_cv_90d: 0.23,
      upi_30d_inbound_count: 131,
      eway_bill_mom_growth: 0.07,
      longest_gap_days: 12,
      ewb_smurfing_index: 0.18,
      msme_category: query.get("msme_category") ?? "all",
    } as T;
  }

  throw new Error(`Mock endpoint not implemented: ${method} ${pathname}`);
}

async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (USE_MOCK) {
    return mockFetch<T>(path, options);
  }

  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const fetchOptions: RequestInit = {
    cache: "no-store",
    ...options,
    headers,
  };

  const res = await fetch(`${API_BASE}${path}`, fetchOptions);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as Record<string, string>).detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<{ token: string; user: Record<string, unknown> }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => apiFetch("/auth/logout", { method: "POST" }),
  me: () => apiFetch<Record<string, unknown>>("/auth/me"),
};

// Scores
export const scoreApi = {
  submit: (gstin: string) =>
    apiFetch<{ task_id: string; status: string }>("/score", {
      method: "POST",
      body: JSON.stringify({ gstin }),
    }),
  get: (taskId: string) => apiFetch<Record<string, unknown>>(`/score/${taskId}`),
  chat: (taskId: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(`/score/${taskId}/chat`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  health: () => apiFetch<Record<string, unknown>>("/health"),
};

type Params = Record<string, string | undefined>;

function buildQs(params?: Params): string {
  if (!params) return "";
  const p = new URLSearchParams(
    Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== ""),
    ) as Record<string, string>,
  );
  const s = p.toString();
  return s ? `?${s}` : "";
}

// Loan requests
export const loanApi = {
  list: (params?: Params) => apiFetch<unknown[]>(`/loan-requests${buildQs(params)}`),
  get: (lid: string) => apiFetch<Record<string, unknown>>(`/loan-requests/${lid}`),
  create: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/loan-requests", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getScore: (lid: string) => apiFetch<Record<string, unknown>>(`/loan-requests/${lid}/score`),
  decide: (lid: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(`/loan-requests/${lid}/decision`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

// Permissions
export const permApi = {
  list: (params?: Params) => apiFetch<unknown[]>(`/permissions${buildQs(params)}`),
  create: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/permissions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (pid: string, action: "approve" | "deny") =>
    apiFetch<Record<string, unknown>>(`/permissions/${pid}`, {
      method: "PUT",
      body: JSON.stringify({ action }),
    }),
};

// Disputes
export const disputeApi = {
  list: (params?: Params) => apiFetch<unknown[]>(`/disputes${buildQs(params)}`),
  create: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/disputes", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  assign: (did: string) =>
    apiFetch<Record<string, unknown>>(`/disputes/${did}/assign`, {
      method: "PUT",
    }),
  resolve: (did: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(`/disputes/${did}/resolve`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

// Reminders
export const reminderApi = {
  list: (gstin?: string) => apiFetch<unknown[]>(`/reminders${gstin ? `?gstin=${gstin}` : ""}`),
  complete: (rid: string) =>
    apiFetch<Record<string, unknown>>(`/reminders/${rid}/complete`, {
      method: "PUT",
    }),
};

// Banks
export const bankApi = {
  list: () => apiFetch<unknown[]>("/banks"),
  create: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/banks", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (bid: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(`/banks/${bid}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

// Admin
export const adminApi = {
  getExplorerGstins: () => apiFetch<any[]>("/explorer/gstins"),
  getExplorerDetails: (gstin: string) => apiFetch<any>(`/explorer/${gstin}/details`),
  getUsers: () => apiFetch<unknown[]>("/users"),
  createUser: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/users", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateUser: (uid: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(`/users/${uid}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  resetUserPassword: (uid: string) =>
    apiFetch<Record<string, unknown>>(`/users/${uid}/reset-password`, {
      method: "POST",
    }),
  getApiKeys: () => apiFetch<unknown[]>("/api-keys"),
  createApiKey: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/api-keys", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  revokeApiKey: (kid: string) =>
    apiFetch<Record<string, unknown>>(`/api-keys/${kid}/revoke`, {
      method: "PUT",
    }),
  rotateApiKey: (kid: string) =>
    apiFetch<Record<string, unknown>>(`/api-keys/${kid}/rotate`, {
      method: "PUT",
    }),
  getApiKeyUsage: (kid: string) => apiFetch<Record<string, unknown>>(`/api-keys/${kid}/usage`),
  getAuditLog: () => apiFetch<unknown[]>("/audit-log"),
  replayAudit: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/audit/replay", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getFraudAlerts: () => apiFetch<unknown[]>("/fraud-alerts"),
  getFraudAlert: (gstin: string) => apiFetch<Record<string, unknown>>(`/fraud-alerts/${gstin}`),
  getRiskThresholds: () => apiFetch<Record<string, unknown>>("/risk-thresholds"),
  updateRiskThresholds: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/risk-thresholds", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  getScoreHistory: (gstin: string) => apiFetch<unknown[]>(`/score-history?gstin=${gstin}`),
  getGlobalGraph: () => apiFetch<Record<string, unknown>>("/transactions/graph"),
  getGstinGraph: (gstin: string) => apiFetch<Record<string, unknown>>(`/transactions/${gstin}/graph`),
  getEwbDistribution: (gstin: string) =>
    apiFetch<Record<string, unknown>>(`/transactions/${gstin}/ewb-distribution`),
  getReceivablesGap: (gstin: string) =>
    apiFetch<Record<string, unknown>>(`/transactions/${gstin}/receivables-gap`),
};

// Notifications
export const notifApi = {
  list: (unread?: boolean) => apiFetch<unknown[]>(`/notifications${unread ? "?unread=true" : ""}`),
  markRead: (nid: string) =>
    apiFetch<Record<string, unknown>>(`/notifications/${nid}/read`, {
      method: "PUT",
    }),
  markAllRead: () =>
    apiFetch<Record<string, unknown>>("/notifications/read-all", {
      method: "PUT",
    }),
};

// MSME
export const msmeApi = {
  chat: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/chat", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getGuideTopics: () => apiFetch<unknown[]>("/guide-topics"),
};

// Analytics
export const analyticsApi = {
  getCohortMedian: (category: string = "all") =>
    apiFetch<Record<string, unknown>>(`/analytics/cohort-median?msme_category=${category}`),
};
