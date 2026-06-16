"""Fetch religion + language claims from Wikidata for every prominent stream
polity, to support civilizational color grouping by religion-language
fingerprint instead of centroid geography.

Reads polity QIDs from population_shares.csv (Cliopatria's Wikidata column),
queries wbgetentities in batches for P140 (religion or worldview), P37
(official language), P2936 (language used), resolves value QIDs to English
labels, and caches everything to data/raw/wikidata_fingerprint.json.
"""
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / "data" / "processed" / "population_shares.csv"
OUT_JSON = ROOT / "data" / "raw" / "wikidata_fingerprint.json"

API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "Demograph/0.1 (https://github.com/alexandrosm/Demograph)"}
PROPS = {"P140": "religion", "P37": "official_language", "P2936": "language_used"}
PROMINENCE = 0.01


def batched(seq, n=50):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def get_entities(qids, props="claims"):
    out = {}
    for chunk in batched(qids):
        r = requests.get(
            API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": props,
                "languages": "en",
                "format": "json",
            },
            headers=HEADERS,
            timeout=60,
        )
        r.raise_for_status()
        out.update(r.json().get("entities", {}))
        time.sleep(0.3)
    return out


def claim_qids(entity, prop):
    vals = []
    for claim in entity.get("claims", {}).get(prop, []):
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        vals.append(snak["datavalue"]["value"]["id"])
    return vals


def main() -> None:
    df = pd.read_csv(IN_CSV)
    peak = df.groupby("name").agg(
        share=("share", "max"), qid=("wikidata", "first")
    )
    keep = peak[(peak.share >= PROMINENCE) & peak.qid.notna()]
    keep = keep[keep.qid.str.startswith("Q", na=False)]
    print(f"{len(keep)} prominent polities with QIDs")

    entities = get_entities(keep.qid.unique().tolist())
    rows = {}
    value_qids = set()
    for name, rec in keep.iterrows():
        ent = entities.get(rec.qid, {})
        claims = {key: claim_qids(ent, p) for p, key in PROPS.items()}
        rows[name] = {"qid": rec.qid, **claims}
        for v in claims.values():
            value_qids.update(v)

    print(f"resolving {len(value_qids)} value labels...")
    labels = {
        q: e.get("labels", {}).get("en", {}).get("value", q)
        for q, e in get_entities(sorted(value_qids), props="labels").items()
    }
    for rec in rows.values():
        for key in PROPS.values():
            rec[key] = [labels.get(q, q) for q in rec[key]]

    OUT_JSON.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    n_rel = sum(1 for r in rows.values() if r["religion"])
    n_lang = sum(1 for r in rows.values() if r["official_language"] or r["language_used"])
    print(f"coverage: religion {n_rel}/{len(rows)}, language {n_lang}/{len(rows)}")
    rels = {}
    for r in rows.values():
        for x in r["religion"]:
            rels[x] = rels.get(x, 0) + 1
    print("distinct religions:", len(rels))
    for k, v in sorted(rels.items(), key=lambda kv: -kv[1]):
        print(f"  {v:3d}  {k}")


if __name__ == "__main__":
    main()
