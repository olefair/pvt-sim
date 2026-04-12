# Data Hygiene For `.learnings/`

These logs are useful only if they stay safe and readable.

## Redact Before Writing

- API keys, tokens, cookies, credentials, and SSH material
- personally identifying information unless it is required for the lesson
- full proprietary prompts or long private conversation excerpts
- stack traces or command output longer than needed to preserve the lesson

## Preferred Style

- keep the shortest error excerpt that still makes the issue recognizable
- replace sensitive values with placeholders such as `<redacted-token>`
- summarize the environment or trigger rather than dumping whole logs
- link to local files when that is enough; do not paste their full contents

## Hard Stop

If the only way to explain the incident is to preserve a secret or other highly
sensitive content, do not write it into `.learnings/`. Keep the note in chat or
store a redacted version only.
