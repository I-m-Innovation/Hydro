document.addEventListener("DOMContentLoaded", () => {
    const triggerSelector = "[data-popover-target]";
    const triggers = Array.from(document.querySelectorAll(triggerSelector));
    if (!triggers.length) {
        return;
    }

    const isKatexAvailable = typeof window.katex !== "undefined";

    const renderKatex = (container) => {
        if (!container || !isKatexAvailable) {
            return;
        }
        const mathNodes = container.querySelectorAll("[data-katex]");
        mathNodes.forEach((node) => {
            const expr = node.getAttribute("data-katex") || "";
            if (!expr.trim()) {
                return;
            }
            try {
                window.katex.render(expr, node, {
                    throwOnError: false,
                    displayMode: true,
                });
            } catch (_error) {
                // Keep popover usable even if formula rendering fails.
            }
        });
    };

    const closePopover = (popover) => {
        if (!popover) {
            return;
        }
        popover.classList.add("is-hidden");
        popover.setAttribute("aria-hidden", "true");
    };

    const closeAllPopovers = () => {
        document.querySelectorAll(".chart-popover").forEach((popover) => {
            closePopover(popover);
        });
    };

    const placePopover = (trigger, popover) => {
        const margin = 8;
        const rect = trigger.getBoundingClientRect();
        popover.style.left = "0px";
        popover.style.top = "0px";
        popover.classList.remove("is-hidden");
        popover.setAttribute("aria-hidden", "false");

        const popRect = popover.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        let left = rect.right - popRect.width;
        if (left < margin) {
            left = margin;
        }
        if (left + popRect.width > viewportWidth - margin) {
            left = Math.max(margin, viewportWidth - popRect.width - margin);
        }

        let top = rect.bottom + margin;
        if (top + popRect.height > viewportHeight - margin) {
            top = rect.top - popRect.height - margin;
        }
        if (top < margin) {
            top = margin;
        }

        popover.style.left = `${Math.round(left)}px`;
        popover.style.top = `${Math.round(top)}px`;
    };

    triggers.forEach((trigger) => {
        const popoverId = trigger.getAttribute("data-popover-target");
        if (!popoverId) {
            return;
        }
        const popover = document.getElementById(popoverId);
        if (!popover) {
            return;
        }

        renderKatex(popover);

        trigger.addEventListener("click", (event) => {
            event.preventDefault();
            const isOpen = !popover.classList.contains("is-hidden");
            closeAllPopovers();
            if (!isOpen) {
                placePopover(trigger, popover);
            }
        });
    });

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            closeAllPopovers();
            return;
        }
        if (target.closest(triggerSelector) || target.closest(".chart-popover")) {
            return;
        }
        closeAllPopovers();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAllPopovers();
        }
    });

    window.addEventListener("resize", closeAllPopovers);
    window.addEventListener("scroll", closeAllPopovers, true);
});
