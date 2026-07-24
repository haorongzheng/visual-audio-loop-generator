const emotionMap = {
  "-1": ["深沉", -1],
  "-0.75": ["阴郁", -0.75],
  "-0.5": ["忧伤", -0.5],
  "-0.25": ["平静", -0.25],
  "0": ["平静", -0.25],
  "0.25": ["温暖", 0.25],
  "0.5": ["明亮", 0.5],
  "0.75": ["欢快", 0.75],
  "1": ["激昂", 1]
};

const energyMap = {
  "0": ["静止", 0],
  "1": ["高能", 1],
  "0.5": ["流动", 0.5]
};

const emotions = [
  ["深沉", "-1"],
  ["阴郁", "-0.75"],
  ["忧伤", "-0.5"],
  ["平静", "-0.25"],
  ["温暖", "0.25"],
  ["明亮", "0.5"],
  ["欢快", "0.75"],
  ["激昂", "1"]
];

const energies = Object.entries(energyMap).map(([value, item]) => [item[0], value]);

const sounds = [
  ["氛围", "ambient"],
  ["原声", "acoustic"],
  ["自然", "organic"],
  ["复古", "vintage"],
  ["电子", "electronic"],
  ["民族", "ethnic"],
  ["电影", "cinematic"]
];

const rhythms = [
  ["极简", "sparse"],
  ["流动", "flow"],
  ["标准", "standard"],
  ["律动", "groove"],
  ["激烈", "aggressive"]
];

let selectedEmotion = "0.75";
let selectedEnergy = "0.5";
let selectedSound = "electronic";
let selectedRhythm = "groove";
let activeTab = "resolved";
let inputMode = "controls";
let lastResult = null;
let resolveRequestId = 0;
let availableInstruments = [];
let guitarPerformanceModes = [];
let stringPerformanceModes = [];
const foundationSettingsStorageKey = "audio-loop-generator.foundation-bass-settings.v2";
const legacyFoundationSettingsStorageKey = "audio-loop-generator.foundation-settings.v1";
const soundInstrumentDefaultsStorageKey = "audio-loop-generator.sound-instrument-defaults.v1";
let savedFoundationSettings = loadSavedFoundationSettings();
let savedSoundInstrumentDefaults = loadSoundInstrumentDefaults();
let mixerSettings = Object.fromEntries(["Foundation", "Bass", "Drums", "Sample"].map((track) => [track, { gain_db: 0, pan: 0 }]));
let effectsSettings = {
  delay: { enabled: false, mix: 0.08, beats: 0.75 },
  reverb: { enabled: false, mix: 0.18, decay: 0.45 },
  filter: { enabled: false, mode: "lowpass", cutoff_hz: 12000 },
  sidechain: { enabled: false, amount: 0.35, release_ms: 140 }
};
const midiTrackNames = ["Foundation", "Bass", "Drums"];
const trackNames = [...midiTrackNames, "Sample"];
const trackControls = Object.fromEntries(trackNames.map((name) => [name, { solo: false, mute: false }]));

const $ = (id) => document.getElementById(id);
const isFilePreview = location.protocol === "file:";

function loadSavedFoundationSettings() {
  try {
    const stored = localStorage.getItem(foundationSettingsStorageKey) || localStorage.getItem(legacyFoundationSettingsStorageKey);
    const value = JSON.parse(stored || "null");
    if (value?.profiles && typeof value.profiles === "object") return { profiles: value.profiles, legacy: value.legacy || {} };
    if (value && typeof value === "object") return { profiles: {}, legacy: value };
    return { profiles: {}, legacy: {} };
  } catch (_) {
    return { profiles: {}, legacy: {} };
  }
}

function loadSoundInstrumentDefaults() {
  try {
    const value = JSON.parse(localStorage.getItem(soundInstrumentDefaultsStorageKey) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch (_) {
    return {};
  }
}

function foundationBassProfileKey() {
  return [selectedEmotion, selectedEnergy, selectedSound, selectedRhythm].join("|");
}

function activeFoundationBassSettings() {
  return savedFoundationSettings.profiles?.[foundationBassProfileKey()] || savedFoundationSettings.legacy || {};
}

function activeSoundInstrumentDefaults() {
  return savedSoundInstrumentDefaults[selectedSound] || {};
}

function setSelectValue(id, value) {
  const select = $(id);
  if (select && value !== undefined && [...select.options].some((option) => option.value === value)) select.value = value;
}

function restoreFoundationSettings(showStatus = false) {
  const hasExactProfile = Boolean(savedFoundationSettings.profiles?.[foundationBassProfileKey()]);
  const settings = activeFoundationBassSettings();
  const defaults = activeSoundInstrumentDefaults();
  const hasDefaults = Boolean(defaults.foundation || defaults.bass);
  if (!Object.keys(settings).length && !hasDefaults) return false;
  setSelectValue("foundation-pattern-source", settings.foundation_pattern_source);
  setSelectValue("foundation-uploaded-pattern", settings.foundation_uploaded_pattern_id);
  setSelectValue("foundation-performance-mode", settings.foundation_performance_mode);
  const override = $("override-uploaded-performance");
  if (override && typeof settings.override_uploaded_performance === "boolean") override.checked = settings.override_uploaded_performance;
  const preserve = $("preserve-uploaded-performance");
  if (preserve && typeof settings.preserve_uploaded_performance === "boolean") preserve.checked = settings.preserve_uploaded_performance;
  setSelectValue("guitar-performance-mode", settings.guitar_performance_mode);
  setSelectValue("string-performance-mode", settings.string_performance_mode);
  const roll = $("guitar-roll-amount");
  if (roll && Number.isFinite(Number(settings.guitar_roll_amount))) {
    roll.value = String(settings.guitar_roll_amount);
    $("guitar-roll-amount-value").textContent = Number(roll.value).toFixed(1);
  }
  setSelectValue("bass-source", settings.bass_source);
  setSelectValue("bass-groove-mode", settings.bass_groove_mode);
  updateFoundationPatternControls();
  updateFoundationPerformanceMode();
  updateBassGrooveControls();
  setSelectValue("bass-groove-variant", settings.bass_groove_variant);
  updateGuitarPerformanceControls();
  setSelectValue("guitar-pattern-variant", settings.guitar_pattern_variant);
  // Instrument choice belongs only to the Sound Direction default. This keeps
  // the same Foundation/Bass pair while emotion, energy and rhythm are changed.
  if (hasDefaults) {
    setSelectValue("foundation-instrument", defaults.foundation);
    setSelectValue("bass-instrument", defaults.bass);
    updateGuitarPerformanceControls();
  } else {
    // Never carry a previous direction's manual instruments into a direction
    // that has not received its own defaults yet.
    setSelectValue("foundation-instrument", "");
    setSelectValue("bass-instrument", "");
    updateGuitarPerformanceControls();
  }
  if (showStatus) $("foundation-settings-status").textContent = hasDefaults ? "已载入当前音色的默认乐器，并载入当前标签的演奏细调。" : "当前音色尚未保存默认乐器，正在使用自动匹配。";
  return true;
}

function captureFoundationBassSettings() {
  return {
    foundation_performance_mode: $("foundation-performance-mode")?.value || "block",
    override_uploaded_performance: $("override-uploaded-performance")?.checked === true,
    foundation_pattern_source: $("foundation-pattern-source")?.value || "auto",
    foundation_uploaded_pattern_id: $("foundation-uploaded-pattern")?.value || "",
    preserve_uploaded_performance: $("preserve-uploaded-performance")?.checked !== false,
    guitar_performance_mode: $("guitar-performance-mode")?.value || "auto",
    guitar_pattern_variant: $("guitar-pattern-variant")?.value || "auto",
    guitar_roll_amount: Number($("guitar-roll-amount")?.value || 1),
    string_performance_mode: $("string-performance-mode")?.value || "auto",
    bass_source: $("bass-source")?.value || "groove_modes",
    bass_groove_mode: $("bass-groove-mode")?.value || "sustain_root",
    bass_groove_variant: $("bass-groove-variant")?.value || "auto"
  };
}

function saveFoundationSettings() {
  savedFoundationSettings.profiles[foundationBassProfileKey()] = captureFoundationBassSettings();
  const foundation = $("foundation-instrument")?.value || "";
  const bass = $("bass-instrument")?.value || "";
  if (foundation && bass) savedSoundInstrumentDefaults[selectedSound] = { foundation, bass };
  try {
    localStorage.setItem(foundationSettingsStorageKey, JSON.stringify(savedFoundationSettings));
    if (foundation && bass) localStorage.setItem(soundInstrumentDefaultsStorageKey, JSON.stringify(savedSoundInstrumentDefaults));
    $("foundation-settings-status").textContent = foundation && bass
      ? "已保存当前标签的演奏细调，并更新当前音色的默认 Foundation / Bass 乐器。"
      : "已保存当前标签的 Foundation / Bass 细调。";
  } catch (_) {
    $("foundation-settings-status").textContent = "当前浏览器无法保存此设置。";
  }
}

function saveSoundInstrumentDefaults() {
  const foundation = $("foundation-instrument")?.value || "";
  const bass = $("bass-instrument")?.value || "";
  if (!foundation || !bass) {
    $("sound-instrument-default-status").textContent = "请先分别选择 Foundation 和 Bass 乐器。";
    return;
  }
  savedSoundInstrumentDefaults[selectedSound] = { foundation, bass };
  try {
    localStorage.setItem(soundInstrumentDefaultsStorageKey, JSON.stringify(savedSoundInstrumentDefaults));
    const soundLabel = sounds.find((item) => item[1] === selectedSound)?.[0] || selectedSound;
    $("sound-instrument-default-status").textContent = `已保存“${soundLabel}”的默认 Foundation / Bass 乐器。`;
  } catch (_) {
    $("sound-instrument-default-status").textContent = "当前浏览器无法保存默认乐器。";
  }
}

if (isFilePreview) {
  $("sample-admin-link").href = "http://127.0.0.1:8766/admin/samples";
  $("instrument-admin-link").href = "http://127.0.0.1:8766/admin/instruments";
  $("sample-import-link").href = "http://127.0.0.1:8766/admin/sample-import";
  $("foundation-pattern-admin-link").href = "http://127.0.0.1:8766/admin/foundation-patterns";
  $("guitar-performance-admin-link").href = "http://127.0.0.1:8766/admin/guitar-performance-modes";
  $("string-performance-admin-link").href = "http://127.0.0.1:8766/admin/string-performance";
  $("bass-groove-admin-link").href = "http://127.0.0.1:8766/admin/bass-groove-modes";
  $("drum-pattern-admin-link").href = "http://127.0.0.1:8766/admin/drum-patterns";
}

const sampleJson = {
  state_id: "json_loop_demo",
  name: "欢快 · 流动 · Electronic · Groove",
  description: "",
  tags: [],
  ref_image_url: "",
  music_state: {
    emotion: { label: "欢快", value: 0.75 },
    energy: { label: "流动", value: 0.5 },
    sound_direction: { label: "电子", value: "electronic" },
    rhythm: { label: "律动", value: "groove" }
  },
  loop: {
    length_bars: 4,
    output_type: "audio_loop",
    midi_driven: true
  }
};

function renderChoices(containerId, items, selected, onPick) {
  const container = $(containerId);
  container.innerHTML = "";
  items.forEach(([label, value]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `choice ${value === selected ? "active" : ""}`;
    button.textContent = label;
    button.addEventListener("click", () => onPick(value));
    container.appendChild(button);
  });
}

function currentBars() {
  return Number(document.querySelector("input[name='bars']:checked").value);
}

function currentState() {
  if (inputMode === "json") return withRenderOptions(currentJsonState());
  const [emotionLabel, emotionValue] = emotionMap[selectedEmotion];
  const [energyLabel, energyValue] = energyMap[selectedEnergy];
  const soundLabel = sounds.find((item) => item[1] === selectedSound)[0];
  const rhythmLabel = rhythms.find((item) => item[1] === selectedRhythm)[0];
  return withRenderOptions({
    state_id: `loop_${Date.now()}`,
    name: $("loop-name").value.trim() || "Audio Loop",
    description: "",
    tags: [],
    ref_image_url: "",
    music_state: {
      emotion: { label: emotionLabel, value: emotionValue },
      energy: { label: energyLabel, value: energyValue },
      sound_direction: { label: soundLabel, value: selectedSound },
      rhythm: { label: rhythmLabel, value: selectedRhythm }
    },
    loop: {
      length_bars: currentBars(),
      output_type: "audio_loop",
      midi_driven: true
    }
  });
}

function withRenderOptions(state) {
  return {
    ...state,
    render_options: {
      solo_tracks: trackNames.filter((name) => trackControls[name].solo),
      muted_tracks: trackNames.filter((name) => trackControls[name].mute)
    },
    generation_settings: {
      instrument_overrides: {
        foundation: $("foundation-instrument")?.value || "",
        bass: $("bass-instrument")?.value || ""
      },
      mixer: mixerSettings,
      effects: effectsSettings,
      foundation_pattern_source: $("foundation-pattern-source")?.value || "auto",
      foundation_uploaded_pattern_id: $("foundation-uploaded-pattern")?.value || "",
      preserve_uploaded_performance: $("preserve-uploaded-performance")?.checked !== false,
      foundation_performance_mode: $("foundation-performance-mode")?.value || "block",
      override_uploaded_performance: $("override-uploaded-performance")?.checked === true,
      guitar_performance_mode: $("guitar-performance-mode")?.value || "auto",
      guitar_pattern_variant: $("guitar-pattern-variant")?.value || "auto",
      guitar_roll_amount: Number($("guitar-roll-amount")?.value || 1),
      string_performance_mode: $("string-performance-mode")?.value || "auto",
      bass_source: $("bass-source")?.value || "groove_modes",
      bass_groove_mode: $("bass-groove-mode")?.value || "sustain_root",
      bass_groove_variant: $("bass-groove-variant")?.value || "auto"
    }
  };
}

async function loadFoundationPatterns() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/foundation-patterns");
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Foundation 模板库加载失败");
    const select = $("foundation-uploaded-pattern");
    const current = activeFoundationBassSettings().foundation_uploaded_pattern_id || select.value;
    select.innerHTML = `<option value="">选择已上传模板</option>${(payload.patterns || []).filter((item) => item.enabled && Number(item.loop_length_bars) === currentBars()).map((item) => `<option value="${item.id}">${item.name} · ${item.loop_length_bars} 小节</option>`).join("")}`;
    if ([...select.options].some((option) => option.value === current)) select.value = current;
    restoreFoundationSettings();
  } catch (_) {
    // 模板库为空或暂不可用时，生成会使用当前 Foundation 演奏模式。
  }
}

function updateFoundationPatternControls() {
  const source = $("foundation-pattern-source")?.value || "auto";
  $("foundation-uploaded-wrap")?.classList.toggle("hidden", source !== "uploaded");
}

function updateFoundationPerformanceMode() {
  const descriptions = {
    auto: "自动根据音色方向、能量与节奏选择，并固定贯穿整个 Loop。",
    block: "稳定、长音、不抢戏。",
    broken: "清楚的上下声部交替，不会变成高速琶音。",
    pulse: "固定节拍重复，适合电子与混合电影感。",
    rhythm_chop: "短促切分，保留空拍。",
    arpeggio: "每小节均匀五连音，固定向上的合法和弦音序列。",
    octave_support: "低区八度支撑加中高区和弦。",
    wide_pad: "开放 Voicing、长音，适合氛围与电影。",
    cluster: "只使用当前和弦内音的紧密排列。"
  };
  const mode = $("foundation-performance-mode")?.value || "auto";
  $("foundation-performance-description").textContent = descriptions[mode] || descriptions.auto;
}

const bassVariants = {
  sustain_root: [["sustain_root_a", "长根音"], ["sustain_root_b", "前半长音"], ["sustain_root_c", "根音加引导"], ["sustain_root_d", "根音五度支撑"]],
  root_fifth: [["root_fifth_a", "根音五度"], ["root_fifth_b", "根音重复五度"], ["root_fifth_c", "根音五度引导"], ["root_fifth_d", "根音八度五度"]],
  pulse: [["pulse_a", "四分脉冲"], ["pulse_b", "八分脉冲"], ["pulse_c", "根音八度脉冲"], ["pulse_d", "稀疏混合脉冲"]],
  groove_pickup: [["groove_pickup_a", "基础律动"], ["groove_pickup_b", "切分根音五度"], ["groove_pickup_c", "引导律动"], ["groove_pickup_d", "八度律动"]],
  house_four_on_floor: [["house_four_on_floor_a", "四拍根音八度"]],
  "808_sync": [["808_sync_a", "808 切分 Pickup"]],
  ethnic_drone: [["ethnic_drone_a", "根音 Drone"]],
  middle_eastern_pulse: [["middle_eastern_pulse_a", "Darbuka 脉冲"]],
  cinematic_sub_sustain: [["cinematic_sub_sustain_a", "根音低频长音"]],
  cinematic_emotional_movement: [["cinematic_emotional_movement_a", "低频情绪推进"]]
};

function updateBassGrooveControls() {
  const source = $("bass-source")?.value || "groove_modes";
  const mode = $("bass-groove-mode")?.value || "sustain_root";
  const variant = $("bass-groove-variant");
  const previous = variant?.value || "auto";
  const modes = mode === "auto" ? Object.values(bassVariants).flat() : bassVariants[mode] || [];
  if (variant) {
    variant.innerHTML = `<option value="auto">自动</option>${modes.map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}`;
    if ([...variant.options].some((option) => option.value === previous)) variant.value = previous;
  }
  $("bass-groove-mode").disabled = source === "legacy_generator";
  variant.disabled = source === "legacy_generator";
  const descriptions = { sustain_root: "每小节以稳定根音长音为主。", root_fifth: "根音与五度做有限、自然的移动。", pulse: "固定脉冲，适合电子与高能状态。", groove_pickup: "在根音基础上加入少量律动过门。", house_four_on_floor: "电子 House 专用。根音、八度与五度锁定四拍 Kick。", "808_sync": "电子 Trap / EDM 专用。长音切分与下一和弦 Pickup；当前以普通 Pickup 代替 MIDI Glide。", ethnic_drone: "民族 Drone：长根音与少量五度回应，支撑 Oud、Nylon Guitar 与民族打击乐。", middle_eastern_pulse: "中东脉冲：根音重拍、五度回应，配合 Darbuka 与民族律动。", cinematic_sub_sustain: "电影低频持续：每小节随和弦换根音，以长音建立重量，不使用流行律动。", cinematic_emotional_movement: "电影情绪推进低音：缓慢跟随和声，用根音、八度和五度推动弦乐情绪。" };
  $("bass-groove-description").textContent = source === "legacy_generator" ? "使用旧 Bass 生成逻辑。" : (descriptions[mode] || "自动选择并锁定一个 Mode 和 Pattern Variant。Bar 4 只做有限收尾变化。");
}

async function loadInstrumentOverrides() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/instruments");
    const payload = await response.json();
    if (!response.ok || !payload.ok) return;
    availableInstruments = payload.instruments || [];
    ["foundation", "bass"].forEach((role) => {
      const select = $(`${role}-instrument`);
      const current = activeFoundationBassSettings().instrument_overrides?.[role] || select.value;
      const options = availableInstruments.filter((instrument) => instrument.enabled && instrument.track_role === role);
      select.innerHTML = `<option value="">自动匹配</option>${options.map((instrument) => `<option value="${instrument.id}">${instrument.name} · ${instrument.category}</option>`).join("")}`;
      if (options.some((instrument) => instrument.id === current)) select.value = current;
    });
    updateGuitarPerformanceControls();
    restoreFoundationSettings();
  } catch (_) {
    // 乐器库不可用时，生成仍会使用旧音源和内置合成音。
  }
}

async function loadGuitarPerformanceModes() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/guitar-performance-modes");
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "吉他模式加载失败");
    guitarPerformanceModes = (payload.modes || []).filter((mode) => mode.enabled !== false);
    const select = $("guitar-performance-mode");
    const selected = activeFoundationBassSettings().guitar_performance_mode || select.value;
    select.innerHTML = `<option value="auto">自动</option>${guitarPerformanceModes.map((mode) => `<option value="${mode.id}">${mode.label || mode.name}</option>`).join("")}`;
    if ([...select.options].some((option) => option.value === selected)) select.value = selected;
    updateGuitarPerformanceControls();
    restoreFoundationSettings();
  } catch (_) {
    guitarPerformanceModes = [];
  }
}

async function loadStringPerformanceModes() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/string-performance-modes");
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "弦乐模式加载失败");
    stringPerformanceModes = (payload.modes || []).filter((mode) => mode.enabled !== false);
    const select = $("string-performance-mode");
    const selected = activeFoundationBassSettings().string_performance_mode || select.value;
    select.innerHTML = `<option value="auto">自动</option>${stringPerformanceModes.map((mode) => `<option value="${mode.id}">${mode.label || mode.name}</option>`).join("")}`;
    if ([...select.options].some((option) => option.value === selected)) select.value = selected;
    updateGuitarPerformanceControls();
    restoreFoundationSettings();
  } catch (_) {
    stringPerformanceModes = [];
  }
}

function updateGuitarPerformanceControls() {
  const instrument = availableInstruments.find((item) => item.id === $("foundation-instrument")?.value);
  const isGuitar = instrument?.performance_engine === "guitar_single_note" && ["nylon", "electric"].includes(instrument?.guitar_type);
  const isString = ["strings", "ensemble_strings", "violin_section", "cello_section"].includes(instrument?.category);
  $("guitar-performance-select")?.classList.toggle("hidden", !isGuitar);
  $("string-performance-select")?.classList.toggle("hidden", !isString);
  $("foundation-template-select")?.classList.toggle("hidden", isGuitar || isString);
  $("foundation-performance-select")?.classList.toggle("hidden", isGuitar || isString);
  updateStringPerformanceControls(instrument);
  if (!isGuitar) return;
  const modeId = $("guitar-performance-mode")?.value || "auto";
  const mode = guitarPerformanceModes.find((item) => item.id === modeId);
  // Variant is meaningful only after a concrete mode is chosen. Auto lets the resolver lock both.
  const variants = mode?.variants || [];
  const variant = $("guitar-pattern-variant");
  const existing = variant?.value || activeFoundationBassSettings().guitar_pattern_variant || "auto";
  if (variant) {
    variant.innerHTML = `<option value="auto">自动</option>${variants.filter((item) => item.enabled !== false).map((item) => `<option value="${item.id}">${item.name || item.id}</option>`).join("")}`;
    if ([...variant.options].some((option) => option.value === existing)) variant.value = existing;
  }
  const typeName = instrument.guitar_type === "nylon" ? "Nylon Guitar" : "Electric Guitar";
  const description = mode ? `${typeName} · ${mode.label || mode.name}。整段 Loop 锁定同一模式与 Variant。` : `${typeName} 将使用自动吉他单音演奏。`;
  $("guitar-performance-description").textContent = description;
}

function updateStringPerformanceControls(instrument = availableInstruments.find((item) => item.id === $("foundation-instrument")?.value)) {
  if (!instrument || !["strings", "ensemble_strings", "violin_section", "cello_section"].includes(instrument.category)) return;
  const modeId = $("string-performance-mode")?.value || "auto";
  const mode = stringPerformanceModes.find((item) => item.id === modeId);
  const categoryNames = { strings: "弦乐", ensemble_strings: "弦乐合奏", violin_section: "小提琴组", cello_section: "大提琴组" };
  $("string-performance-description").textContent = mode
    ? `${categoryNames[instrument.category] || "弦乐"} · ${mode.label || mode.name}。整段 Loop 只使用长音和有限声部变化。`
    : `${categoryNames[instrument.category] || "弦乐"} 将根据当前情绪、能量与音色方向自动锁定弦乐模式。`;
}

function renderMixer() {
  const container = $("mixer-channels");
  if (!container) return;
  container.innerHTML = Object.entries(mixerSettings).map(([track, settings]) => `
    <div class="mixer-channel" data-mixer-track="${track}">
      <b>${track}</b>
      <label><span>增益 <output>${Number(settings.gain_db).toFixed(1)} dB</output></span><input data-mixer="gain_db" type="range" min="-24" max="6" step="0.5" value="${settings.gain_db}" /></label>
      <label><span>声像 <output>${Number(settings.pan).toFixed(1)}</output></span><input data-mixer="pan" type="range" min="-1" max="1" step="0.1" value="${settings.pan}" /></label>
    </div>
  `).join("");
  container.querySelectorAll("input[data-mixer]").forEach((input) => input.addEventListener("input", () => {
    const channel = input.closest("[data-mixer-track]");
    mixerSettings[channel.dataset.mixerTrack][input.dataset.mixer] = Number(input.value);
    channel.querySelector(`input[data-mixer='${input.dataset.mixer}']`).previousElementSibling.querySelector("output").textContent = input.dataset.mixer === "gain_db" ? `${Number(input.value).toFixed(1)} dB` : Number(input.value).toFixed(1);
    $("mixer-status").textContent = "有未保存的调音";
  }));
}

async function loadMixer() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/mixer");
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "调音台加载失败");
    mixerSettings = payload.mixer;
    $("mixer-status").textContent = "已载入保存的调音";
  } catch (error) {
    $("mixer-status").textContent = error.message;
  }
  renderMixer();
}

async function saveMixer() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/mixer/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mixer: mixerSettings }) });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "调音台保存失败");
    mixerSettings = payload.mixer;
    $("mixer-status").textContent = "调音已保存";
    renderMixer();
  } catch (error) {
    $("mixer-status").textContent = error.message;
  }
}

function effectCard(id, name, body) {
  const settings = effectsSettings[id];
  return `
    <div class="effect-channel" data-effect="${id}">
      <header><b>${name}</b><label class="switch"><input data-effect-enabled="${id}" type="checkbox" ${settings.enabled ? "checked" : ""} /> 启用</label></header>
      ${body}
    </div>
  `;
}

function renderEffects() {
  const container = $("effects-channels");
  if (!container) return;
  const delay = effectsSettings.delay;
  const reverb = effectsSettings.reverb;
  const filter = effectsSettings.filter;
  const sidechain = effectsSettings.sidechain;
  container.innerHTML = [
    effectCard("delay", "Delay", `
      <label><span>强度 <output>${Number(delay.mix).toFixed(2)}</output></span><input data-effect="delay" data-effect-key="mix" type="range" min="0" max="0.35" step="0.01" value="${delay.mix}" /></label>
      <label><span>间隔 <output>${Number(delay.beats).toFixed(2)} 拍</output></span><input data-effect="delay" data-effect-key="beats" type="range" min="0.25" max="1.5" step="0.05" value="${delay.beats}" /></label>
    `),
    effectCard("reverb", "Reverb", `
      <label><span>混合 <output>${Number(reverb.mix).toFixed(2)}</output></span><input data-effect="reverb" data-effect-key="mix" type="range" min="0" max="0.6" step="0.01" value="${reverb.mix}" /></label>
      <label><span>尾音 <output>${Number(reverb.decay).toFixed(2)}</output></span><input data-effect="reverb" data-effect-key="decay" type="range" min="0.1" max="0.9" step="0.05" value="${reverb.decay}" /></label>
    `),
    effectCard("filter", "Filter", `
      <label><span>类型</span><select data-effect="filter" data-effect-key="mode"><option value="lowpass" ${filter.mode === "lowpass" ? "selected" : ""}>低通</option><option value="highpass" ${filter.mode === "highpass" ? "selected" : ""}>高通</option><option value="bandpass" ${filter.mode === "bandpass" ? "selected" : ""}>带通</option><option value="telephone" ${filter.mode === "telephone" ? "selected" : ""}>电话声</option></select></label>
      <label><span>频率 <output>${Math.round(Number(filter.cutoff_hz))} Hz</output></span><input data-effect="filter" data-effect-key="cutoff_hz" type="range" min="250" max="18000" step="250" value="${filter.cutoff_hz}" /></label>
    `),
    effectCard("sidechain", "Sidechain", `
      <label><span>深度 <output>${Number(sidechain.amount).toFixed(2)}</output></span><input data-effect="sidechain" data-effect-key="amount" type="range" min="0" max="0.9" step="0.01" value="${sidechain.amount}" /></label>
      <label><span>释放 <output>${Math.round(Number(sidechain.release_ms))} ms</output></span><input data-effect="sidechain" data-effect-key="release_ms" type="range" min="30" max="800" step="10" value="${sidechain.release_ms}" /></label>
    `)
  ].join("");
  container.querySelectorAll("input[data-effect-enabled]").forEach((input) => input.addEventListener("change", () => {
    effectsSettings[input.dataset.effectEnabled].enabled = input.checked;
    $("effects-status").textContent = "有未保存的效果";
  }));
  container.querySelectorAll("[data-effect][data-effect-key]").forEach((input) => input.addEventListener("input", () => {
    const effect = effectsSettings[input.dataset.effect];
    effect[input.dataset.effectKey] = input.tagName === "SELECT" ? input.value : Number(input.value);
    const output = input.closest("label")?.querySelector("output");
    if (output) {
      const key = input.dataset.effectKey;
      output.textContent = key === "cutoff_hz" ? `${Math.round(Number(input.value))} Hz` : key === "release_ms" ? `${Math.round(Number(input.value))} ms` : key === "beats" ? `${Number(input.value).toFixed(2)} 拍` : Number(input.value).toFixed(2);
    }
    $("effects-status").textContent = "有未保存的效果";
  }));
}

async function loadEffects() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/effects");
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "效果加载失败");
    effectsSettings = payload.effects;
    $("effects-status").textContent = "已载入保存的效果";
  } catch (error) {
    $("effects-status").textContent = error.message;
  }
  renderEffects();
}

async function saveEffects() {
  if (isFilePreview) return;
  try {
    const response = await fetch("/api/effects/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ effects: effectsSettings }) });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "效果保存失败");
    effectsSettings = payload.effects;
    $("effects-status").textContent = "效果已保存";
    renderEffects();
  } catch (error) {
    $("effects-status").textContent = error.message;
  }
}

function currentJsonState() {
  try {
    return JSON.parse($("json-input").value);
  } catch (error) {
    throw new Error(`JSON 格式错误：${error.message}`);
  }
}

function setJsonFromControls() {
  const previousMode = inputMode;
  inputMode = "controls";
  const state = currentState();
  delete state.render_options;
  $("json-input").value = JSON.stringify(state, null, 2);
  inputMode = previousMode;
}

function updateLocalLabels() {
  const state = currentState();
  $("emotion-label").textContent = state.music_state.emotion.label;
  $("energy-label").textContent = state.music_state.energy.label;
  $("bars").textContent = state.loop.length_bars;
}

function renderResult(result) {
  lastResult = result;
  const resolved = result.resolved.resolver;
  const drumRule = result.resolved.music_rules?.drum_rule || {};
  const sampleOverlays = sampleTrackEnabled() ? result.resolved.audio_render?.sample_overlays || [] : [];
  const instrumentManifest = result.resolved.audio_render?.instruments || {};
  const foundationPerformance = result.resolved.foundation_performance || {};
  const guitarPerformance = result.resolved.guitar_performance || {};
  const stringPerformance = result.resolved.string_performance || {};
  const bassGroove = result.resolved.bass_groove || {};
  renderChordProgression(result.resolved.music_rules || result.resolved);
  $("bpm").textContent = resolved.energy.bpm;
  $("key").textContent = resolved.emotion.key;
  $("bars").textContent = result.resolved.loop.length_bars;
  $("tracks").innerHTML = [
    ["Foundation", guitarPerformance.enabled ? `${guitarPerformance.mode_name} · ${guitarPerformance.variant_name} · ${guitarPerformance.guitar_type === "nylon" ? "Nylon Guitar" : "Electric Guitar"}` : stringPerformance.enabled ? `${stringPerformance.mode_name} · 弦乐长音 / 声部连接` : foundationPerformance.source === "uploaded_midi" ? `${foundationPerformance.pattern_name} · 录制 MIDI 模板` : foundationPerformance.pattern_name ? `${foundationPerformance.pattern_name} · ${foundationPerformance.bar_4_strategy}` : instrumentManifest.Foundation?.instrument_name || resolved.sound_direction.foundation],
    ["Bass", `${bassGroove.mode_name || "Groove Modes"}${bassGroove.variant_name ? ` · ${bassGroove.variant_name}` : ""} · ${instrumentManifest.Bass?.instrument_name || resolved.sound_direction.bass}`],
    ["Drums", drumRule.pattern_name ? `${drumRule.pattern_name} · ${drumRule.effective_event_count ?? drumRule.event_count ?? 0} 个鼓点` : resolved.sound_direction.drums],
    ["Sample", sampleTrackLabel(sampleOverlays)]
  ]
    .map(([name, sound]) => trackMarkup(name, sound))
    .join("");
  renderSampleOverlays(sampleOverlays);
  bindTrackButtons();
  $("json-output").textContent = JSON.stringify(activeTab === "resolved" ? result.resolved : result.input_json, null, 2);
}

function sampleTrackEnabled() {
  const soloTracks = trackNames.filter((name) => trackControls[name].solo);
  if (soloTracks.length) return soloTracks.includes("Sample");
  return !trackControls.Sample?.mute;
}

function renderChordProgression(resolved) {
  const progression = resolved?.chord_progression || [];
  const container = $("chord-progression");
  const source = $("harmony-source");
  if (!container || !source) return;
  source.textContent = resolved?.harmony_source === "manual_admin" ? "和弦后台规则" : "默认规则";
  container.innerHTML = progression.length
    ? progression.map((chord, index) => `<span class="chord-chip"><small>Bar ${index + 1}</small><b>${chord}</b></span>`).join("")
    : `<span class="chord-empty">暂无和弦进行</span>`;
}

async function previewResolvedHarmony() {
  const container = $("chord-progression");
  const source = $("harmony-source");
  if (!container || !source) return;
  if (isFilePreview) {
    source.textContent = "服务模式下解析";
    container.innerHTML = `<span class="chord-empty">请打开 http://127.0.0.1:8766/ 查看和弦进行</span>`;
    return;
  }
  const requestId = ++resolveRequestId;
  source.textContent = "解析中";
  container.innerHTML = `<span class="chord-empty">正在读取当前标签</span>`;
  try {
    const response = await fetch("/api/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(withRenderOptions(currentState()))
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "和弦解析失败");
    if (requestId === resolveRequestId) {
      const resolved = payload.resolved.music_rules || payload.resolved;
      const overlays = sampleTrackEnabled() ? payload.resolved.audio_render?.sample_overlays || [] : [];
      renderChordProgression(resolved);
      renderSampleOverlays(overlays);
      const performance = payload.resolved.foundation_performance;
      if (performance) $("foundation-performance-description").textContent = performance.reason;
      const guitar = payload.resolved.guitar_performance;
      if (guitar?.enabled) $("guitar-performance-description").textContent = `${guitar.mode_name} · ${guitar.variant_name}，整段 Loop 已锁定。`;
      const strings = payload.resolved.string_performance;
      if (strings?.enabled) $("string-performance-description").textContent = `${strings.mode_name}，整段 Loop 已锁定长音与声部连接。`;
      const sampleTrackText = document.querySelector('[data-track="Sample"] > span');
      if (sampleTrackText) sampleTrackText.textContent = sampleTrackLabel(overlays);
    }
  } catch (error) {
    if (requestId === resolveRequestId) {
      source.textContent = "解析失败";
      container.innerHTML = `<span class="chord-empty">${error.message}</span>`;
    }
  }
}

function renderSampleOverlays(overlays) {
  const container = $("sample-overlays");
  if (!container) return;
  if (!overlays.length) {
    container.innerHTML = `
      <div class="sample-overlay-empty">
        <b>Sample</b>
        <span>本次没有命中 Sample</span>
      </div>
    `;
    return;
  }
  container.innerHTML = overlays
    .map((overlay) => `
      <article class="sample-overlay">
        <div>
          <b>Sample · ${overlay.name || overlay.sample_id}</b>
          <span>Sample 直接播放 · ${overlay.playback_type}</span>
        </div>
        <span>${overlay.trigger_mode} · Bar ${overlay.bar} Step ${overlay.step}</span>
      </article>
    `)
    .join("");
}

function trackMarkup(name, sound) {
  const displayName = name;
  const soloActive = trackControls[name].solo ? "active" : "";
  const muteActive = trackControls[name].mute ? "active" : "";
  return `
    <article class="track" data-track="${name}">
      <div class="track-head">
        <b>${displayName}</b>
        <div class="track-tools">
          <button type="button" class="track-toggle solo ${soloActive}" data-action="solo" data-track="${name}" title="${displayName} Solo" aria-label="${displayName} Solo">S</button>
          <button type="button" class="track-toggle mute ${muteActive}" data-action="mute" data-track="${name}" title="${displayName} Mute" aria-label="${displayName} Mute">M</button>
        </div>
      </div>
      <span>${sound}</span>
    </article>
  `;
}

function bindTrackButtons() {
  document.querySelectorAll(".track-toggle").forEach((button) => {
    button.addEventListener("click", async () => {
      const track = button.dataset.track;
      const action = button.dataset.action;
      if (!trackControls[track]) return;
      if (action === "solo") {
        trackControls[track].solo = !trackControls[track].solo;
        if (trackControls[track].solo) trackControls[track].mute = false;
      }
      if (action === "mute") {
        trackControls[track].mute = !trackControls[track].mute;
        if (trackControls[track].mute) trackControls[track].solo = false;
      }
      if (lastResult) {
        await generate();
      } else {
        renderTrackControlState();
        $("json-output").textContent = JSON.stringify(currentState(), null, 2);
      }
    });
  });
}

function renderTrackControlState() {
  document.querySelectorAll(".track-toggle").forEach((button) => {
    const track = button.dataset.track;
    const action = button.dataset.action;
    button.classList.toggle("active", Boolean(trackControls[track]?.[action]));
  });
}

async function generate() {
  if (isFilePreview) {
    $("status").textContent = "预览模式：生成音频请打开 http://127.0.0.1:8766/";
    renderPreviewState();
    return;
  }
  $("status").textContent = "生成中";
  $("generate").disabled = true;
  try {
    const requestBody = currentState();
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody)
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "生成失败");
    renderResult(payload);
    const midiDownload = $("download");
    const cacheKey = Date.now();
    midiDownload.href = `${payload.midi_url}?t=${cacheKey}`;
    midiDownload.classList.remove("disabled");
    const mp3Download = $("download-mp3");
    if (payload.mp3_url) {
      mp3Download.href = `${payload.mp3_url}?t=${cacheKey}`;
      mp3Download.classList.remove("disabled");
    } else {
      mp3Download.href = "#";
      mp3Download.classList.add("disabled");
    }
    const wavDownload = $("download-wav");
    wavDownload.href = `${payload.wav_url}?t=${cacheKey}`;
    wavDownload.classList.remove("disabled");
    const player = $("player");
    player.src = `${payload.audio_url || payload.mp3_url || payload.wav_url}?t=${cacheKey}`;
    player.load();
    $("status").textContent = payload.audio_warning ? `已生成 WAV · ${payload.audio_warning}` : "已生成";
  } catch (error) {
    $("status").textContent = error.message;
  } finally {
    $("generate").disabled = false;
  }
}

function renderPreviewState() {
  const state = currentState();
  $("bpm").textContent = "—";
  $("key").textContent = "—";
  $("bars").textContent = state.loop.length_bars;
  $("tracks").innerHTML = [
    ...midiTrackNames.map((name) => trackMarkup(name, "预览")),
    trackMarkup("Sample", "Sample 叠加")
  ].join("");
  renderSampleOverlays([]);
  bindTrackButtons();
  $("json-output").textContent = JSON.stringify(state, null, 2);
  previewResolvedHarmony();
}

function sampleTrackLabel(overlays) {
  if (!overlays.length) return "本次没有命中 Sample";
  return `${overlays.length} 个 Sample`;
}

function randomize() {
  const emotionValues = Object.keys(emotionMap).filter((value) => value !== "0");
  const energyValues = Object.keys(energyMap);
  selectedEmotion = emotionValues[Math.floor(Math.random() * emotionValues.length)];
  selectedEnergy = energyValues[Math.floor(Math.random() * energyValues.length)];
  selectedSound = sounds[Math.floor(Math.random() * sounds.length)][1];
  selectedRhythm = rhythms[Math.floor(Math.random() * rhythms.length)][1];
  document.querySelector(`input[name='bars'][value='${Math.random() > 0.6 ? 8 : 4}']`).checked = true;
  renderControls();
  restoreFoundationSettings(true);
  loadFoundationPatterns();
  setJsonFromControls();
  previewResolvedHarmony();
}

function applyFoundationBassProfileForTags() {
  restoreFoundationSettings(true);
  loadFoundationPatterns();
}

function renderControls() {
  renderChoices("emotion-options", emotions, selectedEmotion, (value) => {
    selectedEmotion = value;
    renderControls();
    applyFoundationBassProfileForTags();
    previewResolvedHarmony();
  });
  renderChoices("energy-options", energies, selectedEnergy, (value) => {
    selectedEnergy = value;
    renderControls();
    applyFoundationBassProfileForTags();
    previewResolvedHarmony();
  });
  renderChoices("sound-options", sounds, selectedSound, (value) => {
    selectedSound = value;
    renderControls();
    applyFoundationBassProfileForTags();
    previewResolvedHarmony();
  });
  renderChoices("rhythm-options", rhythms, selectedRhythm, (value) => {
    selectedRhythm = value;
    renderControls();
    applyFoundationBassProfileForTags();
    previewResolvedHarmony();
  });
  updateLocalLabels();
}

function setMode(mode) {
  inputMode = mode;
  document.querySelectorAll(".mode").forEach((button) => button.classList.toggle("active", button.dataset.mode === mode));
  $("control-entry").classList.toggle("hidden", mode !== "controls");
  $("json-entry").classList.toggle("hidden", mode !== "json");
  if (mode === "json") setJsonFromControls();
}

function valueKeyFromState(map, value, label, fallback) {
  const entries = Object.entries(map).filter(([key]) => key !== "0");
  if (label) {
    const labelMatch = entries.find(([, item]) => item[0] === label);
    if (labelMatch) return labelMatch[0];
  }
  if (value !== undefined && value !== null) {
    const valueMatch = entries.find(([, item]) => Number(item[1]) === Number(value));
    if (valueMatch) return valueMatch[0];
  }
  return fallback;
}

function applyJsonToControls() {
  const data = currentJsonState();
  const musicState = data.music_state || {};
  const emotion = musicState.emotion || {};
  const energy = musicState.energy || {};
  const sound = musicState.sound_direction || {};
  const rhythm = musicState.rhythm || {};
  const loop = data.loop || {};
  $("loop-name").value = data.name || data.state_id || "Audio Loop";
  selectedEmotion = valueKeyFromState(emotionMap, emotion.value ?? data.emotion, emotion.label, "0.75");
  selectedEnergy = valueKeyFromState(energyMap, energy.value ?? data.energy, energy.label, "0.5");
  selectedSound = sound.value || data.sound_direction || selectedSound;
  selectedRhythm = rhythm.value || data.rhythm || selectedRhythm;
  document.querySelector(`input[name='bars'][value='${Number(loop.length_bars || data.loop_length || 4) >= 8 ? 8 : 4}']`).checked = true;
  renderControls();
  applyFoundationBassProfileForTags();
  previewResolvedHarmony();
  $("status").textContent = "已套用";
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    activeTab = button.dataset.tab;
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab === button));
    if (lastResult) renderResult(lastResult);
  });
});

document.querySelectorAll(".mode").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});
document.querySelectorAll("input[name='bars']").forEach((input) => input.addEventListener("change", () => {
  updateLocalLabels();
  restoreFoundationSettings(true);
  loadFoundationPatterns();
  previewResolvedHarmony();
}));
$("generate").addEventListener("click", generate);
$("save-mixer").addEventListener("click", saveMixer);
$("save-effects").addEventListener("click", saveEffects);
$("randomize").addEventListener("click", randomize);
$("load-sample").addEventListener("click", () => {
  $("json-input").value = JSON.stringify(sampleJson, null, 2);
  $("status").textContent = "已载入示例";
  if (inputMode === "json") {
    try {
      previewResolvedHarmony();
    } catch (error) {
      $("status").textContent = error.message;
    }
  }
});
$("apply-json").addEventListener("click", () => {
  try {
    applyJsonToControls();
  } catch (error) {
    $("status").textContent = error.message;
  }
});
$("foundation-pattern-source")?.addEventListener("change", updateFoundationPatternControls);
$("foundation-performance-mode")?.addEventListener("change", updateFoundationPerformanceMode);
$("foundation-instrument")?.addEventListener("change", () => { updateGuitarPerformanceControls(); previewResolvedHarmony(); });
$("guitar-performance-mode")?.addEventListener("change", () => { updateGuitarPerformanceControls(); previewResolvedHarmony(); });
$("string-performance-mode")?.addEventListener("change", () => { updateStringPerformanceControls(); previewResolvedHarmony(); });
$("guitar-pattern-variant")?.addEventListener("change", previewResolvedHarmony);
$("guitar-roll-amount")?.addEventListener("input", () => { $("guitar-roll-amount-value").textContent = Number($("guitar-roll-amount").value).toFixed(1); });
$("guitar-roll-amount")?.addEventListener("change", previewResolvedHarmony);
$("bass-source")?.addEventListener("change", updateBassGrooveControls);
$("bass-groove-mode")?.addEventListener("change", updateBassGrooveControls);
$("save-foundation-settings")?.addEventListener("click", saveFoundationSettings);
$("save-sound-instrument-default")?.addEventListener("click", saveSoundInstrumentDefaults);

restoreFoundationSettings();
renderControls();
renderMixer();
renderEffects();
updateFoundationPatternControls();
updateFoundationPerformanceMode();
updateBassGrooveControls();
$("json-input").value = JSON.stringify(sampleJson, null, 2);
loadInstrumentOverrides();
loadGuitarPerformanceModes();
loadStringPerformanceModes();
loadFoundationPatterns();
loadMixer();
loadEffects();
if (isFilePreview) {
  renderPreviewState();
  $("status").textContent = "预览模式：生成音频请打开 http://127.0.0.1:8766/";
} else {
  renderPreviewState();
  $("status").textContent = "可直接查看和弦，生成 MIDI 后可试听";
}
