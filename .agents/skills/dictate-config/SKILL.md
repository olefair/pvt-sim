---
name: dictate-config
description: "Manage and update the dictate tool's configuration — use this skill whenever the user mentions any dictate transcription issue, correction, or config change. Triggers include: 'dictate keeps saying X instead of Y', 'add X to dictate vocab', 'remove X from dictate vocab', 'update the dictate prompt', 'add X to the whisper prompt', 'change the dictate model', 'show dictate config', or any request to fix a recurring mis-transcription. Also use when the user pastes a transcription error and wants it fixed permanently. Covers all three layers of dictate config: correction pairs, initial prompt vocabulary, and server model settings."
---

# Dictate Config Skill

Manages the three layers of dictate transcription config. Always read current state before writing.

## File Map

| What | File | Change requires restart? |
|---|---|---|
| Correction pairs | `C:\Users\olefa\dev\pete-workspace\tools\dictate\user_vocab.json` | No — read on every transcription |
| Initial prompt (vocab bias + punctuation) | `C:\Users\olefa\dev\pete-workspace\tools\dictate\dictate_record.py` — `INITIAL_PROMPT` constant | No — read on every transcription |
| Whisper model / server settings | `C:\Users\olefa\dev\pete-workspace\tools\dictate\start_dictate.ps1` — `Start-Process` line | **Yes** — restart required |

---

## Reference Docs

- [Vocab ordering rules](./references/vocab-ordering.md) — why order matters and how to place new entries safely
- [Whisper prompt guide](./references/whisper-prompt-guide.md) — what the initial prompt does and when to use it vs. corrections

---

## Operations

### Write Posture

Chat may read all config files for diagnosis and display. Chat may also write
edits directly when the change is straightforward and verified (e.g., adding a
correction pair, appending a word to INITIAL_PROMPT).

For config changes:
1. Diagnose the issue (read files, identify what needs to change)
2. Verify the exact change required (which file, which line, old value → new value)
3. If the change is simple and low-risk, make the edit directly
4. If the change is complex, destructive, or affects model/server settings (which require restart), describe the change and confirm before writing

### View current config (always do this first if uncertain)

Read all three files and report:
- Current `INITIAL_PROMPT` string
- All entries in `user_vocab.json` (excluding `__` keys)
- Model/device/compute-type from `start_dictate.ps1`

### Add a correction pair

File: `user_vocab.json`

> **Read the full ordering rules:** [./references/vocab-ordering.md](./references/vocab-ordering.md)

**ORDER MATTERS** — longer/more-specific matches must come before shorter ones that could overlap. The file is processed top-to-bottom. Examples of ordering rules:
- `"backslash"` must come before `"slash"` (otherwise "backslash" gets clobbered to "back/")
- `"pete workspace"` should come before any single-word match for "pete"

When adding, place the new entry in the appropriate section:
- **Symbol/punctuation substitutions** (slash, dot, etc.) — top group
- **Technical term corrections** (.py, .pi variants, etc.) — middle group
- **Project/tool name corrections** — bottom group

If placement is ambiguous, append to the relevant group and note the ordering risk.

**Tip:** If Whisper outputs the *wrong* word for something you say, the correction goes in `user_vocab.json`. If a word is *never recognized at all* (produces gibberish), it belongs in `INITIAL_PROMPT` instead.

### Remove a correction pair

Read the current `user_vocab.json`, confirm the key exists, then delete the line. Always show the user what was removed.

### Update the initial prompt

> **Read the full prompt guide:** [./references/whisper-prompt-guide.md](./references/whisper-prompt-guide.md)

File: `dictate_record.py` — `INITIAL_PROMPT` constant

Rules for a good prompt:
1. List project/tool names and domain terms you say frequently
2. End with a period — nudges Whisper toward better sentence-level punctuation
3. Keep it as a natural sentence or short phrase list, not a raw word dump
4. Don't duplicate words already reliably transcribed

Example of good prompt:
```
"Working on Claude, pvt-sim, Pete-workspace, FaultTensor, and Python."
```

When adding words: append before the closing period, joined with commas.
When removing: delete the word and fix surrounding commas/grammar.

### Change the Whisper model

File: `start_dictate.ps1` — find the `Start-Process` line with `--model`

Available models (faster-whisper):
- `large-v3-turbo` — current default, best speed/quality balance
- `large-v3` — highest quality, slower
- `medium` — faster, slightly less accurate
- `small` — fastest, lowest quality

Always warn: **restart required** — run `start_dictate.ps1 -Stop` then re-launch `Dictate.cmd`.

---

## Common patterns

**"Dictate keeps saying X instead of Y"**
→ Add `"X": "Y"` to `user_vocab.json`. Check ordering.

**"Add X to the dictate vocabulary"** (Whisper should recognize it at all)
→ Add X to `INITIAL_PROMPT` in `dictate_record.py`.

**"Show me what's in my dictate config"**
→ Read all three files and present a clean summary.

**"Dot py is still transcribing wrong"**
→ Check `user_vocab.json` for `.pi`, `. pi`, `dot pi` entries. The spaced variant (`". pi"`) is the most common Whisper output. Ensure all three are present.

---

## Constraints

- Never edit `whisper-server/server.py` for vocab/prompt changes — those belong in `dictate_record.py` or `user_vocab.json`
- Never add bare short words to `user_vocab.json` if they appear inside common English words (e.g. `"pi"` would corrupt "opinion", "pixel", "pipeline")
- When in doubt about a correction's side effects, flag it to the user before writing
- The `pete_canon` whisper stack is entirely separate — never confuse it with this dictate stack