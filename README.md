# Grab + Gojek Personal Intelligence

A privacy-conscious static dashboard for analysing personal Grab and Gojek history, comparing current ride quotes with historical behaviour, and tracking ride efficiency without publishing raw personal travel records.

## Current historical baseline

The currently published analytics baseline contains the previously imported reports:

- 318 total historical transactions processed
- 292 rides
- 26 GrabFood orders
- SGD 7,908.75 total recorded spend in the supplied reports
- One MYR 15.45 Grab ride is retained only in the source summary and is not mixed into SGD analytics

**Important:** these figures remain the baseline until a new Grab/Gojek history refresh is processed. Rides taken after the last source export are not automatically included yet.

## Current dashboard capabilities

### Ride intelligence

- Route-level historical fare distributions
- Grab vs Gojek comparison
- Grab ride classification into:
  - Grab Fixed
  - Grab Metered
  - Grab Premium / Plus where present
- Hour-of-day pricing patterns
- Day-of-week patterns
- Minimum sample threshold before a timing pattern is treated as reliable
- Provider-specific timing patterns
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

The benchmark fallback order is designed to prefer the most specific reliable evidence first:

1. Grab pricing type + exact hour
2. Provider + exact hour
3. Route + exact hour across providers
4. Grab pricing type + weekday
5. Provider + weekday
6. Route + weekday
7. Grab pricing type overall for the route
8. Provider overall for the route
9. Route overall

A timing benchmark may receive a limited weekday adjustment. The adjustment is capped to avoid overreacting to small historical differences.

### Fare score

The dashboard rates a quoted fare from **0 to 5** against the selected historical benchmark:

- 5: exceptional historical value
- 4: very good
- 3: normal-to-good
- 2: somewhat expensive
- 1: expensive
- 0: unusually expensive

The score is a historical comparison, not a live Grab or Gojek quote.

Cost per kilometre is used as an additional cross-check. It should not be treated as the sole predictor because short journeys, booking fees, surge pricing, tolls, waiting time and metered conditions can materially affect S$/km.

## Privacy model

The public GitHub Pages site contains **aggregated analytics only**.

It should not contain:

- original Grab/Gojek PDFs
- phone numbers or email addresses from reports
- booking codes
- exact home address
- exact V Place address
- exact Compassvale address
- private coordinates
- raw transaction-level history
- OneMap password or credentials

Private residential/work locations are converted into aliases such as:

- `HOME`
- `OFFICE`
- `V_PLACE`
- `COMPASSVALE`

The public route-distance file stores only safe aliases and rounded driving distances.

## OneMap distance setup

The route-distance workflow uses these GitHub Actions secrets:

- `ONEMAP_EMAIL`
- `ONEMAP_PASSWORD`
- `PRIVATE_LOCATIONS_JSON`

There is **no need to manually maintain an `ONEMAP_TOKEN` secret**. The distance script authenticates with OneMap when the workflow runs and obtains a temporary access token for that run.

### Distance workflows

Run in this order when locations/distances need to be refreshed:

1. **Build Route Distances**
2. **Enrich Distance Metrics**
3. GitHub Pages deploys the updated public analytics

The distance workflow now supports the trusted route set, including public destinations such as Madras New Woodlands, Rendezvous Restaurant and Gayathri Little India where they exist in the analytics data.

## Repository structure

```text
docs/
  index.html                 Public dashboard page
  styles.css                 Dashboard styling
  app.js                     Dashboard + Fare Checker logic
  data/
    analytics.json           Aggregated public analytics only

scripts/
  import_grab_pdf.py         Grab PDF importer + service classification
  import_gojek_pdf.py        Gojek importer
  normalization.py           Privacy-safe location normalisation
  build_route_distances.py   OneMap driving-distance calculation
  enrich_distance_metrics.py
                             Adds distance + S$/km to analytics

config/
  route_distances.json       Safe aliases + rounded route distances

.github/workflows/
  deploy-pages.yml
  build-route-distances.yml
  enrich-distance-metrics.yml
```

## Publishing on GitHub Pages

1. Keep the repository public only for aggregated output and non-sensitive code.
2. Keep all private credentials in GitHub Actions Secrets.
3. Keep raw ride reports outside the public repository.
4. Use GitHub Pages / GitHub Actions to deploy the `docs` site.

## Historical data refresh

The project does **not yet have a single production-safe end-to-end refresh workflow** for newly downloaded Grab and Gojek reports.

Until that is completed, avoid running an older analytics builder that could replace the richer hourly, service-type and distance-enriched analytics with a simpler file.

The next data-engineering milestone is one controlled update pipeline:

```text
new Grab/Gojek reports
        ↓
deduplicate transactions
        ↓
classify Grab Fixed / Metered / Premium
        ↓
normalise private/public locations
        ↓
rebuild route + hourly + weekday analytics
        ↓
calculate/update OneMap distances
        ↓
calculate S$/km
        ↓
validate analytics.json
        ↓
publish dashboard
```

## Recommended next improvements

1. Validate the service + distance-aware Fare Checker against real current quotes.
2. Add live quote logging, including quotes that were **not** booked.
3. Build the production-safe historical-data refresh pipeline.
4. Use similar-distance journeys as a fallback for new or low-history routes.
5. Expand Ask My Data beyond predefined questions.
6. Expand food-order intelligence.

## Why live quote logging matters

Completed transaction reports only tell us the ride eventually booked. They do not show high quotes that were rejected.

A future quote logger should be able to record examples such as:

```text
Grab Fixed: S$31
Grab Metered: available
Gojek: S$24
Booked: Gojek at S$24
```

That will make future provider recommendations substantially more informative than completed-trip history alone.
