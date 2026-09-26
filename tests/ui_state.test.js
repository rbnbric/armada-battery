// Dependency-free regression checks against the actual shipped UI handlers.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
class Element {
  constructor() {
    this.value = "";
    this.dataset = {};
    this.children = [];
    this.listeners = {};
    this.disabled = false;
    this.checked = false;
    this.className = "";
    this.textContent = "";
    this.attrs = {};
  }
  replaceChildren(...items) {
    this.children = items;
  }
  append(...items) {
    this.children.push(...items);
  }
  addEventListener(event, fn) {
    this.listeners[event] = fn;
  }
  setAttribute(key, value) {
    this.attrs[key] = value;
  }
  removeAttribute(key) {
    delete this.attrs[key];
  }
  focus() {}
  get options() {
    return this.children;
  }
}
function harness() {
  const elements = {};
  const get = (id) => (elements[id] ??= new Element());
  get("workflow").value = "run";
  get("task").value = "17";
  get("reviewed").checked = true;
  let pending = null;
  let fail = false;
  const calls = [];
  const rule = {
    id: "fixture",
    version: 1,
    validation: "SIMULATED",
    minimum_execution_validation: "SIMULATED",
    rationale: "fixture",
    counterexamples: [],
    assumptions: [],
    live_validations: [],
  };
  const plan = {
    certificate: {
      token: "private-certificate",
      expires_at: new Date(Date.now() + 60000).toISOString(),
    },
    finding: {
      summary: "Ready",
      consequence: "Fixture task",
      missing_evidence: [],
      evidence_ids: ["e1"],
      recommended_actions: [],
      evaluated_at: new Date().toISOString(),
      inference: "fixture",
    },
    intent: {
      target: "task:17",
      desired_outcome: "One task run",
      requested_by: "operator",
    },
    rule,
  };
  const context = vm.createContext({
    Node: Element,
    document: {
      getElementById: get,
      createElement: () => new Element(),
      querySelectorAll: () => [],
      querySelector: () => get("nav-toggle"),
    },
    window: { matchMedia: () => ({ matches: false }) },
    navigator: {},
    setInterval: () => {},
    sessionStorage: {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    },
    crypto: { randomUUID: () => "one-execution-key" },
    fetch: async (url, options = {}) => {
      calls.push({ url, options });
      if (url.startsWith("/api/intents")) {
        if (pending) await pending;
        if (fail)
          return {
            ok: false,
            status: 502,
            json: async () => ({ detail: "Preparation failed" }),
          };
        return {
          ok: true,
          status: 200,
          json: async () => structuredClone(plan),
        };
      }
      if (url.startsWith("/api/actions"))
        throw new Error("Connection lost after send");
      return {
        ok: true,
        status: 200,
        json: async () =>
          url.startsWith("/api/receipts")
            ? { receipts: [] }
            : { records: [], count: 0, valid: true },
      };
    },
  });
  const source = fs
    .readFileSync(path.join(__dirname, "../static/app.js"), "utf8")
    .replace(
      /load\(\)\.catch\(\(error\) => announce\(error.message, true\)\);\s*$/,
      "",
    );
  vm.runInContext(source, context);
  return {
    get,
    context,
    calls,
    plan,
    setFail: (v) => (fail = v),
    setPending: (v) => (pending = v),
    run: (code) => vm.runInContext(code, context),
  };
}
test("all input changes and failed preparations consume the displayed plan", async () => {
  const h = harness();
  await h.run("prepare()");
  assert.equal(h.get("execute").disabled, false);
  h.get("task").value = "23";
  h.get("intent-form").listeners.input({ target: h.get("task") });
  assert.equal(h.get("execute").disabled, true);
  assert.equal(h.run("state.certificate"), null);
  h.setFail(true);
  await h.run("prepare()");
  assert.equal(h.get("execute").disabled, true);
  assert.equal(h.run("state.certificate"), null);
});
test("late preparation responses never authorize changed input", async () => {
  const h = harness();
  let release;
  h.setPending(new Promise((resolve) => (release = resolve)));
  const prepare = h.run("prepare()");
  h.get("intent-form").listeners.input({ target: h.get("task") });
  release();
  await prepare;
  assert.equal(h.run("state.certificate"), null);
  assert.equal(h.get("execute").disabled, true);
});
test("expiry disables execution and unresolved quality never inherits success", async () => {
  const h = harness();
  await h.run("prepare()");
  h.run("state.certificate.expires_at = new Date(0).toISOString(); tick()");
  assert.equal(h.get("execute").disabled, true);
  for (const value of [
    "STALE",
    "MALFORMED",
    "CONFLICTED",
    "FORBIDDEN",
    "UNSUPPORTED",
    "UNAVAILABLE",
    "UNKNOWN",
    "OUTCOME_UNKNOWN",
    "EXECUTED_UNVERIFIED",
  ])
    assert.equal(
      h.run(`badge(${JSON.stringify(value)}).className`).includes("safe"),
      false,
      value,
    );
  assert.equal(
    h.run(
      'evidenceQuality({quality:"VALID",captured_at:new Date(0).toISOString(),freshness_seconds:60})',
    ),
    "STALE",
  );
});
test("lost execution response records its key and never retries the mutation", async () => {
  const h = harness();
  await h.run("prepare()");
  await h.run("execute()");
  assert.equal(h.run("state.pending.key"), "one-execution-key");
  assert.equal(h.get("execute").disabled, true);
  await h.run("execute()");
  await h.run("findPending()");
  assert.equal(
    h.calls.filter((c) => c.url.startsWith("/api/actions")).length,
    1,
  );
  assert.equal(h.run("state.pending.key"), "one-execution-key");
});
