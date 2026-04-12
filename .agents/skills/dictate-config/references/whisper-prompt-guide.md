# Whisper Initial Prompt Guide

The `INITIAL_PROMPT` constant in `dictate_record.py` is sent to Whisper as the `initial_prompt` parameter on every transcription request. It biases the model toward recognizing specific vocabulary and toward a particular punctuation and capitalization style.

---

## What It Does

- **Vocabulary priming** — Whisper is more likely to output a word it has "seen" in the prompt. Use this for project names, technical terms, and proper nouns that Whisper would otherwise mangle.
- **Style priming** — The style of the prompt (sentence case, punctuation) nudges Whisper to match it in output.
- **Not a correction mechanism** — If Whisper outputs the wrong word, a correction in `user_vocab.json` is more reliable. Use the prompt for words Whisper fails to recognize at all.

---

## What Makes a Good Prompt

1. **Natural sentence form** — not a raw word dump. Whisper treats this as preceding context.
2. **Ends with a period** — nudges sentence-level punctuation in output.
3. **Contains domain-specific terms** you say often — project names, tool names, technical vocabulary.
4. **Does not duplicate** words Whisper already handles reliably.
5. **Kept concise** — adding every word you know dilutes the signal.

### Current prompt
```
"Working on Claude, pvt-sim, Pete-workspace, FaultTensor, and Python."
```

---

## When to Add to the Prompt vs. Add a Correction

| Symptom | Fix |
|---|---|
| Whisper outputs the **wrong word** | Correction in `user_vocab.json` |
| Whisper outputs **gibberish or nothing** for a term | Add to `INITIAL_PROMPT` |
| Whisper gets it right sometimes but not always | Try prompt first, correction as fallback |

---

## Editing the Prompt

File: `C:\Users\olefa\dev\pete-workspace\tools\dictate\dictate_record.py`  
Constant: `INITIAL_PROMPT`

No restart needed — the prompt is read on every transcription call.

---

## Relationship to Pete's Whisper Stack

Pete (`pete_canon/src/pete/ptt/whisper.py`) has its own separate initial prompt via the `PETE_WHISPER_INITIAL_PROMPT` environment variable. Changes to dictate's `INITIAL_PROMPT` do **not** affect Pete, and vice versa. Never edit `whisper-server/server.py` to manage vocabulary — that file handles HTTP transport only.