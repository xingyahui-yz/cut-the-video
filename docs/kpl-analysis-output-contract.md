# KPL 片段分析输出约定

机器可读结构见 [`schemas/kpl-clip-candidates.schema.json`](../schemas/kpl-clip-candidates.schema.json)。目标是让 Codex 输出能被剪辑助手复核、筛选，并转换成待审时间线的片段候选。

每个候选片段都绑定具体源文件及源内起止秒数，保留可定位的画面/解说证据，并分别说明**操作精彩程度**与**比赛意义**。单场回顾按比赛顺序编排；选手跨场、英雄操作、战队/赛事专题由对应主题决定顺序。格式不设数值评分权重或自动淘汰门槛。

身份无法从比赛画面或可靠赛事实料确认时，标成 `uncertain` 或 `unresolved`，放入待审；不能凭大名单推定实际登场。若叙事建议引用选手经历，必须附知识库中已确认的 fact ID 与来源链接；没有已确认事实时，不生成生涯事实主张。旁白稿不属于首轮必需输出。

`selected` 与 `needs_review` 是可进入待审时间线的候选；`not_selected` 只留在分析记录中，并要求说明排除理由。应用端仍需校验源文件哈希、候选起止范围、排序一致性、重复/重叠片段，以及引用的知识库事实是否存在且已确认；JSON Schema 本身不能完成这些跨字段或外部数据校验。

## 首轮分析素材准备

[`tools/kpl_analysis_packets.py`](../tools/kpl_analysis_packets.py) 会本地校验源文件 SHA-256、用 FFmpeg 按固定间隔抽取带源时间戳的缩略帧、使用本机缓存的 faster-whisper small 生成中文时间戳转写，并按 5 分钟源时间段整理分析包。它只准备视听证据，不判断高光，也不调用 Codex。

人工基线保存后，可从仓库根目录运行：

```powershell
python tools/kpl_analysis_packets.py `
  --asset-map path\to\asset-map.json `
  --output-dir artifacts\analysis-packets
```

默认使用本机配置的 faster-whisper 模型；默认每 15 秒抽一帧、每 5 分钟建立一包，参数可调。输出目录必须是新目录；产物含 `index.json`、每局 `transcript.json`/`packets.json` 和缩略帧；索引记录总处理耗时及每局抽帧、转写耗时。转写可能误识别，不能视为事实证据。资产映射包含本机媒体路径和文件哈希，应保存在本地并加入忽略规则。

### Codex 候选分析与整组选片

[`tools/kpl_codex_analysis.py`](../tools/kpl_codex_analysis.py) 读取上述 `index.json`，逐包将时间戳帧与本地转写提交给本机 Codex CLI，并用候选 schema 约束结构化输出；随后再让 Codex 在整组候选中作 2～5 分钟全局选择。每个模型回应均另存，合并时由程序重写稳定候选 ID 和源素材元数据；全局决策必须覆盖每个候选且恰好一次，并通过身份状态、源片重叠与总时长校验。选择阶段不改写候选事实，只应用状态、原因和时间顺序。输出目录必须是新目录。

命令示例（人工基线保存且分析包已生成后运行；调用本机 Codex CLI，沿用当前 Codex 配置和模型）：

```powershell
python tools/kpl_codex_analysis.py `
  --analysis-index artifacts\analysis-packets\index.json `
  --asset-map path\to\asset-map.json `
  --output-dir artifacts\codex-review
```

完成后，`candidates.json` 可交给下方 FCPXML 导出器；每包原始回应、全局选择回应、`codex-timings.json` 及汇总均保存在新建输出目录。真实分析质量、长任务稳定性和最终 Resolve 导入应在本地素材上验收。

## 首轮时间线导出

命令行导出器位于 [`tools/kpl_timeline.py`](../tools/kpl_timeline.py)，接收候选 JSON 和资产映射，并生成可手动导入 DaVinci Resolve 的 `.fcpxml`：

```powershell
python tools/kpl_timeline.py `
  --candidates path\to\candidates.json `
  --asset-map path\to\asset-map.json `
  --output path\to\review-timeline.fcpxml `
  --project-name "JDG–EDG.M 待审集锦"
```

`asset-map` 将 schema 中的 `asset_id` 对应到本机绝对文件路径、SHA-256、媒体时长、画面尺寸、帧率和音频规格。每次导出都会重新计算时间线所引用源文件的 SHA-256，并验证候选哈希、源时长和范围、待审/排除理由、证据、顺序、源片重叠、序列规格、2～5 分钟总时长及知识库事实；已存在的输出文件不会被覆盖。资产映射属于本机数据，不应提交到远端仓库。

时间线保留源视频和原音轨，片段备注附候选理由、证据、待审信息和已核实的知识库事实。未选候选不进入时间线。输出器测试通过不等于 Resolve 已能正确导入；必须在本机手动导入、检查媒体在线/原声/规格并实际导出，才算接入验收完成。

严格结构化输出要求所有字段都出现；无值字段使用 `null` 或空数组。
