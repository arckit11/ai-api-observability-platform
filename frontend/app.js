// Static single-page dashboard for the API Performance Analytics platform.
// No build step, no framework — just the fetch API against the gateway.

const state = {
  token: sessionStorage.getItem('iapi_token') || null,
  gatewayUrl: sessionStorage.getItem('iapi_gw') || 'http://localhost:8080',
};

// ─── helpers ──────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...children) => {
  const n = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === 'class') n.className = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  });
  children.flat().forEach((c) => {
    n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  });
  return n;
};

const short = (id) => (id ? String(id).slice(0, 8) + '…' : '—');
const fmt = (n, digits = 1) =>
  n == null ? '—' : Number(n).toLocaleString(undefined, { maximumFractionDigits: digits });
const pct = (n) => (n == null ? '—' : (Number(n) * 100).toFixed(1) + '%');

async function api(path) {
  const url = `${state.gatewayUrl}${path}`;
  const headers = { 'Accept': 'application/json' };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return res.json();
}

function setStatus(text, kind = '') {
  const el = $('#status');
  el.textContent = text;
  el.className = 'pill ' + kind;
}

// ─── auth ─────────────────────────────────────────────────────
async function login() {
  const body = {
    username: $('#username').value,
    password: $('#password').value,
  };
  const res = await fetch(`${state.gatewayUrl}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status}`);
  const data = await res.json();
  state.token = data.access_token;
  sessionStorage.setItem('iapi_token', state.token);
  $('#auth-status').textContent = `signed in as ${body.username}`;
  $('#auth-status').className = 'pill ok';
  await refreshAll();
}

// ─── tiles ────────────────────────────────────────────────────
async function loadHealth() {
  const data = await api('/dashboard/health');
  const root = $('#health');
  root.replaceChildren();
  data.forEach((row) => {
    const h = row.health || {};
    const status = (h.status || 'unknown').toLowerCase();
    const score = h.score != null ? Math.round(h.score) : '—';
    root.append(
      el('div', { class: 'service-card' },
        el('h3', {}, short(row.service_id)),
        el('div', { class: 'score' }, score),
        el('span', { class: 'status ' + status }, status),
        h.stale ? el('div', { class: 'spark' }, 'stale · fallback') : null,
      ),
    );
  });
}

async function loadTraffic() {
  const data = await api('/dashboard/traffic');
  const t = $('#traffic-table');
  t.replaceChildren(
    el('thead', {}, el('tr', {},
      el('th', {}, 'Service'),
      el('th', { class: 'num' }, 'Current RPM'),
      el('th', { class: 'num' }, 'Forecast (60 min)'),
      el('th', { class: 'num' }, 'Δ'),
    )),
  );
  const body = el('tbody');
  data.forEach((row) => {
    const curr = row.latest?.rpm;
    const fc = row.forecast?.predicted_rpm;
    const delta = curr != null && fc != null ? fc - curr : null;
    const spark = delta == null ? '' : (delta > 0 ? '↑' : delta < 0 ? '↓' : '·');
    const cls = delta == null ? 'spark' : delta > 0 ? 'spark up' : 'spark down';
    body.append(el('tr', {},
      el('td', { class: 'mono' }, short(row.service_id)),
      el('td', { class: 'num' }, fmt(curr)),
      el('td', { class: 'num' }, fmt(fc)),
      el('td', { class: 'num' },
        el('span', { class: cls }, `${spark} ${delta == null ? '' : fmt(Math.abs(delta))}`)),
    ));
  });
  t.append(body);
}

async function loadLatency() {
  const data = await api('/dashboard/latency');
  const t = $('#latency-table');
  t.replaceChildren(
    el('thead', {}, el('tr', {},
      el('th', {}, 'Service'),
      el('th', { class: 'num' }, 'Mean (ms)'),
      el('th', { class: 'num' }, 'P95 (ms)'),
      el('th', { class: 'num' }, 'P99 (ms)'),
    )),
  );
  const body = el('tbody');
  data.forEach((row) => {
    body.append(el('tr', {},
      el('td', { class: 'mono' }, short(row.service_id)),
      el('td', { class: 'num' }, fmt(row.mean)),
      el('td', { class: 'num' }, fmt(row.p95)),
      el('td', { class: 'num' }, fmt(row.p99)),
    ));
  });
  t.append(body);
}

async function loadPredictions() {
  const data = await api('/dashboard/predictions');
  const t = $('#predictions-table');
  t.replaceChildren(
    el('thead', {}, el('tr', {},
      el('th', {}, 'Service'),
      el('th', { class: 'num' }, 'Anomaly score'),
      el('th', {}, 'Anomaly?'),
      el('th', { class: 'num' }, 'Failure prob.'),
      el('th', {}, 'Risk'),
    )),
  );
  const body = el('tbody');
  data.forEach((row) => {
    const a = row.anomaly || {};
    const f = row.failure || {};
    const risk = f.risk_level || '—';
    body.append(el('tr', {},
      el('td', { class: 'mono' }, short(row.service_id)),
      el('td', { class: 'num' }, fmt(a.anomaly_score, 3)),
      el('td', {}, a.is_anomaly ? 'yes' : 'no'),
      el('td', { class: 'num' }, pct(f.failure_probability)),
      el('td', {}, el('span', { class: 'status ' + risk }, risk)),
    ));
  });
  t.append(body);
}

async function loadAlerts() {
  const data = await api('/dashboard/alerts');
  const t = $('#alerts-table');
  if (!data.length) {
    t.replaceChildren(el('caption', {}, 'no open alerts — everything looks green'));
    return;
  }
  t.replaceChildren(
    el('thead', {}, el('tr', {},
      el('th', {}, 'Opened'),
      el('th', {}, 'Service'),
      el('th', {}, 'Trigger'),
      el('th', {}, 'Severity'),
      el('th', {}, 'ML priority'),
      el('th', {}, 'Message'),
    )),
  );
  const body = el('tbody');
  data.forEach((a) => {
    const mlP = a.ml_priority?.priority || '—';
    body.append(el('tr', {},
      el('td', { class: 'mono' }, new Date(a.opened_at).toLocaleTimeString()),
      el('td', { class: 'mono' }, short(a.service_id)),
      el('td', {}, a.triggering_metric),
      el('td', {}, el('span', { class: 'status ' + (a.severity || '') }, a.severity || '—')),
      el('td', {}, el('span', { class: 'status ' + mlP }, mlP)),
      el('td', {}, a.message),
    ));
  });
  t.append(body);
}

// ─── orchestration ────────────────────────────────────────────
const LOADERS = {
  health: loadHealth,
  traffic: loadTraffic,
  latency: loadLatency,
  predictions: loadPredictions,
  alerts: loadAlerts,
};

async function refresh(name) {
  if (!state.token) { setStatus('sign in first', 'err'); return; }
  setStatus(`loading ${name}…`);
  try {
    await LOADERS[name]();
    setStatus(`${name} updated ${new Date().toLocaleTimeString()}`, 'ok');
  } catch (e) {
    console.error(e);
    setStatus(`${name} failed: ${e.message}`, 'err');
  }
}

async function refreshAll() {
  if (!state.token) { setStatus('sign in first', 'err'); return; }
  setStatus('loading all tiles…');
  await Promise.allSettled(Object.keys(LOADERS).map(refresh));
  setStatus(`refreshed ${new Date().toLocaleTimeString()}`, 'ok');
}

// ─── wire ─────────────────────────────────────────────────────
document.querySelectorAll('[data-refresh]').forEach((btn) => {
  btn.addEventListener('click', () => refresh(btn.dataset.refresh));
});
$('#refresh-all').addEventListener('click', refreshAll);
$('#login').addEventListener('click', () => {
  login().catch((e) => setStatus(`login: ${e.message}`, 'err'));
});
$('#gateway-url').addEventListener('change', (e) => {
  state.gatewayUrl = e.target.value.trim();
  sessionStorage.setItem('iapi_gw', state.gatewayUrl);
});
$('#gateway-url').value = state.gatewayUrl;

if (state.token) {
  $('#auth-status').textContent = 'signed in (cached)';
  $('#auth-status').className = 'pill ok';
  refreshAll();
} else {
  setStatus('sign in to load data');
}
