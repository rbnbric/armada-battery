"use strict";
let nativeLoadEpoch = 0;
let sessionEpoch = 0;
let requiresSignIn = false;
const state = {
  page: "cases",
  caseId: "", caseBrowse: false, nativeReceipt: null, receiptError: "", receiptId: "", caseFilter: "all", caseSearch: "",
  views: {}, caseOrder: [], inspectedKinds: {}, decisionChoices: {},
  nativeCases: null,
  nativeDetail: null,
  nativeError: "",
  decisionDrafts: {},
  revision: 0,
  plan: null,
  certificate: null,
  executionKey: null,
  busy: false,
  server: null,
  catalog: null,
  observations: null,
  trail: null,
  receipts: [],
  assurance: null,
  demonstrationFinding: null,
  errors: {},
  warning30: false,
  pending: null,
};
const byId = (id) => document.getElementById(id);
const LABELS = {
  cases: "Cases",
  overview: "Overview",
  tasks: "Tasks",
  webapps: "Web applications",
  rest: "REST APIs",
  permissions: "Permissions",
  security: "Security",
  os: "Operating system",
  logs: "Logs & audit",
  receipts: "Receipts",
  ledger: "Evidence ledger",
  rules: "Rules",
  request: "New request",
};
const STATES = {
  VALID: ["✓", "safe"],
  SAFE: ["✓", "safe"],
  VERIFIED_SUCCESS: ["✓", "safe"],
  STALE: ["◷", "watch"],
  WATCH: ["◷", "watch"],
  ACT: ["!", "act"],
  VERIFIED_FAILURE: ["✕", "act"],
  BLOCKED: ["⊘", "blocked"],
  BLOCKED_BEFORE_EXECUTION: ["⊘", "blocked"],
  FORBIDDEN: ["⊘", "blocked"],
  VERIFY: ["↻", "verify"],
  EXECUTED_UNVERIFIED: ["?", "verify"],
  OUTCOME_UNKNOWN: ["?", "unknown"],
  MALFORMED: ["?", "unknown"],
  CONFLICTED: ["?", "unknown"],
  UNSUPPORTED: ["?", "unknown"],
  UNAVAILABLE: ["?", "unknown"],
  UNKNOWN: ["?", "unknown"],
  CANCELLED: ["—", "unknown"],
};
const SCENARIO_LABELS = {
  intentional_change: "Intentional change",
  insufficient_privilege: "Insufficient privilege",
  failed_task_restraint: "Failed-task restraint",
  stale_evidence: "Stale evidence",
  ambiguous_transport: "Lost response without retry",
  wrong_rule_defense: "Unqualified rule",
  concurrent_change: "Concurrent target change",
  sensitive_values_absent: "Secret-free evidence",
};
function node(tag, content, cls = "") {
  const n = document.createElement(tag);
  if (content !== undefined) n.textContent = String(content);
  if (cls) n.className = cls;
  return n;
}
function badge(value) {
  const [glyph, cls] = STATES[value] || STATES.UNKNOWN;
  return node("span", `${glyph} ${value || "UNKNOWN"}`, `badge ${cls}`);
}
function announce(message, error = false) {
  byId(error ? "error-message" : "status-message").textContent = message;
}
function clearError() {
  byId("error-message").textContent = "";
}
function button(label, fn) {
  const b = node("button", label);
  b.type = "button";
  b.addEventListener("click", fn);
  return b;
}
function section(title, ...children) {
  const s = node("section", undefined, "section");
  s.append(node("h2", title), ...children);
  return s;
}
function empty(message) {
  return node("p", message, "empty");
}
function fields(values) {
  const dl = node("dl", undefined, "fields");
  Object.entries(values).forEach(([k, v]) => {
    dl.append(
      node("dt", k),
      node(
        "dd",
        v === null || v === undefined || v === ""
          ? "Unavailable / not recorded"
          : Array.isArray(v)
            ? v.length
              ? v.join(", ")
              : "None recorded"
            : typeof v === "object"
              ? JSON.stringify(v)
              : v,
      ),
    );
  });
  return dl;
}
function details(title, value) {
  const d = node("details");
  d.append(
    node("summary", title),
    node(
      "pre",
      typeof value === "string" ? value : JSON.stringify(value, null, 2),
    ),
  );
  return d;
}
function table(headers, rows) {
  const wrap = node("div", undefined, "table-wrap"),
    t = node("table"),
    thead = node("thead"),
    hr = node("tr"),
    body = node("tbody");
  headers.forEach((h) => {
    const th = node("th", h);
    th.scope = "col";
    hr.append(th);
  });
  thead.append(hr);
  rows.forEach((row) => {
    const tr = node("tr");
    row.forEach((value, i) => {
      const td = node("td");
      td.dataset.label = headers[i];
      td.append(
        value instanceof Node ? value : node("span", value ?? "Unavailable"),
      );
      tr.append(td);
    });
    body.append(tr);
  });
  t.append(thead, body);
  wrap.append(t);
  return wrap;
}
function digest(value) {
  if (!value) return node("span", "Unavailable", "quiet");
  const span = node("span", undefined, "digest");
  const disclosure = details(`${value.slice(0, 4)}…${value.slice(-4)}`, value);
  disclosure.append(
    button("Copy digest", async () => {
      try {
        await navigator.clipboard.writeText(value);
        announce("Digest copied.");
      } catch {
        announce("Copy unavailable. Expand the full digest to select it.");
      }
    }),
  );
  span.append(disclosure);
  return span;
}
function age(timestamp) {
  const ms = Date.parse(timestamp);
  if (!Number.isFinite(ms)) return "Age unavailable";
  const seconds = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  return seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
}
function evidenceQuality(value) {
  if (value?.quality === "VALID") {
    const captured = Date.parse(value.captured_at);
    if (!Number.isFinite(captured)) return "UNKNOWN";
    if (captured > Date.now() + 5000) return "CONFLICTED";
    if (Date.now() - captured > (value.freshness_seconds ?? 60) * 1000)
      return "STALE";
  }
  return value?.quality || "UNKNOWN";
}
function clearOperatorView() {
  requiresSignIn = true;
  sessionEpoch++;
  loadEpoch++;
  nativeLoadEpoch++;
  invalidate("Sign in again. Inspect Receipts for any unfinished operation before making another change.");
  for (const key of ["server", "catalog", "observations", "trail", "assurance", "demonstrationFinding", "nativeCases", "nativeDetail", "nativeReceipt", "pending"]) state[key] = null;
  state.receipts = [];
  state.nativeError = ""; state.receiptError = "";
  state.decisionDrafts = {};
  state.views = {}; state.inspectedKinds = {}; state.caseOrder = []; state.caseFilter = "all"; state.caseSearch = ""; state.decisionChoices = {}; paintedView = "";
  state.errors = {};
  state.busy = false;
  for (const id of ["page-content", "receipt", "task-detail"]) byId(id).replaceChildren();
  document.querySelectorAll("#intent-form input, #intent-form select, #intent-form textarea").forEach(field => {
    field.value = "";
    if (field.type === "checkbox") field.checked = false;
    if (field.tagName === "SELECT") field.replaceChildren();
  });
  byId("request-workspace").hidden = true;
  byId("page-content").hidden = false;
  byId("instance").textContent = "Sign-in required";
  byId("authority").textContent = "SIGNED OUT";
  byId("connection").textContent = "Operator sign-in required.";
  byId("page-state").textContent = "Operator sign-in required.";
  byId("prepare").disabled = true;
  byId("new-request").disabled = true;
  byId("refresh").disabled = false;
  byId("login-panel").hidden = false;
  // Storage is only a browser hint; inability to clear it cannot prevent logout.
  for (const name of ["localStorage", "sessionStorage"]) {
    try {
      const storage = globalThis[name];
      for (const key of Object.keys(storage)) if (key.startsWith("battery")) storage.removeItem(key);
    } catch { /* Blocked storage never grants access or prevents sign-out. */ }
  }
}
async function api(path, options = {}) {
  const epoch = sessionEpoch;
  if (state.server?.role === "observer" && options.method && options.method !== "GET" && !path.startsWith("/api/session")) throw new Error("This identity has read-only access.");
  const { timeoutMs = options.method && options.method !== "GET" ? 30000 : 8000, ...request } = options;
  const controller = new AbortController();
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      const error = new Error("Request timed out; no outcome was established.");
      error.code = "TIMEOUT";
      reject(error);
    }, timeoutMs);
  });
  const operation = async () => {
    const response = await fetch(path, { ...request, signal: controller.signal });
    if (epoch !== sessionEpoch) throw new Error("Operator session changed; response discarded.");
    let data;
    try { data = await response.json(); }
    catch { throw new Error("Response was unreadable; no outcome was established."); }
    if (epoch !== sessionEpoch) throw new Error("Operator session changed; response discarded.");
    if (response.status === 401) {
      clearOperatorView();
      throw new Error("Operator sign-in required.");
    }
    if (!response.ok) {
      const error = new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status}). No outcome established.`);
      error.httpStatus = response.status;
      throw error;
    }
    return data;
  };
  try { return await Promise.race([operation(), timeout]); }
  finally { clearTimeout(timer); }
}

function stage(name) {
  document.querySelectorAll("[data-stage]").forEach((n) => {
    if (n.dataset.stage === name) n.setAttribute("aria-current", "step");
    else n.removeAttribute("aria-current");
  });
}
function invalidate(
  message = "Request changed. Prepare it again before execution.",
) {
  state.revision++;
  state.certificate = null;
  state.plan = null;
  state.executionKey = null;
  state.warning30 = false;
  byId("execute").disabled = true;
  byId("action-title").textContent = "Preparation required";
  byId("action-copy").textContent = message;
  byId("certificate-time").textContent = "No current authorization.";
  byId("contract").replaceChildren();
  byId("finding-title").textContent = "Request not evaluated";
  byId("finding-copy").textContent = message;
  byId("blockers").replaceChildren(
    node("p", "? UNKNOWN — prepare the current request.", "unknown"),
  );
  byId("rule").replaceChildren();
  byId("plan-evidence").replaceChildren();
  stage("prepare");
}
// View memory is scoped to this signed-in page. Only the destination name is persisted.
let paintedView = "";
function viewKey() { return `${state.page}/${state.page === "cases" ? (state.caseId || (state.caseBrowse ? "all" : "")) : state.page === "receipts" ? state.receiptId : ""}`; }
function rememberView() {
  const root = byId("page-content");
  if (!paintedView || !root.querySelectorAll || requiresSignIn) return;
  const focused = document.activeElement;
  state.views[paintedView] = {
    open: [...root.querySelectorAll("details")].filter(e => e.open).map(e => e.querySelector("summary")?.textContent),
    scroll: window.scrollY || 0,
    focus: root.contains(focused) ? {id: focused.id, text: focused.textContent, tag: focused.tagName, start: focused.selectionStart, end: focused.selectionEnd} : null,
  };
}
function restoreView() {
  const saved = state.views[viewKey()], root = byId("page-content");
  if (!saved || !root.querySelectorAll) return;
  for (const el of root.querySelectorAll("details")) el.open = saved.open.includes(el.querySelector("summary")?.textContent);
  const f = saved.focus;
  if (f) {
    const el = f.id ? byId(f.id) : [...root.querySelectorAll("button,summary,a")].find(e => e.tagName === f.tag && e.textContent === f.text);
    if (el) { el.focus({preventScroll:true}); if (el.setSelectionRange && f.start != null) el.setSelectionRange(f.start, f.end); }
  }
  window.scrollTo?.(0, saved.scroll);
}
function parseRoute(hash) {
  const match = /^#([a-z]+)(?:\/([A-Za-z0-9_.:-]{1,160}))?$/.exec(hash || "");
  return match && LABELS[match[1]] ? {page:match[1], id:match[2] || ""} : null;
}
function routeHash() { return `#${viewKey().replace(/\/$/, "")}`; }
function navigate(page, focus = true, id = "", historyMode = "push") {
  if (!LABELS[page]) page = "cases";
  rememberView();
  const previous = viewKey();
  state.page = page;
  if (page === "cases") { state.caseBrowse = id === "all"; state.caseId = state.caseBrowse ? "" : id; }
  if (page === "receipts") state.receiptId = id;
  if (previous !== viewKey()) { byId("status-message").textContent = ""; clearError(); }
  if (window.history && historyMode !== "none" && window.location?.hash !== routeHash())
    window.history[historyMode === "replace" ? "replaceState" : "pushState"](null, "", routeHash());
  try { localStorage.setItem("battery-last-page", page); } catch { /* Optional location hint. */ }
  byId("page-title").textContent = LABELS[page];
  if (byId("nav-current")) byId("nav-current").textContent = LABELS[page];
  byId("request-workspace").hidden = page !== "request";
  byId("page-content").hidden = page === "request";
  document.querySelectorAll("[data-page]").forEach(b => {
    if (b.dataset.page === page) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  byId("navigation").dataset.open = "false";
  document.querySelector(".nav-toggle").setAttribute("aria-expanded", "false");
  paintedView = "";
  renderPage();
  if (!state.views[viewKey()] && focus) { byId("workspace").focus({preventScroll:true}); window.scrollTo?.(0,0); }
  if (page === "cases" && !requiresSignIn) loadNativeCases(state.caseId);
  if (page === "receipts" && id && !requiresSignIn) openReceipt(id, byId("page-content"));
}
function openCase(id) { navigate("cases", true, id); }
function initializeRoute() {
  if (!window.location) return;
  let route = parseRoute(window.location.hash);
  if (!route) { let page; try { page = localStorage.getItem("battery-last-page"); } catch {} route = {page: LABELS[page] ? page : "cases", id:""}; }
  navigate(route.page, false, route.id, "replace");
}
window.addEventListener?.("popstate", () => { const r = parseRoute(window.location.hash); if(r) navigate(r.page, true, r.id, "none"); });
window.addEventListener?.("hashchange", () => { const r = parseRoute(window.location.hash); if(r && `#${r.page}${r.id ? "/"+r.id : ""}` !== routeHash()) navigate(r.page, true, r.id, "none"); });
window.addEventListener?.("keydown", event => {
  if (event.key === "Escape" && byId("navigation").dataset.open === "true") {
    byId("navigation").dataset.open = "false";
    const menu = document.querySelector(".nav-toggle"); menu.setAttribute("aria-expanded","false"); menu.focus();
  }
});
function startRequest(workflow = "run", taskId = null) {
  byId("workflow").value = workflow;
  if (taskId !== null) byId("task").value = String(taskId);
  showWorkflow();
  navigate("request");
  byId("workflow").focus();
}
function fillSelect(id, items, key, label = key) {
  const el = byId(id),
    old = el.value;
  el.replaceChildren();
  (items || []).forEach((item) => {
    const option = node("option", key ? item[label] || item[key] : item);
    option.value = String(key ? item[key] : item);
    if (item.Description) option.dataset.detail = item.Description;
    el.append(option);
  });
  if ([...el.options].some((o) => o.value === old)) el.value = old;
}
async function showTask() {
  const id = byId("task").value;
  byId("task-detail").replaceChildren(node("span", "Loading task definition…"));
  if (!id) {
    byId("task-detail").textContent =
      "No task is available from this collector.";
    return;
  }
  try {
    const result = await api(`/api/tasks/${encodeURIComponent(id)}`);
    if (byId("task").value !== id) return;
    byId("task-detail").replaceChildren(
      fields({
        "Task class": result.task.TaskClass,
        Namespace: result.task.NameSpace,
        Description: result.task.Description,
        Observed: result.captured_at,
      }),
      details("Review task definition and runtime state", result.task),
    );
  } catch (error) {
    if (byId("task").value === id)
      byId("task-detail").textContent = error.message;
  }
}
function showWorkflow() {
  const workflow = byId("workflow").value;
  document
    .querySelectorAll(".workflow-fields")
    .forEach(
      (g) => (g.hidden = !g.dataset.workflow.split(" ").includes(workflow)),
    );
  invalidate();
  if (["run", "schedule"].includes(workflow)) showTask();
}
function showRule(rule, root = byId("rule")) {
  root.replaceChildren();
  if (!rule) {
    root.append(empty("Rule observation unavailable."));
    return;
  }
  root.append(
    fields({
      Policy: `${rule.id} · version ${rule.version}`,
      Validation: rule.validation,
      "Execution requires": rule.minimum_execution_validation,
      Rationale: rule.rationale,
    }),
    details("Assumptions", rule.assumptions),
    details("Counterexamples", rule.counterexamples),
    details("Recorded live validations", rule.live_validations),
  );
}
let loadEpoch = 0;
async function load() {
  const epoch = ++loadEpoch;
  byId("refresh").disabled = true;
  clearError();
  const sources = {
    server: "/api/state",
    catalog: "/api/catalog",
    observations: "/api/observations",
    trail: "/api/evidence?limit=100",
    assurance: "/api/assurance",
    demonstrationFinding: "/api/findings/demonstration",
    receipts: "/api/receipts",
  };
  state.errors = {};
  try {
    const results = await Promise.allSettled(Object.entries(sources).map(async ([key, url]) => {
      try {
        const value = await api(url);
        if (epoch !== loadEpoch) return;
        state[key] = key === "receipts" ? value.receipts : value;
        delete state.errors[key];
      } catch (error) {
        if (epoch !== loadEpoch) return;
        state[key] = key === "receipts" ? [] : null;
        state.errors[key] = error.message;
      }
      if (epoch === loadEpoch) renderCollectors(key);
    }));
    const failure = results.find(result => result.status === "rejected");
    if (failure && epoch === loadEpoch) throw failure.reason;
  } finally {
    if (epoch === loadEpoch) {
      byId("refresh").disabled = false;
      if (Object.keys(state.errors).length)
        announce(`Some collectors are unavailable: ${Object.keys(state.errors).join(", ")}. Working areas remain available.`);
      if (state.pending) showPending();
    }
  }
}
function renderCollectors(changed) {
  const server = state.server;
  const readOnly = server?.role === "observer";
  byId("prepare").disabled = readOnly;
  byId("new-request").disabled = readOnly;
  byId("instance").textContent = server?.instance || "Instance unavailable";
  byId("adapter").textContent = server
    ? server.mode === "synthetic" ? "Simulated operation" : "Connected IRIS"
    : "CONTEXT UNKNOWN";
  byId("adapter").className = "badge";
  byId("authority").textContent = server
    ? server.mode === "synthetic"
      ? "Simulation actions only"
      : server.changes_enabled
        ? "Changes enabled"
        : "Read-only observations"
    : "AUTHORITY UNKNOWN";
  if (readOnly) byId("authority").textContent = "READ-ONLY IDENTITY";
  byId("authority").className =
    "badge " +
    (server?.mode === "synthetic"
      ? "safe"
      : server?.changes_enabled
        ? "watch"
        : "unknown");
  byId("connection").textContent = server
    ? `${server.server.version} · ${server.mode === "synthetic" ? "Fixture identity" : "IRIS authority"}: ${server.server.username} · Battery operator: ${server.operator} · ${server.access_mode}`
    : state.errors.server || "Connection unavailable";
  if (changed === "server" && !server?.changes_enabled && state.certificate)
    invalidate("Changes are disabled or authority is unavailable.");
  const c = state.catalog;
  if (c && changed === "catalog") {
    fillSelect("task", c.tasks, "Id", "Name");
    fillSelect("namespace", c.namespaces, null);
    fillSelect("resource", c.resources, "Name");
    fillSelect("username", c.users, "Name");
    fillSelect("role-name", c.roles, "Name");
  }
  updateFreshness();
  if (!(state.page === "receipts" && state.receiptId)) renderPage();
}

function updateFreshness() {
  byId("freshness").textContent = state.server
    ? `Instance observed ${age(state.server.captured_at)}`
    : "No current instance observation";
  document.querySelectorAll("[data-evidence-quality]").forEach((n) => {
    const current = badge(
      evidenceQuality({
        quality: n.dataset.evidenceQuality,
        captured_at: n.dataset.capturedAt,
        freshness_seconds: Number(n.dataset.freshnessSeconds),
      }),
    );
    n.className = current.className;
    n.textContent = current.textContent;
  });
  document.querySelectorAll("[data-evidence-age]").forEach((n) => {
    n.textContent = `${age(n.dataset.evidenceAge)} · stale after ${n.dataset.freshnessSeconds}s`;
  });
  const summary = byId("observation-summary");
  if (summary && state.observations) {
    const areas = Object.values(state.observations.areas);
    summary.textContent = `${areas.length} observation areas returned; ${areas.filter((a) => evidenceQuality(a) !== "VALID").length} are unavailable, stale or otherwise unresolved. Instance health has not been evaluated.`;
  }
  document.querySelectorAll("[data-quality]").forEach((n) => {
    const k = n.dataset.quality;
    const value = state.catalog?.quality?.[k] || state.observations?.areas?.[k];
    n.replaceChildren(badge(evidenceQuality(value)));
  });
}
function observedTable(names) {
  const areas = state.observations?.areas;
  if (!areas)
    return empty(
      state.errors.observations || "No observations have been collected.",
    );
  return table(
    ["Area", "Quality", "Observation / completeness", "Source", "Age"],
    names
      .filter((n) => areas[n])
      .map((name) => {
        const a = areas[name];
        const info = node("div");
        info.append(
          node("span", a.summary),
          node(
            "small",
            `Completeness: ${a.complete === true ? "complete" : a.complete === false ? "partial" : "not established"}`,
          ),
        );
        if (a.values !== undefined && a.values !== null)
          info.append(details("Inspect observed values", a.values));
        const qualityBadge = badge(evidenceQuality(a));
        qualityBadge.dataset.evidenceQuality = a.quality;
        qualityBadge.dataset.capturedAt = a.captured_at;
        qualityBadge.dataset.freshnessSeconds = a.freshness_seconds ?? 60;
        const ageNode = node(
          "span",
          `${age(a.captured_at)} · stale after ${a.freshness_seconds ?? 60}s`,
        );
        ageNode.dataset.evidenceAge = a.captured_at;
        ageNode.dataset.freshnessSeconds = a.freshness_seconds ?? 60;
        return [
          name === "tls" ? "TLS" : name.charAt(0).toUpperCase() + name.slice(1),
          qualityBadge,
          info,
          a.source,
          ageNode,
        ];
      }),
  );
}
function receiptTable(items) {
  if (!items.length)
    return empty(
      state.errors.receipts ||
        "No attempts recorded. Preparation alone does not execute a change.",
    );
  return table(
    ["Result", "Target", "Started (UTC)", "Receipt"],
    items.map((r) => [
      badge(r.status),
      r.target,
      r.started_at,
      button(r.id.slice(0, 8), () => openReceipt(r.id)),
    ]),
  );
}
function collection(name) {
  const c = state.catalog;
  const q = c?.quality?.[name];
  if (!c)
    return { rows: [], notice: state.errors.catalog || "Catalog unavailable." };
  return {
    rows: c[name] || [],
    notice:
      q?.quality === "VALID"
        ? null
        : `${q?.quality || "UNKNOWN"}: ${q?.detail || "No usable collection."}`,
  };
}
function assuranceProof() {
  const proof = node("section", undefined, "proof-result");
  const available = state.assurance?.available;
  const passed = state.assurance?.passed ?? 0;
  const total = state.assurance?.total ?? 0;
  proof.append(
    node("p", "THE CONCRETE RESULT", "eyebrow"),
    node(
      "h2",
      available
        ? `${passed}/${total} failure-mode checks contained`
        : "Live observations are separated from synthetic assurance",
    ),
    node(
      "p",
      available
        ? "When a task request loses its response, Battery dispatches once, records the uncertainty, and verifies the original attempt from fresh evidence. It does not send the change again."
        : state.assurance?.detail ||
            state.errors.assurance ||
            "Assurance evidence is unavailable.",
      "proof-lede",
    ),
  );
  if (available) {
    const metrics = node("div", undefined, "proof-metrics");
    [
      ["1", "dispatch"],
      ["0", "automatic retries"],
      [`${passed}/${total}`, "checks passed"],
    ].forEach(([value, label]) => {
      const item = node("div");
      item.append(node("strong", value), node("span", label));
      metrics.append(item);
    });
    proof.append(metrics);
    if (state.assurance.scenarios?.length) {
      const list = node("ul", undefined, "proof-checks");
      state.assurance.scenarios.forEach((scenario) => {
        const item = node("li");
        item.append(
          badge(scenario.passed ? "VERIFIED_SUCCESS" : "VERIFIED_FAILURE"),
          node("strong", SCENARIO_LABELS[scenario.name] || scenario.name),
          node("span", scenario.detail),
        );
        list.append(item);
      });
      const disclosure = node("details", undefined, "proof-disclosure");
      disclosure.append(node("summary", "Inspect all deterministic checks"), list);
      proof.append(disclosure);
    }
    const actions = node("div", undefined, "proof-actions");
    actions.append(
      button("Try the one-dispatch proof", () => startRequest("run", 17)),
      node(
        "span",
        "About one minute · synthetic target · no credentials required",
        "quiet",
      ),
    );
    proof.append(actions);
  }
  return proof;
}
function findingCard() {
  const finding = state.demonstrationFinding;
  const card = node("section", undefined, "section finding-card");
  card.append(node("p", "SYNTHETIC · OBSERVED TASK HISTORY", "eyebrow"));
  if (!finding?.available) {
    card.append(
      node("h2", "Demonstration finding unavailable"),
      empty(finding?.detail || state.errors.demonstrationFinding || "No finding observation returned."),
    );
    return card;
  }
  const heading = node("div", undefined, "finding-card-heading");
  heading.append(
    node("h2", finding.summary),
    badge(finding.status === "RESOLVED" ? "VERIFIED_SUCCESS" : finding.status === "OPEN" ? "ACT" : "VERIFY"),
  );
  card.append(
    heading,
    node("p", finding.detail),
    fields({
      "Observed task": finding.task_name,
      "History rows": finding.history_count,
      "Observed at": finding.captured_at,
      "Battery receipt": finding.receipt_id || "None recorded",
    }),
  );
  if (finding.status === "OPEN")
    card.append(button("Review this task", () => startRequest("run", finding.task_id)));
  if (finding.receipt_id)
    card.append(button("Inspect receipt", () => openReceipt(finding.receipt_id)));
  return card;
}
function renderPage() {
  if (requiresSignIn) return;
  if (paintedView === viewKey()) rememberView();
  renderPageContent();
  paintedView = viewKey();
  restoreView();
}
function renderPageContent() {
  const root = byId("page-content");
  root.replaceChildren();
  byId("page-state").textContent =
    state.page === "request"
      ? "Prepare → authorize → execute → verify"
      : state.server
        ? `${state.server.mode === "synthetic" ? "Synthetic demonstration" : "IRIS observations"} · ${age(state.server.captured_at)}`
        : "Connection unavailable";
  if (state.page === "request") return;
  const all = Object.keys(state.observations?.areas || {});
  if (state.page === "overview") {
    const unknown = all.filter(
      (k) => evidenceQuality(state.observations.areas[k]) !== "VALID",
    ).length;
    const summary = node(
      "p",
      `${all.length} observation areas returned; ${unknown} are unavailable, stale or otherwise unresolved. Instance health has not been evaluated.`,
      "quiet",
    );
    summary.id = "observation-summary";
    const observationDisclosure = node("details");
    observationDisclosure.append(
      node("summary", `Inspect ${all.length} collected areas`),
      observedTable(all),
    );
    observationDisclosure.open =
      !window.matchMedia("(max-width: 600px)").matches;
    root.append(
      findingCard(),
      assuranceProof(),
      section("Operational evidence", summary, observationDisclosure),
      section("Recent attempts", receiptTable(state.receipts.slice(0, 5))),
      empty(
        "The checks above qualify the synthetic engine only. Live IRIS remains read-only by default; readiness, capacity and scheduled assurance obligations are outside this release.",
      ),
    );
  } else if (state.page === "tasks") {
    const c = collection("tasks");
    if (c.notice) root.append(empty(c.notice));
    root.append(
      node(
        "p",
        "Inspect the task definition before preparing a run or schedule change.",
        "quiet",
      ),
    );
    root.append(
      table(
        ["Task", "Description", "Actions"],
        c.rows.map((t) => {
          const actions = node("div", undefined, "toolbar");
          actions.append(
            button("Run once", () => startRequest("run", t.Id)),
            button("Schedule", () => startRequest("schedule", t.Id)),
          );
          return [t.Name, t.Description || "Description not supplied", actions];
        }),
      ),
    );
  } else if (state.page === "webapps") {
    const c = collection("web_apps");
    root.append(
      button("Create REST application", () => startRequest("webapp")),
    );
    if (c.notice) root.append(empty(c.notice));
    root.append(
      table(
        ["Application", "Observed metadata"],
        c.rows.map((a) => [
          a.Name || a.name || "Unnamed record",
          details("Inspect metadata", a),
        ]),
      ),
      empty(
        "Configuration readback verifies configuration only. Functional endpoint probing is not implemented.",
      ),
    );
  } else if (state.page === "permissions") {
    const users = collection("users"),
      roles = collection("roles");
    root.append(button("Give a reviewed role", () => startRequest("role")));
    [users, roles].forEach((c) => {
      if (c.notice) root.append(empty(c.notice));
    });
    root.append(
      section(
        "Users",
        table(
          ["Identity", "Observed metadata"],
          users.rows.map((u) => [u.Name, details("Inspect user", u)]),
        ),
      ),
      section(
        "Roles",
        table(
          ["Role", "Observed metadata"],
          roles.rows.map((r) => [r.Name, details("Inspect role", r)]),
        ),
      ),
      empty(
        "Effective inherited access is not calculated. Review role resources and inheritance before granting access.",
      ),
    );
  } else if (state.page === "security") {
    root.append(
      observedTable(["tls", "wallets"]),
      empty(
        "TLS and wallet collection metadata are observable. Certificate, OAuth and secret-management changes are not implemented. Secret values are not requested.",
      ),
    );
  } else if (state.page === "os") {
    root.append(
      observedTable([
        "system",
        "processes",
        "databases",
        "license",
        "journals",
      ]),
      empty(
        "Collected values are observations, not a calculated capacity or continuity verdict. Process controls are not implemented.",
      ),
    );
  } else if (state.page === "rest") {
    root.append(
      empty(
        "REST discovery, request construction and response assertions are not implemented. Web application inventory is available.",
      ),
      button("Open web applications", () => navigate("webapps")),
    );
  } else if (state.page === "logs") {
    root.append(
      observedTable(["audit", "journals"]),
      empty(
        "Audit event definitions are configuration, not audit log records. Subsystem log search and correlation are not implemented.",
      ),
      button("Open Battery evidence ledger", () => navigate("ledger")),
    );
  } else if (state.page === "cases") {
    renderNativeCases(root);
  } else if (state.page === "receipts") {
    if (state.receiptId) { root.append(empty("Loading operation receipt…")); return; }
    root.append(receiptTable(state.receipts));
    if (state.pending) root.append(pendingDocument());
  } else if (state.page === "ledger") {
    const t = state.trail;
    root.append(
      node(
        "p",
        !t
          ? state.errors.trail || "Ledger unavailable"
          : t.count === 0
            ? "Ledger empty — nothing to verify."
            : `${t.valid ? "Chain verified" : "Ledger integrity failure"} · ${t.count} records`,
      ),
    );
    if (t?.head) root.append(digest(t.head));
    if (t?.records.length)
      root.append(
        table(
          ["Sequence", "UTC time", "Event", "Target / status", "Digest"],
          [...t.records]
            .reverse()
            .map((r) => [
              r.sequence,
              r.recorded_at,
              r.event_type,
              `${r.target || "—"} · ${r.status || "—"}`,
              digest(r.digest),
            ]),
        ),
        node(
          "p",
          `Showing ${t.records.length} of ${t.count} records. Hash chaining does not prove observation correctness.`,
          "quiet",
        ),
      );
  } else if (state.page === "rules") {
    const box = node("div");
    showRule(state.server?.rule, box);
    root.append(
      box,
      empty(
        "Rule maturity is configured by the operator. Listed validation records, when absent, do not establish live qualification.",
      ),
    );
  }
}
function planRequest() {
  const workflow = byId("workflow").value;
  let path, body;
  if (workflow === "run") {
    path = `/api/intents/task/${byId("task").value}/run`;
    body = { task_definition_reviewed: byId("reviewed").checked };
  } else if (workflow === "schedule") {
    path = `/api/intents/task/${byId("task").value}/schedule`;
    body = {
      period: byId("period").value,
      start_time: byId("start-time").value,
      every: byId("every").value,
      day: byId("day").value,
    };
  } else if (workflow === "webapp") {
    path = "/api/intents/web-app/create";
    body = {
      name: byId("app-name").value,
      namespace: byId("namespace").value,
      dispatch_class: byId("dispatch").value,
      resource: byId("resource").value,
    };
  } else {
    path = "/api/intents/access/grant-role";
    body = {
      username: byId("username").value,
      role_name: byId("role-name").value,
      role_reviewed: byId("role-reviewed").checked,
    };
  }
  return { path, body, type: workflow === "run" ? "task-run" : "admin" };
}
async function prepare(event) {
  event?.preventDefault();
  if (state.busy) return;
  clearError();
  invalidate("Checking current prerequisites…");
  const revision = state.revision,
    request = planRequest();
  byId("prepare").disabled = true;
  try {
    const data = await api(request.path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.body),
    });
    if (revision !== state.revision) return;
    state.plan = data;
    state.certificate = data.certificate || null;
    state.actionType = request.type;
    state.executionKey = crypto.randomUUID();
    state.warning30 = false;
    byId("finding-title").textContent = data.finding.summary;
    byId("finding-copy").textContent = data.finding.consequence;
    const blockers = byId("blockers");
    blockers.replaceChildren();
    if (data.finding.missing_evidence.length)
      data.finding.missing_evidence.forEach((item) =>
        blockers.append(
          node("p", `⊘ BLOCKED — ${item}`, "prerequisite blocked"),
        ),
      );
    else
      blockers.append(
        node(
          "p",
          `${state.certificate ? "✓ TRUE — configured preparation checks passed." : "— Requested outcome is already satisfied; no change needed."}`,
          "prerequisite",
        ),
      );
    blockers.append(
      node(
        "small",
        `Evaluated ${data.finding.evaluated_at}. Evidence: ${data.finding.evidence_ids.length ? data.finding.evidence_ids.join(", ") : "Unavailable / not recorded"}.`,
      ),
    );
    showRule(data.rule);
    byId("plan-evidence").replaceChildren(
      fields({
        "Observed target": data.intent.target,
        Policy: `${data.rule.id} v${data.rule.version}`,
        Inferred: data.finding.inference,
      }),
      details(
        "Sanitized proposed change",
        data.proposed_change || {
          operation: "Run existing task once",
          target: data.intent.target,
        },
      ),
    );
    const raw = data.task || data.context;
    if (raw)
      byId("plan-evidence").append(
        details("Observed preparation context", raw),
      );
    byId("contract").replaceChildren(
      fields({
        "Affected target": data.intent.target,
        "Expected outcome": data.intent.desired_outcome,
        Operator: data.intent.requested_by,
        Verification:
          request.type === "task-run"
            ? "Fresh task history; live v1 attribution may remain unverified."
            : "Fresh configuration readback matches the requested fields.",
        "Verification window": "5 minutes from dispatch; no automatic retry.",
        "Impact classification":
          "Not classified; review actual task side effects or configuration changes.",
        Rollback: "Not automated. Review a separate corrective request.",
        "Authorization expires": data.certificate?.expires_at,
      }),
      details(
        "Exact proposed delta",
        data.proposed_change || { run_task: data.intent.target },
      ),
    );
    byId("action-title").textContent = state.certificate
      ? "Review the prepared change"
      : data.plan_state === "SATISFIED"
        ? "Outcome already satisfied"
        : "Execution blocked";
    byId("action-copy").textContent = state.certificate
      ? "Review the exact target and effect above, then execute once."
      : data.finding.missing_evidence.join(" ") || "No execution is needed.";
    byId("execute").textContent =
      request.type === "task-run" ? "Run and verify" : "Apply and verify";
    byId("execute").disabled = !state.certificate;
    byId("receipt").replaceChildren();
    stage(state.certificate ? "authorize" : "prepare");
    tick();
    announce(
      state.certificate
        ? "Preparation complete. Review the target before authorizing execution."
        : "Preparation complete. No execution is authorized.",
    );
    await refreshProof();
  } catch (error) {
    if (revision === state.revision) {
      invalidate(`Preparation failed: ${error.message}`);
      announce(`Preparation failed: ${error.message}`, true);
    }
  } finally {
    byId("prepare").disabled = requiresSignIn;
  }
}
async function refreshProof() {
  const results = await Promise.allSettled([
    api("/api/evidence?limit=100"),
    api("/api/receipts"),
    api("/api/findings/demonstration"),
  ]);
  if (results[0].status === "fulfilled") state.trail = results[0].value;
  if (results[1].status === "fulfilled")
    state.receipts = results[1].value.receipts;
  if (results[2].status === "fulfilled")
    state.demonstrationFinding = results[2].value;
  if (state.page === "overview") renderPage();
}
function savePending(value) {
  state.pending = value;
  try {
    if (value) sessionStorage.setItem("battery-pending", JSON.stringify(value));
    else sessionStorage.removeItem("battery-pending");
  } catch {
    announce(
      "Browser storage unavailable; note the execution key before leaving this page.",
    );
  }
}
function pendingDocument() {
  const box = node("div", undefined, "receipt-document");
  box.append(
    badge("OUTCOME_UNKNOWN"),
    node(
      "p",
      "Delivery is unknown. A server receipt has not yet been recovered. Battery will not send the change again.",
    ),
    fields({
      "Execution key": state.pending?.key,
      Target: state.pending?.target,
    }),
    button("Find stored receipt", findPending),
  );
  return box;
}
function showPending() {
  if (state.pending) byId("receipt").replaceChildren(pendingDocument());
}
async function findPending() {
  if (!state.pending) return;
  try {
    const data = await api(
      `/api/receipts?execution_key=${encodeURIComponent(state.pending.key)}`,
    );
    state.receipts = data.receipts;
    const receipt = data.receipts.find(
      (r) => r.idempotency_key === state.pending.key,
    );
    if (receipt) {
      savePending(null);
      await openReceipt(receipt.id, byId("receipt"));
    } else
      announce(
        "No receipt found for this execution key. Delivery remains unknown; do not repeat the change.",
      );
  } catch (error) {
    announce(`Receipt lookup unavailable: ${error.message}`, true);
  }
}
async function execute() {
  if (!state.certificate || state.busy) return;
  if (Date.parse(state.certificate.expires_at) <= Date.now()) {
    invalidate("Authorization expired. Prepare fresh evidence.");
    return;
  }
  const cert = state.certificate,
    key = state.executionKey,
    type = state.actionType;
  const target = state.plan.intent.target;
  state.busy = true;
  state.certificate = null;
  byId("execute").disabled = true;
  byId("prepare").disabled = true;
  stage("execute");
  clearError();
  savePending({ key, target });
  announce("Attempt in progress. Do not repeat the change.");
  try {
    const result = await api(
      `/api/actions/${type}/${encodeURIComponent(cert.token)}/execute`,
      { method: "POST", headers: { "Idempotency-Key": key } },
    );
    savePending(null);
    stage("verify");
    await renderReceipt(
      { receipt: result, evidence: [], ledger: [] },
      byId("receipt"),
    );
    await refreshProof();
    await openReceipt(result.id, byId("receipt"));
  } catch (error) {
    showPending();
    announce(
      `Execution response did not establish an outcome: ${error.message}`,
      true,
    );
    stage("verify");
  } finally {
    state.busy = false;
    byId("prepare").disabled = requiresSignIn;
    byId("action-copy").textContent =
      "This authorization is consumed. Reconcile an unresolved attempt before considering another request.";
  }
}
async function openReceipt(id, target = null) {
  if (!target) { navigate("receipts", true, id); return; }
  const epoch = sessionEpoch, route = viewKey();
  try {
    const packet = await api(`/api/receipts/${encodeURIComponent(id)}`);
    if (epoch !== sessionEpoch || route !== viewKey()) return;
    rememberView();
    await renderReceipt(packet, target);
    if (state.page === "receipts") {
      const back = button("Back to case", () => openCase(state.nativeDetail.id));
      if (state.nativeDetail?.receipt_id === id) target.prepend(back);
      paintedView = viewKey(); restoreView();
    }
  } catch (error) {
    if (epoch === sessionEpoch && route === viewKey()) {
      announce(`Receipt detail unavailable: ${error.message}`, true);
      if (target === byId("page-content")) target.replaceChildren(button("Back to receipts", () => navigate("receipts")));
    }
  }
}
async function renderReceipt(packet, target) {
  const r = packet.receipt,
    box = node("article", undefined, "receipt-document");
  box.append(
    node("h2", "Attempt receipt"),
    badge(r.status),
    node(
      "p",
      r.status === "VERIFIED_SUCCESS"
        ? "Requested outcome established from fresh evidence after one bounded dispatch."
        : r.explanation,
      "receipt-verdict",
    ),
    fields({
      "Receipt ID": r.id,
      "Started (UTC)": r.started_at,
      "Finished (UTC)": r.finished_at,
      Target: r.target,
      Operator: r.operator,
      "Action ID": r.action_id,
      "Intent ID": r.intent_id,
      "Idempotency key": r.idempotency_key,
      "Certificate binding digest": r.certificate_digest,
      Transport: r.transport_result,
      "Before evidence IDs": r.before_evidence,
      "After evidence IDs": r.after_evidence,
      "Verification deadline": r.verification_deadline,
      "Verification result": r.explanation,
      "Remaining unknowns":
        r.status === "VERIFIED_SUCCESS"
          ? "Configuration/history predicate only; downstream functional effects are not established."
          : r.explanation,
    }),
  );
  const receiptFacts = box.lastElementChild;
  if (receiptFacts?.tagName === "DL") {
    receiptFacts.remove();
    const disclosure = node("details"); disclosure.append(node("summary", "Receipt properties and identifiers"), receiptFacts); box.append(disclosure);
  }
  box.append(button("Review this receipt with AI Hub", () => submitNativeCase(r.id)));
  (packet.evidence || []).forEach((o) =>
    box.append(details(`${o.source} · ${o.id} · ${o.captured_at}`, o)),
  );
  if (!(packet.evidence || []).length)
    box.append(
      empty("Supporting observation details are unavailable in this response."),
    );
  (packet.ledger || []).forEach((l) => {
    const row = node("div");
    row.append(
      node(
        "span",
        `Ledger ${l.sequence} · ${l.event_type} · ${l.recorded_at} `,
      ),
      digest(l.digest),
    );
    box.append(row);
  });
  if (["OUTCOME_UNKNOWN", "EXECUTED_UNVERIFIED"].includes(r.status)) {
    box.append(
      button("Reconcile from fresh evidence", async (event) => {
        event.currentTarget.disabled = true;
        try {
          await api(`/api/receipts/${encodeURIComponent(r.id)}/reconcile`, {
            method: "POST",
          });
          await refreshProof();
          await openReceipt(r.id, target);
        } catch (error) {
          event.currentTarget.disabled = false;
          announce(
            `Reconciliation unavailable: ${error.message}. The change was not resent.`,
            true,
          );
        }
      }),
      node(
        "p",
        "Reconciliation reads evidence. It never repeats the change.",
        "quiet",
      ),
    );
  }
  target.replaceChildren(box);
  announce(
    `Attempt ${r.status.replaceAll("_", " ").toLowerCase()}.`,
    r.status === "VERIFIED_FAILURE",
  );
}
function tick() {
  updateFreshness();
  if (!state.certificate) return;
  const remaining = Math.ceil(
    (Date.parse(state.certificate.expires_at) - Date.now()) / 1000,
  );
  if (remaining <= 0) {
    invalidate("Authorization expired. Prepare fresh evidence.");
    announce("Authorization expired. Execution is disabled.");
    return;
  }
  byId("certificate-time").textContent =
    `Authorization expires in ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")} · ${state.certificate.expires_at}`;
  if (remaining <= 30 && !state.warning30) {
    state.warning30 = true;
    announce("Authorization expires within 30 seconds.");
  }
}

async function loadNativeCases(id = null) {
  const epoch = ++nativeLoadEpoch;
  try {
    const list = await api("/api/cases");
    if (epoch !== nativeLoadEpoch) return;
    state.nativeCases = list;
    const selected = id || state.caseId;
    if (!selected && !state.caseBrowse && list.available && list.items?.length && state.page === "cases") {
      navigate("cases", false, list.items[0].id, "replace");
      return;
    }
    const previousRevision = state.nativeDetail?.brief?.revision;
    if (selected) {
      const detail = await api(`/api/cases/${encodeURIComponent(selected)}`);
      if (epoch !== nativeLoadEpoch) return;
      state.nativeDetail = detail;
      state.nativeReceipt = null; state.receiptError = "";
      if (detail.receipt_id) {
        try {
          const packet = await api(`/api/receipts/${encodeURIComponent(detail.receipt_id)}`);
          if (epoch !== nativeLoadEpoch) return;
          if (packet.receipt?.id !== detail.receipt_id || packet.receipt?.target !== detail.target)
            throw new Error("The returned receipt does not match this review.");
          state.nativeReceipt = packet;
        } catch (error) {
          if (epoch !== nativeLoadEpoch) return;
          state.receiptError = error.message;
        }
      }
      if (detail.brief) state.inspectedKinds[detail.id] = detail.brief.kind;
      if (previousRevision && detail.brief?.revision !== previousRevision && state.decisionDrafts[detail.id])
        announce("Evidence changed. Your draft is preserved; compare the current facts before recording your decision.");
    }
    state.nativeError = "";
  } catch (error) {
    if (epoch === nativeLoadEpoch) { state.nativeError = error.message; if (id || state.caseId) { state.nativeDetail = null; state.nativeReceipt = null; } }
  }
  if (epoch === nativeLoadEpoch && state.page === "cases") renderPage();
}
async function submitNativeCase(receiptId, parentId = "") {
  const storageKey = `battery-native:${receiptId}:${parentId}`;
  try {
    let key = localStorage.getItem(storageKey);
    if (!key) {
      key = crypto.randomUUID();
      localStorage.setItem(storageKey, key);
    }
    const result = await api("/api/cases", {
      method: "POST", headers: {"Content-Type": "application/json", "Idempotency-Key": key},
      body: JSON.stringify({receipt_id: receiptId, parent_id: parentId}),
    });
    state.nativeDetail = result;
    openCase(result.id);
    announce("Native review admitted. Refresh cases to follow its progress.");
  } catch (error) {
    announce(`Case admission not confirmed: ${error.message}. Retrying this review keeps its request key and does not repeat the operation.`, true);
  }
}
function sourceNote(label, target, context = "") {
  const note = node("div", undefined, "source-note");
  const link = button(label, () => {
    for (let parent = target; parent; parent = parent.parentElement)
      if (parent.tagName === "DETAILS") parent.open = true;
    const focus = target.querySelector?.("summary") || target;
    if (focus.tagName !== "SUMMARY") focus.setAttribute("tabindex", "-1");
    focus.focus?.({preventScroll:true});
    focus.scrollIntoView?.({block:"nearest"});
  });
  link.className = "source-link";
  if (target.id) link.setAttribute("aria-controls", target.id);
  note.append(node("span", "Source: "), link);
  if (context) note.append(node("span", context, "source-context"));
  return note;
}
function sourceTime(value) {
  if (!value) return "time not recorded";
  if (/(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)))
    return new Date(value).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
  return String(value);
}
function briefSourceContext(fact, brief) {
  if (fact.id === "configuration") return `Compared ${sourceTime(brief.read_at)}`;
  if (fact.observed_at) return `Review updated ${fact.observed_at} (IRIS time)`;
  return brief.scope === "synthetic" ? "Simulated operation" : "IRIS operation";
}
function renderDecisionBrief(c) {
  const b = c.brief;
  const evidence = node("details"), factViews = new Map();
  evidence.append(node("summary", "Why is Battery showing this?"));
  for (const fact of b.facts) {
    const item = section(fact.label, fields(fact.value));
    item.id = `decision-fact-${fact.id}`;
    item.append(node("p", briefSourceContext(fact, b), "quiet"));
    factViews.set(fact.id, item); evidence.append(item);
  }
  evidence.append(node("p", `Configuration read: ${b.read_at}. ${b.history_note}`));
  const box = section(b.question, node("p", b.summary));
  const sources = node("div", undefined, "brief-sources");
  for (const fact of b.facts) sources.append(sourceNote(fact.label, factViews.get(fact.id), briefSourceContext(fact, b)));
  box.append(sources);
  box.className += " decision-brief";
  box.dataset.kind = b.kind;
  box.prepend(node("p", b.choices.length ? "Your next decision" : "Current task", "eyebrow"));
  box.append(node("p", `${b.scope === "synthetic" ? "Simulated operation" : "IRIS operation"} · Decision owner: ${b.owner}`));
  box.append(node("p", b.next_step, "decision-next"));
  if (b.successor) box.append(button("Open newer review", () => openCase(b.successor)));
  if (b.differences.length) box.append(table(["What changed", "Retained with receipt", "Current value"], b.differences.map(d => [d.field, JSON.stringify(d.retained), JSON.stringify(d.current)])));
  if (b.differences_omitted) box.append(node("p", `${b.differences_omitted} additional changed fields omitted. Inspect the target before deciding.`));
  for (const unknown of b.unknowns) box.append(node("p", unknown, "brief-limit"));
  const help = node("details"); help.append(node("summary", "More explanation"), evidence);
  if (c.explanation?.status === "ready") {
    const e = c.explanation.content;
    const explanation = section("AI explanation — interpretation of the evidence", node("p", e.summary), node("p", e.meaning), node("p", e.missing));
    explanation.append(node("p", "Sources cited for this explanation as a whole:", "quiet"));
    for (const id of e.evidence_ids) {
      const fact = b.facts.find(f => f.id === id);
      if (fact) explanation.append(sourceNote(fact.label, factViews.get(id), briefSourceContext(fact, b)));
      else explanation.append(node("p", "A cited source is unavailable in this review.", "brief-limit"));
    }
    help.append(explanation);
  } else if (c.explanation) help.append(node("p", c.explanation.detail));
  if (!["IN_PROGRESS", "SUPERSEDED"].includes(b.kind) && (!c.explanation || (c.explanation.status === "unavailable" && (c.explanation.attempt || 1) < 2))) {
    const status = node("p", "Optional: ask AI Hub to explain these observations in everyday language.");
    status.setAttribute("role", "status");
    const explain = button(c.explanation ? "Retry explanation once" : "Explain this evidence", async () => {
      const epoch = sessionEpoch, revision = b.revision;
      explain.disabled = true; status.textContent = "Preparing an explanation. You can still inspect the evidence.";
      try {
        const response = await api(`/api/cases/${encodeURIComponent(c.id)}/explain`, {timeoutMs: 110000, method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({revision, retry: !!c.explanation})});
        if (epoch !== sessionEpoch || state.nativeDetail?.id !== c.id || state.nativeDetail?.brief?.revision !== revision) return;
        if (response.status === "unconfirmed") { status.textContent = response.detail; return; }
        state.nativeDetail.explanation = response;
        if (state.page === "cases") renderPage();
      } catch (error) {
        if (epoch === sessionEpoch) { status.textContent = error.message; explain.disabled = false; }
      }
    });
    help.append(explain, status);
  }
  if (b.choices.length) {
    const form = node("form", undefined, "decision-form"), group = node("fieldset");
    group.append(node("legend", "Choose the next step"));
    const label = node("label", "Your context or reason"), reason = node("textarea");
    reason.id = "decision-reason"; reason.maxLength = 2000; reason.required = true; reason.rows = 3;
    label.htmlFor = reason.id; reason.value = state.decisionDrafts[c.id] || "";
    reason.addEventListener("input", () => { state.decisionDrafts[c.id] = reason.value; });
    for (const option of b.choices) {
      const card = node("label", undefined, "decision-option"), radio = node("input");
      radio.type = "radio"; radio.name = "decision-choice"; radio.value = option.id; radio.required = true;
      radio.checked = state.decisionChoices[c.id] === option.id;
      radio.addEventListener("change", () => { state.decisionChoices[c.id] = option.id; });
      const words = node("span"); words.append(node("strong", option.label), node("span", option.consequence));
      card.append(radio, words); group.append(card);
    }
    const submit = node("button", "Record decision", "primary"); submit.type = "submit";
    const feedback = node("p"); feedback.setAttribute("role", "status");
    form.append(group, label, reason, submit, feedback);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (submit.disabled || !form.reportValidity()) return;
      const option = b.choices.find(o => o.id === state.decisionChoices[c.id]);
      if (!option) return;
      const epoch = sessionEpoch; submit.disabled = true;
      feedback.textContent = "Recording your decision…";
      try {
        const response = await api(`/api/cases/${encodeURIComponent(c.id)}/decision`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({revision:b.revision, choice:option.id, reason:reason.value})});
        if (epoch !== sessionEpoch) return;
        delete state.decisionDrafts[c.id]; delete state.decisionChoices[c.id];
        if (response.child_id) openCase(response.child_id); else await loadNativeCases(c.id);
        announce(response.child_id ? "Your request was recorded and a new review was admitted. The operation was not repeated." : response.next_step);
      } catch (error) {
        if (epoch === sessionEpoch) {
          feedback.textContent = error.message;
          if (error.httpStatus === 409) await loadNativeCases(c.id);
          else announce(`Decision not confirmed: ${error.message}. Your draft is retained.`, true);
        }
      } finally { submit.disabled = false; }
    });
    box.append(form);
  }
  box.append(help);
  if (c.decisions?.length) {
    const history = node("details"); history.append(node("summary", "Your recorded decisions"));
    for (const d of c.decisions) history.append(section(d.choice.replaceAll("_", " "), node("p", d.reason), node("p", `${d.operator} · ${d.recorded_at}`), node("p", d.next_step)));
    box.append(history);
    const last = c.decisions[c.decisions.length-1];
    if (last.revision === b.revision) box.append(node("p", `Your decision is recorded: ${last.next_step}`));
    if (last.choice === "restore_intent") box.append(button("Inspect target before preparing a correction", () => navigate(c.target?.startsWith("task:") ? "tasks" : c.target?.startsWith("web-app:") ? "webapps" : "permissions")));
    if (last.choice === "request_evidence") box.append(button("Check the requested review", async () => {
      const epoch = sessionEpoch;
      try {
        const response = await api(`/api/cases/${encodeURIComponent(c.id)}/decision`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({revision: last.revision, choice: last.choice, reason: last.reason})});
        if (epoch === sessionEpoch) await loadNativeCases(response.child_id);
      } catch (error) { if (epoch === sessionEpoch) announce(error.message, true); }
    }));
  }
  return box;
}

function targetName(target) {
  const id = String(target || "").split(":")[1];
  if (String(target).startsWith("task:")) {
    const task = state.catalog?.tasks?.find(t => String(t.Id) === id);
    return task?.Name || `Task ${id}`;
  }
  return target || "Operation review";
}
function caseLabel(status) {
  return ({VERIFIED_MATCH:"Evidence matched the request", VERIFIED_MISMATCH:"Evidence did not match", QUEUED:"Waiting for review", RUNNING:"Review in progress", RECOVERY_REQUIRED:"Review needs recovery", ADMISSION_UNCERTAIN:"Review admission unconfirmed", HELD_FOR_REVIEW:"Review needs clarification", HELD_FOR_EVIDENCE:"More evidence needed"})[status] || String(status || "Outcome unknown").replaceAll("_", " ").toLowerCase();
}
// The receipt is an operation record; the review is a separate interpretation.
function renderCaseReceipt(c) {
  const box = node("section", undefined, "section case-receipt");
  box.append(node("p", c.source_scope === "synthetic" ? "Simulated operation" : "IRIS operation", "eyebrow"), node("h2", "Operation receipt"));
  const packet = state.nativeReceipt, r = packet?.receipt;
  if (!r || r.id !== c.receipt_id || r.target !== c.target) {
    box.append(node("p", c.receipt_id ? "The receipt could not be displayed." : "No operation receipt is linked to this review."));
    if (state.receiptError) box.append(node("p", state.receiptError, "error-message"));
    box.append(node("p", "The review summary alone does not establish what the operation did.", "quiet"));
    return box;
  }
  const outcome = ({VERIFIED_SUCCESS:"The requested result was verified.", VERIFIED_FAILURE:"The result did not meet the request.", OUTCOME_UNKNOWN:"We do not yet know whether the operation completed.", EXECUTED_UNVERIFIED:"The operation ran; its result has not been verified.", BLOCKED_BEFORE_EXECUTION:"The operation was blocked before it ran.", CANCELLED:"The operation was cancelled."})[r.status] || "The operation outcome needs inspection.";
  const action = ({"task.run-once":"Run the task once", "web-app.create":"Create a web application"})[r.action_id] || r.action_id || "Action not recorded";
  box.append(node("h3", targetName(r.target)), node("p", action), node("p", outcome, "receipt-verdict"));
  if (r.explanation) box.append(node("p", r.explanation));
  if (r.finished_at || r.started_at) box.append(node("p", `${r.finished_at ? "Finished" : "Started"} (UTC): ${r.finished_at || r.started_at}`, "quiet"));
  if (r.status === "VERIFIED_SUCCESS") box.append(node("p", "This verifies the recorded configuration or task history. It does not by itself prove that a downstream service works.", "brief-limit"));
  const properties = node("details"); properties.id = "receipt-source";
  properties.append(node("summary", "Receipt details"), fields(r));
  box.append(sourceNote("Saved operation receipt", properties, r.finished_at ? `Finished ${sourceTime(r.finished_at)}` : "Completion time not recorded"));
  const observations = node("details"); observations.append(node("summary", "Receipt evidence"));
  for (const o of packet.evidence || []) observations.append(details(`${o.source || "Observation"} · ${o.captured_at || "time not recorded"}`, o));
  if (!packet.evidence?.length) observations.append(node("p", "Supporting observations are unavailable in this response."));
  box.append(properties, observations, button("Inspect operation receipt", () => openReceipt(c.receipt_id)));
  return box;
}
function renderCaseStory(c) {
  const r = c.result || {}, story = section("What happened"); story.className += " review-story";
  const steps = node("ol", undefined, "case-story");
  const add = (title, text, label, record) => {
    const step = node("li"); step.append(node("h3", title), node("p", text));
    const supporting = details(label, record);
    const sourceLabels = {"Earlier review details":"Review history", "Evidence check details":"Evidence check record", "Review conclusion details":"Recorded review result"};
    supporting.id = `story-source-${steps.children.length}`;
    step.append(sourceNote(sourceLabels[label], supporting, `Review updated ${c.updated_at || "at an unrecorded time"}${c.updated_at ? " (IRIS time)" : ""}`), supporting);
    steps.append(step);
  };
  const history = Array.isArray(r.ReviewHistoryJSON) ? r.ReviewHistoryJSON : [];
  const first = history[0];
  let assessment = "No earlier agent assessment is included in this record.";
  if (first) {
    assessment = first.verdict === "NO" ? "The first review did not support the rule’s assertion." : first.verdict === "YES" ? "The first review supported the rule’s assertion." : "The first review left the rule’s assertion unresolved.";
    assessment += first.output === "PASS" ? " It reported that the result passed." : first.output === "FAIL" ? " It reported that the result failed." : " It could not establish whether the result passed.";
  }
  add("The initial review", assessment, "Earlier review details", {case_id:c.id, initial_assessment:first || null, review_history:history});
  const probe = ({CHECK_EFFECT_RECEIPT:"Battery checked the saved receipt for this operation.", READ_CURRENT_TARGET:"Battery read the target’s current settings."})[r.executed_probe];
  add("The evidence check", probe || (r.executed_probe ? "Battery recorded an additional evidence check." : "No separate investigation step is recorded here."), "Evidence check details", {case_id:c.id, executed_probe:r.executed_probe || null, evidence_reads:r.ProbeHistoryJSON || null});
  add("The recorded conclusion", caseLabel(c.state) + ".", "Review conclusion details", {case_id:c.id, state:c.state, assertion:r.assertion, output:r.output, proof:r.ProofJSON});
  story.append(steps); return story;
}
function renderNativeCases(root) {
  const toolbar = node("div", undefined, "case-toolbar");
  if (state.caseId) toolbar.append(button("Back to cases", () => navigate("cases", true, "all")));
  else toolbar.append(node("p", "Understand the result. Find the next useful step.", "page-intro"));
  toolbar.append(button("Refresh cases", () => loadNativeCases(state.caseId)));
  root.append(toolbar);
  if (state.nativeError) root.append(node("p", `Could not refresh cases: ${state.nativeError}. Any retained information below may be out of date.`, "error-message"));
  const list = state.nativeCases;
  if (!list) { root.append(empty("Loading cases…")); return; }
  if (!list.available) { root.append(empty(list.detail)); return; }
  if (!state.caseId) {
    const controls = node("div", undefined, "case-filters"), label = node("label", "Find a case"), search = node("input");
    search.id = "case-search"; search.type = "search"; search.value = state.caseSearch; label.htmlFor = search.id;
    const filterLabel = node("label", "Show"), filter = node("select"); filter.id = "case-filter"; filterLabel.htmlFor = filter.id;
    for (const [value,title] of [["all","All loaded cases"],["decision","Needs your decision · inspected"],["attention","Unresolved reviews"],["progress","In progress"],["finished","Finished"]]) { const o = node("option",title); o.value = value; filter.append(o); }
    filter.value = state.caseFilter; controls.append(label,search,filterLabel,filter); root.append(controls);
    search.addEventListener("input", () => { state.caseSearch = search.value; renderPage(); });
    filter.addEventListener("change", () => { state.caseFilter = filter.value; renderPage(); });
    root.append(node("p", "Initially newest first; new arrivals append while you read. Decision needs reflect inspected cases. Open a case to check its current evidence.", "quiet"));
    for (const item of list.items) if (!state.caseOrder.includes(item.id)) state.caseOrder.push(item.id);
    const items = [...list.items].sort((a,b) => state.caseOrder.indexOf(a.id)-state.caseOrder.indexOf(b.id)).filter(c => {
      const match = `${targetName(c.target)} ${c.target} ${c.id}`.toLowerCase().includes(state.caseSearch.toLowerCase());
      const active = ["RUNNING","QUEUED","ADMISSION_UNCERTAIN"].includes(c.state), done = c.state?.startsWith("VERIFIED_");
      return match && (state.caseFilter === "all" || state.caseFilter === "decision" && state.inspectedKinds[c.id] === "CONTEXT_DECISION" || state.caseFilter === "attention" && !active && !done || state.caseFilter === "progress" && active || state.caseFilter === "finished" && done);
    });
    const cards = node("div", undefined, "case-cards");
    for (const c of items) {
      const card = node("article", undefined, "case-card"), open = button(targetName(c.target), () => openCase(c.id)); open.dataset.caseId = c.id;
      card.append(node("p", c.source_scope === "synthetic" ? "Simulated operation" : "IRIS operation", "eyebrow"), open, node("p", caseLabel(c.state), "case-status"), node("p", `Review ${c.id.slice(-8)} · Updated ${c.updated_at || "time unavailable"} (IRIS time)`, "quiet")); cards.append(card);
    }
    root.append(cards, node("p", `${items.length} shown · ${list.items.length} loaded (up to 50 recent authorized reviews).`, "quiet"));
    if (!items.length) root.append(empty(list.items.length ? "No cases match. Choose All loaded cases or clear the search." : "No reviews yet. Open an operation receipt to start an AI Hub review."));
    if (list.budget) root.append(details("Review limits", list.budget));
    return;
  }
  const c = state.nativeDetail?.id === state.caseId ? state.nativeDetail : null;
  if (!c) { root.append(empty(state.nativeError ? "This case could not be opened. Return to cases or refresh." : "Loading the selected case…")); return; }
  root.append(node("p", targetName(c.target), "case-target"));
  const r = c.result || {};
  const layout = node("div", undefined, "receipt-review");
  layout.append(renderCaseReceipt(c));
  const explanation = node("div", undefined, "review-explanation");
  explanation.append(renderCaseStory(c));
  if (c.brief) explanation.append(renderDecisionBrief(c));
  else explanation.append(section("Review status", node("p", caseLabel(c.state)), node("p", c.recovery_reason || "A readable summary is not available yet. Expand the technical evidence for the recorded details.")));
  layout.append(explanation); root.append(layout);
  const box = section("Technical case details", fields({Case: c.id, State: c.state, "Source scope": c.source_scope, Target: c.target, "Parent revision": c.parent_id, "Rule assertion": r.assertion, "Measured output": r.output, "Reviewer assertion": r.reviewer_assertion, "Reviewer output": r.reviewer_output, Reason: c.recovery_reason || r.explanation, "Proposed probe": r.proposed_probe, "Executed probe": r.executed_probe, "Native response ID": r.response_id}));
  if (["QUEUED", "RUNNING"].includes(c.state)) box.append(empty("The native production is working. Refresh cases for its current state; another click does not start a duplicate review."));
  if (c.receipt_id) box.append(button("Inspect operation receipt", () => openReceipt(c.receipt_id)));
  if ((c.state.startsWith("HELD_") || c.state === "RECOVERY_REQUIRED") && c.receipt_id) box.append(button("Review refreshed evidence as a new revision", () => submitNativeCase(c.receipt_id, c.id)));
  if (c.state === "ADMISSION_UNCERTAIN") box.append(empty("Queue admission is uncertain. Inspect the native message trace before starting another revision."));
  for (const [label, key] of [["Measurement proof", "ProofJSON"], ["Reviews, rejected answers and usage", "ReviewHistoryJSON"], ["Evidence tool reads", "ProbeHistoryJSON"]]) {
    if (r[key]) box.append(details(label, r[key]));
  }
  box.append(empty("A measured match does not authorize another operation. Any further change uses the existing prepare, authorize, execute and verify workflow."));
  const technical = node("details");
  if (list.budget) box.append(node("p", `Reviews admitted today: ${list.budget.operator_daily_used} / ${list.budget.operator_daily_limit}.`, "quiet"));
  technical.append(node("summary", "Technical details and full evidence"), box);
  root.append(technical);
}

byId("intent-form").addEventListener("input", () => invalidate());
byId("intent-form").addEventListener("change", (event) => {
  if (event.target.id === "workflow") showWorkflow();
  else {
    invalidate();
    if (event.target.id === "task") {
      byId("reviewed").checked = false;
      showTask();
    }
    if (event.target.id === "role-name" || event.target.id === "username")
      byId("role-reviewed").checked = false;
  }
});
byId("intent-form").addEventListener("submit", prepare);
byId("execute").addEventListener("click", execute);
byId("new-request").addEventListener("click", () => startRequest());
byId("refresh").addEventListener("click", () => {
  invalidate("Evidence refresh requested; prepare the current intent again.");
  load().catch(error => announce(error.message, true));
  if (state.page === "cases") loadNativeCases(state.caseId);
});
document
  .querySelectorAll("[data-page]")
  .forEach((b) => b.addEventListener("click", () => navigate(b.dataset.page)));
document.querySelector(".nav-toggle").addEventListener("click", (event) => {
  const open = byId("navigation").dataset.open !== "true";
  byId("navigation").dataset.open = String(open);
  event.currentTarget.setAttribute("aria-expanded", String(open));
});
byId("sign-out").addEventListener("click", async () => {
  try {
    await api("/api/session/logout", {method: "POST"});
    clearOperatorView();
    window.location.reload();
  } catch (error) { announce(error.message, true); }
});
byId("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_key: byId("access-key").value }),
    });
    byId("access-key").value = "";
    clearOperatorView();
    window.location.reload();
  } catch (error) {
    announce(error.message, true);
  }
});
try {
  const pending = JSON.parse(
    sessionStorage.getItem("battery-pending") || "null",
  );
  if (pending && typeof pending.key === "string") state.pending = pending;
} catch {
  /* An unreadable browser hint grants no authority. */
}
initializeRoute();
setInterval(tick, 1000);
load().catch((error) => announce(error.message, true));
