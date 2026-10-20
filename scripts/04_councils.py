"""Council table on 2025 boundaries: ONS pubs 2001-2019, population, FSA pubs now.

ONS counts are pub and bar *workplaces with employees* (IDBR, SIC 56302, rounded to 5).
FSA counts are premises registered for food hygiene as a pub/bar. They measure different
things, so they are never subtracted from each other.
"""
import os, json
import numpy as np, pandas as pd, geopandas as gpd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, PROC = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data", "processed")

TO2025 = {}
for new, olds in {
    "E06000063": ["E07000026", "E07000028", "E07000029"],                      # Cumberland
    "E06000064": ["E07000027", "E07000030", "E07000031"],                      # Westmorland and Furness
    "E06000065": ["E07000163", "E07000164", "E07000165", "E07000166", "E07000167", "E07000168", "E07000169"],
    "E06000066": ["E07000187", "E07000188", "E07000189", "E07000190", "E07000191", "E07000246"],
    "E06000061": ["E07000150", "E07000152", "E07000153", "E07000156"],          # North Northamptonshire
    "E06000062": ["E07000151", "E07000154", "E07000155"],                      # West Northamptonshire
    "E07000245": ["E07000201", "E07000204"], "E07000244": ["E07000205", "E07000206"],
    "E06000060": ["E07000004", "E07000005", "E07000006", "E07000007"],
    "E06000058": ["E06000028", "E06000029", "E07000048"],
    "E06000059": ["E07000049", "E07000050", "E07000051", "E07000052", "E07000053"],
    "S12000049": ["S12000046"], "S12000050": ["S12000044"],
}.items():
    for o in olds: TO2025[o] = new
fix = lambda c: TO2025.get(c, c)

pop = pd.read_csv(os.path.join(PROC, "population.csv"))
lad = pop[pop.Geography.isin(["Non-metropolitan District", "Unitary Authority", "Metropolitan District",
                              "London Borough", "Council Area", "Local Government District"])]
lad = lad.rename(columns={"Code": "code", "Name": "name", "Mid-2019": "pop2019", "Mid-2025": "pop2025"})[["code", "name", "pop2019", "pop2025"]]

o = pd.read_excel(os.path.join(RAW, "ons", "pubs_la_2001_2019.xls"), "Pubs size LA", header=2)
o = o[o.iloc[:, 2] == "Any number of employees"]
o = o[o["Area code"].astype(str).str[:3].isin(["E06", "E07", "E08", "E09", "S12", "W06", "N09"])]
o["code"] = o["Area code"].map(fix)
yrs = list(range(2001, 2020))
ons = o.groupby("code")[yrs].sum()
ons.columns = [f"ons{y}" for y in yrs]

c = pd.read_csv(os.path.join(PROC, "pubs_clean.csv"), usecols=["kind", "AREACD"])
c["code"] = c.AREACD.map(fix)
fsa = c.pivot_table(index="code", columns="kind", aggfunc="size", fill_value=0)
fsa["fsa_pubs"] = fsa.get("pub", 0) + fsa.get("bar", 0)
fsa = fsa[["fsa_pubs", "club"]].rename(columns={"club": "fsa_clubs"})

t = lad.set_index("code").join(ons).join(fsa).fillna({"fsa_pubs": 0, "fsa_clubs": 0})
t["chg_01_19"] = (t.ons2019 / t.ons2001 - 1)
t["chg_08_19"] = (t.ons2019 / t.ons2008 - 1)
t["ons19_per10k"] = t.ons2019 / t.pop2019 * 1e4
t["fsa_per10k"] = t.fsa_pubs / t.pop2025 * 1e4
t["people_per_pub"] = t.pop2025 / t.fsa_pubs.replace(0, np.nan)

# boundaries dissolved to 2025
b = gpd.read_file(os.path.join(RAW, "bounds", "ltla2022.geojson"))
b["code"] = b.AREACD.map(fix)
b = b.dissolve("code").reset_index()[["code", "geometry"]]
b27 = b.to_crs(27700); b["km2"] = b27.area / 1e6
t = t.join(b.set_index("code")[["km2"]])
t["fsa_per_km2"] = t.fsa_pubs / t.km2
t.reset_index().to_csv(os.path.join(PROC, "councils.csv"), index=False)
missing = set(t.index) - set(b.code)
print("councils:", len(t), "no boundary:", missing, "no ONS:", t.ons2019.isna().sum())

b = b.merge(t.reset_index()[["code", "name"]], on="code")
b["geometry"] = b.geometry.simplify(0.002, preserve_topology=True)
b.to_file(os.path.join(PROC, "councils_2025.geojson"), driver="GeoJSON", COORDINATE_PRECISION=4)

# national series to 2024 (from the London ad hoc table, which also carries the UK and nations)
L = pd.read_excel(os.path.join(RAW, "ons", "london_2001_2024.xls"), "Pubs size", header=2)
L = L[L.iloc[:, 2] == "Any number of employees"].set_index("Area name")
ycols = [c for c in L.columns if str(c).replace(".0", "").isdigit()]
nat = {n: {int(float(y)): float(L.loc[n, y]) for y in ycols} for n in ["United Kingdom", "England", "London"] if n in L.index}
# Small pubs (<10 staff) vs big pubs (10+) for the UK
S = pd.read_excel(os.path.join(RAW, "ons", "london_2001_2024.xls"), "Pubs size", header=2)
S = S[S["Area name"] == "United Kingdom"].set_index(S.columns[2])
nat["UK small (<10 staff)"] = {int(float(y)): float(S.loc["Fewer than 10", y]) for y in ycols}
nat["UK large (10+ staff)"] = {int(float(y)): float(S.loc["10 or more", y]) for y in ycols}
json.dump(nat, open(os.path.join(PROC, "national.json"), "w"), indent=1)

pd.set_option("display.width", 200)
t2 = t.dropna(subset=["chg_01_19"])
print("UK pop 2025", lad.pop2025.sum(), " FSA pubs", t.fsa_pubs.sum(), " people per pub", round(lad.pop2025.sum() / t.fsa_pubs.sum()))
print(t2.sort_values("chg_01_19")[["name", "ons2001", "ons2019", "chg_01_19"]].head(8))
print(t2[t2.ons2001 >= 50].sort_values("chg_01_19")[["name", "ons2001", "ons2019", "chg_01_19"]].tail(8))
print(t.sort_values("fsa_per10k")[["name", "fsa_pubs", "pop2025", "fsa_per10k"]].head(6))
print(t.sort_values("fsa_per10k")[["name", "fsa_pubs", "pop2025", "fsa_per10k"]].tail(8))
print((t2.chg_01_19 < 0).mean(), (t2.ons2019 > t2.ons2001).sum())
