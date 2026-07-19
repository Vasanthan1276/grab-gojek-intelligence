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
      value: money(summary.total_spend_sgd),
      subtitle: "SGD across both reports"
    },
    {
      title: "Ride spend",
      value: money(summary.ride_spend_sgd),
      subtitle: `${summary.ride_transactions} rides`
    },
    {
      title: "Food spend",
      value: money(summary.food_spend_sgd),
      subtitle: `${summary.food_orders} GrabFood orders`
    },
    {
      title: "Average food order",
      value: money(summary.average_food_order),
      subtitle: "Historical average"
    }
  ];

  document.querySelector("#summaryCards").innerHTML =
    cards
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
    document.querySelector("#providerSnapshot");

  if (!container) return;

  container.innerHTML =
    Object.entries(DATA.providers)
      .map(
        ([provider, values]) => `
          <div class="provider-row">

            <div>
              <strong>
                ${provider}
              </strong>

              <div class="muted">
                ${values.rides} rides
                · avg ${money(values.average_ride)}
              </div>
            </div>

            <strong>
              ${money(values.spend_sgd)}
            </strong>

          </div>
        `
      )
      .join("");
}

/* =========================================================
   MONTHLY SPEND
   NO CHART.JS
========================================================= */

function renderMonthly() {
  const oldCanvas =
    document.querySelector("#monthlyChart");

  if (!oldCanvas) return;

  const monthlyData =
    Array.isArray(DATA.monthly)
      ? DATA.monthly
      : [];

  if (!monthlyData.length) {
    oldCanvas.outerHTML = `
      <div class="monthly-empty">
        No monthly data available.
      </div>
    `;

    return;
  }

  const totals =
    monthlyData.map((month) => {
      const grab =
        Number(month["Grab rides"] || 0);

      const gojek =
        Number(month["Gojek rides"] || 0);

      const food =
        Number(month.GrabFood || 0);

      return grab + gojek + food;
    });

  const maximum =
    Math.max(...totals, 1);

  const chart =
    document.createElement("div");

  chart.id = "monthlySpendChart";

  chart.className =
    "monthly-chart";

  chart.innerHTML = `
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

      ${monthlyData
        .map((month) => {
          const grab =
            Number(
              month["Grab rides"] || 0
            );

          const gojek =
            Number(
              month["Gojek rides"] || 0
            );

          const food =
            Number(
              month.GrabFood || 0
            );

          const total =
            grab + gojek + food;

          const overallHeight =
            total > 0
              ? Math.max(
                  (total / maximum) * 100,
                  4
                )
              : 0;

          const grabShare =
            total > 0
              ? (grab / total) * 100
              : 0;

          const gojekShare =
            total > 0
              ? (gojek / total) * 100
              : 0;

          const foodShare =
            total > 0
              ? (food / total) * 100
              : 0;

          const tooltip = [
            `${formatMonth(month.month)}`,
            `Total: ${money(total)}`,
            `Grab rides: ${money(grab)}`,
            `Gojek rides: ${money(gojek)}`,
            `GrabFood: ${money(food)}`
          ].join("\n");

          return `
            <div class="month-column">

              <div class="month-value">
                ${Math.round(total)}
              </div>

              <div class="month-bar-area">

                <div
                  class="month-stack"
                  style="height:${overallHeight}%"
                  title="${tooltip}"
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
                            height:${gojekShare}%
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
                            height:${grabShare}%
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
                            height:${foodShare}%
                          "
                        ></div>
                      `
                      : ""
                  }

                </div>

              </div>

              <div class="month-label">
                ${formatMonth(month.month)}
              </div>

            </div>
          `;
        })
        .join("")}

    </div>
  `;

  oldCanvas.replaceWith(chart);
}

/* =========================================================
   CORE ROUTES
========================================================= */

function renderCoreRoutes() {
  const tableBody =
    document.querySelector("#coreRoutes");

  if (!tableBody) return;

  tableBody.innerHTML =
    DATA.core_routes
      .map((route) => {
        const grabAverage =
          route.providers?.Grab?.average;

        const gojekAverage =
          route.providers?.Gojek?.average;

        const comparison =
          route.provider_comparison;

        let comparisonText =
          "Not enough comparison data";

        if (comparison) {
          comparisonText =
            `${comparison.cheaper} by ` +
            `${money(
              comparison.average_saving
            )}`;
        }

        return `
          <tr>

            <td>
              ${routeName(route)}
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
                  ? money(grabAverage)
                  : "—"
              }
            </td>

            <td>
              ${
                gojekAverage != null
                  ? money(gojekAverage)
                  : "—"
              }
            </td>

            <td class="good">
              ${comparisonText}
            </td>

          </tr>
        `;
      })
      .join("");
}

/* =========================================================
   ROUTE SELECTORS
========================================================= */

function fillRoutes() {
  const routes =
    DATA.routes.filter(
      (route) =>
        route.overall &&
        route.overall.count >= 2
    );

  const options =
    routes
      .map(
        (route) => `
          <option value="${route.key}">
            ${routeName(route)}
            (${route.overall.count})
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
   ROUTE EXPLORER
========================================================= */

function showRoute(key) {
  const route =
    DATA.routes.find(
      (item) =>
        item.key === key
    );

  if (!route) return;

  let comparisonText =
    "Not enough trips on both providers " +
    "for a reliable provider comparison.";

  if (
    route.provider_comparison
  ) {
    comparisonText = `
      <strong>
        ${
          route
            .provider_comparison
            .cheaper
        }
      </strong>

      has historically averaged

      <strong>
        ${money(
          route
            .provider_comparison
            .average_saving
        )}
      </strong>

      less per trip.
    `;
  }

  const bestTimeText =
    route.best_time_bucket
      ? `
        Lowest reliable historical
        time bucket:

        <strong>
          ${route.best_time_bucket}
        </strong>.
      `
      : "";

  const providerRows =
    Object.entries(
      route.providers || {}
    )
      .map(
        ([provider, stats]) => `
          <tr>

            <td>
              ${provider}
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

          </tr>
        `
      )
      .join("");

  document.querySelector(
    "#routeDetail"
  ).innerHTML = `

    <div class="route-kpis">

      <div class="mini">
        <span>
          Trips
        </span>

        <strong>
          ${route.overall.count}
        </strong>
      </div>

      <div class="mini">
        <span>
          Median fare
        </span>

        <strong>
          ${money(
            route.overall.median
          )}
        </strong>
      </div>

      <div class="mini">
        <span>
          Typical range
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
          Observed range
        </span>

        <strong>
          ${money(
            route.overall.min
          )}
          –
          ${money(
            route.overall.max
          )}
        </strong>
      </div>

    </div>

    <div class="route-notes">

      <div>
        ${comparisonText}
      </div>

      ${
        bestTimeText
          ? `
            <div
              style="
                margin-top:8px
              "
            >
              ${bestTimeText}
            </div>
          `
          : ""
      }

    </div>

    <div
      class="table-wrap"
      style="
        margin-top:16px
      "
    >

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
              P25–P75
            </th>

          </tr>

        </thead>

        <tbody>
          ${providerRows}
        </tbody>

      </table>

    </div>
  `;
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

  tabs.forEach((button) => {
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
            `#${button.dataset.tab}`
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
  });
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
        item.key === routeKey
    );

  if (
    !route ||
    !Number.isFinite(amount) ||
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
  ] =
    fareScore(
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
        margin-top:6px
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
        event.key === "Enter"
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
        margin-top:20px
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
    food.top_restaurants || [];

  document.querySelector(
    "#topFood"
  ).innerHTML =
    restaurants
      .slice(0, 8)
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
                  restaurant.restaurant
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

/* =========================================================
   ASK MY DATA
========================================================= */

function answer(
  question
) {
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
        ${top.count} orders
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
        } rides
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
      ) ||
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

function askQuestion() {
  const question =
    document.querySelector(
      "#agentQuestion"
    ).value;

  document.querySelector(
    "#agentAnswer"
  ).innerHTML =
    answer(question);
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
        event.key === "Enter"
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
          padding-top:40px;
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
              white-space:pre-wrap;
              overflow:auto;
            "
          >${error.message}</pre>

        </article>

      </main>
    `;
  }
);
