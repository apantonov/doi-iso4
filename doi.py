#!/usr/bin/env python3
import os
import time
import json
import requests
import argparse
import pandas as pd
from pybtex.database import parse_file
from pybtex.database.output.bibtex import Writer

# ================= CACHES ==================
DOI_CACHE_FILE = "doi_cache.json"
ISO4_LOCAL_FILE = "iso4_local.json"
SLEEP = 0.5

if os.path.exists(DOI_CACHE_FILE):
    with open(DOI_CACHE_FILE, encoding="utf-8") as f:
        DOI_CACHE = json.load(f)
else:
    DOI_CACHE = {}

if os.path.exists(ISO4_LOCAL_FILE):
    with open(ISO4_LOCAL_FILE, encoding="utf-8") as f:
        ISO4_LOCAL = json.load(f)
else:
    ISO4_LOCAL = {}

def save_doi_cache():
    with open(DOI_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(DOI_CACHE, f, indent=2)

# ================= UTILS ==================
def normalize(text):
    return text.lower().replace("{", "").replace("}", "").strip()

def protect_caps(title):
    words = title.split()
    out = []
    for w in words:
        if any(c.isupper() for c in w[1:]):
            out.append("{" + w + "}")
        else:
            out.append(w)
    return " ".join(out)

def similar(t1, t2):
    t1 = normalize(t1)
    t2 = normalize(t2)
    return t1[:70] in t2 or t2[:70] in t1

# ================= METADATA ==================
def query_openalex(title):
    url = "https://api.openalex.org/works"
    params = {"search": title, "per-page": 3}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for work in data.get("results", []):
            if similar(title, work.get("title", "")):
                return work
    except Exception as e:
        print(f"OpenAlex failed: {e}")
    return None

def query_crossref(title):
    url = "https://api.crossref.org/works"
    params = {"query": title, "rows": 3}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for item in data.get("message", {}).get("items", []):
            found = item.get("title", [""])[0]
            if similar(title, found):
                return item
    except Exception as e:
        print(f"Crossref failed: {e}")
    return None

def enrich(entry, verbose=False):
    title = entry.fields.get("title")
    if not title:
        return
    key = normalize(title)

    if key in DOI_CACHE:
        meta = DOI_CACHE[key]
    else:
        meta = None
        work = query_openalex(title)
        if work:
            host_venue = work.get("host_venue") or {}
            journal_name = host_venue.get("display_name") or host_venue.get("name") or None
            biblio = work.get("biblio") or {}
            meta = {
                "doi": work.get("doi"),
                "journal": journal_name,
                "year": work.get("publication_year"),
                "volume": biblio.get("volume"),
                "pages": biblio.get("first_page"),
            }
        else:
            work = query_crossref(title)
            if work:
                container = work.get("container-title", [""])
                meta = {
                    "doi": work.get("DOI"),
                    "journal": container[0] if container else None,
                    "year": work.get("issued", {}).get("date-parts", [[None]])[0][0],
                    "volume": work.get("volume"),
                    "pages": work.get("page"),
                }
        DOI_CACHE[key] = meta
        save_doi_cache()
        time.sleep(SLEEP)

    if not meta:
        if verbose:
            print(f"  No metadata for '{title}'")
        return

    # DOI
    doi = meta.get("doi")
    if doi:
        journal = meta.get("journal") or entry.fields.get("journal")
        if journal:
            if "arXiv" in journal:
                entry.fields["url"] = doi
                entry.fields.pop("doi", None)
            else:
                doi = doi.replace("https://doi.org/", "")
                entry.fields["doi"] = doi

    # year, volume, pages
    for f in ["year","volume","pages"]:
        val = meta.get(f)
        if val:
            entry.fields[f] = str(val)

# ================= ARXIV ==================
def handle_arxiv(entry, verbose=False):
    if "eprint" in entry.fields or "arXiv" in entry.fields:
        entry.fields["archivePrefix"] = "arXiv"
     #   entry.fields.pop("doi", None)
        if verbose:
            print(f"  arXiv handled for {entry.key}")

# ================= CLEAN ==================
def clean(entry, verbose=False):
    if "title" in entry.fields:
        old = entry.fields["title"]
        entry.fields["title"] = protect_caps(old)
        if verbose and old != entry.fields["title"]:
            print(f"  Title protected for {entry.key}")
    for f in ["abstract","keywords","file"]: #"url"
        if f in entry.fields:
            entry.fields.pop(f)
            if verbose:
                print(f"  Removed {f} from {entry.key}")

# ================= PROCESS ==================
def process_bib(input_file, output_file, enrich_flag, arxiv_flag, clean_flag, verbose):
    if not os.path.exists(input_file):
        print(f"Input '{input_file}' not found")
        return
    bib_data = parse_file(input_file)
    if not bib_data.entries:
        print("No entries found")
        return

    for i, entry in enumerate(bib_data.entries.values(), start=1):
        if verbose:
            print(f"[{i}/{len(bib_data.entries)}] {entry.key}")
        if enrich_flag:
            enrich(entry, verbose)
        if arxiv_flag:
            handle_arxiv(entry, verbose)
        if clean_flag:
            clean(entry, verbose)

    w = Writer()
    w.indent = "  "
    w.comma_first = False
    w.order_entries_by_key = False
    w.write_file(bib_data, output_file)
    print(f"\nWritten {len(bib_data.entries)} entries -> {output_file}")

# ================= CLI ==================
if __name__=="__main__":
    parser = argparse.ArgumentParser(prog="clean_bib.py",
        description="Clean & enrich .bib with DOI + arXiv + CSV import")
    parser.add_argument("input", help="Input .bib")
    parser.add_argument("output", help="Output .bib")
    parser.add_argument("--enrich", action="store_true", help="Add DOI/journal/year/vol/pages")
    parser.add_argument("--arxiv", action="store_true", help="Process arXiv")
    parser.add_argument("--clean", action="store_true", help="Clean fields & protect caps")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    process_bib(
        args.input, args.output,
        args.enrich, args.arxiv, args.clean, args.verbose
    )
