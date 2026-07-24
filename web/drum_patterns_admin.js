const $ = (id) => document.getElementById(id);

const soundLabels = { all: "all / 全部", ambient: "ambient / 氛围", acoustic: "acoustic / 原声", organic: "organic / 自然", vintage: "vintage / 复古", electronic: "electronic / 电子", ethnic: "ethnic / 民族", cinematic: "cinematic / 电影" };
const rhythmLabels = { any: "any / 任意", sparse: "sparse / 极简", flow: "flow / 流动", standard: "standard / 标准", groove: "groove / 律动", aggressive: "aggressive / 激烈" };
const drumSlotLabels = {
  kick: "底鼓", snare: "军鼓", clap: "拍手", closed_hat: "闭合踩镲", open_hat: "开放踩镲",
  shaker: "沙锤", perc_1: "打击乐 1", perc_2: "打击乐 2", low_tom: "低嗵鼓",
  high_tom: "高嗵鼓", crash: "碎音镲", ride: "叮叮镲", impact: "冲击音",
  fill_hit: "过门击打", texture_perc: "质感打击乐"
};
const energyBpm = { "静止": 76, "流动": 98, "高能": 126 };
const gridSteps = { "1/16": 16, "1/32": 32, "1/8T": 12, "1/16T": 24 };
const beatGroups = { "1/16": 4, "1/32": 8, "1/8T": 3, "1/16T": 6 };

let definitions = {
  sound_directions: ["all", "ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic"],
  energies: ["静止", "高能", "流动"],
  rhythms: ["any", "sparse", "flow", "standard", "groove", "aggressive"],
  grid_resolutions: ["1/16", "1/32", "1/8T", "1/16T"],
  drum_slots: {}
};
let patterns = [];
let samples = [];
let selectedSound = "electronic";
let selectedEnergy = "流动";
let selectedRhythm = "groove";
let selectedBars = 4;
let activeBar = 1;
let currentGrid = "1/16";
let selectedEventKey = "";
let copiedEvent = null;
let previewContext = null;
let previewTimers = [];
let rowState = {};
let audioBuffers = new Map();

async function loadData() {
  const [patternResponse, sourceResponse] = await Promise.all([fetch("/api/drum-patterns"), fetch("/api/sound-sources")]);
  const patternData = await patternResponse.json();
  if (!patternData.ok) throw new Error(patternData.error || "鼓点后台加载失败");
  definitions = { ...definitions, ...(patternData.definitions || {}) };
  patterns = patternData.drum_patterns || [];
  const sourceData = await sourceResponse.json().catch(() => ({ samples: [] }));
  samples = sourceData.samples || [];
  hydrateControls();
  selectPattern();
}

function hydrateControls() {
  const soundOptions = definitions.sound_directions.filter((value) => value !== "all");
  const rhythmOptions = definitions.rhythms.filter((value) => value !== "any");
  if (!soundOptions.includes(selectedSound)) selectedSound = soundOptions[0] || "electronic";
  if (!rhythmOptions.includes(selectedRhythm)) selectedRhythm = rhythmOptions[0] || "groove";
  renderChoiceGroup("sound-tags", soundOptions, selectedSound, (value) => {
    selectedSound = value;
    setActiveChoice("sound-tags", value);
    selectPattern();
  }, soundLabels);
  renderChoiceGroup("energy-tags", definitions.energies, selectedEnergy, (value) => {
    selectedEnergy = value;
    $("preview-bpm").value = energyBpm[value] || 98;
    setActiveChoice("energy-tags", value);
    selectPattern();
  });
  renderChoiceGroup("rhythm-tags", rhythmOptions, selectedRhythm, (value) => {
    selectedRhythm = value;
    setActiveChoice("rhythm-tags", value);
    selectPattern();
  }, rhythmLabels);
  fillSelect("grid-resolution", definitions.grid_resolutions, (value) => value);
  fillSelect("event-grid", definitions.grid_resolutions, (value) => value);
  $("grid-resolution").value = currentGrid;
}

function renderChoiceGroup(id, values, selected, onPick, labelMap = {}) {
  $(id).innerHTML = values.map((value) => `<button type="button" class="choice ${value === selected ? "active" : ""}" data-value="${escapeAttr(value)}">${escapeHtml(labelMap[value] || value)}</button>`).join("");
  document.querySelectorAll(`#${id} button`).forEach((button) => button.addEventListener("click", () => onPick(button.dataset.value)));
}

function setActiveChoice(id, value) {
  document.querySelectorAll(`#${id} button`).forEach((button) => {
    button.classList.toggle("active", button.dataset.value === value);
  });
}

function fillSelect(id, values, labeler) {
  const current = $(id).value;
  $(id).innerHTML = values.map((value) => `<option value="${escapeAttr(value)}">${escapeHtml(labeler(value))}</option>`).join("");
  if (values.includes(current)) $(id).value = current;
}

function selectPattern() {
  const pattern = patternForSelection();
  activeBar = Math.min(activeBar, Number(pattern.loop_length_bars || selectedBars));
  selectedEventKey = "";
  currentGrid = pattern.default_grid_resolution || currentGrid;
  $("grid-resolution").value = currentGrid;
  $("preview-bpm").value = energyBpm[selectedEnergy] || $("preview-bpm").value || 98;
  $("current-pattern").textContent = `Current Drum Pattern: ${soundLabels[selectedSound] || selectedSound} / ${selectedEnergy} / ${rhythmLabels[selectedRhythm] || selectedRhythm}`;
  $("status-line").textContent = findPattern(selectedSound, selectedEnergy, selectedRhythm, selectedBars)
    ? "正在编辑当前标签的专属鼓型"
    : "当前标签还没有独立鼓型；正在使用默认鼓型，编辑并保存后会成为当前标签的专属版本";
  renderSequencer(pattern);
  renderEventEditor(null);
  renderPatternList();
}

function findPattern(sound, energy, rhythm, bars) {
  return patterns.find((pattern) => {
    const tags = pattern.tags || {};
    return tags.sound_direction === sound && tags.energy === energy && tags.rhythm === rhythm && Number(pattern.loop_length_bars || 4) === Number(bars);
  }) || null;
}

function patternForSelection() {
  const candidates = [
    [selectedSound, selectedEnergy, selectedRhythm],
    ["all", selectedEnergy, selectedRhythm],
    [selectedSound, selectedEnergy, "any"],
    ["all", selectedEnergy, "any"]
  ];
  for (const [sound, energy, rhythm] of candidates) {
    const pattern = findPattern(sound, energy, rhythm, selectedBars);
    if (pattern) return pattern;
  }
  return defaultPattern();
}

function clonePatternForCurrentTags(source) {
  const target = defaultPattern();
  return {
    ...target,
    events: (source.events || []).map((event) => ({ ...event })),
    bar_overrides: Array.isArray(source.bar_overrides) ? [...source.bar_overrides] : [],
    swing: { ...(source.swing || target.swing) },
    humanize: { ...(source.humanize || target.humanize) },
    default_grid_resolution: source.default_grid_resolution || target.default_grid_resolution,
    name: `${selectedSound} / ${selectedEnergy} / ${selectedRhythm}`,
    updated_at: new Date().toISOString()
  };
}

function currentPattern() {
  let pattern = findPattern(selectedSound, selectedEnergy, selectedRhythm, selectedBars);
  if (!pattern) {
    // Merely browsing a tag combination must never alter its shared fallback.
    // The first edit creates an independent copy for the current combination.
    pattern = clonePatternForCurrentTags(patternForSelection());
    patterns.push(pattern);
  }
  pattern.default_grid_resolution = currentGrid;
  pattern.updated_at = new Date().toISOString();
  return pattern;
}

function defaultPattern() {
  const energySlug = { "静止": "still", "流动": "flowing", "高能": "high" }[selectedEnergy] || selectedEnergy;
  return {
    pattern_id: `pattern_${selectedSound}_${energySlug}_${selectedRhythm}_${selectedBars}`.replace(/[^A-Za-z0-9_.-]+/g, "_").toLowerCase(),
    name: `${selectedSound} / ${selectedEnergy} / ${selectedRhythm}`,
    enabled: true,
    tags: { sound_direction: selectedSound, energy: selectedEnergy, rhythm: selectedRhythm },
    loop_length_bars: selectedBars,
    default_grid_resolution: currentGrid,
    time_signature: "4/4",
    events: [],
    bar_overrides: [],
    swing: { enabled: false, amount: 0 },
    humanize: { timing_ticks: selectedEnergy === "静止" ? 8 : selectedEnergy === "高能" ? 4 : 6, velocity_amount: selectedEnergy === "高能" ? 6 : 10 },
    updated_at: new Date().toISOString()
  };
}

function renderSequencer(pattern = currentPattern()) {
  const slots = orderedDrumSlots();
  const steps = gridSteps[currentGrid] || 16;
  const bars = Number(pattern.loop_length_bars || selectedBars);
  activeBar = Math.min(Math.max(1, activeBar), bars);
  $("sequencer").innerHTML = `${barTabsMarkup(bars)}${barMarkup(pattern, slots, activeBar, steps)}`;
  bindGridActions();
}

function orderedDrumSlots() {
  const allSlots = definitions.drum_slots || {};
  const priority = ["kick", "snare", "closed_hat", "open_hat", "clap", "shaker", "perc_1", "perc_2", "low_tom", "high_tom", "crash", "ride", "impact", "fill_hit", "texture_perc"];
  return priority.filter((slot) => allSlots[slot]).map((slot) => [slot, allSlots[slot]]);
}

function barTabsMarkup(bars) {
  const tabs = Array.from({ length: bars }, (_, index) => {
    const bar = index + 1;
    return `<button class="bar-tab ${bar === activeBar ? "active" : ""}" type="button" data-bar-tab="${bar}">Bar ${bar}</button>`;
  }).join("");
  return `<div class="bar-tabs" aria-label="小节选择">${tabs}</div>`;
}

function barMarkup(pattern, slots, bar, steps) {
  const headerCells = Array.from({ length: steps }, (_, step) => `<div class="step-head ${step % beatGroups[currentGrid] === 0 ? "beat-start" : ""}">${step + 1}</div>`).join("");
  const rows = slots.map(([slot, config]) => rowMarkup(pattern, slot, config.label || slot, bar, steps)).join("");
  return `
    <section class="sequencer-bar">
      <div class="bar-title">Bar ${bar}</div>
      <div class="sequencer-row header-row" style="--steps:${steps}">
        <div class="slot-label"></div>
        ${headerCells}
      </div>
      ${rows}
    </section>
  `;
}

function rowMarkup(pattern, slot, label, bar, steps) {
  const state = rowState[slot] || { mute: false, solo: false };
  const paused = Boolean(state.mute);
  const cells = Array.from({ length: steps }, (_, step) => {
    const event = displayEvent(pattern, slot, bar, step, currentGrid);
    const hasOtherGrid = !event && pattern.events.some((item) => item.slot === slot && Number(item.bar) === Number(bar) && item.grid_resolution !== currentGrid && mapsToCurrentStep(item, step));
    const key = event ? eventKey(event) : "";
    const strength = event ? velocityClass(event.velocity) : "";
    const probability = event && Number(event.probability) < 1 ? `<span class="prob-dot">${Math.round(Number(event.probability) * 100)}</span>` : "";
    const subdivision = hasOtherGrid ? `<span class="sub-dot">sub</span>` : "";
    return `<button type="button" class="step-cell ${event ? "on" : ""} ${strength} ${key === selectedEventKey ? "selected" : ""} ${hasOtherGrid ? "has-sub" : ""} ${step % beatGroups[currentGrid] === 0 ? "beat-start" : ""}" data-slot="${escapeAttr(slot)}" data-bar="${bar}" data-step="${step}" data-key="${escapeAttr(key)}">${probability}${subdivision}</button>`;
  }).join("");
  return `
    <div class="sequencer-row" style="--steps:${steps}" data-slot="${escapeAttr(slot)}">
      <div class="slot-label">
        <button type="button" class="row-play" data-row-action="play" data-slot="${escapeAttr(slot)}" title="试听这一轨">▶</button>
        <button type="button" class="row-pause ${paused ? "active" : ""}" data-row-action="pause" data-slot="${escapeAttr(slot)}" title="${paused ? "恢复这一轨" : "暂停这一轨"}">${paused ? "恢复" : "暂停"}</button>
        <button type="button" class="row-toggle ${state.solo ? "active" : ""}" data-row-action="solo" data-slot="${escapeAttr(slot)}">S</button>
        <span>${escapeHtml(label)}</span>
      </div>
      ${cells}
    </div>
  `;
}

function mapsToCurrentStep(event, step) {
  const sourceSteps = gridSteps[event.grid_resolution] || 16;
  const currentSteps = gridSteps[currentGrid] || 16;
  return Math.floor(Number(event.step || 0) * currentSteps / sourceSteps) === step;
}

function bindGridActions() {
  document.querySelectorAll("[data-bar-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeBar = Number(button.dataset.barTab);
      selectedEventKey = "";
      renderEventEditor(null);
      renderSequencer(patternForSelection());
    });
  });
  document.querySelectorAll(".step-cell").forEach((cell) => {
    cell.addEventListener("click", () => handleCellClick(cell));
    cell.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      handleContext(cell);
    });
  });
  document.querySelectorAll("[data-row-action]").forEach((button) => {
    button.addEventListener("click", () => handleRowAction(button.dataset.slot, button.dataset.rowAction));
  });
}

function handleCellClick(cell) {
  const pattern = currentPattern();
  const bar = Number(cell.dataset.bar);
  const event = displayEvent(pattern, cell.dataset.slot, bar, Number(cell.dataset.step), currentGrid);
  if (event) {
    if (bar === 1) removeBarOneMirror(pattern, event);
    deleteEvent(event);
    selectedEventKey = "";
    renderSequencer(pattern);
    renderEventEditor(null);
    return;
  }

  const nextEvent = makeEvent(cell.dataset.slot, Number(cell.dataset.bar), Number(cell.dataset.step), currentGrid);
  pattern.events.push(nextEvent);
  if (bar === 1) mirrorBarOneEvent(pattern, nextEvent);
  selectedEventKey = eventKey(nextEvent);
  renderSequencer(pattern);
  renderEventEditor(nextEvent);
}

function handleContext(cell) {
  const pattern = currentPattern();
  const bar = Number(cell.dataset.bar);
  const event = displayEvent(pattern, cell.dataset.slot, bar, Number(cell.dataset.step), currentGrid);
  const action = window.prompt("Edit / Delete / Copy / Paste", event ? "Edit" : "Paste");
  if (!action) return;
  const normalized = action.trim().toLowerCase();
  if (normalized === "delete" && event) {
    if (bar === 1) removeBarOneMirror(pattern, event);
    deleteEvent(event);
  }
  if (normalized === "copy" && event) copiedEvent = { ...event, bar };
  if (normalized === "paste" && copiedEvent) {
    const pastedEvent = { ...copiedEvent, slot: cell.dataset.slot, bar: Number(cell.dataset.bar), step: Number(cell.dataset.step), grid_resolution: currentGrid };
    pattern.events.push(pastedEvent);
    if (bar === 1) mirrorBarOneEvent(pattern, pastedEvent);
  }
  if (normalized === "edit" && event) {
    selectedEventKey = eventKey(event);
    renderEventEditor(event);
  }
  renderSequencer(pattern);
}

function handleRowAction(slot, action) {
  if (action === "play") {
    previewPattern(slot);
    return;
  }
  rowState[slot] = rowState[slot] || { mute: false, solo: false };
  if (action === "pause" || action === "mute") rowState[slot].mute = !rowState[slot].mute;
  if (action === "solo") rowState[slot].solo = !rowState[slot].solo;
  renderSequencer(currentPattern());
}

function deleteCellEvent(cell) {
  const pattern = currentPattern();
  const bar = Number(cell.dataset.bar);
  const event = findEvent(pattern, cell.dataset.slot, bar, Number(cell.dataset.step), currentGrid);
  if (event) {
    if (bar === 1) removeBarOneMirror(pattern, event);
    deleteEvent(event);
  }
  selectedEventKey = "";
  renderSequencer(pattern);
  renderEventEditor(null);
}

function renderEventEditor(event) {
  $("event-empty").classList.toggle("hidden", Boolean(event));
  $("event-form").classList.toggle("hidden", !event);
  if (!event) return;
  $("event-slot").value = drumSlotLabels[event.slot] || event.slot;
  $("event-bar").value = event.bar;
  $("event-step").value = Number(event.step || 0) + 1;
  $("event-step").max = gridSteps[event.grid_resolution] || 16;
  $("event-grid").value = event.grid_resolution;
  $("event-velocity").value = event.velocity;
  $("velocity-readout").textContent = event.velocity;
  $("event-probability").value = event.probability;
  $("probability-readout").textContent = Number(event.probability).toFixed(2);
  $("event-micro").value = event.micro_timing;
  $("event-duration").value = event.duration_ticks;
  $("event-enabled").checked = event.enabled !== false;
}

function updateSelectedEvent() {
  const pattern = currentPattern();
  const event = pattern.events.find((item) => eventKey(item) === selectedEventKey);
  if (!event) return;
  const previous = { ...event };
  event.bar = clamp(Number($("event-bar").value || 1), 1, selectedBars);
  event.grid_resolution = $("event-grid").value;
  event.step = clamp(Number($("event-step").value || 1) - 1, 0, (gridSteps[event.grid_resolution] || 16) - 1);
  event.velocity = clamp(Number($("event-velocity").value || 96), 1, 127);
  event.probability = clamp(Number($("event-probability").value || 1), 0, 1);
  event.micro_timing = clamp(Number($("event-micro").value || 0), -20, 20);
  event.duration_ticks = clamp(Number($("event-duration").value || 80), 1, 960);
  event.enabled = $("event-enabled").checked;
  event.midi_note = definitions.drum_slots[event.slot]?.midi_note || event.midi_note || 36;
  if (Number(previous.bar) === 1) {
    removeBarOneMirror(pattern, previous);
    if (Number(event.bar) === 1) mirrorBarOneEvent(pattern, event);
  }
  selectedEventKey = eventKey(event);
  renderEventEditor(event);
  renderSequencer(pattern);
}

function makeEvent(slot, bar, step, grid) {
  return {
    bar,
    step,
    grid_resolution: grid,
    slot,
    midi_note: definitions.drum_slots[slot]?.midi_note || 36,
    velocity: defaultVelocity(slot, step),
    probability: 1,
    micro_timing: 0,
    duration_ticks: slot.includes("hat") || slot === "shaker" ? 45 : 80,
    enabled: true
  };
}

function findEvent(pattern, slot, bar, step, grid) {
  return pattern.events.find((event) => event.slot === slot && Number(event.bar) === Number(bar) && Number(event.step) === Number(step) && event.grid_resolution === grid) || null;
}

function mirrorBarOneEvent(pattern, event) {
  const bars = Number(pattern.loop_length_bars || selectedBars);
  for (let bar = 2; bar <= bars; bar += 1) {
    const existing = findEvent(pattern, event.slot, bar, event.step, event.grid_resolution);
    if (existing) Object.assign(existing, { ...event, bar });
    else pattern.events.push({ ...event, bar });
  }
}

function removeBarOneMirror(pattern, event) {
  const bars = Number(pattern.loop_length_bars || selectedBars);
  pattern.events = pattern.events.filter((item) => {
    const isMirroredCell = Number(item.bar) >= 2 && Number(item.bar) <= bars
      && item.slot === event.slot
      && Number(item.step) === Number(event.step)
      && item.grid_resolution === event.grid_resolution;
    return !isMirroredCell;
  });
}

function displayEvent(pattern, slot, bar, step, grid) {
  return findEvent(pattern, slot, bar, step, grid);
}

function deleteEvent(event) {
  const pattern = currentPattern();
  const key = eventKey(event);
  pattern.events = pattern.events.filter((item) => eventKey(item) !== key);
}

function eventKey(event) {
  return `${event.slot}|${event.bar}|${event.step}|${event.grid_resolution}`;
}

function defaultVelocity(slot, step) {
  if (slot === "kick") return step % 4 === 0 ? 112 : 96;
  if (slot === "snare") return 96;
  if (slot.includes("hat") || slot === "shaker") return step % 4 === 0 ? 74 : 58;
  return 80;
}

function velocityClass(velocity) {
  if (Number(velocity) <= 40) return "v-low";
  if (Number(velocity) <= 80) return "v-mid";
  return "v-high";
}

async function saveCurrent() {
  const pattern = currentPattern();
  $("status-line").textContent = "正在保存...";
  const response = await fetch("/api/drum-patterns/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern })
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "保存失败");
  patterns = data.drum_patterns || [];
  $("status-line").textContent = "已保存";
  selectPattern();
}

async function resetCurrent() {
  if (!window.confirm("Are you sure you want to reset this drum pattern?")) return;
  const response = await fetch("/api/drum-patterns/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tags: { sound_direction: selectedSound, energy: selectedEnergy, rhythm: selectedRhythm }, loop_length_bars: selectedBars })
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "重置失败");
  patterns = data.drum_patterns || [];
  $("status-line").textContent = "已重置";
  selectPattern();
}

async function duplicateCurrent() {
  const pattern = currentPattern();
  const sound = window.prompt("Duplicate 到哪个 Sound Direction？", selectedSound) || selectedSound;
  const response = await fetch("/api/drum-patterns/duplicate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern_id: pattern.pattern_id, tags: { sound_direction: sound, energy: selectedEnergy, rhythm: selectedRhythm } })
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "复制失败");
  patterns = data.drum_patterns || [];
  selectedSound = data.pattern.tags.sound_direction;
  $("status-line").textContent = "已复制";
  hydrateControls();
  selectPattern();
}

function renderPatternList() {
  const activePattern = patternForSelection();
  const visiblePatterns = patterns.filter((pattern) => pattern.tags?.sound_direction !== "all" && pattern.tags?.rhythm !== "any");
  $("pattern-list").innerHTML = visiblePatterns.length ? visiblePatterns.map((pattern) => `
    <article class="pattern-card ${pattern.pattern_id === activePattern.pattern_id ? "active" : ""}" data-id="${escapeAttr(pattern.pattern_id)}">
      <b>${escapeHtml(pattern.name)}</b>
      <span>${escapeHtml(pattern.tags?.sound_direction || "all")} / ${escapeHtml(pattern.tags?.energy || "")} / ${escapeHtml(pattern.tags?.rhythm || "")}</span>
      <span>${pattern.loop_length_bars} bars · ${pattern.events?.length || 0} events</span>
    </article>
  `).join("") : `<article class="pattern-card"><b>还没有单独编辑过的鼓型</b><span>从左侧选择音色方向和节奏，编辑后保存即可建立。</span></article>`;
  document.querySelectorAll(".pattern-card[data-id]").forEach((card) => {
    card.addEventListener("click", () => {
      const pattern = patterns.find((item) => item.pattern_id === card.dataset.id);
      if (!pattern) return;
      selectedSound = pattern.tags.sound_direction;
      selectedEnergy = pattern.tags.energy;
      selectedRhythm = pattern.tags.rhythm;
      selectedBars = Number(pattern.loop_length_bars || 4);
      document.querySelector(`input[name="pattern-bars"][value="${selectedBars}"]`).checked = true;
      hydrateControls();
      selectPattern();
    });
  });
}

async function previewPattern(rowSlot = "") {
  stopPreview();
  const pattern = patternForSelection();
  const bpm = Number($("preview-bpm").value || 98);
  const loopSeconds = Number(pattern.loop_length_bars || 4) * 4 * 60 / bpm;
  const events = playableEvents(pattern, rowSlot);
  $("status-line").textContent = rowSlot ? `试听 ${rowSlot}` : "正在试听";
  previewContext = previewContext || new AudioContext();
  await previewContext.resume();
  const startedAt = previewContext.currentTime + 0.04;
  const schedule = async () => {
    for (const event of events) {
      const delay = eventSeconds(event, bpm);
      const timer = window.setTimeout(() => playEvent(event, startedAt + delay), delay * 1000);
      previewTimers.push(timer);
    }
    if ($("preview-metronome").checked) {
      for (let beat = 0; beat < Number(pattern.loop_length_bars || 4) * 4; beat++) {
        const timer = window.setTimeout(() => playClick(startedAt + beat * 60 / bpm, beat % 4 === 0 ? 880 : 660, 0.035), beat * 60 / bpm * 1000);
        previewTimers.push(timer);
      }
    }
  };
  await schedule();
  if ($("preview-loop").checked) {
    const timer = window.setTimeout(() => previewPattern(rowSlot), loopSeconds * 1000);
    previewTimers.push(timer);
  }
}

function playableEvents(pattern, rowSlot) {
  const soloSlots = Object.entries(rowState).filter(([, state]) => state.solo).map(([slot]) => slot);
  return pattern.events
    .filter((event) => event.enabled !== false)
    .filter((event) => !rowSlot || event.slot === rowSlot)
    .filter((event) => soloSlots.length ? soloSlots.includes(event.slot) : !rowState[event.slot]?.mute)
    .filter((event) => Math.random() <= Number(event.probability || 1))
    .sort((a, b) => eventSeconds(a, 120) - eventSeconds(b, 120));
}

function eventSeconds(event, bpm) {
  const steps = gridSteps[event.grid_resolution] || 16;
  const beats = (Number(event.bar || 1) - 1) * 4 + Number(event.step || 0) * 4 / steps + Number(event.micro_timing || 0) / 480;
  return Math.max(0, beats * 60 / bpm);
}

async function playEvent(event, time) {
  const sample = choosePreviewSample(event.slot);
  const volume = Number($("preview-volume").value || 0.8);
  if (sample?.file_url) {
    try {
      const buffer = await loadAudioBuffer(sample.file_url);
      const source = previewContext.createBufferSource();
      const gain = previewContext.createGain();
      source.buffer = buffer;
      gain.gain.value = volume * 10 ** (Number(sample.playback?.gain_db || 0) / 20);
      source.connect(gain).connect(previewContext.destination);
      source.start(time);
      return;
    } catch {
      $("status-line").textContent = `Missing sample for ${event.slot}`;
    }
  } else {
    $("status-line").textContent = `Missing sample for ${event.slot}`;
  }
  playClick(time, fallbackPitch(event.slot), volume * 0.1);
}

function choosePreviewSample(slot) {
  return samples.find((sample) => {
    if (!sample.enabled || sample.target?.track_role !== "drums") return false;
    if (sample.target?.slot !== slot && !(slot.startsWith("perc_") && sample.target?.slot === "perc")) return false;
    const rules = sample.tag_rules || {};
    return ruleMatches(rules.sound_direction, selectedSound)
      && ruleMatches(rules.energy, selectedEnergy)
      && ruleMatches(rules.rhythm, selectedRhythm);
  });
}

function ruleMatches(values, current) {
  return !values || !values.length || !current || values.includes(current);
}

async function loadAudioBuffer(url) {
  if (audioBuffers.has(url)) return audioBuffers.get(url);
  const response = await fetch(url);
  const bytes = await response.arrayBuffer();
  const buffer = await previewContext.decodeAudioData(bytes);
  audioBuffers.set(url, buffer);
  return buffer;
}

function playClick(time, frequency, gainValue) {
  const osc = previewContext.createOscillator();
  const gain = previewContext.createGain();
  osc.frequency.value = frequency;
  osc.type = frequency < 100 ? "sine" : "square";
  gain.gain.setValueAtTime(gainValue, time);
  gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.06);
  osc.connect(gain).connect(previewContext.destination);
  osc.start(time);
  osc.stop(time + 0.07);
}

function fallbackPitch(slot) {
  if (slot === "kick") return 58;
  if (slot === "snare" || slot === "clap") return 210;
  if (slot.includes("hat") || slot === "shaker") return 1200;
  return 420;
}

function stopPreview() {
  previewTimers.forEach((timer) => window.clearTimeout(timer));
  previewTimers = [];
  $("status-line").textContent = "已停止";
}

function exportPatterns() {
  const blob = new Blob([JSON.stringify({ version: "1.0", drum_patterns: patterns }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "drum_patterns.json";
  link.click();
  URL.revokeObjectURL(url);
}

async function importPatterns(file) {
  if (!file) return;
  const text = await file.text();
  const payload = JSON.parse(text);
  const response = await fetch("/api/drum-patterns/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "导入失败");
  patterns = data.drum_patterns || [];
  $("status-line").textContent = "已导入";
  selectPattern();
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

$("grid-resolution").addEventListener("change", () => {
  currentGrid = $("grid-resolution").value;
  renderSequencer(patternForSelection());
});
document.querySelectorAll("input[name='pattern-bars']").forEach((input) => input.addEventListener("change", () => {
  selectedBars = Number(document.querySelector("input[name='pattern-bars']:checked").value);
  selectPattern();
}));
["event-bar", "event-step", "event-grid", "event-velocity", "event-probability", "event-micro", "event-duration", "event-enabled"].forEach((id) => {
  $(id).addEventListener("input", updateSelectedEvent);
  $(id).addEventListener("change", updateSelectedEvent);
});
$("delete-event").addEventListener("click", () => {
  const pattern = currentPattern();
  const event = pattern.events.find((item) => eventKey(item) === selectedEventKey);
  if (event) deleteEvent(event);
  selectedEventKey = "";
  renderEventEditor(null);
  renderSequencer(pattern);
});
$("duplicate-event").addEventListener("click", () => {
  const pattern = currentPattern();
  const event = pattern.events.find((item) => eventKey(item) === selectedEventKey);
  if (!event) return;
  const duplicate = { ...event, step: clamp(Number(event.step) + 1, 0, (gridSteps[event.grid_resolution] || 16) - 1) };
  pattern.events.push(duplicate);
  selectedEventKey = eventKey(duplicate);
  renderSequencer(pattern);
  renderEventEditor(duplicate);
});
$("apply-similar").addEventListener("click", () => {
  const pattern = currentPattern();
  const event = pattern.events.find((item) => eventKey(item) === selectedEventKey);
  if (!event) return;
  pattern.events.filter((item) => item.slot === event.slot).forEach((item) => {
    item.velocity = event.velocity;
    item.probability = event.probability;
    item.micro_timing = event.micro_timing;
    item.duration_ticks = event.duration_ticks;
  });
  renderSequencer(pattern);
});
$("close-event").addEventListener("click", () => {
  selectedEventKey = "";
  renderEventEditor(null);
  renderSequencer(patternForSelection());
});
$("save-pattern").addEventListener("click", () => saveCurrent().catch((error) => ($("status-line").textContent = error.message)));
$("reset-pattern").addEventListener("click", () => resetCurrent().catch((error) => ($("status-line").textContent = error.message)));
$("duplicate-pattern").addEventListener("click", () => duplicateCurrent().catch((error) => ($("status-line").textContent = error.message)));
$("grid-play-all").addEventListener("click", () => previewPattern().catch((error) => ($("status-line").textContent = error.message)));
$("grid-stop").addEventListener("click", stopPreview);
$("preview-play").addEventListener("click", () => previewPattern().catch((error) => ($("status-line").textContent = error.message)));
$("preview-stop").addEventListener("click", stopPreview);
$("export-patterns").addEventListener("click", exportPatterns);
$("import-patterns").addEventListener("change", () => importPatterns($("import-patterns").files[0]).catch((error) => ($("status-line").textContent = error.message)));

loadData().catch((error) => {
  $("status-line").textContent = error.message;
  hydrateControls();
  selectPattern();
});
