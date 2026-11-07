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
      token: "fx-cert",
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
    setTimeout, clearTimeout, AbortController,
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
    .replace(/initializeRoute\(\);\s*setInterval\(tick, 1000\);\s*load\(\)[\s\S]*$/, "");
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

test("a hung read times out even if fetch ignores AbortSignal", async () => {
  const h = harness();
  h.context.fetch = () => new Promise(() => {});
  await assert.rejects(h.run('api("/api/state", {timeoutMs: 10})'), /timed out/);
});
test("body reads have the same deadline as the HTTP request", async () => {
  const h = harness();
  h.context.fetch = async () => ({ok:true,status:200,json:()=>new Promise(()=>{})});
  await assert.rejects(h.run('api("/api/state", {timeoutMs: 10})'), /timed out/);
});
test("collectors render independently and an old refresh cannot overwrite a newer one", async () => {
  const h = harness();
  h.run('renderCollectors = () => {}');
  let release;
  const old = new Promise(r=>release=r);
  h.context.fetch = async url => ({ok:true,status:200,json:()=>url === "/api/assurance" ? old : Promise.resolve(url.startsWith("/api/receipts")?{receipts:[]}:{marker:"old"})});
  const first=h.run('load()');
  await new Promise(r=>setImmediate(r));
  assert.equal(h.run('state.server.marker'), 'old');
  assert.equal(h.get('refresh').disabled,true);
  h.context.fetch = async url => ({ok:true,status:200,json:async()=>url.startsWith("/api/receipts")?{receipts:[]}:{marker:"new"}});
  await h.run('load()');
  release({marker:"old"}); await first;
  assert.equal(h.run('state.assurance.marker'),'new');
  assert.equal(h.get('refresh').disabled,false);
});


test("native review response loss retains its admission key and never invokes an action", async () => {
  const h = harness();
  const storage = new Map();
  h.context.localStorage = {getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v)};
  h.run('var nativeRequests=[]; api=async (path,options)=>{nativeRequests.push({path,options}); throw new Error("lost admission response");}');
  await h.run('submitNativeCase("receipt-1")');
  await h.run('submitNativeCase("receipt-1")');
  const requests = h.run('nativeRequests');
  assert.equal(requests.length, 2);
  assert.equal(requests[0].path, "/api/cases");
  assert.equal(requests[1].path, "/api/cases");
  assert.equal(requests[0].options.headers["Idempotency-Key"], requests[1].options.headers["Idempotency-Key"]);
  assert.match(h.get("error-message").textContent, /does not repeat the operation/);
});
test("recovery shows an explicit revision action and never replays work on render", () => {
  const h = harness();
  h.run(`state.nativeCases = {available:true, items:[], budget:{operator_daily_used:2,operator_daily_limit:20,operator_active_limit:2}};
    state.caseId = 'abandoned-case';
    state.nativeDetail = {id:'abandoned-case',state:'RECOVERY_REQUIRED',receipt_id:'receipt-one',recovery_reason:'Expired RUNNING lease'};
    renderNativeCases(document.getElementById('fixture'))`);
  const words = (e) => [e.textContent, ...e.children.flatMap(words)];
  const text = words(h.get('fixture')).join(' ');
  assert.match(text, /Expired RUNNING lease/);
  assert.match(text, /Review refreshed evidence as a new revision/);
  assert.match(text, /2 \/ 20/);
  assert.equal(h.calls.length, 0);
});
test("read-only identity cannot send a mutation from the UI", async () => {
  const h = harness();
  h.run("state.server = {role:'observer'}");
  await assert.rejects(h.run("api('/api/cases',{method:'POST'})"), /read-only/);
  assert.equal(h.calls.length, 0);
});
test("expired sign-in removes previous operator evidence and rejects late responses", async () => {
  const h = harness();
  h.run("state.nativeDetail={id:'private-case'}; state.receipts=[{id:'private-receipt'}]; state.server={operator:'alice'}");
  h.get('page-content').textContent='private evidence';
  let release;
  const late=new Promise(r=>release=r);
  h.context.fetch=async path=> path==='/api/slow' ? late : {ok:false,status:401,json:async()=>({detail:'sign in'})};
  const pending=h.run("api('/api/slow')");
  await assert.rejects(h.run("api('/api/state')"),/sign-in/);
  release({ok:true,status:200,json:async()=>({private:'old operator'})});
  await assert.rejects(pending,/session changed|sign-in/i);
  assert.equal(h.run('state.nativeDetail'),null);
  assert.equal(h.run('state.receipts.length'),0);
});
test("sign-out clears the page and reloads even when browser storage is blocked", async () => {
  const h=harness(); let reloaded=false;
  h.context.window.location={reload:()=>{reloaded=true;}};
  Object.defineProperty(h.context,'localStorage',{get:()=>{throw new Error('storage blocked');}});
  h.run("state.nativeDetail={id:'private-case'}");
  await h.get('sign-out').listeners.click();
  assert.equal(reloaded,true);
  assert.equal(h.run('state.nativeDetail'),null);
});
test("successful sign-in reloads instead of retaining the previous operator view", async () => {
  const h=harness(); let reloaded=false;
  h.context.window.location={reload:()=>{reloaded=true;}};
  h.run("state.nativeDetail={id:'old-case'}; state.pending={key:'old-key'}");
  h.get('access-key').value='new identity key';
  await h.get('login-form').listeners.submit({preventDefault(){}});
  assert.equal(reloaded,true);
  assert.equal(h.run('state.nativeDetail'),null);
  assert.equal(h.run('state.pending'),null);
  assert.equal(h.get('access-key').value,'');
});
