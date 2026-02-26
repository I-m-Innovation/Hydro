document.addEventListener("DOMContentLoaded", () => {
    const POLL_INTERVAL_MS = 60000*5; // 5 minutes

    const formatNumber = (value, decimals = 2) => {
        if (!Number.isFinite(value)) {
            return "--";
        }
        return value.toFixed(decimals);
    };

    const fetchJsonWithRetry = async (url, retries = 2, delayMs = 1000, maxDelayMs = 10000) => {
        let lastError = null;
        for (let attempt = 0; attempt <= retries; attempt += 1) {
            try {
                const response = await fetch(url, { cache: "no-store" });
                const text = await response.text();
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${text.slice(0, 200)}`);
                }
                return JSON.parse(text);
            } catch (err) {
                lastError = err;
                if (attempt < retries) {
                    const backoff = Math.min(maxDelayMs, delayMs * (2 ** attempt));
                    await new Promise((resolve) => setTimeout(resolve, backoff));
                }
            }
        }
        throw lastError || new Error("Unknown fetch error");
    };

    const initRendimentoPanel = () => {
        const etaEl = document.getElementById("eta-30m");
        const powerEl = document.getElementById("power-30m");
        const headInput = document.getElementById("input-head");
        const flowCanvas = document.getElementById("chart-flow-rate");
        if (!etaEl || !powerEl || !headInput || !flowCanvas) {
            return;
        }

        const idMisuratore = flowCanvas.getAttribute("data-misuratore");
        if (!idMisuratore) {
            return;
        }

        let lastEta = null;
        let lastFlowLs = null;

        const updatePower = () => {
            const headVal = Number(headInput.value);
            if (
                !Number.isFinite(headVal) ||
                headVal <= 0 ||
                !Number.isFinite(lastEta) ||
                !Number.isFinite(lastFlowLs)
            ) {
                return;
            }
            const qM3s = lastFlowLs / 1000.0;
            const powerKw = 9.81 * headVal * qM3s * lastEta;
            powerEl.textContent = formatNumber(powerKw, 2);
        };

        const loadRendimento = async () => {
            try {
                const url = `/portale/api/rendimento-potenza/?id_misuratore=${encodeURIComponent(idMisuratore)}`;
                const data = await fetchJsonWithRetry(url, 2, 1000);
                const isStale = Boolean(data?.is_stale);
                const etaVal = Number(data?.eta);
                const powerVal = Number(data?.power_kw);
                const headVal = Number(data?.head_m);
                const flowVal = Number(data?.flow_ls_avg_30m);

                lastEta = Number.isFinite(etaVal) ? etaVal : null;
                lastFlowLs = Number.isFinite(flowVal) ? flowVal : null;

                if (isStale) {
                    etaEl.textContent = "No data";
                    powerEl.textContent = "No data";
                    return;
                }

                etaEl.textContent = Number.isFinite(etaVal) ? formatNumber(etaVal, 3) : "--";
                powerEl.textContent = Number.isFinite(powerVal) ? formatNumber(powerVal, 2) : "--";

                if (Number.isFinite(headVal) && (!headInput.value || headInput.value === "--")) {
                    headInput.value = headVal.toFixed(1);
                }
            } catch (err) {
                console.error("[rendimento] fetch failed:", err);
            }
        };

        headInput.addEventListener("input", updatePower);
        loadRendimento();
        window.setInterval(loadRendimento, POLL_INTERVAL_MS);
    };

    initRendimentoPanel();
});
