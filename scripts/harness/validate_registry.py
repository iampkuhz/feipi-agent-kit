#!/usr/bin/env python3
"""Validate skill registry (skills/registry.yaml)."""
import os
import sys
import re
import shlex


REQUIRED_SKILL_FIELDS = ("name", "path", "layer", "description", "clients", "entry", "validation", "status")
VALID_LAYERS = {"authoring", "diagram", "integration"}
VALID_STATUS = {"stable", "compatibility"}
VALID_VALIDATION_TYPES = {"script", "none"}


def find_repo_root():
    """Find repository root directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(script_dir, "..", ".."))


def try_parse_yaml_simple(text):
    """Minimal YAML-like parser for the registry structure.
    Handles the specific flat list format of skills/registry.yaml.
    """
    skills = []
    current = {}

    for line in text.splitlines():
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            # If we hit a new list item marker on the next non-comment line, save current
            continue

        # New list item: "- name: ..."
        if stripped.startswith("- "):
            if current:
                skills.append(current)
            current = {}
            stripped = stripped[2:].strip()

        # Key-value pair
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key in ("name", "path", "layer", "description", "entry", "status"):
                current[key] = value
            elif key == "clients":
                current["clients"] = [item.strip() for item in value.strip("[]").split(",") if item.strip()]
            elif key == "validation" and value in ("null", "none", ""):
                current["validation"] = None
            elif key == "type":
                current["validation_type"] = value
            elif key == "command":
                current["validation_command"] = value

    if current:
        skills.append(current)

    return skills


def parse_registry(root):
    """Parse skills/registry.yaml, trying PyYAML first, fallback to simple parser."""
    reg_path = os.path.join(root, "skills", "registry.yaml")

    skills = None

    try:
        import yaml
    except ImportError:
        with open(reg_path, "r", encoding="utf-8") as f:
            text = f.read()
        return try_parse_yaml_simple(text)

    try:
        with open(reg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        print(f"  [FAIL] Cannot parse skills/registry.yaml: {exc}")
        return None

    if not isinstance(data, dict):
        print("  [FAIL] skills/registry.yaml must be a mapping")
        return None

    skills = data.get("skills")
    if not isinstance(skills, list):
        print("  [FAIL] skills/registry.yaml field 'skills' must be a list")
        return None

    return skills


def check_registry_exists(root):
    """Check that skills/registry.yaml exists."""
    path = os.path.join(root, "skills", "registry.yaml")
    if os.path.isfile(path):
        print(f"  [PASS] skills/registry.yaml exists")
        return True
    else:
        print(f"  [FAIL] skills/registry.yaml not found")
        return False


def get_validation_info(skill):
    """Return (validation_present, validation_type, validation_command)."""
    if "validation" in skill:
        val = skill.get("validation")
        if val is None:
            return True, "none", ""
        if isinstance(val, dict):
            return True, val.get("type", ""), val.get("command", "")
        return True, "", ""

    if "validation_type" in skill or "validation_command" in skill:
        return True, skill.get("validation_type", ""), skill.get("validation_command", "")

    return False, "", ""


def check_skill_metadata(skills):
    """Check required registry metadata before filesystem checks."""
    all_ok = True
    seen_names = set()
    seen_paths = set()

    for skill in skills:
        name = skill.get("name", "<unknown>")

        for field in REQUIRED_SKILL_FIELDS:
            if field == "validation":
                present, _, _ = get_validation_info(skill)
                if not present:
                    print(f"  [FAIL] Skill '{name}' missing required field: validation")
                    all_ok = False
                continue

            value = skill.get(field)
            if value in (None, "") or (field == "clients" and not value):
                print(f"  [FAIL] Skill '{name}' missing required field: {field}")
                all_ok = False

        if name in seen_names:
            print(f"  [FAIL] Duplicate skill name: {name}")
            all_ok = False
        seen_names.add(name)

        path = skill.get("path", "")
        if path in seen_paths:
            print(f"  [FAIL] Duplicate skill path: {path}")
            all_ok = False
        seen_paths.add(path)

        if name != "<unknown>" and not re.match(r"^feipi-[a-z0-9-]+$", name):
            print(f"  [FAIL] Skill '{name}' name does not match feipi-* kebab-case")
            all_ok = False

        layer = skill.get("layer")
        if layer and layer not in VALID_LAYERS:
            print(f"  [FAIL] Skill '{name}' has invalid layer: {layer}")
            all_ok = False

        clients = skill.get("clients")
        if clients and not isinstance(clients, list):
            print(f"  [FAIL] Skill '{name}' clients must be a list")
            all_ok = False

        status = skill.get("status")
        if status and status not in VALID_STATUS:
            print(f"  [FAIL] Skill '{name}' has invalid status: {status}")
            all_ok = False

        _, val_type, val_cmd = get_validation_info(skill)
        if val_type and val_type not in VALID_VALIDATION_TYPES:
            print(f"  [FAIL] Skill '{name}' has invalid validation type: {val_type}")
            all_ok = False
        if val_type == "script" and not val_cmd:
            print(f"  [FAIL] Skill '{name}' has validation type 'script' but no command")
            all_ok = False

    return all_ok


def check_skill_paths(root, skills):
    """Check each skill's path directory and SKILL.md entry exist."""
    all_ok = True

    for skill in skills:
        name = skill.get("name", "<unknown>")
        path = skill.get("path", "")
        entry = skill.get("entry", "SKILL.md")

        if not path:
            print(f"  [FAIL] Skill '{name}' has no path")
            all_ok = False
            continue

        full_dir = os.path.join(root, path)
        if os.path.isdir(full_dir):
            print(f"  [PASS] Skill '{name}' directory exists: {path}")
        else:
            print(f"  [FAIL] Skill '{name}' directory missing: {path}")
            all_ok = False
            continue

        # Check entry file
        entry_path = os.path.join(full_dir, entry)
        if os.path.isfile(entry_path):
            print(f"  [PASS] Skill '{name}' entry exists: {path}/{entry}")
        else:
            print(f"  [FAIL] Skill '{name}' entry missing: {path}/{entry}")
            all_ok = False

    return all_ok


def check_validation_scripts(root, skills):
    """If validation.type is 'script', check the script path exists.

    Handles both:
      - Nested dict from PyYAML: skill["validation"]["type"] / ["command"]
      - Flat keys from fallback parser: skill["validation_type"] / ["validation_command"]
    """
    all_ok = True

    for skill in skills:
        name = skill.get("name", "<unknown>")
        _, val_type, val_cmd = get_validation_info(skill)

        if not val_type or val_type != "script":
            continue

        if not val_cmd:
            # check_skill_metadata reports the missing command as the contract error.
            continue

        script_path = validation_script_path(val_cmd)
        if not script_path:
            print(f"  [FAIL] Skill '{name}' validation command does not identify a script: {val_cmd}")
            all_ok = False
            continue

        full_script = os.path.join(root, script_path)
        if os.path.isfile(full_script):
            print(f"  [PASS] Skill '{name}' validation script exists: {script_path}")
        else:
            print(f"  [FAIL] Skill '{name}' validation script missing: {script_path}")
            all_ok = False

    return all_ok


def validation_script_path(command):
    """Find the executable script operand, ignoring later arguments.

    Registry commands may pass a target directory after the script, for example
    ``bash scripts/validate.sh skills/integration/example``. The previous
    implementation selected the final token and mistook that directory for the
    validation script.
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        return ""
    if not parts:
        return ""

    for index, part in enumerate(parts):
        if re.search(r"\.(?:sh|py|js|mjs|cjs)$", part):
            return part
    return ""


def main():
    root = find_repo_root()
    print("=== Registry Validation ===")

    results = []
    results.append(check_registry_exists(root))

    reg_path = os.path.join(root, "skills", "registry.yaml")
    if not os.path.isfile(reg_path):
        print("Registry validation: FAIL (registry file missing)")
        return 1

    skills = parse_registry(root)
    if skills is None:
        print("Registry validation: FAIL (registry parse error)")
        return 1

    if not skills:
        print("  [FAIL] No skills found in registry")
        print("Registry validation: FAIL")
        return 1

    print(f"  [INFO] Found {len(skills)} skill(s) in registry")
    results.append(check_skill_metadata(skills))
    results.append(check_skill_paths(root, skills))
    results.append(check_validation_scripts(root, skills))

    if all(results):
        print("Registry validation: PASS")
        return 0
    else:
        print("Registry validation: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
