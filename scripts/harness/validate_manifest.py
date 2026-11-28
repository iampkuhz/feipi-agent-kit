#!/usr/bin/env python3
"""Validate harness manifest (harness/manifest.yaml)."""
import os
import sys
import re
import json


def find_repo_root():
    """Find repository root directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(script_dir, "..", ".."))


def try_parse_manifest_simple(text):
    """Minimal YAML-like parser for the manifest structure."""
    result = {
        "entrypoints": [],
        "rules": [],
        "skill_registry": None,
        "workflows": [],
        "validation_scripts": [],
        "validation_doctor": None,
        "local_config_files": [],
    }

    current_section = None
    current_item = {}

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if line.startswith("skill_registry:"):
            result["skill_registry"] = line.split(":", 1)[1].strip().strip('"').strip("'")
            continue

        # Detect top-level sections
        top_match = re.match(r'^(\w[\w_]*):\s*$', line)
        if top_match:
            section_name = top_match.group(1)
            if current_item:
                if current_section == "entrypoints":
                    result["entrypoints"].append(current_item)
                elif current_section == "rules":
                    result["rules"].append(current_item)
                elif current_section == "workflows":
                    result["workflows"].append(current_item)
                elif current_section == "validation":
                    if "path" in current_item and "description" in current_item:
                        result["validation_scripts"].append(current_item)
                elif current_section == "local_config":
                    result["local_config_files"].append(current_item)
            current_item = {}
            current_section = section_name
            continue

        # Detect list item start
        if stripped.startswith("- "):
            if current_item and "path" in current_item:
                if current_section == "entrypoints":
                    result["entrypoints"].append(current_item)
                elif current_section == "rules":
                    result["rules"].append(current_item)
                elif current_section == "workflows":
                    result["workflows"].append(current_item)
                elif current_section == "validation" and "description" in current_item:
                    result["validation_scripts"].append(current_item)
                elif current_section == "local_config":
                    result["local_config_files"].append(current_item)
            current_item = {}
            stripped = stripped[2:].strip()

        # Key-value pairs within items
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key in ("path", "type", "description", "name", "scope", "policy"):
                current_item[key] = value

    # Don't forget the last item
    if current_item and "path" in current_item:
        if current_section == "entrypoints":
            result["entrypoints"].append(current_item)
        elif current_section == "rules":
            result["rules"].append(current_item)
        elif current_section == "workflows":
            result["workflows"].append(current_item)
        elif current_section == "validation" and "description" in current_item:
            result["validation_scripts"].append(current_item)
        elif current_section == "local_config":
            result["local_config_files"].append(current_item)

    # Check for validation.doctor path
    in_validation = False
    in_doctor = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r'^validation:\s*$', line):
            in_validation = True
            in_doctor = False
            continue
        if in_validation and re.match(r'^  doctor:\s*$', line):
            in_doctor = True
            continue
        if in_validation and in_doctor:
            m = re.match(r'\s+path:\s*(.+)', line)
            if m:
                result["validation_doctor"] = m.group(1).strip().strip('"').strip("'")
                break
            if re.match(r'^\w', line) and not line.startswith(" "):
                break

    return result


def parse_manifest(root):
    """Parse harness/manifest.yaml, trying PyYAML first, fallback to simple parser."""
    manifest_path = os.path.join(root, "harness", "manifest.yaml")

    data = None

    # Try PyYAML
    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except ImportError:
        pass
    except Exception:
        pass

    if data is None:
        # Fallback
        with open(manifest_path, "r", encoding="utf-8") as f:
            text = f.read()
        data = try_parse_manifest_simple(text)

    return data


def collect_paths(data):
    """Collect all file/dir paths referenced in the manifest.

    Handles both:
    - PyYAML parsed dict: nested structure (commands, validation, local_config)
    - Fallback parser: flat keys (validation_scripts, validation_doctor, local_config_files)
    """
    paths = []

    # Entrypoints
    for ep in data.get("entrypoints", []):
        if "path" in ep:
            paths.append(("entrypoint", ep["path"]))

    # Rules
    for rule in data.get("rules", []):
        if "path" in rule:
            paths.append(("rule", rule["path"]))

    # Skills use the shared registry instead of a second metadata list.
    if data.get("skill_registry"):
        paths.append(("skill_registry", data["skill_registry"]))

    # Workflows
    for wf in data.get("workflows", []):
        if "path" in wf:
            paths.append(("workflow", wf["path"]))

    # Commands — PyYAML nested structure
    commands = data.get("commands", {})
    if isinstance(commands, dict):
        readme = commands.get("readme")
        if readme:
            paths.append(("command_readme", readme))
        for d in commands.get("reserved_dirs", []):
            paths.append(("command_dir", d))
    # Fallback: flat keys from simple parser
    elif commands and "path" in commands:
        paths.append(("command", commands["path"]))

    # Validation — new flat-list structure: [{name, script, description}]
    validation = data.get("validation", [])
    if isinstance(validation, list):
        for v in validation:
            script = v.get("script")
            if script:
                paths.append(("validation", script))
    # Legacy nested dict structure (backwards compat)
    elif isinstance(validation, dict):
        for vs in validation.get("scripts", []):
            if "path" in vs:
                paths.append(("validation", vs["path"]))
        doctor = validation.get("doctor")
        if isinstance(doctor, dict) and doctor.get("path"):
            paths.append(("validation_doctor", doctor["path"]))
    # Fallback: flat keys from simple parser
    for vs in data.get("validation_scripts", []):
        if "path" in vs:
            paths.append(("validation", vs["path"]))
    if data.get("validation_doctor"):
        paths.append(("validation_doctor", data["validation_doctor"]))

    # Local config — PyYAML nested structure
    local_config = data.get("local_config", {})
    if isinstance(local_config, dict):
        for lc in local_config.get("files", []):
            if "path" in lc:
                paths.append(("local_config", lc["path"]))
    # Fallback: flat keys from simple parser
    elif local_config and "path" in local_config:
        paths.append(("local_config", local_config["path"]))

    for lc in data.get("local_config_files", []):
        if "path" in lc:
            paths.append(("local_config", lc["path"]))

    return paths


def check_manifest_exists(root):
    """Check that harness/manifest.yaml exists."""
    path = os.path.join(root, "harness", "manifest.yaml")
    if os.path.isfile(path):
        print(f"  [PASS] harness/manifest.yaml exists")
        return True
    else:
        print(f"  [FAIL] harness/manifest.yaml not found")
        return False


def check_referenced_paths_exist(root, path_list):
    """Check all referenced paths exist as files or directories."""
    all_ok = True

    for label, rel_path in path_list:
        full_path = os.path.join(root, rel_path)
        if os.path.exists(full_path):
            print(f"  [PASS] {label} path exists: {rel_path}")
        else:
            print(f"  [FAIL] {label} path missing: {rel_path}")
            all_ok = False

    return all_ok


def check_schema_files(root, data):
    """Check that referenced JSON schema files are parseable."""
    # Check the manifest schema itself
    schema_path = os.path.join(root, "harness", "schemas", "harness-manifest.schema.json")
    if os.path.isfile(schema_path):
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                json.load(f)
            print(f"  [PASS] Schema file parseable: harness/schemas/harness-manifest.schema.json")
            return True
        except json.JSONDecodeError as e:
            print(f"  [FAIL] Schema file not parseable: harness/schemas/harness-manifest.schema.json ({e})")
            return False
    else:
        print(f"  [SKIP] Schema file not found (optional): harness/schemas/harness-manifest.schema.json")
        return True


def check_workflows_exist(root, data):
    """Check workflow files listed in manifest exist."""
    workflows = data.get("workflows", [])
    if not workflows:
        print(f"  [INFO] No workflows defined in manifest")
        return True

    all_ok = True
    for wf in workflows:
        path = wf.get("path", "")
        name = wf.get("name", "<unknown>")
        full_path = os.path.join(root, path)

        if os.path.isfile(full_path):
            print(f"  [PASS] Workflow file exists: {path}")
        else:
            print(f"  [FAIL] Workflow file missing: {path}")
            all_ok = False

    return all_ok


def main():
    root = find_repo_root()
    print("=== Manifest Validation ===")

    results = []
    results.append(check_manifest_exists(root))

    manifest_path = os.path.join(root, "harness", "manifest.yaml")
    if not os.path.isfile(manifest_path):
        print("Manifest validation: FAIL (manifest file missing)")
        return 1

    data = parse_manifest(root)
    path_list = collect_paths(data)

    results.append(check_referenced_paths_exist(root, path_list))
    results.append(check_schema_files(root, data))
    results.append(check_workflows_exist(root, data))

    if all(results):
        print("Manifest validation: PASS")
        return 0
    else:
        print("Manifest validation: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
