# sci-drawio — 科研图自动绘制 Skill for draw.io

[![CI](https://github.com/yuxian-cell/sci-drawio/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxian-cell/sci-drawio/actions)

一个让 AI Agent 自动绘制**科研示意图 / 信号通路 / 机制图 / 实验流程图 / 技术路线图**的 Skill（技能）。

```text
用户需求/参考图 ──(模型理解)──▶ JSON 图规格(spec) ──(sci_drawio.py)──▶ .drawio ──▶ 三条交付路径
```

- **模型是设计师**：读文字需求或参考图（视觉理解），产出结构化 JSON 图规格；
- **脚本是绘图员**：`scripts/sci_drawio.py` 把 spec 确定性地转成合法 `.drawio` XML，校验、导出 PNG/SVG/PDF、生成浏览器免安装链接；
- **live 实时绘制（可视化过程）**：内置 drawio-live MCP 服务器（`scripts/live/`），通过 localhost 调试通道直接调 draw.io 图模型 API，在**可见画布上逐步绘制**——节点、连线逐个出现，全程可编辑，实时截图与保存；
- **MCP 快速打开**：内置官方 [draw.io MCP 服务器](https://github.com/jgraph/drawio-mcp)（`@drawio/mcp`）客户端——`mcp open` 一条命令把图自动打开在 draw.io 编辑器（浏览器），数据全程本地。
- **零 Python 依赖**（纯标准库）、live 仅需 Node.js 22+、draw.io Desktop 自动探测。

## 快速开始（给 AI Agent）

把本目录安装到你的技能目录（见下方「安装」），然后在对话里直接说：

> "帮我画一张 EGFR-RAS-MAPK 信号通路机制图，标注抑制关系，我要看到逐步绘制过程"

Agent 会按 `SKILL.md` 流程产出 spec → 构建 → **`live draw` 在可见 draw.io 画布上逐步绘制** → 交付。无需用户写任何 XML。

## 快速开始（给人用）

```bash
# 1. 准备 spec（JSON，字段见 references/diagram-spec-schema.md）
# 2. 逐步绘制到可见 draw.io（可视化过程；可保存/截图）
python scripts/sci_drawio.py live draw samples/signaling-pathway.json --step-ms 500 --save out.drawio --screenshot out.png

# 3. 或用官方 MCP 服务器快速打开
npm install -g @drawio/mcp
python scripts/sci_drawio.py mcp open out.drawio --write out.mcp.url

# 4. 导出预览图（可选）
python scripts/sci_drawio.py export out.drawio -f png -o out.png --border 16 --scale 1.5
```

备选（无 Node）：`open` 用桌面版打开；`url` 生成浏览器链接。

## 安装

**方式一：安装到本机技能目录（推荐）**

```bash
python scripts/install.py --target <你的技能目录>
# 例如：python scripts/install.py --target ~/.agents/skills
```

**方式二：手动复制** — 把整个 `sci-drawio` 文件夹复制到你的技能根目录（如 `~/.agents/skills/`、`workspace/.user_skills/`）即可。

**前置要求**
- Python 3.8+（无第三方依赖）
- **live 实时绘制**（推荐）：Node.js 22+（draw.io Desktop 自动探测；仅需浏览器/桌面 draw.io 之一）
- **MCP 快速打开**：Node.js + `npm install -g @drawio/mcp`（一次安装；`mcp` 子命令依赖）
- **桌面版路径**（备选）：[draw.io Desktop](https://github.com/jgraph/drawio-desktop)（`open`/`export` 需要；只在生成 `.drawio` 时不需）——未安装时设置环境变量 `DRAWIO_PATH` 指向 draw.io 可执行文件即可。

## 示例

| 示例 | 类型 | 浏览器预览 | 说明 |
|---|---|---|---|
| `samples/signaling-pathway` | 信号通路机制图 | [预览](samples/signaling-pathway.url) | EGFR-RAS-MAPK，含抑制箭头与图例 |
| `samples/experimental-flow` | 实验流程图 | [预览](samples/experimental-flow.url) | qPCR 流程，菱形判断 + 循环回退 |
| `samples/mechanism-compartments` | 区室机制图 | [预览](samples/mechanism-compartments.url) | JAK-STAT，容器分组 + 跨容器曲线边 |

每个示例含 `.json`（spec 源）、`.drawio`（产物）、`.png`（预览）、`.url`（浏览器链接）。

## 核心能力

- **先思考后绘制（拦截式）**：产出 spec 后按 `references/viz-pitfalls.md` 主动自查——箭头语义混乱、节点过多、容器嵌套过深、边交叉、文字溢出、孤立节点、配色色盲不可分等命中即修正或向用户说明，不带着已知问题绘制。
- **交付前自检闭环**：导出/截图后必须回读渲染图核对（节点完整、无乱码、边关系与箭头正确、容器嵌套正确、无重叠遮挡），发现问题回改 spec 重绘，通过后才交付。
- **期刊导出参数**：`references/scientific-style-guide.md` 内置 Nature/Science/IEEE/中文期刊的栏宽、DPI、矢量优先与灰度检查建议。

- **live 实时绘制（可视化过程）**：内置 drawio-live MCP 服务器（`scripts/live/live-server.mjs`，MIT © icebird1998 scientific-illustrator，零 npm 依赖）。通过 localhost 调试通道直接调 draw.io 图模型 API，在**可见画布上逐步绘制**——`live draw spec.json --step-ms 500` 让节点/连线逐个出现，全程可编辑；输出与 build 路径一致（标题、图例、注释、容器嵌套都逐步绘制）；**绘制完成后 draw.io 窗口保持打开**，用户可立即手动继续编辑，后续 `live status/screenshot/save` 可随时再连接操控，`live close` 显式关闭；`--screenshot` 实时截图、`--save` 从可见画布序列化 .drawio（默认先清空画布，`--no-clear` 追加）。
- **MCP 快速打开**：内置官方 `@drawio/mcp` 服务器客户端（纯标准库 JSON-RPC over stdio）。`mcp open` 调 `open_drawio_xml` 把图自动打开在 draw.io 编辑器；`mcp shapes` 搜索 10,000+ 形状库返回可直接用的 style 串；`mcp list` 列出服务器工具。
- **15 种形状**：rounded/rect/process/ellipse/rhombus/cylinder/parallelogram/hexagon/document/cloud/actor/note/text/swimlane 等（全部经 draw.io 31.4.5 实测渲染）
- **5 类语义箭头**（科研图约定，非任意样式）：
  | 语义 | 渲染 |
  |---|---|
  | `activation` 激活 | 实心三角 ► |
  | `inhibition` 抑制 | **⊥ T 形条**（`endArrow=ERone`） |
  | `translocation` 转位 | 空心 V ▷ |
  | `association` 结合 | 圆点 ● |
  | `production` 生成/转录 | 实心三角 ► |
- **自动布局**：最长路径分层 + 行内排序；支持容器（swimlane）内子布局与自动扩尺寸；**支持循环（反馈回路）**——回边自动跳过分层并渲染为上溯曲线。
- **5 套主题**（nature/minimal/cell/paper + **colorblind** 色盲安全预设，适合投稿）+ 自定义主题 JSON；图例与注释自动生成。
- **三条交付通道**：live 实时绘制 / MCP 快速打开 / 桌面版 CLI + `#create=` URL（`url-verify` 可回读校验）。

## 架构说明（为什么这样设计）

本项目的设计调研了 [GPT-Image2-Skill](https://github.com/wuyoscar/GPT-Image2-Skill)、[drawio-mcp](https://github.com/jgraph/drawio-mcp)、[scientific-illustrator](https://github.com/icebird1998/scientific-illustrator) 与 [scipilot-figure-skill](https://github.com/Haojae/scipilot-figure-skill)（借鉴其"先思考后绘制"拦截规则与视觉自检闭环理念，适配 draw.io 示意图场景）：

- **理解层**：GPT-Image2-Skill 本质是"生图 + 参考图反推 prompt"，不是图像理解器，不适合矢量科研图。本技能改为**内建理解层**——由模型的视觉能力直接读参考图/草图，产出结构化 JSON 谱（`references/diagram-spec-schema.md` 定义），零额外依赖。
- **绘制层（可视化过程）**：官方 drawio-mcp 的 Tool Server（`@drawio/mcp`）只能"生成 URL 新开标签"，无法在已打开的 draw.io 上实时绘制。本技能采用 **drawio-live**（scientific-illustrator 项目的 MIT 组件，已随技能内置）：启动带 localhost 调试通道的可见 draw.io，通过 CDP 直接调用图模型 API 逐步插入可编辑节点/边——**用户亲眼看到绘制过程**。同时保留官方 MCP Tool Server 与桌面 CLI/`#create=` URL 作为备选。

## 目录结构

```text
sci-drawio/
├── SKILL.md                        # 技能主文件（Agent 触发与流程）
├── README.md                       # 本文件（给人看）
├── LICENSE                         # MIT
├── scripts/
│   ├── sci_drawio.py               # 核心 CLI（纯标准库）
│   ├── install.py                  # 一键安装到技能目录
│   └── live/                       # drawio-live MCP 服务器（MIT © icebird1998）
│       ├── live-server.mjs         #   实时画布控制（零 npm 依赖，Node 22+）
│       ├── drawio-path.mjs         #   draw.io 路径探测
│       └── LICENSE-scientific-illustrator.txt
├── references/
│   ├── diagram-spec-schema.md      # spec 字段定义（模型必读）
│   └── scientific-style-guide.md   # 科研图视觉规范
├── assets/
│   └── themes.json                 # 自定义主题（可选）
└── samples/                        # 完整可运行示例
```

## 命令行参考

```bash
python scripts/sci_drawio.py build   spec.json -o out.drawio          # spec → .drawio
python scripts/sci_drawio.py validate out.drawio                      # 校验 XML 结构与引用
python scripts/sci_drawio.py inspect out.drawio                       # 打印节点/边统计
# ★ live 实时绘制（可视化过程，主路径）
python scripts/sci_drawio.py live draw spec.json --step-ms 500 --save out.drawio --screenshot out.png   # 绘制后窗口保持打开
python scripts/sci_drawio.py live draw spec.json --no-clear   # 追加绘制（默认先清空画布）
python scripts/sci_drawio.py live launch [file.drawio]        # 启动/连接可见 draw.io
python scripts/sci_drawio.py live status / screenshot -o s.png / save out.drawio / close
# MCP 快速打开
python scripts/sci_drawio.py mcp open out.drawio [--lightbox] [--routing libavoid]
python scripts/sci_drawio.py mcp shapes "kinase" --limit 10           # 搜索形状库（返回 style 串）
python scripts/sci_drawio.py mcp list                                 # 列出 MCP 服务器工具
# 备选（无 Node）
python scripts/sci_drawio.py open    out.drawio [--layout NAME]       # 桌面版打开
python scripts/sci_drawio.py export  out.drawio -f png -o out.png [--border 16] [--scale 1.5]
python scripts/sci_drawio.py url     out.drawio [--write out.url]     # 浏览器链接
python scripts/sci_drawio.py url-verify out.url -o decoded.xml        # 回读校验链接
```

## 开发说明

- 箭头渲染行为以 draw.io **31.4.5** 实测为准（SVG 路径级验证）：`sharp`/`tech`/`techThin` 在该版本退化为无箭头，已禁用并映射到可用样式。
- `live` 需要 Node.js 22+；draw.io 可执行文件由 `DRAWIO_PATH` 或自动探测（含常见便携路径）提供；live 服务器路径可用 `SCI_DRAWIO_LIVE_SERVER` 覆盖。live 启动的 draw.io 以独立进程运行（`detached`），命令退出后**窗口保持打开**，`live close` 按调试端口精确关闭该窗口（不误关其它 draw.io）。live 支持容器（swimlane 先绘制，子节点 `parent` 嵌套，容器内边/跨容器边自动处理）；默认绘制前清空画布，`--no-clear` 可追加绘制。
- MCP 服务器未安装时 `mcp` 子命令会提示 `npm install -g @drawio/mcp`；也可设 `DRAWIO_MCP_PATH` 指向其 `src/index.js`。
- `.drawio` 是生成物，修改请改 spec 重跑 build，不要手改 XML。

## License

[MIT](LICENSE)
