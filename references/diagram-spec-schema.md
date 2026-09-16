# diagram-spec-schema.md — spec JSON 字段定义

`sci_drawio.py build spec.json` 读取的完整契约。模型产出 spec 时以此为准；脚本对未知字段静默忽略，对缺失必填项报错。

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 图名，也是 .drawio 的 diagram name |
| `type` | string | ✅ | 图类型标签：`schematic`/`flow`/`mechanism`/`pathway`/`framework` 等（影响布局与样式建议，不写死行为） |
| `theme` | string | | 主题名：`nature`（默认）/`minimal`/`cell` 或 `assets/themes.json` 中自定义 |
| `title` | string | | 图标题（自动置顶，居中加粗） |
| `layout` | string | | `auto`（默认，自动分层排布）或 `manual`（用显式 x/y） |
| `nodes` | array | ✅ | 节点列表，见下 |
| `edges` | array | ✅ | 连线列表，见下（可为空数组） |
| `containers` | array | | 容器（swimlane 分组）列表，见下 |
| `layers` | array | | 额外图层列表（默认图层 id="1"；每项 `{"id","name"}`） |
| `legend` | array | | 图例项：`{"label","arrow","dashed","color"}`；脚本自动渲染为图例框 |
| `notes` | array | | 注释：`{"text","x","y","w","h"}`；缺坐标时自动放在图下方 |
| `diagramId` | string | | 可选，diagram 元素 id（默认 sci-drawio-1） |

## nodes[] — 节点

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 唯一标识（字母数字下划线），edge 引用用 |
| `label` | string | ✅ | 显示文本；支持 `<b>/<br>/<sub>/<font color=>` 等 HTML |
| `shape` | string | | 形状名，见形状表；默认 `rounded` |
| `tone` | string | | 主题色系名：`default`/`alt`/`alt2`/`alt3`/`alt4`/`alt5`/`muted`；默认 `default` |
| `rank` | int | | auto 布局时的层级（0 起）；不填则由最长路径推算 |
| `order` | int | | 同一层级内的排序（小的靠左） |
| `x`,`y` | int | manual 必填 | 显式坐标（左上角） |
| `w`,`h` | int | | 尺寸；默认 150×60 |
| `container` | string | | 所属容器 id（坐标相对容器） |
| `layer` | string | | 所属图层 id；默认 "1" |
| `fontStyle` | string | | `normal`/`bold`/`italic`/`bold-italic` |
| `fontSize` | int | | 字号 |
| `align` / `verticalAlign` | string | | 文本对齐：`left/center/right`、`top/middle/bottom` |
| `opacity` | int | | 0–100 透明度 |
| `dashed` | bool | | 节点边框虚线 |
| `whiteSpace` | string | | `nowrap` 时不换行 |

### 形状表（全部经 draw.io 31.4.5 实测渲染）

| shape | 视觉 | 科研用途 |
|---|---|---|
| `rounded` | 圆角矩形 | 蛋白、分子、实体（默认） |
| `rect` | 直角矩形 | 普通步骤、组件 |
| `process` | 双竖线矩形 | 处理步骤、操作 |
| `ellipse` | 椭圆 | 细胞、状态、起始/终止 |
| `double_ellipse` | 双椭圆 | 起始/终止节点 |
| `rhombus` | 菱形 | 判断/分支/条件 |
| `cylinder` | 圆柱 | 数据库、存储、试剂 |
| `parallelogram` | 平行四边形 | 输入/输出 |
| `hexagon` | 六边形 | 修饰、加工节点 |
| `document` | 文档形 | 文档、报告、论文 |
| `cloud` | 云形 | 外部系统、环境因素 |
| `actor` | 人形 | 角色、人员、患者 |
| `note` | 便签形 | 备注块（与 `notes[]` 不同，是可拖动节点） |
| `text` | 纯文本 | 基因名、无框标注 |
| `swimlane` | 泳道（容器） | 用 `containers[]` 声明，不要放在 nodes 里 |

## edges[] — 连线

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 唯一标识 |
| `from`,`to` | string | ✅ | 起止节点 id（须存在于 nodes） |
| `label` | string | | 边标签（如"激活"） |
| `arrow` | string | | 终点箭头语义，见箭头表；默认 `activation` |
| `startArrow` | string | | 起点箭头语义（反向作用） |
| `style` | string | | `orthogonal`（默认，直角折线）/`curved`/`straight`/`raw` |
| `rawStyle` | string | style=raw 必填 | 完整 draw.io 样式字符串，原样透传（不再追加任何默认样式） |
| `dashed` | bool | | 虚线（间接/推测关系） |
| `width` | int | | 线宽 px；默认 2 |
| `color` | string | | 十六进制线色；默认取主题 edge 色 |
| `layer` | string | | 图层 id；默认 "1" |

### 箭头语义表（draw.io 31.4.5 实测：classic/block→实心三角，open→空心V，oval→圆点，ERone→⊥形条；sharp/tech/techThin 会退化为无箭头，禁用）

| arrow | 语义 | 渲染 |
|---|---|---|
| `activation` | 激活/直接作用/磷酸化促进 | 实心三角 ► |
| `inhibition` | 抑制/负调控 | **⊥ T 形条** |
| `translocation` | 转位/转运/迁移 | 空心 V ▷ |
| `association` | 结合/相互作用 | 圆点 ● |
| `production` | 生成/转录/翻译/分泌 | 实心三角 ► |
| `none` | 无箭头 | 纯线 |

## containers[] — 容器（swimlane 分组）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 唯一标识；节点用 `container` 引用 |
| `label` | string | ✅ | 组标题（如"细胞膜""细胞核""Phase 1"） |
| `rank`,`order` | int | | auto 布局时容器在顶层网格中的位置 |
| `startSize` | int | | 标题条高度；默认 30 |
| `x`,`y`,`w`,`h` | int | manual 必填 | 显式几何；auto 布局下 w/h 不填则自动包住子节点 |
| `layer` | string | | 图层 id |

容器规则：
- 子节点（`container` 指向容器的 nodes）坐标**相对容器左上角**，脚本自动偏移。
- 容器无显式尺寸时自动扩张到包住全部子节点（含内边距 20）。
- 边可以跨容器连接，脚本按节点最终绝对坐标生成连线。

## 布局规则（auto 模式）

1. 最长路径分层：节点 rank = 其最长下游路径长度；显式 `rank` 作为下限。
2. 若存在 from→to 边且 to 的 rank ≤ from 的 rank，强制提升 to（保证边方向向下）。
3. 每层从左到右按 `order`（默认按 id 字典序）排列，节点间距 30，层间距按层内最大高度 + 30。
4. 容器作为顶层单元参与分层；其子节点在容器内单独分层排布（纵向）。
5. 标题占顶部 60px 起始偏移；图例自动置于图下方；注释置于图例下方。

## 示例（最小合法 spec）

```json
{
  "name": "Simple Pathway",
  "type": "pathway",
  "theme": "nature",
  "title": "简单通路示例",
  "layout": "auto",
  "nodes": [
    {"id": "a", "label": "因子A", "shape": "rounded", "tone": "default"},
    {"id": "b", "label": "激酶B", "shape": "rounded", "tone": "alt"},
    {"id": "c", "label": "转录", "shape": "process", "tone": "alt2"}
  ],
  "edges": [
    {"id": "e1", "from": "a", "to": "b", "arrow": "activation", "label": "激活"},
    {"id": "e2", "from": "b", "to": "c", "arrow": "production", "label": "促进", "dashed": true}
  ],
  "legend": [
    {"label": "激活", "arrow": "activation"},
    {"label": "促进(间接)", "arrow": "production", "dashed": true}
  ],
  "notes": [{"text": "注：虚线表示间接调控。"}]
}
```

## 常见错误

- edge 引用了不存在的节点 id → 校验报错。
- 节点 id 重复 → 校验报错。
- `layout: "manual"` 但某节点缺 `x`/`y` → 自动回退 auto 布局。
- 在 nodes 里放容器（应用 `containers[]`）。
- 在 label 里用未转义的 `<`/`&`（直接写 HTML 标签是允许的，如 `<b>`；写裸 `<` 会被转义）。
