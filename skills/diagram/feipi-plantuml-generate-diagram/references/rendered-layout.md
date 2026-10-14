# 渲染遮挡检查与组件图修复

## 验收证据

源码中的 `nodesep/ranksep` 只证明配置存在，不能证明渲染后的标签安全。图包必须在当前 SVG 上执行 `lib/rendered_layout.py` 的几何检查，`validation.json.rendered_layout` 记录 `status`、文字数、连线数与最多 50 条定位诊断。最终 verifier 和缓存复用都会从当前 SVG 重算，不能只信报告或 hash。

- `ok`：支持的连线没有穿入可见文字区域。
- `failed`：真实 SVG 中存在可见相交；`blocked_reason=rendered_layout_failed`、`failure_class=layout`、`repairable=true`。仍遵守每图总计两次渲染的上限，失败 SVG 留作定位证据，不是可交付成功图。
- `review_required`：可见几何无法可靠解析；`blocked_reason=rendered_layout_review_required`、`failure_class=visual_review`、`repairable=false`。不能以静态通过、renderer 成功或口头视觉确认直接改写成 success；需要维护支持边界或调整源码产生可检查的输出。
- `skipped`：尚未真实渲染成功；其他失败边界保持原有合同。

## 检查范围与局限

组件、架构、部署图检查 `link` 中的路径/箭头，也检查开放路径、直线和折线；关系线自己的标签同样受检查。组件/容器装饰线不当作关系线。时序图仅检查 `message` 组中的消息箭头，生命线不作为关系线。本门禁重点解决组件图穿字，时序 note 布局仍按原有流程。

按 SVG 的 `textLength`、字号、anchor 与 baseline 建立文字区域，支持坐标变换、相对路径、多子路径、直线、折线、二次/三次贝塞尔和椭圆弧。曲线自适应细分的局部误差为 0.25 SVG 单位；检查考虑线宽、虚线空隙、绘制顺序及后绘制的不透明背景，透明背景不作为遮挡物。无法测量的文字、tspan/textPath、CSS 样式表、use/image、裁剪/mask/filter、渐变等显式进入复核状态。

这是文字区域检查，不是逐字形像素检测；靠近边缘或字间空隙的相交可能需要人工判断。它不验收文本截断、节点重叠、箭头语义或标签归属。最终图仍须转成白底 PNG，查看全图和复杂交叉处，不得宣称自动视觉审阅已通过。

## 组件图默认与一次修复顺序

1. 默认 `skinparam linetype polyline`；边标签保持空或 `E1...En`。PlantUML 官方说明 `ortho` 有标签定位问题，不能把正交走线当作无挡保证：[布局引擎说明](https://plantuml.com/layout-engines)。
2. 根据诊断坐标找出冲突的关系与标签。先从 `ortho` 改为 `polyline` 或默认曲线，再定点增加 `nodesep/ranksep`、指定冲突边的方向或添加必要的隐藏布局关系。
3. 保持 brief、组件、语义关系与关系编号完整。隐藏关系只能约束布局，不得替代可见的业务关系；不要靠覆盖文字的白块、缩字或删除标签绕过验收。
4. 在原失败图包中提交修改，调用同一 `validate_package.sh`；上次 SVG 和报告保留用于定位，脚本在新一轮开始时更新当前证据。未修改失败图不重跑，不换目录清零；第二次仍失败就交 reviewer。
5. 查看成功报告及最终白底 PNG，再交付 SVG 和源码。SVG 的 `textLength` 语义见 [MDN](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/textLength)。
