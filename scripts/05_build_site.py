"""Write the web data files into docs/data/ and copy the page template."""
import os, json, shutil
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC, DOCS = os.path.join(ROOT, "data", "processed"), os.path.join(ROOT, "docs")
os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)
w = lambda name, obj: open(os.path.join(DOCS, "data", name + ".js"), "w", encoding="utf-8").write(
    f"window.PUBS=window.PUBS||{{}};window.PUBS.{name}=" + json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + ";\n")

c = pd.read_csv(os.path.join(PROC, "pubs_clean.csv"), dtype={"postcode": str, "rating": str})
c = c[c.kind.isin(["pub", "bar", "club", "nightclub"])].copy()
c.loc[c.kind == "nightclub", "kind"] = "bar"
K = {"pub": 0, "bar": 1, "club": 2}
c = c.sort_values(["kind", "lat"])
place = c.a3.where(c.a3.notna() & (c.a3.str.len() < 30), c.a2).fillna("")
place = place.where(~place.str.match(r"^\d"), "")
w("points", {
    "lat": (c.lat * 1e5).round().astype(int).tolist(), "lon": (c.lon * 1e5).round().astype(int).tolist(),
    "k": c.kind.map(K).tolist(), "n": c.name.str.strip().tolist(), "pc": c.postcode.fillna("").tolist(),
    "pl": place.str.title().tolist(),
})

# postcode sectors (e.g. "KT3 3") and districts from every FSA premises with a location
pcs = pd.read_csv(os.path.join(PROC, "postcodes_fsa.csv"))
pcs["sector"] = pcs.pc.str[:-2]
pcs["district"] = pcs.pc.str.split().str[0]
sec = pcs.groupby("sector")[["lat", "lon"]].median().round(5)
dis = pcs.groupby("district")[["lat", "lon"]].median().round(5)
w("postcodes", {"s": {k: [v.lat, v.lon] for k, v in sec.iterrows()}, "d": {k: [v.lat, v.lon] for k, v in dis.iterrows()}})

# how pubby is the UK: pubs and bars within 800 m (about a 10-minute walk) of every postcode
tr = Transformer.from_crs(4326, 27700, always_xy=True)
pb = c[c.kind.isin(["pub", "bar"])]
tree = cKDTree(pb[["x", "y"]].to_numpy())
px, py = tr.transform(pcs.lon.to_numpy(), pcs.lat.to_numpy())
P = np.c_[px, py]
cnt = np.array([len(i) for i in tree.query_ball_point(P, 800)])
dist, _ = tree.query(P)
q = np.linspace(0, 100, 101)
w("pubbiness", {"count800": np.percentile(cnt, q).round(1).tolist(), "nearest": np.percentile(dist, q).round(0).tolist(),
                "share_zero": float((cnt == 0).mean()), "median_count": float(np.median(cnt)), "median_nearest": float(np.median(dist))})
print("postcodes", len(P), "median pubs within 800 m", np.median(cnt), "median nearest", np.median(dist).round(), "share none", (cnt == 0).mean().round(3))

# councils
co = pd.read_csv(os.path.join(PROC, "councils.csv"))
g = json.load(open(os.path.join(PROC, "councils_2025.geojson")))
keep = ["name", "pop2025", "fsa_pubs", "fsa_clubs", "ons2001", "ons2008", "ons2019", "chg_01_19", "fsa_per10k", "people_per_pub", "fsa_per_km2"]
co = co.set_index("code")
series = {code: [None if pd.isna(co.loc[code, f"ons{y}"]) else int(co.loc[code, f"ons{y}"]) for y in range(2001, 2020)] for code in co.index}
for f in g["features"]:
    code = f["properties"]["code"]; r = co.loc[code]
    f["properties"] = {"code": code, **{k: (None if pd.isna(r[k]) else (round(float(r[k]), 4) if isinstance(r[k], (float, np.floating)) else r[k])) for k in keep}, "s": series[code]}
w("councils", g)

facts = json.load(open(os.path.join(PROC, "facts.json")))
facts["national"] = json.load(open(os.path.join(PROC, "national.json")))
for k in ["loneliest", "kinds"]: facts.pop(k, None)
w("facts", facts)

shutil.copy(os.path.join(ROOT, "scripts", "page_template.html"), os.path.join(DOCS, "index.html"))
for f in sorted(os.listdir(os.path.join(DOCS, "data"))):
    print(f, round(os.path.getsize(os.path.join(DOCS, "data", f)) / 1e6, 2), "MB")
