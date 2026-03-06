/**
 * Grafico Curva di Rendimento per Turbine
 * Recupera dati dall'API Django e renderizza visualizzazione Chart.js
 */

// Istanza globale del grafico
let istanza_grafico = null;

/**
 * Recupera i dati della curva di rendimento per una turbina specifica dall'API
 * @param {string} nome_turbina - Nome della turbina
 * @returns {Promise<Object|null>} Dati di risposta API o null se errore
 */
async function recupera_dati_curva_rendimento(nome_turbina) {
    if (!nome_turbina?.trim()) {
        console.error('Il nome della turbina è obbligatorio e deve essere una stringa non vuota');
        return null;
    }

    try {
        const url = `/portale/api/curva-rendimento/${encodeURIComponent(nome_turbina.trim())}/`;
        const response = await axios.get(url);
        
        console.log(`✓ Dati recuperati con successo per la turbina: ${nome_turbina}`);
        return response.data;
    } catch (error) {
        console.error(`✗ Impossibile recuperare i dati della curva di rendimento per ${nome_turbina}:`, error);
        return null;
    }
}

/**
 * Configurazione opzioni del grafico
 */
const CONFIGURAZIONE_GRAFICO = {
    type: "line",
    options: {
        responsive: true,
        animation: {
            duration: 0
        },
        interaction: {
            intersect: false, // Non serve essere esattamente sul punto
            mode: 'nearest', // Trova il punto più vicino
            axis: 'x' // Rileva hover lungo tutto l'asse X
        },
        plugins: {
            legend: {
                position: 'top',
            },
            title: {
                display: true,
                font: {
                    size: 14
                }
            },
            tooltip: {
                mode: 'nearest',
                intersect: false,
                callbacks: {
                    title: function() {
                        return ''; // Nasconde il titolo default per evitare duplicazione del valore X
                    },
                    label: function(context) {
                        const x = context.parsed.x;
                        const y = context.parsed.y;
                        const portata_min_ls = 3.5;
                        const portata_max_ls = 128;
                        const portata_reale_ls = portata_min_ls + x * (portata_max_ls - portata_min_ls);
                        return ` Portata norm.: ${x.toFixed(3)} | Portata: ${portata_reale_ls.toFixed(2)} l/s | Rendimento: ${(y * 100).toFixed(1)}%`;
                    }
                }
            }
        },
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Portata normalizzata (x)'
                },
                type: 'linear',
                min: 0,
                max: 1,
                ticks: {
                    count: 11, // Forza esattamente 11 tick (0.0, 0.1, 0.2, ..., 1.0)
                    callback: function(value) {
                        const valore_normalizzato = Number(value);
                        if (valore_normalizzato === 0) {
                            return ['0.0', '(3.5 l/s)'];
                        }
                        if (valore_normalizzato === 1) {
                            return ['1.0', '(128 l/s)'];
                        }
                        return valore_normalizzato.toFixed(1);
                    }
                }
            },
            y: {
                title: {
                    display: true,
                    text: 'Rendimento (η)'
                },
                min: 0,
                max: 1,
                ticks: {
                    stepSize: 0.2,
                    callback: function(value) {
                        return (value * 100).toFixed(0) + '%';
                    }
                }
            }
        }
    }
};

/**
 * Crea e visualizza il grafico della curva di rendimento
 * @param {Object} dati_api - Dati dall'API contenenti curve_points
 * @param {string} nome_turbina - Nome della turbina per il titolo del grafico
 */
function crea_grafico_curva_rendimento(dati_api, nome_turbina) {
    const canvas = document.getElementById("curvaRendimentoChart");
    if (!canvas) {
        console.error('Elemento canvas "curvaRendimentoChart" non trovato');
        return;
    }

    const ctx = canvas.getContext("2d");

    // Distruggi il grafico esistente per prevenire perdite di memoria
    if (istanza_grafico) {
        istanza_grafico.destroy();
        istanza_grafico = null;
    }

    // Valida la struttura dei dati
    if (!dati_api?.curve_points?.x || !dati_api?.curve_points?.eta) {
        console.error('Struttura dati API non valida:', dati_api);
        return;
    }

    const { x: valori_x, eta: valori_eta } = dati_api.curve_points;
    
    // Trova l'indice del punto con il massimo rendimento
    const indice_max_rendimento = valori_eta.indexOf(Math.max(...valori_eta));
    
    // Crea array per i raggi dei punti (0 per tutti tranne il massimo)
    const raggi_punti = valori_eta.map((_, index) => index === indice_max_rendimento ? 6 : 0);
    const colori_punti = valori_eta.map((_, index) => 
        index === indice_max_rendimento ? "rgba(255, 99, 132, 1)" : "rgba(75, 192, 192, 1)"
    );
    
    // Crea configurazione del grafico
    const configurazione = {
        ...CONFIGURAZIONE_GRAFICO,
        data: {
            labels: valori_x,
            datasets: [{
                label: `Rendimento ${nome_turbina}`,
                data: valori_eta,
                borderColor: "rgba(75, 192, 192, 1)",
                backgroundColor: "rgba(75, 192, 192, 0.1)",
                fill: true,
                pointRadius: raggi_punti,
                pointBackgroundColor: colori_punti,
                pointBorderColor: colori_punti,
                pointHoverRadius: 8,
                borderWidth: 2,
                tension: 0.1
            }]
        }
    };

    // Imposta titolo dinamico
    configurazione.options.plugins.title.text = 
        `Curva di Rendimento - ${nome_turbina} calcolata sui dati delle nostre turbine`;

    // Crea istanza del grafico
    istanza_grafico = new Chart(ctx, configurazione);
    console.log(`✓ Grafico creato con successo per ${nome_turbina}`);
}

/**
 * Inizializza il grafico della curva di rendimento per una turbina specifica
 * @param {string} nome_turbina - Nome della turbina
 */
async function inizializza_grafico_curva_rendimento(nome_turbina) {
    console.log(`Inizializzazione grafico per la turbina: ${nome_turbina}`);
    
    const dati = await recupera_dati_curva_rendimento(nome_turbina);
    if (dati) {
        crea_grafico_curva_rendimento(dati, nome_turbina);
    } else {
        console.error(`Impossibile inizializzare il grafico per ${nome_turbina}`);
        // Qui si potrebbe mostrare un messaggio di errore user-friendly
    }
}

/**
 * Gestore evento DOM Content Loaded
 * Inizializza automaticamente il grafico quando la pagina è caricata
 */
document.addEventListener("DOMContentLoaded", () => {
    const canvas = document.getElementById("curvaRendimentoChart");
    if (!canvas) {
        console.error('Elemento canvas non trovato');
        return;
    }

    const nome_turbina = canvas.dataset.nomeTurbina;
    if (!nome_turbina) {
        console.error('Nome turbina non specificato nell\'attributo data-nome-turbina del canvas');
        return;
    }

    console.log('DOM caricato, avvio inizializzazione grafico...');
    inizializza_grafico_curva_rendimento(nome_turbina);
});
