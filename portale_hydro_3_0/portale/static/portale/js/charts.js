document.addEventListener("DOMContentLoaded", () => {
    if (typeof Chart === "undefined") {
        return;
    }

    if (window.ChartZoom) {
        Chart.register(window.ChartZoom);
    }

    // Core constants.
    const DEFAULT_LABELS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
    const POLL_INTERVAL_MS = 60000;
    const FLOW_DECIMATION_THRESHOLD = 1250;
    const GAP_THRESHOLD_SHORT_MS = 2 * 60 * 60 * 1000;
    const GAP_THRESHOLD_LONG_MS = 3 * 24 * 60 * 60 * 1000;
    const LONG_GAP_RANGES = new Set(["6m", "1y", "all"]);

    const grid = document.querySelector(".facility-plot-grid");
    const instances = new Map();
    const pollingIntervals = new Map();

    const isFlowChart = (cfg) => cfg.id === "chart-flow-rate";
    const isDurationCurve = (cfg) => cfg.apiMode === "duration_curve";
    const isHistogram = (cfg) => cfg.apiMode === "flow_histogram";
    const getGapThresholdMs = (rangeKey) =>
        LONG_GAP_RANGES.has(rangeKey)
            ? GAP_THRESHOLD_LONG_MS
            : GAP_THRESHOLD_SHORT_MS;

    // Formatters.
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

    const formatTimestampFull = (value) => {
        const date = value ? new Date(value) : null;
        if (!date || Number.isNaN(date.getTime())) {
            return "";
        }
        const yyyy = String(date.getFullYear());
        const mm = String(date.getMonth() + 1).padStart(2, "0");
        const dd = String(date.getDate()).padStart(2, "0");
        const hh = String(date.getHours()).padStart(2, "0");
        const min = String(date.getMinutes()).padStart(2, "0");
        const ss = String(date.getSeconds()).padStart(2, "0");
        return `${dd}/${mm}/${yyyy} ${hh}:${min}:${ss}`;
    };

    const formatLabelTimestamp = (value) => formatTimestamp(value) || value || "";

    // Numeric helpers.
    const parseNumberArray = (values) =>
        values.map((value) => {
            if (value === null || value === undefined) {
                return null;
            }
            const parsed = Number(value);
            return Number.isFinite(parsed) ? parsed : null;
        });

    const toMillis = (value) => {
        const parsed = Date.parse(value);
        return Number.isFinite(parsed) ? parsed : null;
    };

    const computeYAtX = (xs, ys, xTarget) => {
        if (!Array.isArray(xs) || !Array.isArray(ys)) {
            return null;
        }
        let prev = null;
        for (let i = 0; i < xs.length; i += 1) {
            const x = Number(xs[i]);
            const y = ys[i];
            if (!Number.isFinite(x) || !Number.isFinite(y)) {
                continue;
            }
            if (x === xTarget) {
                return y;
            }
            if (x < xTarget) {
                prev = { x, y };
                continue;
            }
            if (x > xTarget && prev) {
                const ratio = (xTarget - prev.x) / (x - prev.x);
                return prev.y + (y - prev.y) * ratio;
            }
            if (x > xTarget) {
                return null;
            }
        }
        return null;
    };

    const computeGapRanges = (xValues, rangeKey) => {
        const finiteXs = xValues.filter((v) => Number.isFinite(v));
        const gapThresholdMs = getGapThresholdMs(rangeKey);
        const ranges = [];
        for (let i = 0; i < finiteXs.length - 1; i += 1) {
            const a = finiteXs[i];
            const b = finiteXs[i + 1];
            if (b - a > gapThresholdMs) {
                ranges.push({ start: a, end: b });
            }
        }
        return ranges;
    };

    const buildFlowPointsWithGaps = (xValues, values, rangeKey) => {
        const gapThresholdMs = getGapThresholdMs(rangeKey);
        const useMidpointNull = LONG_GAP_RANGES.has(rangeKey);
        const points = [];
        for (let i = 0; i < values.length; i += 1) {
            const value = values[i];
            const x = xValues[i];
            if (value === null || x === null) {
                points.push(null);
            } else {
                points.push({ x, y: value });
            }
            const nextX = xValues[i + 1];
            if (
                Number.isFinite(x) &&
                Number.isFinite(nextX) &&
                nextX - x > gapThresholdMs
            ) {
                points.push(
                    useMidpointNull ? { x: x + (nextX - x) / 2, y: null } : null,
                );
            }
        }
        return points;
    };

    const buildFlowPointsWithGapsShort = (xValues, values, rangeKey) => {
        const gapThresholdMs = getGapThresholdMs(rangeKey);
        const points = [];
        for (let i = 0; i < values.length; i += 1) {
            const value = values[i];
            const x = xValues[i];
            
            // Aggiungi il punto corrente se valido
            if (value !== null && x !== null) {
                points.push({ x, y: value });
            }
            
            // Controlla se c'è un gap con il prossimo punto
            if (i < values.length - 1) {
                const nextX = xValues[i + 1];
                const nextValue = values[i + 1];
                
                if (
                    Number.isFinite(x) &&
                    Number.isFinite(nextX) &&
                    nextX - x > gapThresholdMs &&
                    value !== null &&
                    nextValue !== null
                ) {
                    // Inserisci un punto con y: NaN per interrompere la linea
                    points.push({ x: x + (nextX - x) / 2, y: NaN });
                }
            }
        }
        return points;
    };

    // Average line helpers (flow chart only).
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
            "all": "data-avg-all",
        };
        const rawValue = canvas.getAttribute(attrMap[rangeKey]);
        if (rawValue === "") {
            return null;
        }
        return rawValue ?? null;
    };

    // Plugins.
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

    const gapShadingPlugin = {
        id: "gapShading",
        beforeDatasetsDraw(chart, _args, opts) {
            const gaps = chart._gapRanges || [];
            if (!gaps.length) {
                return;
            }
            const xScale = chart.scales?.x;
            const { ctx, chartArea } = chart;
            if (!xScale || !chartArea) {
                return;
            }
            ctx.save();
            ctx.fillStyle = opts?.color || "rgba(220, 38, 38, 0.08)";
            gaps.forEach((gap) => {
                const xStart = xScale.getPixelForValue(gap.start);
                const xEnd = xScale.getPixelForValue(gap.end);
                if (!Number.isFinite(xStart) || !Number.isFinite(xEnd)) {
                    return;
                }
                const left = Math.min(xStart, xEnd);
                const width = Math.abs(xEnd - xStart);
                if (width <= 0) {
                    return;
                }
                ctx.fillRect(
                    left,
                    chartArea.top,
                    width,
                    chartArea.bottom - chartArea.top,
                );
            });
            ctx.restore();
        },
    };

    const staticVLinePlugin = {
        id: "staticVLine",
        beforeDatasetsDraw(chart, _args, opts) {
            const xValue = opts?.xValue;
            const yValue = opts?.yValue;
            const yZeroValue = opts?.yZeroValue;
            const xScale = chart.scales?.x;
            const yScale = chart.scales?.y;
            const { ctx, chartArea } = chart;
            if (!xScale || !chartArea) {
                return;
            }
            ctx.save();
            if (xValue !== null && xValue !== undefined) {
                const x = xScale.getPixelForValue(xValue);
                if (Number.isFinite(x)) {
                    ctx.beginPath();
                    ctx.moveTo(x, chartArea.top);
                    ctx.lineTo(x, chartArea.bottom);
                    ctx.lineWidth = opts?.lineWidth ?? 1;
                    ctx.strokeStyle = opts?.color || "rgba(29, 78, 216, 0.8)";
                    ctx.setLineDash(opts?.dash || [4, 4]);
                    ctx.stroke();
                }
            }
            if (yZeroValue !== null && yZeroValue !== undefined && yScale) {
                const y0 = yScale.getPixelForValue(yZeroValue);
                if (Number.isFinite(y0)) {
                    ctx.beginPath();
                    ctx.moveTo(chartArea.left, y0);
                    ctx.lineTo(chartArea.right, y0);
                    ctx.lineWidth = opts?.yZeroLineWidth ?? opts?.lineWidth ?? 1;
                    ctx.strokeStyle = opts?.yZeroColor || "rgba(17, 24, 39, 0.6)";
                    ctx.setLineDash(opts?.yZeroDash || []);
                    ctx.stroke();
                }
            }
            if (yValue !== null && yValue !== undefined && yScale) {
                const y = yScale.getPixelForValue(yValue);
                if (Number.isFinite(y)) {
                    ctx.beginPath();
                    ctx.moveTo(chartArea.left, y);
                    ctx.lineTo(chartArea.right, y);
                    ctx.lineWidth = opts?.yLineWidth ?? opts?.lineWidth ?? 1;
                    ctx.strokeStyle = opts?.yColor || "rgba(29, 78, 216, 0.6)";
                    ctx.setLineDash(opts?.yDash || [4, 4]);
                    ctx.stroke();
                }
            }
            ctx.restore();
        },
        afterDraw(chart, _args, opts) {
            const xValue = opts?.xValue;
            const label = opts?.label;
            if (!label || xValue === null || xValue === undefined) {
                return;
            }
            const xScale = chart.scales?.x;
            const { ctx, chartArea } = chart;
            if (!xScale || !chartArea) {
                return;
            }
            const x = xScale.getPixelForValue(xValue);
            if (!Number.isFinite(x)) {
                return;
            }
            ctx.save();
            ctx.fillStyle = opts?.labelColor || "#111827";
            ctx.font = opts?.labelFont || "12px Arial, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            ctx.fillText(label, x, chartArea.bottom + 6);
            ctx.restore();
        },
        afterBuildTicks(chart, _args, opts) {
            const yValue = opts?.yValue;
            const yZeroValue = opts?.yZeroValue;
            const yScale = chart.scales?.y;
            if (!yScale || !Array.isArray(yScale.ticks)) {
                return;
            }
            if (yValue !== null && yValue !== undefined) {
                const exists = yScale.ticks.some(
                    (tick) => Number(tick.value) === Number(yValue),
                );
                if (!exists && Number.isFinite(Number(yValue))) {
                    yScale.ticks.push({ value: Number(yValue) });
                    yScale.ticks.sort((a, b) => a.value - b.value);
                }
            }
            if (yZeroValue !== null && yZeroValue !== undefined) {
                const exists = yScale.ticks.some(
                    (tick) => Number(tick.value) === Number(yZeroValue),
                );
                if (!exists && Number.isFinite(Number(yZeroValue))) {
                    yScale.ticks.push({ value: Number(yZeroValue) });
                    yScale.ticks.sort((a, b) => a.value - b.value);
                }
            }
        },
    };

    // Chart configs.
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
            xScaleType: "linear",
            xTitle: "",
            xTicksCallback: function (value) {
                if (value === this.min || value === this.max) {
                    return formatTimestampFull(value);
                }
                return "";
            },
            xTicksDisplay: true,
            xTicksMaxRotation: 0,
            xTicksMinRotation: 0,
            xTicksMirror: false,
            xTicksPadding: 8,
            xTicksAutoSkip: false,
            xTicksMaxTicksLimit: 2,
            showRange: true,
            showAverage: true,
            datasets: [
                {
                    label: "Portata (raw)",
                    color: "#6b728089",
                    fill: false,
                    source: "flow_ls_raw",
                    order: 2,
                    spanGaps: false,
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
                    spanGaps: false,
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
            xMin: 0,
            xMax: 100,
            xTicksAutoSkip: false,
            xTicksIncludeBounds: true,
            yTitle: "Portata (l/s)",
            yTicksAutoSkip: false,
            yTicksIncludeBounds: true,
            xTicksCallback: (value) => {
                const numeric = Number(value);
                if (!Number.isFinite(numeric)) {
                    return "";
                }
                if (numeric === 0 || numeric === 80 || numeric === 100) {
                    return `${numeric}%`;
                }
                return "";
            },
            xTicksDisplay: true,
            tooltipTitle: (items) =>
                items.length ? `${items[0].parsed.x.toFixed(1)}%` : "",
            showAverage: false,
            staticVLineX: 80,
            datasets: [
                {
                    label: "Curva di durata",
                    color: "#f59e0b",
                    fillColor: "rgba(245, 158, 11, 0.18)",
                    fill: false,
                    source: "flow_ls_smoothed",
                    order: 1,
                    pointRadius: 1,
                    pointHoverRadius: 2,
                    borderWidth: 2,
                },
            ],
        },
    ];

    // Chart factory: create, load data, and wire controls.
    const createChart = (cfg, rangeKey) => {
        const canvas = document.getElementById(cfg.id);
        if (!canvas) return null;

        const chartCard = canvas.closest(".chart-card");
        const decimationInfoButton = chartCard?.querySelector(
            "[data-decimation-info]",
        );

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

        const decimationThreshold = isFlowChart(cfg)
            ? FLOW_DECIMATION_THRESHOLD
            : null;
        let decimationEnabled =
            cfg.useApi &&
            cfg.type === "line" &&
            cfg.xScaleType === "linear" &&
            decimationThreshold !== null; // FIXED: era === null

        const setDecimationEnabled = (isEnabled) => {
            decimationEnabled = Boolean(isEnabled);
            if (chart?.options) {
                // FIXED: Logica unificata per tutti i tipi di grafico
                chart.options.parsing = decimationEnabled ? false : undefined;
                chart.options.normalized = decimationEnabled;
                if (chart.options.plugins?.decimation) {
                    chart.options.plugins.decimation.enabled = decimationEnabled;
                }
            }
            if (decimationInfoButton) {
                decimationInfoButton.style.display = decimationEnabled ? "" : "none";
            }
        };

        const chart = new Chart(canvas, {
            type: cfg.type,
            data: {
                labels: cfg.labels || DEFAULT_LABELS,
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
                normalized: decimationEnabled,
                parsing: decimationEnabled ? false : undefined,
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: cfg.type === "bar" ? "nearest" : "index",
                    intersect: false,
                },
                plugins: {
                    decimation: decimationEnabled
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
                    staticVLine:
                        cfg.staticVLineX !== undefined
                            ? {
                                xValue: cfg.staticVLineX,
                                label: "",
                                color: "rgba(29, 78, 216, 0.85)",
                                yColor: "rgba(29, 78, 216, 0.7)",
                                lineWidth: 2,
                                yLineWidth: 2,
                                yZeroValue: 0,
                                yZeroColor: "rgba(17, 24, 39, 0.25)",
                                yZeroLineWidth: 2,
                                dash: [6, 6],
                            }
                            : {},
                    tooltip: {
                        mode: cfg.type === "bar" ? "nearest" : "index",
                        intersect: false,
                        callbacks: {
                            title:
                                cfg.tooltipTitle ||
                                ((items) => {
                                    if (!items.length) {
                                        return "";
                                    }
                                    if (isFlowChart(cfg)) {
                                        const x = items[0]?.parsed?.x;
                                        return formatTimestampFull(x);
                                    }
                                    return formatLabelTimestamp(items[0].label);
                                }),
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
                        min: cfg.xMin ?? undefined,
                        max: cfg.xMax ?? undefined,
                        ticks: {
                            callback: cfg.xTicksCallback,
                            display: cfg.xTicksDisplay ?? false,
                            autoSkip: cfg.xTicksAutoSkip ?? true,
                            includeBounds: cfg.xTicksIncludeBounds ?? undefined,
                            maxRotation: cfg.xTicksMaxRotation ?? undefined,
                            minRotation: cfg.xTicksMinRotation ?? undefined,
                            mirror: cfg.xTicksMirror ?? undefined,
                            padding: cfg.xTicksPadding ?? undefined,
                            maxTicksLimit: cfg.xTicksMaxTicksLimit ?? undefined,
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
                            autoSkip: cfg.yTicksAutoSkip ?? true,
                            includeBounds: cfg.yTicksIncludeBounds ?? undefined,
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
            plugins: [hoverLinePlugin, gapShadingPlugin, staticVLinePlugin],
        });

        if (decimationThreshold !== null) {
            setDecimationEnabled(false);
        } else {
            setDecimationEnabled(decimationEnabled);
        }

        const applyRangeLabel = (timestamps) => {
            if (isFlowChart(cfg) || !cfg.showRange || !timestamps.length) {
                return;
            }
            const first = timestamps[0];
            const last = timestamps[timestamps.length - 1];
            if (chart.options.scales?.x?.title) {
                chart.options.scales.x.title.text = `${formatTimestamp(
                    first,
                )} -> ${formatTimestamp(last)} (${rangeKey})`;
            }
        };

        if (cfg.useApi) {
            const misuratoreId = canvas.getAttribute("data-misuratore");
            const apiBase = isDurationCurve(cfg)
                ? "/portale/api/duration-curve/"
                : isHistogram(cfg)
                    ? "/portale/api/flow-histogram/"
                    : "/portale/api/measurements/";

            const apiUrl = misuratoreId
                ? isHistogram(cfg)
                    ? `${apiBase}?id_misuratore=${encodeURIComponent(misuratoreId)}`
                    : `${apiBase}?id_misuratore=${encodeURIComponent(
                        misuratoreId,
                    )}&range=${encodeURIComponent(rangeKey)}`
                : isHistogram(cfg)
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

                        const timestamps = isDurationCurve(cfg)
                            ? data?.exceedance_percent || []
                            : isHistogram(cfg)
                                ? data?.range_start || []
                                : data?.timestamps || [];
                        if (!Array.isArray(timestamps)) {
                            return;
                        }

                        const xValues = isFlowChart(cfg)
                            ? timestamps.map(toMillis)
                            : timestamps;

                        chart.data.labels = xValues;

                        if (isFlowChart(cfg) && chart.options.scales?.x) {
                            const finiteXs = xValues.filter((v) => Number.isFinite(v));
                            if (finiteXs.length) {
                                chart.options.scales.x.min = Math.min(...finiteXs);
                                chart.options.scales.x.max = Math.max(...finiteXs);
                            }
                            chart._gapRanges = computeGapRanges(xValues, rangeKey);
                        }

                        let durationValues = null;
                        let durationFilteredPoints = null;

                        datasetConfigs.forEach((ds, index) => {
                            const sourceValues = data[ds.source] || [];
                            const parsedValues = parseNumberArray(sourceValues);

                            if (isFlowChart(cfg)) {
                                console.log(
                                    `[charts] ${cfg.id} dataset "${ds.label}" points received: ${parsedValues.length}`,
                                );
                            }

                            if (isDurationCurve(cfg) && durationValues === null) {
                                durationValues = parsedValues;
                            }

                            if (isFlowChart(cfg) && decimationThreshold) {
                                const shouldDecimate =
                                    parsedValues.length > decimationThreshold;
                                if (shouldDecimate !== decimationEnabled) {
                                    setDecimationEnabled(shouldDecimate);
                                }
                            }

                            if (isHistogram(cfg)) {
                                const mids = (data?.range_start || []).map((start, i) => {
                                    const end = data?.range_end?.[i];
                                    if (end === null || end === undefined) {
                                        return Number(start);
                                    }
                                    return (Number(start) + Number(end)) / 2;
                                });
                                chart._histCounts = (data?.count || []).map((value) =>
                                    Number.isFinite(Number(value)) ? Number(value) : 0,
                                );
                                chart._histPercents = (data?.percent || []).map((value) =>
                                    Number.isFinite(Number(value)) ? Number(value) : 0,
                                );
                                chart._histRanges = (data?.range_start || []).map(
                                    (start, i) => ({
                                        start: Number(start),
                                        end: Number(data?.range_end?.[i]),
                                    }),
                                );
                                chart.data.datasets[index].data = parsedValues.map(
                                    (value, i) =>
                                        value === null ? null : { x: mids[i], y: value },
                                );
                                return;
                            }

                            const useXYPoints =
                                decimationEnabled || isDurationCurve(cfg);

                            if (isDurationCurve(cfg) && useXYPoints) {
                                const filteredPoints = [];
                                parsedValues.forEach((value, i) => {
                                    if (value === null || value < -50) {
                                        return;
                                    }
                                    filteredPoints.push({ x: timestamps[i], y: value });
                                });
                                chart.data.datasets[index].data = filteredPoints;
                                if (durationFilteredPoints === null) {
                                    durationFilteredPoints = filteredPoints;
                                }
                                return;
                            }

                            if (isFlowChart(cfg)) {
                                console.log(`[charts] ${cfg.id} decimationEnabled: ${decimationEnabled}, points: ${parsedValues.length}`);
                                if (decimationEnabled) {
                                    // Con decimazione, usa la funzione originale
                                    chart.data.datasets[index].data = buildFlowPointsWithGaps(
                                        xValues,
                                        parsedValues,
                                        rangeKey,
                                    );
                                } else {
                                    // Senza decimazione, usa la funzione specifica per range brevi
                                    chart.data.datasets[index].data = buildFlowPointsWithGapsShort(
                                        xValues,
                                        parsedValues,
                                        rangeKey,
                                    );
                                }
                                return;
                            }

                            chart.data.datasets[index].data = useXYPoints
                                ? parsedValues.map((value, i) => {
                                    const x = xValues[i];
                                    return value === null || x === null
                                        ? null
                                        : { x, y: value };
                                })
                                : parsedValues;
                        });

                        if (!isHistogram(cfg) && !isFlowChart(cfg)) {
                            applyRangeLabel(timestamps);
                        }

                        if (isDurationCurve(cfg)) {
                            const y80 = computeYAtX(
                                timestamps,
                                durationValues || [],
                                cfg.staticVLineX,
                            );
                            if (chart.options.plugins?.staticVLine) {
                                chart.options.plugins.staticVLine.yValue = Number.isFinite(y80)
                                    ? y80
                                    : null;
                            }
                        }

                        let maxValue = 0;
                        let minValue = Number.POSITIVE_INFINITY;
                        if (isDurationCurve(cfg)) {
                            (durationFilteredPoints || []).forEach((point) => {
                                const value = point?.y;
                                if (!Number.isFinite(value)) {
                                    return;
                                }
                                if (value > maxValue) {
                                    maxValue = value;
                                }
                                if (value < minValue) {
                                    minValue = value;
                                }
                            });
                        } else {
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
                                    if (parsed < minValue) {
                                        minValue = parsed;
                                    }
                                });
                            });
                        }

                        const avgNumeric = parseAverageValue(avgValue);
                        const boundedMax = Number.isFinite(avgNumeric)
                            ? Math.max(maxValue, avgNumeric)
                            : maxValue;

                        if (chart.options.scales?.y) {
                            chart.options.scales.y.suggestedMax = boundedMax * 1.1;
                            if (isDurationCurve(cfg)) {
                                const boundedMin = Number.isFinite(minValue)
                                    ? Math.min(minValue, 0)
                                    : 0;
                                chart.options.scales.y.suggestedMin = boundedMin;
                            }
                        }

                        if (cfg.showAverage) {
                            updateAverageLine(chart, avgValue);
                        }

                        chart.update("none");

                        if (isFlowChart(cfg)) {
                            const firstDataset = chart.data.datasets[0];
                            const rawCount = firstDataset?.data?.length ?? 0;
                            setTimeout(() => {
                                const decimatedCount = Array.isArray(firstDataset?._decimated)
                                    ? firstDataset._decimated.length
                                    : rawCount;
                                console.log(
                                    `[charts] ${cfg.id} points after decimation: ${decimatedCount}`,
                                );
                            }, 0);
                        }
                    })
                    .catch(() => {
                        // Keep existing chart if API fails.
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
        if (!isFlowChart(cfg) && cfg.showRange) {
            applyRangeLabel(chart.data.labels || []);
        }
        return chart;
    };

    // Range buttons.
    const setRangeButtons = (rangeKey) => {
        const buttons = document.querySelectorAll(".range-btn");
        buttons.forEach((button) => {
            button.classList.toggle(
                "is-active",
                button.getAttribute("data-range") === rangeKey,
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

    // Chart controls (zoom/reset).
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
            const targetCard = targetCanvas
                ? targetCanvas.closest(".chart-card")
                : null;
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
});
