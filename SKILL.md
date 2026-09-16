---
name: sci-drawio
description: 自动生成 draw.io 科研图（科研示意图、信号通路/机制图、实验流程/技术路线图、知识图谱等矢量图）的 Skill。当用户要求绘制或生成科研类示意图、机制图、流程图、技术路线图、用 draw.io 作图、生成/编辑/打开/导出 .drawio 文件，或要求在已打开的 draw.io 上逐步可视化绘图时使用。流程：模型先用视觉/文字理解需求（支持参考图或草图），产出结构化 JSON 图规格(spec)，再由本技能脚本确定性地构建 draw.io XML 并校验。交付支持三条 MCP/本地路径：① `live draw` 通过内置 drawio-live MCP 服务器在可见 draw.io 画布上逐步绘制（可视化过程，节点/连线逐个出现，可实时截图与保存）；② `mcp open` 通过官方 @drawio/mcp 服务器自动在 draw.io 中打开；③ 桌面版 CLI 打开/导出 PNG/SVG/PDF、生成浏览器免安装链接。live 仅需 Node.js 22+，mcp 需 npm 安装 @drawio/mcp，零 Python 依赖。流程含绘图前拦截自查（先思考后绘制）与交付前渲染图自检闭环。
---

# sci-drawio — 科研图自动绘制

把用户"画一张科研图"的需求变成真正可编辑、可导出的 draw.io 图。

核心分工：**模型是设计师，脚本是绘图员**。模型负责理解需求并把图的结构（节点、关系、层次、容器）写进结构化 JSON spec；`scripts/sci_drawio.py` 负责把 spec 确定性地转成合法 .drawio XML、校验、调用本机 draw.io 打开/导出。

## 适用与不适用

适用：科研示意图、信号通路/调控机制图、实验流程图、技术路线图、研究框架图、知识图谱、生信分析流程、临床研究设计图等一切 draw.io 能表达的图。

不适用：位图/照片级示意图、3D 渲染、需要精确手绘曲线与手写标注的图、纯艺术插画。若用户需要这些，说明本技能只产出矢量结构图。

## 一、理解需求（模型负责，不调用脚本）

1. 文字需求：直接拆解出实体（节点）、关系（边）、层级（rank）、分组（容器）、标题、图例需求。
2. 参考图/草图（用户上传或给出链接）：**先用视觉能力读图**——提取图中的实体名、形状类型、箭头方向与语义、分组边界、流程顺序。不要猜测图中没有的细节；不确定的关系在图例/注释中标注"推测"。
3. 判断图类型：机制图（实体+调控关系+抑制/激活箭头）、流程图（步骤+判断分支）、框架图（层级分组）、通路图（信号自上而下传导）。类型决定布局方式与样式选择。

## 二、产出 spec（模型负责，核心步骤）

按照 `references/diagram-spec-schema.md` 的字段定义与示例，把理解结果写成 JSON spec。要点：

- **必填**：`name`、`type`、`nodes[]`、`edges[]`（孤立节点也要列 nodes）。
- **布局**：默认 `layout: "auto"`（最长路径分层 + 行内排序打包，自动安排坐标）；需要精确摆放（如对齐参考图结构）时用 `layout: "manual"` 并给每个节点显式 `x/y`。
- **节点形状** 参考图里看到的形状映射为受支持形状（见下）。形状选择规则：实体/蛋白/分子→`rounded`；过程/步骤→`process` 或 `rect`；判断→`rhombus`；数据/存储→`cylinder`；文档→`document`；细胞/膜/区室→`container`（swimlane）或 `ellipse`；基因/文本→`text`。
- **箭头语义** 必须用语义键而非 raw 样式（脚本已按 draw.io 31.4.5 实测验证）：
  - `activation` 激活/直接作用 → 实心三角
  - `inhibition` 抑制/负调控 → **T 形条（⊥，endArrow=ERone）**
  - `translocation` 转位/转运 → 空心 V
  - `association` 结合/相互作用 → 圆点
  - `production` 生成/转录/翻译 → 实心三角
  - `none` 无箭头（普通连线）
  - 反向语义用 `startArrow`（起点加箭头）。
- **颜色**：`tone` 用主题语义色（default/alt/alt2/alt3/alt4/alt5/muted），不要直接写十六进制；需要强调某条边时用边的 `color`。
- **尽量让图自解释**：有 3 种以上箭头语义时，加 `legend`（脚本自动渲染图例）；关键假设/补充信息放 `notes`。

**产出后自查（先思考后绘制）**：spec 写完后按 `references/viz-pitfalls.md` 逐条检查（箭头语义/节点数/容器嵌套/边交叉/文字溢出/孤立节点/配色/与参考图一致性）。**命中即主动修正 spec**；确需保留时向用户说明理由后再继续。不带着已知问题进入绘制。

## 三、构建与校验（调用脚本）

```bash
# 1. spec -> .drawio
python scripts/sci_drawio.py build spec.json -o out.drawio

# 2. 校验（build 已内置一次，单独跑用于复查）
python scripts/sci_drawio.py validate out.drawio
```

build 输出会打印节点/边/容器统计与 bbox；若 XML 校验失败会直接报错退出。报错时按提示修正 spec 重跑，不要手改 .drawio（.drawio 是生成物）。

## 四、交付（可视化过程优先）

**主路径 A：live 实时绘制**——在可见 draw.io 画布上**逐步绘制**（用户能看到节点/连线一个个出现，全程可编辑）。基于技能内置的 drawio-live MCP 服务器（scripts/live/live-server.mjs，MIT © icebird1998 scientific-illustrator，零 npm 依赖，仅需 Node.js 22+）：

```bash
# 一条命令：启动可见 draw.io -> 自动布局 -> 逐步绘制 -> 截图 -> 保存 .drawio
# 绘制完成后 draw.io 窗口【保持打开】，用户可继续手动编辑；默认先清空画布再画
python scripts/sci_drawio.py live draw spec.json --step-ms 500 --save out.drawio --screenshot out.png
# 追加绘制（不清空画布）用 --no-clear

# 会话管理（窗口由 live draw 启动后，任何时刻都可再连接操控）
python scripts/sci_drawio.py live launch [file.drawio]   # 启动/连接可见 draw.io
python scripts/sci_drawio.py live status                 # 会话状态
python scripts/sci_drawio.py live screenshot -o shot.png # 截取当前画布
python scripts/sci_drawio.py live save out.drawio        # 保存当前画布
python scripts/sci_drawio.py live close                  # 关闭 live 启动的窗口（force 兜底，只关调试端口对应窗口）
```

live 模式直接用 draw.io 图模型 API（经 localhost 调试通道）逐步插入可编辑的节点/边，**不生成 XML 再打开、不模拟鼠标键盘**。`DRAWIO_PATH` 自动探测（含常用便携路径），可用环境变量覆盖；服务器路径可用 `SCI_DRAWIO_LIVE_SERVER` 覆盖。**输出与 build 路径一致**：标题、图例（swimlane + 逐项符号文字）、注释（notes）同样逐步绘制；**容器完全支持**：swimlane 容器先绘制，子节点以 `parent` 真实嵌套（容器内子节点坐标相对容器，随容器移动；容器内边挂容器下，跨容器边自动路由）。**绘制完成后窗口保持打开**（draw.io 以独立进程运行，不随命令退出关闭），用户可立即在窗口内手动编辑；后续可用 `live status/screenshot/save` 随时再连接操控，`live close` 显式关闭（只关闭调试端口对应的窗口）。默认绘制前清空当前画布（`--no-clear` 可改为追加）。

**主路径 B：MCP 快速打开**——官方 @drawio/mcp 服务器自动在 draw.io 中打开（浏览器标签页，一条命令出图）：

```bash
python scripts/sci_drawio.py mcp open out.drawio [--lightbox] [--dark auto] [--routing libavoid] [--write out.mcp.url]
python scripts/sci_drawio.py mcp list        # 列出服务器可用工具
python scripts/sci_drawio.py mcp shapes "kinase" --limit 10   # 搜索形状库，返回可直接用的 style 串
# MCP 服务器安装（一次性）：npm install -g @drawio/mcp  或设 DRAWIO_MCP_PATH 指向其 src/index.js
```

`mcp open` 把 XML 压缩为官方 `#create=` URL 并自动打开浏览器编辑器；数据全程本地（URL fragment 不上传）。

**备选路径**（无 Node/无 MCP 时）：

```bash
python scripts/sci_drawio.py open out.drawio                              # 桌面版打开
python scripts/sci_drawio.py export out.drawio -f png -o out.png --border 16 --scale 1.5
python scripts/sci_drawio.py url out.drawio --write out.url               # 浏览器免安装链接
python scripts/sci_drawio.py url-verify out.url -o decoded.xml            # 回读校验链接
```

交付规范：
- **.drawio 文件是主交付物**（可编辑）；导出 PNG/SVG 用于预览与投稿。
- 用 `present_files` 交付 .drawio、PNG（或 SVG/PDF）、必要时附 .url 文本文件。
- 用户要求"可视化过程/在打开的 draw.io 上画"时：用 `live draw`（逐步绘制）；只求快速出图用 `mcp open`。
- 每次修改 spec 后必须重新 build+export，保证交付的 .drawio 与预览图一致。

**交付前自检闭环（必做）**：导出/截图后必须 Read 渲染图逐项核对：① 节点数量与 label 完整、无乱码（含科研符号）；② 边连接关系与箭头语义正确（对照 spec）；③ 容器嵌套正确（子节点在容器内、容器内边/跨容器边正常）；④ 无文字溢出、无重叠遮挡、布局合理。发现问题 → 回改 spec → 重新 build/live 绘制 → 再核对，**通过后才交付**（对应 `references/viz-pitfalls.md` P7/P8 等导出后检查项）。

## 五、规则与限制

- 形状（12 种已实测）：`rect`、`rounded`、`ellipse`、`double_ellipse`、`rhombus`、`cylinder`、`parallelogram`、`hexagon`、`process`、`document`、`cloud`、`actor`、`note`、`text`、`swimlane`（容器）。
- 主题：`nature`（类 Cell 四色系，默认）、`minimal`（黑白灰，适合投稿线图）、`cell`（类似 Excel 调色盘）、`paper`（材料蓝灰）、`colorblind`（Okabe-Ito 色盲安全配色，**投稿推荐**，红绿/蓝紫均可区分）。可用 `assets/themes.json` 追加自定义主题。
- 边样式：`orthogonal`（默认，直角）、`curved`、`straight`；虚线用 `"dashed": true`；raw 高级用法见 schema 参考。
- 容器（swimlane）内子节点坐标相对容器；容器无显式宽高时自动扩到包住子节点。live 模式同样支持容器（swimlane 嵌套 + 容器内边/跨容器边）。
- 图例与注释由 spec 声明生成，不要手工在 XML 里加。
- draw.io 未安装时 `open/export` 会报错并提示设置 `DRAWIO_PATH` 环境变量；`live` 需要 Node.js 22+（draw.io 桌面版路径自动探测）。

## 六、参考文件

- `references/diagram-spec-schema.md` — **必读**：全部字段定义、示例 spec、布局规则、箭头/形状/主题速查。
- `references/scientific-style-guide.md` — 科研图视觉规范（配色、线宽、字体、常见图类型画法、**期刊导出参数**）。
- `references/viz-pitfalls.md` — **绘图前拦截规则**：产出 spec 后必查（箭头语义/节点数/容器嵌套/边交叉/溢出/配色/一致性）。
- `samples/` — 可直接运行的完整示例（机制图/流程图/容器分组），复制修改即可。
- `assets/themes.json` — 可选：自定义主题（模型一般不需要改）。
