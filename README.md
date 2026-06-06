# Minimal Coding Agent

This repo contains a teaching-sized coding agent split into four small modules.

It demonstrates the smallest useful loop:

1. Send the task and recent history to an Anthropic-compatible model.
2. Let the model choose one action in JSON.
3. Execute a local tool.
4. Feed the tool result back into the next round.
5. Stop when the model emits `finish` or the step limit is reached.

## File structure

- [main.py](main.py): startup and CLI entrypoint
- [agent.py](agent.py): the observe-decide-act loop
- [llm.py](llm.py): Anthropic-compatible request building and response parsing
- [tools.py](tools.py): local environment tools exposed to the agent

## Supported tools

- `read_file`
- `search_text`
- `write_file`
- `run_command`

## Environment variables

- `ANTHROPIC_API_KEY`: provider key
- `ANTHROPIC_MODEL`: optional, defaults to `deepseek-chat`
- `ANTHROPIC_BASE_URL`: optional, defaults to `https://api.deepseek.com/anthropic/v1/messages`

DeepSeek can expose an Anthropic-compatible endpoint, so the same request shape works.
The default model is the one we have validated in this toy setup; if you override it, make sure the new model really supports the same Anthropic-compatible message schema.

## Run it

```bash
export ANTHROPIC_API_KEY=your_key
python main.py "read main.py and explain what this project does"
```

The quoted string is the required `task` argument.

- `task` means: the natural-language goal you want the agent to try to complete.
- It is a positional argument, so you must provide it directly after `main.py`.
- If you provide it, the program runs one task and exits.

If you want another task, just run the command again with a new `task`.

The other runtime settings are now fixed in code to keep the CLI minimal.

Example for a code task:

```bash
python main.py "inspect the repo, improve the README, and validate with a command"
```

## What to study in the code

- `SYSTEM_PROMPT` in [llm.py](llm.py): constrains the model into a JSON action protocol.
- `TOOLS` in [tools.py](tools.py): defines the agent's action space.
- `call_model()` in [llm.py](llm.py): the LLM boundary.
- `run_agent()` in [agent.py](agent.py): the observe-decide-act loop.

## Limits by design

This version is intentionally simple.

- It rewrites full files instead of applying diffs.
- It does not keep long-term memory.
- It does not stream tokens.
- It trusts shell commands, so it is for local learning only.
