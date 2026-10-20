"""Clean the FSA pub list.

- Builds a postcode -> location lookup from every geocoded premises in the FSA files
  (used to place pubs that have a postcode but no coordinates, and later for the
  "how pubby is your postcode" search).
- Classifies each record: pub, bar, club (members' / sports / legion clubs), nightclub.
- Joins each pub to a council (2022 lower-tier boundaries).
"""
import os, re, glob, json
import xml.etree.ElementTree as ET
import numpy as np, pandas as pd, geopandas as gpd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, PROC = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data", "processed")

def norm_pc(p):
    p = re.sub(r"\s+", "", str(p or "").upper())
    return p[:-3] + " " + p[-3:] if 5 <= len(p) <= 7 else ""

# 1. postcode lookup from every FSA premises with a location
lk = os.path.join(PROC, "postcodes_fsa.csv")
if not os.path.exists(lk):
    recs = []
    for f in sorted(glob.glob(os.path.join(RAW, "fsa", "*.xml"))):
        for e in ET.parse(f).getroot().iter("EstablishmentDetail"):
            lat, lon = e.findtext("Geocode/Latitude"), e.findtext("Geocode/Longitude")
            pc = norm_pc(e.findtext("PostCode"))
            if lat and lon and pc:
                recs.append((pc, float(lat), float(lon)))
    p = pd.DataFrame(recs, columns=["pc", "lat", "lon"])
    p = p[(p.lat > 49.8) & (p.lat < 61) & (p.lon > -8.7) & (p.lon < 2)]
    p.groupby("pc", as_index=False)[["lat", "lon"]].median().to_csv(lk, index=False)
pcs = pd.read_csv(lk)
print(len(pcs), "postcodes with a location")

# 2. pubs
d = pd.read_csv(os.path.join(PROC, "fsa_pubs.csv"), dtype=str)
d["postcode"] = d.postcode.map(norm_pc)
d["lat"], d["lon"] = pd.to_numeric(d.lat), pd.to_numeric(d.lon)
d["geo"] = np.where(d.lat.notna(), "fsa", "")
miss = d.lat.isna()
m = d[miss].merge(pcs, left_on="postcode", right_on="pc", how="left", suffixes=("", "_pc"))
d.loc[miss, "lat"], d.loc[miss, "lon"] = m.lat_pc.values, m.lon_pc.values
d.loc[miss & d.lat.notna(), "geo"] = "postcode"
print("placed by postcode:", (d.geo == "postcode").sum(), " still unplaced:", d.lat.isna().sum())

n = d.name.fillna("").str.lower()
CLUB = r"\b(club|legion|british legion|institute|ex[- ]servicemen|working ?men|w\.?m\.?c|association|society|r\.?a\.?f\.?a|bowling|cricket|golf|rugby|football|tennis|sailing|yacht|masonic|conservative|labour|liberal|comrades|welfare|veterans|social|sports|athletic|ymca|scout|students|union bar|university|college)\b"
NIGHT = r"\b(nightclub|night club|niteclub)\b"
d["kind"] = "pub"
d.loc[n.str.contains(r"\bbar\b|\blounge\b|cocktail|wine bar|taproom|tap room|bottle shop|brewdog|craft", regex=True), "kind"] = "bar"
d.loc[n.str.contains(CLUB, regex=True), "kind"] = "club"
d.loc[n.str.contains(NIGHT, regex=True), "kind"] = "nightclub"
d.loc[n.str.contains(r"\b(inn|arms|tavern|head|hotel|public house|pub|alehouse|ale house)\b", regex=True) & (d.kind == "bar"), "kind"] = "pub"
d.loc[n.str.contains(r"\b(inn|arms|tavern|hotel)\b", regex=True) & ~n.str.contains(r"\b(club|legion|masonic|institute|welfare)\b", regex=True), "kind"] = "pub"
OTHER = r"\b(centre|center|hall|community|cafe|café|coffee|theatre|cinema|church|brigade|stadium|arena|bingo|casino|leisure|events|catering|kiosk|marquee|festival|lodge|village|pavilion|museum|gallery|school|hospital|caravan|holiday park|campsite|kitchen|restaurant|bistro|deli|shop|store|ltd)\b"
d.loc[n.str.contains(OTHER, regex=True) & ~n.str.contains(r"\b(inn|arms|tavern|pub|public house|bar|hotel)\b", regex=True) & (d.kind == "pub"), "kind"] = "other"
d.loc[(d.a1.fillna("") + " " + d.a2.fillna("")).str.contains("stadium", case=False), "kind"] = "other"
print(d.kind.value_counts())

# 3. council join
g = gpd.GeoDataFrame(d.dropna(subset=["lat"]), geometry=gpd.points_from_xy(d.dropna(subset=["lat"]).lon, d.dropna(subset=["lat"]).lat), crs=4326)
la = gpd.read_file(os.path.join(RAW, "bounds", "ltla2022.geojson"))[["AREACD", "AREANM", "geometry"]]
g = g.to_crs(27700); la = la.to_crs(27700)
j = gpd.sjoin(g, la, how="left", predicate="within").drop(columns="index_right")
out = j[j.AREACD.isna()].drop(columns=["AREACD", "AREANM"])
near = gpd.sjoin_nearest(out, la, how="left", max_distance=5000).drop(columns="index_right")
near = near[~near.index.duplicated()]
j.loc[near.index, ["AREACD", "AREANM"]] = near[["AREACD", "AREANM"]].values
print("no council (offshore or bad coords):", j.AREACD.isna().sum())
j = j.dropna(subset=["AREACD"])
j["x"], j["y"] = j.geometry.x.round(0), j.geometry.y.round(0)
pd.DataFrame(j.drop(columns="geometry")).to_csv(os.path.join(PROC, "pubs_clean.csv"), index=False)
print(len(j), "records written")
