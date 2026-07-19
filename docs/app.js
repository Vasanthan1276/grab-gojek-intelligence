let DATA = null;


/* =========================================================
   BASIC HELPERS
========================================================= */

function money(value) {
  return `S$${Number(value || 0).toFixed(2)}`;
}


function label(value) {
  if (!value) return "";

  return String(value)
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}


function routeName(route) {
  return `${label(route.origin)} → ${label(route.destination)}`;
}


function formatMonth(value) {
  if (!value) return "";

  const [year, month] = value.split("-");

  const date = new Date(
    Number(year),
    Number(month) - 1,
    1
  );

  return date.toLocaleDateString("en-SG", {
    month: "short",
    year: "2-digit"
  });
}


function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


/* =========================================================
   DATA HELPERS
========================================================= */

function reliableEntries(object, minimumCount = 3) {
  if (!object) return [];

  return Object.entries(object)
    .filter(
      ([, stats]) =>
        stats &&
        Number(stats.count || 0) >= minimumCount
    );
}


function cheapestEntry(object, minimumCount = 3) {
  const entries =
    reliableEntries(
      object,
      minimumCount
    );

  if (!entries.length) return null;

  return entries.reduce(
    (best, current) =>
      current[1].average <
      best[1].average
        ? current
        : best
  );
}


function mostExpensiveEntry(
  object,
  minimumCount = 3
) {
  const entries =
    reliableEntries(
      object,
      minimumCount
    );

  if (!entries.length) return null;

  return entries.reduce(
    (worst, current) =>
      current[1].average >
      worst[1].average
        ? current
        : worst
  );
}


function confidenceLevel(count) {
  if (count >= 30) {
    return {
      text: "High confidence",
      className: "confidence-high"
    };
  }

  if (count >= 10) {
    return {
      text: "Good confidence",
      className: "confidence-medium"
    };
  }

  if (count >= 5) {
    return {
      text: "Early pattern",
      className: "confidence-low"
    };
  }

  return {
    text: "Limited history",
    className: "confidence-low"
  };
}


/* =========================================================
   INITIALISE DASHBOARD
========================================================= */

async function init() {
  const response = await fetch(
    `data/analytics.json?v=${Date.now()}`,
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error(
      `Unable to load analytics.json. HTTP ${response.status}`
    );
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
   SUMMARY CARDS
========================================================= */

function renderSummary() {
  const summary = DATA.summary;

  const cards = [
    {
      title: "Total spend",
      value: money(
        summary.total_spend_sgd
      ),
      subtitle:
        "SGD across both reports"
    },

    {
      title: "Ride spend",
      value: money(
        summary.ride_spend_sgd
      ),
      subtitle:
        `${summary.ride_transactions} rides`
    },

    {
      title: "Food spend",
      value: money(
        summary.food_spend_sgd
      ),
      subtitle:
        `${summary.food_orders} GrabFood orders`
    },

    {
      title:
        "Average food order",

      value:
        money(
          summary.average_food_order
        ),

      subtitle:
        "Historical average"
    }
  ];


  document.querySelector(
    "#summaryCards"
  ).innerHTML = cards
    .map(
      (card) => `
        <article class="card metric">

          <div class="label">
            ${card.title}
          </div>

          <div class="value">
            ${card.value}
          </div>

          <div class="sub">
            ${card.subtitle}
          </div>

        </article>
      `
    )
    .join("");
}


/* =========================================================
   PROVIDER SNAPSHOT
========================================================= */

function renderProviders() {
  const container =
    document.querySelector(
      "#providerSnapshot"
    );

  if (!container) return;


  container.innerHTML =
    Object.entries(
      DATA.providers
    )
      .map(
        ([provider, values]) => `
          <div class="provider-row">

            <div>

              <strong>
                ${provider}
              </strong>

              <div class="muted">

                ${values.rides}
                rides

                · avg
                ${money(
                  values.average_ride
                )}

              </div>

            </div>


            <strong>
              ${money(
                values.spend_sgd
              )}
            </strong>

          </div>
        `
      )
      .join("");
}


/* =========================================================
   MONTHLY SPEND
   PURE HTML / CSS
========================================================= */

function renderMonthly() {
  const placeholder =
    document.querySelector(
      "#monthlyChart"
    );

  if (!placeholder) return;


  const monthlyData =
    Array.isArray(
      DATA.monthly
    )
      ? DATA.monthly
      : [];


  if (!monthlyData.length) {

    placeholder.innerHTML = `
      <div class="monthly-empty">
        No monthly data available.
      </div>
    `;

    return;
  }


  const totals =
    monthlyData.map(
      (month) => {

        const grab =
          Number(
            month["Grab rides"] ||
            0
          );

        const gojek =
          Number(
            month["Gojek rides"] ||
            0
          );

        const food =
          Number(
            month.GrabFood ||
            0
          );

        return (
          grab +
          gojek +
          food
        );
      }
    );


  const maximum =
    Math.max(
      ...totals,
      1
    );


  placeholder.innerHTML = `

    <div class="monthly-chart">

      <div class="monthly-legend">

        <div class="legend-item">
          <span
            class="
              legend-dot
              legend-grab
            "
          ></span>

          Grab rides
        </div>


        <div class="legend-item">

          <span
            class="
              legend-dot
              legend-gojek
            "
          ></span>

          Gojek rides
        </div>


        <div class="legend-item">

          <span
            class="
              legend-dot
              legend-food
            "
          ></span>

          GrabFood
        </div>

      </div>


      <div class="monthly-bars">

        ${monthlyData
          .map(
            (month) => {

              const grab =
                Number(
                  month[
                    "Grab rides"
                  ] || 0
                );


              const gojek =
                Number(
                  month[
                    "Gojek rides"
                  ] || 0
                );


              const food =
                Number(
                  month.GrabFood ||
                  0
                );


              const total =
                grab +
                gojek +
                food;


              const overallHeight =
                total > 0
                  ? Math.max(
                      (
                        total /
                        maximum
                      ) *
                        100,

                      4
                    )

                  : 0;


              const grabShare =
                total > 0
                  ? (
                      grab /
                      total
                    ) *
                    100
                  : 0;


              const gojekShare =
                total > 0
                  ? (
                      gojek /
                      total
                    ) *
                    100
                  : 0;


              const foodShare =
                total > 0
                  ? (
                      food /
                      total
                    ) *
                    100
                  : 0;


              const tooltip =
                [
                  formatMonth(
                    month.month
                  ),

                  `Total: ${money(
                    total
                  )}`,

                  `Grab rides: ${money(
                    grab
                  )}`,

                  `Gojek rides: ${money(
                    gojek
                  )}`,

                  `GrabFood: ${money(
                    food
                  )}`
                ].join("\n");


              return `

                <div class="month-column">

                  <div class="month-value">
                    ${Math.round(
                      total
                    )}
                  </div>


                  <div class="month-bar-area">

                    <div
                      class="month-stack"

                      style="
                        height:
                        ${overallHeight}%
                      "

                      title="${escapeHTML(
                        tooltip
                      )}"
                    >


                      ${
                        gojek > 0
                          ? `
                            <div
                              class="
                                month-segment
                                segment-gojek
                              "

                              style="
                                height:
                                ${gojekShare}%
                              "
                            ></div>
                          `
                          : ""
                      }


                      ${
                        grab > 0
                          ? `
                            <div
                              class="
                                month-segment
                                segment-grab
                              "

                              style="
                                height:
                                ${grabShare}%
                              "
                            ></div>
                          `
                          : ""
                      }


                      ${
                        food > 0
                          ? `
                            <div
                              class="
                                month-segment
                                segment-food
                              "

                              style="
                                height:
                                ${foodShare}%
                              "
                            ></div>
                          `
                          : ""
                      }


                    </div>

                  </div>


                  <div class="month-label">

                    ${formatMonth(
                      month.month
                    )}

                  </div>

                </div>
              `;
            }
          )
          .join("")}

      </div>

    </div>
  `;
}


/* =========================================================
   CORE ROUTES
========================================================= */

function renderCoreRoutes() {
  const tableBody =
    document.querySelector(
      "#coreRoutes"
    );

  if (!tableBody) return;


  tableBody.innerHTML =
    DATA.core_routes
      .map(
        (route) => {

          const grabAverage =
            route.providers
              ?.Grab
              ?.average;


          const gojekAverage =
            route.providers
              ?.Gojek
              ?.average;


          const comparison =
            route.provider_comparison;


          let comparisonText =
            "Not enough comparison data";


          if (comparison) {

            comparisonText =
              `${comparison.cheaper} by ` +
              `${money(
                comparison
                  .average_saving
              )}`;
          }


          return `
            <tr>

              <td>
                ${routeName(
                  route
                )}
              </td>

              <td>
                ${route.overall.count}
              </td>

              <td>
                ${money(
                  route.overall.median
                )}
              </td>

              <td>

                ${
                  grabAverage != null
                    ? money(
                        grabAverage
                      )
                    : "—"
                }

              </td>

              <td>

                ${
                  gojekAverage != null
                    ? money(
                        gojekAverage
                      )
                    : "—"
                }

              </td>


              <td class="good">

                ${comparisonText}

              </td>

            </tr>
          `;
        }
      )
      .join("");
}


/* =========================================================
   ROUTE SELECTOR
========================================================= */

function fillRoutes() {
  const routes =
    DATA.routes
      .filter(
        (route) =>
          route.overall &&
          route.overall.count >=
            2
      )
      .sort(
        (a, b) =>
          b.overall.count -
          a.overall.count
      );


  const options =
    routes
      .map(
        (route) => `

          <option
            value="${
              route.key
            }"
          >

            ${routeName(
              route
            )}

            (${
              route.overall.count
            })

          </option>
        `
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

      (event) => {

        showRoute(
          event.target.value
        );

      }
    );
  }


  if (fareRoute) {

    fareRoute.innerHTML =
      options;
  }


  if (
    routeSelect &&
    routeSelect.value
  ) {

    showRoute(
      routeSelect.value
    );
  }
}


/* =========================================================
   RIDES PAGE
========================================================= */

function showRoute(key) {

  const route =
    DATA.routes.find(
      (item) =>
        item.key === key
    );


  if (!route) return;


  const confidence =
    confidenceLevel(
      route.overall.count
    );


  const cheapestTime =
    cheapestEntry(
      route.time_buckets,
      5
    );


  const expensiveTime =
    mostExpensiveEntry(
      route.time_buckets,
      5
    );


  const cheapestDay =
    cheapestEntry(
      route.weekdays,
      3
    );


  const expensiveDay =
    mostExpensiveEntry(
      route.weekdays,
      3
    );


  const providerComparison =
    route.provider_comparison;


  let providerRecommendation = `

    <div class="
      recommendation-neutral
    ">

      There is not enough data
      from both providers for
      a reliable comparison.

    </div>
  `;


  if (providerComparison) {

    providerRecommendation = `

      <div class="
        recommendation-good
      ">

        Historically,

        <strong>
          ${
            providerComparison
              .cheaper
          }
        </strong>

        has been cheaper for
        this route by an average
        of

        <strong>
          ${money(
            providerComparison
              .average_saving
          )}
        </strong>

        per trip.

      </div>
    `;
  }


  const providerCards =
    Object.entries(
      route.providers || {}
    )
      .map(
        ([provider, stats]) => {

          const isWinner =
            providerComparison &&
            providerComparison
              .cheaper ===
              provider;


          return `

            <div class="
              ride-provider-card
              ${
                isWinner
                  ? "provider-winner"
                  : ""
              }
            ">

              <div class="
                provider-card-head
              ">

                <strong>
                  ${provider}
                </strong>

                ${
                  isWinner
                    ? `
                      <span class="
                        winner-badge
                      ">
                        Historical edge
                      </span>
                    `
                    : ""
                }

              </div>


              <div class="
                provider-main-value
              ">

                ${money(
                  stats.average
                )}

              </div>


              <div class="muted">

                Average fare

                · ${
                  stats.count
                } trips

              </div>


              <div class="
                provider-detail-grid
              ">

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
                    Typical
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

              </div>

            </div>
          `;
        }
      )
      .join("");


  const timeEntries =
    Object.entries(
      route.time_buckets ||
      {}
    );


  const weekdayOrder =
    [
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
          route.weekdays?.[
            day
          ]
      )
      .map(
        (day) => [
          day,
          route.weekdays[
            day
          ]
        ]
      );


  const maxTimeAverage =
    Math.max(
      ...timeEntries.map(
        ([, stats]) =>
          stats.average
      ),

      1
    );


  const maxWeekdayAverage =
    Math.max(
      ...weekdayEntries.map(
        ([, stats]) =>
          stats.average
      ),

      1
    );


  const topRoutes =
    DATA.routes
      .filter(
        (item) =>
          item.overall?.count >=
          3
      )
      .sort(
        (a, b) =>
          b.overall.count -
          a.overall.count
      )
      .slice(
        0,
        8
      );


  document.querySelector(
    "#routeDetail"
  ).innerHTML = `


    <!-- RIDE DATA SNAPSHOT -->

    <div class="
      rides-global-summary
    ">


      <div class="
        ride-summary-box
      ">

        <span>
          Historical rides
        </span>

        <strong>
          ${
            DATA.summary
              .ride_transactions
          }
        </strong>

      </div>


      <div class="
        ride-summary-box
      ">

        <span>
          Ride spend
        </span>

        <strong>
          ${money(
            DATA.summary
              .ride_spend_sgd
          )}
        </strong>

      </div>


      <div class="
        ride-summary-box
      ">

        <span>
          Routes tracked
        </span>

        <strong>
          ${
            DATA.routes.length
          }
        </strong>

      </div>


      <div class="
        ride-summary-box
      ">

        <span>
          Selected route
        </span>

        <strong>
          ${
            route.overall.count
          }
          trips
        </strong>

      </div>


    </div>



    <!-- MOST FREQUENT ROUTES -->

    <div class="
      ride-section
    ">

      <div class="
        ride-section-title
      ">

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


      <div class="
        route-ranking
      ">

        ${topRoutes
          .map(
            (
              item,
              index
            ) => {

              const comparison =
                item
                  .provider_comparison;


              return `

                <button

                  class="
                    route-rank-row

                    ${
                      item.key ===
                      route.key

                        ? "active-route"

                        : ""
                    }
                  "

                  data-route-key="
                    ${item.key}
                  "
                >


                  <span class="
                    rank-number
                  ">

                    ${index + 1}

                  </span>


                  <span class="
                    rank-route
                  ">

                    <strong>

                      ${routeName(
                        item
                      )}

                    </strong>


                    <small>

                      ${
                        item.overall
                          .count
                      }
                      trips

                      · median

                      ${money(
                        item.overall
                          .median
                      )}

                    </small>

                  </span>


                  <span class="
                    rank-edge
                  ">

                    ${
                      comparison

                        ? `
                          ${
                            comparison
                              .cheaper
                          }

                          saves

                          ${money(
                            comparison
                              .average_saving
                          )}
                        `

                        : "Single-provider data"
                    }

                  </span>


                </button>
              `;
            }
          )
          .join("")}

      </div>

    </div>



    <!-- SELECTED ROUTE -->

    <div class="
      selected-route-header
    ">


      <div>

        <div class="
          route-eyebrow
        ">
          SELECTED ROUTE
        </div>


        <h2>

          ${routeName(
            route
          )}

        </h2>


        <div class="
          confidence-badge

          ${
            confidence.className
          }
        ">

          ${confidence.text}

          · ${
            route.overall.count
          } trips

        </div>

      </div>


      <div class="
        route-median-big
      ">

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



    <!-- ROUTE KPIs -->

    <div class="
      route-kpis
      enhanced-route-kpis
    ">


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



    <!-- PROVIDER RECOMMENDATION -->

    <div class="
      route-intelligence-banner
    ">

      ${providerRecommendation}

    </div>



    <!-- PROVIDER CARDS -->

    <div class="
      ride-section
    ">

      <div class="
        ride-section-title
      ">

        <div>

          <h3>
            Provider comparison
          </h3>

          <p>
            Historical performance
            for this exact route.
          </p>

        </div>

      </div>


      <div class="
        ride-provider-grid
      ">

        ${providerCards}

      </div>

    </div>



    <!-- TIME ANALYSIS -->

    <div class="
      ride-section
    ">

      <div class="
        ride-section-title
      ">

        <div>

          <h3>
            Time-of-day patterns
          </h3>

          <p>
            Periods with fewer than
            five trips are not used
            for the best/worst
            recommendation.
          </p>

        </div>

      </div>


      <div class="
        pattern-insights
      ">


        <div class="
          pattern-callout
          best-pattern
        ">

          <span>
            Best reliable period
          </span>

          <strong>

            ${
              cheapestTime

                ? cheapestTime[0]

                : "Not enough data"
            }

          </strong>


          ${
            cheapestTime

              ? `

                <small>

                  Avg

                  ${money(
                    cheapestTime[
                      1
                    ].average
                  )}

                  across

                  ${
                    cheapestTime[
                      1
                    ].count
                  }

                  trips

                </small>
              `

              : ""
          }

        </div>



        <div class="
          pattern-callout
          expensive-pattern
        ">

          <span>
            Most expensive period
          </span>

          <strong>

            ${
              expensiveTime

                ? expensiveTime[0]

                : "Not enough data"
            }

          </strong>


          ${
            expensiveTime

              ? `

                <small>

                  Avg

                  ${money(
                    expensiveTime[
                      1
                    ].average
                  )}

                  across

                  ${
                    expensiveTime[
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



      <div class="
        pattern-list
      ">

        ${timeEntries
          .map(
            (
              [
                timeName,
                stats
              ]
            ) => {

              const width =
                (
                  stats.average /
                  maxTimeAverage
                ) *
                100;


              return `

                <div class="
                  pattern-row
                ">


                  <div class="
                    pattern-name
                  ">

                    <strong>

                      ${timeName}

                    </strong>

                    <small>

                      ${stats.count}
                      trips

                    </small>

                  </div>


                  <div class="
                    pattern-bar-track
                  ">

                    <div
                      class="
                        pattern-bar-fill
                      "

                      style="
                        width:
                        ${width}%
                      "
                    ></div>

                  </div>


                  <div class="
                    pattern-price
                  ">

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



    <!-- WEEKDAY ANALYSIS -->

    <div class="
      ride-section
    ">

      <div class="
        ride-section-title
      ">

        <div>

          <h3>
            Day-of-week patterns
          </h3>

          <p>
            Compare average fares
            by weekday for this route.
          </p>

        </div>

      </div>


      <div class="
        pattern-insights
      ">


        <div class="
          pattern-callout
          best-pattern
        ">

          <span>
            Cheapest reliable day
          </span>

          <strong>

            ${
              cheapestDay

                ? cheapestDay[0]

                : "Not enough data"
            }

          </strong>


          ${
            cheapestDay

              ? `

                <small>

                  Avg

                  ${money(
                    cheapestDay[
                      1
                    ].average
                  )}

                  ·

                  ${
                    cheapestDay[
                      1
                    ].count
                  }

                  trips

                </small>

              `

              : ""
          }

        </div>



        <div class="
          pattern-callout
          expensive-pattern
        ">

          <span>
            Most expensive day
          </span>

          <strong>

            ${
              expensiveDay

                ? expensiveDay[0]

                : "Not enough data"
            }

          </strong>


          ${
            expensiveDay

              ? `

                <small>

                  Avg

                  ${money(
                    expensiveDay[
                      1
                    ].average
                  )}

                  ·

                  ${
                    expensiveDay[
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



      <div class="
        pattern-list
      ">

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
                  stats.average /
                  maxWeekdayAverage
                ) *
                100;


              return `

                <div class="
                  pattern-row
                ">


                  <div class="
                    pattern-name
                  ">

                    <strong>
                      ${day}
                    </strong>

                    <small>

                      ${stats.count}
                      trips

                    </small>

                  </div>


                  <div class="
                    pattern-bar-track
                  ">

                    <div
                      class="
                        pattern-bar-fill
                      "

                      style="
                        width:
                        ${width}%
                      "
                    ></div>

                  </div>


                  <div class="
                    pattern-price
                  ">

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



    <!-- ROUTE DETAIL TABLE -->

    <div class="
      ride-section
    ">

      <div class="
        ride-section-title
      ">

        <div>

          <h3>
            Detailed provider statistics
          </h3>

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
              button.dataset
                .routeKey;


            const select =
              document.querySelector(
                "#routeSelect"
              );


            select.value =
              routeKey;


            showRoute(
              routeKey
            );

          }
        );
      }
    );
}


/* =========================================================
   TAB NAVIGATION
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
              tab.classList.remove(
                "active"
              )
          );


          panels.forEach(
            (panel) =>
              panel.classList.remove(
                "active"
              )
          );


          button.classList.add(
            "active"
          );


          const panel =
            document.querySelector(
              `#${
                button.dataset.tab
              }`
            );


          if (panel) {

            panel.classList.add(
              "active"
            );
          }


          window.scrollTo({
            top: 0,
            left: 0,
            behavior: "auto"
          });

        }
      );

    }
  );
}


/* =========================================================
   FARE SCORING
========================================================= */

function fareScore(
  amount,
  stats
) {

  if (
    amount <= stats.p10
  ) {

    return [
      5,
      "Exceptional value"
    ];
  }


  if (
    amount <= stats.p25
  ) {

    return [
      4,
      "Very good"
    ];
  }


  if (
    amount <= stats.median
  ) {

    return [
      3,
      "Normal to good"
    ];
  }


  if (
    amount <= stats.p75
  ) {

    return [
      2,
      "Somewhat expensive"
    ];
  }


  if (
    amount <= stats.p90
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


/* =========================================================
   FARE CHECKER
========================================================= */

function checkFare() {

  const routeKey =
    document.querySelector(
      "#fareRoute"
    ).value;


  const provider =
    document.querySelector(
      "#fareProvider"
    ).value;


  const amount =
    Number(
      document.querySelector(
        "#fareAmount"
      ).value
    );


  const resultBox =
    document.querySelector(
      "#fareResult"
    );


  const route =
    DATA.routes.find(
      (item) =>
        item.key ===
        routeKey
    );


  if (
    !route ||
    !Number.isFinite(
      amount
    ) ||
    amount <= 0
  ) {

    resultBox.innerHTML =
      "Enter a valid fare amount.";

    return;
  }


  const stats =
    provider === "Overall"

      ? route.overall

      : route.providers?.[
          provider
        ];


  if (!stats) {

    resultBox.innerHTML =

      "Not enough historical data " +

      "for that provider and route.";

    return;
  }


  const [
    score,
    description
  ] = fareScore(
    amount,
    stats
  );


  const difference =
    amount -
    stats.median;


  const differenceText =
    difference >= 0

      ? `${money(
          difference
        )} above`

      : `${money(
          Math.abs(
            difference
          )
        )} below`;


  resultBox.innerHTML = `

    <div class="score">

      ${score}

      <small>
        /5
      </small>

    </div>


    <strong>
      ${description}
    </strong>


    <div
      class="muted"

      style="
        margin-top:
        6px
      "
    >

      Quote:
      ${money(amount)}

      · Historical median:
      ${money(
        stats.median
      )}

      · ${differenceText}
      median

      · ${stats.count}
      comparison trips

    </div>
  `;
}


function wireFareChecker() {

  const button =
    document.querySelector(
      "#checkFare"
    );


  const input =
    document.querySelector(
      "#fareAmount"
    );


  button.addEventListener(
    "click",
    checkFare
  );


  input.addEventListener(
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


  document.querySelector(
    "#foodSummary"
  ).innerHTML = `

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

      style="
        margin-top:
        20px
      "
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


  const restaurants =
    food.top_restaurants ||
    [];


  document.querySelector(
    "#topFood"
  ).innerHTML =
    restaurants
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

                ${
                  restaurant.count
                }

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


/* =========================================================
   ASK MY DATA
========================================================= */

function answer(question) {

  const q =
    String(
      question || ""
    )
      .toLowerCase()
      .trim();


  const homeOffice =
    DATA.routes.find(
      (route) =>
        route.key ===
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
    q.includes("food") ||
    q.includes(
      "restaurant"
    )
  ) {

    const top =
      DATA.food
        .top_restaurants?.[0];


    if (!top) {

      return (
        "No food-order data " +
        "is currently available."
      );
    }


    return `

      Your most frequently ordered
      restaurant in this dataset is

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
    q.includes("ride") &&
    q.includes("spend")
  ) {

    return `

      Your recorded ride spend is

      <strong>

        ${money(
          DATA.summary
            .ride_spend_sgd
        )}

      </strong>

      across

      <strong>

        ${
          DATA.summary
            .ride_transactions
        }

        rides

      </strong>.
    `;
  }


  if (
    q.includes("spend")
  ) {

    return `

      Across the supplied history,
      recorded SGD spend is

      <strong>

        ${money(
          DATA.summary
            .total_spend_sgd
        )}

      </strong>.

      This consists of

      <strong>

        ${money(
          DATA.summary
            .ride_spend_sgd
        )}

      </strong>

      on rides and

      <strong>

        ${money(
          DATA.summary
            .food_spend_sgd
        )}

      </strong>

      on GrabFood.
    `;
  }


  if (
    q.includes("cheaper") &&
    homeOffice
      ?.provider_comparison
  ) {

    const comparison =
      homeOffice
        .provider_comparison;


    return `

      For Home → Office,

      <strong>

        ${comparison.cheaper}

      </strong>

      has historically been
      cheaper on average by about

      <strong>

        ${money(
          comparison
            .average_saving
        )}

      </strong>

      per trip.
    `;
  }


  if (
    homeOffice &&

    (
      (
        q.includes("home") &&
        q.includes("office")
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

        ${
          homeOffice
            .overall
            .count
        }

        trips

      </strong>.
    `;
  }


  return `

    I can currently answer
    questions about:

    <strong>

      spending,
      food orders,
      Home → Office fares
      and provider comparisons.

    </strong>

    We will expand this intelligence
    capability in the next phase.
  `;
}


/* =========================================================
   AGENT
========================================================= */

function askQuestion() {

  const question =
    document.querySelector(
      "#agentQuestion"
    ).value;


  document.querySelector(
    "#agentAnswer"
  ).innerHTML =
    answer(
      question
    );
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
              button.dataset.q;


            document.querySelector(
              "#agentQuestion"
            ).value =
              question;


            document.querySelector(
              "#agentAnswer"
            ).innerHTML =
              answer(
                question
              );

          }
        );

      }
    );


  document.querySelector(
    "#askButton"
  ).addEventListener(
    "click",
    askQuestion
  );


  document.querySelector(
    "#agentQuestion"
  ).addEventListener(
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
