let DATA = null;

/* =========================================================
   HELPERS
========================================================= */
const money = (value) => `S$${Number(value || 0).toFixed(2)}`;

function label(value) {
  if (!value) return "";
  return String(value)
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const routeName = (route) => `${label(route.origin)} → ${label(route.destination)}`;

function formatMonth(value) {
  if (!value) return "";
  const [year, month] = value.split("-");
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("en-SG", {
    month: "short",
    year: "2-digit"
  });
}

function formatHour(hour) {
  const h = Number(hour);
  if (!Number.isFinite(h)) return String(hour || "");
  const text = String(h).padStart(2, "0");
  return `${text}:00–${text}:59`;
}

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDistance(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? `${n.toFixed(1)} km` : "—";
}

function formatCostPerKm(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? `S$${n.toFixed(2)}/km` : "—";
}

const routeDistanceKm = (route) => {
  const n = Number(route?.distance?.distance_km);
  return Number.isFinite(n) && n > 0 ? n : null;
};

const minimumTimingSample = () =>
  Number(DATA?.analysis_config?.timing_minimum_reliable_sample || 5);

function confidenceLevel(count) {
  if (count >= 30) return { text: "High confidence", className: "confidence-high" };
  if (count >= 10) return { text: "Good confidence", className: "confidence-medium" };
  if (count >= 5) return { text: "Early pattern", className: "confidence-low" };
  return { text: "Limited history", className: "confidence-low" };
}

function reliableEntries(object, minimumCount = minimumTimingSample()) {
  return Object.entries(object || {}).filter(([, stats]) =>
    Number(stats?.count || 0) >= minimumCount
  );
}

function cheapestEntry(object, minimumCount = minimumTimingSample()) {
  const entries = reliableEntries(object, minimumCount);
  if (!entries.length) return null;
  return entries.reduce((best, current) =>
    Number(current[1].average) < Number(best[1].average) ? current : best
  );
}

function mostExpensiveEntry(object, minimumCount = minimumTimingSample()) {
  const entries = reliableEntries(object, minimumCount);
  if (!entries.length) return null;
  return entries.reduce((worst, current) =>
    Number(current[1].average) > Number(worst[1].average) ? current : worst
  );
}

function createTimingInsight(entry) {
  return entry ? { key: entry[0], label: formatHour(entry[0]), stats: entry[1] } : null;
}

const getBestHour = (route) =>
  route.timing_insights?.best_hour || createTimingInsight(cheapestEntry(route.hourly));

const getWorstHour = (route) =>
  route.timing_insights?.worst_hour || createTimingInsight(mostExpensiveEntry(route.hourly));

/* =========================================================
   INITIALISE
========================================================= */
async function init() {
  const response = await fetch(`data/analytics.json?v=${Date.now()}`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Unable to load analytics.json. HTTP ${response.status}`);
  }

  DATA = await response.json();

  renderSummary();
  renderProviders();
  renderMonthly();
  renderCoreRoutes();
  fillRoutes();
  renderFood();

  wireTabs();
  wireFareChecker();
  wireAgent();
}

/* =========================================================
   OVERVIEW
========================================================= */
function renderSummary() {
  const s = DATA.summary;

  const cards = [
    ["Total spend", money(s.total_spend_sgd), "SGD across both reports"],
    ["Ride spend", money(s.ride_spend_sgd), `${s.ride_transactions} rides`],
    ["Food spend", money(s.food_spend_sgd), `${s.food_orders} GrabFood orders`],
    ["Average food order", money(s.average_food_order), "Historical average"]
  ];

  const container = document.querySelector("#summaryCards");

  if (!container) {
    return;
  }

  container.innerHTML = cards
    .map(
      ([title, value, sub]) => `
        <article class="card metric">
          <div class="label">${title}</div>
          <div class="value">${value}</div>
          <div class="sub">${sub}</div>
        </article>
      `
    )
    .join("");
}

function renderProviders() {
  const container = document.querySelector("#providerSnapshot");

  if (!container) {
    return;
  }

  container.innerHTML = Object.entries(DATA.providers || {})
    .map(
      ([provider, v]) => `
        <div class="provider-row">
          <div>
            <strong>${provider}</strong>
            <div class="muted">
              ${v.rides} rides · avg ${money(v.average_ride)}
            </div>
          </div>

          <strong>${money(v.spend_sgd)}</strong>
        </div>
      `
    )
    .join("");
}

function renderMonthly() {
  const container = document.querySelector("#monthlyChart");

  if (!container) {
    return;
  }

  const monthly = Array.isArray(DATA.monthly)
    ? DATA.monthly
    : [];

  if (!monthly.length) {
    container.innerHTML = `
      <div class="monthly-empty">
        No monthly data available.
      </div>
    `;

    return;
  }

  const totals = monthly.map(
    (m) =>
      Number(m["Grab rides"] || 0) +
      Number(m["Gojek rides"] || 0) +
      Number(m.GrabFood || 0)
  );

  const maximum = Math.max(...totals, 1);

  container.innerHTML = `
    <div class="monthly-chart">

      <div class="monthly-legend">
        <div class="legend-item">
          <span class="legend-dot legend-grab"></span>
          Grab rides
        </div>

        <div class="legend-item">
          <span class="legend-dot legend-gojek"></span>
          Gojek rides
        </div>

        <div class="legend-item">
          <span class="legend-dot legend-food"></span>
          GrabFood
        </div>
      </div>

      <div class="monthly-bars">

        ${monthly
          .map((m) => {
            const grab = Number(m["Grab rides"] || 0);
            const gojek = Number(m["Gojek rides"] || 0);
            const food = Number(m.GrabFood || 0);

            const total =
              grab +
              gojek +
              food;

            const height =
              total
                ? Math.max(
                    (total / maximum) * 100,
                    4
                  )
                : 0;

            const share = (n) =>
              total
                ? (n / total) * 100
                : 0;

            const tip =
              `${formatMonth(m.month)}` +
              ` | Total: ${money(total)}` +
              ` | Grab: ${money(grab)}` +
              ` | Gojek: ${money(gojek)}` +
              ` | GrabFood: ${money(food)}`;

            return `
              <div class="month-column">

                <div class="month-value">
                  ${Math.round(total)}
                </div>

                <div class="month-bar-area">

                  <div
                    class="month-stack"
                    style="height:${height}%;"
                    title="${escapeHTML(tip)}"
                  >

                    ${
                      gojek
                        ? `
                          <div
                            class="month-segment segment-gojek"
                            style="height:${share(gojek)}%;"
                          ></div>
                        `
                        : ""
                    }

                    ${
                      grab
                        ? `
                          <div
                            class="month-segment segment-grab"
                            style="height:${share(grab)}%;"
                          ></div>
                        `
                        : ""
                    }

                    ${
                      food
                        ? `
                          <div
                            class="month-segment segment-food"
                            style="height:${share(food)}%;"
                          ></div>
                        `
                        : ""
                    }

                  </div>

                </div>

                <div class="month-label">
                  ${formatMonth(m.month)}
                </div>

              </div>
            `;
          })
          .join("")}

      </div>

    </div>
  `;
}

function renderCoreRoutes() {
  const body = document.querySelector("#coreRoutes");

  if (!body) {
    return;
  }

  body.innerHTML = (DATA.core_routes || [])
    .map((route) => {
      const grab =
        route.providers?.Grab?.average;

      const gojek =
        route.providers?.Gojek?.average;

      const comparison =
        route.provider_comparison;

      const edge =
        comparison
          ? `${comparison.cheaper} by ${money(
              comparison.average_saving
            )}`
          : "Not enough comparison data";

      return `
        <tr>
          <td>${routeName(route)}</td>
          <td>${route.overall.count}</td>
          <td>${money(route.overall.median)}</td>

          <td>
            ${
              grab != null
                ? money(grab)
                : "—"
            }
          </td>

          <td>
            ${
              gojek != null
                ? money(gojek)
                : "—"
            }
          </td>

          <td class="good">
            ${edge}
          </td>
        </tr>
      `;
    })
    .join("");
}

/* =========================================================
   ROUTES
========================================================= */
function fillRoutes() {
  const routes = (DATA.routes || [])
    .filter(
      (route) =>
        route.overall?.count >= 2
    )
    .sort(
      (a, b) =>
        b.overall.count -
        a.overall.count
    );

  const options = routes
    .map(
      (route) =>
        `<option value="${escapeHTML(
          String(route.key).trim()
        )}">${escapeHTML(
          routeName(route)
        )} (${route.overall.count})</option>`
    )
    .join("");

  const routeSelect =
    document.querySelector(
      "#routeSelect"
    );

  const fareRoute =
    document.querySelector(
      "#fareRoute"
    );

  if (routeSelect) {
    routeSelect.innerHTML =
      options;

    routeSelect.addEventListener(
      "change",
      (event) =>
        showRoute(
          String(
            event.target.value ||
            ""
          ).trim()
        )
    );
  }

  if (fareRoute) {
    fareRoute.innerHTML =
      options;
  }

  if (routeSelect?.value) {
    showRoute(
      String(
        routeSelect.value
      ).trim()
    );
  }
}

function bookingOptionLabel(
  provider,
  pricingType
) {
  if (
    provider ===
    "Gojek"
  ) {
    return "Gojek";
  }

  const names = {
    Fixed:
      "Grab Fixed",

    Metered:
      "Grab Metered",

    Premium:
      "Grab Premium"
  };

  return (
    names[
      pricingType
    ]
    ||
    `Grab ${pricingType}`
  );
}

function getBookingOptions(route) {
  const options = [];

  const pricingTypes =
    route.grab_pricing_types ||
    {};

  const preferred = [
    "Fixed",
    "Metered",
    "Premium"
  ];

  [
    ...preferred,
    ...Object.keys(
      pricingTypes
    ).filter(
      (key) =>
        !preferred.includes(
          key
        )
    )
  ].forEach(
    (pricingType) => {

      const stats =
        pricingTypes[
          pricingType
        ];

      if (!stats) {
        return;
      }

      options.push(
        {
          id:
            `grab-${String(
              pricingType
            )
              .toLowerCase()
              .replace(
                /\s+/g,
                "-"
              )}`,

          provider:
            "Grab",

          pricingType,

          label:
            bookingOptionLabel(
              "Grab",
              pricingType
            ),

          stats,

          costPerKm:
            route
              .cost_per_km
              ?.grab_pricing_types
              ?.[pricingType]
            ||
            null,

          hourly:
            route
              .grab_pricing_hourly
              ?.[pricingType]
            ||
            {},

          weekdays:
            route
              .grab_pricing_weekdays
              ?.[pricingType]
            ||
            {}
        }
      );

    }
  );

  if (
    route
      .providers
      ?.Gojek
  ) {

    options.push(
      {
        id:
          "gojek",

        provider:
          "Gojek",

        pricingType:
          "Standard",

        label:
          "Gojek",

        stats:
          route
            .providers
            .Gojek,

        costPerKm:
          route
            .cost_per_km
            ?.providers
            ?.Gojek
          ||
          null,

        hourly:
          route
            .provider_hourly
            ?.Gojek
          ||
          {},

        weekdays:
          route
            .provider_weekdays
            ?.Gojek
          ||
          {}
      }
    );

  }

  return options;
}

function timingInsightForHourly(hourly) {
  return {
    best:
      createTimingInsight(
        cheapestEntry(
          hourly
        )
      ),

    worst:
      createTimingInsight(
        mostExpensiveEntry(
          hourly
        )
      )
  };
}

function formatOptionCell(stats) {
  if (!stats) {
    return "—";
  }

  const reliable =
    Number(
      stats.count ||
      0
    )
    >=
    minimumTimingSample();

  return `
    <strong>
      ${money(
        stats.average
      )}
    </strong>

    <br>

    <small class="muted">
      ${stats.count}
      trip${
        stats.count === 1
          ? ""
          : "s"
      }

      ${
        reliable
          ? ""
          : " · low sample"
      }
    </small>
  `;
}

function showRoute(key) {
  const cleanKey =
    String(
      key ||
      ""
    ).trim();

  const route =
    (
      DATA.routes ||
      []
    )
      .find(
        (item) =>
          String(
            item.key ||
            ""
          ).trim()
          ===
          cleanKey
      );

  if (!route) {
    return;
  }

  const minimumSample =
    minimumTimingSample();

  const confidence =
    confidenceLevel(
      route.overall.count
    );

  const distanceKm =
    routeDistanceKm(
      route
    );

  const overallCostPerKm =
    route
      .cost_per_km
      ?.overall
    ||
    null;

  const bestHour =
    getBestHour(
      route
    );

  const worstHour =
    getWorstHour(
      route
    );

  const bookingOptions =
    getBookingOptions(
      route
    );

  const topRoutes =
    (
      DATA.routes ||
      []
    )
      .filter(
        (item) =>
          item
            .overall
            ?.count >=
          3
      )
      .sort(
        (
          a,
          b
        ) =>
          b
            .overall
            .count
          -
          a
            .overall
            .count
      )
      .slice(
        0,
        8
      );

  let timingDifference =
    null;

  let timingDifferencePercent =
    null;

  if (
    bestHour &&
    worstHour
  ) {

    timingDifference =
      Number(
        worstHour
          .stats
          .average
      )
      -
      Number(
        bestHour
          .stats
          .average
      );

    timingDifferencePercent =
      Number(
        bestHour
          .stats
          .average
      ) > 0
        ? (
            timingDifference
            /
            Number(
              bestHour
                .stats
                .average
            )
          )
          *
          100
        : null;
  }

  const reliableOptions =
    bookingOptions
      .filter(
        (option) =>
          Number(
            option
              .stats
              .count ||
            0
          )
          >=
          minimumSample
      )
      .sort(
        (
          a,
          b
        ) =>
          Number(
            a
              .stats
              .average
          )
          -
          Number(
            b
              .stats
              .average
          )
      );

  const lowestAverageOption =
    reliableOptions[0] ||
    null;

  const efficientOptions =
    bookingOptions
      .filter(
        (option) =>
          Number(
            option
              .stats
              .count ||
            0
          )
          >=
          minimumSample
          &&
          Number(
            option
              .costPerKm
              ?.average ||
            0
          ) > 0
      )
      .sort(
        (
          a,
          b
        ) =>
          Number(
            a
              .costPerKm
              .average
          )
          -
          Number(
            b
              .costPerKm
              .average
          )
      );

  const lowestCostPerKmOption =
    efficientOptions[0] ||
    null;

  const optionCards =
    bookingOptions
      .map(
        (option) => {

          const stats =
            option.stats;

          const optionConfidence =
            confidenceLevel(
              stats.count
            );

          const isLowest =
            lowestAverageOption
              ?.id ===
            option.id;

          const isMostEfficient =
            lowestCostPerKmOption
              ?.id ===
            option.id;

          return `
            <div
              class="
                ride-provider-card
                ${
                  isLowest
                    ? "provider-winner"
                    : ""
                }
              "
            >

              <div class="provider-card-head">

                <strong>
                  ${escapeHTML(
                    option.label
                  )}
                </strong>

                ${
                  isLowest
                    ? `
                      <span class="winner-badge">
                        Lowest historical average
                      </span>
                    `
                    : ""
                }

              </div>

              <div class="provider-main-value">
                ${money(
                  stats.average
                )}
              </div>

              <div class="muted">
                Average fare
                ·
                ${stats.count}
                trip${
                  stats.count === 1
                    ? ""
                    : "s"
                }
              </div>

              <div class="provider-detail-grid">

                <div>
                  <span>
                    Median
                  </span>

                  <strong>
                    ${money(
                      stats.median
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    Typical range
                  </span>

                  <strong>
                    ${money(
                      stats.p25
                    )}
                    –
                    ${money(
                      stats.p75
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    Average cost/km
                  </span>

                  <strong>
                    ${formatCostPerKm(
                      option
                        .costPerKm
                        ?.average
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    Median cost/km
                  </span>

                  <strong>
                    ${formatCostPerKm(
                      option
                        .costPerKm
                        ?.median
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    Lowest recorded
                  </span>

                  <strong>
                    ${money(
                      stats.min
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    Data confidence
                  </span>

                  <strong>
                    ${optionConfidence.text}
                  </strong>
                </div>

              </div>

              ${
                isMostEfficient
                  ? `
                    <div
                      class="muted"
                      style="margin-top:12px;"
                    >
                      <strong>
                        Lowest historical S$/km
                      </strong>
                      among reliable options.
                    </div>
                  `
                  : ""
              }

            </div>
          `;
        }
      )
      .join("");

  const optionTimingCards =
    bookingOptions
      .map(
        (option) => {

          const insight =
            timingInsightForHourly(
              option.hourly
            );

          if (
            !insight.best
            &&
            !insight.worst
          ) {
            return "";
          }

          const gap =
            insight.best
            &&
            insight.worst
              ? Number(
                  insight
                    .worst
                    .stats
                    .average
                )
                -
                Number(
                  insight
                    .best
                    .stats
                    .average
                )
              : null;

          return `
            <div class="ride-provider-card">

              <div class="provider-card-head">
                <strong>
                  ${escapeHTML(
                    option.label
                  )}
                </strong>
              </div>

              <div class="provider-main-value">
                ${
                  insight.best
                    ? insight
                        .best
                        .label
                    : "Limited data"
                }
              </div>

              <div class="muted">
                Best reliable hour
              </div>

              <div class="provider-detail-grid">

                <div>
                  <span>
                    Best average
                  </span>

                  <strong>
                    ${
                      insight.best
                        ? money(
                            insight
                              .best
                              .stats
                              .average
                          )
                        : "—"
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    Highest-cost hour
                  </span>

                  <strong>
                    ${
                      insight.worst
                        ? insight
                            .worst
                            .label
                        : "—"
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    High-hour average
                  </span>

                  <strong>
                    ${
                      insight.worst
                        ? money(
                            insight
                              .worst
                              .stats
                              .average
                          )
                        : "—"
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    Timing difference
                  </span>

                  <strong>
                    ${
                      gap != null
                        ? money(
                            gap
                          )
                        : "—"
                    }
                  </strong>
                </div>

              </div>

            </div>
          `;
        }
      )
      .join("");

  const allOptionHours =
    Array.from(
      new Set(
        bookingOptions
          .flatMap(
            (option) =>
              Object.keys(
                option.hourly ||
                {}
              )
          )
      )
    )
      .sort(
        (
          a,
          b
        ) =>
          Number(a)
          -
          Number(b)
      );

  const optionTimingTable =
    allOptionHours.length
      ? `
        <div
          class="table-wrap"
          style="margin-top:20px;"
        >

          <table>

            <thead>
              <tr>
                <th>
                  Hour
                </th>

                ${bookingOptions
                  .map(
                    (option) =>
                      `<th>${escapeHTML(
                        option.label
                      )}</th>`
                  )
                  .join("")}
              </tr>
            </thead>

            <tbody>

              ${allOptionHours
                .map(
                  (hour) => `
                    <tr>

                      <td>
                        <strong>
                          ${formatHour(
                            hour
                          )}
                        </strong>
                      </td>

                      ${bookingOptions
                        .map(
                          (option) =>
                            `<td>${formatOptionCell(
                              option
                                .hourly
                                ?.[hour]
                            )}</td>`
                        )
                        .join("")}

                    </tr>
                  `
                )
                .join("")}

            </tbody>

          </table>

        </div>
      `
      : "";

  const hourlyEntries =
    Object.entries(
      route.hourly ||
      {}
    )
      .sort(
        (
          [a],
          [b]
        ) =>
          Number(a)
          -
          Number(b)
      );

  const maxHourlyAverage =
    Math.max(
      ...hourlyEntries
        .map(
          (
            [
              ,
              stats
            ]
          ) =>
            Number(
              stats.average ||
              0
            )
        ),
      1
    );

  const weekdayOrder = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday"
  ];

  const weekdayEntries =
    weekdayOrder
      .filter(
        (day) =>
          route
            .weekdays
            ?.[day]
      )
      .map(
        (day) => [
          day,
          route
            .weekdays[
              day
            ]
        ]
      );

  const maxWeekdayAverage =
    Math.max(
      ...weekdayEntries
        .map(
          (
            [
              ,
              stats
            ]
          ) =>
            Number(
              stats.average ||
              0
            )
        ),
      1
    );

  const cheapestWeekday =
    cheapestEntry(
      route.weekdays,
      minimumSample
    );

  const expensiveWeekday =
    mostExpensiveEntry(
      route.weekdays,
      minimumSample
    );

  const optionSummaryBanner =
    lowestAverageOption
      ? `
        <div class="recommendation-good">

          Among booking options with at least

          ${minimumSample}

          historical trips,

          <strong>
            ${escapeHTML(
              lowestAverageOption.label
            )}
          </strong>

          has the lowest historical average
          on this route at

          <strong>
            ${money(
              lowestAverageOption
                .stats
                .average
            )}
          </strong>.

          ${
            route
              .grab_pricing_types
              ?.Metered
              ? `
                Metered trips are final fares
                you paid and may be selected
                more often when fixed-price
                quotes are already high, so
                treat this as behavioural
                context rather than a perfect
                like-for-like comparison.
              `
              : ""
          }

        </div>
      `
      : `
        <div class="recommendation-neutral">

          There is not enough service-level
          history on this route for a reliable
          comparison between booking options.

        </div>
      `;

  const efficiencySummaryBanner =
    lowestCostPerKmOption
    &&
    distanceKm
      ? `
        <div class="recommendation-neutral">

          Based on the

          <strong>
            ${formatDistance(
              distanceKm
            )}
          </strong>

          driving distance,

          <strong>
            ${escapeHTML(
              lowestCostPerKmOption.label
            )}
          </strong>

          has the lowest historical average
          cost per kilometre at

          <strong>
            ${formatCostPerKm(
              lowestCostPerKmOption
                .costPerKm
                .average
            )}
          </strong>.

          Cost per kilometre is an additional
          comparison signal; short trips,
          tolls, waiting time and surge pricing
          can make comparisons less direct.

        </div>
      `
      : "";

  const detail =
    document.querySelector(
      "#routeDetail"
    );

  if (!detail) {
    return;
  }

  detail.innerHTML = `

    <div class="rides-global-summary">

      <div class="ride-summary-box">
        <span>
          Historical rides
        </span>

        <strong>
          ${DATA.summary.ride_transactions}
        </strong>
      </div>

      <div class="ride-summary-box">
        <span>
          Ride spend
        </span>

        <strong>
          ${money(
            DATA.summary.ride_spend_sgd
          )}
        </strong>
      </div>

      <div class="ride-summary-box">
        <span>
          Routes tracked
        </span>

        <strong>
          ${DATA.routes.length}
        </strong>
      </div>

      <div class="ride-summary-box">
        <span>
          Selected route
        </span>

        <strong>
          ${route.overall.count}
          trips
        </strong>
      </div>

    </div>


    <div class="ride-section">

      <div class="ride-section-title">

        <div>
          <h3>
            Most frequent routes
          </h3>

          <p>
            Your most common journeys
            in the historical dataset.
          </p>
        </div>

      </div>

      <div class="route-ranking">

        ${topRoutes
          .map(
            (
              item,
              index
            ) => {

              const comparison =
                item
                  .provider_comparison;

              const distance =
                routeDistanceKm(
                  item
                );

              return `
                <button

                  class="
                    route-rank-row

                    ${
                      String(
                        item.key
                      ).trim()
                      ===
                      cleanKey
                        ? "active-route"
                        : ""
                    }
                  "

                  data-route-key="${escapeHTML(
                    String(
                      item.key
                    ).trim()
                  )}"

                >

                  <span class="rank-number">
                    ${index + 1}
                  </span>

                  <span class="rank-route">

                    <strong>
                      ${routeName(
                        item
                      )}
                    </strong>

                    <small>

                      ${
                        item
                          .overall
                          .count
                      }

                      trips
                      · median

                      ${money(
                        item
                          .overall
                          .median
                      )}

                      ${
                        distance
                          ? `
                            ·
                            ${formatDistance(
                              distance
                            )}
                          `
                          : ""
                      }

                    </small>

                  </span>

                  <span class="rank-edge">

                    ${
                      comparison
                        ? `
                          ${comparison.cheaper}
                          saves
                          ${money(
                            comparison
                              .average_saving
                          )}
                        `
                        : "Limited comparison"
                    }

                  </span>

                </button>
              `;

            }
          )
          .join("")}

      </div>

    </div>


    <div class="selected-route-header">

      <div>

        <div class="route-eyebrow">
          SELECTED ROUTE
        </div>

        <h2>
          ${routeName(
            route
          )}
        </h2>

        <div
          class="
            confidence-badge
            ${confidence.className}
          "
        >

          ${confidence.text}
          ·
          ${route.overall.count}
          trips

        </div>

      </div>

      <div class="route-median-big">

        <span>
          Historical median
        </span>

        <strong>
          ${money(
            route.overall.median
          )}
        </strong>

      </div>

    </div>


    <div class="route-kpis enhanced-route-kpis">

      <div class="mini">
        <span>
          Average fare
        </span>

        <strong>
          ${money(
            route.overall.average
          )}
        </strong>
      </div>

      <div class="mini">
        <span>
          Driving distance
        </span>

        <strong>
          ${formatDistance(
            distanceKm
          )}
        </strong>
      </div>

      <div class="mini">
        <span>
          Average cost/km
        </span>

        <strong>
          ${formatCostPerKm(
            overallCostPerKm
              ?.average
          )}
        </strong>
      </div>

      <div class="mini">
        <span>
          Typical fare range
        </span>

        <strong>
          ${money(
            route.overall.p25
          )}
          –
          ${money(
            route.overall.p75
          )}
        </strong>
      </div>

      <div class="mini">
        <span>
          Cheapest recorded
        </span>

        <strong>
          ${money(
            route.overall.min
          )}
        </strong>
      </div>

      <div class="mini">
        <span>
          Highest recorded
        </span>

        <strong>
          ${money(
            route.overall.max
          )}
        </strong>
      </div>

    </div>


    <div class="ride-section">

      <div class="ride-section-title">

        <div>

          <h3>
            Booking option comparison
          </h3>

          <p>
            Grab is separated into fixed,
            metered and premium pricing
            where those services exist in
            your history.
          </p>

        </div>

      </div>

      <div class="route-intelligence-banner">
        ${optionSummaryBanner}
      </div>

      ${
        efficiencySummaryBanner
          ? `
            <div class="route-intelligence-banner">
              ${efficiencySummaryBanner}
            </div>
          `
          : ""
      }

      <div class="ride-provider-grid">
        ${optionCards}
      </div>

    </div>


    <div class="ride-section">

      <div class="ride-section-title">

        <div>

          <h3>
            Hourly timing intelligence
          </h3>

          <p>
            An hour needs at least
            ${minimumSample}
            historical trips before it is
            treated as a reliable timing
            pattern.
          </p>

        </div>

      </div>

      <div class="pattern-insights">

        <div
          class="
            pattern-callout
            best-pattern
          "
        >

          <span>
            Best reliable hour
          </span>

          <strong>
            ${
              bestHour
                ? bestHour.label
                : "Not enough data"
            }
          </strong>

          ${
            bestHour
              ? `
                <small>

                  Average

                  ${money(
                    bestHour
                      .stats
                      .average
                  )}

                  ·

                  ${
                    bestHour
                      .stats
                      .count
                  }

                  trips

                </small>
              `
              : ""
          }

        </div>

        <div
          class="
            pattern-callout
            expensive-pattern
          "
        >

          <span>
            Highest-cost reliable hour
          </span>

          <strong>
            ${
              worstHour
                ? worstHour.label
                : "Not enough data"
            }
          </strong>

          ${
            worstHour
              ? `
                <small>

                  Average

                  ${money(
                    worstHour
                      .stats
                      .average
                  )}

                  ·

                  ${
                    worstHour
                      .stats
                      .count
                  }

                  trips

                </small>
              `
              : ""
          }

        </div>

      </div>

      ${
        timingDifference != null
          ? `
            <div class="route-intelligence-banner">

              <div class="recommendation-neutral">

                The highest-cost reliable hour
                has averaged

                <strong>
                  ${money(
                    timingDifference
                  )}
                </strong>

                more than the best reliable hour

                ${
                  timingDifferencePercent != null
                    ? `
                      — about

                      <strong>
                        ${timingDifferencePercent.toFixed(
                          0
                        )}%
                      </strong>

                      higher.
                    `
                    : "."
                }

              </div>

            </div>
          `
          : ""
      }

      <div
        class="pattern-list"
        style="margin-top:20px;"
      >

        ${hourlyEntries
          .map(
            (
              [
                hour,
                stats
              ]
            ) => {

              const width =
                (
                  Number(
                    stats.average
                  )
                  /
                  maxHourlyAverage
                )
                *
                100;

              const reliable =
                Number(
                  stats.count
                )
                >=
                minimumSample;

              return `
                <div
                  class="pattern-row"
                  style="opacity:${
                    reliable
                      ? 1
                      : 0.48
                  };"
                >

                  <div class="pattern-name">

                    <strong>
                      ${formatHour(
                        hour
                      )}
                    </strong>

                    <small>

                      ${stats.count}
                      trips

                      ${
                        reliable
                          ? ""
                          : " · low sample"
                      }

                    </small>

                  </div>

                  <div class="pattern-bar-track">

                    <div
                      class="pattern-bar-fill"
                      style="width:${width}%;"
                    ></div>

                  </div>

                  <div class="pattern-price">
                    ${money(
                      stats.average
                    )}
                  </div>

                </div>
              `;

            }
          )
          .join("")}

      </div>

    </div>


    ${
      bookingOptions.length
        ? `
          <div class="ride-section">

            <div class="ride-section-title">

              <div>

                <h3>
                  Timing by booking option
                </h3>

                <p>
                  This separates Grab fixed and
                  metered timing instead of
                  blending all Grab rides together.
                </p>

              </div>

            </div>

            ${
              optionTimingCards
                ? `
                  <div class="ride-provider-grid">
                    ${optionTimingCards}
                  </div>
                `
                : `
                  <div class="recommendation-neutral">

                    No booking option currently has
                    at least

                    ${minimumSample}

                    trips within the same hour.

                  </div>
                `
            }

            ${optionTimingTable}

          </div>
        `
        : ""
    }


    ${
      weekdayEntries.length
        ? `
          <div class="ride-section">

            <div class="ride-section-title">

              <div>

                <h3>
                  Day-of-week patterns
                </h3>

                <p>
                  Weekday differences are shown
                  alongside the stronger hourly
                  timing patterns.
                </p>

              </div>

            </div>

            <div class="pattern-insights">

              <div
                class="
                  pattern-callout
                  best-pattern
                "
              >

                <span>
                  Lowest reliable weekday
                </span>

                <strong>
                  ${
                    cheapestWeekday
                      ? cheapestWeekday[0]
                      : "Not enough data"
                  }
                </strong>

                ${
                  cheapestWeekday
                    ? `
                      <small>

                        Average

                        ${money(
                          cheapestWeekday[
                            1
                          ].average
                        )}

                        ·

                        ${
                          cheapestWeekday[
                            1
                          ].count
                        }

                        trips

                      </small>
                    `
                    : ""
                }

              </div>

              <div
                class="
                  pattern-callout
                  expensive-pattern
                "
              >

                <span>
                  Highest reliable weekday
                </span>

                <strong>
                  ${
                    expensiveWeekday
                      ? expensiveWeekday[0]
                      : "Not enough data"
                  }
                </strong>

                ${
                  expensiveWeekday
                    ? `
                      <small>

                        Average

                        ${money(
                          expensiveWeekday[
                            1
                          ].average
                        )}

                        ·

                        ${
                          expensiveWeekday[
                            1
                          ].count
                        }

                        trips

                      </small>
                    `
                    : ""
                }

              </div>

            </div>

            <div class="pattern-list">

              ${weekdayEntries
                .map(
                  (
                    [
                      day,
                      stats
                    ]
                  ) => {

                    const width =
                      (
                        Number(
                          stats.average
                        )
                        /
                        maxWeekdayAverage
                      )
                      *
                      100;

                    return `
                      <div class="pattern-row">

                        <div class="pattern-name">

                          <strong>
                            ${day}
                          </strong>

                          <small>
                            ${stats.count}
                            trips
                          </small>

                        </div>

                        <div class="pattern-bar-track">

                          <div
                            class="pattern-bar-fill"
                            style="width:${width}%;"
                          ></div>

                        </div>

                        <div class="pattern-price">
                          ${money(
                            stats.average
                          )}
                        </div>

                      </div>
                    `;

                  }
                )
                .join("")}

            </div>

          </div>
        `
        : ""
    }


    <div class="ride-section">

      <div class="ride-section-title">

        <div>

          <h3>
            Provider totals
          </h3>

          <p>
            Original Grab-versus-Gojek
            view. Grab here combines all
            Grab booking types.
          </p>

        </div>

      </div>

      <div class="table-wrap">

        <table>

          <thead>

            <tr>
              <th>
                Provider
              </th>

              <th>
                Trips
              </th>

              <th>
                Average
              </th>

              <th>
                Median
              </th>

              <th>
                Typical range
              </th>

              <th>
                Avg S$/km
              </th>

              <th>
                Median S$/km
              </th>

              <th>
                Recorded range
              </th>
            </tr>

          </thead>

          <tbody>

            ${Object.entries(
              route.providers ||
              {}
            )
              .map(
                (
                  [
                    provider,
                    stats
                  ]
                ) => `
                  <tr>

                    <td>
                      <strong>
                        ${provider}
                      </strong>
                    </td>

                    <td>
                      ${stats.count}
                    </td>

                    <td>
                      ${money(
                        stats.average
                      )}
                    </td>

                    <td>
                      ${money(
                        stats.median
                      )}
                    </td>

                    <td>
                      ${money(
                        stats.p25
                      )}
                      –
                      ${money(
                        stats.p75
                      )}
                    </td>

                    <td>
                      ${formatCostPerKm(
                        route
                          .cost_per_km
                          ?.providers
                          ?.[provider]
                          ?.average
                      )}
                    </td>

                    <td>
                      ${formatCostPerKm(
                        route
                          .cost_per_km
                          ?.providers
                          ?.[provider]
                          ?.median
                      )}
                    </td>

                    <td>
                      ${money(
                        stats.min
                      )}
                      –
                      ${money(
                        stats.max
                      )}
                    </td>

                  </tr>
                `
              )
              .join("")}

          </tbody>

        </table>

      </div>

    </div>
  `;

  document
    .querySelectorAll(
      ".route-rank-row"
    )
    .forEach(
      (button) => {

        button.addEventListener(
          "click",
          () => {

            const routeKey =
              String(
                button
                  .dataset
                  .routeKey ||
                ""
              ).trim();

            const select =
              document.querySelector(
                "#routeSelect"
              );

            if (select) {
              select.value =
                routeKey;
            }

            showRoute(
              routeKey
            );

          }
        );

      }
    );
}

/* =========================================================
   TABS
========================================================= */
function wireTabs() {
  const tabs =
    document.querySelectorAll(
      ".tab"
    );

  const panels =
    document.querySelectorAll(
      ".panel"
    );

  tabs.forEach(
    (button) => {

      button.addEventListener(
        "click",
        () => {

          tabs.forEach(
            (tab) =>
              tab
                .classList
                .remove(
                  "active"
                )
          );

          panels.forEach(
            (panel) =>
              panel
                .classList
                .remove(
                  "active"
                )
          );

          button
            .classList
            .add(
              "active"
            );

          document
            .querySelector(
              `#${
                button
                  .dataset
                  .tab
              }`
            )
            ?.classList
            .add(
              "active"
            );

          window.scrollTo(
            {
              top: 0,
              left: 0,
              behavior: "auto"
            }
          );

        }
      );

    }
  );
}

/* =========================================================
   TIMING-AWARE FARE CHECKER
   Distance is displayed on Rides only for now.
========================================================= */
function fareScore(
  amount,
  stats
) {
  if (
    amount <=
    Number(
      stats.p10
    )
  ) {
    return [
      5,
      "Exceptional value"
    ];
  }

  if (
    amount <=
    Number(
      stats.p25
    )
  ) {
    return [
      4,
      "Very good"
    ];
  }

  if (
    amount <=
    Number(
      stats.median
    )
  ) {
    return [
      3,
      "Normal to good"
    ];
  }

  if (
    amount <=
    Number(
      stats.p75
    )
  ) {
    return [
      2,
      "Somewhat expensive"
    ];
  }

  if (
    amount <=
    Number(
      stats.p90
    )
  ) {
    return [
      1,
      "Expensive"
    ];
  }

  return [
    0,
    "Unusually expensive"
  ];
}

function localDateString(
  date = new Date()
) {
  return (
    `${date.getFullYear()}-`
    +
    `${String(
      date.getMonth() + 1
    ).padStart(
      2,
      "0"
    )}-`
    +
    `${String(
      date.getDate()
    ).padStart(
      2,
      "0"
    )}`
  );
}

function localTimeString(
  date = new Date()
) {
  return (
    `${String(
      date.getHours()
    ).padStart(
      2,
      "0"
    )}:`
    +
    `${String(
      date.getMinutes()
    ).padStart(
      2,
      "0"
    )}`
  );
}

function weekdayFromDate(value) {
  if (!value) {
    return null;
  }

  const [
    year,
    month,
    day
  ] =
    value
      .split("-")
      .map(
        Number
      );

  if (
    ![
      year,
      month,
      day
    ]
      .every(
        Number.isFinite
      )
  ) {
    return null;
  }

  return [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday"
  ][
    new Date(
      year,
      month - 1,
      day
    ).getDay()
  ];
}

function copyStats(stats) {
  if (!stats) {
    return null;
  }

  return {
    count:
      Number(
        stats.count ||
        0
      ),

    average:
      Number(
        stats.average ||
        0
      ),

    median:
      Number(
        stats.median ||
        0
      ),

    min:
      Number(
        stats.min ||
        0
      ),

    max:
      Number(
        stats.max ||
        0
      ),

    p10:
      Number(
        stats.p10
        ??
        stats.min
        ??
        0
      ),

    p25:
      Number(
        stats.p25
        ??
        stats.median
        ??
        0
      ),

    p75:
      Number(
        stats.p75
        ??
        stats.median
        ??
        0
      ),

    p90:
      Number(
        stats.p90
        ??
        stats.max
        ??
        0
      )
  };
}

function scaleStats(
  stats,
  factor
) {
  const out =
    copyStats(
      stats
    );

  if (!out) {
    return null;
  }

  const safe =
    Math.max(
      0.85,
      Math.min(
        1.15,
        Number(
          factor ||
          1
        )
      )
    );

  [
    "average",
    "median",
    "min",
    "max",
    "p10",
    "p25",
    "p75",
    "p90"
  ]
    .forEach(
      (key) => {

        out[key] =
          Number(
            (
              out[key]
              *
              safe
            ).toFixed(
              2
            )
          );

      }
    );

  return out;
}

const reliableStats =
  (stats) =>
    Boolean(
      stats
      &&
      Number(
        stats.count ||
        0
      )
      >=
      minimumTimingSample()
    );

function getFareContext() {
  const dateValue =
    document.querySelector(
      "#fareDate"
    )
      ?.value;

  const timeValue =
    document.querySelector(
      "#fareTime"
    )
      ?.value;

  const hour =
    timeValue
      ? String(
          Number(
            timeValue
              .split(
                ":"
              )[0]
          )
        )
          .padStart(
            2,
            "0"
          )
      : null;

  return {
    dateValue,
    timeValue,
    hour,

    weekday:
      weekdayFromDate(
        dateValue
      )
  };
}

function getWeekdayStats(
  route,
  provider,
  weekday
) {
  if (!weekday) {
    return null;
  }

  if (
    provider !==
    "Overall"
  ) {

    const providerDay =
      route
        .provider_weekdays
        ?.[provider]
        ?.[weekday];

    if (
      reliableStats(
        providerDay
      )
    ) {

      return {
        stats:
          providerDay,

        source:
          `${provider} + ${weekday}`,

        baseAverage:
          Number(
            route
              .providers
              ?.[provider]
              ?.average
            ||
            0
          )
      };

    }

  }

  const routeDay =
    route
      .weekdays
      ?.[weekday];

  if (
    reliableStats(
      routeDay
    )
  ) {

    return {
      stats:
        routeDay,

      source:
        `All providers + ${weekday}`,

      baseAverage:
        Number(
          route
            .overall
            ?.average
          ||
          0
        )
    };

  }

  return null;
}

function selectFareBenchmark(
  route,
  provider,
  hour,
  weekday
) {
  const minimum =
    minimumTimingSample();

  let timingStats =
    null;

  let source =
    null;

  let level =
    null;

  if (
    provider !==
    "Overall"
    &&
    hour
  ) {

    const providerHour =
      route
        .provider_hourly
        ?.[provider]
        ?.[hour];

    if (
      Number(
        providerHour
          ?.count ||
        0
      )
      >=
      minimum
    ) {

      timingStats =
        providerHour;

      source =
        `${provider} · ${formatHour(
          hour
        )}`;

      level =
        "provider-hour";

    }

  }

  if (
    !timingStats
    &&
    hour
  ) {

    const routeHour =
      route
        .hourly
        ?.[hour];

    if (
      Number(
        routeHour
          ?.count ||
        0
      )
      >=
      minimum
    ) {

      timingStats =
        routeHour;

      source =
        `All providers · ${formatHour(
          hour
        )}`;

      level =
        "route-hour";

    }

  }

  const weekdayContext =
    getWeekdayStats(
      route,
      provider,
      weekday
    );

  if (
    timingStats
  ) {

    let stats =
      copyStats(
        timingStats
      );

    let weekdayAdjustment =
      null;

    if (
      weekdayContext
        ?.baseAverage > 0
    ) {

      const factor =
        Math.max(
          0.85,
          Math.min(
            1.15,
            Number(
              weekdayContext
                .stats
                .average
            )
            /
            weekdayContext
              .baseAverage
          )
        );

      stats =
        scaleStats(
          stats,
          factor
        );

      weekdayAdjustment = {
        factor,

        source:
          weekdayContext
            .source,

        count:
          weekdayContext
            .stats
            .count
      };

    }

    return {
      stats,
      source,
      level,

      sampleCount:
        Number(
          timingStats.count ||
          0
        ),

      weekdayAdjustment
    };

  }

  if (
    weekdayContext
  ) {

    return {
      stats:
        copyStats(
          weekdayContext.stats
        ),

      source:
        weekdayContext.source,

      level:
        provider !==
        "Overall"
          ? "provider-weekday"
          : "route-weekday",

      sampleCount:
        Number(
          weekdayContext
            .stats
            .count ||
          0
        ),

      weekdayAdjustment:
        null
    };

  }

  if (
    provider !==
    "Overall"
    &&
    route
      .providers
      ?.[provider]
  ) {

    return {
      stats:
        copyStats(
          route
            .providers[
              provider
            ]
        ),

      source:
        `${provider} · route overall`,

      level:
        "provider-route",

      sampleCount:
        Number(
          route
            .providers[
              provider
            ]
            .count ||
          0
        ),

      weekdayAdjustment:
        null
    };

  }

  return {
    stats:
      copyStats(
        route.overall
      ),

    source:
      "Route overall",

    level:
      "route-overall",

    sampleCount:
      Number(
        route
          .overall
          ?.count ||
        0
      ),

    weekdayAdjustment:
      null
  };
}

function providerContextEstimate(
  route,
  provider,
  hour,
  weekday
) {
  if (
    !provider
    ||
    provider ===
    "Overall"
  ) {
    return null;
  }

  const minimum =
    minimumTimingSample();

  const providerHour =
    hour
      ? route
          .provider_hourly
          ?.[provider]
          ?.[hour]
      : null;

  if (
    Number(
      providerHour
        ?.count ||
      0
    )
    >=
    minimum
  ) {

    let stats =
      copyStats(
        providerHour
      );

    const providerDay =
      weekday
        ? route
            .provider_weekdays
            ?.[provider]
            ?.[weekday]
        : null;

    const providerOverall =
      route
        .providers
        ?.[provider];

    if (
      reliableStats(
        providerDay
      )
      &&
      Number(
        providerOverall
          ?.average ||
        0
      ) > 0
    ) {

      stats =
        scaleStats(
          stats,
          Number(
            providerDay
              .average
          )
          /
          Number(
            providerOverall
              .average
          )
        );

    }

    return {
      stats,

      source:
        `${provider} · ${formatHour(
          hour
        )}`
    };

  }

  const providerDay =
    weekday
      ? route
          .provider_weekdays
          ?.[provider]
          ?.[weekday]
      : null;

  if (
    reliableStats(
      providerDay
    )
  ) {

    return {
      stats:
        copyStats(
          providerDay
        ),

      source:
        `${provider} · ${weekday}`
    };

  }

  const overall =
    route
      .providers
      ?.[provider];

  return overall
    ? {
        stats:
          copyStats(
            overall
          ),

        source:
          `${provider} · route overall`
      }
    : null;
}

function ensureFareContextControls() {
  const grid =
    document.querySelector(
      "#fare .form-grid"
    );

  const button =
    document.querySelector(
      "#checkFare"
    );

  if (
    !grid
    ||
    !button
    ||
    document.querySelector(
      "#fareDate"
    )
  ) {
    return;
  }

  const now =
    new Date();

  const dateLabel =
    document.createElement(
      "label"
    );

  dateLabel.innerHTML = `
    Journey date

    <input
      id="fareDate"
      type="date"
      value="${localDateString(
        now
      )}"
    >
  `;

  const timeLabel =
    document.createElement(
      "label"
    );

  timeLabel.innerHTML = `
    Journey time

    <input
      id="fareTime"
      type="time"
      value="${localTimeString(
        now
      )}"
    >
  `;

  grid.insertBefore(
    dateLabel,
    button
  );

  grid.insertBefore(
    timeLabel,
    button
  );

  grid
    .classList
    .add(
      "fare-context-grid"
    );

  if (
    !document.querySelector(
      "#fareTimingStyles"
    )
  ) {

    const style =
      document.createElement(
        "style"
      );

    style.id =
      "fareTimingStyles";

    style.textContent = `

      .form-grid.fare-context-grid {
        grid-template-columns:
          minmax(210px,2fr)
          minmax(120px,1fr)
          minmax(125px,1fr)
          minmax(145px,1fr)
          minmax(120px,1fr)
          auto;
      }

      .fare-result-grid {
        display:grid;
        grid-template-columns:
          minmax(150px,.7fr)
          minmax(0,2fr);
        gap:18px;
        align-items:center;
      }

      .fare-result-details {
        display:grid;
        gap:8px;
      }

      .fare-reference {
        padding:11px 13px;
        border:1px solid var(--line);
        border-radius:10px;
        background:#091827;
      }

      .fare-reference strong {
        display:block;
        margin-top:2px;
      }

      .fare-recommendation {
        margin-top:14px;
        padding:13px 15px;
        border-radius:11px;
        background:#0a1c2c;
        border:1px solid var(--line);
      }

      @media(max-width:1100px) {

        .form-grid.fare-context-grid {
          grid-template-columns:
            1fr 1fr 1fr;
        }

      }

      @media(max-width:700px) {

        .form-grid.fare-context-grid,
        .fare-result-grid {
          grid-template-columns:
            1fr;
        }

      }

    `;

    document.head
      .appendChild(
        style
      );
  }
}

function checkFare() {
  const routeKey =
    String(
      document.querySelector(
        "#fareRoute"
      )
        ?.value ||
      ""
    ).trim();

  const provider =
    document.querySelector(
      "#fareProvider"
    )
      ?.value
    ||
    "Overall";

  const amount =
    Number(
      document.querySelector(
        "#fareAmount"
      )
        ?.value
    );

  const resultBox =
    document.querySelector(
      "#fareResult"
    );

  const route =
    (
      DATA.routes ||
      []
    )
      .find(
        (item) =>
          String(
            item.key ||
            ""
          ).trim()
          ===
          routeKey
      );

  if (
    !route
    ||
    !resultBox
    ||
    !Number.isFinite(
      amount
    )
    ||
    amount <= 0
  ) {

    if (resultBox) {
      resultBox.innerHTML =
        "Enter a valid fare amount.";
    }

    return;
  }

  const context =
    getFareContext();

  const benchmark =
    selectFareBenchmark(
      route,
      provider,
      context.hour,
      context.weekday
    );

  if (
    !benchmark
      ?.stats
  ) {

    resultBox.innerHTML =
      "Not enough historical data for that route and context.";

    return;
  }

  const stats =
    benchmark.stats;

  const [
    score,
    description
  ] =
    fareScore(
      amount,
      stats
    );

  const difference =
    amount
    -
    Number(
      stats.median
    );

  const differenceText =
    difference >= 0
      ? `${money(
          difference
        )} above median`
      : `${money(
          Math.abs(
            difference
          )
        )} below median`;

  let weekdayNote =
    "";

  if (
    benchmark
      .weekdayAdjustment
  ) {

    const percent =
      (
        benchmark
          .weekdayAdjustment
          .factor
        -
        1
      )
      *
      100;

    weekdayNote = `
      <div class="fare-reference">

        <span class="muted">
          Weekday adjustment
        </span>

        <strong>
          ${context.weekday}
          historical pattern:

          ${
            percent >= 0
              ? "+"
              : ""
          }

          ${percent.toFixed(
            0
          )}%
        </strong>

      </div>
    `;
  }

  let providerAdvice =
    "";

  if (
    provider ===
    "Grab"
    ||
    provider ===
    "Gojek"
  ) {

    const other =
      provider ===
      "Grab"
        ? "Gojek"
        : "Grab";

    const estimate =
      providerContextEstimate(
        route,
        other,
        context.hour,
        context.weekday
      );

    if (
      estimate
        ?.stats
    ) {

      const otherMedian =
        Number(
          estimate
            .stats
            .median
        );

      const saving =
        amount
        -
        otherMedian;

      providerAdvice =
        saving > 1
          ? `
            <div class="fare-recommendation">

              <strong>
                Check
                ${other}
                before booking.
              </strong>

              Your historical
              ${other}
              benchmark for this
              context is about

              <strong>
                ${money(
                  otherMedian
                )}
              </strong>,

              roughly

              <strong>
                ${money(
                  saving
                )}
              </strong>

              below this quote.

            </div>
          `
          : `
            <div class="fare-recommendation">

              The alternative provider
              does not show a meaningful
              historical saving for this
              context.

            </div>
          `;
    }

  }
  else if (
    route
      .provider_comparison
  ) {

    providerAdvice = `
      <div class="fare-recommendation">

        Historically,

        <strong>
          ${
            route
              .provider_comparison
              .cheaper
          }
        </strong>

        has averaged

        <strong>
          ${money(
            route
              .provider_comparison
              .average_saving
          )}
        </strong>

        less per trip on this
        route overall.

      </div>
    `;
  }

  resultBox.innerHTML = `

    <div class="fare-result-grid">

      <div>

        <div class="score">
          ${score}

          <small>
            /5
          </small>
        </div>

        <strong>
          ${description}
        </strong>

      </div>

      <div class="fare-result-details">

        <div class="fare-reference">

          <span class="muted">
            Quote
          </span>

          <strong>
            ${money(
              amount
            )}
          </strong>

        </div>

        <div class="fare-reference">

          <span class="muted">
            Expected range
            for this context
          </span>

          <strong>
            ${money(
              stats.p25
            )}
            –
            ${money(
              stats.p75
            )}
          </strong>

        </div>

        <div class="fare-reference">

          <span class="muted">
            Context median
          </span>

          <strong>
            ${money(
              stats.median
            )}
            ·
            ${differenceText}
          </strong>

        </div>

        <div class="fare-reference">

          <span class="muted">
            Benchmark used
          </span>

          <strong>
            ${benchmark.source}
            ·
            ${benchmark.sampleCount}
            historical trips
          </strong>

        </div>

        ${weekdayNote}

      </div>

    </div>

    ${providerAdvice}
  `;
}

function wireFareChecker() {
  ensureFareContextControls();

  document
    .querySelector(
      "#checkFare"
    )
    ?.addEventListener(
      "click",
      checkFare
    );

  document
    .querySelector(
      "#fareAmount"
    )
    ?.addEventListener(
      "keydown",
      (event) => {

        if (
          event.key ===
          "Enter"
        ) {
          checkFare();
        }

      }
    );
}

/* =========================================================
   FOOD
========================================================= */
function renderFood() {
  const food =
    DATA.food;

  const summary =
    document.querySelector(
      "#foodSummary"
    );

  const topFood =
    document.querySelector(
      "#topFood"
    );

  if (summary) {

    summary.innerHTML = `

      <div class="metric">

        <div class="label">
          Orders
        </div>

        <div class="value">
          ${food.order_count}
        </div>

      </div>

      <div
        class="metric"
        style="margin-top:20px;"
      >

        <div class="label">
          Total spend
        </div>

        <div class="value">
          ${money(
            food.total_spend_sgd
          )}
        </div>

      </div>
    `;
  }

  if (topFood) {

    topFood.innerHTML =
      (
        food
          .top_restaurants
        ||
        []
      )
        .slice(
          0,
          8
        )
        .map(
          (
            restaurant,
            index
          ) => `

            <div class="food-row">

              <div>

                <strong>
                  ${index + 1}.
                  ${label(
                    restaurant
                      .restaurant
                  )}
                </strong>

                <div class="muted">
                  ${restaurant.count}
                  orders
                  · avg
                  ${money(
                    restaurant
                      .average_order
                  )}
                </div>

              </div>

              <strong>
                ${money(
                  restaurant
                    .total_spend
                )}
              </strong>

            </div>
          `
        )
        .join("");
  }
}

/* =========================================================
   ASK MY DATA
========================================================= */
function answer(question) {
  const q =
    String(
      question ||
      ""
    )
      .toLowerCase()
      .trim();

  const homeOffice =
    (
      DATA.routes ||
      []
    )
      .find(
        (route) =>
          String(
            route.key ||
            ""
          ).trim()
          ===
          "HOME__OFFICE"
      );

  if (!q) {
    return (
      "Ask a question about " +
      "your rides, spending, " +
      "providers or food orders."
    );
  }

  if (
    q.includes(
      "food"
    )
    ||
    q.includes(
      "restaurant"
    )
  ) {

    const top =
      DATA
        .food
        .top_restaurants
        ?.[0];

    if (!top) {
      return (
        "No food-order data " +
        "is currently available."
      );
    }

    return `
      Your most frequently ordered
      restaurant is

      <strong>
        ${label(
          top.restaurant
        )}
      </strong>,

      with

      <strong>
        ${top.count}
        orders
      </strong>

      and

      <strong>
        ${money(
          top.total_spend
        )}
      </strong>

      total spend.
    `;
  }

  if (
    q.includes(
      "ride"
    )
    &&
    q.includes(
      "spend"
    )
  ) {

    return `
      Your recorded ride spend is

      <strong>
        ${money(
          DATA
            .summary
            .ride_spend_sgd
        )}
      </strong>

      across

      <strong>
        ${
          DATA
            .summary
            .ride_transactions
        }

        rides
      </strong>.
    `;
  }

  if (
    q.includes(
      "spend"
    )
  ) {

    return `
      Recorded SGD spend is

      <strong>
        ${money(
          DATA
            .summary
            .total_spend_sgd
        )}
      </strong>.

      This includes

      <strong>
        ${money(
          DATA
            .summary
            .ride_spend_sgd
        )}
      </strong>

      on rides and

      <strong>
        ${money(
          DATA
            .summary
            .food_spend_sgd
        )}
      </strong>

      on GrabFood.
    `;
  }

  if (
    q.includes(
      "cheaper"
    )
    &&
    homeOffice
      ?.provider_comparison
  ) {

    const c =
      homeOffice
        .provider_comparison;

    return `
      For Home → Office,

      <strong>
        ${c.cheaper}
      </strong>

      has historically been cheaper
      on average by about

      <strong>
        ${money(
          c.average_saving
        )}
      </strong>

      per trip.
    `;
  }

  if (
    homeOffice
    &&
    (
      (
        q.includes(
          "home"
        )
        &&
        q.includes(
          "office"
        )
      )
      ||
      q.includes(
        "normal fare"
      )
    )
  ) {

    return `
      For Home → Office,
      your historical median is

      <strong>
        ${money(
          homeOffice
            .overall
            .median
        )}
      </strong>.

      The middle 50% of fares
      were between

      <strong>
        ${money(
          homeOffice
            .overall
            .p25
        )}
      </strong>

      and

      <strong>
        ${money(
          homeOffice
            .overall
            .p75
        )}
      </strong>

      across

      <strong>
        ${homeOffice
          .overall
          .count}

        trips
      </strong>.
    `;
  }

  return `
    I can currently answer
    questions about

    <strong>
      spending,
      food orders,
      Home → Office fares
      and provider comparisons
    </strong>.
  `;
}

function askQuestion() {
  const answerBox =
    document.querySelector(
      "#agentAnswer"
    );

  if (answerBox) {
    answerBox.innerHTML =
      answer(
        document.querySelector(
          "#agentQuestion"
        )
          ?.value
      );
  }
}

function wireAgent() {
  document
    .querySelectorAll(
      ".chips button"
    )
    .forEach(
      (button) => {

        button.addEventListener(
          "click",
          () => {

            const question =
              button
                .dataset
                .q;

            const input =
              document.querySelector(
                "#agentQuestion"
              );

            const answerBox =
              document.querySelector(
                "#agentAnswer"
              );

            if (input) {
              input.value =
                question;
            }

            if (answerBox) {
              answerBox.innerHTML =
                answer(
                  question
                );
            }

          }
        );

      }
    );

  document
    .querySelector(
      "#askButton"
    )
    ?.addEventListener(
      "click",
      askQuestion
    );

  document
    .querySelector(
      "#agentQuestion"
    )
    ?.addEventListener(
      "keydown",
      (event) => {

        if (
          event.key ===
          "Enter"
        ) {
          askQuestion();
        }

      }
    );
}

/* =========================================================
   START
========================================================= */
init().catch(
  (error) => {

    console.error(
      "Dashboard error:",
      error
    );

    document.body.innerHTML = `

      <main
        style="
          padding-top:
          40px;
        "
      >

        <article class="card">

          <h2>
            Could not load dashboard
          </h2>

          <p>
            The dashboard encountered
            an error while loading.
          </p>

          <pre
            style="
              white-space:
              pre-wrap;

              overflow:
              auto;
            "
          >${escapeHTML(
            error.message
          )}</pre>

        </article>

      </main>
    `;

  }
);
