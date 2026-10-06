# Burn the Token

**把喜欢的视频变成可持续积累的镜头库，再把镜头方法用于自己的作品。**

一个面向 Codex 等支持 `SKILL.md` 的 Agent 的视频制作技能。支持多参考视频、个人镜头库、逐镜参考复刻、Remotion 制作、声画对照和高清导出。

## 1. 上传参考视频 → 建立自己的镜头库

把一条或多条想复刻呈现方式的视频交给 Agent。它会登记全部文件、识别重复视频，实际审看后把镜头拆成带时间码的记录。

每个镜头保存：

- 来源视频、起止时间、稳定 ID，以及已观察和未观察的范围。
- 用途与检索标签，例如资料阅读、立体关键词、人物遮挡、纸页入场、流程解释。
- 构图、字体、材质、光影、景深、动作阶段、衔接和声音方法。
- 对照证据、制作使用记录、反馈与修订历史。

以后直接从库里找镜头。新视频可以继续添加，同一个镜头的分析可以持续完善。默认库在工作区 `reference-library/burn-the-token`，也可以指定固定路径跨项目使用。**视频和私人镜头库留在本地，不会自动上传到 GitHub。**

```text
使用 $burn-the-token，把这三条参考视频加入我的镜头库。
重点整理立体文字、人物遮挡和纸张动效，暂时不制作视频。
```

## 2. 调用镜头库 → 执行视频制作

提供文案、口播音频或已有项目，从库中选择适合表达任务的参考，然后执行：

**参考匹配 → 正式质量样稿 → 动态制作 → 同阶段对照 → 音效与衔接 → 预览 → 获授权后导出 → 回填镜头库**

```text
使用 $burn-the-token，从已有镜头库选参考制作这段口播。
先做前三镜，保留我的原声和拍摄规格。
```

```text
使用 $burn-the-token，继续后面的镜头，一次完成剩余部分。
质量标准保持不变，特效之间的额外衔接暂时不改。
```

质量要求贯穿全程：不自行添加参考没有的横线或装饰；细查立体程度、人物覆盖、字体、光影和动作阶段；不重复用整套镜头换字；批量制作仍逐镜检查。音效按动作选，开头有强弱和留白，技术测量与听感分别验收。

## 安装

将本仓库完整放入支持技能的 Agent 技能目录，文件夹名使用 `burn-the-token`。Codex 示例（目标目录需尚不存在）：

```bash
git clone https://github.com/ZhuMeng749/Burn-the-Token.git ~/.codex/skills/burn-the-token
```

若设置了 `CODEX_HOME`，使用对应的 `skills/burn-the-token` 目录。其他 Agent 使用其自己的技能目录。安装后在新会话调用 `$burn-the-token`；已有同名技能先备份再更新，不覆盖个人镜头库。

也可以让 Agent 读取本仓库的 [SKILL.md](SKILL.md) 执行。技能是操作流程、模板和本地管理脚本，不是独立视频编辑应用，也不内置图像生成、配音或渲染服务。

## 镜头库命令

需要 Python 3.9+；媒体导入需要 FFmpeg 提供的 `ffprobe`，抽帧需要 `ffmpeg`。其他库管理操作只用 Python 标准库。不自动安装依赖，不调用付费服务。

```bash
# 新建个人库
python3 scripts/library.py --library ./my-shot-library init

# 一次登记多个视频；同一内容不会重复入库
python3 scripts/library.py --library ./my-shot-library ingest ./reference-a.mp4 ./reference-b.mp4

# Agent 实际审看片段后，用镜头卡模板记录观察
python3 scripts/library.py --library ./my-shot-library record-shot \
  --video <导入得到的视频ID> --start 10.2 --end 15.6 --data ./shot-card.json

# 按词、标签或用途检索；库中原有 ID 保持稳定
python3 scripts/library.py --library ./my-shot-library search --query 立体 --tag 人物遮挡

# 更新分析，保留旧修订；不重新导入原片
python3 scripts/library.py --library ./my-shot-library update-shot --shot <镜头ID> --data ./shot-card.json

# 核验文件与指纹，定位丢失/被替换的源文件
python3 scripts/library.py --library ./my-shot-library check
```

完整用法与数据边界见 [镜头库工作流](references/shot-library.md)。自动登记与抽帧不会产生“已看完”“已听过”或“复刻通过”的结论。

## 仓库结构

```text
SKILL.md                   两阶段入口
agents/openai.yaml         技能显示名称与调用提示
references/                镜头库、制作、对照、声音与验收流程
assets/                    镜头卡、项目状态、单镜评审、时间轴模板
scripts/library.py         本地镜头库管理
scripts/validate_timeline.py 时间轴结构检查
tests/                     去重、检索、修订及媒体流程测试
```

镜头卡是分析与检索记录，不自动等于可直接运行的 Remotion 组件。参考媒体不随仓库分发，使用其具体画面或声音需要另外确认许可。原片规格、声音与用户授权始终优先；结果以实际画面和听音证据验收。

## 检查开发修改

```bash
python3 -m unittest discover -s tests -v
```

FFmpeg 集成测试在本机有 `ffmpeg` / `ffprobe` 时运行，否则明确跳过。测试覆盖库工具，不证明自动审美判断或最终视频质量。
