/*
Questo script gestisce il pannello di rendimento e potenza, recuperando i dati
da un endpoint API e aggiornando dinamicamente i valori visualizzati.
Utilizza un meccanismo di retry esponenziale per gestire eventuali errori di rete
o server, e aggiorna i dati ogni 5 minuti.
*/


document.addEventListener("DOMContentLoaded", () => {
    
    
    const POLL_INTERVAL_MS = 60000*5; // 5 minutes
    const WATER_DENSITY = 1000;
    const GRAVITY = 9.81;

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
        const btnModeAuto = document.getElementById("btn-mode-auto");
        const btnModeManual = document.getElementById("btn-mode-manual");
        const tableAuto = document.getElementById("table-calc-auto");
        const tableManual = document.getElementById("table-calc-manual");
        const setCalcMode = (mode) => {
            if (!tableAuto || !tableManual || !btnModeAuto || !btnModeManual) {
                return;
            }
            const isAuto = mode === "auto";
            tableAuto.classList.toggle("is-hidden", !isAuto);
            tableManual.classList.toggle("is-hidden", isAuto);
            tableAuto.style.display = isAuto ? "table" : "none";
            tableManual.style.display = isAuto ? "none" : "table";
            btnModeAuto.classList.toggle("is-active", isAuto);
            btnModeManual.classList.toggle("is-active", !isAuto);
        };

        if (btnModeAuto) {
            btnModeAuto.addEventListener("click", () => setCalcMode("auto"));
        }
        if (btnModeManual) {
            btnModeManual.addEventListener("click", () => setCalcMode("manual"));
        }
        setCalcMode("auto");

        const etaEl = document.getElementById("eta-30m");
        const powerEl = document.getElementById("power-30m");
        const headInput = document.getElementById("input-head");
        const flow30mEl = document.getElementById("flow-30m");
        const qM3s30mEl = document.getElementById("q-m3s-30m");
        const flowManualInput = document.getElementById("input-flow-manual");
        const etaManualInput = document.getElementById("input-eta-manual");
        const headManualInput = document.getElementById("input-head-manual");
        const qM3sManualEl = document.getElementById("q-m3s-manual");
        const powerManualEl = document.getElementById("power-manual");
        const btnCalcManualPower = document.getElementById("btn-calc-manual-power");
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

        const updateManualDerivedQ = () => {
            if (!flowManualInput || !qM3sManualEl) {
                return;
            }
            const flowManual = Number(flowManualInput.value);
            if (!Number.isFinite(flowManual) || flowManual < 0) {
                qM3sManualEl.textContent = "--";
                return;
            }
            qM3sManualEl.textContent = formatNumber(flowManual / 1000.0, 4);
        };

        const calculateManualPower = () => {
            if (!flowManualInput || !etaManualInput || !headManualInput || !powerManualEl) {
                return;
            }
            const flowManual = Number(flowManualInput.value);
            const etaManual = Number(etaManualInput.value);
            const headManual = Number(headManualInput.value);
            if (
                !Number.isFinite(flowManual) ||
                flowManual < 0 ||
                !Number.isFinite(etaManual) ||
                etaManual < 0 ||
                etaManual > 1 ||
                !Number.isFinite(headManual) ||
                headManual <= 0
            ) {
                powerManualEl.textContent = "--";
                return;
            }
            const qM3s = flowManual / 1000.0;
            const powerKw = Math.max(0, (WATER_DENSITY * GRAVITY * qM3s * headManual * etaManual) / 1000.0);
            powerManualEl.textContent = formatNumber(powerKw, 2);
        };

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
            const powerKw = Math.max(0, 9.81 * headVal * qM3s * lastEta);
            powerEl.textContent = formatNumber(powerKw, 2);
            if (qM3s30mEl) {
                qM3s30mEl.textContent = formatNumber(qM3s, 4);
            }
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
                if (flow30mEl) {
                    flow30mEl.textContent = Number.isFinite(flowVal) ? formatNumber(flowVal, 2) : "--";
                }
                if (qM3s30mEl) {
                    qM3s30mEl.textContent = Number.isFinite(flowVal) ? formatNumber(flowVal / 1000.0, 4) : "--";
                }

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
                if (Number.isFinite(headVal) && headManualInput && !headManualInput.value) {
                    headManualInput.value = headVal.toFixed(1);
                }
                if (Number.isFinite(etaVal) && etaManualInput && !etaManualInput.value) {
                    etaManualInput.value = etaVal.toFixed(3);
                }
                if (Number.isFinite(flowVal) && flowManualInput && !flowManualInput.value) {
                    flowManualInput.value = flowVal.toFixed(2);
                    updateManualDerivedQ();
                }
            } catch (err) {
                console.error("[rendimento] fetch failed:", err);
            }
        };

        headInput.addEventListener("input", updatePower);
        if (flowManualInput) {
            flowManualInput.addEventListener("input", updateManualDerivedQ);
        }
        if (btnCalcManualPower) {
            btnCalcManualPower.addEventListener("click", calculateManualPower);
        }
        if (etaManualInput) {
            etaManualInput.addEventListener("input", calculateManualPower);
        }
        if (headManualInput) {
            headManualInput.addEventListener("input", calculateManualPower);
        }
        loadRendimento();
        window.setInterval(loadRendimento, POLL_INTERVAL_MS);
    };

    initRendimentoPanel();
});
