#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown-it-py==4.0.0"]
# ///
"""生成离线 Skill 审阅页，核对确认所绑定的候选版本。"""

import argparse
import difflib
from hashlib import sha256
import html
import json
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import unquote, urlsplit

from check_delivery import digest, nonempty, require


EXCLUDED = {"__pycache__", ".git", ".DS_Store", "node_modules"}
TEXT = {".md", ".sh", ".py", ".json", ".tsv", ".yaml", ".yml", ".toml", ".txt", ".js"}
STYLE = """
body{margin:0;background:#faf9f5;color:#183235;font:16px/1.65 system-ui,sans-serif;overflow-wrap:anywhere}
header{background:#16363e;color:white;padding:1.35rem max(1rem,calc((100vw - 1060px)/2))}
main{max-width:1060px;margin:auto;padding:1.25rem 1rem 3rem}
h1,h2,h3{line-height:1.25}h1{margin:.5rem 0}p{margin:.45rem 0 1rem}
a{color:#175d61;text-underline-offset:3px}section{padding:1rem 0;border-bottom:1px solid #cddbd5}
nav{display:flex;flex-wrap:wrap;gap:.5rem 1.25rem;font-size:.9rem}
pre{overflow-wrap:normal;background:#edf2ee;padding:.85rem;overflow:auto;border-radius:3px}
code{overflow-wrap:anywhere}summary{cursor:pointer;font-weight:650;color:#175d61;overflow-wrap:anywhere}
details{padding:.55rem 0;border-bottom:1px solid #e0e8e2}table{border-collapse:collapse;display:block;overflow:auto}
th,td{border:1px solid #cddbd5;padding:.32rem .55rem;vertical-align:top}th{background:#e9f0ea}
header small{color:#d1e8e3}.evidence{background:#edf2ee;padding:.65rem .85rem;border-left:3px solid #4d8276}
:focus-visible{outline:2px solid #ab4f21;outline-offset:3px}
"""


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        parts = path.relative_to(root).parts
        if EXCLUDED.intersection(parts):
            continue
        require(not path.is_symlink(), f"审阅候选不能包含符号链接：{path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
    require("SKILL.md" in result, f"缺少 Skill 入口：{root}")
    return result


def fingerprint(files, context_digest):
    payload = {"files": files, "context_sha256": context_digest}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def review_context(context, workspace=None):
    data = json.loads(read(context))
    require(isinstance(data, dict), "审阅资料必须是对象")
    shared = data.get("shared_files", {})
    require(isinstance(shared, dict), "共享文件需声明路径和 SHA-256")
    if shared:
        require(workspace is not None, "核对共享文件需要 --workspace")
        root = workspace.resolve()
        for name, expected in shared.items():
            path = root / name
            require(not Path(name).is_absolute() and path.resolve().is_relative_to(root),
                    f"共享路径超出工作区：{name}")
            require(path.is_file() and digest(path) == expected,
                    f"共享文件已变或缺失：{name}")
    if data.get("shared_diff"):
        require(bool(shared), "共享改动必须登记实际文件")
    return data


def verify_approval(skill, context, approval, workspace=None):
    review_context(context, workspace)
    data = json.loads(approval.read_text(encoding="utf-8"))
    require(isinstance(data, dict) and data.get("status") == "approved", "候选尚无人工确认")
    require(data.get("skill") == skill.name and nonempty(data.get("evidence")),
            "人工确认缺少对应 Skill 或确认出处")
    candidate = fingerprint(inventory(skill), digest(context))
    require(data.get("fingerprint") == candidate, "审阅后候选或审阅资料已变，需要重新确认")
    return candidate


def read(path):
    return path.read_text(encoding="utf-8")


def metadata(text, name):
    frontmatter = text.split("---", 2)[1] if text.startswith("---\n") else ""
    value = re.search(rf"(?m)^{re.escape(name)}:\s*(.+)$", frontmatter)
    return value.group(1).strip().strip('"').strip("'") if value else ""


def render(skill, baseline, context, out, workspace=None):
    # Markdown-it is needed for rendering only. Approval checks use the standard library.
    from markdown_it import MarkdownIt

    data = review_context(context, workspace)
    for key in ("relationships", "project_references", "host_dependencies", "verification"):
        require(isinstance(data.get(key), list) and all(nonempty(item) for item in data[key]),
                f"审阅资料缺少字符串列表：{key}")
    files = inventory(skill)
    candidate = fingerprint(files, digest(context))
    require(not out.exists(), f"审阅快照目录已存在：{out}")
    out.mkdir(parents=True)
    snapshot = out / "snapshot"
    for relative in files:
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill / relative, destination)
    require(inventory(snapshot) == files, "生成期间候选文件发生变化")
    shutil.copy2(context, out / "context.json")
    require(fingerprint(files, digest(out / "context.json")) == candidate, "生成期间审阅资料发生变化")
    info = {"skill": skill.name, "status": "pending", "fingerprint": candidate, "files": files}
    (out / "review.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    escape = html.escape
    markdown = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
    entry = read(snapshot / "SKILL.md")
    description = metadata(entry, "description")
    interface = snapshot / "agents/openai.yaml"
    version = metadata("---\n" + read(interface) + "\n---", "version") if interface.is_file() else ""
    version_label = f" · v{html.escape(version)}" if version else ""
    require(bool(description) and metadata(entry, "name") == skill.name,
            "SKILL.md 缺少 Description 或 Name 与目录不一致")
    # Snapshot files remain browsable from the review without depending on a checkout.
    def code(text):
        return "<pre><code>" + escape(text) + "</code></pre>"

    names = {"relationships": "Skill 调用与消费者", "project_references": "项目 Reference",
             "host_dependencies": "宿主和插件依赖", "verification": "验证结果与待验证项"}
    summaries = ""
    for key, title in names.items():
        items = data[key] or ["本候选无此项。"]
        summaries += "<h3>" + title + "</h3><ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"

    changes = []
    baseline_files = inventory(baseline) if baseline else {}
    for relative in sorted(set(files) | set(baseline_files)):
        if files.get(relative) == baseline_files.get(relative) or Path(relative).suffix not in TEXT:
            continue
        before = read(baseline / relative) if relative in baseline_files else ""
        after = read(snapshot / relative) if relative in files else ""
        patch = "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                               relative + " 旧版", relative + " 候选", lineterm=""))
        changes.append(f"<details><summary>{escape(relative)}</summary>{code(patch)}</details>")

    shared = data.get("shared_diff")
    if shared:
        require(isinstance(shared, str), "共享改动必须是文本差异")
        changes.append("<details><summary>展开共享安装器和版本记录的改动</summary>"
                       + code(shared) + "</details>")

    panels = []
    sections = {path: f"file-{index}" for index, path in enumerate(files, 1)}

    def render_link(renderer, tokens, index, options, env):
        token = tokens[index]
        parsed = urlsplit(token.attrGet("href") or "")
        if not parsed.scheme and not parsed.netloc:
            target = posixpath.normpath(posixpath.join(
                posixpath.dirname(env["file"]), unquote(parsed.path))) if parsed.path else env["file"]
            if target in sections:
                token.attrSet("href", "#" + sections[target])
            else:
                token.attrs.pop("href", None)
                token.attrSet("title", "此文件在候选快照之外")
        return renderer.renderToken(tokens, index, options, env)

    markdown.add_render_rule("link_open", render_link)
    for relative in files:
        path = snapshot / relative
        if path.suffix not in TEXT:
            content = f'<p><a href="{escape(path.relative_to(out).as_posix(), quote=True)}">查看快照文件</a></p>'
        else:
            raw = read(path)
            body = raw.split("---", 2)[2] if relative == "SKILL.md" and raw.startswith("---\n") else raw
            content = markdown.render(body, {"file": relative}) + f'<details><summary>打开原文</summary>{code(raw)}</details>' if path.suffix == ".md" else code(raw)
        panels.append(f"<details id=\"{sections[relative]}\"{' open' if relative == 'SKILL.md' else ''}><summary>{escape(relative)}</summary>{content}</details>")

    references = []
    for relative, section in sections.items():
        if relative.startswith("references/") and relative.endswith(".md"):
            first_heading = next((line[2:].strip() for line in read(snapshot / relative).splitlines()
                                  if line.startswith("# ")), relative)
            references.append(f'<li><a href="#{section}">{escape(first_heading)}</a> <code>{escape(relative)}</code></li>')
    reference_list = ("<h3>Reference 索引</h3><ul>" + "".join(references) + "</ul>") if references else ""

    display = escape(skill.name)
    doc = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{display} · Skill 审阅</title><style>{STYLE}</style>
<header><small>Feipi Agent Kit{version_label} · 待人工审阅</small><h1>{display}</h1>
<p>{escape(description)}</p></header><main>
<nav aria-label="审阅导航"><a href="#scope">调用与验证</a><a href="#entry">入口与文件</a><a href="#changes">查看改动</a><a href="#approval">审阅确认</a></nav>
<section id="scope"><h2>调用、资料与验收</h2>{summaries}</section>
<section id="entry"><h2>完整文件清单与内容</h2>{reference_list}{''.join(panels)}</section>
<section id="changes"><h2>与基线的改动</h2>{''.join(changes) or '<p>本次无可显示的文本差异。</p>'}</section>
<section id="approval"><h2>审阅确认</h2>
<p>可在 Codex 聊天中按文件反馈，或确认这份候选。确认记录绑定以下指纹。</p>
<p class="evidence"><code>{candidate}</code></p>
<p><a href="review.json">候选明细</a> · <a href="context.json">审阅资料</a></p>
</section></main><script>
function revealLinkedFile() {{
  const panel = document.getElementById(location.hash.slice(1));
  if (panel instanceof HTMLDetailsElement) {{ panel.open = true; panel.scrollIntoView(); }}
}}
window.addEventListener('hashchange', revealLinkedFile);
revealLinkedFile();
</script></html>"""
    (out / "index.html").write_text(doc, encoding="utf-8")
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--workspace", type=Path, help="有共享改动时核对实际文件的源码工作区")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--out", type=Path)
    operation.add_argument("--check-approval", type=Path)
    args = parser.parse_args()
    try:
        if args.out:
            candidate = render(args.skill, args.baseline, args.context, args.out, args.workspace)
            print(args.out / "index.html")
        else:
            candidate = verify_approval(args.skill, args.context, args.check_approval, args.workspace)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"[FAIL] {error}\n")
    print(candidate)


if __name__ == "__main__":
    main()
