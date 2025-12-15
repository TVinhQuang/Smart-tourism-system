// File: navbar_loader.js

fetch("../components/navbar.html") // Đảm bảo đường dẫn này đúng với cấu trúc folder của bạn
    .then(res => res.text())
    .then(html => {
        document.getElementById("navbar-root").innerHTML = html;
        
        // --- SỬA QUAN TRỌNG ---
        // Sau khi chèn Navbar xong, gọi hàm dịch lại một lần nữa để dịch các text trong Navbar
        if (typeof applyTranslations === "function") {
            applyTranslations();
        }
    })
    .catch(() => console.warn("Không load được navbar"));

// XÓA hàm changeLanguage ở đây đi để tránh trùng lặp với file static_trans.js