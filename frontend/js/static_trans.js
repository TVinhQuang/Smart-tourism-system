window.langData = {};
let currentLang = 'vi';

async function loadLanguage(lang) {
    try {
        currentLang = lang;
        const response = await fetch(`../i18n/${lang}.json`); // Kiểm tra đúng đường dẫn folder
        if (!response.ok) throw new Error(`Không tải được ngôn ngữ ${lang}`);
        
        window.langData = await response.json();
        localStorage.setItem('userLang', lang);

        // --- SỬA LỖI TẠI ĐÂY ---
        // 1. Render lại danh sách trước (để cập nhật mô tả Anh/Việt)
        if (typeof window.renderAccommodationList === 'function') {
            window.renderAccommodationList(); 
        }

        // 2. Sau đó mới dịch các text tĩnh (data-i18n)
        applyTranslations();
        
        console.log(`Đã chuyển sang ngôn ngữ: ${lang}`);
    } catch (e) {
        console.error(e);
    }
}

function applyTranslations() {
    // Chỉ thực hiện việc thay thế text, KHÔNG gọi lại renderAccommodationList ở đây nữa
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (window.langData[key]) {
            if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
                el.placeholder = window.langData[key];
                if(el.classList.contains('input-readonly') && key === 'val_my_location') {
                     el.value = window.langData[key];
                }
            } else {
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