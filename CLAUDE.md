# CLAUDE.md

Project-level guidance for Claude Code working in this repository.

## What this project is

A personal Telegram bot powered by the Claude API. Two skills are wired in:

1. **MBA Coach** (`mba_skill.py`) — Socratic / Validate / Teach modes,
   grounded in 40+ named business frameworks.
2. **Mitch's OS** (`orchestrator.py` + `SKILL.md`) — a hierarchical personal
   operating system: Executive Orchestrator coordinating six Divisions
   (Health, Business, Wealth, Relationships, Identity, Execution) of
   specialized agents.

The bot entrypoint is `bot.py`. Heroku worker entrypoint is `Procfile`.
Config (model, tokens, history limit) is in `config.py`.

## Repo layout

| File              | Purpose                                                  |
|-------------------|----------------------------------------------------------|
| `bot.py`          | Telegram handlers, history, mode switching               |
| `config.py`       | Env config (model, tokens, max history)                  |
| `mba_skill.py`    | MBA Coach: system prompt, modes, framework library       |
| `orchestrator.py` | Mitch's OS: divisions, agents, scope-based prompt composer |
| `SKILL.md`        | Skill spec for Mitch's OS (frontmatter + instructions)   |
| `Procfile`        | `worker: python bot.py`                                  |
| `requirements.txt`| Python deps                                              |
| `README.md`       | User-facing setup + command reference                    |

## Skill patterns

Both skills follow the same structural pattern. When adding a new skill, copy
the shape:

1. A Python module that defines:
   - dataclasses for the skill's domain objects,
   - reusable prompt fragments (identity, voice, output style, anti-patterns),
   - a `compose_system_prompt(scope_or_mode)` entry point,
   - small discovery helpers (`mode_summary`, `scope_summary`, etc.).
2. A markdown spec (`SKILL.md`-style) describing when to use the skill and
   how to operate within it.
3. Telegram wiring in `bot.py` — per-chat mode/scope state, `/command`
   handlers, and `system_prompt_for()` plumbing.

## Conventions

- **Python 3.10+** — uses `from __future__ import annotations`, `|`-style
  unions, `dataclass(frozen=True)`.
- **No emojis** in any code, prompts, or docs. The user's bot voice is
  deliberately plain.
- **Cite the agent / framework.** Prompts always name which lens is being
  applied (MBA framework name; OS division/agent name).
- **Cache the system prompt.** Large prompts are sent with
  `cache_control: {type: ephemeral}` — see `bot.py:cacheable_system`. The
  MBA and OS system prompts are both 3k+ tokens and benefit substantially.
- **Per-chat state lives in dicts keyed by `chat_id`** (see `histories`,
  `mba_mode` in `bot.py`). When adding a new skill, add another dict for
  its mode/scope.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # add TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY
python bot.py
```

There are no tests yet. When adding logic that warrants tests, prefer
`pytest` and keep the test files alongside the modules they test.

## Editing prompts

- Keep prompt blocks as **plain string constants** at module top level — do
  not interpolate runtime data into the system prompt unless it's stable for
  the whole session (a mode id, a scope id). Otherwise caching breaks.
- When extending `orchestrator.py`:
  - Add the new `Agent(...)` to the right division tuple,
  - Make sure its `id` is unique across the whole system (it's the routing
    key in `AGENTS_BY_ID`),
  - No code change needed in the composer — `compose_system_prompt(agent_id)`
    picks it up automatically.

## Wiring Mitch's OS into the bot

`orchestrator.py` is currently standalone. To expose it through Telegram,
mirror the MBA wiring in `bot.py`:

```python
from orchestrator import (
    compose_system_prompt as compose_os_prompt,
    DEFAULT_SCOPE as OS_DEFAULT,
    DIVISIONS_BY_ID, AGENTS_BY_ID, scope_summary as os_scope_summary,
)

os_scope: dict[int, str | None] = defaultdict(lambda: None)

def system_prompt_for(chat_id: int) -> str:
    if mba_mode[chat_id]:
        return compose_mba_prompt(mba_mode[chat_id])
    if os_scope[chat_id]:
        return compose_os_prompt(os_scope[chat_id])
    return DEFAULT_SYSTEM_PROMPT
```

Then add `/os`, `/os_scope <id>`, `/os_list`, `/os_off` command handlers
that mutate `os_scope[chat_id]` and `histories[chat_id].clear()` on entry,
following the `_enter_mba_mode` template.

## Things to avoid

- **Don't** mix MBA mode and OS scope at the same time. They are mutually
  exclusive system prompts. Entering one should clear the other.
- **Don't** put user-facing strings (e.g. "Cleared. Fresh start!") inside
  the system prompts. Keep handler messages in `bot.py`.
- **Don't** add a generalist fallback agent inside `orchestrator.py`. If a
  user's question doesn't fit any division, the bot should drop OS mode and
  use the default assistant prompt.
- **Don't** add emojis or marketing voice to system prompts. Both skills
  are intentionally direct.

## Git workflow

- Develop on feature branches like `claude/<description>`.
- Open draft PRs by default. Promote to "ready for review" only after the
  bot has been smoke-tested with the changes (a manual `/start`, one normal
  message, one mode-switch, one mode-off).
