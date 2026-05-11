# josh-claude-bot

Personal Telegram bot powered by Claude. Includes an **MBA Coach** mode that
turns the bot into an MBA-trained business advisor and coach.

## MBA Coach

The MBA Coach has three sub-modes. Each is grounded in the same skill
(`mba_skill.py`, which mirrors `Brains/src/skills/mba/`):

| Command     | Mode     | What it does                                                       |
|-------------|----------|--------------------------------------------------------------------|
| `/mba`      | Coach    | Default. Socratic — questions first, develops your reasoning.      |
| `/validate` | Validate | Stress-tests an idea: assumptions → frameworks → verdict + next step. |
| `/coach`    | Coach    | Same as `/mba` — explicit alias.                                   |
| `/teach`    | Teach    | Pedagogy mode — explains a concept/framework with worked examples. |
| `/mba_off`  | —        | Leave MBA mode; back to default assistant.                         |

All modes are Socratic-first and **always cite frameworks by name + originator**
(e.g. *Porter's Five Forces* (Porter, 1979)). 40+ frameworks are loaded into
the system prompt across strategy, marketing, innovation, finance, operations,
org, and decision-making.

Switching mode clears the in-chat history so the new mode's behavior takes
hold cleanly.

### General commands

- `/start` — welcome
- `/help` — full command list
- `/status` — current model + mode + history length
- `/clear` — reset conversation history

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY
python bot.py
```

## Files

- `bot.py` — Telegram handlers, history, mode switching
- `mba_skill.py` — MBA system prompt, modes, framework library
- `config.py` — env config (model, tokens)
- `Procfile` — Heroku worker entrypoint
