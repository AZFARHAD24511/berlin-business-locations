# Data directory

## Where to put files
- `raw/`: original IHK Berlin export ZIP or CSV files.
- `processed/`: generated cleaned datasets and intermediate tables.

Raw and processed data are excluded from Git by default to avoid large commits and accidental redistribution.

## Provenance checklist
Before publishing results, document:
- Official source URL
- Date downloaded
- Data period covered
- File names and formats
- Data dictionary / definitions
- License and reuse terms
- Any transformations or filtering

The loader supports CSV files and ZIP files containing CSV files. Verify the source schema before relying on the pipeline output.
