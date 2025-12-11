// =======================================================
// KHAI BÁO BIẾN TOÀN CỤC
// =======================================================
let routingItem = null;
let map = null;
let routeLine = null;
let markerStart = null;
let markerEnd = null;

// Tọa độ giả lập (Sửa thành TP.HCM - Quận 1 để demo cho đẹp)
// Bạn có thể dùng navigator.geolocation để lấy vị trí thật
const YOUR_LAT = 10.7769;
const YOUR_LON = 106.7009;

// =======================================================
// 1. MỞ MODAL (VÀO BƯỚC 1)
// =======================================================
function openRoutingModal(index) {
    if (!window.homeResults || !window.homeResults[index]) {
        console.error("Không tìm thấy dữ liệu tại index:", index);
        return;
    }
    
    const item = window.homeResults[index];
    routingItem = item;

    // Reset giao diện về Bước 1 (Nếu hàm này lỗi => Modal không hiện)
    switchView(1);

    // --- XỬ LÝ NGÔN NGỮ ---
    const currentLang = localStorage.getItem('userLang') || 'vi';
    
    // 1. Mô tả (Check nếu là object đa ngôn ngữ hay string thường)
    let description = "";
    if (item.desc && typeof item.desc === 'object') {
        description = item.desc[currentLang] || item.desc['vi'];
    } else {
        description = item.desc || "";
    }
    document.getElementById("info-desc").innerText = description;

    // 2. Tiện ích (Dịch từ Key sang Chữ)
    const amenityContainer = document.getElementById("info-amenities");
    amenityContainer.innerHTML = ""; 

    if (item.amenities && item.amenities.length > 0) {
        item.amenities.forEach(key => {
            const span = document.createElement("span");
            span.className = "amenity-tag";
            // Lấy từ điển ra dịch. Nếu chưa tải xong hoặc không có key thì hiện tạm key gốc
            const translatedText = (window.langData && window.langData[key]) ? window.langData[key] : key;
            span.innerText = translatedText;
            amenityContainer.appendChild(span);
        });
    }

    // --- ĐIỀN THÔNG TIN CƠ BẢN ---
    document.getElementById("info-img").src = item.img || 'https://via.placeholder.com/300';
    document.getElementById("info-name").innerText = item.name;
    // ====================== FAVORITE CHECK ======================
    const favBtn = document.getElementById("fav-toggle");
    const favList = loadFavorites();

    if (favList.some(f => f.id === item.id)) {
        favBtn.classList.add("active");
        favBtn.innerText = "❤️";
    } else {
        favBtn.classList.remove("active");
        favBtn.innerText = "♡";
    }

// Sự kiện click
    favBtn.onclick = () => {
        const list = loadFavorites();
        const exists = list.some(f => f.id === item.id);

        if (exists) {
            // Bỏ thích
            const newList = list.filter(f => f.id !== item.id);
            saveFavorites(newList);
            favBtn.classList.remove("active");
            favBtn.innerText = "♡";
        } else {
            // Thêm thích
         list.push(item);
            saveFavorites(list);
            favBtn.classList.add("active");
            favBtn.innerText = "❤️";
        }
    };

    document.getElementById("info-address").innerText = item.address;
    document.getElementById("info-price").innerText = Number(item.price).toLocaleString() + " VND";
    document.getElementById("info-rating").innerText = item.rating;
    
    // Gán giá trị cho ô input "Vị trí của bạn" (nếu có data-i18n)
    const myLocInput = document.querySelector('input[data-i18n="val_my_location"]');
    if(myLocInput && window.langData) {
        myLocInput.value = window.langData["val_my_location"];
    }
    
    // Gán đích đến
    document.getElementById("target-dest").value = item.name;

    // Hiển thị modal (Xóa class hidden)
    document.getElementById("routing-overlay").classList.remove("hidden");
}

// =======================================================
// 2. XỬ LÝ TÌM ĐƯỜNG (CHUYỂN SANG BƯỚC 2)
// =======================================================
document.getElementById("btn-find-route").addEventListener("click", () => {
    // Lấy phương tiện đang chọn
    const modeEl = document.querySelector('input[name="transport"]:checked');
    const mode = modeEl ? modeEl.value : 'driving';
    
    // Hiển thị loading
    const btn = document.getElementById("btn-find-route");
    const originalText = btn.innerText;
    btn.innerText = window.langData["status_calculating"] || "⏳ ...";
    btn.disabled = true;
    btn.classList.add("btn-loading");

    // Lấy ngôn ngữ để gửi cho Backend
    const currentLang = localStorage.getItem('userLang') || 'vi';

    // Gọi API Backend Python
    fetch("http://127.0.0.1:5000/api/route", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            src: { lat: YOUR_LAT, lon: YOUR_LON },
            dst: { lat: routingItem.lat, lon: routingItem.lon },
            profile: mode,
            lang: currentLang // Gửi ngôn ngữ cho server
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            // Chuyển sang Bước 2
            switchView(2);
            
            // Đồng bộ select box ở bước 2
            const quickSelect = document.getElementById("quick-transport-change");
            if(quickSelect) quickSelect.value = mode;

            // Render dữ liệu phân tích
            renderAnalysis(data.info);
            renderSteps(data.instructions);
            
            // Render Bản đồ
            initMap(data.path);

        } else {
            alert((window.langData["error_not_found"] || "Error") + ": " + (data.message || ""));
        }
    })
    .catch(err => {
        console.error(err);
        alert(window.langData["error_server"] || "Server Connection Error!");
    })
    .finally(() => {
        btn.innerText = originalText; // Trả lại tên nút cũ (hoặc lấy từ langData)
        btn.disabled = false;
        btn.classList.remove("btn-loading");
    });
});

// =======================================================
// 3. CÁC HÀM HỖ TRỢ (UI & MAP)
// =======================================================

function switchView(step) {
    const v1 = document.getElementById("view-step-1");
    const v2 = document.getElementById("view-step-2");
    
    if (step === 1) {
        if(v1) v1.classList.remove("hidden");
        if(v2) v2.classList.add("hidden");
    } else {
        if(v1) v1.classList.add("hidden");
        if(v2) v2.classList.remove("hidden");
    }
}

function renderAnalysis(info) {
    document.getElementById("res-distance").innerText = info.distance_text;
    document.getElementById("res-duration").innerText = info.duration_text;
    
    const labelEl = document.getElementById("res-label");
    labelEl.innerText = info.complexity_label;
    
    // Đổi màu chữ theo độ khó
    if(info.complexity_level === 'low') labelEl.style.color = 'green';
    else if(info.complexity_level === 'medium') labelEl.style.color = 'orange';
    else labelEl.style.color = 'red';

    document.getElementById("res-summary").innerText = info.complexity_summary;
    document.getElementById("res-advice").innerText = info.recommendation_msg;

    const ul = document.getElementById("res-details");
    ul.innerHTML = "";
    if(info.analysis_details) {
        info.analysis_details.forEach(detail => {
            const li = document.createElement("li");
            li.innerText = detail;
            ul.appendChild(li);
        });
    }
}

function renderSteps(instructions) {
    const list = document.getElementById("steps-list");
    list.innerHTML = "";
    if(instructions) {
        instructions.forEach((stepText, i) => {
            const div = document.createElement("div");
            div.className = "step-item";
            // Thêm delay animation
            div.style.animationDelay = `${i * 0.05}s`;
            div.innerHTML = `
                <div class="step-icon">${i + 1}</div>
                <div class="step-text">${stepText}</div>
            `;
            list.appendChild(div);
        });
    }
}

function initMap(pathCoords) {
    console.log("--- BẮT ĐẦU VẼ MAP ---");

    // 1. KIỂM TRA & XỬ LÝ TOẠ ĐỘ
    let finalPath = pathCoords || [];
    if (finalPath.length > 0) {
        // Kiểm tra phần tử đầu tiên để xem có bị ngược không
        // [106.xxx, 10.xxx] -> Số đầu > 90 là Kinh độ (Lng) -> Ngược -> Cần đảo
        if (finalPath[0][0] > 90) {
            console.log("⚠️ Toạ độ bị ngược [Lng, Lat], đang đảo chiều...");
            finalPath = finalPath.map(p => [p[1], p[0]]);
        }
    } else {
        console.error("❌ Không có toạ độ đường đi!");
        return;
    }

    // 2. XOÁ MAP CŨ (Destroy)
    // Bắt buộc xoá để tránh lỗi "Ghost Map"
    if (map) {
        map.remove();
        map = null;
    }

    // 3. TẠO MAP MỚI
    try {
        // Đảm bảo thẻ div 'rt-map' đã tồn tại
        const mapContainer = document.getElementById("rt-map");
        if (!mapContainer) {
            console.error("❌ Không tìm thấy thẻ <div id='rt-map'> trong HTML!");
            return;
        }

        map = L.map("rt-map", {
            zoomControl: false, 
            attributionControl: false
        });
    } catch (e) {
        console.error("❌ Lỗi khởi tạo Leaflet:", e);
        return;
    }

    // Thêm TileLayer (Nền bản đồ)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap'
    }).addTo(map);
    L.control.zoom({ position: 'topleft' }).addTo(map);

    // 4. VẼ ĐỐI TƯỢNG (MARKER & LINE)
    const startGroup = L.marker([YOUR_LAT, YOUR_LON]).addTo(map).bindPopup("Bạn ở đây");
    const endGroup = L.marker([routingItem.lat, routingItem.lon]).addTo(map).bindPopup("Đích đến");
    
    let routeLayer = null;
    if (finalPath.length > 0) {
        routeLayer = L.polyline(finalPath, {
            color: 'blue',
            weight: 5,
            opacity: 0.8
        }).addTo(map);
    }

    // 5. CHIẾN THUẬT "CƯỠNG ÉP" CẬP NHẬT GIAO DIỆN
    // Vì Modal có hiệu ứng trượt (transition), ta phải bắt map cập nhật nhiều lần
    
    const forceUpdateMap = () => {
        if (!map) return;
        
        // Bắt Leaflet tính lại kích thước thẻ div
        map.invalidateSize(); 

        // Zoom vào toàn bộ đường đi
        if (routeLayer) {
            map.fitBounds(routeLayer.getBounds(), { padding: [50, 50], animate: false });
        } else {
            // Nếu không có đường thì zoom vào 2 điểm marker
            const group = L.featureGroup([startGroup, endGroup]);
            map.fitBounds(group.getBounds(), { padding: [50, 50], animate: false });
        }
    };

    // --- CHẠY LIÊN TỤC 4 LẦN ĐỂ SỬA LỖI ---
    forceUpdateMap(); // Lần 1: Ngay lập tức
    setTimeout(forceUpdateMap, 300);  // Lần 2: Sau 0.3s
    setTimeout(forceUpdateMap, 600);  // Lần 3: Sau 0.6s (Lúc modal vừa mở xong)
    setTimeout(forceUpdateMap, 1000); // Lần 4: Chốt hạ sau 1s cho chắc ăn
}
// =======================================================
// 4. SỰ KIỆN NÚT BẤM
// =======================================================

// Nút Quay lại (B2 -> B1)
document.getElementById("btn-back-step1").addEventListener("click", () => {
    switchView(1);
});

// Nút Đóng Modal
document.getElementById("btn-close-step1").addEventListener("click", () => {
    document.getElementById("routing-overlay").classList.add("hidden");
});

// Đóng khi click ra ngoài vùng trắng
document.getElementById("routing-overlay").addEventListener("click", (e) => {
    if (e.target.id === "routing-overlay") {
        document.getElementById("routing-overlay").classList.add("hidden");
    }
});

// Xử lý đổi phương tiện nhanh ở Bước 2 (Select box trên bản đồ)
document.getElementById("quick-transport-change").addEventListener("change", (e) => {
    const mode = e.target.value;
    // Đồng bộ lại nút radio ở bước 1
    const radio = document.querySelector(`input[name="transport"][value="${mode}"]`);
    if(radio) radio.checked = true;
    
    // Tự động bấm nút "Tìm đường" lại
    document.getElementById("btn-find-route").click();
});