const state = {
  bikes: [],
  entries: [],
  components: [],
  filterBikeId: "",
  modalKind: null,
  editingId: null,
};

const $ = (sel) => document.querySelector(sel);

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

function fmtDate(iso) {
  const [y, m, d] = String(iso).split("-");
  return `${d}.${m}.${y}`;
}

function fmtKm(n) {
  const v = Number(n);
  const str = Number.isInteger(v)
    ? v.toLocaleString("nb-NO")
    : v.toLocaleString("nb-NO", { maximumFractionDigits: 1 });
  return `${str} km`;
}

function badgeColor(key) {
  let h = 0;
  for (const ch of key) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${h} 45% 38%)`;
}

function todayIso() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  if (res.status !== 204) {
    data = await res.json().catch(() => null);
  }
  if (!res.ok) {
    throw new Error((data && data.error) || `Feil (${res.status})`);
  }
  return data;
}

async function loadAll() {
  const [bikes, entries, components] = await Promise.all([
    api("GET", "/api/bikes"),
    api("GET", "/api/service"),
    api("GET", "/api/components"),
  ]);
  state.bikes = bikes;
  state.entries = entries;
  state.components = components;
}

function renderBikes() {
  const list = $("#bike-list");
  if (!state.bikes.length) {
    list.innerHTML = `<div class="empty">Ingen sykler ennå. Trykk «+ Legg til sykkel».</div>`;
    return;
  }
  list.innerHTML = state.bikes.map((b) => {
    const last = b.last_component
      ? `Siste service: ${esc(b.last_component)} · ${fmtDate(b.last_date)} (ved ${fmtKm(b.last_km)})`
      : "Ingen service registrert ennå";
    return `
      <div class="card bike-card">
        <div>
          <div class="bike-title">${esc(b.owner)}</div>
          <div class="bike-sub">${esc(b.type)} · ${fmtKm(b.km)}</div>
          <div class="bike-last">${esc(last)}</div>
        </div>
        <div class="card-actions">
          <button class="btn small" data-action="edit-bike" data-id="${b.id}" type="button">Rediger</button>
          <button class="btn small danger" data-action="del-bike" data-id="${b.id}" type="button">Slett</button>
        </div>
      </div>`;
  }).join("");
}

function renderFilter() {
  const sel = $("#filter-bike");
  const current = state.filterBikeId;
  sel.innerHTML =
    `<option value="">Alle sykler</option>` +
    state.bikes.map((b) => `<option value="${b.id}">${esc(b.owner)} (${esc(b.type)})</option>`).join("");
  sel.value = current;
}

function renderEntries() {
  const list = $("#entry-list");
  const filtered = state.filterBikeId
    ? state.entries.filter((e) => String(e.bike_id) === state.filterBikeId)
    : state.entries;
  if (!filtered.length) {
    list.innerHTML = `<div class="empty">Ingen serviceoppføringer ennå.</div>`;
    return;
  }
  list.innerHTML = filtered.map((e) => {
    const note = e.note ? `<div class="entry-note">${esc(e.note)}</div>` : "";
    return `
      <div class="card entry-card">
        <div>
          <div class="entry-head">
            <span class="badge" style="background:${badgeColor(e.component)}">${esc(e.component_label)}</span>
            <span class="entry-bike">${esc(e.bike_owner)} · ${esc(e.bike_type)}</span>
          </div>
          <div class="entry-meta">${fmtDate(e.date)} · ved ${fmtKm(e.km)}</div>
          ${note}
        </div>
        <div class="card-actions">
          <button class="btn small" data-action="edit-entry" data-id="${e.id}" type="button">Rediger</button>
          <button class="btn small danger" data-action="del-entry" data-id="${e.id}" type="button">Slett</button>
        </div>
      </div>`;
  }).join("");
}

function renderAll() {
  renderBikes();
  renderFilter();
  renderEntries();
}

function field(label, inner) {
  return `<label class="field"><span>${esc(label)}</span>${inner}</label>`;
}

function openBikeForm(bike) {
  state.modalKind = "bike";
  state.editingId = bike ? bike.id : null;
  $("#modal-title").textContent = bike ? "Rediger sykkel" : "Ny sykkel";
  $("#modal-form").innerHTML =
    field("Eier (navn)", `<input id="f-owner" required maxlength="100" value="${esc(bike ? bike.owner : "")}" placeholder="f.eks. Anna">`) +
    field("Type sykkel", `<input id="f-type" list="bike-types" required maxlength="100" value="${esc(bike ? bike.type : "")}" placeholder="f.eks. Terrengsykkel">
      <datalist id="bike-types">
        <option value="Terrengsykkel"></option>
        <option value="Landeveisssykkel"></option>
        <option value="El-sykkel"></option>
        <option value="Hybrid"></option>
        <option value="Gravelsykkel"></option>
        <option value="Barnesykkel"></option>
        <option value="Downhill"></option>
        <option value="Annet"></option>
      </datalist>`) +
    field("Km-stand nå", `<input id="f-km" type="number" min="0" step="0.5" required value="${bike ? bike.km : 0}">`);
  $("#modal").hidden = false;
  $("#f-owner").focus();
}

function openEntryForm(entry) {
  state.modalKind = "entry";
  state.editingId = entry ? entry.id : null;
  $("#modal-title").textContent = entry ? "Rediger service" : "Ny service";
  const bikeOptions = state.bikes.map((b) =>
    `<option value="${b.id}" ${entry && entry.bike_id === b.id ? "selected" : ""}>${esc(b.owner)} (${esc(b.type)}, ${fmtKm(b.km)})</option>`
  ).join("");
  const compOptions = state.components.map((c) =>
    `<option value="${esc(c.key)}" ${entry && entry.component === c.key ? "selected" : ""}>${esc(c.label)}</option>`
  ).join("");
  $("#modal-form").innerHTML =
    field("Sykkel", `<select id="f-bike-id" required>${bikeOptions}</select>`) +
    field("Komponent", `<select id="f-component" required>${compOptions}</select>`) +
    field("Dato", `<input id="f-date" type="date" required value="${entry ? entry.date : todayIso()}">`) +
    field("Km-stand ved bytte", `<input id="f-km" type="number" min="0" step="0.5" required value="${entry ? entry.km : ""}" placeholder="f.eks. 1150">`) +
    field("Merknad (valgfritt: modell, pris osv.)", `<textarea id="f-note" rows="3" maxlength="1000" placeholder="f.eks. Shimano Deore, ca. 250 kr">${esc(entry ? entry.note : "")}</textarea>`);
  $("#modal").hidden = false;
  $("#f-bike-id").focus();
}

function closeModal() {
  $("#modal").hidden = true;
  state.modalKind = null;
  state.editingId = null;
}

let toastTimer = null;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

async function saveModal() {
  try {
    if (state.modalKind === "bike") {
      const body = {
        owner: $("#f-owner").value.trim(),
        type: $("#f-type").value.trim(),
        km: Number($("#f-km").value),
      };
      if (!body.owner || !body.type || $("#f-km").value === "" || Number.isNaN(body.km)) {
        throw new Error("Fyll ut eier, type og km-stand.");
      }
      if (state.editingId) {
        await api("PUT", `/api/bikes/${state.editingId}`, body);
        toast("Sykkel oppdatert");
      } else {
        await api("POST", "/api/bikes", body);
        toast("Sykkel lagt til");
      }
    } else if (state.modalKind === "entry") {
      const body = {
        bike_id: Number($("#f-bike-id").value),
        component: $("#f-component").value,
        date: $("#f-date").value,
        km: Number($("#f-km").value),
        note: $("#f-note").value.trim(),
      };
      if (!$("#f-bike-id").value || !body.date || $("#f-km").value === "" || Number.isNaN(body.km)) {
        throw new Error("Fyll ut sykkel, komponent, dato og km.");
      }
      if (state.editingId) {
        await api("PUT", `/api/service/${state.editingId}`, body);
        toast("Service oppdatert");
      } else {
        await api("POST", "/api/service", body);
        toast("Service registrert");
      }
    }
    closeModal();
    await loadAll();
    renderAll();
  } catch (err) {
    toast(err.message || "Noe gikk galt");
  }
}

async function handleAction(action, id) {
  if (action === "edit-bike") {
    const bike = state.bikes.find((b) => b.id === id);
    if (bike) openBikeForm(bike);
  } else if (action === "del-bike") {
    const bike = state.bikes.find((b) => b.id === id);
    if (!bike) return;
    const count = bike.entry_count || 0;
    const msg = count > 0
      ? `Slette ${bike.owner} (${bike.type})? ${count} serviceoppføring(er) slettes også.`
      : `Slette ${bike.owner} (${bike.type})?`;
    if (!confirm(msg)) return;
    try {
      await api("DELETE", `/api/bikes/${id}`);
      toast("Sykkel slettet");
      await loadAll();
      renderAll();
    } catch (err) {
      toast(err.message);
    }
  } else if (action === "edit-entry") {
    const entry = state.entries.find((e) => e.id === id);
    if (entry) openEntryForm(entry);
  } else if (action === "del-entry") {
    if (!confirm("Slette denne serviceoppføringen?")) return;
    try {
      await api("DELETE", `/api/service/${id}`);
      toast("Serviceoppføring slettet");
      await loadAll();
      renderAll();
    } catch (err) {
      toast(err.message);
    }
  }
}

function switchTab(which) {
  const bikesActive = which === "bikes";
  $("#tab-bikes").classList.toggle("active", bikesActive);
  $("#tab-service").classList.toggle("active", !bikesActive);
  $("#view-bikes").hidden = !bikesActive;
  $("#view-service").hidden = bikesActive;
}

async function init() {
  $("#tab-bikes").addEventListener("click", () => switchTab("bikes"));
  $("#tab-service").addEventListener("click", () => switchTab("service"));
  $("#btn-add-bike").addEventListener("click", () => openBikeForm(null));
  $("#btn-add-entry").addEventListener("click", () => openEntryForm(null));
  $("#filter-bike").addEventListener("change", (e) => {
    state.filterBikeId = e.target.value;
    renderEntries();
  });
  $("#modal-cancel").addEventListener("click", closeModal);
  $("#modal-save").addEventListener("click", saveModal);
  $("#modal-form").addEventListener("submit", (e) => e.preventDefault());
  $("#modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (btn) handleAction(btn.dataset.action, Number(btn.dataset.id));
  });
  try {
    await loadAll();
    renderAll();
  } catch (err) {
    toast("Kunne ikke laste data: " + err.message);
  }
}

init();
