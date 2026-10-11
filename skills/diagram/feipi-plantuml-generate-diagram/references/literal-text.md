# 图中显示文本

六个 typed profile（`architecture`、`sequence`、`component`、`activity`、`deployment`、`mindmap`）共用 `scripts/lib/text_codec.py`。它只处理已确定为展示内容的值，不解析或重写整段 PlantUML 源码。PlantUML Creole 支持所有图型；Unicode 转义依据官方 [Creole](https://plantuml.com/creole) 与 [Unicode](https://plantuml.com/unicode) 文档。

## 编码与解析边界

- 对显示标签调用 `encode_display_text()`，将可能影响 Creole、引号或图语法的标点写为 PlantUML `<U+XXXX>` 转义；普通字母、数字、空白与中文保持原样。多行文本默认将每个显示行的首个 ASCII 字母也编码，避免 note 中的 `end note`、`actor` 等文本解释为结构；mindmap 节点已经由层级标记定界，不需要该保护。真实 LF 编码为图型标签使用的 `\n`。
- 命令、定界符、语法关键字、箭头、结构 ID、alias、颜色和其他结构字段不编码。把 codec 当作显示文本 helper，而不是安全化任意源码的工具。
- Coverage 必须先用对应图型 parser 识别声明、消息、活动步骤或树节点，再对取得的显示字段调用 `decode_display_text()`，最后与 brief 原始值比较。禁止先 decode 整份源码；禁止递归 decode。Brief 中字面 `<U+0041>`、字面反斜杠加 `n` 都是普通输入，必须先编码再落到 PUML。
- `scripts/encode_display_text.py` 可由标准输入或 `--text` 接受原始显示文本；它不会识别 PUML 结构。
- 控制字符、隐藏格式字符、surrogate 与 U+2028/U+2029 非 LF 行分隔符拒绝；LF 是唯一受支持的多行分隔符。预算仍由各 profile 的原有规则负责。
- 时序 note 的换行布局针对原始 brief 文本计算；实际 LF 表示换行，字面 `\n` 是两个字面字符。输出 PUML 时再编码每个排版行；每行首字母转义避免 `end note` 或其他结构关键字结束显示块或注入新结构。

## 示例

```python
from lib.text_codec import encode_display_text

label = encode_display_text('文件 "__main__.py" [x]')
```

手写已注册图型时，同样只将显示字段替换为 helper 输出；parser 解析出字段后再 decode 参与 coverage 比较。编码不放宽控制字符、coverage、budget 或语法注入检查。
