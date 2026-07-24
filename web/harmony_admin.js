const $ = (id) => document.getElementById(id);

const pc = { C: 0, "C#": 1, Db: 1, D: 2, "D#": 3, Eb: 3, E: 4, F: 5, "F#": 6, Gb: 6, G: 7, "G#": 8, Ab: 8, A: 9, "A#": 10, Bb: 10, B: 11 };
const noteNames = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const pitchChoices = Array.from({ length: 37 }, (_, index) => {
  const midi = 36 + index;
  return { midi, note: noteNames[midi % 12], label: `${noteNames[midi % 12]}${Math.floor(midi / 12) - 1}` };
});

let rules = [];
let defaultRules = [];
let foundationPatterns = [];
let definitions = { emotions: ["深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂"], voicing_styles: ["simple", "rootless", "open", "wide", "close"] };
let emotion = "欢快";
let bars = 4;
let audioContext = null;

if (location.protocol === "file:") $("loop-link").href = "index.html";

async function loadData() {
  const [response, patternResponse] = await Promise.all([fetch("/api/harmony"), fetch("/api/foundation-patterns")]);
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "加载失败");
  const patternData = await patternResponse.json();
  rules = data.harmony_rules || [];
  defaultRules = data.default_rules || [];
  foundationPatterns = patternData.ok ? patternData.patterns || [] : [];
  definitions = { ...definitions, ...(data.definitions || {}) };
  hydrateStatic();
  renderEditor();
  renderList();
}

function hydrateStatic() {
  renderPickers();
  $("voicing-style").innerHTML = definitions.voicing_styles.map((style) => `<option value="${style}">${style}</option>`).join("");
  renderFoundationPatternSelect();
}

function renderFoundationPatternSelect() {
  const select = $("foundation-pattern-select");
  if (!select) return;
  const current = select.value;
  const options = foundationPatterns.filter((pattern) => {
    const tags = pattern.tag_rules || {};
    const emotionMatches = !tags.emotion?.length || tags.emotion.includes(emotion);
    return pattern.enabled && Number(pattern.loop_length_bars) === bars && emotionMatches;
  });
  select.innerHTML = `<option value="">未选择上传模板</option>${options.map((pattern) => `<option value="${escapeAttr(pattern.id)}">${escapeHtml(pattern.name)} · ${pattern.loop_length_bars} 小节</option>`).join("")}`;
  select.value = options.some((pattern) => pattern.id === current) ? current : options[0]?.id || "";
  updateFoundationPatternRange();
}

function activeFoundationPattern() {
  const id = $("foundation-pattern-select")?.value;
  return foundationPatterns.find((pattern) => pattern.id === id) || null;
}

function patternPitchesForBar(index) {
  const pattern = activeFoundationPattern();
  if (!pattern) return [];
  const ticksPerBar = 4 * 480;
  const barStart = index * ticksPerBar;
  const barEnd = barStart + ticksPerBar;
  return [...new Set((pattern.events || []).filter((event) => {
    const start = Number(event.start_tick || 0);
    const end = start + Number(event.duration_ticks || 0);
    return start < barEnd && end > barStart;
  }).map((event) => midiToPitchName(Number(event.note))))].sort((a, b) => pitchNameToMidi(a) - pitchNameToMidi(b));
}

function updateFoundationPatternRange() {
  const pattern = activeFoundationPattern();
  const target = $("foundation-pattern-range");
  if (!target) return;
  target.textContent = pattern ? `${pattern.name} · 录制音域 ${midiToPitchName(pattern.analysis.lowest_note)} - ${midiToPitchName(pattern.analysis.highest_note)}；每个 Bar 只显示实际录制的音。` : "未选择模板时使用默认和弦音域。";
}

function renderPickers() {
  $("emotion-options").innerHTML = definitions.emotions.map((item) => `<button class="choice ${item === emotion ? "active" : ""}" type="button" data-emotion="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("");
  document.querySelectorAll("[data-emotion]").forEach((button) => button.addEventListener("click", () => {
    emotion = button.dataset.emotion;
    renderPickers();
    renderEditor();
  }));
}

function activeRule() {
  return rules.filter((rule) => rule.emotion === emotion && Number(rule.loop_length_bars) === bars).sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))[0] || null;
}

function currentChordItems() {
  const fallback = defaultChords(bars).map((chord, index) => ({ chord, selected_notes: defaultSelectedPitches(chord, index) }));
  let previous = null;
  return [...document.querySelectorAll(".chord-input")].map((input, rowIndex) => {
    const typedChord = input.value.trim();
    const inherited = previous || fallback[rowIndex] || fallback[0] || { chord: "Cmaj9", selected_notes: defaultSelectedPitches("Cmaj9") };
    const domIndex = input.dataset.index;
    const item = {
      chord: typedChord || inherited.chord,
      selected_notes: typedChord ? activeNotesForRow(domIndex) : inherited.selected_notes
    };
    previous = item;
    return item;
  });
}

function currentChords() {
  return currentChordItems().map((item) => item.chord).filter(Boolean);
}

function renderEditor() {
  renderFoundationPatternSelect();
  const rule = activeRule();
  const chords = rule ? rule.chords : defaultChords(bars).map((chord) => ({ chord, selected_notes: null }));
  $("current-rule").textContent = `当前和弦规则：${emotion}`;
  $("enabled").checked = rule ? rule.enabled !== false : true;
  $("voicing-style").value = rule?.voicing_style || "open";
  $("chord-grid").innerHTML = Array.from({ length: bars }, (_, index) => chordRow(index, chords[index] || { chord: "" })).join("");
  bindChordRows();
}

function chordRow(index, chordItem) {
  const chord = typeof chordItem === "string" ? chordItem : chordItem.chord || "";
  const selectedNotes = typeof chordItem === "object" ? (chordItem.selected_notes || pitchesFromAllowedNotes(chordItem.allowed_notes)) : null;
  const validity = validateChord(chord);
  const empty = chord.trim() === "";
  return `
    <article class="chord-row">
      <label class="field">
        <span>Bar ${index + 1}</span>
        <input class="chord-input" data-index="${index}" value="${escapeAttr(chord)}" />
      </label>
      <span class="chord-state ${validity || empty ? "valid" : "invalid"}">${empty ? "延续上一和弦" : validity ? "有效和弦" : "和弦格式无效"}</span>
      <div class="note-filter" data-index="${index}">
        <span>${activeFoundationPattern() ? `录制 MIDI 具体音 · Bar ${index + 1}` : "使用音 C2-C5"}</span>
        <div class="note-pill-row">${noteButtons(chord, selectedNotes, index)}</div>
      </div>
      <button type="button" data-action="play" data-index="${index}">试听</button>
      <button type="button" data-action="copy" data-index="${index}">复制</button>
      <button type="button" data-action="clear" data-index="${index}">清空</button>
    </article>
  `;
}

function bindChordRows() {
  document.querySelectorAll(".chord-input").forEach((input) => input.addEventListener("input", () => {
    const row = input.closest(".chord-row");
    const state = row.querySelector(".chord-state");
    const empty = input.value.trim() === "";
    const valid = empty || validateChord(input.value);
    state.textContent = empty ? "延续上一和弦" : valid ? "有效和弦" : "和弦格式无效";
    state.classList.toggle("valid", valid);
    state.classList.toggle("invalid", !valid);
    refreshNoteFilter(input.dataset.index, empty ? inheritedChordForRow(Number(input.dataset.index)) : input.value, !empty);
  }));
  document.querySelectorAll(".note-pill").forEach((button) => button.addEventListener("click", () => {
    button.classList.toggle("active");
  }));
  document.querySelectorAll(".chord-row button[data-action]").forEach((button) => button.addEventListener("click", async () => {
    const input = document.querySelector(`.chord-input[data-index="${button.dataset.index}"]`);
    const chord = input.value.trim() || inheritedChordForRow(Number(button.dataset.index));
    if (button.dataset.action === "play") await playChord(chord, 1.2, activeNotesForRow(button.dataset.index));
    if (button.dataset.action === "copy") navigator.clipboard?.writeText(input.value);
    if (button.dataset.action === "clear") {
      input.value = "";
      input.dispatchEvent(new Event("input"));
    }
  }));
}

async function saveRule() {
  const chords = currentChordItems();
  const payload = {
    rule_id: `harmony_${emotion}_all_${bars}`,
    emotion,
    sound_direction: "all",
    loop_length_bars: bars,
    chords,
    voicing_style: $("voicing-style").value,
    enabled: $("enabled").checked
  };
  const response = await fetch("/api/harmony/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rule: payload }) });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "保存失败");
  rules = data.harmony_rules || [];
  $("status-line").textContent = "已保存";
  renderEditor();
  renderList();
}

async function deleteRule(ruleId) {
  const response = await fetch("/api/harmony/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rule_id: ruleId }) });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "删除失败");
  rules = data.harmony_rules || [];
  renderEditor();
  renderList();
}

async function resetRule() {
  if (!confirm("Are you sure you want to reset this harmony rule?")) return;
  const response = await fetch("/api/harmony/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ emotion, sound_direction: "all", loop_length_bars: bars }) });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "恢复失败");
  rules = data.harmony_rules || [];
  renderEditor();
  renderList();
}

function duplicateRule(ruleId) {
  const source = rules.find((rule) => rule.rule_id === ruleId);
  if (!source) return;
  emotion = source.emotion;
  bars = source.loop_length_bars;
  renderPickers();
  $("voicing-style").value = source.voicing_style;
  $("chord-grid").innerHTML = source.chords.map((item, idx) => chordRow(idx, item)).join("");
  bindChordRows();
  $("status-line").textContent = "已复制到当前编辑区，保存后生效";
}

function renderList() {
  $("rule-list").innerHTML = rules.length ? rules.map((rule) => `
    <article class="source-card harmony-card" data-rule-id="${escapeAttr(rule.rule_id)}">
      <div class="source-card-head">
        <b>${escapeHtml(rule.emotion)}</b>
        <span>${rule.enabled ? "Enabled" : "Disabled"}</span>
      </div>
      <p>${escapeHtml(rule.chords.map((item) => item.chord).join(" - "))}</p>
      <p class="saved-notes">${escapeHtml(rule.chords.map((item) => `${item.chord}: ${(item.selected_notes || pitchesFromAllowedNotes(item.allowed_notes) || []).join(" ")}`).join(" / "))}</p>
      <div class="sample-meta">
        <span>${rule.loop_length_bars} bars</span>
        <span>${escapeHtml(rule.voicing_style)}</span>
        <span>${escapeHtml(rule.updated_at || "")}</span>
      </div>
      <div class="card-actions">
        <button type="button" data-action="preview">Preview</button>
        <button type="button" data-action="edit">Edit</button>
        <button type="button" data-action="duplicate">Duplicate</button>
        <button type="button" data-action="delete">Delete</button>
      </div>
    </article>
  `).join("") : `<article class="source-card"><b>还没有保存的和弦规则</b></article>`;
  document.querySelectorAll(".harmony-card button").forEach((button) => button.addEventListener("click", async () => {
    const ruleId = button.closest(".harmony-card").dataset.ruleId;
    const rule = rules.find((item) => item.rule_id === ruleId);
    if (!rule) return;
    if (button.dataset.action === "preview") await playProgression(rule.chords);
    if (button.dataset.action === "edit") {
      emotion = rule.emotion;
      bars = Number(rule.loop_length_bars);
      document.querySelector(`input[name="harmony-bars"][value="${bars}"]`).checked = true;
      renderPickers();
      renderEditor();
    }
    if (button.dataset.action === "duplicate") duplicateRule(ruleId);
    if (button.dataset.action === "delete" && confirm("Delete this harmony rule?")) await deleteRule(ruleId);
  }));
}

async function playProgression(chords = currentChordItems()) {
  const bpm = Number($("preview-bpm").value || 96);
  const seconds = 4 * 60 / bpm;
  for (const item of chords) {
    const chord = typeof item === "string" ? item : item.chord;
    const selectedNotes = typeof item === "string" ? null : item.selected_notes || pitchesFromAllowedNotes(item.allowed_notes);
    await playChord(chord, seconds * 0.85, selectedNotes);
    await wait(seconds * 150);
  }
}

async function playChord(chord, seconds, selectedNotes = null) {
  const notes = chordToMidi(chord, $("voicing-style").value, selectedNotes).sort((a, b) => a - b);
  if (!notes.length) return;
  audioContext = audioContext || new AudioContext();
  const now = audioContext.currentTime;
  const stepSeconds = Math.min(0.22, Math.max(0.09, seconds / Math.max(1, notes.length)));
  notes.forEach((midi, index) => {
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const start = now + index * stepSeconds;
    const end = start + stepSeconds * 0.88;
    osc.type = "triangle";
    osc.frequency.value = 440 * 2 ** ((midi - 69) / 12);
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(0.08, start + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, end);
    osc.connect(gain).connect(audioContext.destination);
    osc.start(start);
    osc.stop(end + 0.05);
  });
  await wait(notes.length * stepSeconds * 1000);
}

function chordToMidi(chord, voicing, selectedNotes = null) {
  if (Array.isArray(selectedNotes)) {
    return selectedNotes.map(pitchNameToMidi).filter((midi) => midi !== null).sort((a, b) => a - b);
  }
  const parsed = parseChord(chord);
  if (!parsed) return [];
  let notes = parsed.intervals.map((interval) => 48 + parsed.root + interval);
  if (voicing === "rootless" && notes.length > 3) notes = notes.slice(1);
  if (voicing === "open") notes = notes.map((note, index) => note + (index % 2 ? 12 : 0));
  if (voicing === "wide") notes = notes.map((note, index) => note + index * 12);
  if (voicing === "close") notes = notes.map((note) => note > 72 ? note - 12 : note);
  return notes.filter((note) => note >= 36 && note <= 72);
}

function notesForChord(chord) {
  return chordToMidi(chord, $("voicing-style").value).map(midiToPitchName);
}

function noteButtons(chord, selectedNotes, index = 0) {
  const selected = new Set(Array.isArray(selectedNotes) ? selectedNotes : defaultSelectedPitches(chord, index));
  const choices = patternPitchesForBar(index).map((label) => ({ label })) || [];
  const effectiveChoices = choices.length ? choices : pitchChoices;
  return effectiveChoices.map((pitch) => {
    const active = selected.has(pitch.label);
    return `<button class="note-pill ${active ? "active" : ""}" type="button" data-note="${escapeAttr(pitch.label)}">${escapeHtml(pitch.label)}</button>`;
  }).join("");
}

function activeNotesForRow(index) {
  return [...document.querySelectorAll(`.note-filter[data-index="${index}"] .note-pill.active`)].map((button) => button.dataset.note);
}

function refreshNoteFilter(index, chord, preserveSelection = false) {
  const container = document.querySelector(`.note-filter[data-index="${index}"] .note-pill-row`);
  if (!container) return;
  const previous = activeNotesForRow(index);
  const selected = preserveSelection && previous.length ? previous : defaultSelectedPitches(chord, Number(index));
  container.innerHTML = noteButtons(chord, selected, Number(index));
  container.querySelectorAll(".note-pill").forEach((button) => button.addEventListener("click", () => {
    button.classList.toggle("active");
  }));
}

function inheritedChordForRow(index) {
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const input = document.querySelector(`.chord-input[data-index="${cursor}"]`);
    const chord = input?.value.trim();
    if (chord) return chord;
  }
  return defaultChords(bars)[index] || defaultChords(bars)[0] || "Cmaj9";
}

function defaultSelectedPitches(chord, index = 0) {
  const recordedPitches = patternPitchesForBar(index);
  if (recordedPitches.length) return recordedPitches;
  const parsed = parseChord(chord);
  if (!parsed) return [];
  return parsed.intervals
    .map((interval) => 48 + parsed.root + interval)
    .filter((midi) => midi >= 36 && midi <= 72)
    .map(midiToPitchName);
}

function pitchesFromAllowedNotes(allowedNotes) {
  if (!Array.isArray(allowedNotes)) return null;
  const allowed = new Set(allowedNotes);
  return pitchChoices.filter((pitch) => allowed.has(pitch.note)).map((pitch) => pitch.label);
}

function pitchNameToMidi(value) {
  const match = String(value || "").match(/^([A-G](?:#|b)?)([0-8])$/);
  if (!match) return null;
  return (Number(match[2]) + 1) * 12 + pc[match[1]];
}

function midiToPitchName(midi) {
  return `${noteNames[midi % 12]}${Math.floor(midi / 12) - 1}`;
}

function parseChord(value) {
  const text = String(value || "").trim().replace(/\s+/g, "");
  const match = text.match(/^([A-G](?:#|b)?)([^/]*)/);
  if (!match) return null;
  const root = pc[match[1]];
  if (root === undefined) return null;
  const quality = match[2] || "";
  const normalized = quality.replace(/[()]/g, "");
  const hasPlain9 = /(^|[^a-z#b])9/.test(normalized);
  const minor = /^m(?!aj)/.test(quality);
  const sus2 = quality.includes("sus2");
  const sus4 = quality.includes("sus4") || (quality.includes("sus") && !sus2);
  let intervals = [0, sus2 ? 2 : sus4 ? 5 : minor ? 3 : 4, 7];
  if (quality.includes("dim")) intervals = [0, 3, 6];
  if (quality.includes("m7b5")) intervals = [0, 3, 6, 10];
  if (normalized.includes("maj7") || normalized.includes("maj9")) intervals.push(11);
  else if (
    normalized.includes("m7") ||
    normalized.includes("m9") ||
    normalized.includes("m11") ||
    normalized.includes("13") ||
    normalized.includes("7") ||
    normalized.includes("9sus") ||
    normalized.includes("7sus") ||
    normalized.includes("alt") ||
    hasPlain9 ||
    /(^|[^a-z])11/.test(normalized)
  ) intervals.push(10);
  if (quality.includes("6/9") || quality === "6") intervals.push(9);
  if (
    normalized.includes("add9") ||
    normalized.includes("maj9") ||
    normalized.includes("m9") ||
    normalized.includes("m11") ||
    hasPlain9 ||
    normalized.includes("9sus") ||
    normalized.includes("6/9")
  ) intervals.push(14);
  if (quality.includes("#11")) intervals.push(18);
  else if (quality.includes("11")) intervals.push(17);
  if (quality.includes("13")) intervals.push(21);
  if (quality.includes("b9")) intervals.push(13);
  if (quality.includes("#9")) intervals.push(15);
  return { root, intervals: [...new Set(intervals)] };
}

function validateChord(chord) {
  return Boolean(parseChord(chord));
}

function defaultChords(count) {
  const rule = defaultRules.find((item) => item.emotion === emotion && Number(item.loop_length_bars) === Number(count));
  const chords = rule?.chords?.map((item) => typeof item === "string" ? item : item.chord).filter(Boolean) || [];
  if (chords.length) return chords;
  return Array.from({ length: count }, () => "Cmaj9");
}

function exportRules() {
  const blob = new Blob([JSON.stringify({ version: "1.0", harmony_rules: rules }, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "harmony_rules.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function importRules() {
  const file = $("import-file").files[0];
  if (!file) return;
  const data = JSON.parse(await file.text());
  const response = await fetch("/api/harmony/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!result.ok) throw new Error(result.error || "导入失败");
  rules = result.harmony_rules || [];
  renderEditor();
  renderList();
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

document.querySelectorAll("input[name='harmony-bars']").forEach((input) => input.addEventListener("change", () => {
  bars = Number(document.querySelector("input[name='harmony-bars']:checked").value);
  renderFoundationPatternSelect();
  renderEditor();
}));
$("foundation-pattern-select").addEventListener("change", () => {
  updateFoundationPatternRange();
  renderEditor();
});
$("save-rule").addEventListener("click", () => saveRule().catch((error) => ($("status-line").textContent = error.message)));
$("preview-progression").addEventListener("click", () => playProgression().catch((error) => ($("status-line").textContent = error.message)));
$("reset-rule").addEventListener("click", () => resetRule().catch((error) => ($("status-line").textContent = error.message)));
$("voicing-style").addEventListener("change", () => {
  const items = currentChordItems();
  $("chord-grid").innerHTML = items.map((item, index) => chordRow(index, item)).join("");
  bindChordRows();
});
$("export-rules").addEventListener("click", exportRules);
$("import-rules").addEventListener("click", () => $("import-file").click());
$("import-file").addEventListener("change", () => importRules().catch((error) => ($("status-line").textContent = error.message)));

loadData().catch((error) => {
  $("status-line").textContent = error.message;
  hydrateStatic();
  renderEditor();
});
