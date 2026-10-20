# Last orders? The UK drawn with its pubs

**[Read the story](https://etymo.co.uk/uk-pubs/)**

Can you draw the UK with nothing but pubs? A data story about 38,000 pubs and bars, the pubs we lost before COVID, the most common pub names, the streets that are basically a pub crawl, the furthest you can get from a pint, and how pubby your postcode is.

## Data

| Data | Source | Used for |
|---|---|---|
| Food hygiene rating register, all 363 councils (October 2026) | [Food Standards Agency](https://ratings.food.gov.uk/open-data) | Every pub, bar and club today |
| Public houses and bars by local authority, 2001–2019 | [ONS](https://www.ons.gov.uk/businessindustryandtrade/business/activitysizeandlocation/datasets/publichousesandbarsbysizelocalauthoritiesoftheuk2001to2019) | Change by council before COVID |
| Public houses and bars, London boroughs, 2001–2024 | [ONS](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/adhocs/2926onslocalpublichousesandbarslondonboroughs2001to2024) | UK totals to 2024, small vs large pubs |
| Mid-2025 population estimates | [ONS](https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/datasets/populationestimatesforukenglandandwalesscotlandandnorthernireland) | People per pub |
| Council boundaries | [ONSvisual/topojson_boundaries](https://github.com/ONSvisual/topojson_boundaries) | Maps |

All under the Open Government Licence v3.0. Basemap © OpenStreetMap contributors © CARTO.

## Pipeline

| Script | What it does |
|---|---|
| `01_fsa_pubs.py` | Reads every FSA council file. Keeps premises registered as Pub/bar/nightclub, plus restaurants, hotels and other caterers whose names clearly say pub (Inn, Arms, Tavern, Bar…) |
| `02_clean.py` | Builds a postcode lookup from all ~600,000 FSA premises; places pubs that have a postcode but no coordinates; sorts records into pub, bar, club and other; joins each to a council |
| `03_analysis.py` | Pub names, pubbiest streets, furthest point from a pub (1 km grid refined to 100 m, British National Grid) |
| `04_councils.py` | Council table on 2025 boundaries: ONS 2001–2019, population, FSA counts today; UK series to 2024 |
| `05_build_site.py` | Writes `docs/data/*.js` and copies `page_template.html` to `docs/index.html` |

```
python -m pip install -r requirements.txt
# FSA files go in data/raw/fsa/ (FHRS###en-GB.xml), ONS files in data/raw/ons/, boundaries in data/raw/bounds/
python scripts/01_fsa_pubs.py
python scripts/02_clean.py
python scripts/03_analysis.py
python scripts/04_councils.py
python scripts/05_build_site.py
```

## Limits

- **Two different counts.** ONS counts pub and bar workplaces with at least one employee, rounded to 5. The FSA register counts premises registered for food hygiene. Nationally they match closely, council by council they don't, so the story never subtracts one from the other.
- **Council-level change stops in 2019.** ONS only publishes council figures to 2024 for London.
- **Councils register pubs differently.** The Highland Council files most of its pubs as hotels. Scotland is left out of the "furthest from a pub" chapter for that reason; Northern Ireland is left out because its furthest point sits on the border with Donegal, outside this data.
- **About 7% of pubs have no location** in the register and no postcode match, so they are not on the map. This can make a remote spot look further from a pub than it is.
- **Pub, bar or club** is decided from the name with simple word rules. Expect some Bowling Club Bars in the wrong pile.
- **Postcode search** uses the middle of the postcode sector, worked out from the FSA register itself.

---

Made by [Eriola Trungu Impersimi](https://etymo.co.uk) · @ET
