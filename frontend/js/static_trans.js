async function translatePage(lang) {
    try {
        const res = await fetch(`../i18n/${lang}.json`);
        const dict = await res.json();

        document.querySelectorAll("[data-i18n]").forEach(el => {
            const key = el.getAttribute("data-i18n");
            if (dict[key]) el.innerText = dict[key];
        });

    } catch (err) {
        console.error("Translation error:", err);
    }
}
