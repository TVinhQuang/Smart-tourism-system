window.langData = {};
let currentLang = 'vi';

async function loadLanguage(lang) {
    try {
        currentLang = lang;
        // LƯU Ý: Đường dẫn '../i18n/' giả định file html nằm trong thư mục con (vd: /pages/). 
        // Nếu file html nằm ở root, hãy sửa thành 'i18n/'
        const response = await fetch(`../i18n/${lang}.json`); 
        if (!response.ok) throw new Error(`Không tải được ngôn ngữ ${lang}`);
        
        window.langData = await response.json();
        localStorage.setItem('userLang', lang);

        // --- CẬP NHẬT LOGIC RENDER ---
        // 1. Render lại danh sách (nếu có) để cập nhật nội dung động
        if (typeof window.renderAccommodationList === 'function') {
            // Trang Gợi ý
            window.renderAccommodationList(); 
        } else if (typeof window.renderResults === 'function' && window.homeResults) {
            // Trang Yêu thích (Favorite)
            window.renderResults(window.homeResults);
        }

        // 2. Dịch các text tĩnh (data-i18n)
        applyTranslations();
        
        console.log(`Đã chuyển sang ngôn ngữ: ${lang}`);
    } catch (e) {
        console.error(e);
    }
}

function applyTranslations() {
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        // Kiểm tra xem key có tồn tại trong langData không
        if (window.langData && window.langData[key]) {
            if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
                el.placeholder = window.langData[key];
                if(el.classList.contains('input-readonly') && key === 'val_my_location') {
                     el.value = window.langData[key];
                }
            } else {
                // Sử dụng innerHTML nếu muốn chèn icon hoặc tag b, strong...
                // Nếu chỉ là text thuần thì dùng innerText
                el.innerText = window.langData[key];
            }
        }
    });
}

function changeLanguage(lang) {
    loadLanguage(lang);
}

document.addEventListener("DOMContentLoaded", () => {
    const savedLang = localStorage.getItem('userLang') || 'vi';
    loadLanguage(savedLang);
});