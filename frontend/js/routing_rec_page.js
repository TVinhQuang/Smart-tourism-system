// =======================================================
// KHAI BÁO BIẾN TOÀN CỤC
// =======================================================
let routingItem = null;
let map = null;
let myCurrentLat = 10.7769; // Mặc định TP.HCM
let myCurrentLon = 106.7009;
let isUsingGPS = false; 

// =======================================================
// 1. MỞ MODAL & KHỞI TẠO (Đã sửa lỗi hiển thị tiện ích)
// =======================================================
function openRoutingModal(index) {
    if (!window.homeResults || !window.homeResults[index]) {
        console.error("Không tìm thấy dữ liệu tại index:", index);
        return;
    }

    routingItem = window.homeResults[index];
    const overlay = document.getElementById("routing-overlay");
    if (overlay) overlay.classList.remove("hidden");

    switchView(1);

    const item = routingItem;
    document.getElementById("info-name").innerText = item.name;
    document.getElementById("info-address").innerText = item.address || "";
    
    const priceText = item.price ? Number(item.price).toLocaleString() + " VND" : "Liên hệ";
    document.getElementById("info-price").innerText = priceText;
    
    document.getElementById("info-rating").innerText = item.rating || "N/A";
    document.getElementById("target-dest").value = item.name;

    // --- XỬ LÝ HIỆN TIỆN ÍCH ---
    const amenityContainer = document.getElementById("info-amenities");
    if (amenityContainer) {
        amenityContainer.innerHTML = ""; 
        if (item.amenities && Array.isArray(item.amenities) && item.amenities.length > 0) {
            item.amenities.forEach(amenity => {
                const span = document.createElement("span");
                // Style inline để đảm bảo đẹp ngay lập tức
                span.style.cssText = "background:#f1f1f1; padding:4px 10px; border-radius:15px; font-size:0.85rem; margin:0 5px 5px 0; display:inline-block; color:#555;";
                span.innerText = amenity.charAt(0).toUpperCase() + amenity.slice(1);
                amenityContainer.appendChild(span);
            });
        } else {
            amenityContainer.innerHTML = "<span style='color:#999; font-style:italic; font-size:0.9rem;'>Không có thông tin tiện ích</span>";
        }
    }

    // Tự động kích hoạt GPS
    getUserLocation();
}

// =======================================================
// 2. XỬ LÝ GEOCODING (Hàm bị thiếu gây lỗi của bạn)
// =======================================================
async function resolveStartCoordinates() {
    const inputStart = document.getElementById("start-location");
    const query = inputStart.value.trim();

    // Nếu ô nhập trống hoặc đang là text GPS mặc định
    if (isUsingGPS || query === "" || query.includes("Vị trí của bạn")) {
        return { lat: myCurrentLat, lon: myCurrentLon };
    }

    // Gọi API tìm kiếm địa chỉ (Nominatim)
    try {
        const btn = document.getElementById("btn-find-route");
        if(btn) btn.innerText = "🔍 Đang tìm địa chỉ...";
        
        console.log("Đang tìm tọa độ cho:", query);
        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`;
        
        const res = await fetch(url);
        const data = await res.json();

        if (data && data.length > 0) {
            console.log("✅ Tìm thấy:", data[0].display_name);
            return { 
                lat: parseFloat(data[0].lat), 
                lon: parseFloat(data[0].lon) 
            };
        } else {
            alert("Không tìm thấy địa điểm: " + query);
            return null;
        }
    } catch (e) {
        console.error("Lỗi Geocoding:", e);
        alert("Lỗi khi tìm địa điểm. Vui lòng kiểm tra mạng.");
        return null;
    }
}

// =======================================================
// 3. HÀM TÌM ĐƯỜNG (EXECUTE)
// =======================================================
async function executeFindRoute(forceMode = null) {
    console.log("🚀 Bắt đầu tìm đường...");

    // A. Xử lý tọa độ điểm xuất phát
    const startCoords = await resolveStartCoordinates();
    if (!startCoords) {
        const btn = document.getElementById("btn-find-route");
        if(btn) { btn.innerText = "🗺️ Tìm đường đi"; btn.disabled = false; }
        return; 
    }

    // B. Xác định phương tiện
    let mode = 'driving';
    if (forceMode) {
        mode = forceMode;
    } else {
        const isStep2 = !document.getElementById("view-step-2").classList.contains("hidden");
        const quickSelect = document.getElementById("quick-transport-change");
        if (isStep2 && quickSelect) {
            mode = quickSelect.value;
        } else {
            const radio = document.querySelector('input[name="transport"]:checked');
            if (radio) mode = radio.value;
        }
    }

    // C. Chuẩn hoá Profile cho OSRM
    if (mode === 'foot' || mode === 'di_bo') mode = 'walking';
    if (mode === 'bike' || mode === 'bicycle') mode = 'cycling';
    if (mode === 'car' || mode === 'oto') mode = 'driving';

    // D. Gửi Request
    const btn = document.getElementById("btn-find-route");
    const originalText = "🗺️ Tìm đường đi"; 
    if(btn) { btn.innerText = "⏳ Đang tính toán..."; btn.disabled = true; }

    const currentLang = localStorage.getItem('userLang') || 'vi';

    fetch("http://127.0.0.1:5000/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            src: { lat: startCoords.lat, lon: startCoords.lon },
            dst: { lat: routingItem.lat, lon: routingItem.lon },
            profile: mode,
            lang: currentLang
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            switchView(2);
            
            // Đồng bộ Dropdown Step 2
            const quickSelect = document.getElementById("quick-transport-change");
            if (quickSelect) {
                if(mode === 'walking') quickSelect.value = 'foot'; 
                else if(mode === 'cycling') quickSelect.value = 'cycling';
                else quickSelect.value = 'driving';
            }

            renderAnalysis(data.info);
            renderSteps(data.instructions);
            
            // Vẽ bản đồ với tọa độ thực tế tìm được
            initMap(data.path, startCoords); 
        } else {
            alert("Lỗi: " + (data.message || "Không tìm thấy đường"));
        }
    })
    .catch(err => {
        console.error(err);
        alert("Lỗi kết nối Server!");
    })
    .finally(() => {
        if(btn) { btn.innerText = originalText; btn.disabled = false; }
    });
}

// =======================================================
// 4. CÁC HÀM HỖ TRỢ UI & MAP
// =======================================================

function getUserLocation() {
    const inputStart = document.getElementById("start-location");
    if (!inputStart) return;

    if (navigator.geolocation) {
        inputStart.value = "⏳ Đang lấy vị trí...";
        navigator.geolocation.getCurrentPosition(
            (position) => {
                myCurrentLat = position.coords.latitude;
                myCurrentLon = position.coords.longitude;
                isUsingGPS = true;
                inputStart.value = "📍 Vị trí của bạn (GPS)";
                console.log("📍 GPS OK:", myCurrentLat, myCurrentLon);
            },
            (error) => {
                console.warn("GPS Fail:", error.message);
                inputStart.value = ""; 
                inputStart.placeholder = "Nhập địa chỉ của bạn...";
                isUsingGPS = false;
            }
        );
    } else {
        alert("Trình duyệt không hỗ trợ GPS");
    }
}

function switchView(step) {
    const v1 = document.getElementById("view-step-1");
    const v2 = document.getElementById("view-step-2");
    if (step === 1) {
        v1?.classList.remove("hidden");
        v2?.classList.add("hidden");
    } else {
        v1?.classList.add("hidden");
        v2?.classList.remove("hidden");
    }
}

function renderAnalysis(info) {
    document.getElementById("res-distance").innerText = info.distance_text;
    document.getElementById("res-duration").innerText = info.duration_text;
    document.getElementById("res-label").innerText = info.complexity_label;
    document.getElementById("res-summary").innerText = info.complexity_summary;
    document.getElementById("res-advice").innerText = info.recommendation_msg;

    const ul = document.getElementById("res-details");
    ul.innerHTML = "";
    if (info.analysis_details) {
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
    if (instructions) {
        instructions.forEach((stepText, i) => {
            const div = document.createElement("div");
            div.className = "step-item";
            div.innerHTML = `<div class="step-icon">${i + 1}</div><div class="step-text">${stepText}</div>`;
            list.appendChild(div);
        });
    }
}

// --- HÀM VẼ MAP (Đã sửa lỗi màn hình trắng) ---
function initMap(pathCoords, startCoords) {
    console.log("--- BẮT ĐẦU VẼ MAP ---");

    let finalPath = pathCoords || [];
    // Đảo chiều nếu tọa độ bị ngược (Lng, Lat)
    if (finalPath.length > 0 && finalPath[0][0] > 90) {
        finalPath = finalPath.map(p => [p[1], p[0]]);
    }

    if (map) { map.remove(); map = null; }

    try {
        map = L.map("rt-map", { zoomControl: false, attributionControl: false });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap' }).addTo(map);
        L.control.zoom({ position: 'topleft' }).addTo(map);

        const startLat = startCoords ? startCoords.lat : myCurrentLat;
        const startLon = startCoords ? startCoords.lon : myCurrentLon;
        
        const startGroup = L.marker([startLat, startLon]).addTo(map).bindPopup("Điểm xuất phát");
        const endGroup = L.marker([routingItem.lat, routingItem.lon]).addTo(map).bindPopup("Đích đến");

        let routeLayer = null;
        if (finalPath.length > 0) {
            routeLayer = L.polyline(finalPath, { color: 'blue', weight: 5, opacity: 0.8 }).addTo(map);
        }

        // --- CHIẾN THUẬT FORCE UPDATE (Quan trọng) ---
        const forceUpdateMap = () => {
            if (!map) return;
            map.invalidateSize(); 
            if (routeLayer) map.fitBounds(routeLayer.getBounds(), { padding: [50, 50], animate: false });
            else map.fitBounds(L.featureGroup([startGroup, endGroup]).getBounds(), { padding: [50, 50] });
        };

        forceUpdateMap(); 
        setTimeout(forceUpdateMap, 300);
        setTimeout(forceUpdateMap, 600);
        setTimeout(forceUpdateMap, 1000);

    } catch (e) { console.error("Lỗi Map:", e); }
}

// =======================================================
// 5. EVENT LISTENERS
// =======================================================

const inputStart = document.getElementById("start-location");
if(inputStart) {
    inputStart.addEventListener("input", () => { isUsingGPS = false; });
}

const btnGps = document.getElementById("btn-use-gps");
if(btnGps) {
    btnGps.addEventListener("click", getUserLocation);
}

document.getElementById("btn-find-route").addEventListener("click", () => executeFindRoute());

// Sự kiện đổi phương tiện nhanh ở bước 2
const quickSelect = document.getElementById("quick-transport-change");
if (quickSelect) {
    quickSelect.addEventListener("change", function() {
        executeFindRoute(this.value);
    });
}

document.getElementById("btn-back-step1").addEventListener("click", () => switchView(1));
document.getElementById("btn-close-step1").addEventListener("click", () => document.getElementById("routing-overlay").classList.add("hidden"));
document.getElementById("routing-overlay").addEventListener("click", (e) => {
    if (e.target.id === "routing-overlay") document.getElementById("routing-overlay").classList.add("hidden");
});