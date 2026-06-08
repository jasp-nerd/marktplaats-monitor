# Contributing

Thanks for taking the time. Bug reports, feature ideas, and pull requests are
all welcome, even small ones.

## Reporting a bug or asking for a feature

Open an issue. The templates ask for the few things that make a report
actionable: what you ran, what you expected, what happened. A redacted snippet
of your `config.yaml` and the log line usually tells the whole story.

## Working on the code

```bash
git clone https://github.com/jasp-nerd/marktplaats-monitor
cd marktplaats-monitor
pip install -e ".[dev]"

ruff check . && black --check . && pytest
```

Before you open a pull request:

- `ruff check .` and `black --check .` pass (run `black .` to format)
- `pytest` is green, and new behaviour comes with a test
- the commit message says what changed and why

Keep pull requests focused on one thing. A small PR that does one job gets
reviewed and merged faster than a large one that does five.

## Scope

This stays a personal, read-only monitoring tool. Two things are out of scope
on purpose: auto-messaging sellers and auto-buying. Both cross Marktplaats'
terms of service. Everything else is fair game, so open an issue first if you
want to talk through a bigger change before you build it.
