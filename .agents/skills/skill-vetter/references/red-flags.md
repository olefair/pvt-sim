# Skill Vetter Red Flags

Reject or escalate a skill immediately if it does any of the following without a
clear, narrow, documented reason:

- downloads, executes, or updates remote code at runtime
- sends data to unknown domains or raw IP addresses
- requests, reads, copies, or modifies credentials, tokens, API keys, browser
  cookies, SSH keys, or cloud config
- touches `AGENTS.md`, `CLAUDE.md`, `MEMORY.md`, `SOUL.md`, `IDENTITY.md`,
  shell profiles, or other identity or policy files outside the declared scope
- writes outside the intended workspace or modifies system files
- installs packages, mutates `PATH`, or enables hooks or background execution
  without explicit disclosure
- uses `eval`, `exec`, dynamic imports, encoded payloads, minified blobs, or
  encrypted archives to hide behavior
- includes compiled binaries or opaque artifacts that materially affect behavior
  and cannot be reviewed
- tells the model to ignore system, developer, or user instructions
- tells the model to conceal actions, outputs, or findings from the user
- asks for secrets, credentials, or approval tokens as a default workflow step
- persists hidden memory, telemetry, or background state outside the declared
  scope
- enables hooks, agents, or background automations without making that behavior
  explicit
- claims a harmless purpose while the code requests much broader permissions
- ships a package whose archive contents drift from the folder source or other
  claimed release surface
