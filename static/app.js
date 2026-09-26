"use strict";
const state = {
  page: "overview",
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
  errors: {},
  warning30: false,
  pending: null,
};
const byId = (id) => document.getElementById(id);
const LABELS = {
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
async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Response was unreadable; no outcome was established.");
  }
  if (response.status === 401) {
    byId("login-panel").hidden = false;
    throw new Error("Operator sign-in required.");
  }
  if (!response.ok) {
    const error = new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). No outcome established.`,
    );
    error.httpStatus = response.status;
    throw error;
  }
  return data;
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
function navigate(page, focus = true) {
  state.page = page;
  byId("page-title").textContent = LABELS[page] || page;
  byId("request-workspace").hidden = page !== "request";
  byId("page-content").hidden = page === "request";
  document.querySelectorAll("[data-page]").forEach((b) => {
    if (b.dataset.page === page) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  byId("navigation").dataset.open = "false";
  document.querySelector(".nav-toggle").setAttribute("aria-expanded", "false");
  renderPage();
  if (focus) byId("workspace").focus();
}
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
async function load() {
  byId("refresh").disabled = true;
  clearError();
  const sources = {
    server: "/api/state",
    catalog: "/api/catalog",
    observations: "/api/observations",
    trail: "/api/evidence?limit=100",
    assurance: "/api/assurance",
    receipts: "/api/receipts",
  };
  const keys = Object.keys(sources);
  const results = await Promise.allSettled(keys.map((k) => api(sources[k])));
  state.errors = {};
  results.forEach((r, i) => {
    const k = keys[i];
    if (r.status === "fulfilled")
      state[k] = k === "receipts" ? r.value.receipts : r.value;
    else {
      state[k] = k === "receipts" ? [] : null;
      state.errors[k] = r.reason.message;
    }
  });
  const server = state.server;
  byId("instance").textContent = server?.instance || "Instance unavailable";
  byId("adapter").textContent = server
    ? server.mode.toUpperCase()
    : "CONTEXT UNKNOWN";
  byId("adapter").className = "badge";
  byId("authority").textContent = server
    ? server.changes_enabled
      ? "CHANGES ENABLED"
      : "OBSERVATION ONLY"
    : "AUTHORITY UNKNOWN";
  byId("authority").className =
    "badge " + (server?.changes_enabled ? "watch" : "unknown");
  byId("connection").textContent = server
    ? `${server.server.version} · IRIS authority: ${server.server.username} · Battery operator: ${server.operator} · ${server.access_mode}`
    : state.errors.server || "Connection unavailable";
  if (!server?.changes_enabled && state.certificate)
    invalidate("Changes are disabled or authority is unavailable.");
  const c = state.catalog;
  if (c) {
    fillSelect("task", c.tasks, "Id", "Name");
    fillSelect("namespace", c.namespaces, null);
    fillSelect("resource", c.resources, "Name");
    fillSelect("username", c.users, "Name");
    fillSelect("role-name", c.roles, "Name");
  }
  updateFreshness();
  renderPage();
  byId("refresh").disabled = false;
  if (Object.keys(state.errors).length)
    announce(
      `Some collectors are unavailable: ${Object.keys(state.errors).join(", ")}. Working areas remain available.`,
    );
  if (state.pending) showPending();
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
function renderPage() {
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
      section("Operational evidence", summary, observationDisclosure),
      section("Recent attempts", receiptTable(state.receipts.slice(0, 5))),
      section(
        "Assurance",
        empty(
          state.assurance?.available
            ? `${state.assurance.passed}/${state.assurance.total} synthetic scenarios passed. This does not qualify live IRIS changes.`
            : state.assurance?.detail ||
                state.errors.assurance ||
                "Assurance unavailable.",
        ),
      ),
      empty(
        "Readiness conditions, charge, coverage and scheduled assurance obligations are not calculated in this release.",
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
  } else if (state.page === "receipts") {
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
    byId("prepare").disabled = false;
  }
}
async function refreshProof() {
  const results = await Promise.allSettled([
    api("/api/evidence?limit=100"),
    api("/api/receipts"),
  ]);
  if (results[0].status === "fulfilled") state.trail = results[0].value;
  if (results[1].status === "fulfilled")
    state.receipts = results[1].value.receipts;
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
    byId("prepare").disabled = false;
    byId("action-copy").textContent =
      "This authorization is consumed. Reconcile an unresolved attempt before considering another request.";
  }
}
async function openReceipt(id, target = null) {
  try {
    const packet = await api(`/api/receipts/${encodeURIComponent(id)}`);
    if (!target) {
      navigate("receipts");
      target = byId("page-content");
    }
    await renderReceipt(packet, target);
  } catch (error) {
    announce(`Receipt detail unavailable: ${error.message}`, true);
  }
}
async function renderReceipt(packet, target) {
  const r = packet.receipt,
    box = node("article", undefined, "receipt-document");
  box.append(
    node("h2", "Attempt receipt"),
    badge(r.status),
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
  load();
});
document
  .querySelectorAll("[data-page]")
  .forEach((b) => b.addEventListener("click", () => navigate(b.dataset.page)));
document.querySelector(".nav-toggle").addEventListener("click", (event) => {
  const open = byId("navigation").dataset.open !== "true";
  byId("navigation").dataset.open = String(open);
  event.currentTarget.setAttribute("aria-expanded", String(open));
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
    byId("login-panel").hidden = true;
    await load();
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
setInterval(tick, 1000);
load().catch((error) => announce(error.message, true));
