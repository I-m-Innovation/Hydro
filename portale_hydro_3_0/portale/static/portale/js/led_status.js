document.addEventListener("DOMContentLoaded", function() {
    const leds = document.querySelectorAll('[data-misuratore-id]');
    if(!leds.length){
        console.log("No LED elements found on the page.");
        return;
    }

    const API_ENDPOINT = '/portale/api/led-status/';
    const REFRESH_INTERVAL = 280000; // 280 seconds

    const setLedStatus = (ledElement, status) => {
        ledElement.classList.remove("status-green", "status-orange", "status-red", "status-gray");
        ledElement.classList.add(status);
    };
    
    const computeStatus = (lastIso) => {
        // Handle null or invalid dates
        if (!lastIso) {
            console.log("No latest measurement date provided.");
            return "status-gray"; // No data
        }
        if (Number.isNaN(lastIso.getTime())) {
            console.error("Invalid date:", lastIso);
            return "status-gray";
        }
        // Calculate the difference in hours
        const diffMs = Date.now() - lastIso.getTime();
        const diffHours = diffMs / (1000 * 60 * 60);
        // Determine status based on the time difference
        if (diffHours > 6 ) return "status-red";      // More than 6 hours
        if (diffHours > 2 ) return "status-orange";   // Between 2 and 6 hours
        return "status-green";                        // Less than 2 hours
    };

    const fetchJsonWithRetry = async (url, retries = 3, delayMs = 1000) => {
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
                    await new Promise((resolve) => setTimeout(resolve, delayMs));
                }
            }
        }
        throw lastError || new Error("Unknown fetch error");
    };

    let ledFetchInFlight = false;

    const GREY_RECHECK_BASE_MS = 3000; // 3 seconds
    const GREY_RECHECK_MAX_MS = 60000; // 60 seconds
    let greyRetryDelay = GREY_RECHECK_BASE_MS;
    let greyRetryTimer = null;

    const scheduleGreyRetry = () => {
        if (greyRetryTimer) {
            return;
        }
        greyRetryTimer = window.setTimeout(() => {
            greyRetryTimer = null;
            const hasGrey = Array.from(leds).some((led) =>
                led.classList.contains("status-gray"),
            );
            if (hasGrey) {
                updateLeds();
            } else {
                greyRetryDelay = GREY_RECHECK_BASE_MS;
            }
        }, greyRetryDelay);
    };

    const bumpGreyBackoff = () => {
        greyRetryDelay = Math.min(GREY_RECHECK_MAX_MS, Math.ceil(greyRetryDelay * 2));
    };

    const resetGreyBackoff = () => {
        greyRetryDelay = GREY_RECHECK_BASE_MS;
        if (greyRetryTimer) {
            window.clearTimeout(greyRetryTimer);
            greyRetryTimer = null;
        }
    };

    const updateLeds = () => {
        if (ledFetchInFlight) {
            return;
        }
        ledFetchInFlight = true;
        fetchJsonWithRetry(API_ENDPOINT, 3, 2000)
            .then((payload) => {
                const lastById = new Map();

                (payload.items || []).forEach(item => {
                    const id = String(item.id_misuratore);
                    const last = item.latest_measurement;
                    if (!id){
                        console.error("Missing id_misuratore in item:", item);
                        return;
                    } 
                    if (!last){
                        console.log(`No latest measurement for id ${id}.`);
                        return;
                    }
                    lastById.set(id, last);
                });

                leds.forEach(led => {
                    const misuratoreId = led.getAttribute('data-misuratore-id');
                    const lastIsoStr = lastById.get(String(misuratoreId));
                    const lastIso = lastIsoStr ? new Date(lastIsoStr) : null;
                    const status = computeStatus(lastIso);
                    setLedStatus(led, status);
                });

                const hasGrey = Array.from(leds).some((led) =>
                    led.classList.contains("status-gray"),
                );
                if (hasGrey) {
                    bumpGreyBackoff();
                    scheduleGreyRetry();
                } else {
                    resetGreyBackoff();
                }
            })
            .catch(error => {
                console.error("Error fetching LED status data after retries:", error);
                leds.forEach(led => setLedStatus(led, "status-gray"));
                bumpGreyBackoff();
                scheduleGreyRetry();
            })
            .finally(() => {
                ledFetchInFlight = false;
            });
    };

    window.refreshLedStatus = updateLeds;
    document.addEventListener("led-status:refresh", updateLeds);

    updateLeds();
    setInterval(updateLeds, REFRESH_INTERVAL);


/*	
id_misuratore	"CU4"
latest_measurement	"2024-01-25T07:23:30Z"
*/
});
