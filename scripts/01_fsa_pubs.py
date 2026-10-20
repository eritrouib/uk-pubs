"""Extract pubs/bars/nightclubs from the FSA food hygiene open data (one XML per council)."""
import sys, glob, os, csv
import re
import xml.etree.ElementTree as ET

# Some councils (Highland above all) register many pubs as restaurants or hotels.
# Premises in those groups whose name says pub are kept too.
OTHER_TYPES = {"1", "7841", "7842"}   # restaurant/cafe, other catering, hotel/B&B
PUBNAME = re.compile(r"\b(inn|tavern|arms|public house|pub|ale ?house|bar)\b", re.I)
NOTPUB = re.compile(r"\b(sandwich|snack|salad|juice|coffee|espresso|sushi|noodle|burger|kebab|pizza|tapas|oyster|milk|ice cream|gelato|cake|breakfast|grill bar|cafe|café|tea|deli|bakery|restaurant|kitchen|curry|tandoori|spice|express|travelodge|premier inn|holiday inn|days inn|best western|school|nursery|hospital|care|college|university|fish|chips|chippy|grill|oriental|chinese|indian|thai|veg|vegan|roll|rolls|bbq|steak|steakhouse|ristorante|trattoria|motel|dessert|ice|taco|tacos|wok|fried|chicken|bagel|crepe|waffle|smoothie|wine bar & kitchen)\b", re.I)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "fsa")
OUT = os.path.join(ROOT, "data", "processed", "fsa_pubs.csv")

rows, auth = [], {}
for f in sorted(glob.glob(os.path.join(RAW, "*.xml"))):
    try:
        r = ET.parse(f).getroot()
    except ET.ParseError as e:
        print("bad", f, e); continue
    for e in r.iter("EstablishmentDetail"):
        la = e.findtext("LocalAuthorityName")
        auth.setdefault(la, 0)
        bt, nm = e.findtext("BusinessTypeID"), e.findtext("BusinessName") or ""
        if bt == "7843":
            src = "pub type"
        elif bt in OTHER_TYPES and PUBNAME.search(nm) and not NOTPUB.search(nm):
            src = "pub name"
        else:
            continue
        auth[la] += 1
        lon, lat = e.findtext("Geocode/Longitude"), e.findtext("Geocode/Latitude")
        rows.append(dict(
            id=e.findtext("FHRSID"), name=(e.findtext("BusinessName") or "").strip(),
            a1=e.findtext("AddressLine1") or "", a2=e.findtext("AddressLine2") or "",
            a3=e.findtext("AddressLine3") or "", a4=e.findtext("AddressLine4") or "",
            postcode=e.findtext("PostCode") or "", rating=e.findtext("RatingValue") or "",
            la=la, la_code=e.findtext("LocalAuthorityCode"),
            lon=lon or "", lat=lat or "", src=src, btype=e.findtext("BusinessType")))

with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
geo = sum(1 for r in rows if r["lat"])
print(f"{len(rows)} pub/bar/nightclub records, {geo} with coordinates, {len(auth)} authorities")
