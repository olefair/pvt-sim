/**
 * Self-Improving Agent Hook for OpenClaw
 * 
 * Injects a reminder to evaluate learnings during agent bootstrap.
 * Fires on agent:bootstrap event before workspace files are injected.
 */

import type { HookHandler } from 'openclaw/hooks';
import fs from 'node:fs';
import path from 'node:path';

const REMINDER_CONTENT = `## Self-Improving Agent Reminder

After completing tasks, evaluate if any learnings should be captured:

**Log when:**
- User corrects you → \`.learnings/LEARNINGS.md\`
- Command/operation fails → \`.learnings/ERRORS.md\`
- User wants missing capability → \`.learnings/FEATURE_REQUESTS.md\`
- You discover your knowledge was wrong → \`.learnings/LEARNINGS.md\`
- You find a better approach → \`.learnings/LEARNINGS.md\`

**Promote when pattern is proven:**
- Behavioral patterns → \`SOUL.md\`
- Workflow improvements → \`AGENTS.md\`
- Tool gotchas → \`TOOLS.md\`

Keep entries simple: date, title, what happened, what to do differently.`;

function collectCandidateRoots(event: Record<string, unknown>): string[] {
  const maybeRoots = [
    event.cwd,
    event.workspacePath,
    (event.context as Record<string, unknown> | undefined)?.cwd,
    (event.context as Record<string, unknown> | undefined)?.workspacePath,
    process.cwd(),
  ];

  return [...new Set(maybeRoots.filter((value): value is string => typeof value === 'string' && value.trim().length > 0))];
}

function shouldInject(event: Record<string, unknown>): boolean {
  if (process.env.SELF_IMPROVING_AGENT_FORCE === '1') {
    return true;
  }

  for (const root of collectCandidateRoots(event)) {
    try {
      if (fs.existsSync(path.join(root, '.learnings'))) {
        return true;
      }
    } catch {
      // Ignore invalid candidate paths and continue.
    }
  }

  return false;
}

const handler: HookHandler = async (event) => {
  // Safety checks for event structure
  if (!event || typeof event !== 'object') {
    return;
  }

  // Only handle agent:bootstrap events
  if (event.type !== 'agent' || event.action !== 'bootstrap') {
    return;
  }

  // Safety check for context
  if (!event.context || typeof event.context !== 'object') {
    return;
  }

  // Skip sub-agent sessions to avoid bootstrap issues
  // Sub-agents have sessionKey patterns like "agent:main:subagent:..."
  const sessionKey = event.sessionKey || '';
  if (sessionKey.includes(':subagent:')) {
    return;
  }

  // Keep global hook installs quiet unless the active workspace has opted into
  // the .learnings workflow, unless a maintainer intentionally forces it on.
  if (!shouldInject(event as Record<string, unknown>)) {
    return;
  }

  // Inject the reminder as a virtual bootstrap file
  // Check that bootstrapFiles is an array before pushing
  if (Array.isArray(event.context.bootstrapFiles)) {
    event.context.bootstrapFiles.push({
      path: 'SELF_IMPROVEMENT_REMINDER.md',
      content: REMINDER_CONTENT,
      virtual: true,
    });
  }
};

export default handler;
