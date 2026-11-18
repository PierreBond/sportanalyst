"""Map DB team names (football-data.org style) to model team classes.

Single source of truth used by the API (main.py), batch_predict.py and
check_team_mapping.py so the mappings can never drift apart.
"""
import re
import unicodedata

TEAM_PREFIXES = ["SE ", "CR ", "CA ", "SC ", "EC ", "GR ", "AE ", "AD ",
                 "RC ", "RCD ", "SS ", "SSC ", "TSG ", "SV ", "OGC ",
                 "PSV ", "SBV ", "VfB ", "VfL ", "RB ", "1. FC ",
                 "1. FSV ", "FC ", "US "]
TEAM_SUFFIXES = [" FC", " CF", " EC", " FR", " FBC", " FBPA", " AF",
                 " GF", " US", " AC", " OSC", " AFC", " UD", " Calcio",
                 " Balompié", " de Fútbol", " de Barcelona", " Alsace"]
TEAM_REMOVALS = [" Paulista", " de Madrid", " de La Coruña", " 1901",
                 " 1963", " 1899", " Tilburg", " Leuwarden"]
TEAM_SPECIAL = {
    "ca mineiro": "Atletico-MG",
    "ca paranaense": "Atletico Paranaense",
    "fc bayern munchen": "Bayern Munich",
    "bayern munchen": "Bayern Munich",
    "bayer 04 leverkusen": "Bayer Leverkusen",
    "1. fc union berlin": "Union Berlin",
    "paris saint-germain fc": "Paris Saint Germain",
    "paris saint-germain": "Paris Saint Germain",
    "racing club de lens": "Lens",
    "tsg 1899 hoffenheim": "1899 Hoffenheim",
    "ss lazio": "Lazio",
    "ssc napoli": "Napoli",
    "fc barcelona": "Barcelona",
    "rc celta de vigo": "Celta Vigo",
    "rcd espanyol de barcelona": "Espanyol",
    "real betis balompié": "Real Betis",
    "real betis balompie": "Real Betis",
    "real sociedad de fútbol": "Real Sociedad",
    "real sociedad de futbol": "Real Sociedad",
    "sevilla fc": "Sevilla",
    "valencia cf": "Valencia",
    "villarreal cf": "Villarreal",
    "athletic club": "Athletic Club",
    "real madrid cf": "Real Madrid",
    "rc strasbourg alsace": "Strasbourg",
    "stade brestois 29": "Stade Brestois 29",
    "stade rennais fc 1901": "Rennes",
    "olympique lyonnais": "Lyon",
    "olympique de marseille": "Marseille",
    "ogc nice": "Nice",
    "toulouse fc": "Toulouse",
    "lecce": "Lecce",
    "us lecce": "Lecce",
    "us sassuolo calcio": "Sassuolo",
    "udinese calcio": "Udinese",
    "torino fc": "Torino",
    "venezia fc": "Venezia",
    "parma calcio 1913": "Parma",
    "genoa cfc": "Genoa",
    "cagliari calcio": "Cagliari",
    "empoli fc": "Empoli",
    "hellas verona fc": "Hellas Verona",
    "monza": "Monza",
    "frosinone calcio": "Frosinone",
    "hamburger sv": "Hamburger SV",
    "werder bremen": "Werder Bremen",
    "fortuna düsseldorf": "Fortuna Dusseldorf",
    "fortuna dusseldorf": "Fortuna Dusseldorf",
    "sv darmstadt 98": "SV Darmstadt 98",
    "holstein kiel": "Holstein Kiel",
    "fc heidenheim": "FC Heidenheim",
    "vfl bochum": "Vfl Bochum",
    "1. fc köln": "1. FC Köln",
    "1. fc koln": "1. FC Köln",
    "borussia mönchengladbach": "Borussia Monchengladbach",
    "borussia monchengladbach": "Borussia Monchengladbach",
    "leeds united fc": "Leeds",
    "burnley fc": "Burnley",
    "sheffield united fc": "Sheffield Utd",
    "luton town fc": "Luton",
    "ipswich town fc": "Ipswich",
    "1. fsv mainz 05": "FSV Mainz 05",
    "ac monza": "Monza",
    "acf fiorentina": "Fiorentina",
    "afc ajax": "Ajax",
    "afc bournemouth": "Bournemouth",
    "aj auxerre": "Auxerre",
    "as monaco fc": "Monaco",
    "az": "AZ Alkmaar",
    "angers sco": "Angers",
    "atalanta bc": "Atalanta",
    "bologna fc 1909": "Bologna",
    "brighton & hove albion fc": "Brighton",
    "club atletico de madrid": "Atletico Madrid",
    "deportivo alaves": "Alaves",
    "es troyes ac": "Estac Troyes",
    "fc internazionale milano": "Inter",
    "fc twente '65": "Twente",
    "feyenoord rotterdam": "Feyenoord",
    "nec": "NEC Nijmegen",
    "newcastle united fc": "Newcastle",
    "psv": "PSV Eindhoven",
    "sc cambuur-leeuwarden": "Cambuur",
    "tottenham hotspur fc": "Tottenham",
}


# Clubs the two data providers store under different official names, so the
# canonicalizer lands them in two classes and each half only sees half of the
# club's matches. The class that holds the history wins: a fixture stored
# under the thin name then gets the full sample. Without this, PSV was
# served an Elo of 1549 instead of 1797.
CANON_FIX = {
    "acf fiorentina": "fiorentina",
    "aj auxerre": "auxerre",
    "as monaco": "monaco",
    "az": "az alkmaar",
    "cr flamengo": "flamengo",
    "cr vasco da gama": "vasco da gama",
    "deportivo alaves": "alaves",
    "es troyes": "estac troyes",
    "mineiro": "atletico mg",
    "nec": "nec nijmegen",
    "olympique lyonnais": "lyon",
    "olympique marseille": "marseille",
    "ogc nice": "nice",
    "paranaense": "atletico paranaense",
    "paris": "paris saint germain",
    "psv": "psv eindhoven",
    "racing lens": "lens",
    "rayo vallecano madrid": "rayo vallecano",
    "sbv excelsior": "excelsior",
    "se palmeiras": "palmeiras",
    "stade rennes": "rennes",
}


def remove_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


# Tokens that carry no club identity. Removing them keeps one club in one
# class ("Atalanta BC" / "Atalanta", "Brighton & Hove Albion FC" / "Brighton").
# Tokens are only dropped when something is left, so "FC Barcelona" keeps
# "barcelona" while "Espanyol de Barcelona" becomes "espanyol".
CLUB_TOKENS = (
    "fc|sc|cf|ac|afc|ca|rb|ssc|ss|rc|rcd|sv|vfl|vfb|tsg|us|club|de|del"
    "|cfc|fbc|fbpa|ec|osc|sco|bc|fr|af|gf|ud"
    "|calcio|balompie|futbol|town|united|hotspur|rotterdam|tilburg|leeuwarden"
    "|alsace|milano|barcelona|hove|albion|paulista|coruna|and"
)


def canon_team(name: str) -> str:
    """Canonicalize a club name so spelling variants map to one value.

    Training and serving both key on this form. It used to live in
    train_model.py only, which meant the API looked up raw database names and
    missed every team, handing out the default Elo instead.
    """
    n = remove_accents(name).lower().strip()
    n = n.replace("&", " and ")
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    n = re.sub(r"\b\d+\b", " ", n)
    n = n.replace("munchen", "munich").replace("internazionale", "inter")
    n = n.replace("rennais", "rennes")
    n = re.sub(r"\s+", " ", n).strip()
    for token in CLUB_TOKENS.split("|"):
        candidate = re.sub(rf"\b{token}\b", " ", n).strip()
        if not candidate:
            continue
        # Dropping the token must not leave a meaningless fragment: "Barcelona
        # B" became "b", "La Coruna" became "la", "Man United" became "man".
        if " " not in candidate and len(candidate) < 4:
            continue
        n = candidate
    n = re.sub(r"\s+", " ", n).strip()
    return CANON_FIX.get(n, n)


def resolve_team_name(db_name: str, known: set[str]) -> str:
    """Return the model team class for a DB team name, or db_name if unknown.

    Every successful branch returns a name from `known`, so callers can check
    `resolve_team_name(n, known) in known` to test resolvability.
    """
    if not db_name or db_name in known:
        return db_name
    normalized = remove_accents(db_name).lower().strip()
    special = TEAM_SPECIAL.get(normalized)
    if special and special in known:
        return special
    for p in TEAM_PREFIXES:
        if db_name.startswith(p) and db_name[len(p):] in known:
            return db_name[len(p):]
    for s in TEAM_SUFFIXES:
        if db_name.endswith(s) and db_name[:-len(s)] in known:
            return db_name[:-len(s)]
    for r in TEAM_REMOVALS:
        candidate = db_name.replace(r, "")
        if candidate in known:
            return candidate
    db_clean = normalized
    for k in known:
        if remove_accents(k).lower().strip() == db_clean:
            return k
    # Fallback: strip standalone numbers (e.g. "Bayer 04 Leverkusen" -> "Bayer Leverkusen")
    no_numbers = re.sub(r'\b\d+\b', '', db_clean).strip()
    no_numbers = re.sub(r'\s+', ' ', no_numbers)
    for k in known:
        if remove_accents(k).lower().strip() == no_numbers:
            return k
    return db_name
