#!/usr/bin/env python3
"""Build the Global Power Atlas dataset and embed it into atlas.html.

Usage
  python3 scripts/build_atlas.py                      # validate data.json, embed into atlas.html
  python3 scripts/build_atlas.py --extract DIR        # merge DIR/vol*.json into data.json first, then validate and embed

The per-volume extraction files (DIR/vol1.json ... vol4.json) are the intermediate
output of the source-reading step. They are not committed; data.json is the
normalised artifact that is committed and embedded.

Standard library only. No network access.
"""
import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data.json")
HTML_PATH = os.path.join(ROOT, "atlas.html")
DATA_START = "/*DATA:START*/"
DATA_END = "/*DATA:END*/"

CATEGORIES = ["Trade", "Energy", "Resources", "Military", "Finance", "Geopolitics"]
TYPES = {
    "country", "region", "city", "port", "chokepoint", "trade-route", "pipeline",
    "energy-infrastructure", "resource", "military-site", "financial-center",
    "alliance", "institution", "event", "other",
}
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
TEXT_FIELDS = [
    "geography", "economicResourceSignificance", "strategicDynamics", "vulnerabilities",
]

# Known cross-volume duplicates the extraction agents may have written differently.
# Filled in after reviewing the merge report; keys are raw ids, values are canonical ids.
ALIASES = {}


def slug(value):
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def clean_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def load_extractions(directory):
    files = sorted(glob.glob(os.path.join(directory, "vol*.json")))
    if not files:
        sys.exit(f"No vol*.json files found in {directory}")
    entities = []
    volumes = []
    for path in files:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        volumes.append({"volume": payload.get("volume"), "book": payload.get("book")})
        for item in payload.get("entities", []):
            entities.append(item)
    return entities, volumes


def merge(raw_entities, log):
    merged = {}
    order = []

    for raw in raw_entities:
        raw_id = slug(raw.get("id", ""))
        if not raw_id:
            log.append("skipped entity without id")
            continue
        eid = ALIASES.get(raw_id, raw_id)
        if eid not in merged:
            merged[eid] = {
                "id": eid,
                "title": clean_text(raw.get("title")) or eid,
                "type": clean_text(raw.get("type")) or "other",
                "categories": [],
                "latitude": None,
                "longitude": None,
                "coordinateSource": None,
                "coordinatesApproximate": False,
                "_text": {f: [] for f in TEXT_FIELDS},
                "connectedEntities": [],
                "sources": [],
                "confidence": None,
                "needsReview": False,
                "_reviewNotes": [],
            }
            order.append(eid)
        m = merged[eid]

        for cat in raw.get("categories") or []:
            if cat in CATEGORIES and cat not in m["categories"]:
                m["categories"].append(cat)
            elif cat not in CATEGORIES:
                log.append(f"{eid}: dropped unknown category {cat!r}")

        lat, lon = raw.get("latitude"), raw.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            if m["latitude"] is None:
                m["latitude"], m["longitude"] = float(lat), float(lon)
                m["coordinateSource"] = clean_text(raw.get("coordinateSource"))
                m["coordinatesApproximate"] = raw.get("coordinatesApproximate") is True
            elif abs(m["latitude"] - lat) > 1 or abs(m["longitude"] - lon) > 1:
                m["needsReview"] = True
                m["_reviewNotes"].append("Volumes give different coordinates; the first one is used.")
                log.append(f"{eid}: conflicting coordinates kept first value")

        for field in TEXT_FIELDS:
            text = clean_text(raw.get(field))
            if text and text not in m["_text"][field]:
                m["_text"][field].append(text)

        for conn in raw.get("connectedEntities") or []:
            cid = ALIASES.get(slug(conn), slug(conn))
            if cid and cid not in m["connectedEntities"] and cid != eid:
                m["connectedEntities"].append(cid)

        for src in raw.get("sources") or []:
            if not isinstance(src, dict):
                continue
            key = (src.get("volume"), src.get("chapter"), src.get("locator"), src.get("note"))
            if key not in [(s.get("volume"), s.get("chapter"), s.get("locator"), s.get("note")) for s in m["sources"]]:
                m["sources"].append({
                    "volume": src.get("volume"),
                    "book": clean_text(src.get("book")),
                    "chapter": clean_text(src.get("chapter")),
                    "locator": clean_text(src.get("locator")),
                    "note": clean_text(src.get("note")),
                    "contentKind": clean_text(src.get("contentKind")),
                })

        conf = clean_text(raw.get("confidence"))
        if conf in CONFIDENCE_RANK:
            if m["confidence"] is None or CONFIDENCE_RANK[conf] < CONFIDENCE_RANK[m["confidence"]]:
                m["confidence"] = conf
        if raw.get("needsReview") is True:
            m["needsReview"] = True
        note = clean_text(raw.get("reviewNotes"))
        if note and note not in m["_reviewNotes"]:
            m["_reviewNotes"].append(note)

    out = []
    for eid in order:
        m = merged[eid]
        m["connectedEntities"] = [c for c in m["connectedEntities"] if c in merged]
        for field in TEXT_FIELDS:
            m[field] = " ".join(m["_text"][field]) or None
        m["reviewNotes"] = " ".join(m["_reviewNotes"]) or None
        del m["_text"], m["_reviewNotes"]
        if m["latitude"] is None:
            m["coordinateSource"] = None
            m["coordinatesApproximate"] = False
        if m["confidence"] is None:
            m["confidence"] = "low"
        if not m["sources"]:
            m["needsReview"] = True
            log.append(f"{eid}: no sources recorded")
        out.append(m)
    return out


def unresolved_connections(raw_entities, final_ids, log):
    for raw in raw_entities:
        eid = ALIASES.get(slug(raw.get("id", "")), slug(raw.get("id", "")))
        for conn in raw.get("connectedEntities") or []:
            cid = ALIASES.get(slug(conn), slug(conn))
            if cid not in final_ids:
                log.append(f"{eid}: connection to missing entity {conn!r} dropped")


def validate(dataset):
    problems = []
    ids = set()
    for e in dataset["entities"]:
        eid = e["id"]
        if eid in ids:
            problems.append(f"duplicate id {eid}")
        ids.add(eid)
        if e["type"] not in TYPES:
            problems.append(f"{eid}: unknown type {e['type']!r}")
        for c in e["categories"]:
            if c not in CATEGORIES:
                problems.append(f"{eid}: unknown category {c!r}")
        if (e["latitude"] is None) != (e["longitude"] is None):
            problems.append(f"{eid}: only one coordinate is set")
        if e["latitude"] is not None and not (-90 <= e["latitude"] <= 90 and -180 <= e["longitude"] <= 180):
            problems.append(f"{eid}: coordinates out of range")
        if e["latitude"] is None and e["coordinatesApproximate"]:
            problems.append(f"{eid}: approximate flag without coordinates")
        if not e["sources"]:
            problems.append(f"{eid}: missing sources")
        for s in e["sources"]:
            if not s.get("chapter") or not s.get("book"):
                problems.append(f"{eid}: source missing book or chapter")
    for e in dataset["entities"]:
        for c in e["connectedEntities"]:
            if c not in ids:
                problems.append(f"{e['id']}: dangling connection {c}")
    return problems


def build_meta(dataset, volumes):
    ents = dataset["entities"]
    counts = {c: sum(1 for e in ents if c in e["categories"]) for c in CATEGORIES}
    return {
        "title": "Global Power Atlas",
        "description": "Entities, relationships and source notes extracted from the four-volume Geopolitics, Political Economy & Global Strategy series.",
        "volumes": sorted(volumes, key=lambda v: v.get("volume") or 0),
        "entityCount": len(ents),
        "mappedCount": sum(1 for e in ents if e["latitude"] is not None),
        "approximateCount": sum(1 for e in ents if e["latitude"] is not None and e["coordinatesApproximate"]),
        "needsReviewCount": sum(1 for e in ents if e["needsReview"]),
        "categoryCounts": counts,
        "categories": CATEGORIES,
        "confidenceScale": ["low", "medium", "high"],
    }


def write_data(dataset):
    with open(DATA_PATH, "w", encoding="utf-8") as fh:
        json.dump(dataset, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def embed(dataset):
    with open(HTML_PATH, encoding="utf-8") as fh:
        html = fh.read()
    start = html.find(DATA_START)
    end = html.find(DATA_END)
    if start == -1 or end == -1 or end < start:
        sys.exit("Data markers not found in atlas.html")
    payload = json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    block = DATA_START + "\nwindow.ATLAS_DATA = " + payload + ";\n" + DATA_END
    html = html[:start] + block + html[end + len(DATA_END):]
    with open(HTML_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extract", help="directory containing vol1.json ... vol4.json extraction files")
    parser.add_argument("--report", help="optional path to write the merge log as text")
    args = parser.parse_args()

    log = []
    if args.extract:
        raw_entities, volumes = load_extractions(args.extract)
        entities = merge(raw_entities, log)
        unresolved_connections(raw_entities, {e["id"] for e in entities}, log)
        dataset = {"meta": build_meta({"entities": entities}, volumes), "entities": entities}
        write_data(dataset)
        print(f"Merged {len(raw_entities)} raw records into {len(entities)} entities")
    else:
        with open(DATA_PATH, encoding="utf-8") as fh:
            dataset = json.load(fh)

    problems = validate(dataset)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write("\n".join(log + problems) + "\n")
    for line in log:
        print("note:", line)
    if problems:
        for p in problems:
            print("ERROR:", p)
        sys.exit(1)

    embed(dataset)
    meta = dataset["meta"]
    print(f"Validated {meta['entityCount']} entities; {meta['mappedCount']} mapped; "
          f"{meta['needsReviewCount']} flagged for review; embedded into atlas.html")


if __name__ == "__main__":
    main()
