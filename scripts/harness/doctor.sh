#!/usr/bin/env bash
# scripts/harness/doctor.sh
# Master entry point: runs all harness validators, returns clear exit code.
# Offline only — no network, no service ports.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

overall=0

run_check() {
    local label="$1"
    local script="$2"

    echo ""
    echo "--- $label ---"

    if python3 "$script"; then
        echo -e "  ${GREEN}[PASS]${NC} $label"
    else
        echo -e "  ${RED}[FAIL]${NC} $label"
        overall=1
    fi
}

echo "============================================"
echo "  Feipi Agent Kit — Harness Doctor"
echo "============================================"
echo "Repo root: $REPO_ROOT"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"

run_check "Rules Validation" "$SCRIPT_DIR/validate_rules.py"
run_check "Commands Validation" "$SCRIPT_DIR/validate_commands.py"
run_check "Registry Validation" "$SCRIPT_DIR/validate_registry.py"
run_check "Manifest Validation" "$SCRIPT_DIR/validate_manifest.py"
run_check "Skill Layout and Install Filtering" "$SCRIPT_DIR/validate_skill_layout.py"

echo ""
echo "============================================"
if [ $overall -eq 0 ]; then
    echo -e "  ${GREEN}All checks passed.${NC}"
else
    echo -e "  ${RED}Some checks failed. Review output above.${NC}"
fi
echo "============================================"

exit $overall
