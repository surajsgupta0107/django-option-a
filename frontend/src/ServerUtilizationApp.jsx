import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  LayoutDashboard, Server, SlidersHorizontal, UserRound, Upload, Search,
  X, Mail, ChevronUp, ChevronDown, Download, CheckCircle2, AlertTriangle,
  FileSpreadsheet, Send, History, MessageSquare, ArrowUpDown, AlertCircle, RefreshCw,
} from "lucide-react";

/* ---------------------------------- FEATURE FLAGS ---------------------------------- */
// Toggle features on/off without deleting any code. Flip to false, rebuild
// (npm run build), redeploy — the tab, its nav entry, and its route all disappear
// together; nothing is torn out, so re-enabling later is a one-line change back.
const FEATURE_FLAGS = {
  ownerPortalTab: true, // To disable: set ownerPortalTab: false. To bring it back later: flip it to true.
};

/* ---------------------------------- API CLIENT ---------------------------------- */
// Built and served by Django itself (see /static/react + templates/react_app.html) —
// same-origin as the API, so a relative path just works with zero config. Still
// overridable from Settings for local `vite dev` usage against a different host/port.
const DEFAULT_API_BASE_URL = "/api";

function loadApiConfig() {
  try {
    return {
      baseUrl: localStorage.getItem("suo_api_base_url") || DEFAULT_API_BASE_URL,
      adminKey: localStorage.getItem("suo_admin_api_key") || "dev-admin-key-change-me",
    };
  } catch {
    return { baseUrl: DEFAULT_API_BASE_URL, adminKey: "dev-admin-key-change-me" };
  }
}
function saveApiConfig(baseUrl, adminKey) {
  try {
    localStorage.setItem("suo_api_base_url", baseUrl);
    localStorage.setItem("suo_admin_api_key", adminKey);
  } catch { /* localStorage unavailable — config just won't persist across reloads */ }
}

async function apiFetch(baseUrl, path, { method = "GET", adminKey, body, isForm = false } = {}) {
  const headers = {};
  if (adminKey) headers["X-API-Key"] = adminKey;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(`${baseUrl}${path}`, {
    method, headers, body: isForm ? body : (body ? JSON.stringify(body) : undefined),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || j.error || JSON.stringify(j); } catch { /* non-JSON error body */ }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

/* Maps the backend's snake_case Server representation onto the shape the UI already
   uses throughout this file, so the rest of the component tree needed no changes. */
function apiServerToInternal(s) {
  return {
    id: s.id,
    name: s.name,
    application: s.application,
    owner: s.owner,
    ownerEmail: s.owner_email,
    company: s.company,
    description: s.description,
    os: s.os,
    environment: s.environment,
    cpu: s.cpu_pct,
    memory: s.memory_pct,
    storage: s.storage_pct,
    cpuAllocated: s.cpu_allocated,
    memAllocated: s.mem_allocated_gb,
    storageAllocated: s.storage_allocated_gb,
    reclaimableVcpu: s.reclaimable_vcpu,
    reclaimableMemoryGb: s.reclaimable_memory_gb,
    status: s.status,
    remindersSent: s.reminders_sent,
    lastReminderDate: s.last_reminder_at ? new Date(s.last_reminder_at) : null,
    ownerResponded: s.owner_responded,
    ownerResponse: s.latest_response,
    comments: (s.responses || []).map(r => ({
      date: new Date(r.submitted_at),
      author: r.responded_by_name || s.owner,
      text: r.comment || RESPONSE_LABELS[r.decision] || "",
    })),
  };
}

function apiThresholdsToInternal(t) {
  return {
    cpu: t.cpu_threshold, memory: t.memory_threshold, storage: t.storage_threshold,
    mode: t.rule_mode,
    enabled: { cpu: t.cpu_enabled, memory: t.memory_enabled, storage: t.storage_enabled },
  };
}
function internalThresholdsToApi(local, emailTemplate) {
  return {
    cpu_threshold: local.cpu, memory_threshold: local.memory, storage_threshold: local.storage,
    cpu_enabled: local.enabled.cpu, memory_enabled: local.enabled.memory, storage_enabled: local.enabled.storage,
    rule_mode: local.mode, email_template: emailTemplate,
  };
}

/* ---------------------------------- THEME ---------------------------------- */
const FONT_LINK_ID = "suo-font-link";

const GlobalStyle = () => (
  <style>{`
    :root {
      --bg: #0A0E14;
      --surface: #11161F;
      --surface-2: #182130;
      --surface-3: #1F2A3B;
      --border: #253044;
      --text: #E8EEF5;
      --text-dim: #8DA0B5;
      --text-faint: #56687D;
      --accent: #FF7A3D;
      --accent-dim: #C75A26;
      --ok: #3FD6B0;
      --ok-dim: #1E5C4C;
      --warn: #F2BD46;
      --warn-dim: #6B5217;
      --crit: #FF6B6B;
      --crit-dim: #6B2626;
      --mono: 'IBM Plex Mono', ui-monospace, monospace;
      --sans: 'IBM Plex Sans', system-ui, sans-serif;
    }
    .suo-root {
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      min-height: 100vh;
      width: 100%;
      display: flex;
      font-size: 13px;
    }
    .suo-root * { box-sizing: border-box; }
    .suo-mono { font-family: var(--mono); }

    /* Sidebar */
    .suo-sidebar {
      width: 208px;
      flex-shrink: 0;
      background: var(--surface);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 18px 12px;
      gap: 4px;
    }
    .suo-brand {
      display: flex; align-items: center; gap: 8px;
      padding: 4px 8px 20px 8px;
    }
    .suo-brand-mark {
      width: 22px; height: 22px; border-radius: 4px;
      background: linear-gradient(135deg, var(--accent), var(--warn));
      flex-shrink: 0;
    }
    .suo-brand-text { font-weight: 600; font-size: 13.5px; letter-spacing: 0.2px; }
    .suo-brand-sub { font-size: 10px; color: var(--text-faint); font-family: var(--mono); }

    .suo-navitem {
      display: flex; align-items: center; gap: 10px;
      padding: 9px 10px; border-radius: 7px;
      color: var(--text-dim); cursor: pointer; font-size: 13px; font-weight: 500;
      border: 1px solid transparent;
      background: transparent;
      transition: background 120ms ease, color 120ms ease;
    }
    .suo-navitem:hover { background: var(--surface-2); color: var(--text); }
    .suo-navitem.active {
      background: var(--surface-2); color: var(--text);
      border-color: var(--border);
    }
    .suo-navitem.active .suo-navdot { background: var(--accent); }
    .suo-navdot { width: 5px; height: 5px; border-radius: 50%; background: transparent; margin-left: auto; }

    .suo-sidebar-foot {
      margin-top: auto; padding: 10px 8px; font-size: 10.5px; color: var(--text-faint);
      border-top: 1px solid var(--border); line-height: 1.5;
    }

    /* Main */
    .suo-main { flex: 1; min-width: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
    .suo-topbar {
      display: flex; align-items: center; justify-content: space-between;
      padding: 14px 24px; border-bottom: 1px solid var(--border);
      background: var(--surface); flex-shrink: 0;
    }
    .suo-topbar h1 { font-size: 16px; font-weight: 600; margin: 0; letter-spacing: 0.1px; }
    .suo-topbar-sub { font-size: 11.5px; color: var(--text-faint); margin-top: 2px; }
    .suo-content { flex: 1; overflow-y: auto; padding: 22px 24px 40px 24px; }

    .suo-btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 8px 13px; border-radius: 6px; font-size: 12.5px; font-weight: 500;
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
      cursor: pointer; transition: all 120ms ease; white-space: nowrap;
    }
    .suo-btn:hover { background: var(--surface-3); }
    .suo-btn-primary { background: var(--accent); border-color: var(--accent); color: #1A0D05; font-weight: 600; }
    .suo-btn-primary:hover { background: #FF8A54; }
    .suo-btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
    .suo-btn-ghost { background: transparent; border-color: transparent; }
    .suo-btn-ghost:hover { background: var(--surface-2); }
    .suo-btn-sm { padding: 5px 9px; font-size: 11.5px; }

    /* Cards */
    .suo-card {
      background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
      padding: 16px 18px;
    }
    .suo-kpi-label { font-size: 11px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600; }
    .suo-kpi-value { font-size: 26px; font-weight: 700; margin-top: 8px; font-family: var(--mono); letter-spacing: -0.5px; }
    .suo-kpi-note { font-size: 11px; color: var(--text-dim); margin-top: 6px; }

    /* Badges */
    .suo-badge {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 3px 8px; border-radius: 20px; font-size: 10.5px; font-weight: 600;
      font-family: var(--mono); text-transform: uppercase; letter-spacing: 0.3px;
    }
    .suo-badge-ok { background: var(--ok-dim); color: var(--ok); }
    .suo-badge-warn { background: var(--warn-dim); color: var(--warn); }
    .suo-badge-crit { background: var(--crit-dim); color: var(--crit); }
    .suo-badge-neutral { background: var(--surface-3); color: var(--text-dim); }

    /* LED gauge - signature element */
    .suo-led-row { display: flex; gap: 2px; align-items: center; }
    .suo-led {
      width: 6px; height: 12px; border-radius: 1px; background: var(--surface-3);
      border: 1px solid var(--border);
    }
    .suo-led.on-ok { background: var(--ok); border-color: var(--ok); }
    .suo-led.on-warn { background: var(--warn); border-color: var(--warn); }
    .suo-led.on-crit { background: var(--crit); border-color: var(--crit); }
    .suo-led-big { width: 10px; height: 22px; border-radius: 2px; }

    /* Table */
    .suo-table-wrap { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: var(--surface); }
    table.suo-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
    .suo-table th {
      text-align: left; padding: 10px 12px; background: var(--surface-2);
      color: var(--text-faint); font-size: 10.5px; text-transform: uppercase;
      letter-spacing: 0.5px; font-weight: 600; border-bottom: 1px solid var(--border);
      cursor: pointer; user-select: none; white-space: nowrap;
    }
    .suo-table th:hover { color: var(--text-dim); }
    .suo-table td { padding: 9px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
    .suo-table tr:last-child td { border-bottom: none; }
    .suo-table tr.suo-row:hover { background: var(--surface-2); cursor: pointer; }
    .suo-table tr.suo-row.selected { background: var(--surface-3); }

    .suo-input, .suo-select {
      background: var(--surface-2); border: 1px solid var(--border); color: var(--text);
      border-radius: 6px; padding: 7px 10px; font-size: 12.5px; font-family: var(--sans);
      outline: none;
    }
    .suo-input:focus, .suo-select:focus { border-color: var(--accent-dim); }
    .suo-input::placeholder { color: var(--text-faint); }

    .suo-search-wrap { position: relative; }
    .suo-search-wrap svg { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: var(--text-faint); }
    .suo-search-wrap input { padding-left: 30px; width: 230px; }

    /* Modal */
    .suo-modal-overlay {
      position: fixed; inset: 0; background: rgba(4,6,10,0.72);
      display: flex; align-items: center; justify-content: center; z-index: 50;
      padding: 24px;
    }
    .suo-modal {
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
      width: 100%; max-width: 680px; max-height: 88vh; overflow-y: auto;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    }
    .suo-modal-head {
      display: flex; align-items: flex-start; justify-content: space-between;
      padding: 18px 22px; border-bottom: 1px solid var(--border); position: sticky; top: 0;
      background: var(--surface); z-index: 2;
    }
    .suo-modal-body { padding: 20px 22px; }

    .suo-checkbox-row { display: flex; align-items: center; gap: 8px; }
    .suo-divider { height: 1px; background: var(--border); margin: 16px 0; }

    /* Toasts */
    .suo-toast-wrap { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 8px; z-index: 100; }
    .suo-toast {
      background: var(--surface-3); border: 1px solid var(--border); border-left: 3px solid var(--ok);
      border-radius: 8px; padding: 11px 16px; font-size: 12.5px; color: var(--text);
      box-shadow: 0 8px 24px rgba(0,0,0,0.4); min-width: 260px;
      animation: suo-toast-in 180ms ease;
    }
    @keyframes suo-toast-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

    .suo-chip {
      display: inline-flex; align-items: center; gap: 4px;
      background: var(--surface-2); border: 1px solid var(--border); border-radius: 20px;
      padding: 3px 10px; font-size: 11.5px; color: var(--text-dim);
    }

    .suo-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
    .suo-scrollbar::-webkit-scrollbar-track { background: transparent; }
    .suo-scrollbar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

    .suo-radio-card {
      border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px;
      cursor: pointer; display: flex; gap: 10px; align-items: flex-start;
      background: var(--surface-2); transition: border-color 120ms ease;
    }
    .suo-radio-card.active { border-color: var(--accent); background: var(--surface-3); }
    .suo-radio-card input { margin-top: 2px; accent-color: var(--accent); }

    .suo-drop {
      border: 1.5px dashed var(--border); border-radius: 10px; padding: 32px 20px;
      text-align: center; color: var(--text-dim); transition: all 150ms ease;
    }
    .suo-drop.drag { border-color: var(--accent); background: rgba(255,122,61,0.06); }
  `}</style>
);

function injectFonts() {
  if (typeof document !== "undefined" && !document.getElementById(FONT_LINK_ID)) {
    const link = document.createElement("link");
    link.id = FONT_LINK_ID;
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap";
    document.head.appendChild(link);
  }
}

/* ---------------------------------- CONSTANTS ---------------------------------- */
const RESPONSE_LABELS = {
  keep: "Hardware still required",
  downsize: "Can be downsized",
  decommission: "Can be decommissioned",
};

function fmtDate(d) {
  if (!d) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
function daysAgo(d) {
  if (!d) return Infinity;
  return Math.round((new Date() - d) / (1000 * 60 * 60 * 24));
}

function needsReminder(server, status) {
  if (status !== "Underutilized") return false;
  if (server.ownerResponded) return false;
  if (server.remindersSent === 0) return true;
  return daysAgo(server.lastReminderDate) > 30;
}
function ledClass(value, status) {
  if (status === "Underutilized") return "on-warn";
  if (status === "Overutilized") return "on-crit";
  return "on-ok";
}

function LedGauge({ value, status, big }) {
  if (value === null || value === undefined) {
    return <span className="suo-mono" style={{ fontSize: 11, color: "var(--text-faint)" }} title="Not tracked in this dataset">n/a</span>;
  }
  const segments = 10;
  const filled = Math.round((value / 100) * segments);
  const cls = ledClass(value, status);
  return (
    <div className="suo-led-row" title={`${value}%`}>
      {Array.from({ length: segments }).map((_, i) => (
        <div key={i} className={`suo-led ${big ? "suo-led-big" : ""} ${i < filled ? "on " + cls : ""}`} />
      ))}
    </div>
  );
}

function StatusBadge({ status }) {
  if (status === "Underutilized") return <span className="suo-badge suo-badge-warn"><AlertTriangle size={11} />Underutilized</span>;
  if (status === "Overutilized") return <span className="suo-badge suo-badge-crit"><AlertTriangle size={11} />Overutilized</span>;
  return <span className="suo-badge suo-badge-ok"><CheckCircle2 size={11} />Optimal</span>;
}

function downloadCSV(filename, rows) {
  const blob = new Blob([rows], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function toCSV(servers) {
  const header = ["Server Name", "Application", "Company", "Owner", "Owner Email", "Environment", "CPU %", "Memory %", "Storage %", "Status", "Reminders Sent", "Last Reminder", "Owner Response", "Comments"];
  const lines = [header.join(",")];
  servers.forEach(s => {
    const lastComment = s.comments.length ? s.comments[s.comments.length - 1].text.replace(/,/g, ";").replace(/\n/g, " ") : "";
    lines.push([
      s.name, `"${s.application}"`, `"${s.company || ""}"`, `"${s.owner}"`, s.ownerEmail, s.environment,
      s.cpu, s.memory, s.storage != null ? s.storage : "", s.status, s.remindersSent, s.lastReminderDate ? fmtDate(s.lastReminderDate) : "",
      s.ownerResponse ? RESPONSE_LABELS[s.ownerResponse] : "", `"${lastComment}"`,
    ].join(","));
  });
  return lines.join("\n");
}

const SAMPLE_TEMPLATE_CSV = `Server Name,Application,Owner,Owner Email,Environment,CPU Utilization %,Memory Utilization %,Storage Utilization %,Allocated vCPU,Allocated Memory GB,Allocated Storage GB
PRD-ORD-001,Order Management,Priya Nair,priya.nair@company.com,Production,14,22,18,8,32,500
DEV-CRM-002,CRM Suite,Marcus Chen,marcus.chen@company.com,Development,63,58,44,4,16,250`;

/* ---------------------------------- APP ---------------------------------- */
export default function App() {
  useEffect(() => { injectFonts(); }, []);

  const initialApiConfig = useMemo(() => loadApiConfig(), []);
  const [apiBaseUrl, setApiBaseUrl] = useState(initialApiConfig.baseUrl);
  const [adminKey, setAdminKey] = useState(initialApiConfig.adminKey);

  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [view, setView] = useState("dashboard");
  useEffect(() => {
    if (view === "portal" && !FEATURE_FLAGS.ownerPortalTab) setView("dashboard");
  }, [view]);
  const [toasts, setToasts] = useState([]);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);

  const [thresholds, setThresholds] = useState({
    cpu: 20, memory: 25, storage: 30, mode: "any",
    enabled: { cpu: true, memory: true, storage: false },
  });
  const [emailTemplate, setEmailTemplate] = useState("");

  // Servers view state
  const [search, setSearch] = useState("");
  const [filterApp, setFilterApp] = useState("All");
  const [filterCompany, setFilterCompany] = useState("All");
  const [filterOwner, setFilterOwner] = useState("All");
  const [filterEnv, setFilterEnv] = useState("All");
  const [filterStatus, setFilterStatus] = useState("All");
  const [needsReminderOnly, setNeedsReminderOnly] = useState(false);
  const [sortKey, setSortKey] = useState("cpu");
  const [sortDir, setSortDir] = useState("asc");
  const [selectedIds, setSelectedIds] = useState([]);
  const [modalServer, setModalServer] = useState(null);

  // Owner portal state
  const [portalSelectedId, setPortalSelectedId] = useState("");
  const [portalResponse, setPortalResponse] = useState("keep");
  const [portalComment, setPortalComment] = useState("");

  const fileInputRef = useRef(null);

  function pushToast(msg) {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, { id, msg }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3600);
  }

  async function fetchServers() {
    const data = await apiFetch(apiBaseUrl, "/servers");
    setServers(data.items.map(apiServerToInternal));
    setLastSyncedAt(new Date());
  }

  async function fetchThresholds() {
    const data = await apiFetch(apiBaseUrl, "/thresholds");
    setThresholds(apiThresholdsToInternal(data));
    setEmailTemplate(data.email_template);
  }

  async function loadAll(showSpinner = true) {
    if (showSpinner) setLoading(true);
    setLoadError(null);
    try {
      await Promise.all([fetchServers(), fetchThresholds()]);
    } catch (err) {
      setLoadError(err.message || "Could not reach the backend API");
    } finally {
      if (showSpinner) setLoading(false);
    }
  }

  useEffect(() => { loadAll(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [apiBaseUrl]);

  const withStatus = servers; // status is computed server-side and already attached per server

  const kpis = useMemo(() => {
    const total = withStatus.length;
    const under = withStatus.filter(s => s.status === "Underutilized");
    const reclaimCpu = under.reduce((a, s) => a + (s.reclaimableVcpu != null ? s.reclaimableVcpu : s.cpuAllocated), 0);
    const reclaimMemGb = under.reduce((a, s) => a + (s.reclaimableMemoryGb != null ? s.reclaimableMemoryGb : s.memAllocated * 0.5), 0);
    const reminded = withStatus.filter(s => s.remindersSent > 0);
    const responded = reminded.filter(s => s.ownerResponded);
    const escalations = under.filter(s => s.remindersSent >= 2 && !s.ownerResponded);
    return {
      total, underCount: under.length, underPct: total ? Math.round((under.length / total) * 100) : 0,
      reclaimCpu, reclaimMemGb: Math.round(reclaimMemGb),
      responseRate: reminded.length ? Math.round((responded.length / reminded.length) * 100) : 0,
      remindedCount: reminded.length,
      escalations: escalations.length,
    };
  }, [withStatus]);

  const statusPieData = useMemo(() => {
    const counts = { Optimal: 0, Underutilized: 0, Overutilized: 0 };
    withStatus.forEach(s => counts[s.status]++);
    return [
      { name: "Optimal", value: counts.Optimal, color: "#3FD6B0" },
      { name: "Underutilized", value: counts.Underutilized, color: "#F2BD46" },
      { name: "Overutilized", value: counts.Overutilized, color: "#FF6B6B" },
    ];
  }, [withStatus]);

  const environmentsInData = useMemo(() => Array.from(new Set(servers.map(s => s.environment))).sort(), [servers]);

  const envChartData = useMemo(() => {
    return environmentsInData.map(env => {
      const group = withStatus.filter(s => s.environment === env);
      const avg = (key) => {
        const vals = group.map(s => s[key]).filter(v => v != null);
        return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
      };
      return { env, CPU: avg("cpu"), Memory: avg("memory"), Storage: avg("storage") };
    });
  }, [withStatus, environmentsInData]);

  const appUnderChartData = useMemo(() => {
    const counts = {};
    withStatus.forEach(s => { if (s.status === "Underutilized") counts[s.application] = (counts[s.application] || 0) + 1; });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([app, count]) => ({ app: app.length > 16 ? app.slice(0, 15) + "…" : app, count }));
  }, [withStatus]);

  const applicationsInData = useMemo(() => Array.from(new Set(servers.map(s => s.application))).sort(), [servers]);
  const ownersInData = useMemo(() => Array.from(new Set(servers.map(s => s.owner))).sort(), [servers]);
  const companiesInData = useMemo(() => Array.from(new Set(servers.map(s => s.company).filter(Boolean))).sort(), [servers]);


  const filteredSorted = useMemo(() => {
    let list = withStatus.filter(s => {
      if (search && !(`${s.name} ${s.application} ${s.owner} ${s.company || ""}`.toLowerCase().includes(search.toLowerCase()))) return false;
      if (filterApp !== "All" && s.application !== filterApp) return false;
      if (filterCompany !== "All" && s.company !== filterCompany) return false;
      if (filterOwner !== "All" && s.owner !== filterOwner) return false;
      if (filterEnv !== "All" && s.environment !== filterEnv) return false;
      if (filterStatus !== "All" && s.status !== filterStatus) return false;
      if (needsReminderOnly && !needsReminder(s, s.status)) return false;
      return true;
    });
    list.sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (sortKey === "lastReminderDate") { av = av ? av.getTime() : -1; bv = bv ? bv.getTime() : -1; }
      if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return list;
  }, [withStatus, search, filterApp, filterCompany, filterOwner, filterEnv, filterStatus, needsReminderOnly, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }

  async function sendReminder(ids) {
    setSelectedIds([]);
    try {
      if (ids.length === 1) {
        await apiFetch(apiBaseUrl, `/reminders/server/${ids[0]}`, { method: "POST", adminKey, body: {} });
      } else {
        await apiFetch(apiBaseUrl, "/reminders/bulk", { method: "POST", adminKey, body: { server_ids: ids } });
      }
      pushToast(ids.length === 1 ? "Reminder email queued" : `Reminder emails queued for ${ids.length} servers`);
      await fetchServers();
    } catch (err) {
      pushToast(`Couldn't send reminder: ${err.message}`);
    }
  }

  async function submitOwnerFeedback() {
    if (!portalSelectedId) return;
    try {
      await apiFetch(apiBaseUrl, `/responses/submit-dev/${portalSelectedId}`, {
        method: "POST",
        body: { decision: portalResponse, comment: portalComment },
      });
      pushToast("Feedback submitted — infrastructure team notified");
      setPortalComment("");
      await fetchServers();
    } catch (err) {
      pushToast(`Couldn't submit feedback: ${err.message}`);
    }
  }

  async function handleFiles(fileList) {
    const file = fileList[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await apiFetch(apiBaseUrl, "/servers/upload", { method: "POST", adminKey, body: form, isForm: true });
      pushToast(`Imported ${result.imported} servers from ${file.name}${result.skipped ? ` (${result.skipped} skipped)` : ""}`);
      setUploadOpen(false);
      await fetchServers();
    } catch (err) {
      pushToast(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  }

  const portalServer = withStatus.find(s => String(s.id) === String(portalSelectedId));

  /* ---------------------------------- RENDER ---------------------------------- */
  return (
    <div className="suo-root">
      <GlobalStyle />
      <aside className="suo-sidebar">
        <div className="suo-brand">
          <div className="suo-brand-mark" />
          <div>
            <div className="suo-brand-text">RightSize</div>
            <div className="suo-brand-sub">infra utilization</div>
          </div>
        </div>
        {[
          { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
          { key: "servers", label: "Servers", icon: Server },
          { key: "portal", label: "Owner Portal", icon: UserRound, enabled: FEATURE_FLAGS.ownerPortalTab },
          { key: "settings", label: "Settings", icon: SlidersHorizontal },
        ].filter(item => item.enabled !== false).map(item => (
          <div key={item.key} className={`suo-navitem ${view === item.key ? "active" : ""}`} onClick={() => setView(item.key)}>
            <item.icon size={15} />
            {item.label}
            <span className="suo-navdot" />
          </div>
        ))}
        <div className="suo-sidebar-foot">
          API: <span className="suo-mono" style={{ color: "var(--text-dim)" }}>{apiBaseUrl}</span><br />
          {servers.length} servers loaded{lastSyncedAt ? ` · synced ${lastSyncedAt.toLocaleTimeString()}` : ""}<br /><br />
          Connected to a live backend — changes here persist for real.
        </div>
      </aside>

      <div className="suo-main">
        <div className="suo-topbar">
          <div>
            <h1>
              {view === "dashboard" && "Utilization Overview"}
              {view === "servers" && "Servers"}
              {view === "portal" && "Application Owner Portal"}
              {view === "settings" && "Settings"}
            </h1>
            <div className="suo-topbar-sub">
              {view === "dashboard" && "Organization-wide infrastructure efficiency"}
              {view === "servers" && `${filteredSorted.length} of ${servers.length} servers shown`}
              {view === "portal" && "Review a server and share whether the allocation is still needed"}
              {view === "settings" && "Configure what counts as underutilized"}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {view === "servers" && (
              <button className="suo-btn" onClick={() => downloadCSV("server-utilization-export.csv", toCSV(filteredSorted))}>
                <Download size={13} /> Export view
              </button>
            )}
            <button className="suo-btn" onClick={() => loadAll(false)} title="Refresh from API">
              <RefreshCw size={13} /> Refresh
            </button>
            <button className="suo-btn suo-btn-primary" onClick={() => setUploadOpen(true)}>
              <Upload size={13} /> Upload data
            </button>
          </div>
        </div>

        {loadError && (
          <div style={{ margin: "0 24px", marginTop: 14, padding: "10px 14px", background: "var(--crit-dim)", color: "var(--crit)", borderRadius: 8, fontSize: 12.5, display: "flex", alignItems: "center", gap: 8 }}>
            <AlertCircle size={14} /> Couldn't reach the API at {apiBaseUrl} — {loadError}. Check the backend is running and the URL in Settings, then hit Refresh.
          </div>
        )}

        <div className="suo-content suo-scrollbar">
          {loading ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", color: "var(--text-faint)", fontSize: 13 }}>
              Loading servers…
            </div>
          ) : (
          <>
          {view === "dashboard" && (
            <DashboardView kpis={kpis} statusPieData={statusPieData} envChartData={envChartData} appUnderChartData={appUnderChartData} withStatus={withStatus} onGoToServers={(statusFilter) => { setFilterStatus(statusFilter); setView("servers"); }} environmentsCount={environmentsInData.length} />
          )}

          {view === "servers" && (
            <ServersView
              filteredSorted={filteredSorted} search={search} setSearch={setSearch}
              filterApp={filterApp} setFilterApp={setFilterApp} applicationsInData={applicationsInData}
              filterCompany={filterCompany} setFilterCompany={setFilterCompany} companiesInData={companiesInData}
              filterOwner={filterOwner} setFilterOwner={setFilterOwner} ownersInData={ownersInData}
              filterEnv={filterEnv} setFilterEnv={setFilterEnv} environmentsInData={environmentsInData}
              filterStatus={filterStatus} setFilterStatus={setFilterStatus}
              needsReminderOnly={needsReminderOnly} setNeedsReminderOnly={setNeedsReminderOnly}
              sortKey={sortKey} sortDir={sortDir} toggleSort={toggleSort}
              selectedIds={selectedIds} setSelectedIds={setSelectedIds}
              setModalServer={setModalServer} sendReminder={sendReminder}
            />
          )}

          {view === "portal" && (
            <OwnerPortalView
              servers={withStatus} portalSelectedId={portalSelectedId} setPortalSelectedId={setPortalSelectedId}
              portalResponse={portalResponse} setPortalResponse={setPortalResponse}
              portalComment={portalComment} setPortalComment={setPortalComment}
              portalServer={portalServer} submitOwnerFeedback={submitOwnerFeedback}
            />
          )}

          {view === "settings" && (
            <SettingsView
              thresholds={thresholds} setThresholds={setThresholds} emailTemplate={emailTemplate} setEmailTemplate={setEmailTemplate}
              pushToast={pushToast} apiBaseUrl={apiBaseUrl} setApiBaseUrl={setApiBaseUrl} adminKey={adminKey} setAdminKey={setAdminKey}
              saveThresholdsToApi={async (local, template) => {
                await apiFetch(apiBaseUrl, "/thresholds", { method: "PUT", adminKey, body: internalThresholdsToApi(local, template) });
                await loadAll(false);
              }}
            />
          )}
          </>
          )}
        </div>
      </div>

      {modalServer && (
        <ServerModal server={withStatus.find(s => s.id === modalServer.id) || modalServer} onClose={() => setModalServer(null)} sendReminder={sendReminder} emailTemplate={emailTemplate} />
      )}

      {uploadOpen && (
        <UploadModal
          onClose={() => setUploadOpen(false)} dragActive={dragActive} setDragActive={setDragActive}
          handleFiles={handleFiles} fileInputRef={fileInputRef} uploading={uploading}
        />
      )}

      <div className="suo-toast-wrap">
        {toasts.map(t => <div key={t.id} className="suo-toast">{t.msg}</div>)}
      </div>
    </div>
  );
}

/* ---------------------------------- DASHBOARD VIEW ---------------------------------- */
function DashboardView({ kpis, statusPieData, envChartData, appUnderChartData, withStatus, onGoToServers, environmentsCount }) {
  const escalationList = withStatus.filter(s => s.status === "Underutilized" && s.remindersSent >= 2 && !s.ownerResponded).slice(0, 5);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
        <div className="suo-card" style={{ cursor: "pointer" }} onClick={() => onGoToServers("All")}>
          <div className="suo-kpi-label">Total Servers</div>
          <div className="suo-kpi-value">{kpis.total}</div>
          <div className="suo-kpi-note">Across {environmentsCount} environments</div>
        </div>
        <div className="suo-card" style={{ cursor: "pointer", borderColor: "var(--warn-dim)" }} onClick={() => onGoToServers("Underutilized")}>
          <div className="suo-kpi-label" style={{ color: "var(--warn)" }}>Underutilized</div>
          <div className="suo-kpi-value" style={{ color: "var(--warn)" }}>{kpis.underCount}</div>
          <div className="suo-kpi-note">{kpis.underPct}% of the fleet — candidates for review</div>
        </div>
        <div className="suo-card">
          <div className="suo-kpi-label">Reclaimable Capacity</div>
          <div className="suo-kpi-value">{kpis.reclaimCpu} <span style={{ fontSize: 14, color: "var(--text-faint)" }}>vCPU</span></div>
          <div className="suo-kpi-note">{kpis.reclaimMemGb.toLocaleString()} GB memory on underutilized hosts</div>
        </div>
        <div className="suo-card">
          <div className="suo-kpi-label">Owner Response Rate</div>
          <div className="suo-kpi-value">{kpis.responseRate}%</div>
          <div className="suo-kpi-note">{kpis.escalations > 0 ? <span style={{ color: "var(--crit)" }}>{kpis.escalations} need escalation</span> : `${kpis.remindedCount} owners reminded so far`}</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.4fr", gap: 14 }}>
        <div className="suo-card">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Fleet status</div>
          <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 8 }}>Based on current threshold rules</div>
          <ResponsiveContainer width="100%" height={210}>
            <PieChart>
              <Pie data={statusPieData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={3}>
                {statusPieData.map((d, i) => <Cell key={i} fill={d.color} stroke="none" />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#182130", border: "1px solid #253044", borderRadius: 8, fontSize: 12 }} itemStyle={{ color: "#E8EEF5" }} />
              <Legend wrapperStyle={{ fontSize: 11.5 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="suo-card">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Average utilization by environment</div>
          <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 8 }}>CPU / Memory / Storage</div>
          <ResponsiveContainer width="100%" height={210}>
            <BarChart data={envChartData} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#253044" vertical={false} />
              <XAxis dataKey="env" tick={{ fill: "#8DA0B5", fontSize: 11 }} axisLine={{ stroke: "#253044" }} tickLine={false} />
              <YAxis tick={{ fill: "#8DA0B5", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#182130", border: "1px solid #253044", borderRadius: 8, fontSize: 12 }} itemStyle={{ color: "#E8EEF5" }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Legend wrapperStyle={{ fontSize: 11.5 }} />
              <Bar dataKey="CPU" fill="#3FD6B0" radius={[3, 3, 0, 0]} />
              <Bar dataKey="Memory" fill="#F2BD46" radius={[3, 3, 0, 0]} />
              <Bar dataKey="Storage" fill="#FF7A3D" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1.1fr", gap: 14 }}>
        <div className="suo-card">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Applications with the most underutilized servers</div>
          <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 8 }}>Top opportunities for rightsizing conversations</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={appUnderChartData} layout="vertical" margin={{ top: 4, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#253044" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#8DA0B5", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
              <YAxis type="category" dataKey="app" tick={{ fill: "#8DA0B5", fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
              <Tooltip contentStyle={{ background: "#182130", border: "1px solid #253044", borderRadius: 8, fontSize: 12 }} itemStyle={{ color: "#E8EEF5" }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="count" fill="#F2BD46" radius={[0, 3, 3, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="suo-card">
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Needs escalation</div>
          <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 10 }}>2+ reminders sent, no response yet</div>
          {escalationList.length === 0 ? (
            <div style={{ color: "var(--text-faint)", fontSize: 12, padding: "20px 0", textAlign: "center" }}>Nothing waiting on escalation right now.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {escalationList.map(s => (
                <div key={s.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", background: "var(--surface-2)", borderRadius: 7 }}>
                  <div>
                    <div className="suo-mono" style={{ fontSize: 12, fontWeight: 600 }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{s.owner} · {s.remindersSent} reminders sent</div>
                  </div>
                  <span className="suo-badge suo-badge-crit">stalled</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------- SERVERS VIEW ---------------------------------- */
function ServersView(props) {
  const {
    filteredSorted, search, setSearch, filterApp, setFilterApp, applicationsInData,
    filterOwner, setFilterOwner, ownersInData, filterEnv, setFilterEnv, environmentsInData,
    filterCompany, setFilterCompany, companiesInData,
    filterStatus, setFilterStatus, needsReminderOnly, setNeedsReminderOnly,
    sortKey, sortDir, toggleSort, selectedIds, setSelectedIds, setModalServer, sendReminder,
  } = props;

  const allChecked = filteredSorted.length > 0 && selectedIds.length === filteredSorted.length;
  const eligibleForBulk = filteredSorted.filter(s => needsReminder(s, s.status));

  function toggleAll() {
    setSelectedIds(allChecked ? [] : filteredSorted.map(s => s.id));
  }
  function toggleOne(id) {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }
  function SortHeader({ label, k }) {
    return (
      <th onClick={() => toggleSort(k)}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
          {label} {sortKey === k ? (sortDir === "asc" ? <ChevronUp size={11} /> : <ChevronDown size={11} />) : <ArrowUpDown size={10} style={{ opacity: 0.35 }} />}
        </span>
      </th>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="suo-card" style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        <div className="suo-search-wrap">
          <Search size={13} />
          <input className="suo-input" placeholder="Search server, app, owner…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="suo-select" value={filterApp} onChange={e => setFilterApp(e.target.value)}>
          <option value="All">All applications</option>
          {applicationsInData.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        {companiesInData.length > 0 && (
          <select className="suo-select" value={filterCompany} onChange={e => setFilterCompany(e.target.value)}>
            <option value="All">All companies</option>
            {companiesInData.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
        <select className="suo-select" value={filterOwner} onChange={e => setFilterOwner(e.target.value)}>
          <option value="All">All owners</option>
          {ownersInData.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
        <select className="suo-select" value={filterEnv} onChange={e => setFilterEnv(e.target.value)}>
          <option value="All">All environments</option>
          {environmentsInData.map(e => <option key={e} value={e}>{e}</option>)}
        </select>
        <select className="suo-select" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="All">All statuses</option>
          <option>Underutilized</option>
          <option>Optimal</option>
          <option>Overutilized</option>
        </select>
        <label className="suo-checkbox-row" style={{ fontSize: 12, color: "var(--text-dim)", cursor: "pointer" }}>
          <input type="checkbox" checked={needsReminderOnly} onChange={e => setNeedsReminderOnly(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
          Needs reminder
        </label>
        {selectedIds.length > 0 && (
          <button className="suo-btn suo-btn-primary" style={{ marginLeft: "auto" }} onClick={() => sendReminder(selectedIds)}>
            <Send size={13} /> Send reminder ({selectedIds.length})
          </button>
        )}
        {selectedIds.length === 0 && eligibleForBulk.length > 0 && (
          <button className="suo-btn" style={{ marginLeft: "auto" }} onClick={() => sendReminder(eligibleForBulk.map(s => s.id))}>
            <Send size={13} /> Remind all underutilized ({eligibleForBulk.length})
          </button>
        )}
      </div>

      <div className="suo-table-wrap">
        <div style={{ maxHeight: "calc(100vh - 260px)", overflowY: "auto" }} className="suo-scrollbar">
          <table className="suo-table">
            <thead>
              <tr>
                <th style={{ width: 30 }}><input type="checkbox" checked={allChecked} onChange={toggleAll} style={{ accentColor: "var(--accent)" }} /></th>
                <SortHeader label="Server" k="name" />
                <SortHeader label="Application" k="application" />
                <SortHeader label="Company" k="company" />
                <SortHeader label="Owner" k="owner" />
                <SortHeader label="Environment" k="environment" />
                <SortHeader label="CPU" k="cpu" />
                <SortHeader label="Memory" k="memory" />
                <SortHeader label="Storage" k="storage" />
                <SortHeader label="Status" k="status" />
                <SortHeader label="Reminders" k="remindersSent" />
                <SortHeader label="Last Reminder" k="lastReminderDate" />
                <th>Response</th>
              </tr>
            </thead>
            <tbody>
              {filteredSorted.map(s => (
                <tr key={s.id} className={`suo-row ${selectedIds.includes(s.id) ? "selected" : ""}`} onClick={() => setModalServer(s)}>
                  <td onClick={e => e.stopPropagation()}><input type="checkbox" checked={selectedIds.includes(s.id)} onChange={() => toggleOne(s.id)} style={{ accentColor: "var(--accent)" }} /></td>
                  <td className="suo-mono" style={{ fontWeight: 600 }}>{s.name}</td>
                  <td>{s.application}</td>
                  <td style={{ color: s.company ? "var(--text)" : "var(--text-faint)" }}>{s.company || "—"}</td>
                  <td>{s.owner}</td>
                  <td><span className="suo-chip">{s.environment}</span></td>
                  <td><LedGauge value={s.cpu} status={s.status} /></td>
                  <td><LedGauge value={s.memory} status={s.status} /></td>
                  <td><LedGauge value={s.storage} status={s.status} /></td>
                  <td><StatusBadge status={s.status} /></td>
                  <td className="suo-mono">{s.remindersSent}</td>
                  <td className="suo-mono" style={{ color: "var(--text-dim)" }}>{fmtDate(s.lastReminderDate)}</td>
                  <td>
                    {s.ownerResponded
                      ? <span className="suo-badge suo-badge-neutral">{RESPONSE_LABELS[s.ownerResponse]}</span>
                      : (s.remindersSent > 0 ? <span style={{ color: "var(--text-faint)", fontSize: 11.5 }}>Awaiting reply</span> : <span style={{ color: "var(--text-faint)", fontSize: 11.5 }}>—</span>)}
                  </td>
                </tr>
              ))}
              {filteredSorted.length === 0 && (
                <tr><td colSpan={12} style={{ textAlign: "center", padding: 30, color: "var(--text-faint)" }}>No servers match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------- SERVER MODAL ---------------------------------- */
function ServerModal({ server, onClose, sendReminder, emailTemplate }) {
  const s = server;
  const eligibleReminder = needsReminder(s, s.status);
  const preview = emailTemplate
    .replace("{owner}", s.owner).replace("{server}", s.name).replace("{application}", s.application)
    .replace("{environment}", s.environment).replace("{cpu}", s.cpu).replace("{memory}", s.memory).replace("{storage}", s.storage);

  return (
    <div className="suo-modal-overlay" onClick={onClose}>
      <div className="suo-modal suo-scrollbar" onClick={e => e.stopPropagation()}>
        <div className="suo-modal-head">
          <div>
            <div className="suo-mono" style={{ fontSize: 16, fontWeight: 700 }}>{s.name}</div>
            <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
              {s.application} · {s.environment} · {s.owner}{s.company ? ` · ${s.company}` : ""}
            </div>
            {(s.description || s.os) && (
              <div style={{ fontSize: 11, color: "var(--text-faint)", marginTop: 3 }}>
                {s.description}{s.description && s.os ? " · " : ""}{s.os ? `OS: ${s.os}` : ""}
              </div>
            )}
          </div>
          <button className="suo-btn suo-btn-ghost suo-btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="suo-modal-body">
          <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
            <StatusBadge status={s.status} />
            {needsReminder(s, s.status) && <span className="suo-badge suo-badge-neutral">Needs reminder</span>}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            {[
              { label: "CPU", value: s.cpu, alloc: `${s.cpuAllocated} vCPU allocated`, reclaim: s.reclaimableVcpu != null ? `${s.reclaimableVcpu} vCPU reclaimable` : null },
              { label: "Memory", value: s.memory, alloc: `${s.memAllocated} GB allocated`, reclaim: s.reclaimableMemoryGb != null ? `${s.reclaimableMemoryGb} GB reclaimable` : null },
              { label: "Storage", value: s.storage, alloc: s.storageAllocated != null ? `${s.storageAllocated} GB allocated` : "Not tracked in this dataset", reclaim: null },
            ].map(m => (
              <div key={m.label} className="suo-card" style={{ padding: 12 }}>
                <div style={{ fontSize: 11, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: 0.4, fontWeight: 600 }}>{m.label}</div>
                <div className="suo-mono" style={{ fontSize: 20, fontWeight: 700, margin: "6px 0" }}>{m.value != null ? `${m.value}%` : "—"}</div>
                <LedGauge value={m.value} status={s.status} big />
                <div style={{ fontSize: 10.5, color: "var(--text-faint)", marginTop: 8 }}>{m.alloc}</div>
                {m.reclaim && <div style={{ fontSize: 10.5, color: "var(--warn)", marginTop: 2 }}>{m.reclaim}</div>}
              </div>
            ))}
          </div>

          <div className="suo-divider" />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}><History size={14} /> Reminder history</div>
            <button className="suo-btn suo-btn-primary suo-btn-sm" disabled={!eligibleReminder} onClick={() => sendReminder([s.id])}>
              <Mail size={12} /> Send reminder
            </button>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 4 }}>
            {s.remindersSent} sent · last {fmtDate(s.lastReminderDate)} · {s.ownerResponded ? "owner responded" : (s.remindersSent > 0 ? "awaiting response" : "no reminders yet")}
          </div>

          {eligibleReminder && (
            <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 8, padding: 10, fontSize: 11.5, color: "var(--text-dim)", marginTop: 8, whiteSpace: "pre-wrap" }}>
              {preview}
            </div>
          )}

          <div className="suo-divider" />
          <div style={{ fontWeight: 600, fontSize: 13, display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}><MessageSquare size={14} /> Owner comments</div>
          {s.comments.length === 0 ? (
            <div style={{ fontSize: 12, color: "var(--text-faint)" }}>No comments yet.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {s.comments.map((c, i) => (
                <div key={i} style={{ background: "var(--surface-2)", borderRadius: 8, padding: 10 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 600 }}>{c.author} <span style={{ color: "var(--text-faint)", fontWeight: 400 }}>· {fmtDate(c.date)}</span></div>
                  <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>{c.text}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------- OWNER PORTAL VIEW ---------------------------------- */
function OwnerPortalView({ servers, portalSelectedId, setPortalSelectedId, portalResponse, setPortalResponse, portalComment, setPortalComment, portalServer, submitOwnerFeedback }) {
  return (
    <div style={{ maxWidth: 640, display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="suo-card">
        <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10 }}>
          This simulates the simplified access an application owner would use — no infrastructure login required. Select the server you were reminded about.
        </div>
        <select className="suo-select" style={{ width: "100%" }} value={portalSelectedId} onChange={e => setPortalSelectedId(e.target.value)}>
          <option value="">Select a server…</option>
          {servers.filter(s => s.remindersSent > 0).map(s => (
            <option key={s.id} value={s.id}>{s.name} — {s.application} ({s.owner})</option>
          ))}
        </select>
      </div>

      {portalServer && (
        <>
          <div className="suo-card">
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>Current utilization</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
              {[["CPU", portalServer.cpu], ["Memory", portalServer.memory], ["Storage", portalServer.storage]].map(([label, val]) => (
                <div key={label}>
                  <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{label}</div>
                  <div className="suo-mono" style={{ fontSize: 18, fontWeight: 700, margin: "4px 0" }}>{val}%</div>
                  <LedGauge value={val} status={portalServer.status} />
                </div>
              ))}
            </div>
          </div>

          <div className="suo-card">
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12 }}>Is this allocation still needed?</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Object.entries(RESPONSE_LABELS).map(([key, label]) => (
                <label key={key} className={`suo-radio-card ${portalResponse === key ? "active" : ""}`}>
                  <input type="radio" name="resp" checked={portalResponse === key} onChange={() => setPortalResponse(key)} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12.5 }}>{label}</div>
                  </div>
                </label>
              ))}
            </div>
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 6 }}>Additional comments or justification</div>
              <textarea className="suo-input" style={{ width: "100%", minHeight: 80, resize: "vertical", fontFamily: "var(--sans)" }} value={portalComment} onChange={e => setPortalComment(e.target.value)} placeholder="e.g. This server supports a scheduled monthly job outside business hours…" />
            </div>
            <button className="suo-btn suo-btn-primary" style={{ marginTop: 12 }} onClick={submitOwnerFeedback}>Submit feedback</button>
          </div>

          {portalServer.comments.length > 0 && (
            <div className="suo-card">
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>Previous responses</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {portalServer.comments.map((c, i) => (
                  <div key={i} style={{ background: "var(--surface-2)", borderRadius: 8, padding: 10 }}>
                    <div style={{ fontSize: 11.5, fontWeight: 600 }}>{c.author} <span style={{ color: "var(--text-faint)", fontWeight: 400 }}>· {fmtDate(c.date)}</span></div>
                    <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>{c.text}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ---------------------------------- SETTINGS VIEW ---------------------------------- */
function SettingsView({ thresholds, setThresholds, emailTemplate, setEmailTemplate, pushToast, apiBaseUrl, setApiBaseUrl, adminKey, setAdminKey, saveThresholdsToApi }) {
  const [local, setLocal] = useState(thresholds);
  const [templateDraft, setTemplateDraft] = useState(emailTemplate);
  const [urlDraft, setUrlDraft] = useState(apiBaseUrl);
  const [keyDraft, setKeyDraft] = useState(adminKey);
  const [saving, setSaving] = useState(false);

  useEffect(() => { setLocal(thresholds); }, [thresholds]);
  useEffect(() => { setTemplateDraft(emailTemplate); }, [emailTemplate]);

  function update(field, value) { setLocal(prev => ({ ...prev, [field]: value })); }
  function updateEnabled(field, value) { setLocal(prev => ({ ...prev, enabled: { ...prev.enabled, [field]: value } })); }

  async function save() {
    setSaving(true);
    try {
      await saveThresholdsToApi(local, templateDraft);
      pushToast("Settings saved");
    } catch (err) {
      pushToast(`Couldn't save settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  function connect() {
    saveApiConfig(urlDraft, keyDraft);
    setApiBaseUrl(urlDraft);
    setAdminKey(keyDraft);
    pushToast("API connection updated");
  }

  return (
    <div style={{ maxWidth: 640, display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="suo-card">
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>API connection</div>
        <div style={{ fontSize: 11.5, color: "var(--text-faint)", marginBottom: 14 }}>Points at the Django backend from this same project (default port 8000). The admin key gates upload/reminder/threshold changes.</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 4 }}>API base URL</div>
            <input className="suo-input" style={{ width: "100%" }} value={urlDraft} onChange={e => setUrlDraft(e.target.value)} placeholder="http://localhost:8000/api" />
          </div>
          <div>
            <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 4 }}>Admin API key (X-API-Key)</div>
            <input className="suo-input" style={{ width: "100%" }} value={keyDraft} onChange={e => setKeyDraft(e.target.value)} type="password" />
          </div>
          <div><button className="suo-btn suo-btn-sm" onClick={connect}>Update connection</button></div>
        </div>
      </div>

      <div className="suo-card">
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Underutilization thresholds</div>
        <div style={{ fontSize: 11.5, color: "var(--text-faint)", marginBottom: 14 }}>A server is flagged "Underutilized" when its utilization falls below these limits.</div>

        {[
          { key: "cpu", label: "CPU utilization below" },
          { key: "memory", label: "Memory utilization below" },
          { key: "storage", label: "Storage utilization below" },
        ].map(row => (
          <div key={row.key} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <label className="suo-checkbox-row" style={{ width: 210, fontSize: 12.5 }}>
              <input type="checkbox" checked={local.enabled[row.key]} onChange={e => updateEnabled(row.key, e.target.checked)} style={{ accentColor: "var(--accent)" }} />
              {row.label}
            </label>
            <input type="range" min={0} max={100} value={local[row.key]} disabled={!local.enabled[row.key]} onChange={e => update(row.key, parseInt(e.target.value))} style={{ flex: 1, accentColor: "var(--accent)" }} />
            <span className="suo-mono" style={{ width: 44, textAlign: "right", fontWeight: 600 }}>{local[row.key]}%</span>
          </div>
        ))}

        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12.5, marginBottom: 8 }}>Flag as underutilized when</div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className={`suo-btn suo-btn-sm ${local.mode === "any" ? "suo-btn-primary" : ""}`} onClick={() => update("mode", "any")}>ANY enabled metric is below threshold</button>
            <button className={`suo-btn suo-btn-sm ${local.mode === "all" ? "suo-btn-primary" : ""}`} onClick={() => update("mode", "all")}>ALL enabled metrics are below threshold</button>
          </div>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-faint)", marginTop: 12 }}>Servers over 85% on any metric are separately flagged "Overutilized" — configurable server-side via `overutilized_ceiling`, not yet exposed in this screen.</div>
      </div>

      <div className="suo-card">
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Reminder email template</div>
        <div style={{ fontSize: 11.5, color: "var(--text-faint)", marginBottom: 10 }}>Placeholders: {"{owner} {server} {application} {environment} {cpu} {memory} {response_link}"}</div>
        <textarea className="suo-input" style={{ width: "100%", minHeight: 140, fontFamily: "var(--mono)", fontSize: 12, resize: "vertical" }} value={templateDraft} onChange={e => setTemplateDraft(e.target.value)} />
      </div>

      <div>
        <button className="suo-btn suo-btn-primary" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save settings"}</button>
      </div>
    </div>
  );
}

/* ---------------------------------- UPLOAD MODAL ---------------------------------- */
function UploadModal({ onClose, dragActive, setDragActive, handleFiles, fileInputRef, uploading }) {
  return (
    <div className="suo-modal-overlay" onClick={onClose}>
      <div className="suo-modal" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        <div className="suo-modal-head">
          <div style={{ fontWeight: 700, fontSize: 15 }}>Upload utilization data</div>
          <button className="suo-btn suo-btn-ghost suo-btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="suo-modal-body">
          {uploading ? (
            <div style={{ textAlign: "center", padding: "36px 0", color: "var(--text-dim)", fontSize: 13 }}>
              Uploading and parsing on the server…
            </div>
          ) : (
          <>
          <div
            className={`suo-drop ${dragActive ? "drag" : ""}`}
            onDragOver={e => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={e => { e.preventDefault(); setDragActive(false); handleFiles(e.dataTransfer.files); }}
          >
            <FileSpreadsheet size={26} style={{ marginBottom: 8, color: "var(--text-faint)" }} />
            <div style={{ fontSize: 13, marginBottom: 4 }}>Drag a CSV or Excel file here</div>
            <div style={{ fontSize: 11.5, color: "var(--text-faint)", marginBottom: 14 }}>or</div>
            <button className="suo-btn suo-btn-primary suo-btn-sm" onClick={() => fileInputRef.current?.click()}>Browse files</button>
            <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" style={{ display: "none" }} onChange={e => handleFiles(e.target.files)} />
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginTop: 14, lineHeight: 1.6 }}>
            Expected columns: <span className="suo-mono">Server Name, Application, Owner, Owner Email, Environment, CPU/Memory/Storage Utilization %</span>. Column names are matched flexibly — close variants are fine. This replaces the current dataset on the server (see backend README).
          </div>
          <button className="suo-btn suo-btn-sm" style={{ marginTop: 12 }} onClick={() => downloadCSV("sample-utilization-template.csv", SAMPLE_TEMPLATE_CSV)}>
            <Download size={12} /> Download sample template
          </button>
          </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------- OWNER RESPONSE PAGE (real, token-based flow) ---------------------------------- */
// Standalone page — no sidebar, no admin key, no other tabs. This is what an
// application owner actually lands on from the link in a reminder email
// (build_response_link() in servers_app/security.py), not the dev-mode dropdown
// under the main app's "Owner Portal" tab. Mounted directly by main.jsx when the URL
// path is /owner-response, bypassing <App/> entirely — see main.jsx for the routing.
export function OwnerResponsePage() {
  useEffect(() => { injectFonts(); }, []);

  const token = useMemo(() => new URLSearchParams(window.location.search).get("token"), []);
  const apiBaseUrl = useMemo(() => loadApiConfig().baseUrl, []);

  const [status, setStatus] = useState("loading"); // loading | error | ready | submitted
  const [errorMessage, setErrorMessage] = useState("");
  const [server, setServer] = useState(null);
  const [decision, setDecision] = useState("keep");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMessage("This link is missing its access token. Please use the link from the reminder email directly, rather than a bookmarked or retyped URL.");
      return;
    }
    (async () => {
      try {
        const data = await apiFetch(apiBaseUrl, `/responses/lookup?token=${encodeURIComponent(token)}`);
        setServer(apiServerToInternal(data));
        setStatus("ready");
      } catch (err) {
        setStatus("error");
        setErrorMessage((err.message || "").replace(/^\d+\s*/, "") || "Something went wrong loading this link.");
      }
    })();
  }, [token, apiBaseUrl]);

  async function submit() {
    setSubmitting(true);
    setSubmitError("");
    try {
      await apiFetch(apiBaseUrl, `/responses/submit?token=${encodeURIComponent(token)}`, {
        method: "POST", body: { decision, comment },
      });
      setStatus("submitted");
    } catch (err) {
      setSubmitError((err.message || "").replace(/^\d+\s*/, "") || "Couldn't submit that — please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="suo-root" style={{ alignItems: "flex-start", justifyContent: "center", padding: "40px 20px" }}>
      <GlobalStyle />
      <div style={{ width: "100%", maxWidth: 560 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24 }}>
          <div className="suo-brand-mark" />
          <div>
            <div className="suo-brand-text">RightSize</div>
            <div className="suo-brand-sub">application owner response</div>
          </div>
        </div>

        {status === "loading" && (
          <div className="suo-card" style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-dim)" }}>
            Loading server details…
          </div>
        )}

        {status === "error" && (
          <div className="suo-card" style={{ borderColor: "var(--crit-dim)" }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: "var(--crit)", marginBottom: 8 }}>Can't open this link</div>
            <div style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.6 }}>{errorMessage}</div>
          </div>
        )}

        {status === "submitted" && (
          <div className="suo-card" style={{ textAlign: "center", padding: "36px 20px" }}>
            <CheckCircle2 size={28} style={{ color: "var(--ok)", marginBottom: 12 }} />
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>Thanks — feedback submitted</div>
            <div style={{ fontSize: 12.5, color: "var(--text-dim)" }}>The infrastructure team has been notified. You can close this page.</div>
          </div>
        )}

        {status === "ready" && server && (
          <>
            <div className="suo-card">
              <div className="suo-mono" style={{ fontSize: 15, fontWeight: 700 }}>{server.name}</div>
              <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
                {server.application} · {server.environment} · {server.owner}{server.company ? ` · ${server.company}` : ""}
              </div>
              <div className="suo-divider" />
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>Current utilization</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                {[["CPU", server.cpu], ["Memory", server.memory], ["Storage", server.storage]].map(([label, val]) => (
                  <div key={label}>
                    <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{label}</div>
                    <div className="suo-mono" style={{ fontSize: 18, fontWeight: 700, margin: "4px 0" }}>{val != null ? `${val}%` : "—"}</div>
                    <LedGauge value={val} status={server.status} />
                  </div>
                ))}
              </div>
            </div>

            <div className="suo-card">
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12 }}>Is this allocation still needed?</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {Object.entries(RESPONSE_LABELS).map(([key, label]) => (
                  <label key={key} className={`suo-radio-card ${decision === key ? "active" : ""}`}>
                    <input type="radio" name="resp" checked={decision === key} onChange={() => setDecision(key)} />
                    <div style={{ fontWeight: 600, fontSize: 12.5 }}>{label}</div>
                  </label>
                ))}
              </div>
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginBottom: 6 }}>Additional comments or justification</div>
                <textarea
                  className="suo-input" style={{ width: "100%", minHeight: 80, resize: "vertical", fontFamily: "var(--sans)" }}
                  value={comment} onChange={e => setComment(e.target.value)}
                  placeholder="e.g. This server supports a scheduled monthly job outside business hours…"
                />
              </div>
              {submitError && <div style={{ color: "var(--crit)", fontSize: 12, marginTop: 10 }}>{submitError}</div>}
              <button className="suo-btn suo-btn-primary" style={{ marginTop: 12 }} onClick={submit} disabled={submitting}>
                {submitting ? "Submitting…" : "Submit feedback"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
