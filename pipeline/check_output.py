"""Quick inspection helper: top shares at given years + Greek-era presence."""
import sys

import pandas as pd

df = pd.read_csv(r"data\processed\population_shares.csv")
years = [int(a) for a in sys.argv[1:]] or [-500, -300, 800]
for y in years:
    s = df[df.year == y].nlargest(9, "share")
    print(f"--- {y} ---")
    for r in s.itertuples():
        print(f"  {r.name[:44]:44s} {r.share:7.1%}  {r.population/1e6:7.1f}M")

greek = df[df.name.str.contains("Greek|Athen|Seleuc|Ptolem|Maced|Achaem")]
print("--- Greek/Hellenistic presence ---")
print(
    greek.groupby("name")
    .agg(yrs=("year", lambda s: f"{s.min()}..{s.max()}"), peak=("share", "max"))
    .to_string()
)
tri = df[
    (df.year == 800)
    & df.name.isin(["Pala Empire", "Rashtrakuta Dynasty", "Gurjara-Pratihara Dynasty"])
]
print(f"India tripartite sum at 800: {tri.population.sum()/1e6:.1f}M")
