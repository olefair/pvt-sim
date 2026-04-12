#!/bin/bash
# Self-Improving Agent activator hook
# Emits a lightweight reminder for CLI agents that support prompt hooks.
# Keeps quiet unless the repo has adopted the .learnings workflow, unless
# SELF_IMPROVING_AGENT_FORCE=1 is set explicitly.

set -e

if [ "${SELF_IMPROVING_AGENT_FORCE:-0}" != "1" ] && [ ! -d ".learnings" ]; then
    exit 0
fi

cat << 'EOF'
<self-improving-agent-reminder>
After completing this task, evaluate if extractable knowledge emerged:
- Non-obvious solution discovered through investigation?
- Workaround for unexpected behavior?
- Project-specific pattern learned?
- Error required debugging to resolve?

If yes: Log to .learnings/ using the self-improving-agent skill format.
If high-value (recurring, broadly applicable): Consider skill extraction.
</self-improving-agent-reminder>
EOF
