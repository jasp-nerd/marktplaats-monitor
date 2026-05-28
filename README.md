<p align="center">
  <img src="assets/banner.svg" alt="marktplaats-monitor — self-hosted saved-search alerts for Marktplaats" width="100%">
</p>

<p align="center">
  <a href="https://github.com/jasp-nerd/marktplaats-scraper/actions/workflows/ci.yml"><img src="https://github.com/jasp-nerd/marktplaats-scraper/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white" alt="Docker">
</p>

# Marktplaats Monitor

Self-hosted monitor for [Marktplaats](https://www.marktplaats.nl). Watches one
or more saved searches and pushes an alert the moment a matching listing
appears — or drops in price — to **Discord, Telegram, ntfy, email, Slack,
Pushover, Matrix, or ~100 other services** via
[Apprise](https://github.com/caronc/apprise).

- 🔎 **Multiple saved searches**, each with its own filters and destination
- 💸 **Price-drop tracking**, not just new listings
- 🎯 Filters: price range, distance from a postcode, condition, category,
  required keywords, regex blacklist
- 🔔 Apprise (any service) by default, or opt-in rich native Discord embeds
- 🧠 Pluggable listing-evaluator hook (a future genAI scorer drops in here)
- 🗃️ SQLite state — survives restarts; dedupes on the stable Marktplaats item id
- 🐳 One-command Docker / docker-compose, or run locally / on a VPS

> Personal, read-only monitoring tool. Be considerate with polling intervals.
> Not affiliated with Marktplaats.

## Demo

<table>
<tr>
<td align="center" width="60%">
  <img src="assets/demo.gif" alt="CLI demo — help, annotated config, stats" width="100%"><br>
  <sub><em>One command in your terminal.</em></sub>
</td>
<td align="center" width="40%">
  <img src="assets/discord-screenshot.png" alt="A real Apple HomePod alert delivered to Discord as a rich native embed" width="100%"><br>
  <sub><em>One rich embed in your channel.</em></sub>
</td>
</tr>
</table>

## Quickstart

Requires **Python 3.11+** (or just use Docker).

```bash
git clone https://github.com/jasp-nerd/marktplaats-scraper
cd marktplaats-scraper

cp .env.example .env            # put your Apprise URL(s) here
cp config.example.yaml config.yaml   # define your searches

pip install -r requirements.txt      # or: pip install -e ".[dev]" for dev
python -m marktplaats_monitor test   # verify notifications work
python -m marktplaats_monitor run    # start monitoring
```

### Docker

```bash
cp .env.example .env && cp config.example.yaml config.yaml
docker compose up -d
docker compose logs -f
docker compose exec monitor python -m marktplaats_monitor stats
```

State persists in the `mp_data` volume; `config.yaml` is mounted read-only.

## Commands

| Command | What it does |
|---|---|
| `run` | Poll forever (daemon). |
| `once` | One full cycle over all searches, then exit (cron/CI friendly). |
| `test` | Send a sample notification through each search's backend and exit. |
| `stats` | Print per-search statistics (totals, last 24h, avg price, hits). |

Global flags: `-c/--config` (default `config.yaml`), `--db` (default
`data/monitor.sqlite3`), `--log-level`.

## Configuration

Everything non-secret lives in **`config.yaml`** — a `defaults:` block plus a
`searches:` list. Every default can be overridden per search. See
[`config.example.yaml`](config.example.yaml) for a fully annotated example.

**Secrets never go in the YAML.** Reference them with an `env:NAME` token,
resolved from the environment / `.env`:

```yaml
defaults:
  notify:
    backend: apprise
    apprise_urls: ["env:APPRISE_URLS"]
searches:
  - id: example-1
    name: "Example — road bike"
    url: "https://www.marktplaats.nl/q/racefiets/"
    price_min: 100         # euros
    price_max: 500
    distance_km: 25        # only applies if the url has a #postcode:1234AB
    exclude_keywords: ['(?i)\bdefect\b', "kapot"]
    condition: used        # new | as_good_as_new | used | refurbished | not_working
```

Each search needs an `id` plus **one of** `url`, `query`, or `category`:

- `url` — paste a Marktplaats search address (filters in the `#...` fragment
  are honored). Get it by searching on marktplaats.nl and copying the bar.
- `query` — just the search words (e.g. `query: "racefiets"`); combine with
  `postcode`/`distance_km`/`price_*`/`condition` instead of crafting a URL.
- `category` — a category name (see `config.example.yaml`).

If you give more than one, `query` overrides the URL's search term, and a
config-level `postcode`/`distance_km` overrides one embedded in the URL.

Precedence: **CLI flag → env → per-search → defaults → built-in**.

### Notifications (Apprise)

The default backend is Apprise, so you are **not** limited to Discord and the
app does not allowlist services — you put whatever
[Apprise URL](https://github.com/caronc/apprise#supported-notifications) you
want in `.env`:

```
APPRISE_URLS=discord://WEBHOOK_ID/WEBHOOK_TOKEN
# or tgram://BOT/CHAT, ntfy://ntfy.sh/topic, mailto://user:pass@host, slack://...
# multiple, separated by commas or spaces
```

Per search you can set `notify.mention` (`none` | `everyone` | `here` |
`role:<id>`) and `notify.attach_image`. For pixel-perfect Discord embeds set
`notify.backend: discord_native` (uses `DISCORD_WEBHOOK_URL`).

## Deployment

- **Docker Compose** (recommended): `docker compose up -d` — restarts on
  failure, state in a named volume. Upgrades: `git pull && docker compose up -d --build`.
- **systemd (bare VPS):**

  ```ini
  # /etc/systemd/system/marktplaats-monitor.service
  [Service]
  WorkingDirectory=/opt/marktplaats-scraper
  ExecStart=/opt/marktplaats-scraper/.venv/bin/python -m marktplaats_monitor run
  Restart=always
  [Install]
  WantedBy=multi-user.target
  ```
- **PaaS (Heroku/Railway-style):** the `Procfile` runs
  `python -m marktplaats_monitor run` as a worker.

## How it works

Uses Marktplaats' own JSON search API (`/lrp/api/search`) — no headless
browser, no HTML scraping. Field behaviour is documented in
[`docs/marktplaats-api.md`](docs/marktplaats-api.md). Page 1 is fetched
strictly newest-first (`sortBy=SORT_INDEX&sortOrder=DECREASING` — the same
"Nieuwste eerst" sort the Marktplaats UI uses); paid `DAGTOPPER` promos are
filtered by default so the dedup window contains real chronological organic
results. Dedup and price history live in SQLite, keyed on the stable
`itemId` (a price/title edit does not fire a false "new"). A notification is
only marked sent once delivery succeeds, so a transient outage retries next
cycle.

## Extending: the evaluator hook

`fetch → filter → evaluator → state → notify`. The evaluator defaults to a
no-op. Implement the `ListingEvaluator` protocol, register it, and set
`evaluator.type` in config — no pipeline change required. This is where the
planned **genAI scorer** (rate fit to your description + whether the price is
fair) will plug in.

## Roadmap

- 🧠 GenAI listing scorer (fit + value-for-money) via the evaluator hook
- 🌐 Web dashboard (manage searches, recent hits, live logs)
- 📰 RSS/Atom feed of matches
- 🔁 Proxy rotation / rate-limit resilience
- 👥 Multi-user (if it ever becomes a hosted service)

**Non-goals:** auto-messaging or auto-buying from sellers (ToS/ethics).

## Development

```bash
pip install -e ".[dev]"
ruff check . && black --check . && pytest
```

## Attribution & license

MIT — see [LICENSE](LICENSE). The Marktplaats category map and the Dutch
date/price-type parsing are **vendored** from the MIT-licensed
[marktplaats-py](https://github.com/jensjeflensje/marktplaats-py) (© 2023 Jens
de Ruiter); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No runtime
dependency on that library — the scraper is our own.
