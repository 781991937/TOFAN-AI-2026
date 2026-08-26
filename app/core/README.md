# TOFAN AI Python Core

## Architecture

`app/core` is the Python application layer. It contains no Telegram/aiogram handlers.

- `runtime.py` — composition root; constructs shared services once.
- `automation_engine.py` — document extraction, lesson splitting, page building and local analysis.
- `ai_engine.py` — AI analysis and quiz generation boundary.

The Telegram bot under `app/bot` is the interface/adapter layer. It receives user events and delegates to the Python services injected by `PythonRuntime`.

## Domain separation

```text
Telegram / aiogram
        |
        v
   Bot adapters
      /    \
     /      \
 AI domain   Automation domain
     |             |
 ai_engine    automation_engine
     \             /
      \           /
        Database
```

The AI and Automation engines may share persistence, but they do not import each other's Telegram handlers.
