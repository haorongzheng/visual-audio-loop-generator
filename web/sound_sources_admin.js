const $ = (id) => document.getElementById(id);

const labels = {
  role: { foundation: "Foundation", bass: "Bass", drums: "Drums", texture_fx: "Sample" },
  sound: { ambient: "ambient / 氛围", acoustic: "acoustic / 原声", organic: "organic / 自然", vintage: "vintage / 复古", electronic: "electronic / 电子", ethnic: "ethnic / 民族", cinematic: "cinematic / 电影" },
  rhythm: { sparse: "sparse / 极简", flow: "flow / 流动", standard: "standard / 标准", groove: "groove / 律动", aggressive: "aggressive / 激烈" },
  slot: {
    kick: "Kick",
    snare: "Snare",
    clap: "Clap",
    closed_hat: "Closed Hat",
    open_hat: "Open Hat",
    shaker: "Shaker",
    perc: "Perc",
    perc_1: "Perc 1",
    perc_2: "Perc 2",
    low_tom: "Low Tom",
    high_tom: "High Tom",
    crash: "Crash",
    ride: "Ride",
    impact: "Impact",
    fill_hit: "Fill Hit",
    texture_perc: "Texture Perc"
  }
};

const defaultDefinitions = {
  track_roles: ["foundation", "bass", "drums", "texture_fx"],
  sound_directions: ["ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic"],
  energies: ["静止", "高能", "流动"],
  rhythms: ["sparse", "flow", "standard", "groove", "aggressive"],
  emotions: ["深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂"],
  drum_slots: { kick: {}, snare: {}, clap: {}, closed_hat: {}, open_hat: {}, shaker: {}, perc: {}, perc_1: {}, perc_2: {}, low_tom: {}, high_tom: {}, crash: {}, ride: {}, impact: {}, fill_hit: {}, texture_perc: {} }
};

let samples = [];
let definitions = { ...defaultDefinitions };
let selectedId = "";
let pendingFile = null;
let activeKind = "instrument";

if (location.protocol === "file:") {
  $("loop-console-link").href = "index.html";
}

async function loadData() {
  const response = await fetch("/api/sound-sources");
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "加载失败");
  samples = data.samples || [];
  definitions = { ...defaultDefinitions, ...(data.definitions || {}) };
  hydrateOptions();
  if (!selectedId && samples[0]) selectedId = samples[0].sample_id;
  renderForm();
  renderList();
}

function hydrateOptions() {
  hydrateTrackRoleOptions();
  fillSelect("slot", Object.keys(definitions.drum_slots || labels.slot), (value) => labels.slot[value] || value);
  fillSelect("insert-bar", ["1", "2", "3", "4", "5", "6", "7", "8"], (value) => `Bar ${value}`);
  hydrateFilterRoleOptions();
  fillSelect("filter-emotion", ["", ...(definitions.emotions || [])], (value) => value || "全部情绪");
  fillSelect("filter-energy", ["", ...(definitions.energies || [])], (value) => value || "全部能量");
  fillSelect("filter-sound", ["", ...(definitions.sound_directions || [])], (value) => value ? labels.sound[value] || value : "全部音色方向");
  fillSelect("filter-rhythm", ["", ...(definitions.rhythms || [])], (value) => value ? labels.rhythm[value] || value : "全部节奏");
  renderChoices("emotion-tags", definitions.emotions || [], {});
  renderChoices("energy-tags", definitions.energies || [], {});
  renderChoices("sound-tags", definitions.sound_directions || [], labels.sound);
  renderChoices("rhythm-tags", definitions.rhythms || [], labels.rhythm);
}

function hydrateTrackRoleOptions() {
  const roles = rolesForKind();
  fillSelect("track-role", roles, (value) => labels.role[value] || value);
  if (!roles.includes($("track-role").value)) $("track-role").value = roles[0];
}

function hydrateFilterRoleOptions() {
  const roles = rolesForKind();
  fillSelect("filter-role", ["", ...roles], (value) => value ? labels.role[value] || value : "全部轨道");
  if ($("filter-role").value && !roles.includes($("filter-role").value)) $("filter-role").value = "";
}

function rolesForKind() {
  return activeKind === "sample" ? ["texture_fx"] : ["foundation", "bass", "drums"];
}

function fillSelect(id, values, labeler) {
  const current = $(id).value;
  $(id).innerHTML = values.map((value) => `<option value="${escapeAttr(value)}">${escapeHtml(labeler(value))}</option>`).join("");
  if (values.includes(current)) $(id).value = current;
}

function renderChoices(id, values, labelMap) {
  $(id).innerHTML = values.map((value) => `
    <label class="choice">
      <input type="checkbox" value="${escapeAttr(value)}" />
      <span>${escapeHtml(labelMap[value] || value)}</span>
    </label>
  `).join("");
}

function blankSample() {
  const now = new Date().toISOString();
  return {
    sample_id: `sample_${Date.now()}`,
    name: "",
    description: "",
    file_name: "",
    file_url: "",
    enabled: true,
    target: activeKind === "sample" ? { track_role: "texture_fx", slot: "" } : { track_role: "drums", slot: "kick" },
    tag_rules: { sound_direction: [], energy: [], rhythm: [], emotion: [] },
    playback: { gain_db: 0, pan: 0, probability: 1, bar: 1 },
    audio_info: { duration_ms: 0, format: "" },
    created_at: now,
    updated_at: now
  };
}

function currentSample() {
  return samples.find((sample) => sample.sample_id === selectedId) || null;
}

function renderForm() {
  const sample = currentSample() || blankSample();
  if (currentSample()) activeKind = sample.target?.track_role === "texture_fx" ? "sample" : "instrument";
  updateKindButtons();
  hydrateTrackRoleOptions();
  $("sample-name").value = sample.name || "";
  $("sample-description").value = sample.description || "";
  $("track-role").value = sample.target?.track_role || "drums";
  $("slot").value = sample.target?.slot || "kick";
  $("gain-db").value = sample.playback?.gain_db ?? 0;
  $("pan").value = sample.playback?.pan ?? 0;
  $("probability").value = sample.playback?.probability ?? 1;
  $("insert-bar").value = String(sample.playback?.bar || 1);
  $("enabled").checked = sample.enabled !== false;
  $("preview-player").src = sample.file_url || "";
  updatePreviewVolume();
  updateGainReadout();
  $("file-readout").textContent = sample.file_name ? `${sample.file_name} · ${formatDuration(sample.audio_info?.duration_ms)}` : "尚未选择文件";
  setChecked("sound-tags", sample.tag_rules?.sound_direction || []);
  setChecked("energy-tags", sample.tag_rules?.energy || []);
  setChecked("rhythm-tags", sample.tag_rules?.rhythm || []);
  setChecked("emotion-tags", sample.tag_rules?.emotion || []);
  updateRoleVisibility();
}

function collectForm(base = currentSample() || blankSample()) {
  const role = activeKind === "sample" ? "texture_fx" : $("track-role").value;
  return {
    ...base,
    name: $("sample-name").value.trim() || base.name || "未命名采样",
    description: $("sample-description").value.trim(),
    enabled: $("enabled").checked,
    target: { track_role: role, slot: role === "drums" ? $("slot").value : "" },
    tag_rules: {
      emotion: getChecked("emotion-tags"),
      energy: getChecked("energy-tags"),
      sound_direction: getChecked("sound-tags"),
      rhythm: getChecked("rhythm-tags")
    },
    playback: {
      gain_db: Number($("gain-db").value || 0),
      pan: Number($("pan").value || 0),
      probability: Number($("probability").value || 1),
      bar: Number($("insert-bar").value || 1)
    },
    updated_at: new Date().toISOString()
  };
}

function getChecked(id) {
  return [...document.querySelectorAll(`#${id} input:checked`)].map((input) => input.value);
}

function setChecked(id, values) {
  const set = new Set(values || []);
  document.querySelectorAll(`#${id} input`).forEach((input) => (input.checked = set.has(input.value)));
}

function updateRoleVisibility() {
  const isSample = activeKind === "sample";
  const isDrums = !isSample && $("track-role").value === "drums";
  document.body.classList.toggle("sample-kind", isSample);
  $("upload-title").textContent = isSample ? "上传直接播放采样" : "上传音源文件";
  $("target-title").textContent = isSample ? "选择采样目标" : "选择 MIDI 目标";
  $("kind-help").textContent = isSample ? "采样部分：音频文件会作为 Sample 直接播放，不由 MIDI 音符触发。" : "音源部分：采样会被 Foundation / Bass / Drums 的 MIDI 事件调用。";
  $("track-role").disabled = isSample;
  $("slot-field").style.display = isDrums ? "grid" : "none";
  $("insert-bar-field").style.display = isSample ? "grid" : "none";
  $("rhythm-block").style.display = "grid";
}

function updateKindButtons() {
  document.querySelectorAll(".binder-mode .mode").forEach((button) => {
    button.classList.toggle("active", button.dataset.kind === activeKind);
  });
}

async function saveCurrent() {
  if (pendingFile) {
    await uploadPendingFile();
    return;
  }
  const sample = collectForm();
  samples = upsert(samples, sample);
  await saveAll();
  selectedId = sample.sample_id;
  renderForm();
  renderList();
}

async function uploadPendingFile() {
  const form = new FormData();
  const draft = collectForm(blankSample());
  form.append("files", pendingFile);
  form.append("name", draft.name);
  form.append("description", draft.description);
  form.append("track_role", draft.target.track_role);
  form.append("slot", draft.target.slot);
  form.append("sound_direction", JSON.stringify(draft.tag_rules.sound_direction));
  form.append("energy", JSON.stringify(draft.tag_rules.energy));
  form.append("rhythm", JSON.stringify(draft.tag_rules.rhythm));
  form.append("emotion", JSON.stringify(draft.tag_rules.emotion));
  form.append("gain_db", draft.playback.gain_db);
  form.append("pan", draft.playback.pan);
  form.append("probability", draft.playback.probability);
  form.append("bar", draft.playback.bar);
  form.append("enabled", draft.enabled);
  $("status-line").textContent = "正在上传...";
  const response = await fetch("/api/sound-sources/upload", { method: "POST", body: form });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "上传失败");
  samples = data.samples || [];
  selectedId = data.uploaded?.[0]?.sample_id || selectedId;
  pendingFile = null;
  $("sample-file").value = "";
  $("status-line").textContent = "已上传";
  renderForm();
  renderList();
}

async function saveAll() {
  const response = await fetch("/api/sound-sources/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ samples })
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "保存失败");
  samples = data.samples || [];
  $("status-line").textContent = "已保存";
}

function renderList() {
  const query = $("search").value.trim().toLowerCase();
  const role = $("filter-role").value;
  const emotion = $("filter-emotion").value;
  const energy = $("filter-energy").value;
  const sound = $("filter-sound").value;
  const rhythm = $("filter-rhythm").value;
  const filtered = samples.filter((sample) => {
    const rules = sample.tag_rules || {};
    if (!rolesForKind().includes(sample.target?.track_role)) return false;
    if (query && ![sample.name, sample.description, sample.file_name].join(" ").toLowerCase().includes(query)) return false;
    if (role && sample.target?.track_role !== role) return false;
    if (emotion && !(rules.emotion || []).includes(emotion)) return false;
    if (energy && !(rules.energy || []).includes(energy)) return false;
    if (sound && !(rules.sound_direction || []).includes(sound)) return false;
    if (rhythm && !(rules.rhythm || []).includes(rhythm)) return false;
    return true;
  });
  $("sample-list").innerHTML = filtered.length ? filtered.map(sampleCard).join("") : `<article class="source-card"><b>还没有匹配的采样</b></article>`;
  bindListActions();
}

function sampleCard(sample) {
  const rules = sample.tag_rules || {};
  return `
    <article class="source-card ${sample.sample_id === selectedId ? "active" : ""}" data-id="${escapeAttr(sample.sample_id)}">
      <div class="source-card-head">
        <b>${escapeHtml(sample.name || "未命名采样")}</b>
        <span>${sample.enabled ? "启用" : "停用"}</span>
      </div>
      <p>${escapeHtml(sample.file_name || sample.file_url || "")}</p>
      <div class="sample-meta">
        <span>${escapeHtml(labels.role[sample.target?.track_role] || sample.target?.track_role || "")}</span>
        <span>${sample.target?.slot ? escapeHtml(labels.slot[sample.target.slot] || sample.target.slot) : "无槽位"}</span>
        <span>${tagText(rules.emotion, {}, "不限情绪")}</span>
        <span>${tagText(rules.energy, {}, "不限能量")}</span>
        <span>${tagText(rules.sound_direction, labels.sound, "不限音色方向")}</span>
        <span>${tagText(rules.rhythm, labels.rhythm, "不限节奏")}</span>
        ${sample.target?.track_role === "texture_fx" ? `<span>Bar ${Number(sample.playback?.bar || 1)}</span>` : ""}
      </div>
      <div class="card-actions">
        <button type="button" data-action="play">试听</button>
        <button type="button" data-action="edit">编辑</button>
        <button type="button" data-action="toggle">${sample.enabled ? "禁用" : "启用"}</button>
        <button type="button" data-action="delete">删除</button>
      </div>
    </article>
  `;
}

function bindListActions() {
  document.querySelectorAll(".source-card[data-id]").forEach((card) => {
    card.addEventListener("click", () => {
      selectedId = card.dataset.id;
      pendingFile = null;
      renderForm();
      renderList();
    });
    card.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.stopPropagation();
        await handleCardAction(card.dataset.id, button.dataset.action);
      });
    });
  });
}

async function handleCardAction(id, action) {
  const sample = samples.find((item) => item.sample_id === id);
  if (!sample) return;
  if (action === "play") {
    $("preview-player").src = sample.file_url;
    $("preview-player").play();
    return;
  }
  if (action === "edit") {
    selectedId = id;
    pendingFile = null;
    renderForm();
    renderList();
    return;
  }
  if (action === "toggle") {
    sample.enabled = !sample.enabled;
    sample.updated_at = new Date().toISOString();
    await saveAll();
  }
  if (action === "delete") {
    samples = samples.filter((item) => item.sample_id !== id);
    if (selectedId === id) selectedId = samples[0]?.sample_id || "";
    await saveAll();
  }
  renderForm();
  renderList();
}

function newSample() {
  selectedId = "";
  pendingFile = null;
  $("sample-file").value = "";
  $("preview-player").removeAttribute("src");
  $("file-readout").textContent = "尚未选择文件";
  const sample = blankSample();
  $("sample-name").value = "";
  $("sample-description").value = "";
  hydrateTrackRoleOptions();
  $("track-role").value = sample.target.track_role;
  $("slot").value = sample.target.slot;
  $("gain-db").value = 0;
  $("pan").value = 0;
  $("probability").value = 1;
  $("insert-bar").value = "1";
  $("enabled").checked = true;
  setChecked("sound-tags", []);
  setChecked("energy-tags", []);
  setChecked("rhythm-tags", []);
  setChecked("emotion-tags", []);
  updateRoleVisibility();
  updatePreviewVolume();
  updateGainReadout();
}

function setKind(kind) {
  activeKind = kind;
  selectedId = "";
  pendingFile = null;
  hydrateTrackRoleOptions();
  hydrateFilterRoleOptions();
  hydrateOptions();
  updateKindButtons();
  newSample();
  renderList();
}

function upsert(items, sample) {
  const index = items.findIndex((item) => item.sample_id === sample.sample_id);
  if (index >= 0) items[index] = sample;
  else items.push(sample);
  return items;
}

function tagText(values, map, empty) {
  if (!values || !values.length) return empty;
  return values.map((value) => map[value] || value).join("、");
}

function formatDuration(ms) {
  return ms ? `${Math.round(ms / 10) / 100} 秒` : "未知时长";
}

function updatePreviewVolume() {
  const gainDb = Number($("gain-db").value || 0);
  $("preview-player").volume = Math.max(0, Math.min(1, 10 ** (gainDb / 20)));
}

function updateGainReadout() {
  const value = Number($("gain-db").value || 0);
  $("gain-readout").textContent = `${value > 0 ? "+" : ""}${value} dB`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

$("sample-file").addEventListener("change", () => {
  pendingFile = $("sample-file").files[0] || null;
  if (pendingFile) {
    if (!$("sample-name").value.trim()) $("sample-name").value = pendingFile.name.replace(/\.[^.]+$/, "").replace(/[_-]/g, " ");
    $("file-readout").textContent = pendingFile.name;
    $("preview-player").src = URL.createObjectURL(pendingFile);
    updatePreviewVolume();
    updateGainReadout();
  }
});
$("track-role").addEventListener("change", updateRoleVisibility);
$("gain-db").addEventListener("input", () => {
  updatePreviewVolume();
  updateGainReadout();
});
document.querySelectorAll(".binder-mode .mode").forEach((button) => {
  button.addEventListener("click", () => setKind(button.dataset.kind));
});
$("new-sample").addEventListener("click", newSample);
$("save-sample").addEventListener("click", () => saveCurrent().catch((error) => ($("status-line").textContent = error.message)));
["search", "filter-role", "filter-emotion", "filter-energy", "filter-sound", "filter-rhythm"].forEach((id) => $(id).addEventListener("input", renderList));

loadData().catch((error) => {
  $("status-line").textContent = error.message;
  definitions = { ...defaultDefinitions };
  hydrateOptions();
  renderForm();
  renderList();
});
