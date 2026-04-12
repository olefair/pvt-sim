# Vocab Ordering Reference

The `user_vocab.json` file is processed **top-to-bottom**. The first matching key wins. This means order is a correctness concern, not just a style preference.

---

## The Core Rule

Put **longer and more specific** matches before **shorter and more general** ones when any overlap is possible.

---

## Known Ordering Constraints

### backslash before slash
If `slash` came first, `"backslash"` would become `"back/"` because the substring `slash` matches inside it. Always order: `back slash` → `backslash` → `slash`.

### Punctuation cleanup after slash/underscore substitution
Whisper often wraps substituted symbols in commas or dashes: `, / ,` or `- / -`. The cleanup passes must come **after** the substitution entry that produces the symbol. If cleanup came first there would be nothing to match yet.

### Multi-word phrases before their component words
`"pete workspace": "Pete-workspace"` must come before any single-word match for `pete`. If a single-word entry matched first, it would consume `pete` before the phrase entry could fire.

---

## Grouping Convention

Keep the file organized in these sections:

1. **Symbol substitutions** — slash, backslash, underscore, dot
2. **Punctuation cleanup** — comma/dash artifacts around substituted symbols
3. **File extension corrections** — `.pi` → `.py` variants
4. **Project and tool names** — pvt-sim, FaultTensor, Pete-workspace, etc.

---

## Before Adding a New Entry

Ask:
1. Does the new key appear as a substring of any existing key? If yes, the existing key must come first.
2. Does any existing key appear as a substring of the new key? If yes, the new key must come first.
3. Is the new key a multi-word phrase? Put it above any single-word entries that share words with it.
4. Does the key appear inside common English words? If yes, use a spaced or more specific variant to avoid corruption (e.g. `" dot "` not `"dot"`).