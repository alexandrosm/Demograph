"""Civilizational classification by religion-language fingerprint.

Cascade per polity: hand override -> first Wikidata religion claim (P140)
-> language family with era rules -> geographic centroid fallback.

Families (color spheres): americas (pre-Columbian + indigenous), westeurope
(Latin Christendom + classical Mediterranean + its New-World offshoots),
orthodox (Byzantine/Slavic), africa, ancientne (pre-Islamic Near East:
Egypt/Mesopotamia/Zoroastrian Persia), islam, steppe (Tengric/nomadic),
dharmic (Indic sphere incl. Indianized SE Asia), sinic (China/Korea/Vietnam),
japan. Subfamily = language family, for shade variation within a sphere.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINGERPRINT_JSON = ROOT / "data" / "raw" / "wikidata_fingerprint.json"

ISLAM_ERA = 622  # language-based Islamic-sphere attribution only after this

OVERRIDES = {
    "Roman Empire": ("westeurope", "classical"),  # wikidata claim is late-empire
    "Indus Valley Civilization": ("dharmic", "harappan"),
    "British Africa": ("africa", "colonial"),
    "French Africa": ("africa", "colonial"),
    "Byzantine Empire": ("orthodox", "Greek"),  # no wikidata signal
    "Caliphate of Córdoba": ("islam", "Semitic"),  # al-Andalus, no signal
    "Ethiopia": ("africa", "Semitic"),  # Amharic->islam trap; Orthodox Christian
    "French Fifth Republic": ("westeurope", "Romance"),  # Algeria-era centroid
    "French Indochina": ("sinic", "colonial"),  # colonial Vietnam
    "House of Jagiellon": ("westeurope", "SlavicWest"),  # Catholic, no signal
    "Kamarupa Kingdom": ("dharmic", "IndoAryan"),  # Assam, geo box edge
    "Mongol Empire": ("steppe", "Mongolic"),  # subfamily was Sinitic via claims
}

# Colonial linguae francae shouldn't drive classification when better
# signals exist (Pakistan lists English first; Congo lists French).
COLONIAL_LANGS = {"English", "French", "Spanish", "Portuguese", "Dutch"}

RELIGION_SPHERE = {
    "Islam": "islam", "Sunni Islam": "islam", "Shia Islam": "islam",
    "Twelver Shiism": "islam", "Ahmadiyya": "islam", "Alevism": "islam",
    "Bektashi Order": "islam", "Ibadi Islam": "islam",
    "Catholic Church": "westeurope", "Catholicism": "westeurope",
    "Latin Church": "westeurope", "Protestantism": "westeurope",
    "Lutheranism": "westeurope", "Reformed Christianity": "westeurope",
    "Church of England": "westeurope", "Arianism": "westeurope",
    "Frankish paganism": "westeurope", "Eastern Catholic Churches": "westeurope",
    "Eastern Orthodoxy": "orthodox", "Greek Orthodoxy": "orthodox",
    "Armenian Apostolic Church": "orthodox", "Syriac Orthodox Church": "orthodox",
    "Nestorianism": "orthodox",
    "Hinduism": "dharmic", "Jainism": "dharmic", "Shaivism": "dharmic",
    "Sikhism": "dharmic",
    "Taoism": "sinic", "Confucianism": "sinic", "Chinese folk religion": "sinic",
    "Heaven worship": "sinic", "Caodaism": "sinic", "Hòa Hảo": "sinic",
    "Korean shamanism": "sinic",
    "Shinto": "japan", "State Shinto": "japan", "shinbutsu-shūgō": "japan",
    "Tengrism": "steppe", "shamanism": "steppe",
    "Zoroastrianism": "ancientne", "Babylonian religion": "ancientne",
    "religion of ancient Egypt": "ancientne", "Hittite religion": "ancientne",
    "Hittite mythology": "ancientne", "Judaism": "ancientne",
    "Aztec religion": "americas", "religion in the Inca Empire": "americas",
    # ambiguous -> resolved by language: "Christianity", "Buddhism", "secular state"
}

LANG_FAMILY = {
    "Romance": ["Latin", "medieval Latin", "Old Latin", "French", "Old French",
                "Italian", "Spanish", "Portuguese", "Galician",
                "Andalusi Romance", "Romanian", "Catalan", "Occitan"],
    "Germanic": ["English", "Old English", "Middle English", "German",
                 "Low German", "Old High German", "Dutch", "Swedish", "Danish",
                 "Norwegian", "Gothic", "Old Norse", "Afrikaans"],
    # Catholic West Slavs pattern with Latin Christendom, not Orthodoxy
    "SlavicWest": ["Polish", "Czech", "Slovak", "Slovene", "Croatian"],
    "SlavicEast": ["Russian", "Ukrainian", "Belarusian", "Serbian",
                   "Bulgarian", "Old Church Slavonic", "Church Slavonic",
                   "Macedonian"],
    "Greek": ["Greek", "Ancient Greek", "Koine Greek", "medieval Greek",
              "Modern Greek"],
    "Iranian": ["Persian", "Old Persian", "Middle Persian", "Pashto",
                "Bactrian", "Sogdian", "Kurdish", "Tajik", "Avestan", "Dari"],
    "Turkic": ["Ottoman Turkish", "Turkish", "Chagatai", "Azerbaijani",
               "Uzbek", "Tatar", "Kazakh", "Uyghur", "Old Turkic",
               "Kipchak languages", "Turkmen"],
    "Semitic": ["Arabic", "Classical Arabic", "Babylonian", "Akkadian",
                "Aramaic", "Imperial Aramaic", "Hebrew", "Syriac",
                "Phoenician", "Amharic", "Ge'ez"],
    "IndoAryan": ["Sanskrit", "Urdu", "Hindi", "Hindustani", "Marathi",
                  "Bengali", "Punjabi", "Prakrit", "Pali", "Nepali",
                  "Sinhala", "Gujarati", "Odia", "Assamese", "Maithili"],
    "Dravidian": ["Kannada", "Telugu", "Tamil", "Malayalam"],
    "Sinitic": ["Chinese", "Old Chinese", "Classical Chinese", "Mandarin",
                "Cantonese"],
    "Japonic": ["Japanese", "Old Japanese"],
    "Koreanic": ["Korean", "Middle Korean"],
    "Vietic": ["Vietnamese"],
    "KhmerMon": ["Khmer", "Old Khmer", "Mon"],
    "Tai": ["Thai", "Lao"],
    "Burmese": ["Burmese"],
    "Austronesian": ["Malay", "Indonesian", "Javanese", "Old Javanese",
                     "Tagalog", "Malagasy"],
    "Mongolic": ["Mongolian", "Middle Mongol"],
    "Tungusic": ["Manchu", "Jurchen"],
    "TibetoBurman": ["Tibetan", "Classical Tibetan"],
    "Egyptian": ["Egyptian", "Coptic", "Demotic"],
    "AncientNE": ["Elamite", "Sumerian", "Hittite", "Luwian",
                  "Classical Armenian", "Armenian"],
}
LANG_TO_FAMILY = {l: fam for fam, ls in LANG_FAMILY.items() for l in ls}

# language family -> sphere; callables get the polity's first attested year
LANGFAM_SPHERE = {
    "Romance": "westeurope", "Germanic": "westeurope",
    "SlavicWest": "westeurope", "SlavicEast": "orthodox",
    "Greek": lambda y: "westeurope" if y < 330 else "orthodox",
    "Iranian": lambda y: "islam" if y >= ISLAM_ERA else "ancientne",
    "Turkic": lambda y: "islam" if y >= 950 else "steppe",
    "Semitic": lambda y: "islam" if y >= ISLAM_ERA else "ancientne",
    "IndoAryan": "dharmic", "Dravidian": "dharmic", "KhmerMon": "dharmic",
    "Tai": "dharmic", "Burmese": "dharmic",
    "Austronesian": lambda y: "islam" if y >= 1400 else "dharmic",
    "Sinitic": "sinic", "Koreanic": "sinic", "Vietic": "sinic",
    "Japonic": "japan",
    "Mongolic": "steppe", "Tungusic": "sinic", "TibetoBurman": "dharmic",
    "Egyptian": "ancientne", "AncientNE": "ancientne",
}


def _sphere_from_langfam(fam, year):
    rule = LANGFAM_SPHERE.get(fam)
    return rule(year) if callable(rule) else rule


def geo_fallback(lon, lat, year):
    if lon < -30:
        return "americas" if year <= 1500 else "westeurope", "geo"
    if lat >= 44 and 22 <= lon <= 58:
        return "orthodox", "geo"
    if lat >= 36 and lon <= 58:
        return "westeurope", "geo"
    if lat <= 18 and -20 <= lon <= 42:
        return "africa", "geo"
    if lon <= 62 and lat >= 12:
        return ("islam" if year >= ISLAM_ERA else "ancientne"), "geo"
    if lon <= 62:
        return "africa", "geo"
    if lon <= 92 and lat <= 40:
        return "dharmic", "geo"
    if lon <= 92:
        return "steppe", "geo"
    if 128 <= lon <= 146 and 28 <= lat <= 46:
        return "japan", "geo"
    if lat >= 22:
        return "sinic", "geo"
    return ("islam" if year >= 1500 else "dharmic"), "geo"  # maritime SE Asia


class Classifier:
    def __init__(self):
        self.fp = json.loads(FINGERPRINT_JSON.read_text(encoding="utf-8"))

    def classify(self, name, lon, lat, first_year, last_year=None):
        sphere, sub = self._classify(name, lon, lat, first_year)
        # Pre-Christian Europe is NOT Latin Christendom: any Western-sphere
        # polity that ended by ~400 CE (before a Christianized Europe exists)
        # belongs to the Classical Mediterranean — Greek City-States, Macedon,
        # the Roman Republic/Empire. Successor states (Western Rome,
        # Byzantium) inherit via lineage gradients instead.
        if sphere == "westeurope" and last_year is not None and last_year <= 400:
            return "classical", sub
        return sphere, sub

    def _classify(self, name, lon, lat, first_year):
        if name in OVERRIDES:
            return OVERRIDES[name]
        rec = self.fp.get(name, {})
        # Only official languages (P37) carry classification weight; P2936
        # "language used" is an exhaustive inventory (the USA item lists 200+
        # indigenous languages incl. Tagalog, which once made the USA
        # Austronesian-Islamic here). If P37 is empty, take just the first
        # few P2936 entries, which are ordered roughly by prominence.
        langs = rec.get("official_language", []) or rec.get("language_used", [])[:3]
        # Prefer non-colonial languages for the fingerprint (Pakistan lists
        # English before Urdu; that shouldn't make it Germanic).
        native = [l for l in langs if l not in COLONIAL_LANGS]
        langfam = next(
            (LANG_TO_FAMILY[l] for l in native + langs if l in LANG_TO_FAMILY), None
        )
        had_religion = False
        for rel in rec.get("religion", []):
            sphere = RELIGION_SPHERE.get(rel)
            if sphere:
                return sphere, (langfam or "unknown")
            if rel == "Buddhism":
                had_religion = True
                if langfam in ("Sinitic", "Koreanic", "Vietic", "Tungusic"):
                    return "sinic", langfam
                if langfam == "Japonic":
                    return "japan", langfam
                if langfam in ("IndoAryan", "Dravidian", "KhmerMon", "Tai",
                               "Burmese", "TibetoBurman"):
                    return "dharmic", langfam
                break  # Buddhist but language unknown: geography decides
            # "Christianity" / "secular state" fall through to language
        # New-World guard (after religion, which catches Aztec/Inca religions
        # and Catholic colonial empires): no language signal may relocate a
        # Western-Hemisphere polity to an Old-World sphere. <= 1500 because
        # pre-Columbian polities founded 1428/1438 first appear at the 1500
        # slice.
        if lon < -30:
            return ("americas" if first_year <= 1500 else "westeurope",
                    langfam or "geo")
        geo = geo_fallback(lon, lat, first_year)
        if had_religion:
            return geo
        # Muslim-ruled Indian polities without wikidata signals
        if "Sultanate" in name and geo[0] == "dharmic":
            return "islam", (langfam or "unknown")
        if langfam:
            # Colonial linguae francae alone shouldn't pull modern Africa or
            # colonial Asia into the West; trust geography there.
            colonial_only = not any(l in LANG_TO_FAMILY for l in native)
            if colonial_only and geo[0] in ("africa", "sinic", "seasia"):
                return geo[0], "colonial"
            sphere = _sphere_from_langfam(langfam, first_year)
            if sphere:
                return sphere, langfam
        return geo


if __name__ == "__main__":
    import pandas as pd

    df = pd.read_csv(ROOT / "data" / "processed" / "population_shares.csv")
    agg = df.groupby("name").agg(
        share=("share", "max"), lon=("lon", "mean"), lat=("lat", "mean"),
        first=("year", "min"), last=("year", "max"),
    )
    clf = Classifier()
    out = {}
    for name, r in agg[agg.share >= 0.01].iterrows():
        if name == "Stateless & unmapped":
            continue
        out[name] = clf.classify(name, r.lon, r.lat, int(r.first), int(r.last))
    by_sphere = {}
    for name, (sphere, sub) in sorted(out.items()):
        by_sphere.setdefault(sphere, []).append(f"{name} [{sub}]")
    for sphere, names in sorted(by_sphere.items()):
        print(f"\n=== {sphere} ({len(names)}) ===")
        for n in names:
            print("  " + n)
