"""
Scrape Wikipedia category members (EN + HE) for biblical and medieval Jewish names,
resolve EN/HE titles via Wikidata sitelinks, and collect father/teacher/student claims.

Output: names_extended.csv with columns:
  wiki_category, term, hebrew_term, wikipedia_en, wikipedia_he, wikidata_id,
  father, student_of, student

Usage: python -u scrape.py
"""
import sys
import io
import json
import time
import csv
import os
import urllib.parse

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": "EzraBrandt-TalmudNamesExt/1.0 (https://github.com/EzraBrand; ezrabrand@gmail.com) name-glossary scraper"
}

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Curated category seeds. Label is the human-readable bucket; lang is the wiki edition.
# expand=True walks one level of subcategories under this seed (treating each subcat
# as an additional source category that inherits the parent's label).
SEEDS = [
    # Biblical (English) — expand "Hebrew Bible people" so we pick up the Book-by-book subcats
    {"lang": "en", "cat": "Category:Hebrew Bible people",          "label": "Biblical",            "expand": True},
    {"lang": "en", "cat": "Category:Torah people",                 "label": "Biblical"},
    {"lang": "en", "cat": "Category:Books of Samuel people",       "label": "Biblical"},
    {"lang": "en", "cat": "Category:Books of Kings people",        "label": "Biblical"},
    # Biblical (Hebrew)
    {"lang": "he", "cat": "קטגוריה:אישים בתנ\"ך",                 "label": "Biblical",            "expand": True},
    {"lang": "he", "cat": "קטגוריה:אישים בתורה",                  "label": "Biblical"},
    {"lang": "he", "cat": "קטגוריה:נביאים",                       "label": "Biblical"},
    {"lang": "he", "cat": "קטגוריה:מלכי ישראל",                   "label": "Biblical kings"},
    {"lang": "he", "cat": "קטגוריה:מלכי יהודה",                   "label": "Biblical kings"},
    # Talmudic (Tannaim — Mishnaic era, ~10–220 CE)
    {"lang": "en", "cat": "Category:Tannaim",                      "label": "Tannaim",             "expand": True},
    {"lang": "he", "cat": "קטגוריה:תנאים",                        "label": "Tannaim",             "expand": True},
    {"lang": "en", "cat": "Category:Mishnah rabbis",               "label": "Tannaim"},
    # Talmudic (Amoraim — ~220–500 CE)
    {"lang": "en", "cat": "Category:Amoraim",                      "label": "Amoraim",             "expand": True},
    {"lang": "he", "cat": "קטגוריה:אמוראים",                      "label": "Amoraim",             "expand": True},
    # Geonim (~600–1000 CE)
    {"lang": "en", "cat": "Category:Geonim",                       "label": "Geonim"},
    {"lang": "he", "cat": "קטגוריה:גאונים",                       "label": "Geonim"},
    # Rishonim (~1000–1500 CE)
    {"lang": "en", "cat": "Category:Rishonim",                     "label": "Medieval",            "expand": True},
    {"lang": "he", "cat": "קטגוריה:ראשונים",                      "label": "Medieval",            "expand": True},
    # Medieval Jewish theologians — expand to get century-by-century subcats
    {"lang": "en", "cat": "Category:Medieval Jewish theologians",  "label": "Medieval",     "expand": True},
    {"lang": "en", "cat": "Category:Medieval rabbis",              "label": "Medieval"},
]

# Explicit blocklist of titles that aren't personal names (events, books, lists, tribes, places, themes).
# These are dropped during row-building.
NON_NAME_TITLES = {
    # User-requested:
    "Proverbs 31", "prophet", "rape in the Hebrew Bible",
    "Reconciliation of Jacob with Esau", "Responsa of the Geonim",
    # Themes / generic concepts:
    "biblical character", "biblical judge", "theophoric name", "nephilim",
    "Almah", "Nasi", "Ushpizin", "Erev Rav", "Shophet", "Gibborim",
    "Literary prophets", "Twelve Minor Prophets", "Shulamite",
    "kuschan", "Frat Maimon", "Gatherer",
    # Group/era labels:
    "Geonim", "Rishonim", "Tosafot", "Tosafot Hachmei Anglia",
    "Hachmei Provence", "Aliyah of the Tosafists", "Halachot Gedolot",
    "Palestinian Gaonate", "Talmudic Academies in Babylonia",
    "Targum Jonathan", "Kol Bo",
    # Nations / tribes / collective ethnonyms:
    "Ammonites", "Amorites", "Anakim", "Arameans", "Assyrians",
    "Cherethites and Pelethites", "Egyptians", "Geshurites",
    "Gibeonites", "Greeks", "Hebrews", "Biblical Hittites",
    "Hivite", "Ishmaelites", "Jewish people", "Kadmonites",
    "Kenite", "Kittim", "Korahites", "Medes", "Omrides",
    "Rephaite", "Rechabite", "Gershonite", "Ahohite", "Agagite",
    "Emite", "Edomites", "Moabites", "Hittites",
    # Empires / kingdoms / places:
    "Achaemenid Empire", "Assyrian Empire", "Persian Empire",
    "Babylon", "Canaan", "Chaldea", "Dedan", "Edom", "Egypt",
    "Hebron", "Moab", "Sheba", "Geshur", "Etam", "Eshtemoa",
    "Arqa", "Heth", "Cush", "Havilah", "Kingdom of Kush",
    "Ohel", "Massa", "Sherah", "Ano",
    # Events / collective stories:
    "Binding of Isaac", "Finding of Moses", "Judgment of Solomon",
    "Daughters of Zelophehad", "Wives of Esau", "Wives aboard Noah's Ark",
    "Sons of God", "Sons of Zadok", "Sisera's mother", "Song of Hannah",
    "Raising of the son of the widow of Zarephath",
    "Raising of the son of the woman of Shunem",
    "Tomb of the Matriarchs", "Tomb of Isaac Gaon",
    "Pharaoh's daughter (wife of Solomon)", "Pharaoh's magicians",
    "Widow of Zarephath", "Wife of Phinehas", "Wise woman of Abel",
    "Witch of Endor", "Woman of Shunem", "Woman of Tekoa", "Woman of Thebez",
    "Women in the Bible", "Mount of Olives Hoshana Rabbah ceremony",
    "The Double Gate", "The Levite's Concubine", "David's Mighty Warriors",
    "Daughter of Jephthah", "Jephtah's Daughter: A Biblical Tragedy",
    "Lot and his daughters", "Lot's daughters", "Lot's wife", "Noah's wife",
    "Job's wife", "Isaiah's wife", "wife of Manoah", "son of Shelomith",
    "Korah and his group dispute", "Joab, Asahel, and Abishai",
    "Joseph, the Baker and the Butler", "Bigthan and Teresh",
    "Eldad and Medad", "Hophni and Phinehas", "Mahlon and Chilion",
    "Nadab and Abihu", "Shadrach, Meshach, and Abednego",
    "Perez and Zerah", "David and Goliath", "Jacob and Esau",
    "ten sons of Haman", "seven shepherds", "Bat Choua",
    "the Lord appears to Abraham by the oaks of Mamre",
    "Zipporah at the inn", "Arbor mirabilis", "Jaffe family",
    "Cyrus the Great in the Bible", "I grandi condottieri",
    # Minor index articles:
    "Minor Biblical characters, L-Z",
    # Foreign / non-Jewish figures (modern occultists, founders of non-Jewish
    # religions, mythological figures, antagonists from other peoples).
    "Aleister Crowley", "Edmund Creffield", "Joanna Southcott",
    "Tiresias", "Hiram Abiff",
    "Zoroaster", "Mazdak", "Zulaikha",
    # Foreign biblical kings and officials — non-Israelite, kept out of a Jewish-names index.
    # Persian:
    "Cyrus the Great", "Darius I", "Darius the Mede", "Ahasuerus",
    "Haman", "Vashti", "Memucan", "Hegai", "Bigthan and Teresh",
    # Babylonian:
    "Nebuchadnezzar II", "Belshazzar", "Nabonidus",
    "Amel-Marduk", "Neriglissar",
    # Assyrian:
    "Sennacherib", "Sargon II", "Shalmaneser V", "Tiglath-Pileser III",
    "Rabsaris", "Rabshakeh",
    # Egyptian:
    "Pharaoh", "Apries", "Necho II", "Shishak", "Taharqa",
    "Tahpenes", "Hagar", "Potiphar", "Potipherah",
    # Moabite / Ammonite:
    "Balak", "Eglon", "Mesha",
    "Nahash of Ammon", "Hanun", "Shobi", "Baalis",
    # Edomite:
    "Hadad (Bible)", "Hadad the Edomite",
    # Aramean / Syrian:
    "Hazael", "Rezin", "Rezon the Syrian",
    "Hadadezer ben Rehob", "Naaman", "Tou",
    "Balaam", "Beor",
    # Phoenician / Tyrian:
    "Hiram", "Hiram I", "Ithobaal I", "Jezebel",
    # Canaanite:
    "Adoni-Bezek", "Adonizedek", "Jabin", "Sisera",
    "Uriah the Hittite", "Elon the Hittite",
    # Philistine:
    "Achish", "Goliath", "Delilah",
    # Amalekite:
    "Agag",
    # Elamite / Median / other ancient:
    "Chedorlaomer", "Deioces", "Arioch", "Tidal",
    # Cushite invader (distinct from the Israelite Zerah son of Judah, who stays):
    "Zerah the Cushite",
    # Mythical / non-Jewish foreigners:
    "Geshem the Arabian",
    # Esau's line (Edomites) — non-Israelite descendants:
    "Esau", "Amalek", "Eliphaz", "Reuel", "Anah",
    # Ishmael and his line (Arab progenitors) — non-Israelite:
    "Ishmael", "Dumah",
    # Other non-Israelite Genesis founders / antagonists:
    "Nimrod", "Raamah",
    # Modern events / liturgical texts (not personal names):
    "2021 Meron crowd crush", "Askinu L'seudasa", "Birkat haMinim",
    # Classical / canonical texts (not personal names):
    "Mishnah", "Tosefta", "Talmud", "Gemara", "Halakha",
    # Modern Israeli moshav, not a Tannaitic figure:
    "Beit Gamliel",
    # Modern Israeli religious-Zionist youth movement, not a Tannaitic figure:
    "Bnei Akiva",
    # Misc. individual removals:
    "Nahman Ktufa",
    "נביא עיוור",   # "Blind prophet" — a phrase / role label, not a personal name
    "Bar Yohai",   # Modern Israeli moshav named after Shimon bar Yochai (the sage himself is still in the index)
    "Tavi (slave)",  # Canaanite slave of Rabban Gamliel — non-Israelite
    # Non-Israelite biblical figures missed in the earlier pass:
    "Cozbi",        # Midianite princess (Numbers 25)
    "Debir",        # Canaanite king of Eglon (Joshua 10) / disambiguation page
    "Efron",        # Efron the Hittite (Genesis 23)
    "Elioud",       # Non-canonical figure from Aramaic/extra-biblical Nephilim genealogy
    # Hebrew-only Wikipedia entries that are events / places / phrases / foreign figures, not personal names:
    "פרעה",                    # generic title "Pharaoh", here referring to Pharaoh of Moses' time
    "פראם",                    # non-Israelite figure
    "סוא מלך מצרים",            # "So, king of Egypt" — foreign king
    "ענר, אשכול וממרא",         # Non-Israelite allies of Abraham (multi-person article)
    "על דאטפת אטפוך",           # Talmudic Aramaic phrase ("because you drowned …")
    "בני הנביאים",              # "Sons of the prophets" — collective
    "בני משה שמעבר לסמבטיון",   # "Sons of Moses beyond Sambation" — mythical collective
    "בני עבדי שלמה",            # "Sons of Solomon's servants" — collective
    "בני קטורה",                # "Sons of Keturah" — non-Israelite descendants of Abraham
    "הפרדס של עקיבא",           # "The orchard of Akiva" — Pardes story, not a person
    "מתו בעטיו של נחש",         # Talmudic phrase "they died only because of the serpent" — aggadic concept
    # Additional Hebrew topic / event / phrase / foreign-figure entries:
    "חכמי יבנה ברומא",          # "Sages of Yavneh in Rome" — collective event
    "חיבור ספר הזוהר",          # "Composition of the Zohar" — event / topic
    "ואמרתם כה לחי",            # "And you shall say thus to the living" — biblical phrase
    "השועל והדגים",             # "The fox and the fishes" — aggadic parable
    "טוב שבגויים הרוג",         # "The best of the gentiles, kill" — Talmudic phrase
    "הקדשה לנבואה",             # "Consecration to prophecy" — concept
    "הנבואה במסורת ישראל",      # "Prophecy in Jewish tradition" — topic
    "הלל לומד תורה",            # "Hillel studies Torah" — aggadic story
    # Anonymous biblical figures / pair articles / events / topics / non-Israelite kings:
    "אחימן ששי ותלמי",          # Ahiman, Sheshai, and Talmai — Anakim giants (non-Israelite, triple article)
    "אם אין אני לי מי לי",      # Hillel's famous saying, not a name
    "ברית יצחק ואבימלך",        # Covenant of Isaac and Abimelech — event
    "דוד וישבי",                # David and Ishbi-benob — event
    "הוהם מלך חברון",           # Hoham king of Hebron — non-Israelite Canaanite king
    "הורם מלך גזר",             # Horam king of Gezer — non-Israelite Canaanite king
    "יפיע מלך לכיש",            # Yafia king of Lachish — non-Israelite Canaanite king
    "הולך בדרכו עקיבא",         # Story-title phrase, not a person
    "הנביא מבית אל",            # "The prophet from Bethel" — anonymous figure (1 Kings 13)
    "יואל ואביה בני שמואל",     # Joel and Abijah, Samuel's sons — pair article
    "ישיבת רשב\"י",             # "Yeshiva of Rashbi" — institution / place
    "מיילדות במקרא",            # "Midwifery in the Bible" — topic article
}

# Regex patterns matched against the title to reject likely non-names.
import re as _re_for_patterns
NON_NAME_PATTERNS = [
    _re_for_patterns.compile(r"^[a-z]"),                        # starts lowercase (English)
    _re_for_patterns.compile(r"^[Ll]ist of "),                   # list articles
    _re_for_patterns.compile(r"^[Tt]imeline of "),               # timeline articles
    _re_for_patterns.compile(r" in the Hebrew Bible$"),
    _re_for_patterns.compile(r" in the Bible$"),
    _re_for_patterns.compile(r" in rabbinic literature$"),
    _re_for_patterns.compile(r"^Book of "),                      # book articles (not people)
    _re_for_patterns.compile(r"\bMinor Biblical characters\b"),
    _re_for_patterns.compile(r"^Tomb of "),
    _re_for_patterns.compile(r"^Tombs of "),
    _re_for_patterns.compile(r"^Responsa "),
    _re_for_patterns.compile(r"^Kingdom of "),
    _re_for_patterns.compile(r"\bEmpire$"),
    _re_for_patterns.compile(r"\bGaonate$"),
    _re_for_patterns.compile(r"^\d"),                            # year-prefixed events
    _re_for_patterns.compile(r"^Baraita\b"),                     # rabbinic text articles
    _re_for_patterns.compile(r"^Sefer "),                        # "Book of X" rabbinic works
    _re_for_patterns.compile(r"^Midrash "),                      # midrashic works
    _re_for_patterns.compile(r"^Targum "),                       # Targum works
    _re_for_patterns.compile(r"^Pirkei "),                       # Pirkei X works (e.g. Pirkei Avot)
    _re_for_patterns.compile(r"^Halachot "),                     # Halachot collections
    # Hebrew-language phrase / event / place prefixes (Hebrew-only Wikipedia article titles):
    _re_for_patterns.compile(r"^מערת "),                          # "Cave of X" — place
    _re_for_patterns.compile(r"^מלחמת "),                         # "War of X" — event
    _re_for_patterns.compile(r"^מיתת "),                          # "Death of X" — event
    _re_for_patterns.compile(r"^מציאת "),                         # "Finding of X" — event
    _re_for_patterns.compile(r"^נס "),                            # "Miracle of X" — event
    _re_for_patterns.compile(r"^פיוט "),                          # "Piyyut X" — liturgical work
    _re_for_patterns.compile(r"^שבעת "),                          # "Seven X" — collective
    _re_for_patterns.compile(r"^חורבן "),                         # "Destruction of X" — event
    _re_for_patterns.compile(r"^עקדת "),                          # "Binding of X" — event (Akedat Yitzchak)
    _re_for_patterns.compile(r"^קריעת "),                         # "Splitting/tearing of X" — event (Kri'at Yam Suf)
    _re_for_patterns.compile(r"^קבר "),                           # "Grave of X" — place
    _re_for_patterns.compile(r"^גלות "),                          # "Exile of X" — event
    _re_for_patterns.compile(r"^הבטחת "),                         # "Promise of X" — event
    _re_for_patterns.compile(r"^פרשת "),                          # "Parashat X" — Torah portion / episode
]


def is_non_name(title: str) -> bool:
    if not title:
        return False
    if title in NON_NAME_TITLES:
        return True
    for pat in NON_NAME_PATTERNS:
        if pat.search(title):
            return True
    return False

# Subcategories we DON'T want to walk into (meta / non-name / off-topic).
SUBCAT_BLOCKLIST = {
    "Category:Cultural depictions of Hebrew Bible people",
    "Category:Hebrew Bible people in Islam",
    "Category:Hebrew Bible people in Mandaeism",
    "Category:Hebrew Bible people in rabbinic literature",
    "קטגוריה:קטגוריות לפי אישי תנ\"ך",
    "קטגוריה:אישים בתנ\"ך המוזכרים במקורות חיצוניים",
    "קטגוריה:אישים בתנ\"ך שהונצחו על בולי ישראל",
    "קטגוריה:אישים בתנ\"ך שעל שמם כוכב לכת מינורי",
    "קטגוריה:אישים בתנ\"ך שהגיעו לגיל 900",
}


def api_get(endpoint, params, retries=6, base_wait=15):
    for i in range(retries):
        try:
            r = requests.get(endpoint, headers=HEADERS, params=params, timeout=60)
        except requests.RequestException as e:
            wait = base_wait * (i + 1)
            print(f"  network error {e!r}, sleeping {wait}s", flush=True)
            time.sleep(wait)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            wait = base_wait * (i + 1)
            print(f"  HTTP {r.status_code}, sleeping {wait}s", flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {retries} retries: {endpoint} {params}")


def category_members(cat, lang, cmtype="page"):
    """Fetch all mainspace members for a category. cmtype='page' for articles, 'subcat' for subcategories."""
    api = f"https://{lang}.wikipedia.org/w/api.php"
    out, cont = [], {}
    page_num = 0
    while True:
        page_num += 1
        params = {
            "action": "query", "format": "json", "formatversion": 2,
            "list": "categorymembers", "cmtitle": cat,
            "cmlimit": "500", "cmtype": cmtype, **cont,
        }
        if cmtype == "page":
            params["cmnamespace"] = "0"
        t0 = time.time()
        data = api_get(api, params)
        batch = data.get("query", {}).get("categorymembers", [])
        out.extend(batch)
        dt = time.time() - t0
        if page_num > 1 or "continue" in data:
            print(f"    page {page_num}: +{len(batch)} (total {len(out)}) [{dt:.2f}s]", flush=True)
        if "continue" not in data:
            break
        cont = data["continue"]
        time.sleep(1.0)
    return out


def expand_seeds(seeds):
    """For seeds with expand=True, fetch direct subcats and add each as an additional source."""
    expanded = []
    for s in seeds:
        expanded.append({"lang": s["lang"], "cat": s["cat"], "label": s["label"]})
        if s.get("expand"):
            try:
                subs = category_members(s["cat"], s["lang"], cmtype="subcat")
            except Exception as e:
                print(f"  ERROR expanding {s['cat']}: {e}", flush=True)
                continue
            kept = 0
            for sub in subs:
                title = sub["title"]
                if title in SUBCAT_BLOCKLIST:
                    continue
                expanded.append({"lang": s["lang"], "cat": title, "label": s["label"]})
                kept += 1
            print(f"  expanded {s['cat']} -> {kept} subcats", flush=True)
    return expanded


def get_qids_batch(titles, lang):
    """Map title -> wikibase Q-ID (handles redirects)."""
    if not titles:
        return {}
    api = f"https://{lang}.wikipedia.org/w/api.php"
    result = {}
    total_batches = (len(titles) + 49) // 50
    # 50 titles per batch
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        batch_num = i // 50 + 1
        print(f"    QID batch {batch_num}/{total_batches} ({len(chunk)} titles, {lang})", flush=True)
        params = {
            "action": "query", "format": "json", "formatversion": 2,
            "prop": "pageprops", "ppprop": "wikibase_item",
            "titles": "|".join(chunk), "redirects": 1,
        }
        data = api_get(api, params)
        pages = data.get("query", {}).get("pages", [])
        # Track redirects: original -> resolved
        normalized = {n["from"]: n["to"] for n in data.get("query", {}).get("normalized", [])}
        redirects = {r["from"]: r["to"] for r in data.get("query", {}).get("redirects", [])}
        title_to_qid = {}
        for p in pages:
            if p.get("missing"):
                continue
            qid = p.get("pageprops", {}).get("wikibase_item")
            title_to_qid[p["title"]] = qid
        for orig in chunk:
            resolved = orig
            # Apply normalization + redirect chain
            if resolved in normalized:
                resolved = normalized[resolved]
            if resolved in redirects:
                resolved = redirects[resolved]
            result[orig] = title_to_qid.get(resolved)
        time.sleep(1.0)
    return result


def get_wikidata_entities(qids):
    """Batch-fetch full entity data (labels, sitelinks, claims) for QIDs."""
    if not qids:
        return {}
    api = "https://www.wikidata.org/w/api.php"
    result = {}
    qids = list(qids)
    total_batches = (len(qids) + 49) // 50
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        batch_num = i // 50 + 1
        print(f"    Wikidata batch {batch_num}/{total_batches} ({len(chunk)} entities)", flush=True)
        params = {
            "action": "wbgetentities", "format": "json",
            "ids": "|".join(chunk),
            "props": "labels|sitelinks|claims",
            "languages": "en|he",
            "sitefilter": "enwiki|hewiki",
        }
        data = api_get(api, params)
        for qid, ent in data.get("entities", {}).items():
            result[qid] = ent
        time.sleep(1.0)
    return result


def resolve_claim_labels(entities, claim_qids):
    """For a set of QIDs referenced as claim values, fetch their en+he labels."""
    return get_wikidata_entities(claim_qids) if claim_qids else {}


def extract_claim_qids(entity, prop):
    """Extract list of QID strings from a property's claims (item-typed)."""
    out = []
    for claim in entity.get("claims", {}).get(prop, []) or []:
        try:
            dv = claim["mainsnak"]["datavalue"]["value"]
            if isinstance(dv, dict) and "id" in dv:
                out.append(dv["id"])
        except (KeyError, TypeError):
            continue
    return out


def extract_claim_times(entity, prop):
    """Extract list of formatted date strings from a property's time-typed claims.
    Wikidata times look like '+1100-01-01T00:00:00Z' with a precision int:
      9 = year, 10 = month, 11 = day. Lower precision means broader.
    BCE dates have a '-' sign prefix; we render as 'NNN BCE'."""
    out = []
    for claim in entity.get("claims", {}).get(prop, []) or []:
        try:
            v = claim["mainsnak"]["datavalue"]["value"]
            time = v.get("time", "")           # e.g. '+1100-01-01T00:00:00Z' or '-0586-...'
            precision = v.get("precision", 11)
            if not time:
                continue
            sign = time[0]
            body = time[1:]                    # drop sign
            year_str, rest = body.split("-", 1)
            year = int(year_str)
            month_day = rest.split("T", 1)[0]  # 'MM-DD'
            mm, dd = month_day.split("-")
            if precision >= 11:
                date_str = f"{year:04d}-{mm}-{dd}"
            elif precision == 10:
                date_str = f"{year:04d}-{mm}"
            elif precision == 9:
                date_str = f"{year:04d}"
            elif precision == 8:
                date_str = f"{year // 10 * 10}s"
            elif precision == 7:
                date_str = f"{year // 100 + (1 if year % 100 else 0)}c"   # rough century
            else:
                date_str = f"{year:04d}"
            if sign == "-":
                # strip leading zeros for BCE display
                date_str = date_str.lstrip("0") or "0"
                date_str = f"{date_str} BCE"
            out.append(date_str)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def label_for(ent, lang="en"):
    if not ent:
        return ""
    labels = ent.get("labels", {})
    if lang in labels:
        return labels[lang]["value"]
    # fallback
    for v in labels.values():
        return v["value"]
    return ""


def sitelink_url(ent, site):
    """Return the Wikipedia URL for a given site (enwiki/hewiki), or empty string."""
    if not ent:
        return ""
    sl = ent.get("sitelinks", {}).get(site)
    if not sl:
        return ""
    title = sl["title"]
    lang = site.replace("wiki", "")
    return f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"


def sitelink_title(ent, site):
    if not ent:
        return ""
    sl = ent.get("sitelinks", {}).get(site)
    return sl["title"] if sl else ""


def main():
    # ---------- Phase 1: collect category members per seed ----------
    members_cache = os.path.join(CACHE_DIR, "members.json")
    if os.path.exists(members_cache):
        with open(members_cache, "r", encoding="utf-8") as f:
            seed_members = json.load(f)
        print(f"loaded cached members for {len(seed_members)} seeds", flush=True)
    else:
        print(f"expanding {len(SEEDS)} root seeds", flush=True)
        all_seeds = expand_seeds(SEEDS)
        print(f"-> {len(all_seeds)} total category fetches", flush=True)
        seed_members = []
        for s in all_seeds:
            print(f"fetching {s['lang']} :: {s['cat']}", flush=True)
            try:
                members = category_members(s["cat"], s["lang"])
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                members = []
            print(f"  -> {len(members)} members", flush=True)
            seed_members.append({**s, "members": members})
        with open(members_cache, "w", encoding="utf-8") as f:
            json.dump(seed_members, f, ensure_ascii=False, indent=2)

    # ---------- Phase 2: resolve titles -> QIDs per language ----------
    qid_cache = os.path.join(CACHE_DIR, "title_to_qid.json")
    if os.path.exists(qid_cache):
        with open(qid_cache, "r", encoding="utf-8") as f:
            title_qid = json.load(f)
    else:
        title_qid = {"en": {}, "he": {}}
        for s in seed_members:
            lang = s["lang"]
            titles = [m["title"] for m in s["members"]]
            print(f"resolving QIDs for {len(titles)} titles ({lang})", flush=True)
            mapping = get_qids_batch(titles, lang)
            title_qid[lang].update(mapping)
        with open(qid_cache, "w", encoding="utf-8") as f:
            json.dump(title_qid, f, ensure_ascii=False, indent=2)

    # ---------- Phase 3: build entry list keyed by QID (dedup across categories) ----------
    # entry: qid -> {wiki_categories: set, source_titles: dict}
    by_qid = {}
    no_qid = []  # entries that lack a wikidata mapping
    for s in seed_members:
        lang = s["lang"]
        label = s["label"]
        for m in s["members"]:
            title = m["title"]
            qid = title_qid.get(lang, {}).get(title)
            if qid:
                bucket = by_qid.setdefault(qid, {"labels": set(), "src": {}})
                bucket["labels"].add(label)
                bucket["src"].setdefault(lang, title)
            else:
                no_qid.append({"lang": lang, "title": title, "label": label})
    print(f"entries with QID: {len(by_qid)}; entries missing QID: {len(no_qid)}", flush=True)

    # ---------- Phase 4: fetch Wikidata entities for primary QIDs ----------
    ent_cache = os.path.join(CACHE_DIR, "entities.json")
    if os.path.exists(ent_cache):
        with open(ent_cache, "r", encoding="utf-8") as f:
            entities = json.load(f)
    else:
        print(f"fetching {len(by_qid)} primary entities", flush=True)
        entities = get_wikidata_entities(list(by_qid.keys()))
        with open(ent_cache, "w", encoding="utf-8") as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)

    # ---------- Phase 5: collect referenced QIDs for relation + place properties ----------
    # Item-typed claims (resolved to labels):
    ITEM_PROPS = {
        "father": "P22",
        "student_of": "P1066",
        "student": "P802",
        "place_of_birth": "P19",
        "place_of_death": "P20",
    }
    # Time-typed claims (formatted as date strings):
    TIME_PROPS = {
        "date_of_birth": "P569",
        "date_of_death": "P570",
    }
    ref_qids = set()
    for qid, ent in entities.items():
        for prop in ITEM_PROPS.values():
            for v in extract_claim_qids(ent, prop):
                if v != qid:
                    ref_qids.add(v)
    ref_cache = os.path.join(CACHE_DIR, "ref_entities.json")
    if os.path.exists(ref_cache):
        with open(ref_cache, "r", encoding="utf-8") as f:
            ref_entities = json.load(f)
    else:
        print(f"fetching {len(ref_qids)} referenced entities for relationship labels", flush=True)
        ref_entities = get_wikidata_entities(list(ref_qids))
        with open(ref_cache, "w", encoding="utf-8") as f:
            json.dump(ref_entities, f, ensure_ascii=False, indent=2)

    # ---------- Phase 6: write CSV ----------
    out_csv = os.path.join(HERE, "names_extended.csv")
    fieldnames = [
        "category", "term", "hebrew_term",
        "wikipedia_en", "wikipedia_he", "wikidata_id",
        "father", "student_of", "student",
        "date_of_birth", "place_of_birth",
        "date_of_death", "place_of_death",
    ]
    rows = []
    skipped_non_names = []
    for qid, bucket in by_qid.items():
        ent = entities.get(qid, {})
        en_title = sitelink_title(ent, "enwiki")
        he_title = sitelink_title(ent, "hewiki")
        # term = EN label or EN title or HE label as fallback
        term = label_for(ent, "en") or en_title or label_for(ent, "he") or he_title or qid
        hebrew_term = label_for(ent, "he") or he_title

        # Drop obvious non-names (events, books, lists, tribes, places, themes).
        if is_non_name(term) or is_non_name(en_title) or is_non_name(he_title):
            skipped_non_names.append({"qid": qid, "term": term, "en": en_title, "he": he_title})
            continue

        def resolve(prop_qids):
            out = []
            for q in prop_qids:
                e = ref_entities.get(q) or entities.get(q)
                en = label_for(e, "en")
                he = label_for(e, "he")
                if en and he and en != he:
                    out.append(f"{en} / {he}")
                else:
                    out.append(en or he or q)
            return "; ".join(out)

        father = resolve(extract_claim_qids(ent, ITEM_PROPS["father"]))
        student_of = resolve(extract_claim_qids(ent, ITEM_PROPS["student_of"]))
        student = resolve(extract_claim_qids(ent, ITEM_PROPS["student"]))
        place_of_birth = resolve(extract_claim_qids(ent, ITEM_PROPS["place_of_birth"]))
        place_of_death = resolve(extract_claim_qids(ent, ITEM_PROPS["place_of_death"]))
        date_of_birth = "; ".join(extract_claim_times(ent, TIME_PROPS["date_of_birth"]))
        date_of_death = "; ".join(extract_claim_times(ent, TIME_PROPS["date_of_death"]))

        rows.append({
            "category": "; ".join(sorted(bucket["labels"])),
            "term": term,
            "hebrew_term": hebrew_term,
            "wikipedia_en": sitelink_url(ent, "enwiki"),
            "wikipedia_he": sitelink_url(ent, "hewiki"),
            "wikidata_id": qid,
            "father": father,
            "student_of": student_of,
            "student": student,
            "date_of_birth": date_of_birth,
            "place_of_birth": place_of_birth,
            "date_of_death": date_of_death,
            "place_of_death": place_of_death,
        })

    # Sort by term for stable output
    rows.sort(key=lambda r: r["term"].lower())

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"wrote {len(rows)} rows to {out_csv}", flush=True)

    # also save a tiny diagnostic file showing entries that lacked QIDs
    with open(os.path.join(CACHE_DIR, "no_qid.json"), "w", encoding="utf-8") as f:
        json.dump(no_qid, f, ensure_ascii=False, indent=2)
    # And entries that were dropped as non-names — useful for tuning the filter
    with open(os.path.join(CACHE_DIR, "skipped_non_names.json"), "w", encoding="utf-8") as f:
        json.dump(skipped_non_names, f, ensure_ascii=False, indent=2)
    print(f"skipped {len(skipped_non_names)} non-name entries (logged to cache/skipped_non_names.json)", flush=True)

    # ---------- Phase 7: bake CSV into index.html so file:// loads work ----------
    html_path = os.path.join(HERE, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(out_csv, "r", encoding="utf-8") as f:
            csv_text = f.read()
        # Defuse any literal "</script>" inside the CSV so it won't close our wrapper.
        safe_csv = csv_text.replace("</script>", "<\\/script>")
        marker = '<script type="text/plain" id="csv-data">'
        start = html.find(marker)
        if start != -1:
            end = html.find("</script>", start)
            if end != -1:
                new_html = html[:start + len(marker)] + safe_csv + html[end:]
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(new_html)
                print(f"baked {len(csv_text)} bytes of CSV into {html_path}", flush=True)
            else:
                print("warning: could not find closing </script> for csv-data block", flush=True)
        else:
            print("warning: no #csv-data placeholder in index.html — skipping bake", flush=True)


if __name__ == "__main__":
    main()
