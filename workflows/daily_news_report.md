# Workflow: Daily World + Bulgaria News Review (EN/BG)

## Objective
Every morning, produce a bilingual (English/Bulgarian) static website covering the most important news of
the past ~24 hours from major world and Bulgarian outlets. For stories covered by 2+ outlets, it shows how
the coverage differed. Every item links to the original article. A Telegram message with the link goes out
when the site is ready.

## Schedule & where it runs
- GitHub Actions (`.github/workflows/daily.yml`), cron `0 4 * * *` = 06:00 Sofia in winter / 07:00 in summer.
- Can also be started by hand: GitHub → Actions → "Daily news report" → Run workflow.
- The Claude steps use your **Claude subscription** through Claude Code (`CLAUDE_CODE_OAUTH_TOKEN`), not API credits.
- The site is published to GitHub Pages: `https://<github-user>.github.io/<repo>/`. Each day is also saved to `site/archive/`.

## Pipeline (`python tools/run_pipeline.py` runs all steps; `--from` / `--until` run part of it)
| # | Step | Tool | Output |
|---|------|------|--------|
| 1 | fetch | `tools/fetch_feeds.py` — every source in `tools/sources.yaml`, last 26h | `.tmp/articles_raw.json` |
| 2 | prefilter | `tools/prefilter.py` — drops sport/lifestyle/weather sections, topic hubs, TV bulletins | `.tmp/articles_filtered.json` |
| 3 | cluster | `tools/cluster_stories.py` — multilingual embeddings + agglomerative clustering, ranked by distinct outlets | `.tmp/clusters.json`, `.tmp/candidates.json` |
| 4 | select | `tools/run_claude.py select` — Claude as editor, prompt `tools/prompts/select.md` | `.tmp/selection.json` |
| 5 | extract | `tools/extract_articles.py` — full text (trafilatura) for up to 6 outlets per story | `.tmp/stories_input/*.json` |
| 6 | analyze | `tools/run_claude.py analyze` — one Claude call per story, prompt `tools/prompts/analyze.md` | `.tmp/stories/*.json` |
| 7 | validate | `tools/validate_report.py` — schema `tools/story_schema.json`, URLs must come from the input | `.tmp/report.json`, `data/history.json` |
| 8 | render | `tools/render_report.py` + `tools/templates/report.html.j2` | `site/index.html`, `site/archive/` |
| 9 | notify | `tools/notify_telegram.py` | Telegram message |

## Editorial rules (what counts as "local")
These rules live in `tools/prompts/select.md`. Change them there.
- **World (~15):** events of international significance.
- **Bulgaria (~10):** news of national significance only.
- **Always excluded:** single-city/regional news, crime blotter, sport, celebrities, lifestyle, weather
  forecasts (warnings and disasters are allowed), and US/UK domestic stories that matter only locally.
- Stories already in the last 7 days' reports (`data/history.json`) come back only when there is a substantial new development.
- Section sizes: env `N_WORLD`, `N_BG`.

## Coverage comparison rubric
Defined in `tools/prompts/analyze.md`. Aspects: framing, emphasis, omission, tone, who is quoted, context,
conflicting facts. There are 2–5 concrete differences per story, each naming the outlets involved. Claude must not invent
differences. Articles marked `title_only` are compared on their headlines only.

## Sources (`tools/sources.yaml`) and their quirks (verified 2026-11-02)
- **CNN:** RSS dead since 2024, so we use the Google News sitemap `edition.cnn.com/sitemaps/cnn/news.xml`.
- **Reuters, AP:** sitemaps return 401/403 and the articles block scrapers. We use a Google News `site:` search,
  so they give titles + links only. Google News links redirect to a consent page from EU IPs. `extract_articles.py`
  tries to decode them with `googlenewsdecoder`; if that fails it keeps the Google link, which a browser follows correctly.
- **Google News also lists topic hubs** ("Benjamin Netanyahu", "Georgia Bulldogs"). The prefilter drops titles under 4 words.
  It also lists one article under several URLs, so the fetcher dedupes by title too.
- **BNR** moved its news from bnr.bg to **bnrnews.bg** in 2026. The feed is `bnrnews.bg/api/rss/main` (about 50 items, roughly 10h).
- **BNT:** no RSS. We use the monthly sitemap `bntnews.bg/sitemap/sitemap_news_YYYY_M.xml`, which has dates only and no times.
- **Свободна Европа:** the Bulgarian service has published nothing since 2026-04-02 (empty feeds and sitemaps).
  It is disabled (`enabled: false`). Re-check occasionally.
- **Капитал, bTV, Mediapool** return **403 from GitHub Actions** (they block data-centre IPs) but work from a
  home connection. Each has a `fallback:` Google News feed in `sources.yaml`. It's used only when the primary
  feeds return nothing. In CI these outlets therefore come in as Google News titles; full text is usually blocked too.
- **Капитал:** partly paywalled, so the analysis often has only the RSS summary.
- **Nova:** the feed includes hourly "Новините на NOVA" broadcast entries; the prefilter drops them.
- When a source shows `EMPTY` in the fetch output, check its URL by hand. Sites change feed URLs without notice.

## Edge cases & recovery
- **A feed fails:** the run continues. The warning shows in the fetch output, and the outlet shows 0 in the site's sources table.
- **Claude returns invalid JSON:** `run_claude.py` retries once. A story that still fails is skipped and the others are kept.
- **Fewer than 5 valid stories:** `validate_report.py` exits 1, the workflow fails, and the site keeps yesterday's report.
- **Subscription usage limits hit:** lower `CLAUDE_PARALLEL` (default 3) or `N_WORLD`/`N_BG`, or set the repo variable
  `CLAUDE_MODEL` (default `sonnet`). As a last resort, switch to an API key: put `ANTHROPIC_API_KEY` in the secrets
  instead of the OAuth token. It costs about $0.7–1.5/day.
- **Clusters merge different events or split one event:** tune `--threshold` in `cluster_stories.py`. 0.42 worked well:
  lower means stricter. Claude also merges and splits during selection.
- **Running locally without the `claude` CLI:** run `--until cluster`, do the select step by hand following
  `tools/prompts/select.md` and write `.tmp/selection.json`, run `extract`, write `.tmp/stories/*.json` per
  `tools/prompts/analyze.md`, then `--from validate`.

## Security (the repo and site are public)
- Secrets live only in GitHub secrets and the local `.env`, which is gitignored. Never commit them.
- **Prompt injection:** article text is untrusted. `run_claude.py` runs Claude with **all tools disabled**,
  in an empty temp directory, with only the Claude auth variables in its environment. So an injected article
  can't make it read files or tokens.
- `validate_report.py` drops any story containing a credential-like string or the value of a secret env var.
  It also rejects any URL that wasn't in the input.
- The template autoescapes everything, and links must be `http(s)` URLs that came from the feeds (no XSS via the report).
- `notify_telegram.py` never prints the request URL, because it contains the bot token.
- The workflow runs only on schedule or by manual dispatch, never on pull requests, so forks can't reach the secrets.
- Full article texts (`.tmp/`) are never committed. The site only shows short summaries and links.

## One-time setup (GitHub)
1. Create a GitHub repo (public: Pages is free only for public repos) and push this folder.
   `.env`, `.tmp/` and credentials are gitignored.
2. On your PC, install Claude Code (`npm i -g @anthropic-ai/claude-code`) and run `claude setup-token`.
   Copy the token it prints.
3. Repo → Settings → Secrets and variables → Actions → New repository secret:
   - `CLAUDE_CODE_OAUTH_TOKEN` — the token from step 2
   - `TELEGRAM_BOT_TOKEN` — from @BotFather (`/newbot`)
   - `TELEGRAM_CHAT_ID` — send your bot a message, then open
     `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `message.chat.id`
4. Repo → Settings → Pages → Source: **GitHub Actions**.
5. Actions tab → "Daily news report" → **Run workflow** to test. The first run takes about 15 minutes (it downloads the model).

## Lessons learned
- 2026-11-02: first build. On a typical day there are about 660 articles; 560 survive the prefilter, forming 390 clusters, about 65 of them covered by several outlets.
  Cross-language clustering (EN↔BG) works well with `paraphrase-multilingual-MiniLM-L12-v2` at threshold 0.42.
- 2026-11-02, first GitHub Actions run (about 9 min, analysis about 3 min): it succeeded, but Капитал, bTV and Mediapool got 403
  (fixed with the fallback feeds). Claude invented a story id "b01x", which failed the schema; `run_claude.py select` now
  renumbers ids itself. Google News link decoding works from GitHub's US IPs, unlike from Bulgaria.
