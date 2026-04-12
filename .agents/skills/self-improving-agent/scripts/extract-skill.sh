#!/bin/bash
# Scaffold a workspace-compliant skill from a proven learning.
# This helper generates the minimum Pete workspace layout:
#   <skill>/SKILL.md
#   <skill>/references/output-template.md
#   <skill>/agents/openai.yaml

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

usage() {
    cat << 'EOF'
Usage: extract-skill.sh <skill-name> [options]

Scaffold a workspace-compliant skill from a proven learning.

Arguments:
  skill-name     Lowercase skill slug using letters, numbers, and hyphens

Options:
  --dry-run      Show what would be created without writing files
  --output-dir   Relative output directory under the current workspace
                 Default: ./tools/SKILLS/folders if it exists, otherwise ./skills
  -h, --help     Show this help message

Examples:
  extract-skill.sh pnpm-workspace-gotchas --dry-run
  extract-skill.sh api-timeout-patterns
  extract-skill.sh docker-m1-fixes --output-dir ./tools/SKILLS/folders
EOF
}

SKILL_NAME=""
DRY_RUN=false

if [ -d "./SKILLS/folders" ]; then
    OUTPUT_DIR="./SKILLS/folders"
elif [ -d "./tools/SKILLS/folders" ]; then
    OUTPUT_DIR="./tools/SKILLS/folders"
else
    OUTPUT_DIR="./skills"
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --output-dir)
            if [ -z "${2:-}" ] || [[ "${2:-}" == -* ]]; then
                log_error "--output-dir requires a relative path argument"
                usage
                exit 1
            fi
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [ -n "$SKILL_NAME" ]; then
                log_error "Unexpected argument: $1"
                usage
                exit 1
            fi
            SKILL_NAME="$1"
            shift
            ;;
    esac
done

if [ -z "$SKILL_NAME" ]; then
    log_error "Skill name is required"
    usage
    exit 1
fi

if ! [[ "$SKILL_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    log_error "Invalid skill name. Use lowercase letters, numbers, and hyphens only."
    exit 1
fi

if [[ "$OUTPUT_DIR" = /* ]] || [[ "$OUTPUT_DIR" =~ (^|/)\.\.(/|$) ]]; then
    log_error "Output directory must be a relative path inside the current workspace."
    exit 1
fi

OUTPUT_DIR="${OUTPUT_DIR#./}"
OUTPUT_DIR="./$OUTPUT_DIR"
SKILL_PATH="$OUTPUT_DIR/$SKILL_NAME"
DISPLAY_NAME="$(echo "$SKILL_NAME" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')"

if [ -e "$SKILL_PATH" ] && [ "$DRY_RUN" = false ]; then
    log_error "Target already exists: $SKILL_PATH"
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    log_info "Dry run - would create:"
    echo "  $SKILL_PATH/"
    echo "  $SKILL_PATH/SKILL.md"
    echo "  $SKILL_PATH/references/output-template.md"
    echo "  $SKILL_PATH/agents/openai.yaml"
    echo ""
    echo "Notes:"
    echo "  - This is only a scaffold. Finish the skill against SKILLS/SKILL_STANDARD.md."
    echo "  - Package later from tools/SKILLS/folders/$SKILL_NAME into tools/SKILLS/packages/$SKILL_NAME.skill."
    exit 0
fi

mkdir -p "$SKILL_PATH/references" "$SKILL_PATH/agents"

cat > "$SKILL_PATH/SKILL.md" << EOF
---
name: $SKILL_NAME
description: >
  [TODO: State what this skill does, when to use it, and its trigger surface.]
---

# $DISPLAY_NAME

[TODO: One-sentence purpose.]

## Output Location

[TODO: If the skill writes files, state the exact path, naming rule, and format.
If it does not write files, say so plainly.]

## Workflow

1. [TODO: Step one]
2. [TODO: Step two]
3. [TODO: Verification or handoff step]

## References

- \`references/output-template.md\` - [TODO: say when to read it]

## Failure Modes

- [TODO: main guardrail]
- [TODO: main edge case]
EOF

cat > "$SKILL_PATH/references/output-template.md" << 'EOF'
# Output Template

[TODO: Put the durable schema, routing rules, template, or decision table here instead of
copying large reference blocks into SKILL.md.]
EOF

cat > "$SKILL_PATH/agents/openai.yaml" << EOF
interface:
  display_name: "$DISPLAY_NAME"
  short_description: "[TODO: Short UI description.]"
  default_prompt: "Use \$$SKILL_NAME for [TODO: default invocation guidance]."

policy:
  allow_implicit_invocation: false
EOF

log_info "Workspace-compliant scaffold created at $SKILL_PATH"
echo ""
echo "Next steps:"
echo "  1. Fill in SKILL.md and references/output-template.md"
echo "  2. Review against SKILLS/SKILL_STANDARD.md"
echo "  3. Add more references/assets/scripts only if the skill actually needs them"
echo "  4. Package from tools/SKILLS/folders/$SKILL_NAME into tools/SKILLS/packages/$SKILL_NAME.skill"
