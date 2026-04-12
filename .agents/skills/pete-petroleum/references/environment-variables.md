# Pete Petroleum Environment Variables

## TTS Configuration

| Variable | Values | Description |
|----------|--------|-------------|
| `PETE_TTS_SPOKEN_MODE` | `strip` / `smart` / `llm` | Controls how spoken response is derived from written response |
| `PETE_TTS_SPOKEN_MAX_SENTENCES` | integer | Maximum sentences in spoken output |
| `PETE_TTS_SPOKEN_MAX_CHARS` | integer | Maximum characters in spoken output |
| `PETE_ELEVENLABS_MODEL` | model id/name | ElevenLabs model selection (v1 / v2 / v2.5 / etc.) |

## LLM Configuration

| Variable | Values | Description |
|----------|--------|-------------|
| `PETE_WARMUP_LLM` | `0` / `1` | Whether to warm up LLM on startup |

## Network and Tools

| Variable | Values | Description |
|----------|--------|-------------|
| `PETE_ENABLE_NETWORK_TOOLS` | `0` / `1` | Gate for web search and network-dependent tools |

## Security Note

Never commit API keys or tokens. In cloud environments, prefer keeping keys out of the agent phase whenever possible. All secrets should be set as environment variables.
