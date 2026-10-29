# 图包合同 v1

图包包含 brief.json、diagram.mmd、diagram.svg、diagram.png、render-evidence.json、explanation.md、validation.json；组件细化还有 evidence/overview.json。路径固定在包内，hash 绑定所有工件；父图路径不能是绝对路径或逃出输入目录。

状态由入口内部推导：blocked / review_required / success。前四个检查 brief、coverage、render、layout 都必须 passed，真实图像、geometry、metrics、renderer 身份和最终 verifier 都一致后才进入 review_required；人工查看并登记结论才能 success。普通工作流不需重复运行 verifier，独立审计可执行 `python3 scripts/verify_package.py package`。

- typed 源码必须与 brief 的确定性生成结果一致（忽略普通注释和行首尾空白），由此拒绝漏节点、增节点、错关系、消息重排、文本失真及隐藏指令。
- 通用源码只执行语法与 expected_text 检查，必须额外人工语义验收。
- 几何证据来自最终 SVG 的浏览器 DOM，使用实际文字包围盒与每2px采样的关系线。复核裁切、文字重叠及关系穿字；flowchart 边标签具有遮罩，仅排除带背景标签与其所属边的交叉。原生 mindmap 的边在节点底色下连接中心，排除本边两端节点内被遮住的部分，仍检查第三方文字与节点区域。分组标题移至左上角，画布按真实文字边界补足留白。此检测不能证明无所有视觉问题，人工仍须检查遮罩归属、字体、箭头与拥挤程度。
- 原生图型的渲染细节可能不被全部几何选择器覆盖。只承诺已采集的 geometry，不能将没有线段证据当作所有连线通过；通用图必须人工检查关系。
- 修改输入或实现合同即缓存失效。`--reuse` 首先只读验证旧包，再更新 last_run 计数并复核一次。损坏包返回 blocked，不修补 hash 冒充缓存成功。
- `timings.total_ms` 从入口开始到报告物化前；render_ms 含渲染子进程及 PNG/几何提取，static_ms 含其他工作及浏览器预检；不含最终报告落盘与 verifier。历史 timings/counters 保留；缓存 last_run 的 render_calls=0、verifier_calls=2、cache_hits=1。
- 每包保存已消耗次数，最多2次；渲染前冻结次数，中断也保留。失败输入未变不允许再次渲染；不得以换目录规避上限。
- 失败移除 SVG/PNG 与几何文件，保留源码和报告，不把旧图当结果。无法可靠检查或未完成人工复核都不能宣称交付成功。
