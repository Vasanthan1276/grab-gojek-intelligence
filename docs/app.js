let DATA;
let monthlyChart = null;

const money = (n) => `S$${Number(n || 0).toFixed(2)}`;

const label = (s) => {
  if (!s) return "";
  return s
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

function routeName(route) {
  return `${label(route.origin)} → ${label(route.destination)}`;
}

async function init() {
  const response = await fetch("./data/analytics.json", {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Unable to load analytics.json: ${response.status}`);
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

/* --------------------------------------------------
   SUMMARY
-------------------------------------------------- */

function renderSummary() {
  const s = DATA.summary;

  const cards = [
    [
      "Total spend",
      money(s.total_spend_sgd),
      "SGD across both reports"
    ],
    [
      "Ride spend",
      money(s.ride_spend_sgd),
      `${s.ride_transactions} rides`
    ],
    [
      "Food spend",
      money(s.food_spend_sgd),
      `${s.food_orders} GrabFood orders`
    ],
    [
      "Average food order",
      money(s.average_food_order),
      "Historical average"
    ]
  ];

  document.querySelector("#summaryCards").innerHTML = cards
    .map(
      ([title, value, subtitle]) => `
        <article class="card metric">
          <div class="label">${title}</div>
          <div class="value">${value}</div>
          <div class="sub">${subtitle}</div>
        </article>
      `
    )
    .join("");
}

/* --------------------------------------------------
   PROVIDERS
-------------------------------------------------- */

function renderProviders() {
  const container = document.querySelector("#providerSnapshot");

  container.innerHTML = Object.entries(DATA.providers)
    .map(
      ([provider, values]) => `
        <div class="provider-row">
          <div>
            <strong>${provider}</strong>
            <div class="muted">
              ${values.rides} rides · avg ${money(values.average_ride)}
            </div>
          </div>

          <strong>${money(values.spend_sgd)}</strong>
        </div>
      `
    )
    .join("");
}

/* --------------------------------------------------
   MONTHLY CHART
-------------------------------------------------- */

function renderMonthly() {
  if (!window.Chart) {
    console.warn("Chart.js did not load.");
    return;
  }

  const canvas = document.querySelector("#monthlyChart");

  if (!canvas) return;

  if (monthlyChart) {
    monthlyChart.destroy();
  }

  monthlyChart = new Chart(canvas, {
    type: "bar",

    data: {
      labels: DATA.monthly.map((item) => item.month),

      datasets: [
        {
          label: "Grab rides",
          data: DATA.monthly.map((item) => item["Grab rides"] || 0)
        },
        {
          label: "Gojek rides",
          data: DATA.monthly.map((item) => item["Gojek rides"] || 0)
        },
        {
          label: "GrabFood",
          data: DATA.monthly.map((item) => item.GrabFood || 0)
        }
      ]
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 200,

      animation: {
        duration: 400
      },

      plugins: {
        legend: {
          labels: {
            color: "#bcd0e5"
          }
        }
      },

      scales: {
        x: {
          stacked: true,
          ticks: {
            color: "#91a6bd"
          },
          grid: {
            color: "#1d3046"
          }
        },

        y: {
          stacked: true,
          beginAtZero: true,
          ticks: {
            color: "#91a6bd"
          },
          grid: {
            color: "#1d3046"
          }
        }
      }
    }
  });
}

/* --------------------------------------------------
   CORE ROUTES
-------------------------------------------------- */

function renderCoreRoutes() {
  const tbody = document.querySelector("#coreRoutes");

  tbody.innerHTML = DATA.core_routes
    .map((route) => {
      const grabAverage = route.providers.Grab?.average;
      const gojekAverage = route.providers.Gojek?.average;
      const comparison = route.provider_comparison;

      return `
        <tr>
          <td>${routeName(route)}</td>
          <td>${route.overall.count}</td>
          <td>${money(route.overall.median)}</td>
          <td>${grabAverage ? money(grabAverage) : "—"}</td>
          <td>${gojekAverage ? money(gojekAverage) : "—"}</td>
          <td class="good">
            ${
              comparison
                ? `${comparison.cheaper} by ${money(
                    comparison.average_saving
                  )}`
                : "Not enough comparison data"
            }
          </td>
        </tr>
      `;
    })
    .join("");
}

/* --------------------------------------------------
   ROUTE EXPLORER
-------------------------------------------------- */

function fillRoutes() {
  const routes = DATA.routes.filter(
    (route) => route.overall && route.overall.count >= 2
  );

  const options = routes
    .map(
      (route) =>
        `<option value="${route.key}">
          ${routeName(route)} (${route.overall.count})
        </option>`
    )
    .join("");

  const routeSelect = document.querySelector("#routeSelect");
  const fareRoute = document.querySelector("#fareRoute");

  routeSelect.innerHTML = options;
  fareRoute.innerHTML = options;

  routeSelect.addEventListener("change", (event) => {
    showRoute(event.target.value);
  });

  if (routeSelect.value) {
    showRoute(routeSelect.value);
  }
}

function showRoute(key) {
  const route = DATA.routes.find((item) => item.key === key);

  if (!route) return;

  let comparisonText =
    "Not enough trips on both providers for a reliable provider comparison.";

  if (route.provider_comparison) {
    comparisonText = `
      ${route.provider_comparison.cheaper} has historically averaged
      ${money(route.provider_comparison.average_saving)} less per trip.
    `;
  }

  const bestTime = route.best_time_bucket
    ? `Lowest reliable time bucket: <strong>${route.best_time_bucket}</strong>.`
    : "";

  const providerRows = Object.entries(route.providers)
    .map(
      ([provider, stats]) => `
        <tr>
          <td>${provider}</td>
          <td>${stats.count}</td>
          <td>${money(stats.average)}</td>
          <td>${money(stats.median)}</td>
          <td>${money(stats.p25)}–${money(stats.p75)}</td>
        </tr>
      `
    )
    .join("");

  document.querySelector("#routeDetail").innerHTML = `
    <div class="route-kpis">

      <div class="mini">
        <span>Trips</span>
        <strong>${route.overall.count}</strong>
      </div>

      <div class="mini">
        <span>Median fare</span>
        <strong>${money(route.overall.median)}</strong>
      </div>

      <div class="mini">
        <span>Typical range</span>
        <strong>
          ${money(route.overall.p25)}–${money(route.overall.p75)}
        </strong>
      </div>

      <div class="mini">
        <span>Observed range</span>
        <strong>
          ${money(route.overall.min)}–${money(route.overall.max)}
        </strong>
      </div>

    </div>

    <div class="route-notes">
      ${comparisonText}
      ${bestTime}
    </div>

    <div class="table-wrap">

      <table>

        <thead>
          <tr>
            <th>Provider</th>
            <th>Trips</th>
            <th>Average</th>
            <th>Median</th>
            <th>P25–P75</th>
          </tr>
        </thead>

        <tbody>
          ${providerRows}
        </tbody>

      </table>

    </div>
  `;
}

/* --------------------------------------------------
   TABS
-------------------------------------------------- */

function wireTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document
        .querySelectorAll(".tab")
        .forEach((tab) => tab.classList.remove("active"));

      document
        .querySelectorAll(".panel")
        .forEach((panel) => panel.classList.remove("active"));

      button.classList.add("active");

      const target = document.querySelector(`#${button.dataset.tab}`);

      if (target) {
        target.classList.add("active");
      }

      window.scrollTo({
        top: 0,
        behavior: "instant"
      });
    });
  });
}

/* --------------------------------------------------
   FARE CHECKER
-------------------------------------------------- */

function fareScore(amount, stats) {
  if (amount <= stats.p10) {
    return [5, "Exceptional value"];
  }

  if (amount <= stats.p25) {
    return [4, "Very good"];
  }

  if (amount <= stats.median) {
    return [3, "Normal to good"];
  }

  if (amount <= stats.p75) {
    return [2, "Somewhat expensive"];
  }

  if (amount <= stats.p90) {
    return [1, "Expensive"];
  }

  return [0, "Unusually expensive"];
}

function wireFareChecker() {
  document.querySelector("#checkFare").addEventListener("click", () => {
    const routeKey = document.querySelector("#fareRoute").value;
    const provider = document.querySelector("#fareProvider").value;
    const amount = Number(document.querySelector("#fareAmount").value);

    const route = DATA.routes.find(
      (item) => item.key === routeKey
    );

    const resultBox = document.querySelector("#fareResult");

    if (!route || !amount || amount <= 0) {
      resultBox.innerHTML =
        "Enter a valid fare amount to compare with your history.";
      return;
    }

    const stats =
      provider === "Overall"
        ? route.overall
        : route.providers[provider];

    if (!stats) {
      resultBox.innerHTML =
        "Not enough historical data for that provider and route.";
      return;
    }

    const [score, description] = fareScore(amount, stats);

    const difference = amount - stats.median;

    const differenceText =
      difference >= 0
        ? `${money(difference)} above`
        : `${money(Math.abs(difference))} below`;

    resultBox.innerHTML = `
      <div class="score">
        ${score}<small>/5</small>
      </div>

      <strong>${description}</strong>

      <div class="muted">
        Quote: ${money(amount)}
        · Historical median: ${money(stats.median)}
        · ${differenceText} median
        · ${stats.count} comparison trips
      </div>
    `;
  });
}

/* --------------------------------------------------
   FOOD
-------------------------------------------------- */

function renderFood() {
  const food = DATA.food;

  document.querySelector("#foodSummary").innerHTML = `
    <div class="metric">
      <div class="label">Orders</div>
      <div class="value">${food.order_count}</div>
    </div>

    <div class="metric">
      <div class="label">Total spend</div>
      <div class="value">${money(food.total_spend_sgd)}</div>
    </div>
  `;

  document.querySelector("#topFood").innerHTML =
    food.top_restaurants
      .slice(0, 8)
      .map(
        (restaurant) => `
          <div class="food-row">

            <div>
              <strong>${label(restaurant.restaurant)}</strong>

              <div class="muted">
                ${restaurant.count} orders
                · avg ${money(restaurant.average_order)}
              </div>
            </div>

            <strong>${money(restaurant.total_spend)}</strong>

          </div>
        `
      )
      .join("");
}

/* --------------------------------------------------
   ASK MY DATA
-------------------------------------------------- */

function answer(question) {
  const q = question.toLowerCase().trim();

  const homeOffice = DATA.routes.find(
    (route) => route.key === "HOME__OFFICE"
  );

  if (q.includes("food") || q.includes("restaurant")) {
    const top = DATA.food.top_restaurants[0];

    return `
      Your most frequently ordered restaurant in this dataset is
      <strong>${label(top.restaurant)}</strong>,
      with ${top.count} orders and
      ${money(top.total_spend)} total spend.
    `;
  }

  if (q.includes("spend")) {
    return `
      Across the supplied history, recorded SGD spend is
      <strong>${money(DATA.summary.total_spend_sgd)}</strong>:
      ${money(DATA.summary.ride_spend_sgd)} on rides and
      ${money(DATA.summary.food_spend_sgd)} on GrabFood.
    `;
  }

  if (
    q.includes("cheaper") &&
    homeOffice?.provider_comparison
  ) {
    const comparison = homeOffice.provider_comparison;

    return `
      For Home → Office,
      <strong>${comparison.cheaper}</strong>
      has historically been cheaper on average by about
      <strong>${money(comparison.average_saving)}</strong>
      per trip.
    `;
  }

  if (
    homeOffice &&
    (
      (q.includes("home") && q.includes("office")) ||
      q.includes("normal fare")
    )
  ) {
    return `
      For Home → Office, your historical median is
      <strong>${money(homeOffice.overall.median)}</strong>,
      with the middle 50% of fares between
      ${money(homeOffice.overall.p25)}
      and
      ${money(homeOffice.overall.p75)}
      across ${homeOffice.overall.count} trips.
    `;
  }

  return `
    I can currently answer questions about spending,
    food, Home → Office fares and provider comparisons.
    More natural-language intelligence will be added
    as we develop the platform.
  `;
}

function wireAgent() {
  document.querySelectorAll(".chips button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector("#agentQuestion").value =
        button.dataset.q;

      document.querySelector("#agentAnswer").innerHTML =
        answer(button.dataset.q);
    });
  });

  document.querySelector("#askButton").addEventListener("click", () => {
    const question =
      document.querySelector("#agentQuestion").value;

    document.querySelector("#agentAnswer").innerHTML =
      answer(question);
  });
}

/* --------------------------------------------------
   START
-------------------------------------------------- */

init().catch((error) => {
  console.error(error);

  document.body.innerHTML = `
    <main style="padding-top:40px">

      <article class="card">

        <h2>Could not load dashboard data</h2>

        <p>
          The dashboard encountered an error while loading.
        </p>

        <pre style="white-space:pre-wrap">
${error.message}
        </pre>

      </article>

    </main>
  `;
});
