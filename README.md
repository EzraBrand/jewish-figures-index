# Jewish Figures Index

An index of **Jewish/Israelite figures** spanning three historical periods:

- **Biblical** — figures from the Hebrew Bible (Tanakh)
- **Talmudic** — Tannaim (Mishnaic era, ~10–220 CE) and Amoraim (~220–500 CE)
- **Medieval** — Geonim (~600–1000 CE) and Rishonim (~1000–1500 CE)

Names are scraped from curated English and Hebrew Wikipedia categories and enriched with biographical fields from Wikidata.

**Live site:** <https://ezrabrand.github.io/jewish-figures-index/>

Companion to the [Talmud NLP indexer glossary](https://ezrabrand.github.io/talmud-nlp-indexer/glossary/) — this index extends the timeline backward to biblical figures and forward to medieval scholars.

## What's in the index

The published table currently has **853 deduped entries**, distributed across the following category buckets:

| Category | Rows |
| --- | ---: |
| Biblical | 428 |
| Tannaim | 234 |
| Medieval | 70 |
| Amoraim | 67 |
| Geonim | 52 |
| Biblical kings | 41 |

(Some entries belong to more than one bucket, so column sums slightly exceed 853.)

Each row contains:

| Column | Source |
| --- | --- |
| Term (English) | Wikidata label, or English Wikipedia page title |
| Category | Source bucket(s): `Biblical`, `Biblical kings`, `Tannaim`, `Amoraim`, `Geonim`, `Medieval` |
| Wikipedia EN | English Wikipedia URL (via Wikidata sitelinks) |
| Wikipedia HE | Hebrew Wikipedia URL (via Wikidata sitelinks) |
| Wikidata ID | Q-ID, links to wikidata.org |
| Father's Name | Wikidata P22 |
| Birth / Death Date | Wikidata P569 / P570 (BCE rendered as `NNN BCE`) |
| Birth / Death Place | Wikidata P19 / P20 |
| Name(s) of Teacher(s) | Wikidata P1066 |
| Name(s) of Student(s) | Wikidata P802 |

Entries are deduped by Wikidata Q-ID — a figure appearing in both English and Hebrew Wikipedia categories produces a single row with both `Category` buckets joined by `; `.

## Scope and filtering

Only **Jewish/Israelite** figures are included. The scraper drops non-name entries via an explicit blocklist plus regex patterns. Excluded categories:

- **Foreign biblical rulers** — Persian (Cyrus, Darius, Ahasuerus, Haman, Vashti), Babylonian (Nebuchadnezzar II, Belshazzar, Nabonidus), Assyrian (Sennacherib, Sargon II, Tiglath-Pileser III), Egyptian (Pharaoh, Necho II, Shishak, Taharqa), Moabite, Aramean, Canaanite, Philistine, Amalekite, etc.
- **Non-Israelite Genesis figures** — Esau, Ishmael, Amalek, Eliphaz, Reuel, Anah, Nimrod, Dumah, and other founders of non-Israelite nations
- **Non-Jewish religious / mythological figures** — Zoroaster, Mazdak, Tiresias, etc.
- **Topic articles, books, lists, events** — `List of …`, `Book of …`, `Tomb of …`, `Binding of Isaac`, `Reconciliation of Jacob with Esau`, `Cyrus the Great in the Bible`, etc.
- **Liturgical / classical texts** — Mishnah, Tosefta, Baraita on the …, Birkat haMinim, Targum …
- **Tribes / nations / places** — Ammonites, Hittites, Babylon, Edom, Egypt, Hebron, …
- **Modern events** — anything starting with a year (e.g. "2021 Meron crowd crush")

The exact filter is in [`scrape.py`](scrape.py) under `NON_NAME_TITLES` and `NON_NAME_PATTERNS`. Each scrape run logs all dropped entries to `cache/skipped_non_names.json` so the filter can be audited and refined.

## Files

- [`index.html`](index.html) — self-contained viewer. The CSV is embedded inline inside a `<script type="text/plain" id="csv-data">` block, so the page works when opened directly from disk (no server needed). Click column headers to sort; filter by free text or by Wiki category.
- [`names_extended.csv`](names_extended.csv) — the data, sorted alphabetically by term.
- [`scrape.py`](scrape.py) — the scraper. Idempotent and cache-aware; safe to re-run.

## License / attribution

- Names, biographical data, and category memberships are sourced from **English and Hebrew Wikipedia** (CC BY-SA 4.0) and **Wikidata** (CC0).
- Scraper code and HTML viewer in this repository are released under the **MIT License**.
