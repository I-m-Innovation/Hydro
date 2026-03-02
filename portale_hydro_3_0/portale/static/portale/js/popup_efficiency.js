/**
 * Gestione Popup per Curva di Rendimento
 * Gestisce apertura/chiusura del popup con effetto blur per il grafico di efficienza
 */

/**
 * Mostra il popup della curva di rendimento con animazioni
 */
function showEfficiencyPopup() {
    const popup = document.getElementById('modal-curva-di-rendimento');
    if (!popup) return;

    popup.classList.remove('is-hidden');

    // Trigger chart initialization after popup is visible
    setTimeout(() => {
        if (window.inizializza_grafico_curva_rendimento) {
            window.inizializza_grafico_curva_rendimento('Pelton');
        }
    }, 300);
}

/**
 * Nasconde il popup e pulisce la memoria del grafico
 */
function hideEfficiencyPopup() {
    const popup = document.getElementById('modal-curva-di-rendimento');
    if (!popup) return;

    popup.classList.add('is-hidden');

    // Destroy chart to free memory
    if (window.istanza_grafico) {
        window.istanza_grafico.destroy();
        window.istanza_grafico = null;
    }
}

/**
 * Inizializza gli event listeners per il popup
 */
function initializePopupEventListeners() {
    // Event listeners per entrambi i bottoni
    const btnShowCurve = document.querySelector('.btn-show-efficiency-curve');
    const btnEfficiencyPopup = document.querySelector('.btn-efficiency-popup');

    if (btnShowCurve) {
        btnShowCurve.addEventListener('click', showEfficiencyPopup);
    }

    if (btnEfficiencyPopup) {
        btnEfficiencyPopup.addEventListener('click', showEfficiencyPopup);
    }

    // Close button
    const closeBtn = document.querySelector('.popup-close-simple');
    if (closeBtn) {
        closeBtn.addEventListener('click', hideEfficiencyPopup);
    }

    // Close on backdrop click
    const popup = document.getElementById('modal-curva-di-rendimento');
    if (popup) {
        popup.addEventListener('click', e => {
            if (e.target.classList.contains('popup-overlay')) {
                hideEfficiencyPopup();
            }
        });
    }

    // Close on ESC key
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && popup && !popup.classList.contains('is-hidden')) {
            hideEfficiencyPopup();
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializePopupEventListeners);
