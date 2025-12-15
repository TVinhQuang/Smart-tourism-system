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
let YOUR_LAT = 10.7769;
let YOUR_LON = 106.7009;
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
    console.log("debug info-desc:", document.getElementById("info-desc"));

    // --- ĐIỀN THÔNG TIN CƠ BẢN ---
    document.getElementById("info-img").src = item.img || 'https://via.placeholder.com/300';
    document.getElementById("info-name").innerText = item.name;
    // ====================== FAVORITE CHECK ======================
    function loadFavorites() {
    const data = localStorage.getItem('favorites');
    return data ? JSON.parse(data) : [];
}

// Ví dụ: Hàm setup trong routing_homepage.js hoặc nơi hiển thị chi tiết hotel
function setupFavoriteButton(currentHotelData) {
    const favBtn = document.getElementById("fav-toggle");
    if (!favBtn) return;

    // 1. Hàm kiểm tra trạng thái tim hiện tại
    const checkFavoriteStatus = () => {
        const favorites = JSON.parse(localStorage.getItem("favorites") || "[]");
        // Kiểm tra dựa trên ID hoặc Tên (nếu không có ID duy nhất)
        const isFav = favorites.some(item => item.name === currentHotelData.name); 
        
        // Cập nhật giao diện nút tim
        favBtn.textContent = isFav ? "❤️" : "♡";
        favBtn.style.color = isFav ? "red" : "#333";
        favBtn.style.cursor = "pointer";
    };

    // Gọi 1 lần khi mở modal
    checkFavoriteStatus();

    // 2. Xử lý sự kiện Click
    favBtn.onclick = function() {
        let favorites = JSON.parse(localStorage.getItem("favorites") || "[]");
        const index = favorites.findIndex(item => item.name === currentHotelData.name);

        if (index > -1) {
            // Đã có -> Xóa đi (Un-like)
            favorites.splice(index, 1);
            alert("Đã xóa khỏi danh sách yêu thích!");
        } else {
            // Chưa có -> Thêm vào
            favorites.push(currentHotelData);
            alert("Đã thêm vào danh sách yêu thích!");
        }

        // Lưu lại và cập nhật giao diện
        localStorage.setItem("favorites", JSON.stringify(favorites));
        checkFavoriteStatus();
    };
}

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
// =======================================================
// 2. XỬ LÝ TÌM ĐƯỜNG (CHẠY LOCAL - KHÔNG MOCK)
// =======================================================
document.getElementById("btn-find-route").addEventListener("click", () => {
    // Lấy phương tiện đang chọn
    const modeEl = document.querySelector('input[name="transport"]:checked');
    const mode = modeEl ? modeEl.value : 'driving';
    
    // Hiển thị loading
    const btn = document.getElementById("btn-find-route");
    const originalText = btn.innerText;
    btn.innerText = (window.langData && window.langData["status_calculating"]) ? window.langData["status_calculating"] : "⏳ Đang tính toán...";
    btn.disabled = true;
    btn.classList.add("btn-loading");

    // Lấy ngôn ngữ để gửi cho Backend
    const currentLang = localStorage.getItem('userLang') || 'vi';

    // --- SỬA LẠI ĐOẠN NÀY ---
    // Chỉ trỏ về gốc server Python Local
    const BASE_URL = 'http://127.0.0.1:8000'; 

    // 2. ENDPOINT MỚI: /api/route (Không phải /api/recommend-hotel)
    fetch(`${BASE_URL}/api/route`, {  
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            src: { lat: YOUR_LAT, lon: YOUR_LON },
            dst: { lat: routingItem.lat, lon: routingItem.lon },
            profile: mode,
            lang: currentLang 
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

            // --- HIỂN THỊ DỮ LIỆU THẬT TỪ SERVER ---
            // Server phải trả về đúng cấu trúc: info, instructions, path
            if (data.info) renderAnalysis(data.info);
            if (data.instructions) renderSteps(data.instructions);
            if (data.path) initMap(data.path);

        } else {
            // Xử lý lỗi từ server trả về
            const errorMsg = (window.langData && window.langData["error_not_found"]) 
                             ? window.langData["error_not_found"] 
                             : "Không tìm thấy đường đi";
            alert(`${errorMsg}: ${data.message || ""}`);
        }
    })
    .catch(err => {
        console.error("Fetch Error:", err);
        const serverError = (window.langData && window.langData["error_server"]) 
                            ? window.langData["error_server"] 
                            : "Lỗi kết nối Server Local (Port 5000)!";
        alert(serverError + "\nHãy kiểm tra xem Python backend đã chạy chưa?");
    })
    .finally(() => {
        btn.innerText = originalText; 
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

// Trong file js/routing_rec_page.js

function renderAnalysis(info) {
    // 1. Điền thông tin cơ bản (Khoảng cách, Thời gian)
    document.getElementById("res-distance").innerText = info.distance_text;
    document.getElementById("res-duration").innerText = info.duration_text;
    
    // 2. Lấy dữ liệu an toàn
    const complexity = info.complexity || {};
    const recommendation = info.recommendation || {};

    // 3. Xác định màu sắc cho nhãn độ khó
    let badgeColor = '#28a745'; // Xanh (Dễ)
    let badgeText = complexity.label || "Dễ đi";
    
    if (complexity.level === 'medium') badgeColor = '#fd7e14'; // Cam (Trung bình)
    if (complexity.level === 'high') badgeColor = '#dc3545';   // Đỏ (Khó)

    // 4. [QUAN TRỌNG] Thay vì gán text, ta thay đổi HTML của hộp cha
    // Tìm thẻ cha chứa phần phân tích (trong file HTML bạn cần đặt id cho div bao quanh)
    // Ở đây ta sẽ render đè vào thẻ div có class "complexity-box"
    
    const container = document.querySelector(".complexity-box");
    
    if (container) {
        container.innerHTML = `
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                <strong style="font-size:1.1rem; color:#333;">Đánh giá lộ trình:</strong>
                <span style="background:${badgeColor}; color:white; padding:4px 10px; border-radius:12px; font-size:0.9rem; font-weight:bold;">
                    ${badgeText}
                </span>
            </div>

            <p style="color:#555; margin-bottom:8px; line-height:1.4;">
                ${complexity.summary || ""}
            </p>

            ${(complexity.reasons && complexity.reasons.length > 0) ? 
                `<ul style="margin:5px 0 10px 20px; color:#dc3545; font-size:0.9rem;">
                    ${complexity.reasons.map(r => `<li>${r}</li>`).join('')}
                </ul>` 
            : ''}

            <div style="background:#e3f2fd; border-left:4px solid #2196f3; padding:12px; border-radius:4px; margin-top:10px; display:flex; gap:10px;">
                <span style="font-size:1.2rem;">💡</span>
                <div>
                    <strong style="display:block; font-size:0.85rem; color:#1565c0; margin-bottom:2px;">Gợi ý di chuyển:</strong>
                    <p style="margin:0; font-size:0.95rem; color:#0d47a1; line-height:1.4;">
                        ${recommendation.message || "Không có gợi ý cụ thể."}
                    </p>
                </div>
            </div>
        `;
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

// =======================================================
// XỬ LÝ NÚT LẤY VỊ TRÍ (GPS)
// =======================================================
const btnGPS = document.getElementById("btn-use-gps");

if (btnGPS) {
    btnGPS.addEventListener("click", () => {
        const startInput = document.getElementById("start-location");
        
        // 1. Kiểm tra trình duyệt có hỗ trợ không
        if (!navigator.geolocation) {
            alert("Trình duyệt của bạn không hỗ trợ định vị GPS.");
            return;
        }

        // 2. Hiệu ứng đang tải
        const originalText = btnGPS.innerText;
        btnGPS.innerText = "⏳";
        btnGPS.disabled = true;
        if(startInput) startInput.value = "Đang lấy vị trí...";

        // 3. Gọi API lấy vị trí
        navigator.geolocation.getCurrentPosition(
            (position) => {
                // --- THÀNH CÔNG ---
                YOUR_LAT = position.coords.latitude;
                YOUR_LON = position.coords.longitude;

                console.log("📍 GPS:", YOUR_LAT, YOUR_LON);

                // Cập nhật giao diện
                if(startInput) {
                    startInput.value = `Vị trí của tôi `;
                }
                
                // Trả lại nút bấm
                btnGPS.innerText = "📍"; // Hoặc icon cũ
                btnGPS.disabled = false;
                
                // Nếu bản đồ đang mở, cập nhật luôn marker xuất phát
                if (map && markerStart) {
                    markerStart.setLatLng([YOUR_LAT, YOUR_LON]).bindPopup("Vị trí hiện tại").openPopup();
                    map.setView([YOUR_LAT, YOUR_LON], 13);
                }
            },
            (error) => {
                // --- THẤT BẠI ---
                console.error("Lỗi GPS:", error);
                let msg = "Không thể lấy vị trí.";
                
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        msg = "Bạn đã từ chối cấp quyền vị trí.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        msg = "Không xác định được vị trí.";
                        break;
                    case error.TIMEOUT:
                        msg = "Hết thời gian chờ lấy vị trí.";
                        break;
                }
                
                alert(msg);
                if(startInput) startInput.value = ""; // Xóa trắng nếu lỗi
                btnGPS.innerText = originalText;
                btnGPS.disabled = false;
            },
            {
                enableHighAccuracy: true, // Lấy chính xác cao nhất có thể
                timeout: 10000,           // Chờ tối đa 10 giây
                maximumAge: 0             // Không dùng cache cũ
            }
        );
    });
}

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