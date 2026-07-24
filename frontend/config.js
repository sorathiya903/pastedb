const API_URL = "https://pastedb-rw62.onrender.com"
const WS_URL = API_URL.replace(/^http/, "ws");

const debug=false



  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-H8NDTL7KT9');


function trackEvent(name, params = {}) {
    if (typeof gtag === "function") {
        gtag("event", name, params);
    }
}

document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-ga-event]");
    if (!btn) return;

    trackEvent(btn.dataset.gaEvent);
});

