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

    // Reset giao diện về Bước 1
    switchView(1);

    // --- XỬ LÝ NGÔN NGỮ ---
    const currentLang = localStorage.getItem('userLang') || 'vi';
    
    // --- LƯU Ý: ĐÃ BỎ PHẦN MÔ TẢ (DESC) VÀ ẢNH (IMG) TẠI ĐÂY ---

    // 1. Tiện ích (Dịch từ Key sang Chữ)
    const amenityContainer = document.getElementById("info-amenities");
    if (amenityContainer) {
        amenityContainer.innerHTML = ""; 
        if (item.amenities && item.amenities.length > 0) {
            item.amenities.forEach(key => {
                const span = document.createElement("span");
                span.className = "amenity-tag";
                // Lấy từ điển ra dịch
                const translatedText = (window.langData && window.langData[key]) ? window.langData[key] : key;
                span.innerText = translatedText;
                amenityContainer.appendChild(span);
            });
        }
    }

    // --- ĐIỀN THÔNG TIN CƠ BẢN ---
    // Không set src cho info-img
    document.getElementById("info-name").innerText = item.name;
    document.getElementById("info-address").innerText = item.address;
    document.getElementById("info-price").innerText = Number(item.price).toLocaleString() + " VND";
    document.getElementById("info-rating").innerText = item.rating;

    // ====================== FAVORITE CHECK ======================
    // Định nghĩa hàm xử lý nút yêu thích
    function setupFavoriteButton(currentHotelData) {
        const favBtn = document.getElementById("fav-toggle");
        if (!favBtn) return;

        // Hàm kiểm tra trạng thái
        const checkFavoriteStatus = () => {
            const favorites = JSON.parse(localStorage.getItem("favorites") || "[]");
            const isFav = favorites.some(i => i.name === currentHotelData.name); 
            
            favBtn.textContent = isFav ? "❤️" : "♡";
            favBtn.style.color = isFav ? "red" : "#333";
            favBtn.style.cursor = "pointer";
        };

        checkFavoriteStatus();

        // Xử lý sự kiện Click
        favBtn.onclick = function() {
            let favorites = JSON.parse(localStorage.getItem("favorites") || "[]");
            const index = favorites.findIndex(i => i.name === currentHotelData.name);

            if (index > -1) {
                favorites.splice(index, 1);
                alert("Đã xóa khỏi danh sách yêu thích!");
            } else {
                favorites.push(currentHotelData);
                alert("Đã thêm vào danh sách yêu thích!");
            }
            localStorage.setItem("favorites", JSON.stringify(favorites));
            checkFavoriteStatus();
        };
    }
    // Gọi hàm setup nút yêu thích
    setupFavoriteButton(item);

    
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
// 2. XỬ LÝ TÌM ĐƯỜNG (CHẠY LOCAL - KHÔNG MOCK)
// =======================================================
document.getElementById("btn-find-route").addEventListener("click", () => {
    // Lấy phương tiện đang chọn ở Bước 1
    const modeEl = document.querySelector('input[name="transport"]:checked');
    const mode = modeEl ? modeEl.value : 'driving';
    
    // Chuyển view trước để người dùng thấy loading
    switchView(2);
    
    // Đồng bộ select box ở bước 2
    const quickSelect = document.getElementById("quick-transport-change");
    if(quickSelect) quickSelect.value = mode;

    // Gọi hàm tìm đường
    findRouteWithMode(mode);
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
    // 1. Điền thông tin cơ bản
    // Dùng try-catch để tránh lỗi nếu thiếu thẻ HTML
    try {
        if(document.getElementById("res-distance")) 
            document.getElementById("res-distance").innerText = info.distance_text;
        if(document.getElementById("res-duration"))
            document.getElementById("res-duration").innerText = info.duration_text;
    } catch(e) { console.warn("Thiếu thẻ res-distance hoặc res-duration"); }
    
    // 2. Lấy dữ liệu an toàn
    const complexity = info.complexity || {};
    const recommendation = info.recommendation || {};

    // 3. Xác định màu sắc cho nhãn độ khó
    let badgeColor = '#28a745'; // Xanh (Dễ)
    let badgeText = complexity.label || "Dễ đi";
    
    if (complexity.level === 'medium') badgeColor = '#fd7e14'; // Cam
    if (complexity.level === 'high') badgeColor = '#dc3545';   // Đỏ

    // 4. [FIX LỖI] Tìm thẻ cha để render nội dung
    // Ưu tiên tìm ID cũ "analysis-content-area", nếu không thấy thì tìm class ".complexity-box" (giống Homepage)
    let contentArea = document.getElementById("analysis-content-area");
    
    if (!contentArea) {
        contentArea = document.querySelector(".complexity-box");
    }

    // Nếu tìm thấy thẻ thì mới render
    if (contentArea) {
        contentArea.innerHTML = `
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
    } else {
        console.error("LỖI: Không tìm thấy thẻ <div id='analysis-content-area'> hoặc <div class='complexity-box'> trong HTML!");
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
        if (finalPath[0][0] > 90) {
            console.log("⚠️ Toạ độ bị ngược [Lng, Lat], đang đảo chiều...");
            finalPath = finalPath.map(p => [p[1], p[0]]);
        }
    } else {
        console.error("❌ Không có toạ độ đường đi!");
        return;
    }

    // 2. XOÁ MAP CŨ
    if (map) {
        map.remove();
        map = null;
    }

    // 3. TẠO MAP MỚI
    try {
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

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap'
    }).addTo(map);
    L.control.zoom({ position: 'topleft' }).addTo(map);

    // 4. VẼ ĐỐI TƯỢNG
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

    // 5. CHIẾN THUẬT "CƯỠNG ÉP" CẬP NHẬT GIAO DIỆN (Fix lỗi render map khi modal trượt)
    const forceUpdateMap = () => {
        if (!map) return;
        map.invalidateSize(); 

        if (routeLayer) {
            map.fitBounds(routeLayer.getBounds(), { padding: [50, 50], animate: false });
        } else {
            const group = L.featureGroup([startGroup, endGroup]);
            map.fitBounds(group.getBounds(), { padding: [50, 50], animate: false });
        }
    };

    forceUpdateMap(); 
    setTimeout(forceUpdateMap, 300);
    setTimeout(forceUpdateMap, 600);
    setTimeout(forceUpdateMap, 1000);
}

// =======================================================
// 4. SỰ KIỆN NÚT BẤM
// =======================================================

// XỬ LÝ NÚT LẤY VỊ TRÍ (GPS)
const btnGPS = document.getElementById("btn-use-gps");
if (btnGPS) {
    btnGPS.addEventListener("click", () => {
        const startInput = document.getElementById("start-location");
        
        if (!navigator.geolocation) {
            alert("Trình duyệt không hỗ trợ GPS.");
            return;
        }

        const originalText = btnGPS.innerText;
        btnGPS.innerText = "⏳";
        btnGPS.disabled = true;
        if(startInput) startInput.value = "Đang lấy vị trí...";

        navigator.geolocation.getCurrentPosition(
            (position) => {
                YOUR_LAT = position.coords.latitude;
                YOUR_LON = position.coords.longitude;
                console.log("📍 GPS:", YOUR_LAT, YOUR_LON);

                if(startInput) startInput.value = `Vị trí của tôi `;
                btnGPS.innerText = "📍";
                btnGPS.disabled = false;
                
                if (map && markerStart) {
                    markerStart.setLatLng([YOUR_LAT, YOUR_LON]).bindPopup("Vị trí hiện tại").openPopup();
                    map.setView([YOUR_LAT, YOUR_LON], 13);
                }
            },
            (error) => {
                console.error("Lỗi GPS:", error);
                alert("Không thể lấy vị trí. Hãy kiểm tra quyền truy cập.");
                if(startInput) startInput.value = "";
                btnGPS.innerText = originalText;
                btnGPS.disabled = false;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    });
}

// Nút Quay lại
document.getElementById("btn-back-step1").addEventListener("click", () => {
    switchView(1);
});

// Nút Đóng Modal
document.getElementById("btn-close-step1").addEventListener("click", () => {
    document.getElementById("routing-overlay").classList.add("hidden");
});

document.getElementById("routing-overlay").addEventListener("click", (e) => {
    if (e.target.id === "routing-overlay") {
        document.getElementById("routing-overlay").classList.add("hidden");
    }
});

// Xử lý đổi phương tiện nhanh
document.getElementById("quick-transport-change").addEventListener("change", (e) => {
    const mode = e.target.value;
    const radio = document.querySelector(`input[name="transport"][value="${mode}"]`);
    if(radio) radio.checked = true;
    document.getElementById("btn-find-route").click();
});

// =======================================================
// XỬ LÝ ĐỔI PHƯƠNG TIỆN NHANH (BƯỚC 2)
// =======================================================
// =======================================================
// XỬ LÝ LOGIC ĐỒNG BỘ & TÌM ĐƯỜNG
// =======================================================

// 1. Khi đổi ở Bước 2 (Trên bản đồ) -> Gọi tìm đường ngay
const quickTransportSelect = document.getElementById("quick-transport-change");
if (quickTransportSelect) {
    quickTransportSelect.addEventListener("change", (e) => {
        const newMode = e.target.value;
        console.log("🔄 Bước 2 đổi sang:", newMode);

        // Đồng bộ ngược lại Radio ở Bước 1
        const radioStep1 = document.querySelector(`input[name="transport"][value="${newMode}"]`);
        if (radioStep1) radioStep1.checked = true;

        // Gọi API tìm đường mới
        findRouteWithMode(newMode);
    });
}

// 2. Hàm tìm đường (Gọi API)
function findRouteWithMode(mode) {
    // Hiển thị loading
    const contentArea = document.getElementById("analysis-content-area") || document.querySelector(".complexity-box");
    if(contentArea) {
        contentArea.innerHTML = `
            <div style="text-align:center; padding:30px; color:#666;">
                <div style="font-size:24px; margin-bottom:10px;">⏳</div>
                Đang tính toán lại lộ trình cho <b>${mode === 'driving' ? 'Ô tô' : (mode === 'walking' ? 'Đi bộ' : 'Xe đạp')}</b>...
            </div>`;
    }

    const currentLang = localStorage.getItem('userLang') || 'vi';
    const BASE_URL = 'http://127.0.0.1:8000'; 

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
            // Cập nhật giao diện
            if (data.info) renderAnalysis(data.info);
            if (data.instructions) renderSteps(data.instructions);
            if (data.path) initMap(data.path);
            console.log("✅ Cập nhật lộ trình thành công!");
        } else {
            alert(`Lỗi: ${data.message}`);
        }
    })
    .catch(err => {
        console.error("Fetch Error:", err);
        if(contentArea) contentArea.innerHTML = `<p style="color:red; text-align:center;">❌ Lỗi kết nối server.</p>`;
    });
}

// 3. Khi bấm nút "Tìm đường ngay" ở Bước 1
document.getElementById("btn-find-route").addEventListener("click", () => {
    // Lấy phương tiện đang chọn ở Bước 1
    const modeEl = document.querySelector('input[name="transport"]:checked');
    const mode = modeEl ? modeEl.value : 'driving';
    
    // Chuyển sang Bước 2
    switchView(2);
    
    // Đồng bộ giá trị cho cái Select Box ở Bước 2 vừa hiện ra
    const quickSelect = document.getElementById("quick-transport-change");
    if(quickSelect) quickSelect.value = mode;

    // Gọi hàm tìm đường
    findRouteWithMode(mode);
});