// --- 1. LOGIC DUY TRÌ TRẠNG THÁI ĐĂNG NHẬP (Dùng LOCALSTORAGE) ---

function logoutUser() {
    localStorage.removeItem('loggedInUserEmail');
    window.location.href = 'login.html'; 
}

function formatEmail(email) {
    if (!email) return "Người dùng";
    const parts = email.split('@');
    return parts[0]; 
}

function updateNavbarForLoggedInUser() {
    // ĐỌC EMAIL TỪ LOCAL STORAGE
    const userEmail = localStorage.getItem('loggedInUserEmail'); 
    const navbarRoot = document.getElementById('navbar-root');
    
    if (navbarRoot.innerHTML !== "") {
        const loginButtonContainer = navbarRoot.querySelector('.nav-right'); 

        if (userEmail) {
            const displayName = formatEmail(userEmail);
            if (loginButtonContainer) {
                // Thay thế nút "Đăng nhập" bằng Tên người dùng và nút Đăng xuất
                loginButtonContainer.innerHTML = `
                    <div class="user-info-group">
                        <span class="user-greeting">👋 <span data-i18n="nav_greeting">Xin chào,</span> <strong>${displayName}</strong></span>
                        <button class="btn-logout" onclick="logoutUser()">
                            <img src="../images/logout.png" class="logout-icon" style="height: 16px;">
                            <span data-i18n="nav_logout">Đăng xuất</span>
                        </button>
                    </div>
                `;
            }
        } else {
            // Nếu chưa đăng nhập, hiển thị nút Đăng nhập
            if (loginButtonContainer) {
                 loginButtonContainer.innerHTML = `<a href="login.html" class="btn-login" data-i18n="nav_login">Đăng nhập</a>`;
            }
        }
        // Áp dụng dịch thuật cho các phần tử vừa được chèn
        applyTranslations();
    }

    loginButtonContainer.innerHTML = `
    <div class="user-info-group">
        <span class="user-greeting">👋 <span data-i18n="nav_greeting">Xin chào,</span> <strong>${displayName}</strong></span>
        <button class="btn-logout" onclick="logoutUser()">
            <img src="../../images/logout.png" class="logout-icon" style="height: 16px;">
            <span data-i18n="nav_logout">Đăng xuất</span>
        </button>
    </div>
`
}

// --- 2. LOGIC DỊCH THUẬT VÀ TOGGLE DROPWDOWN ---

let currentTranslations = {};

function getTranslation(key) {
    return currentTranslations[key] || key;
}

// Thay thế hàm applyTranslations cũ bằng hàm này
function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const keyRaw = element.getAttribute('data-i18n');
        
        // Kiểm tra xem có phải dịch thuộc tính không (ví dụ: [placeholder]val_my_location)
        if (keyRaw.startsWith('[') && keyRaw.includes(']')) {
            const parts = keyRaw.split(']');
            const attribute = parts[0].replace('[', ''); // Lấy tên thuộc tính (vd: placeholder)
            const key = parts[1]; // Lấy key (vd: val_my_location)
            
            // Dịch và gán vào thuộc tính
            element.setAttribute(attribute, getTranslation(key));
        } else {
            // Dịch nội dung text bình thường
            const translation = getTranslation(keyRaw);
            if (element.tagName === 'BUTTON' || element.tagName === 'A') {
                // Giữ lại icon nếu có, chỉ thay text node cuối cùng
                if (element.lastChild && element.lastChild.nodeType === 3) {
                    element.lastChild.textContent = translation;
                } else {
                    element.textContent = translation;
                }
            } else {
                element.textContent = translation;
            }
        }
    });
}

async function loadAndApplyLanguage(lang) {
    const filePath = `../i18n/${lang}.json`;
    
    try {
        const response = await fetch(filePath);
        if (!response.ok) { throw new Error(`Không thể tải file dịch thuật: ${filePath}`); }
        currentTranslations = await response.json();
        localStorage.setItem('lang', lang); 

        applyTranslations();
        updateNavbarForLoggedInUser(); // Cập nhật lại Navbar sau khi dịch

    } catch (error) {
        console.error("Lỗi Dịch thuật:", error);
    }
}

function changeLanguage(lang) {
    loadAndApplyLanguage(lang);
    const menu = document.getElementById('languageMenu');
    if (menu) {
        menu.classList.add('hidden');
        document.removeEventListener('click', closeMenuOutside);
    }
    return false;
}

function toggleLanguageMenu() {
    const menu = document.getElementById('languageMenu');
    if (menu) {
        menu.classList.toggle('hidden'); 
        if (!menu.classList.contains('hidden')) {
            document.addEventListener('click', closeMenuOutside);
        } else {
            document.removeEventListener('click', closeMenuOutside);
        }
    }
}

function closeMenuOutside(event) {
    const dropdown = document.querySelector('.dropdown');
    const menu = document.getElementById('languageMenu');

    if (dropdown && menu && !dropdown.contains(event.target)) {
        menu.classList.add('hidden');
        document.removeEventListener('click', closeMenuOutside);
    }
}

// --- 3. KHỞI TẠO CHUNG ---

document.addEventListener('DOMContentLoaded', () => {
    // 1. Load Navbar
    fetch('../components/navbar.html')
        .then(r => r.text())
        .then(html => { 
            document.getElementById('navbar-root').innerHTML = html; 
            // 2. Tải ngôn ngữ và cập nhật Navbar (Chỉ chạy sau khi Navbar load)
            const defaultLang = localStorage.getItem('lang') || 'vi'; 
            loadAndApplyLanguage(defaultLang);
        })
        .catch(e => console.warn('Không thể load navbar component', e));
});