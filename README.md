# Visual Audio Loop Generator

本项目是一个本地运行的 Visual Audio Loop Generator。它读取一份已完成 `music_state` 标注的图片 JSON，实时解析音乐规则，生成 4 或 8 小节可循环的 MIDI，并使用本地音源、乐器库和采样渲染为可播放的 WAV / MP3。

系统的最终产物是 **Audio Loop**；MIDI 只作为内部驱动层。项目不调用在线音乐生成模型，不依赖固定 MIDI 素材，和弦、Foundation、Bass、鼓点和采样触发都由规则与后台保存的配置决定。

## 目录

- [快速开始](#快速开始)
- [核心流程](#核心流程)
- [主控制台](#主控制台)
- [标准输入 JSON](#标准输入-json)
- [音乐规则与轨道](#音乐规则与轨道)
- [后台页面](#后台页面)
- [音源、乐器与采样导入](#音源乐器与采样导入)
- [保存与命中逻辑](#保存与命中逻辑)
- [输出、接口与数据目录](#输出接口与数据目录)
- [测试与常见问题](#测试与常见问题)

## 快速开始

### 运行环境

- Python 3.9 或更高版本。
- 项目核心只使用 Python 标准库，无需安装 npm 依赖。
- MP3 导出在 macOS 上会调用系统 `afconvert`；无法编码 MP3 时，仍会输出可播放的 WAV，并在接口返回提示中说明原因。
- 可上传的音频与采样导入格式：WAV、AIFF / AIF、FLAC；直接采样也支持浏览器可播放的常见音频格式。

### 启动网页

在项目根目录执行：

```bash
python3 -B -m auto_loop_midi_generator --serve --port 8766
```

然后打开 [http://127.0.0.1:8766/](http://127.0.0.1:8766/)。

也可以双击根目录的 `启动音乐引擎.command`。网页后台必须通过本地服务打开；不要直接使用 `file://` 打开 HTML 文件，否则上传、保存和 API 请求不会工作。

### 命令行批量生成 MIDI

```bash
python3 -B -m auto_loop_midi_generator examples/annotations.json -o output_midi
```

输入可以是单个 JSON 文件，也可以是包含多个 JSON 文件的目录。命令行批量模式只输出 MIDI；网页模式会生成 MIDI、WAV，并在可用时生成 MP3。

### 运行测试

```bash
python3 -B -m unittest discover -s tests -q
```

## 核心流程

```text
标注图片 JSON
  -> music_state
  -> Resolver
  -> Harmony / Performance / Drum Pattern / Instrument Matcher
  -> Foundation + Bass + Drums MIDI
  -> 本地乐器音源 + 直接采样 + 调音台 / 效果
  -> WAV / MP3 Audio Loop
```

默认音乐基础设置：

| 项目 | 数值 |
| --- | --- |
| 拍号 | 4/4 |
| 默认 Loop 长度 | 4 小节 |
| 可选 Loop 长度 | 8 小节 |
| PPQ | 480 |
| 鼓机网格 | 每小节 16 Step |
| MIDI 轨道 | Foundation、Bass、Drums |

`Accent` 与 `Accompaniment` 已移除。直接播放的音频采样在渲染阶段作为独立 `Sample` 轨叠加，不属于 MIDI 轨。

## 主控制台

主页面：[http://127.0.0.1:8766/](http://127.0.0.1:8766/)

主控制台支持两种输入方式：

1. 点击选择情绪、能量、音色方向、节奏和 4 / 8 小节。
2. 切换至 JSON 输入，将完整标注 JSON 粘贴进去并读取。

选择任何标签后，控制台会立即请求 Resolver 并展示当前和弦进行、BPM、调性、命中的鼓型、音源、采样和演奏模式，无需先生成 MIDI。点击生成后，系统才写入 MIDI 与音频文件并更新播放器。

主控制台还提供：

- Foundation 与 Bass 乐器选择。
- Foundation、吉他、弦乐与 Bass 律动模式选择。
- Foundation / Bass 组合保存：可保存为当前四标签配置，也可保存为当前音色方向的默认乐器选择。
- 四个声部的调音台：Foundation、Bass、Drums、Sample 均可独立调节增益和声像并保存。
- 效果控制：Delay、Reverb、Filter、Sidechain 默认关闭，可自行开启并保存。
- Solo / Mute：Foundation、Bass、Drums、Sample 都有独立 Solo 和 Mute。重新生成后只渲染未静音、或当前 Solo 的轨道。
- WAV、MP3、MIDI 下载。

## 标准输入 JSON

输入结构只保存图像状态与四个音乐标签。BPM、和弦、Bass、MIDI、音源、FX 都不写回输入 JSON，由 Resolver、后台数据和当前生成设置决定。

```json
{
  "state_id": "6a48e1f065d4cdde57f3d172",
  "name": "欢快 · 流动 · Electronic · Groove",
  "description": "",
  "tags": [],
  "ref_image_url": "image_url",
  "music_state": {
    "emotion": {
      "label": "欢快",
      "value": 0.75
    },
    "energy": {
      "label": "流动",
      "value": 0.5
    },
    "sound_direction": {
      "label": "电子",
      "value": "electronic"
    },
    "rhythm": {
      "label": "律动",
      "value": "groove"
    }
  },
  "loop": {
    "length_bars": 4,
    "output_type": "audio_loop",
    "midi_driven": true
  }
}
```

### 字段规则

`value` 是 Resolver 的实际判断值；`label` 用于显示。粘贴 JSON 时，请保持两者一致。例如 `energy.value: 0` 就是静止，不能只把显示文字改成“静止”而保留 `0.5`。

| 字段 | 可用值 |
| --- | --- |
| `emotion.value` | `-1` 深沉、`-0.75` 阴郁、`-0.5` 忧伤、`-0.25` 平静、`0.25` 温暖、`0.5` 明亮、`0.75` 欢快、`1` 激昂 |
| `energy.value` | `0` 静止、`0.5` 流动、`1` 高能 |
| `sound_direction.value` | `ambient`、`acoustic`、`organic`、`vintage`、`electronic`、`ethnic`、`cinematic` |
| `rhythm.value` | `sparse`、`flow`、`standard`、`groove`、`aggressive` |
| `loop.length_bars` | `4` 或 `8`；其他值会归一为最近的 4 或 8 小节逻辑 |
| `loop.output_type` | 固定使用 `audio_loop` |
| `loop.midi_driven` | 固定使用 `true` |

8 小节模式会复制前 4 小节的核心和声与 Bass 结构，以确保 Loop 结构稳定。

## 音乐规则与轨道

### Resolver

Resolver 根据 `emotion + energy + sound_direction + rhythm + length_bars` 输出：

- BPM、调性与大小调倾向。
- 和弦进行、和声复杂度、Voicing 风格。
- Foundation、Bass、Drums 的规则与演奏配置。
- 音频渲染配置、命中的音源、直接采样与鼓型。

人工和弦规则命中时，会覆盖默认 `Emotion x Sound Direction` 和声表。音色方向会影响和声语言，但当前情绪也有固定的基础进行，因此切换音色不会把已保存的手动和弦规则改掉。

### Foundation

Foundation 负责和弦铺底。普通 Foundation 会在无根音 Voicing、转位和声部连接之间选择，默认以柱式和弦为主。

| 类型 | 可用模式 |
| --- | --- |
| 通用 Foundation | 柱式和弦、分解和弦、和弦脉冲、节奏切分、五连音琶音、八度支撑、宽音域铺底、音簇和弦 |
| Nylon / Electric Guitar | 留白扫弦回应、留白渐强扫弦、留白向下扫弦、留白开放扫弦 |
| Ethnic Nylon Guitar | 乌德琴式拨弦、沙漠脉冲；支持 `roll_up` 与 `roll_down` |
| Strings | 弦乐长音铺陈、弦乐情绪推进 |

弦乐长音会在每个和弦变化时重新配音并保留微小 Legato 重叠，不会持续旧和弦到下一小节。弦乐情绪推进优先保持共同音，减少大跳。

上传的 Foundation MIDI 模板也可被选择。模板会依照已保存的原始 MIDI 音域播放，不自动上移八度。

### Bass

Bass 跟随当前和弦的低音根音，不属于节奏层。每个 Loop 会锁定一种 Bass 模式和一个 Variant。

| 类别 | 模式 |
| --- | --- |
| 基础 | 长音根音、根音五度、脉冲低音、律动过门 |
| Electronic | House 四拍低音、808 切分低音 |
| Ethnic | 民族持续低音、中东脉冲低音 |
| Cinematic | 电影低频持续、电影情绪推进低音 |

Electronic Bass 的 MIDI 音域会整体提高一个八度。House 模式只使用根音、八度和五度以锁定四拍 Kick；808 模式使用长音与 Pickup，不进入传统 Walking Bass。Ethnic 模式不使用七音、半音经过或快速行进。

电影 Bass 与弦乐 Foundation 有明确联动：

| Foundation | 自动 Bass |
| --- | --- |
| 弦乐长音铺陈 | 电影低频持续 |
| 弦乐情绪推进 | 电影情绪推进低音 |

`电影低频持续` 每小节按当前和弦换根音，保持长音重量；`电影情绪推进低音` 只缓慢使用根音、八度与五度，不使用流行切分或 Funk 走向。

### Drums

Drums 包含 Kick、Snare、Closed Hat、Open Hat、Percussion、Tom、Crash、Ride 和 Fill。鼓点后台命中的 Pattern 优先于默认节奏规则。若没有命中后台 Pattern，才使用 `rhythm + energy` 的基础鼓点。

鼓轨渲染不自动添加 Delay 或 Reverb；所有效果由主控制台的效果开关决定，且默认关闭。

## 后台页面

所有后台都从主控制台顶部进入，也可以直接打开下面的地址。

| 页面 | 地址 | 用途 |
| --- | --- | --- |
| 音源 / 采样后台 | [打开](http://127.0.0.1:8766/admin/samples) | 管理 MIDI 音源与直接叠加采样 |
| 乐器库 | [打开](http://127.0.0.1:8766/admin/instruments) | 管理 Foundation、Bass 多采样乐器和 Zone |
| 采样导入中心 | [打开](http://127.0.0.1:8766/admin/sample-import) | 单 WAV、SFZ、MappingChart、VSCO2 导入 |
| Foundation 模板库 | [打开](http://127.0.0.1:8766/admin/foundation-patterns) | 上传、分析、匹配 Foundation MIDI 模板 |
| 和弦编辑 | [打开](http://127.0.0.1:8766/admin/harmony) | 编辑各标签组合的和弦与实际音符 |
| Foundation 演奏模式 | [打开](http://127.0.0.1:8766/admin/foundation-performance-modes) | 编辑通用 Foundation 模式 |
| 吉他演奏模式 | [打开](http://127.0.0.1:8766/admin/guitar-performance-modes) | 编辑吉他扫弦、拨弦与民族模式 |
| 弦乐演奏模式 | [打开](http://127.0.0.1:8766/admin/string-performance) | 编辑弦乐长音与声部推进 |
| Bass 律动模式 | [打开](http://127.0.0.1:8766/admin/bass-groove-modes) | 编辑基础、电子、民族、电影 Bass 模式 |
| 鼓点后台 | [打开](http://127.0.0.1:8766/admin/drum-patterns) | 编辑 Step Sequencer 与鼓点事件 |

### 和弦编辑

和弦规则按以下组合保存与匹配：

```text
情绪 + 音色方向 + 4/8 小节
```

每个 Bar 都可填写和弦标记，并在 C2 到 C5 的音区选择实际使用的音。已定义的和弦会保存“和弦名 + 所选音符”；试听以从低到高的顺序播放。某个 Bar 清空时，会沿用前一个有效和弦。

### 鼓点后台

- 点击空网格添加事件；再次点击已有方块删除事件。
- 每条轨道有试听、Mute、Solo 和暂停控制；页面提供总播放。
- 每个事件支持 Bar、Step、细分、力度、概率、微时值、时长、启用状态。
- 修改 Bar 1 的事件时，Bar 2 到 Bar 4 会实时同步同一位置的新增、删除和参数；其他 Bar 中独立编辑的位置保留。
- 保存后的事件是前端鼓轨唯一来源，前端不会再次自动补点或重新编排。

### Foundation / 吉他 / 弦乐 / Bass 模式后台

这些后台会保存模式定义、标签适用范围、力度、时值、概率、Priority 与启用状态。保存后，下次生成会直接使用新配置。

- 吉他模式支持单音、和弦堆叠、上扫与下扫，Nylon 吉他在民族方向优先使用乌德琴式拨弦或沙漠脉冲。
- 弦乐后台支持长音、持续、力度、Voice Leading、情绪 / 能量 / 音色方向条件。
- Bass 后台分组显示 Electronic Bass、民族 Bass、电影 Bass。电影 Bass 可编辑持续、和声跟随和允许情绪。

## 音源、乐器与采样导入

### MIDI 音源与直接采样的区别

| 类型 | 工作方式 | 用途 |
| --- | --- | --- |
| MIDI 音源 | MIDI 音符触发音源 / 单采样 | Foundation、Bass、鼓件槽位 |
| 多采样乐器 | 按 MIDI 音高与 Zone 音域选择采样 | Foundation、Bass 的真实乐器 |
| 直接采样 | 不依赖 MIDI，按设置直接叠加到最终音频 | Texture、Vocal、FX、One-shot、音频 Loop |

不要把直接采样当作 MIDI 音源使用。前者没有音高跟随；后者根据 MIDI 音符和 Zone 映射播放。

### 乐器库

乐器库的每件乐器包含：

```json
{
  "id": "instrument_id",
  "name": "Instrument Name",
  "source_library": "source name",
  "track_role": "foundation",
  "category": "Strings",
  "sample_zones": []
}
```

每个 Zone 记录采样文件、根音、最低音、最高音、增益、声像及可选的力度范围。上传文件名含 `C3`、`F#2` 等音名时，系统会自动识别根音。单个 C2 Zone 的相邻初始范围可按 B1 到 C#2 的逻辑调整，再由你在后台精确修改。

乐器自动匹配依次比较标签命中数、Priority 和稳定 Seed，因此同一 JSON 多次生成会得到稳定结果。没有可用 Zone 时，Foundation 与 Bass 会回退到旧音源或内置合成声音。

### 采样导入中心

支持四种导入：

1. **单个 WAV**：创建一件带单个 Zone 的乐器。
2. **SFZ 乐器**：上传 `.sfz` 与其引用的 WAV / AIFF / FLAC，解析 `sample=`、音高和力度范围。
3. **MappingChart**：选择含 `MappingChart.txt` 和采样文件的完整文件夹，解析音高、Velocity Layer、Round Robin 和 Zone。
4. **VSCO2 音源库**：选择整个 VSCO2 文件夹，递归索引 `.sfz`、`.wav`、`.aiff`、`.flac`，解析每个 SFZ 为独立乐器候选。

VSCO 导入流程是：上传文件夹 -> 分析 SFZ -> 在 Step 2 单独选择一个乐器 -> 在 Step 3 为该乐器指定名称、轨道、分类和来源信息 -> 创建乐器。不会把 75 个 SFZ 打包成一件乐器，也不会默认全部选中。创建完成后，仍可在乐器库单独修改名称、轨道、分类、标签、优先级和启用状态。

### 标签命中

音源、乐器、直接采样和鼓型都使用以下标签维度：

```text
情绪 + 能量 + 音色方向 + 节奏
```

保存时请确保标签使用与主控制台一致的值。某个采样只标记 `ambient` 时，不会在 `acoustic` 状态命中；若出现跨方向命中，请在后台检查该条目的音色方向标签是否包含“任意”或额外方向。

直接采样可设置插入 Bar、Step、概率、增益、声像、淡入淡出和触发方式。主控制台的 Sample Solo / Mute 会对它们生效。

## 保存与命中逻辑

### Foundation / Bass 设置保存

主控制台支持两层保存：

1. **四标签配置**：保存当前情绪、能量、音色方向、节奏下的 Foundation / Bass 设置、模式和乐器选择。
2. **音色方向默认乐器**：保存当前音色方向下默认的 Foundation 与 Bass 乐器。之后切换同一个音色方向时会自动载入；情绪、能量和节奏不会把该默认乐器覆盖掉。

未保存默认乐器的音色方向会回到“自动匹配”，不会沿用上一个音色方向的乐器。

### 鼓型匹配优先级

鼓型按标签的精确程度选择，优先级如下：

```text
音色方向 + 能量 + 节奏
-> 任意音色方向 + 能量 + 节奏
-> 音色方向 + 能量 + 任意节奏
-> 任意音色方向 + 能量 + 任意节奏
```

同标签下优先使用与 Loop 长度一致的 Pattern。若 8 小节没有专属 Pattern，系统循环使用已保存的 4 小节事件。

### 模式选择优先级

- 明确手动选择模式时，整段 Loop 固定使用该模式。
- 选择 `自动` 时，由当前标签和已启用的后台模式决定。
- 电子、民族、电影 Bass 只会在各自允许的音色方向中自动选择。
- 弦乐 Foundation 会优先触发对应的电影 Bass 联动。

## 输出、接口与数据目录

### 输出文件

| 目录 | 内容 |
| --- | --- |
| `output_midi/` | 生成的 `.mid` 文件 |
| `output_audio/` | 生成的 `.wav` 与可用时的 `.mp3` 文件 |
| `samples/` | 直接采样配置与上传文件 |
| `sound_sources/` | MIDI 音源与鼓件音源配置 |
| `instruments/` | 多采样乐器与 Zone 文件 |
| `sample_import/` | 导入任务、预览和临时导入数据 |
| `harmony/` | 手动和弦规则 |
| `drum_patterns/` | 鼓点 Pattern 数据 |
| `mixer/` | 调音台与效果设置 |
| `data/` | Foundation、Bass、吉他、弦乐演奏模式等后台配置 |

输出文件以 `state_id` 为基础命名。主控制台创建的临时状态会使用时间戳名称。

### HTTP API

所有接口由本地服务提供。JSON 写入接口使用 `POST` 且需要 `Content-Type: application/json`；乐器和采样上传接口使用 `multipart/form-data`。

| 方法 | 地址 | 说明 |
| --- | --- | --- |
| `POST` | `/api/resolve` | 仅解析 JSON，返回 Resolver、和弦、模式、乐器、鼓型与采样命中 |
| `POST` | `/api/generate` | 生成 MIDI、WAV、MP3 并返回下载地址 |
| `GET` / `POST` | `/api/mixer` / `/api/mixer/save` | 读取或保存调音台 |
| `GET` / `POST` | `/api/effects` / `/api/effects/save` | 读取或保存效果设置 |
| `GET` / `POST` | `/api/harmony` / `/api/harmony/save` | 读取或保存和弦规则 |
| `POST` | `/api/harmony/delete`、`/api/harmony/import`、`/api/harmony/reset` | 删除、导入或重置和弦规则 |
| `GET` / `POST` | `/api/drum-patterns` / `/api/drum-patterns/save` | 读取或保存鼓点 Pattern |
| `POST` | `/api/drum-patterns/import`、`/api/drum-patterns/reset`、`/api/drum-patterns/duplicate` | 导入、重置或复制鼓型 |
| `GET` / `POST` | `/api/sound-sources` / `/api/sound-sources/save` | 读取或保存 MIDI 音源 |
| `POST` | `/api/sound-sources/upload`、`/api/sound-sources/import` | 上传或导入 MIDI 音源配置 |
| `GET` / `POST` | `/api/samples` / `/api/samples/upsert` | 读取或保存直接采样 |
| `POST` | `/api/samples/upload`、`/api/samples/delete` | 上传或删除直接采样 |
| `GET` / `POST` | `/api/instruments` | 读取或创建多采样乐器 |
| `PUT` / `DELETE` | `/api/instruments/{id}` | 更新或删除乐器 |
| `PUT` / `DELETE` | `/api/instruments/{id}/zones/{zone_id}` | 更新或删除 Zone |
| `GET` / `POST` | `/api/foundation-patterns` / `/api/foundation-patterns/upload` | Foundation 模板库与上传 |
| `GET` / `POST` | `/api/foundation-performance-modes` / `/api/foundation-performance-modes/save` | Foundation 演奏模式 |
| `GET` / `POST` | `/api/bass-groove-modes` / `/api/bass-groove-modes/save` | Bass 律动模式 |
| `GET` / `POST` | `/api/guitar-performance-modes` / `/api/guitar-performance-modes/save` | 吉他演奏模式 |
| `GET` / `POST` | `/api/string-performance-modes` / `/api/string-performance-modes/save` | 弦乐演奏模式 |
| `POST` | `/api/sample-import/*` | 单采样、SFZ、MappingChart、VSCO 分析与创建流程 |

接口调用示例：

```bash
curl -X POST http://127.0.0.1:8766/api/resolve \
  -H 'Content-Type: application/json' \
  --data @examples/annotations.json
```

`/api/resolve` 与 `/api/generate` 接收单个标准 JSON；需要附带控制台设置时，在 JSON 顶层添加 `generation_settings` 与 `render_options`。

## 主要代码结构

```text
auto_loop_midi_generator/
  music_state_schema.py       输入 JSON 归一化
  resolver.py                 情绪、能量、音色、节奏 Resolver
  harmony_rules.py            默认和声规则
  harmony_admin.py            手动和弦规则
  generator.py                Foundation、Bass、Drums MIDI 生成
  midi_rule_generator.py      MIDI 规则辅助层
  foundation_performance.py   通用 Foundation 演奏模式
  foundation_midi_patterns.py 上传 MIDI 模板库
  guitar_performance.py       Nylon / Electric Guitar 演奏模式
  string_performance.py       弦乐演奏模式
  bass_grooves.py             基础、电子、民族、电影 Bass 模式
  drum_patterns.py            鼓机网格与 Pattern 匹配
  instrument_library.py       多采样乐器与 Zone 选择
  sample_import.py            SFZ、MappingChart、VSCO 导入
  sound_sources.py            MIDI 音源与鼓件音源
  sample_library.py           直接音频采样叠加
  mixer_config.py             调音台持久化
  effects_config.py           效果设置持久化
  audio_renderer.py           WAV / MP3 渲染
  web.py                      本地 HTTP 服务与 API
web/
  index.html                  Loop 主控制台
  *_admin.html / *_admin.js   各类后台页面
  styles.css                  共用界面样式
tests/                        单元与通路测试
```

## 测试与常见问题

### 后台保存后前端没有变化

1. 确认后台条目已启用，且当前四个标签与后台标签一致。
2. 重新点击生成。已生成的旧音频不会自动变成新配置。
3. 修改 Python 文件后重启服务；只改 HTML / JS 时刷新页面即可。
4. 在主控制台查看 Resolver 结果，确认是否命中了预期的 Pattern、乐器、采样或模式。

### JSON 显示“静止”，但实际生成不是静止

检查 `music_state.energy.value`。只有数值 `0` 才是静止；`0.5` 会被解析为流动，`1` 会解析为高能。情绪同理，应以 `emotion.value` 为准。

### 上传音源或乐器后没有声音

1. 检查乐器 / 音源是否启用，轨道角色是否是 Foundation 或 Bass。
2. 检查音色方向、情绪、能量、节奏标签是否能命中。
3. 检查 Zone 根音、最低音和最高音是否覆盖生成的 MIDI 音域。
4. 检查主控制台调音台没有把该轨增益调低、Mute 或被其他轨 Solo 排除。
5. 没有可用乐器时，Foundation / Bass 会使用内置回退音色；鼓件没有可用音源时不会强制用合成鼓替代。

### 前端鼓点与鼓机后台不一致

在主控制台的 Resolver 结果中查看 `music_rules.drum_rule` 的 `pattern_id`、`pattern_name`、`event_count` 和 `effective_event_count`。确认命中的是当前编辑并保存的 Pattern，再重新生成音频。

### MP3 下载失败或播放器时长为 0

系统会优先给出 WAV。检查生成结果中的 `audio_warning`，确认本机是否具备 MP3 编码能力。WAV 能播放时，音乐生成和音源通路是正常的。

### 用 file:// 打开后台时出现 Failed to fetch

这是正常现象。请通过 [http://127.0.0.1:8766/](http://127.0.0.1:8766/) 或 `/admin/...` 路径打开页面，而不是直接双击 HTML 文件。

## 运行边界

- 项目是单机本地工具，数据以 JSON 和本地文件保存；没有登录、多用户、云同步或权限隔离。
- 这是规则型生成和本地渲染引擎，不是云端 AI 作曲服务。
- 音频质量取决于所上传的乐器 Zone、鼓件音源、直接采样、调音台和效果设置。
- 生成的 Loop 用于试听、素材验证与原型制作；正式发布前应按实际用途检查采样库授权与输出音量。
