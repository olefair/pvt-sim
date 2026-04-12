#!/bin/bash
# Self-Improving Agent error detector hook
# Triggers on CLI post-tool hooks to detect likely command failures.
# Emits reminders only when .learnings exists unless forced explicitly.

set -e

if [ "${SELF_IMPROVING_AGENT_FORCE:-0}" != "1" ] && [ ! -d ".learnings" ]; then
    exit 0
fi

OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"
EXIT_CODE="${CLAUDE_TOOL_EXIT_CODE:-${CODEX_TOOL_EXIT_CODE:-}}"

ERROR_PATTERNS=(
    "error:"
    "Error:"
    "ERROR:"
    "failed"
    "FAILED"
    "command not found"
    "No such file"
    "Permission denied"
    "fatal:"
    "Exception"
    "Traceback"
    "npm ERR!"
    "ModuleNotFoundError"
    "SyntaxError"
    "TypeError"
    "exit code"
    "non-zero"
)

contains_error=false
if [ -n "$EXIT_CODE" ] && [ "$EXIT_CODE" != "0" ]; then
    contains_error=true
fi

for pattern in "${ERROR_PATTERNS[@]}"; do
    if [[ "$OUTPUT" == *"$pattern"* ]]; then
        contains_error=true
        break
    fi
done

if [ "$contains_error" = true ]; then
    cat << 'EOF'
<self-improving-agent-error-detected>
A command error was detected. Consider logging this to .learnings/ERRORS.md if:
- The error was unexpected or non-obvious
- It required investigation to resolve
- It might recur in similar contexts
- The solution could benefit future sessions

Use the self-improving-agent format: [ERR-YYYYMMDD-XXX]
</self-improving-agent-error-detected>
EOF
fi
