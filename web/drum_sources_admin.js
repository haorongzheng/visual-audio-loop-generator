const drumSounds = [["Ambient", "ambient"], ["Acoustic", "acoustic"], ["Organic", "organic"], ["Vintage", "vintage"], ["Electronic", "electronic"], ["Ethnic", "ethnic"], ["Cinematic", "cinematic"]];
const drumEnergies = [["静止", "静止"], ["高能", "高能"], ["流动", "流动"]];
const drumRhythms = [["Sparse", "sparse"], ["Flow", "flow"], ["Standard", "standard"], ["Groove", "groove"], ["Aggressive", "aggressive"]];

const slotDefinitions = {
  kick: ["Kick", 36],
  snare: ["Snare", 38],
  clap: ["Clap", 39],
  closed_hat: ["Closed Hat", 42],
  open_hat: ["Open Hat", 46],
  shaker: ["Shaker", 70],
  perc_1: ["Perc 1", 75],
  perc_2: ["Perc 2", 76],
  low_tom: ["Low Tom", 45],
  high_tom: ["High Tom", 50],
  crash: ["Crash", 49],
  ride: ["Ride", 51],
  impact: ["Impact", 55],
  fill_hit: ["Fill Hit", 48],
  texture_perc: ["Texture Perc", 82]
};

const roundRobinModes = ["off", "sequential", "random", "weighted_random"];
let selectedSound = "electronic";
let selectedEnergy = "流动";
let selectedRhythm = "groove";
let selectedSlot = "kick";
let currentKit = null;
let coverage = null;

const $ = (id) => document.getElementById(id);
const isFilePreview = location.protocol === "file:";

if (isFilePreview) {
  document.querySelectorAll("a[href='/']").forEach((link) => (link.href = "index.html"));
  document.querySelectorAll("a[href='/admin/index.html']").forEach((link) => (link.href = "samples_admin.html"));
}

function defaultKit() {
  const slots = {};
  Object.entries(slotDefinitions).forEach(([slotId, [label, midi]]) => {
    slots[slotId] = {
      slot_type: slotId,
      label,
      midi_note: midi,
      enabled: true,
      round_robin_mode: "weighted_random",
      choke_group: slotId.includes("hat") ? "hat" : slotId === "crash" || slotId === "ride" ? "crash" : null,
      description: "",
      samples: []
    };
  });
  return {
    kit_id: `kit_${selectedSound}_${selectedEnergy}_${selectedRhythm}`,
    name: `${selectedSound} / ${selectedEnergy} / ${selectedRhythm}`,
    enabled: true,
    tags: { sound_direction: selectedSound, energy: selectedEnergy, rhythm: selectedRhythm },
    slots
  };
}

function renderChoiceGroup(containerId, items, selected, onPick) {
  const container = $(containerId);
  container.innerHTML = "";
  items.forEach(([label, value]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `choice ${value === selected ? "active" : ""}`;
    button.textContent = label;
    button.addEventListener("click", () => {
      onPick(value);
      loadKit();
    });
    container.appendChild(button);
  });
}

async function loadKit() {
  if (isFilePreview) {
    currentKit = currentKit || defaultKit();
    coverage = computeLocalCoverage(currentKit);
    renderAll();
    return;
  }
  const url = `/api/drum-sources?sound_direction=${encodeURIComponent(selectedSound)}&energy=${encodeURIComponent(selectedEnergy)}&rhythm=${encodeURIComponent(selectedRhythm)}`;
  const response = await fetch(url);
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "加载失败");
  currentKit = payload.kit;
  coverage = payload.coverage;
  renderAll();
}

function renderAll() {
  renderFilters();
  renderPath();
  renderSlotGrid();
  renderEditor();
  renderCoverage();
  $("drum-kit-json").textContent = JSON.stringify(currentKit, null, 2);
}

function renderFilters() {
  renderChoiceGroup("drum-sound-options", drumSounds, selectedSound, (value) => (selectedSound = value));
  renderChoiceGroup("drum-energy-options", drumEnergies, selectedEnergy, (value) => (selectedEnergy = value));
  renderChoiceGroup("drum-rhythm-options", drumRhythms, selectedRhythm, (value) => (selectedRhythm = value));
}

function renderPath() {
  const soundLabel = drumSounds.find((item) => item[1] === selectedSound)?.[0] || selectedSound;
  const rhythmLabel = drumRhythms.find((item) => item[1] === selectedRhythm)?.[0] || selectedRhythm;
  $("current-kit-path").textContent = `${soundLabel} / ${selectedEnergy} / ${rhythmLabel}`;
  $("coverage-label").textContent = `Coverage ${coverage?.percent ?? 0}%`;
}

function renderSlotGrid() {
  const slots = currentKit?.slots || {};
  $("slot-count").textContent = `${Object.keys(slotDefinitions).length} Slots`;
  $("drum-slot-grid").innerHTML = Object.entries(slotDefinitions)
    .map(([slotId, [label, defaultMidi]]) => slotCard(slotId, slots[slotId] || { label, midi_note: defaultMidi, samples: [] }))
    .join("");
  document.querySelectorAll(".drum-slot-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectedSlot = card.dataset.slot;
      renderAll();
    });
  });
  document.querySelectorAll(".slot-play").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      playSlot(button.dataset.slot);
    });
  });
}

function slotCard(slotId, slot) {
  const samples = slot.samples || [];
  const main = samples[0]?.file_name || "None";
  const active = selectedSlot === slotId ? "active" : "";
  const enabled = slot.enabled !== false ? "ON" : "OFF";
  return `
    <article class="drum-slot-card ${active}" data-slot="${slotId}">
      <div class="slot-card-head">
        <b>${slot.label || slotDefinitions[slotId][0]}</b>
        <button type="button" class="track-toggle slot-play" data-slot="${slotId}">▶</button>
      </div>
      <span>MIDI Note: ${slot.midi_note ?? slotDefinitions[slotId][1]}</span>
      <span>Samples: ${samples.length}</span>
      <span>Main: ${escapeHtml(main)}</span>
      <div class="wave-mini"></div>
      <span>Enabled: ${enabled}</span>
      <span>Variation: ${samples.length}</span>
      <span>Velocity Layer: ${samples.length ? "ON" : "OFF"}</span>
    </article>
  `;
}

function renderEditor() {
  const slot = activeSlot();
  $("selected-slot-label").textContent = slot.label;
  $("slot-label").value = slot.label;
  $("slot-midi-note").value = slot.midi_note;
  $("slot-enabled").checked = slot.enabled !== false;
  fillSelect("slot-round-robin", roundRobinModes);
  $("slot-round-robin").value = slot.round_robin_mode || "weighted_random";
  $("slot-choke-group").value = slot.choke_group || "";
  $("slot-description").value = slot.description || "";
  $("slot-upload-label").textContent = `Upload ${slot.label} Sample`;
  $("variation-list").innerHTML = (slot.samples || []).map((sample, index) => variationMarkup(sample, index)).join("") || `<div class="sample-overlay-empty"><b>No samples</b><span>Upload files to this slot.</span></div>`;
  bindVariationInputs();
}

function activeSlot() {
  return currentKit.slots[selectedSlot];
}

function collectEditor() {
  const slot = activeSlot();
  slot.label = $("slot-label").value.trim() || slot.label;
  slot.midi_note = Number($("slot-midi-note").value || slot.midi_note);
  slot.enabled = $("slot-enabled").checked;
  slot.round_robin_mode = $("slot-round-robin").value;
  slot.choke_group = $("slot-choke-group").value.trim() || null;
  slot.description = $("slot-description").value;
  return slot;
}

function variationMarkup(sample, index) {
  const p = sample.playback || {};
  return `
    <article class="variation-card" data-index="${index}">
      <div class="slot-card-head">
        <b>${escapeHtml(sample.name || sample.file_name || "Sample")}</b>
        <button type="button" class="track-toggle variation-play" data-index="${index}">▶</button>
      </div>
      <span>${escapeHtml(sample.file_name || "")}</span>
      <audio controls preload="none" src="${sample.file_url}"></audio>
      <div class="variation-grid">
        <label>Vel Min<input data-field="velocity_min" value="${p.velocity_min ?? 1}" type="number" min="1" max="127" /></label>
        <label>Vel Max<input data-field="velocity_max" value="${p.velocity_max ?? 127}" type="number" min="1" max="127" /></label>
        <label>Weight<input data-field="weight" value="${p.weight ?? 50}" type="number" min="1" /></label>
        <label>Gain dB<input data-field="gain_db" value="${p.gain_db ?? 0}" type="number" step="0.1" /></label>
        <label>Pan<input data-field="pan" value="${p.pan ?? 0}" type="number" step="0.01" min="-1" max="1" /></label>
        <label>Offset ms<input data-field="start_offset_ms" value="${p.start_offset_ms ?? 0}" type="number" min="0" /></label>
        <label>Fade Out<input data-field="fade_out_ms" value="${p.fade_out_ms ?? 10}" type="number" min="0" /></label>
      </div>
      <label class="check-row"><input data-field="enabled" type="checkbox" ${p.enabled !== false ? "checked" : ""} />Enabled</label>
      <button type="button" class="danger-button variation-delete" data-index="${index}">Delete</button>
    </article>
  `;
}

function bindVariationInputs() {
  document.querySelectorAll(".variation-card input").forEach((input) => {
    input.addEventListener("input", () => {
      const card = input.closest(".variation-card");
      const sample = activeSlot().samples[Number(card.dataset.index)];
      const field = input.dataset.field;
      if (field === "enabled") sample.playback[field] = input.checked;
      else sample.playback[field] = Number(input.value);
      updateJson();
    });
  });
  document.querySelectorAll(".variation-play").forEach((button) => button.addEventListener("click", () => playSample(activeSlot().samples[Number(button.dataset.index)])));
  document.querySelectorAll(".variation-delete").forEach((button) => {
    button.addEventListener("click", () => {
      activeSlot().samples.splice(Number(button.dataset.index), 1);
      renderAll();
    });
  });
}

function renderCoverage() {
  const uploaded = coverage?.uploaded || {};
  $("slot-coverage").innerHTML = Object.entries(slotDefinitions)
    .map(([slotId, [label]]) => `<div class="coverage-row"><span>${label}</span><b>${uploaded[slotId] || 0}</b></div>`)
    .join("");
  const missing = coverage?.missing_required || [];
  $("missing-slots").innerHTML = missing.length ? `<b>Missing Required Slots</b>${missing.map((item) => `<span>${item}</span>`).join("")}` : `<b>Required Slots OK</b>`;
}

async function saveKit() {
  collectEditor();
  if (isFilePreview) {
    $("drum-admin-status").textContent = "预览模式";
    updateJson();
    return;
  }
  const response = await fetch("/api/drum-sources/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kit: currentKit })
  });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "保存失败");
  currentKit = payload.kit;
  coverage = payload.coverage;
  $("drum-admin-status").textContent = "已保存";
  renderAll();
}

async function uploadFiles(files, slotType = selectedSlot) {
  if (!files.length) return;
  if (isFilePreview) {
    $("drum-admin-status").textContent = "预览模式不能保存上传";
    return;
  }
  const form = new FormData();
  [...files].forEach((file) => form.append("files", file));
  form.append("sound_direction", selectedSound);
  form.append("energy", selectedEnergy);
  form.append("rhythm", selectedRhythm);
  form.append("slot_type", slotType || "");
  const response = await fetch("/api/drum-sources/upload", { method: "POST", body: form });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "上传失败");
  currentKit = payload.kit;
  coverage = payload.coverage;
  selectedSlot = slotType || selectedSlot;
  $("drum-admin-status").textContent = "已上传";
  renderAll();
}

function duplicateKit() {
  currentKit.kit_id = `${currentKit.kit_id}_copy_${Date.now()}`;
  currentKit.name = `${currentKit.name} Copy`;
  $("drum-admin-status").textContent = "已复制，点击 Save Kit 保存";
  renderAll();
}

function exportKit() {
  const blob = new Blob([JSON.stringify(currentKit, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${currentKit.kit_id}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function importKit(file) {
  if (!file) return;
  const text = await file.text();
  const data = JSON.parse(text);
  if (isFilePreview) {
    currentKit = data.kit || data;
    coverage = computeLocalCoverage(currentKit);
    renderAll();
    return;
  }
  const response = await fetch("/api/drum-sources/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "导入失败");
  $("drum-admin-status").textContent = "已导入";
  await loadKit();
}

function playSlot(slotId) {
  const sample = (currentKit.slots[slotId]?.samples || []).find((item) => item.enabled !== false);
  if (sample) playSample(sample);
}

function playSample(sample) {
  if (!sample?.file_url) return;
  const player = $("drum-preview-player");
  player.src = sample.file_url;
  player.load();
  player.play().catch(() => {});
}

function playPattern() {
  const order = ["kick", "closed_hat", "snare", "closed_hat", "kick", "open_hat", "snare", "closed_hat"];
  let index = 0;
  window.clearInterval(window.drumPatternTimer);
  playSlot(order[index]);
  window.drumPatternTimer = window.setInterval(() => {
    index += 1;
    if (index >= order.length) {
      window.clearInterval(window.drumPatternTimer);
      return;
    }
    playSlot(order[index]);
  }, 240);
}

function stopPreview() {
  window.clearInterval(window.drumPatternTimer);
  $("drum-preview-player").pause();
}

function computeLocalCoverage(kit) {
  const uploaded = {};
  Object.keys(slotDefinitions).forEach((slotId) => (uploaded[slotId] = kit.slots?.[slotId]?.samples?.length || 0));
  const covered = Object.values(uploaded).filter(Boolean).length;
  return { percent: Math.round((covered / Object.keys(slotDefinitions).length) * 100), uploaded, missing_required: [] };
}

function fillSelect(id, options) {
  $(id).innerHTML = options.map((value) => `<option value="${value}">${value}</option>`).join("");
}

function updateJson() {
  $("drum-kit-json").textContent = JSON.stringify(currentKit, null, 2);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[char]);
}

["slot-label", "slot-midi-note", "slot-enabled", "slot-round-robin", "slot-choke-group", "slot-description"].forEach((id) => {
  $(id).addEventListener("input", () => {
    collectEditor();
    renderSlotGrid();
    updateJson();
  });
});

$("save-kit").addEventListener("click", () => saveKit().catch((error) => ($("drum-admin-status").textContent = error.message)));
$("duplicate-kit").addEventListener("click", duplicateKit);
$("export-kit").addEventListener("click", exportKit);
$("import-kit").addEventListener("change", (event) => importKit(event.target.files[0]).catch((error) => ($("drum-admin-status").textContent = error.message)));
$("drum-upload-top").addEventListener("change", (event) => uploadFiles(event.target.files, "").catch((error) => ($("drum-admin-status").textContent = error.message)));
$("slot-upload").addEventListener("change", (event) => uploadFiles(event.target.files, selectedSlot).catch((error) => ($("drum-admin-status").textContent = error.message)));
$("preview-kit").addEventListener("click", playPattern);
$("play-pattern").addEventListener("click", playPattern);
$("stop-preview").addEventListener("click", stopPreview);
document.querySelectorAll("[data-preview-slot]").forEach((button) => button.addEventListener("click", () => playSlot(button.dataset.previewSlot)));

loadKit().catch((error) => {
  currentKit = defaultKit();
  coverage = computeLocalCoverage(currentKit);
  renderAll();
  $("drum-admin-status").textContent = error.message;
});
