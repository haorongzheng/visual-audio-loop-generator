const $ = (id) => document.getElementById(id);
const tags = {
  allowed_sound_directions: ["ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic"],
  allowed_energy: ["静止", "高能", "流动"],
  allowed_rhythm: ["sparse", "flow", "standard", "groove", "aggressive"]
};
const chords = [[60, 64, 67, 71, 74], [57, 60, 64, 67, 71], [53, 57, 60, 64, 67], [55, 60, 62, 65, 69]];
let modes = [];
let context;

function status(text) { $("status-line").textContent = text; }
async function request(url, options = {}) { const response = await fetch(url, options); const payload = await response.json(); if (!response.ok || !payload.ok) throw new Error(payload.error || "请求失败"); return payload; }
function tagButtons(mode, field) { return tags[field].map((value) => `<button type="button" class="choice ${mode[field]?.includes(value) ? "active" : ""}" data-tag-field="${field}" data-tag-value="${value}">${value}</button>`).join(""); }
function listValues(card, field) { return [...card.querySelectorAll(`[data-tag-field="${field}"].active`)].map((item) => item.dataset.tagValue); }
function render() {
  $("mode-list").innerHTML = modes.map((mode) => `<article class="foundation-pattern-card" data-mode-id="${mode.id}">
    <div style="width:100%"><div class="pattern-card-head"><div><b>${mode.label}</b><small>${mode.name} · ${mode.description}</small></div><label class="switch"><input data-field="enabled" type="checkbox" ${mode.enabled ? "checked" : ""}/> 启用</label></div>
    <div class="four-col" style="margin-top:12px"><label class="field"><span>Timing</span><input data-field="timing" type="number" min="0" max="0.5" step="0.01" value="${mode.timing}" /></label><label class="field"><span>Velocity</span><input data-field="velocity" type="number" min="0" max="0.5" step="0.01" value="${mode.velocity}" /></label><label class="field"><span>优先级</span><input data-field="priority" type="number" min="0" max="999" value="${mode.priority}" /></label><div class="field"><span>Bar 4 变化</span><b>${mode.bar4}</b></div></div>
    <div class="tag-sections"><div class="tag-block"><span>允许音色方向</span><div class="choice-grid">${tagButtons(mode, "allowed_sound_directions")}</div></div><div class="tag-block"><span>允许能量</span><div class="choice-grid">${tagButtons(mode, "allowed_energy")}</div></div><div class="tag-block"><span>允许节奏</span><div class="choice-grid">${tagButtons(mode, "allowed_rhythm")}</div></div></div></div>
    <div class="actions"><button type="button" data-preview="${mode.id}">试听 4 小节</button></div></article>`).join("");
  document.querySelectorAll("[data-tag-field]").forEach((button) => button.addEventListener("click", () => button.classList.toggle("active")));
  document.querySelectorAll("[data-preview]").forEach((button) => button.addEventListener("click", () => preview(button.dataset.preview)));
}
function currentModes() { return modes.map((mode) => { const card = document.querySelector(`[data-mode-id="${mode.id}"]`); return { ...mode, enabled: card.querySelector('[data-field="enabled"]').checked, timing: Number(card.querySelector('[data-field="timing"]').value), velocity: Number(card.querySelector('[data-field="velocity"]').value), priority: Number(card.querySelector('[data-field="priority"]').value), allowed_sound_directions: listValues(card, "allowed_sound_directions"), allowed_energy: listValues(card, "allowed_energy"), allowed_rhythm: listValues(card, "allowed_rhythm") }; }); }
function preview(modeId) {
  const mode = currentModes().find((item) => item.id === modeId); if (!mode) return;
  context ||= new AudioContext(); const bpm = Number($("preview-bpm").value || 96); const energy = $("preview-energy").value; const secondsPerStep = 60 / bpm / 4; const now = context.currentTime + .05;
  const events = mode.events.filter((event) => !(energy === "静止" && ["pulse", "arpeggio"].includes(mode.id) && event[0] % 4));
  for (let bar = 0; bar < 4; bar += 1) for (const [step, duration, level, kind] of events) {
    let notes = chords[bar]; if (kind === "split_lower") notes = notes.slice(0, 2); if (["split_upper", "upper_chord"].includes(kind)) notes = notes.slice(2); if (kind === "arp_up") notes = [notes[(step / 2) % notes.length]];
    notes.forEach((note, index) => { const osc = context.createOscillator(), gain = context.createGain(); const start = now + (bar * 16 + step) * secondsPerStep + (kind === "arp_up" ? index * secondsPerStep * .35 : 0); const length = Math.max(.06, duration * secondsPerStep * (mode.id === "block" ? .78 : .55)); osc.type = "triangle"; osc.frequency.value = 440 * 2 ** ((note - 69) / 12); gain.gain.setValueAtTime(.0001, start); gain.gain.exponentialRampToValueAtTime(Math.max(.015, .055 * level), start + .012); gain.gain.exponentialRampToValueAtTime(.0001, start + length); osc.connect(gain).connect(context.destination); osc.start(start); osc.stop(start + length + .02); });
  }
  status(`正在试听 ${mode.label}`);
}
async function load() { const payload = await request("/api/foundation-performance-modes"); modes = payload.modes || []; render(); status("已加载 8 个内置模式"); }
$("save").addEventListener("click", async () => { try { const payload = await request("/api/foundation-performance-modes/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ modes: currentModes() }) }); modes = payload.modes; render(); status("已保存。新的生成会直接使用这些设置。"); } catch (error) { status(error.message); } });
$("reset").addEventListener("click", async () => { if (!confirm("恢复全部 Foundation 演奏模式为默认设置？")) return; try { const payload = await request("/api/foundation-performance-modes/reset", { method: "POST" }); modes = payload.modes; render(); status("已恢复默认设置"); } catch (error) { status(error.message); } });
load().catch((error) => status(error.message));
