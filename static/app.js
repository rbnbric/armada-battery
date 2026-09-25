const state = { certificate: null, actionType: null };
const byId = id => document.getElementById(id);

function text(tag, content, className = '') {
  const node = document.createElement(tag);
  node.textContent = String(content);
  if (className) node.className = className;
  return node;
}

function fillSelect(id, items, valueKey, labelKey = valueKey) {
  const select = byId(id);
  select.replaceChildren();
  items.forEach(item => {
    const option = document.createElement('option');
    option.value = valueKey ? item[valueKey] : item;
    option.textContent = labelKey ? item[labelKey] : item;
    if (item.Description) option.dataset.detail = item.Description;
    select.append(option);
  });
}

function showRule(rule) {
  const root = byId('rule');
  root.replaceChildren(
    text('p', `Validation: ${rule.validation}; execution requires ${rule.minimum_execution_validation}.`),
    text('p', rule.rationale),
    text('strong', 'Known counterexamples')
  );
  const list = text('ul', '', 'rule-list');
  rule.counterexamples.forEach(item => list.append(text('li', item)));
  root.append(list);
}

async function load() {
  const [stateResponse, catalogResponse, observationResponse, assuranceResponse] = await Promise.all([
    fetch('/api/state'), fetch('/api/catalog'), fetch('/api/observations'), fetch('/api/assurance')
  ]);
  const server = await stateResponse.json();
  const catalog = await catalogResponse.json();
  const observations = await observationResponse.json();
  const assurance = await assuranceResponse.json();
  if (!stateResponse.ok || !catalogResponse.ok || !observationResponse.ok || !assuranceResponse.ok) throw new Error(server.detail || catalog.detail || observations.detail || assurance.detail || 'API unavailable');
  byId('connection').textContent = `${server.mode.toUpperCase()} · ${server.server.version} · ${server.server.username}`;
  fillSelect('task', catalog.tasks, 'Id', 'Name');
  fillSelect('namespace', catalog.namespaces, null);
  fillSelect('resource', catalog.resources, 'Name');
  fillSelect('username', catalog.users, 'Name');
  fillSelect('role-name', catalog.roles, 'Name');
  byId('task').addEventListener('change', showTask);
  byId('workflow').addEventListener('change', showWorkflow);
  showTask();
  showWorkflow();
  showRule(server.rule);
  showObservations(observations.areas);
  showAssurance(assurance);
  await refreshEvidence();
}

function showObservations(areas) {
  const root = byId('observations');
  root.replaceChildren();
  Object.entries(areas).forEach(([name, area]) => {
    const card = text('article', '', 'observation');
    card.append(
      text('span', area.quality, `quality ${area.quality}`),
      text('h3', name),
      text('p', area.summary),
      text('small', area.source)
    );
    root.append(card);
  });
}

function showAssurance(report) {
  const root = byId('assurance-list');
  root.replaceChildren();
  if (!report.available) {
    byId('assurance-score').textContent = 'Live validation pending';
    root.append(text('p', report.detail, 'quiet'));
    return;
  }
  byId('assurance-score').textContent = `${report.passed} / ${report.total} scenarios proved`;
  report.scenarios.forEach(item => {
    const row = text('div', '', 'proof-row');
    row.append(text('span', item.name.replaceAll('_', ' ')), text('strong', item.passed ? 'PASS' : 'FAIL', item.passed ? 'success' : 'blocker'));
    root.append(row);
  });
}

async function refreshEvidence() {
  const response = await fetch('/api/evidence?limit=12');
  const trail = await response.json();
  byId('ledger-state').textContent = trail.valid ? 'Ledger chain verified' : 'Ledger integrity failure';
  const root = byId('evidence-list');
  root.replaceChildren();
  trail.records.slice().reverse().forEach(item => {
    const row = text('div', '', 'proof-row');
    row.append(text('span', `${item.sequence}. ${item.event_type}${item.target ? ` · ${item.target}` : ''}`), text('code', item.digest));
    root.append(row);
  });
  if (!trail.records.length) root.append(text('p', 'No actions prepared in this session.', 'quiet'));
}

function showTask() {
  const option = byId('task').selectedOptions[0];
  byId('task-detail').textContent = option ? option.dataset.detail || option.textContent : 'No tasks available';
}

function showWorkflow() {
  const workflow = byId('workflow').value;
  document.querySelectorAll('.workflow-fields').forEach(group => {
    group.hidden = !group.dataset.workflow.split(' ').includes(workflow);
  });
  state.certificate = null;
  byId('execute').disabled = true;
}

async function requestPlan() {
  const workflow = byId('workflow').value;
  const common = {};
  if (workflow === 'run') return fetch(`/api/intents/task/${byId('task').value}/run`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({...common, task_definition_reviewed: byId('reviewed').checked})
  });
  if (workflow === 'schedule') return fetch(`/api/intents/task/${byId('task').value}/schedule`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({...common, period: byId('period').value, start_time: byId('start-time').value, every: byId('every').value, day: byId('day').value})
  });
  if (workflow === 'webapp') return fetch('/api/intents/web-app/create', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({...common, name: byId('app-name').value, namespace: byId('namespace').value, dispatch_class: byId('dispatch').value, resource: byId('resource').value})
  });
  return fetch('/api/intents/access/grant-role', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({...common, username: byId('username').value, role_name: byId('role-name').value, role_reviewed: byId('role-reviewed').checked})
  });
}

byId('prepare').addEventListener('click', async () => {
  try {
    const response = await requestPlan();
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Preparation failed');
    byId('finding-title').textContent = data.finding.summary;
    byId('finding-copy').textContent = data.finding.consequence;
    const blockers = byId('blockers');
    blockers.replaceChildren();
    data.finding.missing_evidence.forEach(item => blockers.append(text('div', item, 'blocker')));
    showRule(data.rule);
    state.certificate = data.certificate?.token || null;
    state.actionType = byId('workflow').value === 'run' ? 'task-run' : 'admin';
    byId('execute').disabled = !state.certificate;
    byId('action-title').textContent = data.plan_state === 'SATISFIED' ? 'Outcome already satisfied' : state.certificate ? 'Action is eligible' : 'Execution blocked';
    byId('action-copy').textContent = data.finding.recommended_actions.join(' ');
    byId('execute').textContent = state.actionType === 'task-run' ? 'Run once and verify' : 'Apply once and verify';
    byId('receipt').replaceChildren();
    await refreshEvidence();
  } catch (error) {
    byId('action-title').textContent = 'Preparation failed';
    byId('action-copy').textContent = error.message;
  }
});

byId('execute').addEventListener('click', async () => {
  byId('execute').disabled = true;
  const path = state.actionType === 'task-run' ? 'task-run' : 'admin';
  const response = await fetch(`/api/actions/${path}/${state.certificate}/execute`, {
    method: 'POST', headers: {'Idempotency-Key': crypto.randomUUID()}
  });
  const data = await response.json();
  const root = byId('receipt');
  root.replaceChildren(
    text('strong', data.status || 'REQUEST FAILED', data.status === 'VERIFIED_SUCCESS' ? 'success' : ''),
    text('p', data.explanation || data.detail)
  );
  await refreshEvidence();
});

load().catch(error => { byId('connection').textContent = `Unavailable: ${error.message}`; });
