# doi-iso4

To add doi:
python doi.py input.bib output.bib --enrich --clean --arxiv --verbose

To set journal field in the ISO4 standard:
python iso4.py original.bib modified.bib --iso4-csv journals.csv
