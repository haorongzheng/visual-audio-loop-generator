const $ = (id) => document.getElementById(id);
const directionTags = ["ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic"];
const emotionTags = ["深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂"];
const energyTags = ["静止", "流动", "高能"];
const degreeChoices = ["root", "third", "fifth", "seventh", "octave_root", "octave_third", "octave_fifth"];
let modes = [];
let selectedId = "";

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
async function request(url, options = {}) { const response = await fetch(url, options); const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.error || "请求失败"); return data; }
function current() { return modes.find((item) => item.id === selectedId) || modes[0]; }
function tagChoices(key, values, items) { return items.map((value) => `<label><input data-tag="${key}" type="checkbox" value="${value}" ${values.includes(value) ? "checked" : ""}>${esc(value)}</label>`).join(""); }

function renderList() {
  const mode = current();
  $("mode-list").innerHTML = modes.map((item) => `<button data-mode="${item.id}" class="${item.id === mode?.id ? "active" : ""}"><b>${esc(item.label)}</b><br><small>${esc(item.description)}</small></button>`).join("");
  document.querySelectorAll("[data-mode]").forEach((button) => button.onclick = () => { selectedId = button.dataset.mode; render(); });
}

function eventRow(event, index) {
  return `<div class="event-row" data-event="${index}">
    <label class="field"><span>开始 Bar</span><input data-event-field="bar" type="number" min="0" max="3" value="${Number(event.bar) || 0}"></label>
    <label class="field degrees"><span>和弦音级</span><input data-event-field="degrees" value="${esc((event.degrees || []).join(", "))}" placeholder="root, third, fifth"></label>
    <label class="field"><span>持续小节</span><input data-event-field="duration_bars" type="number" min="1" max="4" value="${Number(event.duration_bars) || 1}"></label>
    <label class="switch"><input data-event-field="enabled" type="checkbox" ${event.enabled !== false ? "checked" : ""}> 启用</label>
    <button data-remove-event="${index}">删除</button>
  </div>`;
}

function render() {
  const mode = current();
  if (!mode) return;
  selectedId = mode.id;
  renderList();
  $("editor").innerHTML = `
    <div class="grid">
      <label class="field"><span>模式名称</span><input data-field="label" value="${esc(mode.label)}"></label>
      <label class="field"><span>英文名称</span><input data-field="name" value="${esc(mode.name)}"></label>
      <label class="field"><span>持续比例</span><input data-field="duration_ratio" type="number" min="0.1" max="1" step="0.05" value="${mode.duration_ratio}"></label>
      <label class="field"><span>延音</span><input data-field="sustain" type="number" min="0.1" max="1" step="0.05" value="${mode.sustain}"></label>
      <label class="field"><span>最低力度</span><input data-velocity="0" type="number" min="1" max="127" value="${mode.velocity_range?.[0] ?? 55}"></label>
      <label class="field"><span>最高力度</span><input data-velocity="1" type="number" min="1" max="127" value="${mode.velocity_range?.[1] ?? 75}"></label>
      <label class="field"><span>力度浮动</span><input data-field="velocity_amount" type="number" min="0" max="0.3" step="0.01" value="${mode.velocity_amount}"></label>
      <label class="field"><span>优先级</span><input data-field="priority" type="number" min="0" max="100" value="${mode.priority}"></label>
    </div>
    <label class="field"><span>描述</span><input data-field="description" value="${esc(mode.description)}"></label>
    <p><label class="switch"><input id="voice-leading" type="checkbox" ${mode.voice_leading !== false ? "checked" : ""}> 启用声部连接</label> <label class="switch"><input id="enabled" type="checkbox" ${mode.enabled !== false ? "checked" : ""}> 启用此模式</label></p>
    <p><b>允许音色方向：</b><span class="tags">${tagChoices("sound", mode.allowed_sound_directions || [], directionTags)}</span></p>
    <p><b>允许情绪：</b><span class="tags">${tagChoices("emotion", mode.allowed_emotions || [], emotionTags)}</span></p>
    <p><b>允许能量：</b><span class="tags">${tagChoices("energy", mode.allowed_energy || [], energyTags)}</span></p>
    <h2>和弦事件</h2>
    <p class="hint">可用音级：${degreeChoices.join("、")}。Bar 从 0 开始，对应界面中的第 1 小节。</p>
    <div id="events">${(mode.events || []).map(eventRow).join("")}</div>
    <button id="add-event">新增和弦事件</button>`;
  document.querySelectorAll("[data-field]").forEach((input) => input.oninput = () => { mode[input.dataset.field] = input.type === "number" ? Number(input.value) : input.value; });
  document.querySelectorAll("[data-velocity]").forEach((input) => input.oninput = () => { mode.velocity_range[Number(input.dataset.velocity)] = Number(input.value); });
  $("voice-leading").onchange = () => { mode.voice_leading = $("voice-leading").checked; };
  $("enabled").onchange = () => { mode.enabled = $("enabled").checked; };
  const tagKeys = { sound: "allowed_sound_directions", emotion: "allowed_emotions", energy: "allowed_energy" };
  Object.entries(tagKeys).forEach(([tag, key]) => document.querySelectorAll(`[data-tag="${tag}"]`).forEach((input) => input.onchange = () => { mode[key] = [...document.querySelectorAll(`[data-tag="${tag}"]:checked`)].map((item) => item.value); }));
  document.querySelectorAll("[data-event]").forEach((row) => {
    const event = mode.events[Number(row.dataset.event)];
    row.querySelectorAll("[data-event-field]").forEach((input) => input.onchange = () => {
      const key = input.dataset.eventField;
      if (key === "degrees") event.degrees = input.value.split(",").map((value) => value.trim()).filter((value) => degreeChoices.includes(value));
      else event[key] = input.type === "checkbox" ? input.checked : Number(input.value);
    });
  });
  document.querySelectorAll("[data-remove-event]").forEach((button) => button.onclick = () => { mode.events.splice(Number(button.dataset.removeEvent), 1); render(); });
  $("add-event").onclick = () => { mode.events.push({ bar: 0, degrees: ["root", "third", "fifth"], duration_bars: 1, enabled: true }); render(); };
  $("preview").textContent = `${mode.label}：${(mode.events || []).filter((item) => item.enabled !== false).map((item) => `第 ${Number(item.bar) + 1} 小节 ${item.degrees.join(" + ")}，持续 ${item.duration_bars} 小节`).join("；") || "没有启用的和弦事件"}`;
}

async function load() { const data = await request("/api/string-performance-modes"); modes = data.modes || []; selectedId ||= modes[0]?.id || ""; render(); }
$("save").onclick = async () => { try { const data = await request("/api/string-performance-modes/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ modes }) }); modes = data.modes || modes; $("status").textContent = "已保存"; render(); } catch (error) { $("status").textContent = error.message; } };
$("reset").onclick = async () => { if (!confirm("恢复两组默认弦乐模式？")) return; try { const data = await request("/api/string-performance-modes/reset", { method: "POST" }); modes = data.modes || []; selectedId = modes[0]?.id || ""; $("status").textContent = "已恢复默认"; render(); } catch (error) { $("status").textContent = error.message; } };
load().catch((error) => { $("status").textContent = error.message; });
