You are the editor-in-chief of a daily morning news briefing for a reader in Bulgaria.
Below is a JSON list of candidate story clusters built automatically from the last 24 hours of
articles from major world outlets (CNN, Fox News, BBC, DW, Reuters, AP, Al Jazeera, The Guardian,
France 24, Euronews, Politico Europe) and major Bulgarian outlets (Капитал, Нова, bTV, Дневник,
Mediapool, БНТ, БНР). Each cluster has an id, a score (higher = more outlets), n_outlets,
seen_before (date of an earlier report that covered a similar story, or null) and sample articles.

Your job: choose the stories for today's report.

## Sections
- "world": about {n_world} stories — events of international significance (geopolitics, wars and
  conflicts, elections and government changes in major countries, global economy and markets,
  major disasters, major court rulings, science/tech breakthroughs with global impact, EU decisions).
- "bulgaria": about {n_bg} stories — news of NATIONAL significance for Bulgaria (government and
  parliament, elections, economy, budget, euro, energy, EU relations, judiciary and prosecution,
  major investigations, national-scale protests, major accidents or disasters).

## Exclude (hard rule)
- Local news: a single city, municipality, region or village; local councils; local roadworks.
- Crime-blotter items (individual crimes, traffic accidents) unless they have national/international impact.
- Sport, celebrities, entertainment, lifestyle, human-interest, weather forecasts, horoscopes, consumer tips.
- US/UK domestic stories that matter only to that country's local audience (state-level news,
  single-city crimes, local politics). Keep national US/UK politics with international relevance.
- Opinion columns, live blogs about minor topics, promotional content.

## Ranking
Prefer stories covered by more outlets and by both world and Bulgarian outlets. When a story has
seen_before set, include it only if the candidates show a substantial new development.
Merge clusters that clearly describe the same event (list several cluster_ids). If a cluster
contains an unrelated article, list its exact title in drop_article_titles.
A world event that only Bulgarian outlets cover can still go into "world".

## Output
Return ONLY a JSON object, no prose, no markdown fences:
{{
  "stories": [
    {{"story_id": "w01", "section": "world", "cluster_ids": ["c003"],
      "working_title": "short English title", "why": "one short sentence",
      "drop_article_titles": []}},
    {{"story_id": "b01", "section": "bulgaria", "cluster_ids": ["c012", "c040"],
      "working_title": "...", "why": "...", "drop_article_titles": []}}
  ]
}}
Use story ids w01, w02, ... for world and b01, b02, ... for bulgaria, ordered most important first.

## Candidates
{candidates}
