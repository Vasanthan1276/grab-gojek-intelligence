# Grab + Gojek Personal Intelligence

A privacy-conscious static dashboard for analysing aggregated Grab and Gojek history.

## Current baseline

- 318 total historical transactions processed
- 292 rides
- 26 GrabFood orders
- SGD 7,908.75 total recorded spend in the supplied reports
- One MYR 15.45 Grab ride is retained only in the source summary and is not mixed into SGD analytics

The published site contains **aggregated analytics only**. It does not contain the original PDFs, phone number, email address, booking codes, exact home address, exact transaction timeline, or raw transaction-level dataset.

## Publish on GitHub Pages

1. Create a repository named `grab-gojek-intelligence`.
2. Upload the contents of this folder to the repository root.
3. Open **Settings -> Pages** and select **GitHub Actions** as the source if prompted.
4. Open the **Actions** tab and run **Deploy dashboard to Pages**, or push a new commit to `main`.

## Monthly updates - current safe workflow

Raw reports should stay off the public repository.

1. Put new PDFs in a local private folder.
2. Process them with the importer scripts once the private alias configuration is set up.
3. Commit only the regenerated `docs/data/analytics.json`.

The next project phase can automate this with either a private processing repository or another private storage method, while publishing only aggregate results.

## Repository structure

```
docs/                    Public GitHub Pages site
  index.html
  styles.css
  app.js
  data/analytics.json    Aggregated data only
scripts/                 Local import/analysis tools
config/                  Example alias configuration only
.github/workflows/       GitHub Pages deployment
```

## Fare score

The dashboard rates a quoted fare from **0 to 5** against the historical distribution for the selected route/provider:

- 5: exceptional historical value
- 4: very good
- 3: normal-to-good
- 2: somewhat expensive
- 1: expensive
- 0: unusually expensive

This is a historical comparison, not a live fare quote.
