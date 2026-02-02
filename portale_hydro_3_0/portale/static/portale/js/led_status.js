document.addEventListener("DOMContentLoaded", function() {
    const leds = document.querySelectorAll('[data-misuratore-id]');
    if(!leds.length){
        console.log("No LED elements found on the page.");
        return;
    }

    const API_ENDPOINT = '/portale/api/led-status/';
    const REFRESH_INTERVAL = 60000; // 60 seconds

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

    const updateLeds = () => {
        fetch(API_ENDPOINT)
            .then(response => response.json())
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
            })
            .catch(error => {
                console.error("Error fetching LED status data:", error);
                leds.forEach(led => setLedStatus(led, "status-gray"));
            });
    };

    updateLeds();
    setInterval(updateLeds, REFRESH_INTERVAL);


/*	
id_misuratore	"CU4"
latest_measurement	"2024-01-25T07:23:30Z"
*/
});
