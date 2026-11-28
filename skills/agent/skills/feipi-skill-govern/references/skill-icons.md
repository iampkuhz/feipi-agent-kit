# 查找、设计与分发 Skill 图标

处理新增 Skill、图标补齐或用户要求换图时，先看目标 `SKILL.md` 的名称、触发说明和主要交付。提炼实际用途的中英文词项，例如「家庭健康档案 / health records」。对已有 Skill 的审计同时读取原本的 `icon`、`color` 和图库链接。现有图案仍贴合用途时沿用该选择。

## 查找与应用

1. 在目标仓库运行 `skill_icon_catalog.py search`，传入用途词项，或用 `--skill` 从目标入口提取名称和描述。用更精确的短语补充搜索，尤其是描述中同时出现其他产品或邻近用途时。
2. Codex 从目标仓库 `assets/skill-icons/catalog.json` 读取每个母版的 ID、中文名称、图形与用途说明及同义词。Cursor 读取版本化原生名称表，先用已登记的双语提示，再用每个原生名称与拆分后的词检索。两边各返回候选 ID、说明和命中的词。执行治理的 Agent 根据主要交付与图形来选，复用图标时检查相邻 Skill 是否容易区分。只有合适的一端能复用时，可先选定该端。
3. 选定后执行 `bind`。它修改 `SKILL.md` 的 Cursor `icon` 与可选 `color`，同时把 Codex 的选定 ID 写进 `agents/openai.yaml` 的 `icon_small` 和 `icon_large`。两个字段都引用同一个 `./assets/<图标 ID>.png`。源码内的同名链接指向图库母版，安装会把图像实拷到这个路径。
4. 运行 `validate.sh` 检查目标。它验证 Cursor 名称和颜色、Codex 目录描述与 PNG 一一对应、相对绑定、宿主路径和图像。需要验收分发时，在目标客户端的隔离安装中核对宿主实际读取的文件和预览。保留该选择的理由、使用的名称/母版和验证范围。

以下命令中的脚本路径相对于治理 Skill 目录，可在目标仓库使用绝对路径调用。`--skill` 及 `bind` 的参数指向目标 Skill 源码。

```bash
python3 scripts/skill_icon_catalog.py search '家庭健康' 'health records' --skill "$target_skill"
python3 scripts/skill_icon_catalog.py bind "$target_skill" --cursor cross-medical --color green --codex health-maintain-family-records
bash scripts/validate.sh "$target_skill" --require-maintenance
```

## Codex 桌面端显示验收

在 macOS 桌面版 `26.1120.50957` 已实测本地 Skill 的自定义图标。打开 **Settings → Plugins → Skills**，点击右上角 **Browse directory**，在目录的 **Skills** 中搜索已安装的目标，查看卡片左侧是否显示选定的 PNG。也可通过 `codex://skills` 打开 Skills。验收记录应注明客户端版本和实际查看的入口。 [OpenAI 桌面端入口](https://learn.chatgpt.com/docs/app/commands#skills)

该版本在以下两处为本地 Skill 统一显示通用方块图标。

- **Settings → Plugins → Skills** 的启用开关列表。
- 聊天输入框的 **`$` Skill 选择器**中标记为 **Local file** 的条目。

这两处由客户端决定图标，不读取 `agents/openai.yaml` 的 `interface.icon_small` 和 `interface.icon_large`。出现方块时使用目录卡片验收；更换 PNG 或重新安装无法改变这两处的显示。

## 发现 Cursor 新图标

收到换图需求且现有候选不足、或仓库准备支持新版本时，检查目标版本的真实安装包。可以使用已安装应用、应用资源目录或官方安装 ZIP。从 Homebrew 下载时可用 `brew fetch --cask cursor`，再用 `brew --cache --cask cursor` 定位下载包。该检索只读取安装包。

```bash
python3 scripts/discover_cursor_icons.py "$cursor_bundle" --query '监控 performance latency' --snapshot "$scratch/cursor-names.txt"
```

结果包括构建版本、增加/移除的名称和命中用途的新增候选。新名称能直接按原生名与拆词搜索。需要服务于中文意图时，在 `cursor-icon-keywords.json` 为合适的图形补通用名、说明和中英文同义词。选入新名称前核对字形是否贴合用途、目标部署版本是否支持，并核对移除的名称是否已被现有 Skill 使用。更新 `cursor-icon-names.txt` 后跑仓库全量校验。若安装包结构变化而脚本无法追到徽章的名称校验表，继续使用经验证的快照，定位新结构后再更新。

## 新绘 Codex 图标

先用目录检索是否有准确的复用图。需要原创图稿时，选一个能表达主要用途的轮廓，并赋予稳定的英文 ID、易懂的中文名称、图形与用途说明及检索同义词。推荐描述具体到可视元素，例如「屏幕与脉冲线，表示持续观测服务状态」。

- 母版保留一张 256 × 256 的透明 PNG。设计用 32 × 32 网格，四周透明，圆角底板距边缘 1 格，圆角半径 8 格。
- 主图使用白色线稿，统一约 2.15 格线宽与圆角端点。主体通常放在 6–26 格内，允许一个强调色细节。沿用渲染器中的配色，按用途选颜色。优先表达单一动作或对象，缩至 16、24、40 px 检查轮廓和对比度。
- 可以手绘或用矢量编辑器起稿。`render_skill_icon.py` 接收主体与可选点缀的 SVG path `d` 值，统一生成底板、线宽、颜色和分辨率。该命令使用 `rsvg-convert`。先将试稿写入临时区，核对灰白/深色背景和小尺寸显示。

```bash
python3 scripts/render_skill_icon.py "$scratch/monitoring.png" --palette blue \
  --main 'M7 8h18v16H7Z' --accent-path 'M9 17h4l2-5 3 8 2-3h3'
```

图稿合适后，把一张 PNG 和 `catalog.json` 中同 ID 的记录放进目标仓库图库。再次用用途搜索确认能找到它，再绑定到目标 Skill 并校验。共享图稿需要局部修改时使用新 ID，旧母版留给仍使用它的 Skill。
