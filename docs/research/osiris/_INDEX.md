# Osiris — OSINT capabilities reference

> Source: https://github.com/simplifaisoul/osiris
> Live: https://www.osirisai.live
> Pulled into Theo's brain on 2026-05-24.

## What this is

Osiris is an Open Source Intelligence dashboard built by simplifaisoul.
It aggregates live data from public OSINT sources into one interface and
exposes the aggregation behind a JSON API at `https://www.osirisai.live/api/*`.

Theo can use the `osint_query` tool to hit those endpoints directly when
the human asks about real-world intel: earthquakes, fires, flights, news,
ports, ships, conflict zones, cyber threats, etc. The `README.md` in this
directory has the full capability list; `AGENTS.md` and `DOCKER.md` cover
operational notes from the project's own agent / container setup.

## Why it's here

Ian wanted Theo to know about Osiris three ways:
1. As reference docs (this directory).
2. As searchable memory — these `.md` files are indexed alongside
   transcripts so `semantic_recall` can surface them when relevant.
3. As a live tool — `osint_query` calls the Osiris API at runtime.

## Endpoint cheat sheet

| Domain | URL |
|---|---|
| Earthquakes | `/api/earthquakes` |
| Fires | `/api/fires` |
| Flights | `/api/flights` |
| Maritime / ports | `/api/maritime` |
| Live news streams | `/api/live-news` |
| News articles | `/api/news` |
| GDELT events | `/api/gdelt` |
| Weather alerts | `/api/weather` |
| Air quality | `/api/air-quality` |
| Satellites | `/api/satellites` |
| Space weather | `/api/space-weather` |
| CCTV cameras | `/api/cctv` |
| Frontlines (conflict zones) | `/api/frontlines` |
| Country risk | `/api/country-risk` |
| Infrastructure | `/api/infrastructure` |
| Cyber threats (CVEs) | `/api/cyber-threats` |
| Markets | `/api/markets` |
| Region dossier | `/api/region-dossier` |
| RECON — port scan | `/api/scanner` |
| RECON — DNS/WHOIS/SSL | `/api/osint/sweep` |
| RECON — IP lookup | `/api/osint/ip` |
| Sentinel | `/api/sentinel` |
| Health check | `/api/health` |
