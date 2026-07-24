const $ = (id) => document.getElementById(id);
const tagDefinitions = {
  emotion: ["深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂"],
  energy: ["静止", "高能", "流动"],
  sound_direction: ["ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic"],
  rhythm: ["sparse", "flow", "standard", "groove", "aggressive"]
};
let uploadId = "";
let selectedTrack = null;
let patterns = [];
let audioContext = null;

function setStatus(text) { $("status-line").textContent = text; }
function selectedTags(field) { return [...document.querySelectorAll(`#tags-${field} .choice.active`)].map((button) => button.dataset.value); }
function renderTags() { Object.entries(tagDefinitions).forEach(([field, values]) => { $("tags-" + field).innerHTML = values.map((value) => `<button class="choice" type="button" data-value="${value}">${value}</button>`).join(""); }); document.querySelectorAll("#tags-emotion .choice, #tags-energy .choice, #tags-sound_direction .choice, #tags-rhythm .choice").forEach((button) => button.addEventListener("click", () => button.classList.toggle("active"))); }
function renderSourceChordInputs() { const previous = [...document.querySelectorAll("[data-source-chord]")].map((input) => input.value); const bars = Number($("pattern-bars").value); $("source-chord-inputs").innerHTML = Array.from({ length: bars }, (_, index) => `<label class="field"><span>Bar ${index + 1}</span><input data-source-chord="${index}" value="${previous[index] || ""}" placeholder="例如 ${index === 0 ? "Cmaj9" : "Am9"}" /></label>`).join(""); }

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "请求失败");
  return payload;
}

async function analyze() {
  const file = $("midi-file").files[0];
  if (!file) throw new Error("请先选择 MIDI 文件。");
  setStatus("正在分析 MIDI");
  const form = new FormData();
  form.append("midi_file", file);
  const payload = await request("/api/foundation-patterns/upload", { method: "POST", body: form });
  uploadId = payload.upload_id;
  selectedTrack = payload.auto_selected_track_index;
  $("pattern-name").value = $("pattern-name").value || file.name.replace(/\.(mid|midi)$/i, "");
  $("upload-readout").textContent = file.name;
  const analysis = payload.analysis;
  $("analysis-summary").innerHTML = `<b>PPQ ${analysis.ppq}</b><span>${analysis.time_signature} · ${analysis.track_count} 条轨道 · 建议 ${analysis.suggested_loop_length_bars || "无"} 小节</span>`;
  if (analysis.suggested_loop_length_bars) { $("pattern-bars").value = analysis.suggested_loop_length_bars; renderSourceChordInputs(); }
  $("track-selection").innerHTML = analysis.note_tracks.map((track) => `<button class="pattern-track ${track.track_index === selectedTrack ? "active" : ""}" type="button" data-track="${track.track_index}"><b>轨道 ${track.track_index + 1} · ${track.track_name}</b><span>${track.note_count} 音符 · ${track.lowest_note}-${track.highest_note} · ${track.estimated_bars} 小节 · Ch ${track.channels.join(", ") || "0"}</span></button>`).join("");
  document.querySelectorAll(".pattern-track").forEach((button) => button.addEventListener("click", () => { selectedTrack = Number(button.dataset.track); document.querySelectorAll(".pattern-track").forEach((item) => item.classList.toggle("active", item === button)); }));
  setStatus("已完成分析，请确认源轨道与和弦");
}

function payloadForSave() { return { name: $("pattern-name").value.trim(), description: $("pattern-description").value.trim(), version: $("pattern-version").value.trim() || "1.0.0", source_track_index: selectedTrack, loop_length_bars: Number($("pattern-bars").value), source_key_root: $("source-key-root").value.trim() || "C", source_mode: $("source-mode").value, source_chords: [...document.querySelectorAll("[data-source-chord]")].map((input) => input.value.trim()), emotion: selectedTags("emotion"), energy: selectedTags("energy"), sound_direction: selectedTags("sound_direction"), rhythm: selectedTags("rhythm"), priority: Number($("pattern-priority").value || 100), enabled: $("pattern-enabled").checked }; }

async function savePattern() {
  if (!uploadId) throw new Error("请先上传并分析 MIDI。");
  if (selectedTrack === null) throw new Error("请选择 Foundation 源轨道。");
  setStatus("正在保存模板");
  const payload = await request(`/api/foundation-patterns/${uploadId}/save`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payloadForSave()) });
  uploadId = ""; selectedTrack = null; $("midi-file").value = ""; $("track-selection").innerHTML = ""; $("analysis-summary").textContent = "上传后显示 PPQ、长度、音域与轨道。"; renderSourceChordInputs(); $("pattern-description").value = "";
  patterns = payload.patterns || patterns; renderLibrary(); setStatus("模板已保存");
}

function patternMatchesSearch(pattern) { return pattern.name.toLowerCase().includes($("pattern-search").value.trim().toLowerCase()); }
function tagsText(tags) { return Object.values(tags || {}).flat().join(" · ") || "不限标签"; }
function renderLibrary() { const list = $("pattern-list"); const items = patterns.filter(patternMatchesSearch); list.innerHTML = items.length ? items.map((pattern) => `<article class="foundation-pattern-card"><div><div class="pattern-card-head"><b>${pattern.name}</b><span>${pattern.enabled ? "已启用" : "已停用"}</span></div><p>${pattern.loop_length_bars} 小节 · ${pattern.source_harmony.key_root} ${pattern.source_harmony.mode} · ${pattern.analysis.note_count} 音符 · ${pattern.analysis.lowest_note}-${pattern.analysis.highest_note}</p><p>${pattern.source_harmony.chords.join(" | ")}</p><small>${tagsText(pattern.tag_rules)}</small><div class="midi-visualization">${(pattern.events || []).map((event) => `<i style="left:${event.start_tick / (pattern.loop_length_bars * 19.2)}%;width:${Math.max(1, event.duration_ticks / (pattern.loop_length_bars * 19.2))}%;bottom:${Math.max(0, Math.min(70, event.note - 35))}px"></i>`).join("")}</div></div><div class="actions"><button type="button" data-action="play" data-id="${pattern.id}">试听原始</button><button type="button" data-action="adapted" data-id="${pattern.id}">试听适配</button><button type="button" data-action="normalize" data-id="${pattern.id}">规范音区</button><button type="button" data-action="duplicate" data-id="${pattern.id}">复制</button><button type="button" data-action="delete" data-id="${pattern.id}">删除</button></div></article>`).join("") : `<div class="file-readout">还没有已保存的 Foundation MIDI 模板。</div>`; list.querySelectorAll("button[data-action]").forEach((button) => button.addEventListener("click", () => patternAction(button.dataset.action, button.dataset.id))); }

function playPattern(pattern) { audioContext ||= new AudioContext(); const now = audioContext.currentTime + 0.04; const secondsPerTick = 60 / 96 / 480; (pattern.events || []).forEach((event) => { const oscillator = audioContext.createOscillator(), gain = audioContext.createGain(); oscillator.type = "triangle"; oscillator.frequency.value = 440 * 2 ** ((event.note - 69) / 12); gain.gain.setValueAtTime(0.0001, now + event.start_tick * secondsPerTick); gain.gain.exponentialRampToValueAtTime(Math.max(0.02, event.velocity / 900), now + event.start_tick * secondsPerTick + 0.01); gain.gain.exponentialRampToValueAtTime(0.0001, now + (event.start_tick + event.duration_ticks) * secondsPerTick); oscillator.connect(gain).connect(audioContext.destination); oscillator.start(now + event.start_tick * secondsPerTick); oscillator.stop(now + (event.start_tick + event.duration_ticks) * secondsPerTick + 0.03); }); }

async function patternAction(action, id) { const pattern = patterns.find((item) => item.id === id); try { if (action === "play") return playPattern(pattern); if (action === "adapted") { const payload = await request(`/api/foundation-patterns/${id}/preview-adapted`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target_chords: $("preview-target-chords").value }) }); return playPattern({ ...pattern, events: payload.events }); } if (action === "delete") { if (!confirm(`删除 ${pattern.name}？`)) return; await request(`/api/foundation-patterns/${id}`, { method: "DELETE" }); patterns = patterns.filter((item) => item.id !== id); renderLibrary(); return; } const endpoint = action === "normalize" ? "normalize-register" : "duplicate"; const payload = await request(`/api/foundation-patterns/${id}/${endpoint}`, { method: "POST" }); if (action === "duplicate") patterns = payload.patterns || patterns; else patterns = patterns.map((item) => item.id === id ? payload.pattern : item); renderLibrary(); setStatus(action === "normalize" ? "已规范 Foundation 音区" : "已复制模板"); } catch (error) { setStatus(error.message); } }

async function load() { const payload = await request("/api/foundation-patterns"); patterns = payload.patterns || []; renderLibrary(); }
$("analyze-midi").addEventListener("click", () => analyze().catch((error) => setStatus(error.message)));
$("save-pattern").addEventListener("click", () => savePattern().catch((error) => setStatus(error.message)));
$("midi-file").addEventListener("change", () => {
  const file = $("midi-file").files[0];
  if (!file) return;
  $("upload-readout").textContent = `已选择 ${file.name}，正在分析`;
  analyze().catch((error) => {
    $("upload-readout").textContent = file.name;
    setStatus(error.message);
  });
});
$("pattern-bars").addEventListener("change", renderSourceChordInputs);
$("pattern-search").addEventListener("input", renderLibrary);
renderTags(); renderSourceChordInputs(); load().catch((error) => setStatus(error.message));
