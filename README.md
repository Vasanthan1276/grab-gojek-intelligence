# Grab + Gojek Personal Intelligence

A privacy-conscious static dashboard for analysing personal Grab and Gojek history, comparing current ride quotes with historical behaviour, and tracking ride efficiency without publishing raw personal travel records.

## Current data foundation

The private historical seed used for the refresh pipeline starts from the previously validated baseline:

- 318 total historical transactions
- 292 rides
- 26 GrabFood orders
- SGD 7,908.75 recorded spend
- one MYR 15.45 Grab ride retained in the private history/source summary but not mixed into SGD fare analytics

After a historical refresh is run, the figures shown in `docs/data/analytics.json` and on the dashboard become the current source of truth and may be higher than this seed baseline.

## Current dashboard capabilities

### Ride intelligence

- Route-level historical fare distributions
- Grab vs Gojek comparison
- Grab classification into Fixed, Metered and Premium / Plus where present
- Exact-hour pricing patterns
- Day-of-week patterns
- Provider-specific timing patterns
- Minimum sample threshold before a timing pattern is treated as reliable
- Driving distance for trusted routes using OneMap
- Average and median S$/km
- Booking-option S$/km comparison

### Service + distance-aware Fare Checker

The Fare Checker can use:

- route
- provider
- Grab pricing type
- journey hour
- weekday
- historical fare distribution
- driving distance
- quote S$/km
- historical S$/km

The benchmark fallback order prefers the most specific reliable evidence first:

1. Grab pricing type + exact hour
2. Provider + exact hour
3. Route + exact hour across providers
4. Grab pricing type + weekday
5. Provider + weekday
6. Route + weekday
7. Grab pricing type overall for the route
8. Provider overall for the route
9. Route overall

The dashboard scores a quote from 0 to 5. Cost/km is a cross-check rather than the sole predictor because booking fees, surge pricing, tolls, waiting time and metered conditions can materially affect S$/km.

## Privacy model

The public GitHub repository and GitHub Pages site should contain aggregated analytics only.

Never publish:

- original Grab/Gojek PDFs
- exact private addresses
- raw transaction-level history
- booking codes
- phone numbers or email addresses from reports
- private coordinates
- OneMap credentials
- `config/private_aliases.json`
- anything inside `local_private/` or `local_data/`

Private locations are converted to safe aliases such as `HOME`, `OFFICE`, `V_PLACE` and `COMPASSVALE` before public analytics are generated.

## Production-safe historical refresh

The project now has a local refresh pipeline designed specifically to prevent raw personal reports from entering the public GitHub repository.

```text
fresh Grab/Gojek PDFs (local only)
        ↓
import + private location normalisation
        ↓
merge with private historical master
        ↓
deduplicate overlapping report periods
        ↓
classify Grab Fixed / Metered / Premium
        ↓
rebuild route + hour + weekday analytics
        ↓
apply existing OneMap route distances
        ↓
recalculate S$/km
        ↓
privacy + shrinkage validation
        ↓
docs/data/analytics.json
```

### Why the refresh runs locally

The repository is public. Original ride reports and the transaction-level master therefore must not be sent through a public GitHub Actions workflow or committed to the repository.

The private inputs stay on the local computer. Only the aggregated `docs/data/analytics.json` is committed.

## One-time local setup

### 1. Keep a local copy of the repository

GitHub Desktop is recommended on Windows because it makes it easy to see exactly which files will be committed.

### 2. Install Python

Use Python 3.12 or later. During installation, enable **Add Python to PATH**.

### 3. Tesseract OCR

Grab statement PDFs currently require Tesseract OCR. The refresh script automatically checks the normal Windows Tesseract installation folders.

Gojek-only refreshes do not need Tesseract.

### 4. Private aliases

Run:

```text
setup_private_aliases.bat
```

Enter distinctive fragments for the private aliases requested. The resulting file is:

```text
config/private_aliases.json
```

It is ignored by Git and must remain local.

### 5. Private historical master

Place the supplied private seed at:

```text
local_private/transactions.json
```

`local_private/` is ignored by Git. Do not upload this file through the GitHub website.

## Updating history with new reports

Put fresh exports here:

```text
local_data/grab/
local_data/gojek/
```

It is safe for the new reports to overlap the previous reporting period. The refresh uses provider + timestamp + fare + currency + category as the stable deduplication fingerprint, so overlapping exports should not double-count the same journey.

Then double-click:

```text
refresh_history.bat
```

On the first run it creates a local `.venv` and installs the Python packages in `requirements.txt`.

The refresh produces:

```text
docs/data/analytics.json                 PUBLIC aggregated output
local_private/transactions.json          PRIVATE master
local_private/last_refresh_report.json   PRIVATE refresh report
local_private/backups/...                PRIVATE analytics backups
```

The script includes a safety stop if the regenerated transaction count unexpectedly becomes lower than the currently published analytics count.

## Route publishing rule

All previously trusted routes remain trusted.

For a brand-new route, the refresh automatically publishes it only when:

- it has at least 2 historical rides, and
- both location labels look clean enough for public analytics.

One-off or questionable new routes remain in the private master and are listed in `local_private/last_refresh_report.json` for later review. This prevents OCR-garbage locations from polluting the public dashboard.

## After a successful local refresh

Review the refreshed dashboard and then commit only the safe public changes, principally:

```text
docs/data/analytics.json
```

If the refresh introduced a new route that does not yet have a driving distance, run the GitHub Actions workflows in this order:

1. **Build Route Distances**
2. **Enrich Distance Metrics**

The OneMap workflow continues to request a temporary access token automatically from `ONEMAP_EMAIL` and `ONEMAP_PASSWORD`; there is no manually maintained `ONEMAP_TOKEN` secret.

## Repository structure

```text
docs/
  index.html
  styles.css
  app.js
  data/
    analytics.json              Public aggregated analytics

scripts/
  import_grab_pdf.py            Grab importer + service detection
  import_gojek_pdf.py           Gojek importer
  normalization.py              Location normalisation
  build_analytics.py            Full service/timing analytics builder
  refresh_history.py            Safe local merge + rebuild pipeline
  setup_private_aliases.py      One-time local privacy alias setup
  build_route_distances.py      OneMap driving-distance builder
  enrich_distance_metrics.py    Distance + S$/km enrichment

config/
  route_distances.json          Public rounded route distances
  private_aliases.json          PRIVATE/local only, Git ignored

local_data/                     PRIVATE/local only, Git ignored
  grab/
  gojek/

local_private/                  PRIVATE/local only, Git ignored
  transactions.json
  last_refresh_report.json

.github/workflows/
  deploy-pages.yml
  build-route-distances.yml
  enrich-distance-metrics.yml

refresh_history.bat
setup_private_aliases.bat
```

## Recommended next improvements

1. Refresh the historical data with the post-trip Grab/Gojek reports.
2. Add live quote logging, including quotes that were not booked.
3. Use similar-distance journeys as a fallback for new or low-history routes.
4. Expand Ask My Data beyond predefined questions.
5. Expand food-order intelligence.

## Why live quote logging is still important

Completed transaction reports show only the ride eventually booked. They do not show a high quote that was rejected. A later quote logger can record Grab Fixed, Grab Metered and Gojek quotes together with the option ultimately selected. That will provide stronger evidence for future booking recommendations than completed-trip history alone.
