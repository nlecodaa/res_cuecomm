const DEFAULT_CENTER = [28.6139, 77.209];
const DEFAULT_ZOOM = 15;

const rows = document.querySelector("#incidentRows");
const emptyState = document.querySelector("#emptyState");
const activeCount = document.querySelector("#activeCount");
const criticalCount = document.querySelector("#criticalCount");
const dispatchedCount = document.querySelector("#dispatchedCount");
const socketBadge = document.querySelector("#socketBadge");

const incidents = new Map();
const markers = new Map();
let reconnectTimer = null;

const BACKEND_ORIGIN = (() => {
  const localBackend = ["127.0.0.1", "localhost"].includes(window.location.hostname) && window.location.port === "8000";
  return localBackend ? window.location.origin : "http://127.0.0.1:8000";
})();

function apiUrl(path) {
  return `${BACKEND_ORIGIN}${path}`;
}

function websocketUrl(role) {
  const backend = new URL(BACKEND_ORIGIN);
  const protocol = backend.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${backend.host}/ws?role=${role}`;
}

const map = L.map("dashboardMap").setView(DEFAULT_CENTER, DEFAULT_ZOOM);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function markerColor(incident) {
  if (incident.status === "Dispatched") return "#2563eb";
  if (incident.severity === "Critical") return "#dc2626";
  if (incident.severity === "High") return "#ea580c";
  if (incident.severity === "Medium") return "#f59e0b";
  return "#16a34a";
}

function incidentIcon(incident) {
  return L.divIcon({
    className: "incident-marker",
    html: `<span class="incident-marker-dot" style="background:${markerColor(incident)}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function popupContent(incident) {
  return `
    <strong>#${incident.id} ${escapeHtml(incident.category)}</strong><br>
    Severity: ${escapeHtml(incident.severity)}<br>
    Status: ${escapeHtml(incident.status)}<br>
    <span>${escapeHtml(incident.raw_text)}</span>
  `;
}

function severityRank(severity) {
  return { Critical: 0, High: 1, Medium: 2, Low: 3 }[severity] ?? 4;
}

function statusRank(status) {
  return { Pending: 0, Dispatched: 1, Resolved: 2 }[status] ?? 3;
}

function sortedIncidents() {
  return [...incidents.values()].sort((a, b) => {
    const bySeverity = severityRank(a.severity) - severityRank(b.severity);
    if (bySeverity !== 0) return bySeverity;
    const byStatus = statusRank(a.status) - statusRank(b.status);
    if (byStatus !== 0) return byStatus;
    return new Date(b.timestamp) - new Date(a.timestamp);
  });
}

function upsertMarker(incident) {
  if (incident.status === "Resolved") {
    removeMarker(incident.id);
    return;
  }

  const latLng = [incident.latitude, incident.longitude];
  if (markers.has(incident.id)) {
    markers.get(incident.id).setLatLng(latLng).setIcon(incidentIcon(incident)).bindPopup(popupContent(incident));
    return;
  }

  const marker = L.marker(latLng, { icon: incidentIcon(incident) })
    .addTo(map)
    .bindPopup(popupContent(incident));
  markers.set(incident.id, marker);
}

function removeMarker(id) {
  const marker = markers.get(id);
  if (!marker) return;
  marker.remove();
  markers.delete(id);
}

function upsertIncident(incident) {
  if (incident.status === "Resolved") {
    incidents.delete(incident.id);
    removeMarker(incident.id);
  } else {
    incidents.set(incident.id, incident);
    upsertMarker(incident);
  }

  render();
}

function badgeClass(base, value) {
  return `${base}-badge ${base}-${String(value).toLowerCase()}`;
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function makeTextCell(text, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text;
  return cell;
}

function makeBadgeCell(type, value) {
  const cell = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = badgeClass(type, value);
  badge.textContent = value;
  cell.appendChild(badge);
  return cell;
}

function makeActionsCell(incident) {
  const cell = document.createElement("td");
  cell.className = "text-end";

  const group = document.createElement("div");
  group.className = "btn-group btn-group-sm";
  group.setAttribute("role", "group");

  const deployButton = document.createElement("button");
  deployButton.type = "button";
  deployButton.className = "btn btn-outline-info";
  deployButton.textContent = "Deploy Unit";
  deployButton.disabled = incident.status === "Dispatched";
  deployButton.addEventListener("click", () => setTicketStatus(incident.id, "Dispatched"));

  const resolveButton = document.createElement("button");
  resolveButton.type = "button";
  resolveButton.className = "btn btn-outline-success";
  resolveButton.textContent = "Resolve";
  resolveButton.addEventListener("click", () => setTicketStatus(incident.id, "Resolved"));

  group.append(deployButton, resolveButton);
  cell.appendChild(group);
  return cell;
}

function render() {
  rows.replaceChildren();
  const active = sortedIncidents();

  active.forEach((incident) => {
    const row = document.createElement("tr");
    row.appendChild(makeTextCell(`#${incident.id}`));
    row.appendChild(makeTextCell(incident.category));
    row.appendChild(makeBadgeCell("severity", incident.severity));
    row.appendChild(makeBadgeCell("status", incident.status));
    row.appendChild(makeTextCell(incident.raw_text, "raw-cell"));
    row.appendChild(makeTextCell(formatTime(incident.timestamp)));
    row.appendChild(makeActionsCell(incident));
    rows.appendChild(row);
  });

  activeCount.textContent = active.length;
  criticalCount.textContent = active.filter((incident) => incident.severity === "Critical").length;
  dispatchedCount.textContent = active.filter((incident) => incident.status === "Dispatched").length;
  emptyState.classList.toggle("is-visible", active.length === 0);
}

async function setTicketStatus(id, status) {
  const response = await fetch(apiUrl(`/ticket/${id}/status`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    window.alert(error.detail || "Could not update ticket status.");
    return;
  }

  const incident = await response.json();
  upsertIncident(incident);
}

async function loadActiveIncidents() {
  const response = await fetch(apiUrl("/incidents"));
  if (!response.ok) throw new Error("Could not load incident feed.");
  const active = await response.json();
  incidents.clear();
  markers.forEach((marker) => marker.remove());
  markers.clear();
  active.forEach((incident) => incidents.set(incident.id, incident));
  active.forEach(upsertMarker);
  render();
}

function setSocketState(state) {
  socketBadge.textContent = state;
  socketBadge.className = `badge ${state === "Live" ? "text-bg-success" : state === "Connecting" ? "text-bg-secondary" : "text-bg-warning"}`;
}

function connectWebSocket() {
  setSocketState("Connecting");
  const socket = new WebSocket(websocketUrl("dashboard"));

  socket.addEventListener("open", () => {
    setSocketState("Live");
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  });

  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "snapshot") {
      incidents.clear();
      markers.forEach((marker) => marker.remove());
      markers.clear();
      payload.incidents.forEach((incident) => incidents.set(incident.id, incident));
      payload.incidents.forEach(upsertMarker);
      render();
      return;
    }

    if (payload.incident) {
      upsertIncident(payload.incident);
    }
  });

  socket.addEventListener("close", () => {
    setSocketState("Offline");
    reconnectTimer = window.setTimeout(connectWebSocket, 1500);
  });
}

loadActiveIncidents().catch(() => render());
connectWebSocket();
