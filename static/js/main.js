/**
 * VenuePulseAI – Main client-side JavaScript
 */

document.addEventListener("DOMContentLoaded", () => {
    console.log("VenuePulseAI loaded.");

    // Auto-dismiss flash alerts after 5 seconds
    document.querySelectorAll(".alert").forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.4s ease";
            alert.style.opacity = "0";
            setTimeout(() => alert.remove(), 400);
        }, 5000);
    });
});
