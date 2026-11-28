"""校验各宿主读取的调用策略、徽章、图标及其资源。"""

import os
from pathlib import Path
import re
import struct

from skill_icon_catalog import cursor_names, load_codex_catalog

CURSOR_COLORS = {"default", "green", "cyan", "blue", "purple", "magenta", "orange", "yellow", "red", "brand"}
CODEX_ICON = re.compile(r"(?:\./)?assets/[a-z0-9]+(?:-[a-z0-9]+)*\.png")


def field_value(text, indent, field, source, *, required=True):
    # 只读取治理字段约定使用的 YAML 块映射，其他扩展字段由宿主读取。
    pattern = rf"""^{" " * indent}(['"]?){re.escape(field)}\1[ \t]*:(?=[ \t]|$)[ \t]*([^\n]*)$"""
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if not matches and not required:
        return None
    if len(matches) != 1:
        raise ValueError(f"{source} 必须有且只有一个 {field} 字段")
    match = matches[0]
    children = []
    for line in text[match.end():].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" " * (indent + 1)):
            break
        children.append(line)
    return match[2].strip(), children


def scalar_field(text, indent, field, source, *, boolean=False, required=True):
    result = field_value(text, indent, field, source, required=required)
    if result is None:
        return None
    value, children = result
    scalar = re.fullmatch(r"""("[^"\\]*"|'[^']*'|[^\s#'"]+)(?:[ \t]+#.*)?""", value)
    if not scalar or children:
        raise ValueError(f"{source}.{field} 须为单行标量")
    token = scalar[1]
    if boolean:
        if token not in {"true", "false"}:
            raise ValueError(f"{source}.{field} 须为 YAML 布尔值 true 或 false")
        return token == "true"
    return token[1:-1] if token[0] in ("'", '"') else token


def mapping_field(text, field, source):
    value, children = field_value(text, 0, field, source)
    if not children or (value and not value.startswith("#")):
        raise ValueError(f"{source}.{field} 须为 YAML 块映射")
    indent = min(len(line) - len(line.lstrip(" ")) for line in children)
    return "\n".join(children), indent


def validate_cursor_badge(frontmatter):
    icon = scalar_field(frontmatter, 0, "icon", "SKILL.md")
    if icon not in cursor_names():
        raise ValueError(f"SKILL.md 的 icon 未收录于 Cursor 图标表：{icon!r}")
    color = scalar_field(frontmatter, 0, "color", "SKILL.md")
    if color not in CURSOR_COLORS:
        raise ValueError(f"SKILL.md 的 color 未收录于 Cursor 颜色表：{color!r}")


def source_library(skill):
    for parent in skill.parents:
        if parent.name == "skills" and (parent / "registry.yaml").is_file() and (parent.parent / "workbench").is_file():
            return parent.parent / "assets/skill-icons"
    return None


def validate_icon_file(path, library, source):
    if not path.is_file():
        raise ValueError(f"{source} 的资源缺失：{path}")
    target = path.resolve()
    if library is not None:
        if (not path.is_symlink() or target.parent != library or target.suffix != ".png"
                or os.readlink(path) != os.path.relpath(target, path.parent)):
            raise ValueError(f"{source} 须通过相对链接引用仓库 assets/skill-icons/ 中的 PNG：{path}")
        if path.name != target.name:
            raise ValueError(f"{source} 的文件名须与图库母版同名：{path.name} → {target.name}")
    elif target != path:
        raise ValueError(f"{source} 须为安装包或独立 Skill 内的 PNG 实文件：{path}")

    with path.open("rb") as image:
        header = image.read(24)
    if len(header) != 24 or header[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
        raise ValueError(f"{source} 须为有效的 PNG 图像：{path}")
    width, height = struct.unpack(">II", header[16:24])
    if width != height or width == 0:
        raise ValueError(f"{source} 须使用方形 PNG 图像：{path}")


def codex_icon_path(config):
    interface, indent = mapping_field(config, "interface", "agents/openai.yaml")
    source = "agents/openai.yaml 的 interface"
    paths = []
    for field in ("icon_small", "icon_large"):
        value = scalar_field(interface, indent, field, source)
        if not CODEX_ICON.fullmatch(value):
            raise ValueError(f"{source}.{field} 须引用 ./assets/下以图标 ID 命名的 PNG")
        paths.append(Path(value))
    if paths[0] != paths[1]:
        raise ValueError(f"{source}.icon_small 和 icon_large 须引用同一个 PNG")
    return paths[0]


def validate_codex_interface(skill, config):
    interface, indent = mapping_field(config, "interface", "agents/openai.yaml")
    source = "agents/openai.yaml 的 interface"
    brand_color = scalar_field(interface, indent, "brand_color", source, required=False)
    if brand_color is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", brand_color):
        raise ValueError(f"{source}.brand_color 须为六位十六进制颜色")

    skill = skill.resolve()
    library = source_library(skill)
    validate_icon_file(skill / codex_icon_path(config), library, f"{source}.icon_small 和 icon_large")
    if library is not None:
        load_codex_catalog(library)
    if skill.name == "feipi-skill-govern":
        validate_icon_file(skill / "templates/code.png", library, "初始化图标模板")


def skill_frontmatter(entry):
    lines = entry.read_text(encoding="utf-8").splitlines(keepends=True)
    end = next((index for index, line in enumerate(lines[1:], 1) if line.rstrip("\n") == "---"), None)
    if lines[:1] != ["---\n"] or end is None:
        raise ValueError("SKILL.md 缺少完整的 Frontmatter")
    return lines[0], "".join(lines[1:end]), "".join(lines[end:])


def validate_host_metadata(skill):
    _, frontmatter, _ = skill_frontmatter(skill / "SKILL.md")
    validate_cursor_badge(frontmatter)
    disabled = scalar_field(frontmatter, 0, "disable-model-invocation", "SKILL.md", boolean=True)
    if skill.name.endswith("-mode") and not disabled:
        raise ValueError("工作模式须声明 disable-model-invocation: true")
    if disabled and scalar_field(frontmatter, 0, "user-invocable", "SKILL.md",
                                 boolean=True, required=False) is False:
        raise ValueError("仅手动调用的 Skill 须保留 user-invocable: true")

    config = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
    policy, indent = mapping_field(config, "policy", "agents/openai.yaml")
    allowed = scalar_field(policy, indent, "allow_implicit_invocation", "agents/openai.yaml policy", boolean=True)
    if allowed == disabled:
        raise ValueError("SKILL.md 的 disable-model-invocation 与 agents/openai.yaml 的 "
                         "policy.allow_implicit_invocation 必须互为相反的布尔值")

    validate_codex_interface(skill, config)
