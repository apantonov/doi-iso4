import os
import json
import argparse
import bibtexparser
from bibtexparser.bwriter import BibTexWriter

# -----------------------------
# Constants and cache
# -----------------------------
DOI_CACHE_FILE = "doi_cache.json"
DOI_CACHE = {}
if os.path.exists(DOI_CACHE_FILE):
    try:
        with open(DOI_CACHE_FILE, "r", encoding="utf-8") as f:
            DOI_CACHE = json.load(f)
    except (json.JSONDecodeError, ValueError):
        DOI_CACHE = {}

# -----------------------------
# Processing the journal name
# -----------------------------
def normalize_journal(name):
    if not name:
        return ""
    # removing brackets, quotation marks, dots, etc.
    name = name.replace("{","").replace("}","").replace('"','')
    name = name.replace(".","").replace("\n","").replace("\t","").strip().lower()
    return name

# -----------------------------
# Uploading CSV with ISO4
# -----------------------------
ISO4_DICT = {}
def load_iso4_csv(csv_path):
    global ISO4_DICT
    ISO4_DICT = {}
    if not os.path.exists(csv_path):
        print(f"Error: CSV file {csv_path} не найден")
        return
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[1:]:  # skipping title
        parts = line.strip().split(",")
        if len(parts) >= 2:
            journal, iso4 = parts[0].strip(), parts[1].strip()
            key = normalize_journal(journal)  # creating key
            ISO4_DICT[key] = iso4

# -----------------------------
# Repalcing with ISO4
# -----------------------------
def enrich_entry(entry):

    # Replacing journal with ISO4
    if "journal" in entry:
        key = normalize_journal(entry["journal"])
        if key in ISO4_DICT:
            entry["journal"] = ISO4_DICT[key]

# -----------------------------
# Processing the bib-file
# -----------------------------
def process_bib(input_file, output_file):
    with open(input_file, encoding="utf-8") as f:
        db = bibtexparser.load(f)
    for entry in db.entries:
        enrich_entry(entry)
    writer = BibTexWriter()
    writer.indent = "  "
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(writer.write(db))
    print(f"File proceeded: {output_file}")

# -----------------------------
# Arguments
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BibTeX cleaner with ISO4 journal names")
    parser.add_argument("input", help="Input bib file")
    parser.add_argument("output", help="Output bib file")
    parser.add_argument("--iso4-csv", help="CSV with JournalTitle,ISO4", required=True)
    args = parser.parse_args()

    load_iso4_csv(args.iso4_csv)
    process_bib(args.input, args.output)