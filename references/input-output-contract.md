# 输入与输出契约

## 输入与缺省行为

| 字段 | 是否必需 | 缺省处理 |
|---|---|---|
| reference_videos / library selections | 首次入库需来源 | 新视频可为一条或多条文件/路径/链接；已有库可直接用视频/镜头 ID，无需重新上传。全部新来源纳入覆盖清单；不可读取时不凭标题猜内容 |
| library.root | 否 | 指定路径优先，其次项目已有配置，再读 BURN_THE_TOKEN_LIBRARY；否则工作区 reference-library/burn-the-token，记录绝对路径供续接 |
| review_mode | 否 | 默认逐镜静态→动态→衔接；保留用户已有整段或直接导出的明确授权 |
| topic | 否 | 根据参考主题和已有账号上下文提出 3 个原创角度，择最有证据与可视化空间的一条写完，不等待例行选题审批 |
| account_positioning | 否 | 优先沿用已知定位；没有则按参考知识门槛写给同类受众，标假设，不虚构用户身份、经历或测试结果 |
| target_duration | 否 | 参考时长作为暂定目标；最终服从实际获批人声，不能偷偷拉伸音频凑时长 |
| presenter_mode | 否 | 暂按参考的真人/画外音模式分段；没有真人素材则停在录制交接，不擅自改用数字人 |
| existing_assets | 否 | 盘点明确关联的素材；保留原文件，不无限扫描无关目录 |
| final_audio | 否 | 先写稿估时；收到认可的音频后精确对齐；记录是否已含真人、BGM、音效 |
| sfx_library_path | 否 | 指定路径优先，其次项目既有可读库，再检查当前用户 `~/Desktop/音效`；不存在时如实说明并列替代方案 |
| remotion_project_path | 否 | 继续既有项目则读对应项目；新任务则在当前工作区建独立项目；多个候选无法判断才问 |
| output_spec | 否 | 用户规格优先，否则继承主拍摄素材；只有参考时暂用参考参数并标 provisional，收到真人后重算 |
| voice / avatar | 否 | 沿用用户已指定的音色/形象；缺失时先交配音稿，实际生成前确定，不从参考推断使用权限 |

规格继承须考虑旋转元数据后的显示方向。多份主拍摄素材规格冲突时，已有获批 Composition 优先，其次用户指定主素材；仍无法判定才问。不把 29.97 简写为 30；不因预览卡顿降低成片规格。VFR、HDR、非方形像素等无法直接保持时，记录情况并提出最小处理方案，不静默转换。

## 交付文件

使用项目中的 `production/<视频标识>/` 或当前任务允许的交付目录。前期允许标为 `estimated / waiting_media / not_run`，不能用空表装作完成：

| 文件 | 内容与验收条件 |
|---|---|
| `reference-analysis.md` | 有时间码的观察、文案骨架、节奏、镜头/视觉状态、音效/BGM与可迁移方法；区分观察、测量、推断、未知 |
| `reference-inventory.json` | 全部参考的总览、连续播放、听音范围及未观察部分，不伪报完整观看 |
| `shots/<shot-id>/shot-review.json` | 对应参考、呈现维度映射、口播帧范围、静态/动态版本、确认和反馈；使用单镜模板 |
| `original-script.md` | 选题理由、完整原创口播、事实来源、估时；已确认稿标版本 |
| `performance-script.md` | 真人/克隆音顺序、录制台词、纯 TTS 文本、停顿/情绪/重音、发音表与素材命名 |
| `asset-manifest.csv` | 四类素材的 ID、口播实体、来源/许可状态、真实路径、内容区裁切、使用范围、替代方案和检验状态；另附 SFX/BGM cue sheet |
| `storyboard.md` + `timeline.json` | 可阅读分镜与可计算帧时间轴；每句对应画面、音轨、变化、转场和声音事件；估时/精确版分开 |
| `remotion-execution.md` | 本片字体/颜色/纹理、组件/动画/素材、声音路线、Composition 参数、依赖和启动方法 |
| `preview-and-changes.md` | 项目绝对路径、真实 Composition ID 与 localhost 路由、已完成帧范围、查看方式、修改文件/目的、播放结果和版本确认 |
| `quality-checklist.md` | 每项 PASS/FAIL/NOT_RUN、时间码/证据、剩余问题与阶段结论；末期附导出路径、真实规格及完整解码结果 |

对继续项目复用同等内容的已有文件，不为了模板重复创建八套文档。逐镜新增当前镜记录、对照画面与播放证据即可。

`project-state.json` 用于恢复；`timeline.json` 不是视频。最终 MP4 等媒体仅在导出阶段增加。

## 时间轴数据约定

- 整数帧，统一 `[start_frame, end_frame)`；时长为相减。秒仅作显示，以精确 fps 分数换算、统一量化，防止累积取整漂移。
- `composition` 存 width/height/fps（如 `30000/1001`）、全片 duration_frames；`review_range` 是本次已实现、检查的范围。
- `shots` 覆盖 review_range，可在转场重叠，但要填 transition_overlap；每镜包括 script_ids、asset_ids、解释目标、视觉状态、运动交接与字幕重点词。
- `audio_clips` 只列实际启用的声音区间，包括视频内嵌原音。kind 为 speech/music/sfx/ambience，speech.route 为 presenter_original、clone 或 master。母带必须按实际开声区间拆分，不可填全长却声称局部已静音。
- 口播之外的主时间轴空白以 `intentional_silences` 表示；仅代表无人声，音乐/音效可继续，不许借此遮掩缺失句子。
- 每条声音有 asset_id、source_in_seconds、gain_db、speed（默认 1）；动作音另可记 transient_offset_seconds。循环音源须显式设置 loop，不能假造源文件长度。
- `assets` 存实际 path（相对 timeline.json 或绝对路径）、探测到的 duration_seconds 和 role。role=reference 的参考片不能进入成片。官方发布不代表无限制转载许可。
- 模板空值、前一个视频的批准、旧截图都不能当作新版本已验收。可增补 word timings、裁切、来源、运动控制点或音乐包络字段。

### 数组元素字段

以下为数据形状，示例中的值要换成实测或本片设计，不作为默认规格：

```json
{
  "asset_example": {
    "id": "presenter-01",
    "path": "../../public/media/P01.mp4",
    "role": "presenter",
    "duration_seconds": 4.2
  },
  "shot_example": {
    "id": "shot-01",
    "start_frame": 0,
    "end_frame": 90,
    "script_ids": ["P01"],
    "asset_ids": ["presenter-01"],
    "transition_overlap": false,
    "explanation": "真人提出问题，关键词带出下一段对象",
    "visual_states": [
      {"frame": 0, "action": "真人入场并缓慢推近"},
      {"frame": 35, "action": "随关键词出现实体贴图"},
      {"frame": 72, "action": "推向实体，接下镜同向运动"}
    ],
    "motion_handoff": "向右推近主体；下一镜接相同主体位置"
  },
  "audio_clip_example": {
    "id": "voice-01",
    "kind": "speech",
    "route": "presenter_original",
    "asset_id": "presenter-01",
    "start_frame": 0,
    "end_frame": 90,
    "source_in_seconds": 0.5,
    "speed": 1,
    "gain_db": -1,
    "loop": false
  },
  "intentional_silence_example": {
    "id": "pause-01",
    "start_frame": 90,
    "end_frame": 99,
    "reason": "用户最终音频中结论后的自然停顿"
  }
}
```

`asset_example` 等只是说明标签，实际元素分别放进 assets、shots、audio_clips、intentional_silences 数组；不要把这段整段替代 timeline.json。每条数组元素使用 `id`，引用素材用 `asset_id` 或 `asset_ids`。

approval 从 null 变为对象时记录 `{ "version": "实际版本", "user_quote": "实际原话", "confirmed_at": "实际时间", "scope": "确认范围" }`。确认由执行代理根据对话核实，结构检查器不会鉴别授权真伪。

### 单镜记录

采用已维护的审美基准时，`project-state.json` 的 `aesthetic_baseline` 记录实际加载的 `profile_id` 与 `profile_path`；单镜记录中的 `baseline_style_id` 和 `reference_effect_ids` 引用该规范里的风格及效果。效果编号负责选择方法，下面的 `reference_evidence` 仍负责记录本次实际观察与原片时间范围。没有使用基准时保留空值，不强加风格。

`shot-review.template.json` 中 `reference_evidence` 的每个 `reference_id` 唯一；`presentation_mapping` 与 `motion_beats` 中的 `reference_ids` 引用它。时间码是原片秒数，动作帧范围是本片 `[start, end)`，二者不可混用。`observation_kind` 区分静帧、连续播放、听音或旧记录复用；未观察部分写在 `uncertainty`。

映射维度不适用时填具体理由，例如无声音改动、沿用已确认的同一字幕体系；不要强加效果来填满表。沿用体系也要指向已确认版本或其参考。设计依据写 `observed_basis`，本片主题替换与实现适配写 `original_content_adaptation`。静态、动态、衔接的确认分别存于 `approvals`，模板中的空值不代表已通过。

### 对照与范围字段

状态模板第 3 版、单镜模板第 2 版增加以下可选记录。旧项目按当前任务补齐，不重建媒体、不清空旧字段或确认，不要求迁移所有历史镜头；时间轴结构格式及检查器不受影响。

| 字段 | 填写规则 |
|---|---|
| `batch_size` | 当前用户指定的批量，未知为 null；一次完成剩余范围写入 `authorized_scope` |
| `continuity` | `mode` 为 preserve / reference_first / optimize；记录作用范围、用户原话与暂缓事项 |
| `protected_ranges` / `reverted_ranges` | 每条包含镜头或边界、帧范围、版本、作用维度（如 visual / audio / continuity）和用户原话；保留与回退不可混同 |
| `reference_usage` | 每条记录 reference_id、原片区间、shot_id、显著素材/布局/动作组合、版本及有意重复理由；与“有哪些源文件”的参考清单分开 |
| `audio_preferences` | 用户要求的库路径及轨道 dB 范围；使用负值的闭区间，如 [-12, -8]。源校准与实际混音测量另存 cue/质检，不当成轨道范围 |
| `reuse_check` | 是否查过已用参考；同源区间与相同呈现组合分开，必要时填写此前镜号与有意呼应理由 |
| `paired_stage_evidence` | 每条写 stage、reference_id/源时间码、本片帧、对照文件与实际观看类型；按动作阶段对齐，不要求时长相同 |
| `detail_findings` | 每条写维度、参考观察、本片现状、差异证据、修复动作、复检证据及状态；重点记录立体字与人物遮挡 |
| `comparison_review` | 指明量表、各项原始分/满分/权重/证据/扣分理由，已检验总分与可检验满分、未检验维度、实质问题和修复顺序；见 [评审规则](reference-fidelity-review.md) |
| `sound_design` | 指向 cue sheet；参考听音、库内候选试听、混音试听、技术检测分别记状态，不能相互替代 |

新增检查状态使用 `not_run` / `pass` / `fail`，适用时另用 `deferred` / `not_applicable` 并给理由。`preview.audio_render_verified` 只说明音轨生成/技术校验；原有 `audio_verified` 不得仅凭此标 true。确认和导出授权仍由对话证据决定，不由评分或字段自动产生。

阶段 1 的核心交付是独立镜头库、覆盖记录和可查询的镜头卡，不要求生成视频制作的全部文档。项目 `library` 保存 root、selected_video_ids、selected_shot_ids；单镜 `library_reference` 保存选中 shot_id、revision、video_id 与 source_range_seconds。参考映射继续记录当次实际观察，库 ID 不替代证据。
