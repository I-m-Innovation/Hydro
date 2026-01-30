// #region Boot
document.addEventListener("DOMContentLoaded", () => {
  if (typeof Chart === "undefined") {
    return;
  }

  if (window.ChartZoom) {
    Chart.register(window.ChartZoom);
  }

  // Default labels used before API data arrives.
  const labels = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
  const grid = document.querySelector(".facility-plot-grid");
  const instances = new Map();
  const pollingIntervals = new Map();
  const POLL_INTERVAL_MS = 60000; // 1 minute

  // #endregion Boot

  // #region Plugins
  const hoverLinePlugin = {
    id: "hoverLine",
    afterDatasetsDraw(chart) {
      const active = chart.getActiveElements();
      if (!active || !active.length) {
        return;
      }
      const { ctx, chartArea } = chart;
      const x = active[0].element.x;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(29, 78, 216, 0.3)";
      ctx.stroke();
      ctx.restore();
    },
  };
  // #endregion Plugins

  // #region Average Line Helpers
  // Average line dataset shown only on the flow chart.
  const buildAverageDataset = () => ({
    label: "Media",
    data: [],
    type: "line",
    borderColor: "#dc2626",
    backgroundColor: "rgba(17, 24, 39, 0)",
    borderDash: [6, 6],
    borderWidth: 1,
    pointRadius: 0,
    tension: 0,
    fill: false,
    order: 999,
    _isAverage: true,
  });

  const parseAverageValue = (value) => {
    if (value === null || value === undefined) {
      return NaN;
    }
    if (typeof value === "number") {
      return Number.isFinite(value) ? value : NaN;
    }
    const normalized = String(value).trim().replace(",", ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : NaN;
  };

  const updateAverageLine = (chart, avgValue) => {
    if (!chart) {
      return;
    }
    const avgDataset = chart.data.datasets.find((ds) => ds._isAverage);
    if (!avgDataset) {
      return;
    }
    const avg = parseAverageValue(avgValue);
    const labels = chart.data.labels || [];
    if (!Number.isFinite(avg) || !labels.length) {
      avgDataset.data = [];
      avgDataset.hidden = true;
      return;
    }
    avgDataset.data = labels.map((label) => ({ x: label, y: avg }));
    avgDataset.hidden = false;
  };

  // Reads precomputed averages from data-avg-* attributes.
  const getAverageForRange = (canvas, rangeKey) => {
    if (!canvas) {
      return null;
    }
    const attrMap = {
      "24h": "data-avg-24h",
      "7d": "data-avg-7d",
      "1m": "data-avg-1m",
      "6m": "data-avg-6m",
      "1y": "data-avg-1y",
      all: "data-avg-all",
    };
    const rawValue = canvas.getAttribute(attrMap[rangeKey]);
    if (rawValue === "") {
      return null;
    }
    return rawValue ?? null;
  };
  // #endregion Average Line Helpers

  // #region Chart Configs
  const charts = [
    {
      
      id: "chart-flow-rate",
      type: "line",
      label: "Portata (flow)",
      data: [],
      color: "#1d4ed8",
      fillColor: "rgba(29, 78, 216, 0.18)",
      fill: true,
      useApi: true,
      showRange: true,
      showAverage: true,
      datasets: [
        {
          label: "Portata (raw)",
          color: "#6b728089",
          // fillColor: "rgba(107, 114, 128, 0.42)",
          fill: false,
          source: "flow_ls_raw",
          order: 2,
          borderWidth: 1,
        },
        {
          label: "Portata (smoothed)",
          color: "#2563eb",
          fillColor: "rgba(83, 206, 255, 0.54)",
          fill: true,
          source: "flow_ls_smoothed",
          order: 1,
          pointRadius: 0,
          pointHoverRadius: 2,
          spanGaps: true,
          borderWidth: 1,
        },
      ],
    },
    {
      id: "chart-fluid-velocity",
      type: "bar",
      label: "Dati normalizzati in percentuale",
      data: [],
      color: "#16a34a",
      fillColor: "rgba(22, 163, 74, 0.18)",
      fill: false,
      useApi: true,
      apiMode: "flow_histogram",
      xScaleType: "linear",
      xTitle: "Portata (l/s)",
      yTitle: "Distribuzione (%)",
      xTicksCallback: (value) => value,
      xTicksDisplay: true,
      tooltipTitle: (items) => {
        if (!items.length) {
          return "";
        }
        const item = items[0];
        const start = item?.chart?._histRanges?.[item.dataIndex]?.start;
        const end = item?.chart?._histRanges?.[item.dataIndex]?.end;
        if (Number.isFinite(start) && Number.isFinite(end)) {
          return `${start.toFixed(2)} - ${end.toFixed(2)} l/s`;
        }
        return `${Number(item.parsed.x).toFixed(2)} l/s`;
      },
      showAverage: false,
      yTickPrecision: 0,
      datasets: [
        {
          label: "Distribuzione",
          color: "#2563eb",
          fillColor: "rgba(37, 99, 235, 0.35)",
          fill: true,
          source: "percent",
          order: 1,
          borderWidth: 1,
        },
      ],
    },
    {
      id: "chart-curva-di-durata",
      type: "line",
      label: "Curva di durata",
      data: [],
      color: "#f59e0b",
      fillColor: "rgba(245, 158, 11, 0.18)",
      fill: false,
      useApi: true,
      apiMode: "duration_curve",
      xScaleType: "linear",
      xTitle: "% tempo di superamento",
      xTicksCallback: (value) => `${value}%`,
      tooltipTitle: (items) =>
        items.length ? `${items[0].parsed.x.toFixed(1)}%` : "",
      showAverage: false,
      datasets: [
        {
          label: "Curva di durata",
          color: "#f59e0b",
          fillColor: "rgba(245, 158, 11, 0.18)",
          fill: false,
          source: "flow_ls_smoothed",
          order: 1,
          pointRadius: 0,
          pointHoverRadius: 3,
          borderWidth: 2,
        },
      ],
    },
  ];
  // #endregion Chart Configs

  // #region Formatters
  const formatTimestamp = (value) => {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) {
      return "";
    }
    const yy = String(date.getFullYear()).slice(-2);
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    const hh = String(date.getHours()).padStart(2, "0");
    const min = String(date.getMinutes()).padStart(2, "0");
    const ss = String(date.getSeconds()).padStart(2, "0");
    return `${dd}-${mm}-${yy} ${hh}:${min}:${ss}`;
  };

  const formatLabelTimestamp = (value) => formatTimestamp(value) || value || "";
  // #endregion Formatters

  // #region Chart Factory
  // Creates a chart instance and wires data loading + average line.
  const createChart = (cfg, rangeKey) => {
    const canvas = document.getElementById(cfg.id);
    if (!canvas) {
      return null;
    }

    const chartCard = canvas.closest(".chart-card");
    const setLoading = (isLoading) => {
      chartCard?.classList.toggle("is-loading", isLoading);
    };

    const datasetConfigs = cfg.datasets || [
      {
        label: cfg.label,
        color: cfg.color,
        fillColor: cfg.fillColor,
        fill: cfg.fill,
        source: "values",
      },
    ];

    const avgValue = getAverageForRange(canvas, rangeKey);
    const averageDataset = cfg.showAverage ? buildAverageDataset() : null;

    const enableDecimation = cfg.useApi && cfg.type === "line" && cfg.xScaleType === "linear";
    const chart = new Chart(canvas, {
      type: cfg.type,
      data: {
        labels: cfg.labels || labels,
        datasets: [
          ...datasetConfigs.map((ds) => ({
            label: ds.label,
            data: cfg.data || [],
            borderColor: ds.color,
            backgroundColor: ds.fillColor || ds.color,
            borderWidth: ds.borderWidth ?? 1,
            pointRadius: ds.pointRadius ?? 0,
            pointHoverRadius: ds.pointHoverRadius ?? 4,
            tension: 0.25,
            fill: ds.fill,
            order: ds.order,
            spanGaps: ds.spanGaps,
            showLine: ds.showLine,
          })),
          ...(averageDataset ? [averageDataset] : []),
        ],
      },
      options: {
        animation: false,
        normalized: enableDecimation,
        parsing: enableDecimation ? false : undefined,
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: cfg.type === "bar" ? "nearest" : "index",
          intersect: false,
        },
        plugins: {
          decimation: enableDecimation
            ? {
                enabled: true,
                algorithm: "lttb",
                samples: 1000,
              }
            : {
                enabled: false,
              },
          legend: {
            display: true,
          },
          hoverLine: {},
          tooltip: {
            mode: cfg.type === "bar" ? "nearest" : "index",
            intersect: false,
            callbacks: {
              title:
                cfg.tooltipTitle ||
                ((items) =>
                  items.length ? formatLabelTimestamp(items[0].label) : ""),
              label: (context) => {
                if (cfg.apiMode === "flow_histogram") {
                  const index = context.dataIndex;
                  const count = context.chart?._histCounts?.[index] ?? 0;
                  const percent = context.chart?._histPercents?.[index] ?? 0;
                  return `${percent.toFixed(2)}% (${count} punti)`;
                }
                const value = context.parsed?.y ?? context.parsed;
                if (value === null || value === undefined) {
                  return "";
                }
                return `${value}`;
              },
            },
            backgroundColor: "rgba(17, 24, 39, 0.4)",
          },
          zoom: {
            pan: {
              enabled: true,
              mode: "x",
              modifierKey: null,
              threshold: 2,
            },
            zoom: {
              wheel: {
                enabled: true,
              },
              pinch: {
                enabled: true,
              },
              drag: {
                enabled: true,
                borderColor: "rgba(29, 78, 216, 0.4)",
                borderWidth: 1,
                backgroundColor: "rgba(29, 78, 216, 0.08)",
              },
              mode: "x",
            },
          },
        },
        scales: {
          x: {
            type: cfg.xScaleType,
            ticks: {
              callback: cfg.xTicksCallback,
              display: cfg.xTicksDisplay ?? false,
            },
            title: {
              display: Boolean(cfg.showRange || cfg.xTitle),
              text: cfg.xTitle || "",
            },
            grid: {
              color: "#fff",
            },
            border: {
              display: true,
              color: "rgba(17, 24, 39, 0.45)",
              width: 2,
            },
          },
          y: {
            beginAtZero: true,
            ticks: {
              maxTicksLimit: 5,
              precision: cfg.yTickPrecision ?? 0,
            },
            title: {
              display: Boolean(cfg.yTitle),
              text: cfg.yTitle || "",
            },
            grid: {
              color: "#fff",
            },
            border: {
              display: true,
              color: "rgba(17, 24, 39, 0.2)",
              width: 1,
            },
          },
        },
      },
      plugins: [hoverLinePlugin],
    });

    const applyRangeLabel = (timestamps) => {
      if (!cfg.showRange || !timestamps.length) {
        return;
      }
      const first = timestamps[0];
      const last = timestamps[timestamps.length - 1];
      if (chart.options.scales?.x?.title) {
        chart.options.scales.x.title.text = `${formatTimestamp(
          first
        )} -> ${formatTimestamp(last)} (${rangeKey})`;
      }
    };

    if (cfg.useApi) {
      const misuratoreId = canvas.getAttribute("data-misuratore");
      const apiBase =
        cfg.apiMode === "duration_curve"
          ? "/portale/api/duration-curve/"
          : cfg.apiMode === "flow_histogram"
            ? "/portale/api/flow-histogram/"
            : "/portale/api/measurements/";
      const apiUrl = misuratoreId
        ? cfg.apiMode === "flow_histogram"
          ? `${apiBase}?id_misuratore=${encodeURIComponent(misuratoreId)}`
          : `${apiBase}?id_misuratore=${encodeURIComponent(
              misuratoreId
            )}&range=${encodeURIComponent(rangeKey)}`
        : cfg.apiMode === "flow_histogram"
          ? apiBase
          : `${apiBase}?range=${encodeURIComponent(rangeKey)}`;

      const loadApiData = () => {
        setLoading(true);
        fetch(apiUrl)
          .then((response) => {
            if (!response.ok) {
              throw new Error("API error");
            }
            return response.json();
          })
          .then((data) => {
            console.log(`[charts] refreshed ${cfg.id} (${rangeKey})`);
            const isDurationCurve = cfg.apiMode === "duration_curve";
            const isHistogram = cfg.apiMode === "flow_histogram";
            const timestamps = isDurationCurve
              ? data?.exceedance_percent || []
              : isHistogram
                ? data?.range_start || []
                : data?.timestamps || [];
            if (!Array.isArray(timestamps)) {
              return;
            }
            chart.data.labels = timestamps;
            datasetConfigs.forEach((ds, index) => {
              const sourceValues = data[ds.source] || [];
              const parsedValues = sourceValues.map((value) => {
                if (value === null || value === undefined) {
                  return null;
                }
                const parsed = Number(value);
                return Number.isFinite(parsed) ? parsed : null;
              });
              if (isHistogram) {
                const mids = (data?.range_start || []).map((start, i) => {
                  const end = data?.range_end?.[i];
                  if (end === null || end === undefined) {
                    return Number(start);
                  }
                  return (Number(start) + Number(end)) / 2;
                });
                chart._histCounts = (data?.count || []).map((value) =>
                  Number.isFinite(Number(value)) ? Number(value) : 0
                );
                chart._histPercents = (data?.percent || []).map((value) =>
                  Number.isFinite(Number(value)) ? Number(value) : 0
                );
                chart._histRanges = (data?.range_start || []).map((start, i) => ({
                  start: Number(start),
                  end: Number(data?.range_end?.[i]),
                }));
                chart.data.datasets[index].data = parsedValues.map((value, i) =>
                  value === null ? null : { x: mids[i], y: value }
                );
              } else {
                const useXYPoints = enableDecimation || isDurationCurve;
                chart.data.datasets[index].data = useXYPoints
                  ? parsedValues.map((value, i) =>
                      value === null ? null : { x: timestamps[i], y: value }
                    )
                  : parsedValues;
              }
            });
            if (!isHistogram) {
              applyRangeLabel(timestamps);
            }
            let maxValue = 0;
            datasetConfigs.forEach((ds) => {
              const sourceValues = data[ds.source] || [];
              sourceValues.forEach((value) => {
                const parsed = Number(value);
                if (!Number.isFinite(parsed)) {
                  return;
                }
                if (parsed > maxValue) {
                  maxValue = parsed;
                }
              });
            });
            const avgNumeric = parseAverageValue(avgValue);
            const boundedMax = Number.isFinite(avgNumeric)
              ? Math.max(maxValue, avgNumeric)
              : maxValue;
            if (chart.options.scales?.y) {
              chart.options.scales.y.suggestedMax = boundedMax * 1.1;
            }
            if (cfg.showAverage) {
              updateAverageLine(chart, avgValue);
            }
            chart.update("none");
          })
          .catch(() => {
            // keep dummy chart if API fails
          })
          .finally(() => {
            setLoading(false);
          });
      };

      loadApiData();

      if (rangeKey === "24h") {
        const intervalId = window.setInterval(loadApiData, POLL_INTERVAL_MS);
        pollingIntervals.set(cfg.id, intervalId);
      }
    } else {
      setLoading(false);
    }

    if (cfg.showAverage) {
      updateAverageLine(chart, avgValue);
    }
    instances.set(cfg.id, chart);
    applyRangeLabel(chart.data.labels || []);
    return chart;
  };
  // #endregion Chart Factory

  // #region Range Buttons
  const setRangeButtons = (rangeKey) => {
    const buttons = document.querySelectorAll(".range-btn");
    buttons.forEach((button) => {
      button.classList.toggle(
        "is-active",
        button.getAttribute("data-range") === rangeKey
      );
    });
  };

  const initCharts = (rangeKey) => {
    instances.forEach((chartInstance) => {
      chartInstance.destroy();
    });
    instances.clear();
    pollingIntervals.forEach((intervalId) => {
      window.clearInterval(intervalId);
    });
    pollingIntervals.clear();
    charts.forEach((cfg) => {
      createChart(cfg, rangeKey);
    });
  };

  const defaultRange = "24h";
  setRangeButtons(defaultRange);
  initCharts(defaultRange);

  const rangeButtons = document.querySelectorAll(".range-btn");
  rangeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const rangeKey = button.getAttribute("data-range") || defaultRange;
      setRangeButtons(rangeKey);
      initCharts(rangeKey);
    });
  });

  // #endregion Range Buttons

  // #region Chart Controls

  if (!grid) {
    return;
  }

  const resetButtons = grid.querySelectorAll(".chart-reset");
  resetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-target");
      const targetChart = targetId ? instances.get(targetId) : null;
      if (targetChart && typeof targetChart.resetZoom === "function") {
        targetChart.resetZoom();
      }
    });
  });

  const zoomButtons = grid.querySelectorAll(".chart-zoom");
  zoomButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-target");
      if (!targetId) {
        return;
      }

      const targetCanvas = document.getElementById(targetId);
      const targetCard = targetCanvas ? targetCanvas.closest(".chart-card") : null;
      if (!targetCard) {
        return;
      }

      const isZoomed = grid.classList.contains("is-zoomed");
      const cards = grid.querySelectorAll(".chart-card");
      if (!isZoomed) {
        grid.classList.add("is-zoomed");
        const gridHeight = grid.clientHeight;
        const footerGap = 16;
        if (gridHeight) {
          grid.style.height = `${gridHeight}px`;
        }
        cards.forEach((card) => {
          if (card === targetCard) {
            card.classList.add("is-zoomed");
            card.classList.remove("is-dim");
          } else {
            card.classList.add("is-dim");
            card.classList.remove("is-zoomed");
          }
        });
        button.textContent = "Esci";
        if (gridHeight && targetCard) {
          const zoomHeight = Math.max(0, gridHeight - footerGap);
          targetCard.style.height = `${zoomHeight}px`;
          const canvas = targetCard.querySelector("canvas");
          if (canvas) {
            canvas.style.height = "100%";
          }
        }
      } else {
        grid.classList.remove("is-zoomed");
        grid.style.height = "";
        cards.forEach((card) => {
          card.classList.remove("is-zoomed");
          card.classList.remove("is-dim");
          card.style.height = "";
        });
        zoomButtons.forEach((btn) => {
          btn.textContent = "Zoom";
        });
      }

      requestAnimationFrame(() => {
        instances.forEach((chartInstance) => {
          if (chartInstance?.canvas) {
            chartInstance.canvas.style.width = "100%";
            chartInstance.canvas.style.height = "100%";
            chartInstance.canvas.removeAttribute("width");
            chartInstance.canvas.removeAttribute("height");
          }
          chartInstance.resize();
        });
        setTimeout(() => {
          instances.forEach((chartInstance) => {
            chartInstance.resize();
          });
        }, 0);
      });
    });
  });
  // #endregion Chart Controls
});
