"use strict";

// Credential-free GitHub Pages walkthrough. This intercepts the application's
// own API calls with labeled synthetic fixtures; it never contacts IRIS.
(() => {
  const originalFetch = window.fetch.bind(window);
  let executed = false;

  const now = () => new Date().toISOString();
  const later = (seconds) => new Date(Date.now() + seconds * 1000).toISOString();
  const task = {
    Id: 17,
    Name: "Battery Demonstration Task",
    Description: "Synthetic on-demand task with no external side effects",
    TaskClass: "Battery.Demo.Task",
    NameSpace: "USER",
    TimePeriod: "On Demand",
    Suspended: false,
    Status: "1",
  };
  const rule = {
    id: "task.intent.run-existing",
    version: 1,
    rationale:
      "The operator requested a new run. The adapter exposes task history for independent readback.",
    assumptions: [
      "The selected task is the intended target.",
      "The task is not suspended or already running.",
      "The operator reviewed its definition and side effects.",
    ],
    counterexamples: [
      "The target can change after preflight.",
      "A lost response can leave execution outcome ambiguous.",
    ],
    live_validations: [],
    validation: "SIMULATED",
    minimum_execution_validation: "SIMULATED",
  };
  const scenarios = [
    ["intentional_change", "A requested configuration change is applied and verified by fresh readback."],
    ["insufficient_privilege", "Missing authority blocks the request before dispatch."],
    ["failed_task_restraint", "A prior failure produces review evidence instead of an automatic retry."],
    ["stale_evidence", "Expired observations invalidate the authorization before execution."],
    ["ambiguous_transport", "A lost response is reconciled after one dispatch without resending the change."],
    ["wrong_rule_defense", "A draft rule cannot authorize a security-sensitive role grant."],
    ["concurrent_change", "A target changed after preflight is rejected before execution."],
    ["sensitive_values_absent", "Collected evidence excludes secret values and retains a valid ledger chain."],
  ].map(([name, detail]) => ({ name, detail, passed: true }));
  const quality = () => ({ quality: "VALID", captured_at: now() });
  const observation = (source, summary, values = null) => ({
    source,
    quality: "VALID",
    summary,
    captured_at: now(),
    freshness_seconds: 60,
    complete: true,
    values,
  });
  const receipt = () => ({
    id: "demo-receipt-0001",
    intent_id: "demo-intent-0001",
    action_id: "task.run-once",
    target: "task:17",
    operator: "pages-demo-operator",
    idempotency_key: "browser-generated-single-attempt-key",
    started_at: now(),
    finished_at: now(),
    status: "VERIFIED_SUCCESS",
    transport_result:
      "Synthetic dispatch became ambiguous; fresh history reconciled the original attempt without resend",
    before_evidence: ["evidence-server", "evidence-task", "evidence-history-before"],
    after_evidence: ["evidence-history-after"],
    explanation:
      "A fresh synthetic history row establishes the requested bounded outcome; one dispatch was recorded.",
    certificate_digest:
      "4ccff3cc0fb7760d42a54eee32dcba3d72ee421353bcc95cc85b25dcbb1c5003",
    verification_deadline: later(300),
  });
  const ledger = () =>
    executed
      ? [
          {
            sequence: 1,
            digest: "b628cdfee660d92c0458a6936777e290f7063ae7b7d2970f02023bd2cf5d5aed",
            event_type: "action_attempted",
            recorded_at: now(),
            target: "task:17",
            status: "OUTCOME_UNKNOWN",
          },
          {
            sequence: 2,
            digest: "c7aea5aeb532f207dad85c01b331346d2a240fc4903bfda5206c9a8d200d932a",
            event_type: "action_reconciled",
            recorded_at: now(),
            target: "task:17",
            status: "VERIFIED_SUCCESS",
          },
        ]
      : [];

  function json(data, status = 200) {
    return Promise.resolve(
      new Response(JSON.stringify(data), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }

  function prepared(reviewed) {
    const evidenceIds = [
      "evidence-server",
      "evidence-task",
      "evidence-history-before",
    ];
    return {
      intent: {
        id: "demo-intent-0001",
        kind: "RUN",
        target: "task:17",
        desired_outcome:
          "A new terminal history row exists for the requested task run.",
        requested_by: "pages-demo-operator",
        requested_at: now(),
      },
      finding: {
        state: reviewed ? "SAFE" : "BLOCKED",
        summary: reviewed
          ? "The requested task run is prepared."
          : "Task definition review is required.",
        consequence:
          "Execution may create the task's declared and external side effects.",
        evidence_ids: evidenceIds,
        missing_evidence: reviewed
          ? []
          : ["Review the task definition and acknowledge its side effects."],
        evaluated_at: now(),
        inference:
          "configured policy applied to current task, privilege, and history observations",
      },
      rule,
      task,
      history: [],
      certificate: reviewed
        ? {
            token: "pages-demo-single-use-certificate",
            intent_id: "demo-intent-0001",
            action_id: "task.run-once",
            target: "task:17",
            operator: "pages-demo-operator",
            issued_at: now(),
            expires_at: later(300),
            evidence_digest:
              "cc9945fcaeab96a4c160cbf7855c8ec0b1f0805844e14e4d4650a641f06d4453",
            used: false,
            evidence_ids: evidenceIds,
          }
        : null,
    };
  }

  function packet() {
    return {
      receipt: receipt(),
      evidence: [
        {
          id: "evidence-task",
          source: "GET /v1/task/info",
          target: "task:17",
          quality: "VALID",
          captured_at: now(),
          value: task,
        },
        {
          id: "evidence-history-after",
          source: "fresh task-history reconciliation",
          target: "task:17",
          quality: "VALID",
          captured_at: now(),
          value: [
            {
              TaskId: 17,
              Status: "Success",
              Result: "Success",
              Completed: now(),
            },
          ],
        },
      ],
      ledger: ledger(),
    };
  }

  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.startsWith("/api/")) return originalFetch(input, options);
    const path = url.pathname;
    const method = (options.method || "GET").toUpperCase();

    if (path === "/api/state")
      return json({
        captured_at: now(),
        mode: "synthetic",
        changes_enabled: true,
        server: {
          version: "synthetic-v1",
          username: "demo-operator",
          system_mode: "DEVELOPMENT",
        },
        tasks: [task],
        rule,
        ledger_valid: true,
        operator: "pages-demo-operator",
        access_mode: "credential-free labeled walkthrough",
        instance: "GitHub Pages synthetic fixture",
      });
    if (path === "/api/catalog")
      return json({
        quality: {
          namespaces: quality(),
          web_apps: quality(),
          users: quality(),
          roles: quality(),
          resources: quality(),
          tasks: quality(),
        },
        namespaces: ["USER"],
        web_apps: [
          {
            Name: "/api/existing",
            NameSpace: "USER",
            Enabled: true,
            Resource: "App.Reader",
            DispatchClass: "Demo.Existing",
          },
        ],
        users: [{ Name: "alex", FullName: "Alex Example", Enabled: true, Roles: [] }],
        roles: [
          {
            Name: "App.Reader",
            Description: "Read the demonstration application",
            GrantedRoles: [],
            Resources: [{ Name: "App.Reader", Permissions: "R" }],
          },
        ],
        resources: [
          { Name: "App.Reader", Description: "Demonstration application" },
        ],
        tasks: [task],
      });
    if (path === "/api/observations")
      return json({
        captured_at: now(),
        areas: {
          system: observation(
            "synthetic system fixture",
            "CPU 7% · memory 34% · 259 GB storage available",
          ),
          processes: observation("synthetic process fixture", "4 processes observed"),
          databases: observation("synthetic database fixture", "3 databases observed"),
          license: observation("synthetic license fixture", "Community license observable"),
          audit: observation("synthetic audit fixture", "Auditing enabled"),
          journals: observation("synthetic journal fixture", "2 recent files observed"),
          tls: observation("synthetic TLS fixture", "2 metadata records; secrets omitted"),
          wallets: observation("synthetic wallet fixture", "1 collection; secrets not requested"),
        },
      });
    if (path === "/api/assurance")
      return json({
        scope: "synthetic",
        available: true,
        passed: 8,
        total: 8,
        scenarios,
      });
    if (path === "/api/evidence") {
      const records = ledger();
      return json({
        valid: true,
        count: records.length,
        head: records.length ? records.at(-1).digest : null,
        records,
      });
    }
    if (path === "/api/receipts")
      return json({ receipts: executed ? [receipt()] : [] });
    if (path === "/api/tasks/17")
      return json({ task, captured_at: now(), quality: "VALID" });
    if (path === "/api/intents/task/17/run" && method === "POST") {
      const body = JSON.parse(options.body || "{}");
      return json(prepared(Boolean(body.task_definition_reviewed)));
    }
    if (path.includes("/api/intents/") && method === "POST")
      return json(
        { detail: "This hosted walkthrough executes the task-run example only." },
        409,
      );
    if (path.startsWith("/api/actions/task-run/") && method === "POST") {
      executed = true;
      return json(receipt());
    }
    if (path === "/api/receipts/demo-receipt-0001") return json(packet());
    return json({ detail: "This route is outside the hosted walkthrough." }, 404);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const banner = document.createElement("div");
    banner.className = "demo-banner";
    banner.setAttribute("role", "note");
    banner.innerHTML =
      '<strong>Credential-free synthetic walkthrough.</strong> No IRIS request is sent. Select <b>Try the one-dispatch proof</b>, review the demonstration task, then prepare and execute it once.';
    document.body.prepend(banner);
    document.querySelectorAll("#workflow option:not([value='run'])").forEach((option) => {
      option.disabled = true;
      option.textContent += " — local app only";
    });
  });
})();
