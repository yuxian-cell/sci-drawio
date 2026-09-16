# replicate-workflow.md — 参考图复刻工作流（模型执行规范）

当任务包含"参考图 + 要求复刻"时，按本文件执行。**模型是视觉引擎**：坐标和结构以模型"看到"参考图像素为准，不依赖 OCR 文本提取（OCR 对密集中文小字/竖排极不可靠，坐标偏差可达几十像素）。

## 0. 阶段总览

```
read → spec → build → live → shot → selfcheck → fix(循环) → deliver
```

阶段由 `ref-replicate next` 推进。fix 循环：发现问题 → 改 spec → 重跑 build → live draw → shot → selfcheck，直到无重大差异。

## 1. read —— 视觉读图（不要 OCR 中转）

- 用 Read 打开参考图；图大/字密时**放大裁剪区域**逐块精读（左上→右上→左中→…）。
- 提取：① 标题位置与字号；② 章节竖条/模块色带（每块的 x/y/w/h、填充色）；③ 模块内每个框的**文字内容、同行合并、竖排标注**；④ 全部标注线（箭头+文字+起止）；⑤ 小节号位置。
- 关键技巧：**以模块色带为锚点**——先锁定色带的像素坐标，再定模块内内容，避免整体漂移。多模块的共享行（横跨两模块的变量/指标行）单独记录，通常放顶层（不归属单个容器）。

## 2. spec —— 视觉直出坐标

- `layout: "manual"`，每个节点 `x/y/w/h` 用**参考图像素值**（参考图多大，坐标就用多大）。
- 容器（swimlane）表达模块色带；**容器子节点坐标相对容器左上角**（脚本自动偏移，写绝对坐标会被叠加而错位）。横跨多模块的行放**顶层**。
- 同行合并框（如"概念|形成原因"与"保守治疗/手术治疗"同框）用 `<br>` 合并成**一个节点**，不要拆散——拆散会造成"文字错乱"观感。
- 数据源文本与参考图文字冲突时**以数据源为准**，其余按参考图。
- 颜色、字号、行距尽量还原参考图（子框高 20px、行距 25–30px、标注 9–11px 是常见值）。

## 3. build —— 构建

```bash
python scripts/sci_drawio.py build spec.json -o out.drawio
```

输出显示 nodes/edges/containers/bbox；脚本内置零重叠与引用校验。再跑一次越界自检：每个容器子节点（相对坐标）不得超出容器（`x+w ≤ 容器w`，`y+h ≤ 容器h-标题条`）。

## 4. live —— 逐步绘制到可见窗口

```bash
python scripts/sci_drawio.py live draw spec.json --step-ms 90 --save out.drawio
```

- 绘制前自动清空画布（会**清掉当前窗口内容**——若窗口里有用户内容，先 `live save 备份.drawio`）。
- 绘制期间**不要**让用户窗口被遮挡/最小化；draw 结束的自动截图偶发超时——**单独用 `ref-replicate shot` 截图**（带重试）。
- 绘制完成后窗口保持打开。

## 5. shot —— 干净画布截图

```bash
python scripts/sci_drawio.py ref-replicate shot -o shot.png
```

自动：隐藏 draw.io 的便笺本/格式面板/菜单等 UI → fit 画布 → 截图 → 恢复 UI 与原缩放。若窗口遮挡导致 CDP 截图超时，命令自动重试并提示恢复窗口。

## 6. selfcheck —— 并排自检

```bash
python scripts/sci_drawio.py ref-replicate selfcheck
```

生成"参考图 | 当前画布"**同高并排**的对比图 + JSON 报告。用 Read 查看拼图，逐项核对：

1. **布局**：四章/模块边界、色带位置是否一致；有无整体漂移或重叠。
2. **文字**：每模块内文字是否与参考图（或数据源）一致；竖排标注是否都在；合并行是否还原。
3. **连线**：参考图每条标注线（引出/包括/得到/验证/模型合并/方法对应…）在画布上是否都有对应；箭头方向正确。
4. **细节**：小节号、字号、行距、间距。

## 7. fix —— 修正循环

- 发现问题 → 改 spec（或生成器脚本）→ build → live draw → shot → selfcheck。
- 每次 fix 前 `ref-replicate next` 会累计 fix_round；满意后 `ref-replicate next --to deliver`。
- 修改生成器脚本后**必须重新 build 再 live**，不要手改 .drawio。

## 8. deliver —— 交付

```bash
python scripts/sci_drawio.py ref-replicate report
```

交付物：`.drawio`（可编辑主交付）+ 预览 PNG（可用 `export` 或 selfcheck 拼图）。用 `present_files` 交付，窗口保持打开。
