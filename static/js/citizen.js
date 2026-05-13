const DEFAULT_CENTER = [28.6139, 77.209];
const DEFAULT_ZOOM = 15;

const form = document.querySelector("#reportForm");
const rawText = document.querySelector("#rawText");
const submitBtn = document.querySelector("#submitBtn");
const locateBtn = document.querySelector("#locateBtn");
const formStatus = document.querySelector("#formStatus");

const map = L.map("citizenMap").setView(DEFAULT_CENTER, DEFAULT_ZOOM);
const markers = new Map();
let userMarker = null;
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

function setStatus(message, tone = "neutral") {
  formStatus.textContent = message;
  formStatus.className = `form-status mt-3 mb-0 text-${tone === "error" ? "danger" : tone === "success" ? "success" : "secondary"}`;
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

function publicPopup(incident) {
  return `
    <strong>${escapeHtml(incident.category)}</strong><br>
    Severity: ${escapeHtml(incident.severity)}<br>
    Status: ${escapeHtml(incident.status)}
  `;
}

function upsertIncident(incident) {
  if (incident.status === "Resolved") {
    removeIncident(incident.id);
    return;
  }

  const latLng = [incident.latitude, incident.longitude];
  if (markers.has(incident.id)) {
    markers.get(incident.id).setLatLng(latLng).setIcon(incidentIcon(incident)).bindPopup(publicPopup(incident));
    return;
  }

  const marker = L.marker(latLng, { icon: incidentIcon(incident) })
    .addTo(map)
    .bindPopup(publicPopup(incident));
  markers.set(incident.id, marker);
}

function removeIncident(id) {
  const marker = markers.get(id);
  if (!marker) return;
  marker.remove();
  markers.delete(id);
}

async function loadActiveIncidents() {
  const response = await fetch(apiUrl("/incidents/public"));
  if (!response.ok) throw new Error("Could not load active incidents.");
  const incidents = await response.json();
  incidents.forEach(upsertIncident);
}

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is unavailable."));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
        });
      },
      reject,
      { enableHighAccuracy: true, timeout: 7000, maximumAge: 15000 },
    );
  });
}

async function locateUser({ quiet = false } = {}) {
  try {
    const position = await getPosition();
    const latLng = [position.latitude, position.longitude];
    map.setView(latLng, DEFAULT_ZOOM);

    if (userMarker) {
      userMarker.setLatLng(latLng);
    } else {
      userMarker = L.circleMarker(latLng, {
        radius: 8,
        color: "#0f172a",
        weight: 2,
        fillColor: "#38bdf8",
        fillOpacity: 0.9,
      }).addTo(map).bindPopup("Your location");
    }

    if (!quiet) setStatus("Location detected.", "success");
    return position;
  } catch (error) {
    if (!quiet) setStatus("Location unavailable. Demo coordinates will be used.", "error");
    return {
      latitude: DEFAULT_CENTER[0],
      longitude: DEFAULT_CENTER[1],
      accuracy: null,
    };
  }
}

async function submitReport(event) {
  event.preventDefault();
  const text = rawText.value.trim();
  if (text.length < 3) {
    setStatus("Please describe the emergency in a little more detail.", "error");
    return;
  }

  submitBtn.disabled = true;
  locateBtn.disabled = true;
  setStatus("Capturing location and submitting report...");

  try {
    const position = await locateUser({ quiet: true });
    const response = await fetch(apiUrl("/report"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        raw_text: text,
        latitude: position.latitude,
        longitude: position.longitude,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Report submission failed.");
    }

    const incident = await response.json();
    rawText.value = "";
    setStatus(`Report submitted. Classified as ${incident.category} / ${incident.severity}.`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    submitBtn.disabled = false;
    locateBtn.disabled = false;
  }
}

function connectWebSocket() {
  const socket = new WebSocket(websocketUrl("citizen"));

  socket.addEventListener("open", () => {
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  });

  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "snapshot") {
      markers.forEach((marker) => marker.remove());
      markers.clear();
      payload.incidents.forEach(upsertIncident);
      return;
    }

    if (payload.incident) {
      upsertIncident(payload.incident);
    }
  });

  socket.addEventListener("close", () => {
    reconnectTimer = window.setTimeout(connectWebSocket, 1500);
  });
}

form.addEventListener("submit", submitReport);
locateBtn.addEventListener("click", () => locateUser());

loadActiveIncidents().catch((error) => setStatus(error.message, "error"));
connectWebSocket();
