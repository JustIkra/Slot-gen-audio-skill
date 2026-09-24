# Qwen Omni audio review routes

The user-selected default is `qwen/qwen3.8-omni-flash` through OpenRouter with
`OPENROUTER_KEY`. To compare with the previous reviewer, explicitly pass
`--model alibaba/qwen3.5-omni-plus` for AIMLAPI with `AIMLAPI_KEY`. The old bare
selector `qwen3.8-omni-flash` remains an alias for the OpenRouter model. There
is no silent fallback or audio generation in either route.

| Route | Qwen3.8 default | Qwen3.5 explicit |
|---|---|---|
| Provider | OpenRouter | AIMLAPI |
| API budget field | `max_completion_tokens` | `max_tokens` |
| Input/output here | MP3 in `input_audio`, text JSON out | Same |

The prior Qwen3.5 game-audio benchmark had 28 complete responses in 32 calls
over 16 Book of Abydos and Enigmatic Creatures episodes. Four requests ended
with incomplete HTTP reads. The switch to Qwen3.8 is a user choice, not a claim
that a same-corpus audio comparison proved it superior. Visual/video tests do
not substitute for listening to the actual cue or checking event timing.

For a paired comparison, use identical source files, segments, brief and
`--max-tokens`, then inspect both complete reports alongside measured levels,
duration and human listening. A partial stream, refusal or inaccessible audio
is a failed review, never acceptance. Verify current provider pricing and
availability before a substantial paid batch.

Official references:

- [OpenRouter Qwen3.8 Omni Flash](https://openrouter.ai/qwen/qwen3.8-omni-flash/)
- [OpenRouter chat completions](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request)
- [AIMLAPI Qwen3.5 Omni Plus](https://aimlapi.com/models/qwen3-5-omni-plus)
