"""Fun facts and council figures from the cleaned pub list."""
import os, re, json
import numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.prepared import prep

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, PROC = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data", "processed")
c = pd.read_csv(os.path.join(PROC, "pubs_clean.csv"), dtype={"postcode": str})
pb = c[c.kind.isin(["pub", "bar"])].copy()          # "a pub" = pubs and bars
pub = c[c.kind == "pub"].copy()
facts = {"n_all": len(c), "n_pubbar": len(pb), "kinds": c.kind.value_counts().to_dict()}

# ---------- pub names ----------
def base(n):
    n = str(n).lower().replace("&", " and ").replace("’", "'")
    n = re.sub(r"[^a-z' ]", " ", n)
    n = re.sub(r"'s\b", "s", n).replace("'", "")
    n = re.sub(r"^\s*(ye olde|ye old|the|ye)\s+", "", n.strip())
    n = re.sub(r"\s+(inn|hotel|pub|public house|tavern|bar|freehouse|free house|arms hotel)\s*$", "", n)
    n = re.sub(r"\b(ltd|limited|plc|llp)\b", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    if n in ("new", "old", "station", "half way", "halfway"): n += " inn"
    n = re.sub(r"\bkings\b", "kings", n)
    return n
pub["base"] = pub.name.map(base)
names = pub.base.value_counts()
names = names[names.index.str.len() > 2]
facts["top_names"] = [[k.title(), int(v)] for k, v in names.head(25).items()]
facts["n_unique_names"] = int(pub.base.nunique())
words = pub.base.str.split().explode()
STOP = {"and", "of", "the", "inn", "at", "on", "in", "a", "house", "bar", "hotel", "s"}
w = words[~words.isin(STOP)].value_counts()
facts["top_words"] = [[k, int(v)] for k, v in w.head(30).items()]

# animals / royals / trades
GROUPS = {
    "Royals": r"\b(king|kings|queen|queens|prince|princess|crown|royal|duke|duchess|victoria|albert|george|regent)\b",
    "Animals": r"\b(lion|horse|hart|swan|bull|bulls|bear|fox|hound|greyhound|eagle|cock|dog|lamb|ram|stag|boar|falcon|pheasant|dolphin|unicorn|dragon|goat|pig|hare|feathers|owl|raven|magpie|pelican)\b",
    "Trees and plants": r"\b(oak|wheatsheaf|plough|barley|hop|hops|vine|rose|ivy|holly|yew|elm|thistle|acorn|tree)\b",
    "Transport": r"\b(railway|station|coach|horses|anchor|ship|boat|canal|bridge|wagon|engine|train|lock|ferry)\b",
}
facts["groups"] = {g: int(pub.base.str.contains(r, regex=True).sum()) for g, r in GROUPS.items()}

# red lion vs royal oak vs white hart by country / region
la = gpd.read_file(os.path.join(RAW, "bounds", "ltla2022.geojson"))
rg = gpd.read_file(os.path.join(RAW, "bounds", "ltla2022.geojson"))  # placeholder for area calcs

# ---------- per council ----------
la27 = la.to_crs(27700)
la27["km2"] = la27.area / 1e6
cnt = pb.groupby("AREACD").size().rename("pubs")
clubs = c[c.kind == "club"].groupby("AREACD").size().rename("clubs")
co = la27[["AREACD", "AREANM", "km2"]].set_index("AREACD").join(cnt).join(clubs).fillna(0)
co["per_km2"] = co.pubs / co.km2
co["clubs_share"] = co.clubs / (co.clubs + co.pubs)
top_name = pub.groupby("AREACD").base.agg(lambda s: s.value_counts().index[0].title())
co = co.join(top_name.rename("top_name"))
r5 = pb.assign(r5=pb.rating.astype(str).isin(["5", "Pass"])).groupby("AREACD").r5.mean()
co = co.join(r5.rename("share_5"))
# council table: see 04_councils.py

# ---------- loneliest pub & pubbiest street ----------
xy = pb[["x", "y"]].to_numpy()
tree = cKDTree(xy)
dd, ii = tree.query(xy, k=2)
pb["nn_m"] = dd[:, 1]
lon = pb.sort_values("nn_m", ascending=False)
facts["loneliest_ew"] = lon[lon.AREACD.str[0].isin(["E", "W"])].head(10)[["name", "a1", "a2", "a3", "postcode", "AREANM", "nn_m", "lat", "lon"]].round(5).to_dict("records")
facts["loneliest"] = lon.head(10)[["name", "a1", "a2", "a3", "postcode", "AREANM", "nn_m", "lat", "lon"]].round(5).to_dict("records")
facts["median_nn_m"] = float(np.median(pb.nn_m))

def street(r):
    for a in [r.a1, r.a2]:
        a = str(a)
        if re.search(r"\b(street|st|road|rd|lane|ln|high street|square|row|place|way|gate|walk|hill|market)\b", a, re.I):
            s = re.sub(r"^[\d\-/a-z]*\d[\d\-/a-z]*\s*,?\s*", "", a.strip(), flags=re.I)
            s = re.sub(r"\bst\b\.?$", "street", s, flags=re.I)
            s = re.sub(r"\brd\b\.?$", "road", s, flags=re.I)
            return s.title().strip(", ")
    return None
pb["street"] = pb.apply(street, axis=1)
pb["district"] = pb.postcode.fillna("").str.split().str[0]
st = pb.dropna(subset=["street"]).groupby(["street", "AREANM"]).agg(n=("name", "size"), lat=("lat", "median"), lon=("lon", "median"),
    x0=("x", "min"), x1=("x", "max"), y0=("y", "min"), y1=("y", "max"), names=("name", lambda s: list(s)[:40]))
st["spread"] = np.hypot(st.x1 - st.x0, st.y1 - st.y0).round()
st = st[st.spread < 1500].drop(columns=["x0", "x1", "y0", "y1"]).sort_values("n", ascending=False)  # same physical street, not two High Streets
facts["pubbiest_streets"] = st.head(15).reset_index().round(5).to_dict("records")

# ---------- furthest point from a pub ----------
uk = gpd.read_file(os.path.join(RAW, "bounds", "ctry.geojson")).to_crs(27700)
res = {}
gb = uk[uk.AREACD.str[0].isin(list("ESW"))].union_all()
mainland = max(gb.geoms, key=lambda g: g.area)
def big(g): return max(g.geoms, key=lambda x: x.area) if g.geom_type == "MultiPolygon" else g
eng = uk[uk.AREACD.str[0] == "E"].union_all(); wal = uk[uk.AREACD.str[0] == "W"].union_all()
sco = uk[uk.AREACD.str[0] == "S"].union_all()
AREAS = [("England", big(eng)), ("Wales", big(wal)), ("Scotland (mainland)", sco.intersection(mainland)),
         ("Great Britain (mainland)", mainland), ("Northern Ireland", uk[uk.AREACD.str[0] == "N"].union_all())]
for nm, geo in AREAS:
    minx, miny, maxx, maxy = geo.bounds
    step = 1000
    gx, gy = np.meshgrid(np.arange(minx, maxx, step), np.arange(miny, maxy, step))
    pts = np.c_[gx.ravel(), gy.ravel()]
    import shapely
    inside = shapely.contains_xy(geo, pts[:, 0], pts[:, 1])
    pts = pts[inside]
    d1, i1 = tree.query(pts)
    k = np.argsort(-d1)[:2000]
    # refine around the best candidates at 100 m
    best = (0, None)
    for j in k[:50]:
        cx, cy = pts[j]
        fx, fy = np.meshgrid(np.arange(cx - 1000, cx + 1000, 100), np.arange(cy - 1000, cy + 1000, 100))
        fp = np.c_[fx.ravel(), fy.ravel()]
        fp = fp[shapely.contains_xy(geo, fp[:, 0], fp[:, 1])]
        if len(fp) == 0: continue
        fd, fi = tree.query(fp)
        m = fd.argmax()
        if fd[m] > best[0]: best = (fd[m], fp[m], fi[m])
    p = gpd.GeoSeries([Point(best[1])], crs=27700).to_crs(4326)[0]
    near = pb.iloc[best[2]]
    res[nm] = dict(km=round(best[0] / 1000, 1), lat=round(p.y, 5), lon=round(p.x, 5),
                   nearest=near["name"], nearest_place=" ".join(str(v) for v in [near.a1, near.a2, near.a3] if isinstance(v, str)), nearest_la=near.AREANM,
                   nearest_lat=near.lat, nearest_lon=near.lon)
    # share of land more than 5 km / 10 km from a pub
    res[nm]["share_over_5km"] = float((d1 > 5000).mean()); res[nm]["share_over_10km"] = float((d1 > 10000).mean())
facts["furthest"] = res

# England only: furthest
json.dump(facts, open(os.path.join(PROC, "facts.json"), "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in facts.items() if k not in ("loneliest",)}, indent=1, default=str)[:6000])
print(pd.DataFrame(facts["loneliest"])[["name", "AREANM", "nn_m", "lat", "lon"]])
print(pd.DataFrame(facts["loneliest_ew"])[["name", "a2", "AREANM", "nn_m", "lat", "lon"]])
