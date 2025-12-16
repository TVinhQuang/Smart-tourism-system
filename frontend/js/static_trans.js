// File: js/static_trans.js

window.langData = {};
let currentLang = localStorage.getItem('lang') || 'vi'; 

async function loadLanguage(lang) {
    try {
        currentLang = lang;
        localStorage.setItem('lang', lang); 

        // --- SỬA LOGIC ĐƯỜNG DẪN ---
        // Giả định mặc định file html nằm cùng cấp với folder i18n
        let path = `i18n/${lang}.json`;
        
        // Kiểm tra thử xem có cần lùi ra thư mục cha không (cho các trang con)
        const response = await fetch(path);
        
        window.langData = await response.json();

        applyTranslations();

        // 2. [THÊM MỚI] Dịch nội dung động (Danh sách khách sạn)
        // Kiểm tra nếu hàm renderAccommodationList tồn tại (được load từ homepage.js) thì chạy lại nó
        if (typeof window.renderAccommodationList === 'function') {
            window.renderAccommodationList();
        }

        console.log(`Đã tải ngôn ngữ: ${lang}`);
    } catch (e) {
        console.error("Lỗi tải ngôn ngữ:", e);
    }
}

function applyTranslations() {
    if (!window.langData) return;
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (window.langData[key]) {
            if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
                el.placeholder = window.langData[key];
                if(el.classList.contains('input-readonly') && key === 'val_my_location') {
                     el.value = window.langData[key];
                }
            } else {
                el.innerHTML = window.langData[key];
            }
        }
    });
}

function changeLanguage(lang) {
    localStorage.setItem('lang', lang);
    loadLanguage(lang); // Tải lại ngôn ngữ ngay lập tức
}

// Tự động chạy khi load trang
document.addEventListener("DOMContentLoaded", () => {
    // Nếu trang không có navbar loader (trang lẻ), tự chạy luôn
    if (!document.getElementById('navbar-root')) {
        loadLanguage(currentLang);
    }
});