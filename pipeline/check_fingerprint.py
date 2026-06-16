"""Inspect fetched Wikidata fingerprints: distinct languages + key polities."""
import json

rows = json.load(open(r"data\raw\wikidata_fingerprint.json", encoding="utf-8"))
langs = {}
for r in rows.values():
    for x in r["official_language"] + r["language_used"]:
        langs[x] = langs.get(x, 0) + 1
print("distinct languages:", len(langs))
for k, v in sorted(langs.items(), key=lambda kv: -kv[1])[:40]:
    print(f"  {v:3d}  {k}")
print()
KEY = [
    "Union of Soviet Socialist Republics", "British Empire", "Ottoman Empire",
    "Mughal Empire", "Byzantine Empire", "Roman Empire", "Khmer Empire",
    "Abbasid Caliphate", "Qing Dynasty", "United States of America",
    "Russian Empire", "Achaemenid Empire",
]
for n in KEY:
    r = rows.get(n)
    if r:
        lang = (r["official_language"] + r["language_used"])[:4]
        print(f'{n:40s} rel={r["religion"]} lang={lang}')
    else:
        print(f"{n:40s} -- not in set")
missing = [n for n, r in rows.items()
           if not r["religion"] and not r["official_language"] and not r["language_used"]]
print(f"\nno signal at all: {len(missing)}/{len(rows)}")
print(sorted(missing)[:30])
