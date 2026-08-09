"""Run the agent on four California parcels.

    python3 -m agent.demo

Paradise burned in the 2018 Camp Fire. Malibu burned in Woolsey the same year.
Sacramento and Fresno are flat inland cities. All four are real coordinates and
every number below is fetched live.
"""
from . import agent

SITES = [
    agent.Site("Paradise, CA (Camp Fire 2018)", 39.7486, -121.5798),
    agent.Site("Malibu, CA (Woolsey Fire 2018)", 34.0259, -118.7798),
    agent.Site("Sacramento, CA (downtown)", 38.5816, -121.4944),
    agent.Site("Fresno, CA (downtown)", 36.7378, -119.7871),
]

def val(f, n):
    v = f.get(n)
    v = v.get("value") if isinstance(v, dict) else v
    # Mireye returns full float precision, so ndvi_current arrives as
    # 0.06319910287857056. Printing that implies a certainty the underlying
    # raster does not have, and it is unreadable next to the rounded figures in
    # the flag lines below.
    return round(v, 3) if isinstance(v, float) else v

def main():
    r = agent.run(SITES)
    print(f"use case: {r.use_case}")
    print(f"planned {len(r.planned_fields)} fields from the catalog preset: {', '.join(r.planned_fields)}")
    print(f"decisive fields NOT in the catalog: {', '.join(r.missing_decisive)}")
    for f, g in r.ghost_hints.items():
        print(f"hint on {f} names a field that does not exist: {', '.join(g)}")
    print()
    for res in r.results:
        f = res.fields
        print(f"--- {res.site.name}")
        print(f"    canopy {val(f,'tree_canopy_pct')}%   ndvi {val(f,'ndvi_current')}   "
              f"cover {val(f,'lcms_class')}   slope {val(f,'slope_degrees')}")
        print(f"    {res.verdict.line()}")
        for w in res.flags:
            print(f"    flag: {w}")
        for c in res.would_change:
            print(f"    would change the answer: {c}")
        print()
    fr = r.field_request
    if fr:
        print(f"field request: {fr['status']}"
              + (f" (HTTP {fr.get('http_status')})" if fr['status'] != 'filed' else ""))

if __name__ == "__main__":
    main()
