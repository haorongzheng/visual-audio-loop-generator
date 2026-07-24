const emotions = [["深沉", "深沉"], ["阴郁", "阴郁"], ["忧伤", "忧伤"], ["平静", "平静"], ["温暖", "温暖"], ["明亮", "明亮"], ["欢快", "欢快"], ["激昂", "激昂"]];
const energies = [["静止", "静止"], ["高能", "高能"], ["流动", "流动"]];
const sounds = [["氛围", "ambient"], ["原声", "acoustic"], ["自然", "organic"], ["复古", "vintage"], ["电子", "electronic"], ["民族", "ethnic"], ["电影", "cinematic"]];
const rhythms = [["极简", "sparse"], ["流动", "flow"], ["标准", "standard"], ["律动", "groove"], ["激烈", "aggressive"]];

const sampleTypes = ["texture", "one_shot", "drum_one_shot", "drum_loop", "tonal_loop", "transition"];
const playbackTypes = ["one_shot", "loop", "sync_loop", "random_one_shot", "fill"];
const triggerModes = ["on_loop_start", "on_bar", "on_step", "random_step", "on_fill", "continuous"];
const reverbOptions = ["none", "room", "hall", "plate", "large_hall"];
const delayOptions = ["none", "short", "ping_pong", "tape"];
const filterOptions = ["none", "lowpass", "highpass", "bandpass", "telephone"];

let samples = [];
let selectedId = null;

const $ = (id) => document.getElementById(id);

if (location.protocol === "file:") {
  $("loop-console-link").href = "index.html";
  $("drum-source-link").href = "sound_sources_admin.html";
}

function defaultSample() {
  const now = new Date().toISOString();
  return {
    sample_id: `sample_${Date.now()}`,
    name: "Untitled Sample",
    description: "",
    file_url: "",
    enabled: true,
    sample_type: "texture",
    playback_type: "loop",
    audio_info: {
      duration_seconds: 0,
      bpm: null,
      key: null,
      root_note: null,
      length_bars: 4,
      is_loop: true
    },
    tag_rules: { emotion: [], energy: [], sound_direction: [], rhythm: [] },
    trigger_rule: { trigger_mode: "on_loop_start", bar: 1, step: 0, probability: 0.65, max_uses_per_loop: 1 },
    mix: { gain_db: -12, pan: 0, fade_in_ms: 20, fade_out_ms: 80 },
    fx: { reverb: "room", delay: "none", filter: "none", sidechain: false },
    priority: 50,
    created_at: now,
    updated_at: now
  };
}

function selectedSample() {
  return samples.find((sample) => sample.sample_id === selectedId) || null;
}

function fillSelect(id, options) {
  $(id).innerHTML = options.map((value) => `<option value="${value}">${value}</option>`).join("");
}

function renderMultiSelect(containerId, items, values, key) {
  const container = $(containerId);
  container.innerHTML = "";
  items.forEach(([label, value]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `choice ${values.includes(value) ? "active" : ""}`;
    button.textContent = label;
    button.addEventListener("click", () => {
      const sample = collectForm();
      const set = new Set(sample.tag_rules[key]);
      if (set.has(value)) set.delete(value);
      else set.add(value);
      sample.tag_rules[key] = [...set];
      updateSampleInMemory(sample);
      renderEditor();
    });
    container.appendChild(button);
  });
}

function renderList() {
  const query = $("sample-search").value.trim().toLowerCase();
  const list = $("sample-list");
  const filtered = samples.filter((sample) => {
    const haystack = [sample.name, sample.sample_type, ...(sample.tag_rules?.emotion || []), ...(sample.tag_rules?.energy || []), ...(sample.tag_rules?.sound_direction || []), ...(sample.tag_rules?.rhythm || [])].join(" ").toLowerCase();
    return !query || haystack.includes(query);
  });
  list.innerHTML = filtered.map(sampleCard).join("");
  list.querySelectorAll(".sample-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectedId = card.dataset.id;
      renderAll();
    });
  });
  list.querySelectorAll(".sample-preview").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const sample = samples.find((item) => item.sample_id === button.dataset.id);
      previewSample(sample);
    });
  });
}

function sampleCard(sample) {
  const active = sample.sample_id === selectedId ? "active" : "";
  const enabled = sample.enabled ? "启用" : "停用";
  const tagLine = [
    ...(sample.tag_rules?.sound_direction || []),
    ...(sample.tag_rules?.emotion || []),
    ...(sample.tag_rules?.energy || []),
    ...(sample.tag_rules?.rhythm || [])
  ].slice(0, 6);
  return `
    <article class="sample-card ${active}" data-id="${sample.sample_id}">
      <div class="sample-card-head">
        <b>${escapeHtml(sample.name || "Untitled Sample")}</b>
        <button type="button" class="track-toggle sample-preview" data-id="${sample.sample_id}" title="Preview" aria-label="Preview">▶</button>
      </div>
      <div class="sample-meta">
        <span>${sample.sample_type}</span>
        <span>${enabled}</span>
      </div>
      <div class="tag-line">${tagLine.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("") || "<span>Any State</span>"}</div>
    </article>
  `;
}

function renderEditor() {
  const sample = selectedSample() || defaultSample();
  $("editor-title").textContent = sample.name || "Untitled Sample";
  $("name").value = sample.name || "";
  $("description").value = sample.description || "";
  $("enabled").checked = Boolean(sample.enabled);
  $("sample-type").value = sample.sample_type || "texture";
  $("playback-type").value = sample.playback_type || "loop";
  $("priority").value = sample.priority ?? 50;
  $("file-url").value = sample.file_url || "";
  $("duration").value = sample.audio_info?.duration_seconds ?? 0;
  $("bpm-input").value = sample.audio_info?.bpm ?? "";
  $("key-input").value = sample.audio_info?.key ?? "";
  $("root-note").value = sample.audio_info?.root_note ?? "";
  $("length-bars").value = sample.audio_info?.length_bars ?? 4;
  $("is-loop").checked = Boolean(sample.audio_info?.is_loop);
  $("trigger-mode").value = sample.trigger_rule?.trigger_mode || "on_loop_start";
  $("trigger-bar").value = sample.trigger_rule?.bar ?? 1;
  $("trigger-step").value = sample.trigger_rule?.step ?? 0;
  $("probability").value = sample.trigger_rule?.probability ?? 0.65;
  $("max-uses").value = sample.trigger_rule?.max_uses_per_loop ?? 1;
  $("gain-db").value = sample.mix?.gain_db ?? -12;
  $("pan").value = sample.mix?.pan ?? 0;
  $("fade-in").value = sample.mix?.fade_in_ms ?? 20;
  $("fade-out").value = sample.mix?.fade_out_ms ?? 80;
  $("reverb").value = sample.fx?.reverb || "room";
  $("delay").value = sample.fx?.delay || "none";
  $("filter").value = sample.fx?.filter || "none";
  $("sidechain").checked = Boolean(sample.fx?.sidechain);
  renderMultiSelect("emotion-tags", emotions, sample.tag_rules?.emotion || [], "emotion");
  renderMultiSelect("energy-tags", energies, sample.tag_rules?.energy || [], "energy");
  renderMultiSelect("sound-tags", sounds, sample.tag_rules?.sound_direction || [], "sound_direction");
  renderMultiSelect("rhythm-tags", rhythms, sample.tag_rules?.rhythm || [], "rhythm");
  $("admin-json").textContent = JSON.stringify(sample, null, 2);
}

function collectForm() {
  const existing = selectedSample() || defaultSample();
  return {
    ...existing,
    name: $("name").value.trim() || "Untitled Sample",
    description: $("description").value,
    file_url: $("file-url").value.trim(),
    enabled: $("enabled").checked,
    sample_type: $("sample-type").value,
    playback_type: $("playback-type").value,
    audio_info: {
      ...(existing.audio_info || {}),
      duration_seconds: numberOrNull($("duration").value) || 0,
      bpm: numberOrNull($("bpm-input").value),
      key: emptyToNull($("key-input").value),
      root_note: emptyToNull($("root-note").value),
      length_bars: numberOrNull($("length-bars").value) || 4,
      is_loop: $("is-loop").checked
    },
    tag_rules: existing.tag_rules || { emotion: [], energy: [], sound_direction: [], rhythm: [] },
    trigger_rule: {
      trigger_mode: $("trigger-mode").value,
      bar: numberOrNull($("trigger-bar").value) || 1,
      step: numberOrNull($("trigger-step").value) || 0,
      probability: numberOrNull($("probability").value) ?? 0.65,
      max_uses_per_loop: numberOrNull($("max-uses").value) || 1
    },
    mix: {
      gain_db: numberOrNull($("gain-db").value) ?? -12,
      pan: numberOrNull($("pan").value) ?? 0,
      fade_in_ms: numberOrNull($("fade-in").value) || 0,
      fade_out_ms: numberOrNull($("fade-out").value) || 0
    },
    fx: {
      reverb: $("reverb").value,
      delay: $("delay").value,
      filter: $("filter").value,
      sidechain: $("sidechain").checked
    },
    priority: numberOrNull($("priority").value) || 50
  };
}

function updateSampleInMemory(sample) {
  const index = samples.findIndex((item) => item.sample_id === sample.sample_id);
  if (index >= 0) samples[index] = sample;
  else samples.unshift(sample);
  selectedId = sample.sample_id;
}

function renderAll() {
  renderList();
  renderEditor();
}

async function loadSamples() {
  if (location.protocol === "file:") {
    samples = [defaultSample()];
    selectedId = samples[0].sample_id;
    renderAll();
    $("admin-status").textContent = "预览模式";
    return;
  }
  const response = await fetch("/api/samples");
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "加载失败");
  samples = payload.samples || [];
  if (!selectedId && samples[0]) selectedId = samples[0].sample_id;
  if (!selectedId && samples.length === 0) {
    const sample = defaultSample();
    samples = [sample];
    selectedId = sample.sample_id;
  }
  renderAll();
}

async function saveSample() {
  const sample = collectForm();
  if (!sample.file_url) {
    $("admin-status").textContent = "请先上传音频文件";
    return;
  }
  updateSampleInMemory(sample);
  if (location.protocol === "file:") {
    $("admin-status").textContent = "预览模式";
    renderAll();
    return;
  }
  $("admin-status").textContent = "保存中";
  const response = await fetch("/api/samples/upsert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sample })
  });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "保存失败");
  samples = payload.samples || [];
  selectedId = payload.sample.sample_id;
  $("admin-status").textContent = "已保存";
  renderAll();
}

async function uploadSample() {
  const file = $("sample-file").files[0];
  if (!file) return;
  if (location.protocol === "file:") {
    const sample = collectForm();
    sample.name = file.name.replace(/\.[^.]+$/, "") || sample.name;
    sample.file_url = URL.createObjectURL(file);
    updateSampleInMemory(sample);
    $("admin-status").textContent = "预览模式";
    renderAll();
    previewSample(sample);
    return;
  }
  $("admin-status").textContent = "上传中";
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/samples/upload", { method: "POST", body: form });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "上传失败");
  samples = payload.samples || [];
  selectedId = payload.sample.sample_id;
  $("sample-file").value = "";
  $("admin-status").textContent = "已上传";
  renderAll();
}

async function deleteSample() {
  const sample = selectedSample();
  if (!sample) return;
  if (location.protocol === "file:") {
    samples = samples.filter((item) => item.sample_id !== sample.sample_id);
    if (samples.length === 0) samples = [defaultSample()];
    selectedId = samples[0].sample_id;
    $("admin-status").textContent = "预览模式";
    renderAll();
    return;
  }
  const response = await fetch("/api/samples/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sample_id: sample.sample_id })
  });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "删除失败");
  samples = payload.samples || [];
  selectedId = samples[0]?.sample_id || null;
  $("admin-status").textContent = "已删除";
  renderAll();
}

function newSample() {
  const sample = defaultSample();
  updateSampleInMemory(sample);
  $("admin-status").textContent = "已新建";
  renderAll();
}

function previewSample(sample = selectedSample()) {
  if (!sample?.file_url) {
    $("admin-status").textContent = "没有音频文件";
    return;
  }
  const player = $("sample-player");
  player.src = `${sample.file_url}?t=${Date.now()}`;
  player.load();
  player.play().catch(() => {});
}

function bindFormAutosync() {
  document.querySelectorAll(".sample-editor input, .sample-editor textarea, .sample-editor select").forEach((input) => {
    input.addEventListener("input", () => {
      updateSampleInMemory(collectForm());
      renderList();
      $("admin-json").textContent = JSON.stringify(selectedSample(), null, 2);
    });
  });
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function emptyToNull(value) {
  const text = String(value || "").trim();
  return text || null;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[char]);
}

fillSelect("sample-type", sampleTypes);
fillSelect("playback-type", playbackTypes);
fillSelect("trigger-mode", triggerModes);
fillSelect("reverb", reverbOptions);
fillSelect("delay", delayOptions);
fillSelect("filter", filterOptions);
bindFormAutosync();

$("sample-search").addEventListener("input", renderList);
$("sample-file").addEventListener("change", () => uploadSample().catch((error) => ($("admin-status").textContent = error.message)));
$("save-sample").addEventListener("click", () => saveSample().catch((error) => ($("admin-status").textContent = error.message)));
$("save-sample-bottom").addEventListener("click", () => saveSample().catch((error) => ($("admin-status").textContent = error.message)));
$("new-sample").addEventListener("click", newSample);
$("delete-sample").addEventListener("click", () => deleteSample().catch((error) => ($("admin-status").textContent = error.message)));
$("preview-sample").addEventListener("click", () => previewSample());

loadSamples().catch((error) => {
  const sample = defaultSample();
  samples = [sample];
  selectedId = sample.sample_id;
  renderAll();
  $("admin-status").textContent = error.message;
});
