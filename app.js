document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll(".flash").forEach((message) => {
    window.setTimeout(() => message.classList.add("flash-hidden"), 4200);
  });

  if (!window.Chart) return;
  Chart.defaults.font.family = "DM Sans, sans-serif";
  Chart.defaults.color = "#758078";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  const dashboardData = document.querySelector("#dashboard-data");
  if (dashboardData) {
    const data = JSON.parse(dashboardData.textContent);
    const canvas = document.querySelector("#weeklyChart");
    if (canvas) {
      new Chart(canvas, {
        type: "line",
        data: { labels: data.weekly_spending.labels, datasets: [{ data: data.weekly_spending.values, borderColor: "#287753", backgroundColor: "rgba(40, 119, 83, .11)", fill: true, tension: .35, borderWidth: 2.5, pointRadius: 3, pointHoverRadius: 5 }] },
        options: chartOptions("$", false),
      });
    }
  }

  const analyticsData = document.querySelector("#analytics-data");
  if (analyticsData) {
    const data = JSON.parse(analyticsData.textContent);
    makeChart("spendingChart", "line", data.monthly_spending, "#287753", "$", false);
    makeChart("frequencyChart", "bar", data.monthly_frequency, "#d49a45", "", true);
    const colors = ["#287753", "#d49a45", "#7097bd", "#d77960", "#8a9d67", "#8878a2", "#54a99a"];
    const categoryCanvas = document.querySelector("#categoryChart");
    if (categoryCanvas) new Chart(categoryCanvas, {
      type: "doughnut",
      data: { labels: data.category_spending.labels, datasets: [{ data: data.category_spending.values, backgroundColor: colors, borderWidth: 3, borderColor: "#fff", hoverOffset: 5 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "67%", plugins: { legend: { position: "bottom", labels: { padding: 18, boxWidth: 7 } }, tooltip: { callbacks: { label: (context) => ` ${context.label}: $${Number(context.raw).toFixed(2)}` } } } },
    });
    makeChart("itemsChart", "bar", data.top_items, "#7097bd", "", true);
  }
});

function chartOptions(prefix, beginAtZero) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => `${prefix}${Number(context.raw).toFixed(prefix ? 2 : 0)}` } } },
    scales: {
      x: { grid: { display: false }, border: { display: false } },
      y: { beginAtZero, border: { display: false }, grid: { color: "#edf0ed" }, ticks: { callback: (value) => `${prefix}${value}` } },
    },
  };
}

function makeChart(id, type, series, color, prefix, beginAtZero) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  new Chart(canvas, {
    type,
    data: { labels: series.labels, datasets: [{ data: series.values, backgroundColor: type === "bar" ? `${color}cc` : "rgba(40, 119, 83, .1)", borderColor: color, borderWidth: type === "bar" ? 0 : 2.5, borderRadius: type === "bar" ? 4 : 0, tension: .32, fill: type === "line", pointRadius: 3 }] },
    options: chartOptions(prefix, beginAtZero),
  });
}