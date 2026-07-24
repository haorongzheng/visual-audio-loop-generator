const $ = (id) => document.getElementById(id);
if (window.location.protocol === "file:") window.location.replace("http://127.0.0.1:8766/admin/sample-import");
const noteNames = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
let sourceType = "single_wav";
let activeJob = null;
let definitions = { categories: [] };
let audioContext = null;
let selectedVscoInstruments = new Set();
let vscoDefinitions = [];

function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char])); }
function noteName(value) { const midi = Number(value); return `${noteNames[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`; }
function status(message, isError = false) { const node = $("import-status"); node.textContent = message; node.classList.toggle("error", isError); }
async function request(url, options = {}) { const response = await fetch(url, options); const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.error || "请求失败"); return data; }

function updateSourcePicker() {
  const input = $("import-files");
  const label = $("import-file-label");
  input.value = "";
  input.removeAttribute("webkitdirectory");
  input.removeAttribute("directory");
  if (sourceType === "single_wav") { input.accept = ".wav,audio/wav"; input.multiple = false; label.textContent = "选择一个 WAV 文件"; }
  if (sourceType === "sfz") { input.accept = ".sfz,.wav,.aif,.aiff,.flac"; input.multiple = true; label.textContent = "选择 SFZ 文件与它引用的采样"; }
  if (sourceType === "mappingchart") { input.accept = ".txt,.wav,.aif,.aiff,.flac,audio/wav,audio/aiff,audio/flac"; input.multiple = true; input.setAttribute("webkitdirectory", ""); input.setAttribute("directory", ""); label.textContent = "选择含 MappingChart.txt 的完整采样文件夹"; }
  if (sourceType === "vsco_library") { input.accept = ".sfz,.wav,.aif,.aiff,.flac"; input.multiple = true; input.setAttribute("webkitdirectory", ""); input.setAttribute("directory", ""); label.textContent = "选择整个 VSCO2 文件夹（支持 FLAC）"; }
  document.querySelectorAll("[data-source-type]").forEach((button) => button.classList.toggle("active", button.dataset.sourceType === sourceType));
}

function fillCategories() { const categories = [["", "选择分类"], ["piano", "Piano"], ["keyboard", "Keys"], ["nylon_guitar", "Nylon Guitar"], ["electric_guitar", "Electric Guitar"], ["strings", "Strings"], ["brass", "Brass"], ["woodwinds", "Woodwinds"], ["mallet", "Mallet"], ["organ", "Organ"], ["synth", "Synth"], ["other", "Other"]]; $("instrument-category").innerHTML = categories.map(([value, label]) => `<option value="${value}">${label}</option>`).join(""); }
function renderKeyboard(zones, selectedNote = null) {
  $("mapping-keyboard").innerHTML = Array.from({ length: 8 }, (_, index) => {
    const note = 24 + index * 12;
    const count = zones.filter((zone) => zone.low_midi_note <= note && note <= zone.high_midi_note).length;
    return `<button class="${count ? "mapped" : ""} ${selectedNote === note ? "active" : ""}" data-mapping-note="${note}">${noteName(note)}<small>${count || ""}</small></button>`;
  }).join("");
  document.querySelectorAll("[data-mapping-note]").forEach((button) => button.addEventListener("click", () => {
    const note = Number(button.dataset.mappingNote);
    document.querySelectorAll("#mapping-preview tr").forEach((row) => row.classList.toggle("zone-highlight", Number(row.dataset.low) <= note && note <= Number(row.dataset.high)));
    renderKeyboard(zones, note);
  }));
}
function renderPreview(job) {
  activeJob = job;
  const preview = job?.preview;
  if (!preview) return;
  $("preview-count").textContent = `${preview.zone_count} 个 Zone`;
  const warning = preview.warnings?.length ? `<span class="error">${preview.warnings.length} 个提示：${escapeHtml(preview.warnings[0])}</span>` : "";
  $("preview-summary").innerHTML = `<b>${escapeHtml(preview.instrument_name)}</b><span>${escapeHtml(preview.format)} · ${preview.sample_count} 个采样 · ${preview.keys || preview.zone_count} 个键 · ${preview.velocity_layers} 个力度层 · ${preview.round_robin || 1} 个 RR</span><span>整体音域：${noteName(preview.range.low)} 至 ${noteName(preview.range.high)}</span>${warning}`;
  if (!preview.instruments?.length && !$("instrument-name").value) $("instrument-name").value = preview.instrument_name;
  if (!$("source-library").value) $("source-library").value = preview.instrument_name;
  $("create-instrument").disabled = false;
  if (!preview.instruments?.length) $("create-instrument").textContent = "创建乐器并进入乐器库";
  renderVscoInstruments(preview.instruments || []);
  $("mapping-preview").innerHTML = preview.zones.map((zone, index) => {
    const audio = zone.sample_rate ? `${zone.sample_rate} Hz · ${zone.channels || 1} 声道 · ${Math.round(zone.duration_ms || 0)} ms` : (zone.warning || "待转换");
    const rr = zone.round_robin_group ? `rr${zone.round_robin_index || 1}` : "-";
    return `<tr data-low="${zone.low_midi_note}" data-high="${zone.high_midi_note}"><td><b>${escapeHtml(zone.file_name)}</b></td><td>${noteName(zone.root_midi_note)}</td><td>${noteName(zone.low_midi_note)}</td><td>${noteName(zone.high_midi_note)}</td><td>${zone.velocity_low}-${zone.velocity_high} <small>dyn${zone.velocity_layer || 1}</small></td><td>${rr}</td><td><small>${escapeHtml(audio)}</small></td><td><button data-preview-zone="${index}">试听</button></td></tr>`;
  }).join("");
  renderKeyboard(preview.zones);
  document.querySelectorAll("[data-preview-zone]").forEach((button) => button.addEventListener("click", () => playPreview(Number(button.dataset.previewZone))));
}

function renderVscoInstruments(instruments) {
  const container = $("vsco-instrument-list");
  if (!instruments.length) { container.classList.add("hidden"); container.innerHTML = ""; return; }
  vscoDefinitions = instruments;
  selectedVscoInstruments = new Set();
  const groups = [...new Set(instruments.map((item) => vscoGroup(item.name)))].sort((a, b) => a.localeCompare(b));
  container.classList.remove("hidden");
  container.innerHTML = `<div class="panel-head"><div><b>发现 ${instruments.length} 个 SFZ 乐器</b><span id="vsco-selection-count">先选择细分类，再选择一件乐器</span></div><span>每次创建一件</span></div><label class="field vsco-category-filter"><span>细分类</span><select id="vsco-category-select"><option value="">选择细分类</option>${groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)} · ${instruments.filter((item) => vscoGroup(item.name) === group).length}</option>`).join("")}</select></label><div id="vsco-category-items" class="vsco-category-items"><p class="hint">选择细分类后显示对应 SFZ 乐器。</p></div>`;
  $("vsco-category-select").addEventListener("change", () => { selectedVscoInstruments = new Set(); renderVscoCategoryItems(); updateVscoNameField(); });
  updateVscoNameField();
}

function renderVscoCategoryItems() {
  const group = $("vsco-category-select").value;
  const items = vscoDefinitions.filter((item) => vscoGroup(item.name) === group).sort((a, b) => a.name.localeCompare(b.name));
  $("vsco-category-items").innerHTML = items.length ? items.map((item) => `<button class="vsco-instrument-card ${selectedVscoInstruments.has(item.id) ? "active" : ""}" data-vsco-instrument="${escapeHtml(item.id)}"><b>${escapeHtml(item.name)}</b><span>${item.zone_count} 个 Zone · ${item.keys} 个键 · ${item.velocity_layers} 个力度层 · RR ${item.round_robin}</span></button>`).join("") : `<p class="hint">选择细分类后显示对应 SFZ 乐器。</p>`;
  document.querySelectorAll("[data-vsco-instrument]").forEach((button) => button.addEventListener("click", () => { selectedVscoInstruments = new Set([button.dataset.vscoInstrument]); renderVscoCategoryItems(); updateVscoNameField(); }));
}

function vscoGroup(name) {
  const value = String(name).toLowerCase();
  if (/violin/.test(value)) return "Violin";
  if (/viola/.test(value)) return "Viola";
  if (/cello/.test(value)) return "Cello";
  if (/contrabass/.test(value)) return "Contrabass";
  if (/harp/.test(value)) return "Harp";
  if (/trumpet/.test(value)) return "Trumpet";
  if (/trombone/.test(value)) return "Trombone";
  if (/horn/.test(value)) return "French Horn";
  if (/tuba/.test(value)) return "Tuba";
  if (/flute/.test(value)) return "Flute";
  if (/oboe/.test(value)) return "Oboe";
  if (/clarinet/.test(value)) return "Clarinet";
  if (/bassoon/.test(value)) return "Bassoon";
  if (/piccolo/.test(value)) return "Piccolo";
  if (/(piano|upright)/.test(value)) return "Piano";
  if (/organ/.test(value)) return "Organ";
  if (/(xylophone|glockenspiel|marimba|bell)/.test(value)) return "Mallet";
  if (/(timpani|perc)/.test(value)) return "Percussion";
  return "Other";
}

function updateVscoNameField() {
  const field = $("instrument-name");
  const selected = vscoDefinitions.filter((item) => selectedVscoInstruments.has(item.id));
  const count = $("vsco-selection-count");
  if (count) count.textContent = selected.length ? `当前选择：${selected[0].name}` : "从下方选择一个乐器";
  $("create-instrument").disabled = !selected.length || !$("track-role").value;
  $("create-instrument").textContent = selected.length ? "创建此乐器并进入乐器库" : "选择乐器后创建";
  if (selected.length === 1) { field.value = selected[0].name; field.placeholder = "可修改此乐器名称"; }
  else { field.value = ""; field.placeholder = "批量创建保留各 SFZ 名称"; }
}

async function playPreview(index) {
  if (!activeJob) return;
  try {
    audioContext ||= new AudioContext();
    const response = await fetch(`/api/sample-import/jobs/${encodeURIComponent(activeJob.id)}/audio/${index}`);
    if (!response.ok) throw new Error("该文件当前不能试听，请使用 WAV 文件。");
    const source = audioContext.createBufferSource();
    source.buffer = await audioContext.decodeAudioData(await response.arrayBuffer());
    source.connect(audioContext.destination);
    source.start();
    source.stop(audioContext.currentTime + Math.min(3, source.buffer.duration));
    status(`正在试听 ${activeJob.preview.zones[index].file_name}`);
  } catch (error) { status(error.message, true); }
}

async function analyzeImport() {
  const files = [...$("import-files").files];
  if (!files.length) { status("请先选择文件。", true); return; }
  try {
    if (sourceType === "vsco_library") return uploadVscoLibrary(files);
    status("正在上传并分析…");
    const form = new FormData();
    form.append("source_type", sourceType);
    files.forEach((file) => form.append("files", file, file.webkitRelativePath || file.name));
    const data = await request("/api/sample-import/upload", { method: "POST", body: form });
    renderPreview(data.job);
    status(`分析完成：${data.job.preview.zone_count} 个 Zone`);
    await loadJobs();
  } catch (error) { status(error.message, true); }
}

async function uploadVscoLibrary(files) {
  try {
    const usable = files.filter((file) => /\.(sfz|wav|aif|aiff|flac)$/i.test(file.name));
    if (!usable.some((file) => /\.sfz$/i.test(file.name))) throw new Error("所选文件夹中没有 SFZ 文件。");
    status(`正在建立 VSCO 索引：0 / ${usable.length}`);
    const started = await request("/api/sample-import/vsco/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    for (let index = 0; index < usable.length; index += 1) {
      const form = new FormData();
      form.append("job_id", started.job.id);
      form.append("file", usable[index], usable[index].webkitRelativePath || usable[index].name);
      await request("/api/sample-import/vsco/file", { method: "POST", body: form });
      if (index % 10 === 0 || index === usable.length - 1) status(`正在建立 VSCO 索引：${index + 1} / ${usable.length}`);
    }
    status("正在解析 SFZ 与采样关联…");
    const data = await request("/api/sample-import/vsco/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_id: started.job.id }) });
    renderPreview(data.job);
    status(`分析完成：${data.job.preview.instruments.length} 个 SFZ 乐器`);
    await loadJobs();
  } catch (error) { status(error.message, true); }
}

function metadata() {
  return {
    job_id: activeJob?.id,
    name: $("instrument-name").value.trim(),
    track_role: $("track-role").value,
    category: $("instrument-category").value,
    library: $("source-library").value.trim(),
    license: $("source-license").value.trim(),
    author: $("source-author").value.trim(),
    url: $("source-url").value.trim(),
    priority: Number($("instrument-priority").value || 100),
    enable_after_import: $("enable-after-import").checked
  };
}
async function createInstrument() {
  if (!activeJob) return;
  try {
    $("create-instrument").disabled = true;
    status("正在创建乐器…");
    const isVsco = activeJob?.preview?.source === "vsco_library";
    const payload = { ...metadata(), instrument_ids: [...selectedVscoInstruments] };
    if (isVsco && payload.instrument_ids.length !== 1) throw new Error("请先选择一件 VSCO 乐器。");
    if (isVsco && !payload.track_role) throw new Error("请先选择轨道。" );
    await request(isVsco ? "/api/sample-import/vsco/import" : "/api/sample-import/create-instrument", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    window.location.href = "/admin/instruments";
  } catch (error) { $("create-instrument").disabled = false; status(error.message, true); }
}

function renderJobs(jobs) {
  $("import-jobs").innerHTML = jobs.length ? jobs.map((job) => {
    const created = job.created_instruments || [];
    const createdLabel = created.length ? `已创建乐器${created.length > 1 ? ` · ${created.length} 件` : ""}：${escapeHtml(created.map((item) => item.name).join("、"))}` : "仅完成分析，尚未创建乐器";
    const actions = job.preview ? `<button data-open-job="${escapeHtml(job.id)}">打开预览</button>` : "";
    const manage = created.length ? `<a class="button-link" href="/admin/instruments">查看乐器</a>` : `<button class="danger" data-delete-job="${escapeHtml(job.id)}">删除分析任务</button>`;
    return `<article class="import-job"><div><b>${escapeHtml(job.preview?.instrument_name || job.id)}</b><span>${escapeHtml(job.preview?.format || "待分析")} · ${job.preview?.zone_count || 0} 个 Zone</span><span class="import-job-state ${created.length ? "is-created" : "is-analysis"}">${createdLabel}</span></div><div class="actions"><small>${escapeHtml(job.status)} · ${escapeHtml(job.created_at || "")}</small><div class="import-job-actions">${actions}${manage}</div></div></article>`;
  }).join("") : `<p class="hint">尚无导入任务。</p>`;
  document.querySelectorAll("[data-open-job]").forEach((button) => button.addEventListener("click", () => {
    const job = jobs.find((item) => item.id === button.dataset.openJob);
    if (job) { renderPreview(job); status(`已打开 ${job.preview.instrument_name} 的导入预览`); }
  }));
  document.querySelectorAll("[data-delete-job]").forEach((button) => button.addEventListener("click", async () => {
    const job = jobs.find((item) => item.id === button.dataset.deleteJob);
    if (!job || !window.confirm(`删除“${job.preview?.instrument_name || job.id}”的分析任务及其暂存采样？`)) return;
    try {
      const data = await request(`/api/sample-import/jobs/${encodeURIComponent(job.id)}`, { method: "DELETE" });
      if (activeJob?.id === job.id) activeJob = null;
      renderJobs(data.jobs || []);
      status("已删除未创建乐器的分析任务。");
    } catch (error) { status(error.message, true); }
  }));
}
async function loadJobs() { const data = await request("/api/sample-import/jobs"); renderJobs(data.jobs || []); }
async function loadDefinitions() { const data = await request("/api/instruments"); definitions = data.definitions || definitions; fillCategories(); }
function formatBytes(value) { return `${(Number(value || 0) / 1024 / 1024).toFixed(1)} MB`; }

function bind() {
  document.querySelectorAll("[data-source-type]").forEach((button) => button.addEventListener("click", () => { sourceType = button.dataset.sourceType; updateSourcePicker(); }));
  $("analyze-import").addEventListener("click", analyzeImport);
  $("create-instrument").addEventListener("click", createInstrument);
  $("track-role").addEventListener("change", () => { if (activeJob?.preview?.source === "vsco_library") updateVscoNameField(); });
  $("refresh-jobs").addEventListener("click", () => loadJobs().catch((error) => status(error.message, true)));
  $("cleanup-deleted-jobs").addEventListener("click", async () => {
    if (!window.confirm("清理已删除乐器对应的导入暂存文件？仍在乐器库中的乐器不会受影响。")) return;
    try {
      const data = await request("/api/sample-import/cleanup-deleted", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      renderJobs(data.jobs || []);
      status(data.cleanup.count ? `已清理 ${data.cleanup.count} 个遗留任务，释放 ${formatBytes(data.cleanup.bytes_freed)}。` : "没有发现可清理的已删除乐器暂存文件。");
    } catch (error) { status(error.message, true); }
  });
}

bind();
updateSourcePicker();
Promise.all([loadDefinitions(), loadJobs()]).catch((error) => status(error.message, true));
