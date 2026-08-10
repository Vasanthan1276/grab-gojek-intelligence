# Grab + Gojek Personal Intelligence

A privacy-conscious static dashboard for analysing personal Grab and Gojek history, comparing current ride quotes with historical behaviour, and tracking ride efficiency without publishing raw personal travel records.

## Current data foundation

As of the 10 Aug 2026 historical refresh, the public aggregated analytics represents:

- 343 total historical transactions
- 317 rides
- 26 GrabFood orders
- SGD 8,579.44 recorded spend
- one MYR 15.45 Grab ride retained in the private history/source summary but not mixed into SGD fare analytics

`docs/data/analytics.json` and the dashboard are the current source of truth after each successful refresh.

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

The Fare Checker can use route, provider, Grab pricing type, journey hour, weekday, historical fare distribution, driving distance, quote S$/km and historical S$/km.

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

The public GitHub repository and GitHub Pages site contain aggregated analytics only.

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

### Stronger route privacy rules

A route being historically trusted no longer bypasses the privacy check.

- `PRIVATE_xxxxxx` labels are never published as route analytics.
- legacy readable work labels are consolidated into `OFFICE` before analytics are rebuilt.
- one-off or unclean routes remain only in the private master/report.
- previously hashed `PRIVATE_xxxxxx` entries cannot be reverse-mapped to an address; they remain private unless a future source report provides a readable location again.

## Production-safe historical refresh

The refresh pipeline runs locally because the repository is public.

```text
fresh Grab/Gojek PDFs (local only)
        ↓
import + private location normalisation
        ↓
re-normalise the existing private historical master
        ↓
merge + deduplicate overlapping report periods
        ↓
classify Grab Fixed / Metered / Premium
        ↓
rebuild route + hour + weekday analytics
        ↓
exclude private/unclean routes from public analytics
        ↓
apply existing OneMap distances
        ↓
recalculate S$/km
        ↓
privacy + shrinkage validation
        ↓
docs/data/analytics.json
```

The stable deduplication fingerprint intentionally excludes origin/destination. This allows historical location labels to be cleaned up without duplicating transactions.

## Updating history

Put fresh exports here:

```text
local_data/grab/
local_data/gojek/
```

Then double-click:

```text
refresh_history.bat
```

The refresh produces:

```text
docs/data/analytics.json                 PUBLIC aggregated output
local_private/transactions.json          PRIVATE master
local_private/last_refresh_report.json   PRIVATE refresh report
local_private/backups/...                PRIVATE analytics backups
```

Overlapping report periods are allowed. Duplicate transactions are skipped.

## Route publishing rule

For a route to appear publicly:

1. both location labels must pass the privacy/cleanliness check; and
2. it must either already be a clean trusted route or have at least 2 historical rides.

A historical route with a `PRIVATE_xxxxxx` or legacy unclean label is no longer carried forward merely because it was previously trusted.

## OneMap route distances

The `Build Route Distances` workflow now:

- processes **all** current public routes; there is no 60-route cap
- uses precise public searches for known ambiguous POIs
- keeps private locations in `PRIVATE_LOCATIONS_JSON` GitHub Secrets
- never stores private coordinates or exact private addresses
- rounds published driving distance to 0.5 km
- preserves an existing valid rounded distance if a temporary OneMap lookup/routing failure occurs
- drops stale distance records for routes that no longer exist in public analytics

After a local history refresh, run GitHub Actions in this order:

1. **Build Route Distances**
2. **Enrich Distance Metrics**

The OneMap workflow requests a temporary access token automatically from `ONEMAP_EMAIL` and `ONEMAP_PASSWORD`; a manually maintained `ONEMAP_TOKEN` secret is not required.

## One-time local setup

### GitHub Desktop

Keep a local clone so private data never has to be uploaded through the GitHub website.

For active development, keeping the working repository outside a OneDrive-synchronised folder is preferable because cloud sync can temporarily lock Git's internal files.

### Python and Tesseract

The Windows refresh uses Python and Tesseract OCR for Grab PDFs. Gojek-only refreshes do not require Tesseract.

### Private aliases

Run once:

```text
setup_private_aliases.bat
```

The resulting:

```text
config/private_aliases.json
```

is local-only and Git ignored.

## Repository structure

```text
docs/
  index.html
  styles.css
  app.js
  data/
    analytics.json

scripts/
  import_grab_pdf.py
  import_gojek_pdf.py
  normalization.py
  build_analytics.py
  refresh_history.py
  setup_private_aliases.py
  build_route_distances.py
  enrich_distance_metrics.py

config/
  route_distances.json
  private_aliases.json          PRIVATE/local only

local_data/                     PRIVATE/local only
local_private/                  PRIVATE/local only

.github/workflows/
  deploy-pages.yml
  build-route-distances.yml
  enrich-distance-metrics.yml

refresh_history.bat
setup_private_aliases.bat
```

## Recommended next improvement

The next major feature is **live quote logging**.

Completed transaction reports show only the ride eventually booked. A live quote logger can capture:

- Grab Fixed quote
- Grab Metered availability/final fare
- Gojek quote
- route/date/time
- option selected
- quoted S$/km

That will let future recommendations learn from prices that were seen but rejected, not only completed trips.
