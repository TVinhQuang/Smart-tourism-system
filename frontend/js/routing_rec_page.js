// =======================================================
// KHAI BÁO BIẾN TOÀN CỤC
// =======================================================
let routingItem = null;
let map = null;
let routeLine = null;
let markerStart = null;
let markerEnd = null;

// Tọa độ giả lập (TP.HCM - Quận 1)
const YOUR_LAT = 10.7628;
const YOUR_LON = 106.6825;

// =======================================================
// 1. MỞ MODAL (VÀO BƯỚC 1)
// =======================================================
function openRoutingModal(index) {
    if (!window.homeResults || !window.homeResults[index]) {
        console.error("Không tìm thấy dữ liệu tại index:", index);
        return;
    }

    routingItem = window.homeResults[index];

    // MỞ MODAL TRƯỚC
    const overlay = document.getElementById("routing-overlay");
    if (!overlay) {
        console.error("❌ Không tìm thấy routing-overlay");
        return;
    }
    overlay.classList.remove("hidden");

    // SAU ĐÓ MỚI CHUYỂN VIEW
    switchView(1);

    const item = routingItem;
    document.getElementById("info-name").innerText = item.name;
    document.getElementById("info-address").innerText = item.address || "";
    document.getElementById("info-price").innerText =
        item.price ? Number(item.price).toLocaleString() + " VND" : "Liên hệ";
    document.getElementById("info-rating").innerText = item.rating || "N/A";
    document.getElementById("target-dest").value = item.name;
}

// =======================================================
// 2. HÀM XỬ LÝ TÌM ĐƯỜNG (CORE LOGIC)
// =======================================================
function executeFindRoute() {
    console.log("🚀 Bắt đầu hàm executeFindRoute...");

    // 1. XÁC ĐỊNH PHƯƠNG TIỆN (MODE)
    let mode = 'driving'; // Mặc định

    // Kiểm tra xem đang ở Step 2 (đã có bản đồ) hay Step 1
    const viewStep2 = document.getElementById("view-step-2");
    const isStep2 = viewStep2 && !viewStep2.classList.contains("hidden");
    const quickSelect = document.getElementById("quick-transport-change");

    if (isStep2 && quickSelect) {
        // Ưu tiên lấy từ Dropdown nếu đang ở màn hình bản đồ
        mode = quickSelect.value;
        console.log("ℹ️ Lấy mode từ Dropdown (Step 2):", mode);
    } else {
        // Lấy từ Radio button nếu đang ở màn hình đầu
        const modeEl = document.querySelector('input[name="transport"]:checked');
        if (modeEl) mode = modeEl.value;
        console.log("ℹ️ Lấy mode từ Radio (Step 1):", mode);
    }

    // 2. CHUẨN HOÁ DỮ LIỆU (QUAN TRỌNG)
    // Đổi hết về chuẩn OSRM (walking, cycling, driving)
    if (mode === 'foot' || mode === 'di_bo') mode = 'walking';
    if (mode === 'bike' || mode === 'bicycle') mode = 'cycling';
    if (mode === 'car' || mode === 'moto' || mode === 'oto') mode = 'driving';

    console.log("📡 Gửi yêu cầu với Profile chuẩn hoá:", mode);

    // 3. UI LOADING
    const btn = document.getElementById("btn-find-route");
    const originalText = btn.innerText;
    btn.innerText = "⏳ Đang tính toán...";
    btn.disabled = true;

    // 4. GỌI API
    const currentLang = localStorage.getItem('userLang') || 'vi';

    fetch("http://127.0.0.1:5000/api/route", {
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

            // Đồng bộ ngược lại dropdown cho đúng hiển thị
            if (quickSelect) {
                // Nếu mode là walking, trả về value tương ứng trong HTML (ví dụ 'foot')
                // Kiểm tra xem trong HTML bạn đặt là 'foot' hay 'walking' để set cho đúng
                if(mode === 'walking') quickSelect.value = 'foot'; 
                else if(mode === 'cycling') quickSelect.value = 'cycling';
                else quickSelect.value = 'driving';
            }

            renderAnalysis(data.info);
            renderSteps(data.instructions);
            initMap(data.path);
        } else {
            alert("Lỗi: " + (data.message || "Không tìm thấy đường"));
        }
    })
    .catch(err => {
        console.error("Fetch Error:", err);
        alert("Lỗi kết nối Server!");
    })
    .finally(() => {
        btn.innerText = originalText;
        btn.disabled = false;
    });
}

// =======================================================
// 3. CÁC HÀM HỖ TRỢ (UI & MAP)
// =======================================================

function switchView(step) {
    const v1 = document.getElementById("view-step-1");
    const v2 = document.getElementById("view-step-2");

    if (step === 1) {
        if (v1) v1.classList.remove("hidden");
        if (v2) v2.classList.add("hidden");
    } else {
        if (v1) v1.classList.add("hidden");
        if (v2) v2.classList.remove("hidden");
    }
}

function renderAnalysis(info) {
    document.getElementById("res-distance").innerText = info.distance_text;
    document.getElementById("res-duration").innerText = info.duration_text;

    const labelEl = document.getElementById("res-label");
    labelEl.innerText = info.complexity_label;

    if (info.complexity_level === 'low') labelEl.style.color = 'green';
    else if (info.complexity_level === 'medium') labelEl.style.color = 'orange';
    else labelEl.style.color = 'red';

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
    console.log("--- VẼ MAP ---");
    let finalPath = pathCoords || [];
    
    // Đảo ngược toạ độ nếu cần [Lng, Lat] -> [Lat, Lng]
    if (finalPath.length > 0 && finalPath[0][0] > 90) {
        finalPath = finalPath.map(p => [p[1], p[0]]);
    }

    if (map) {
        map.remove();
        map = null;
    }

    try {
        const mapContainer = document.getElementById("rt-map");
        if (!mapContainer) return;

        map = L.map("rt-map", { zoomControl: false, attributionControl: false });
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);
        L.control.zoom({ position: 'topleft' }).addTo(map);

        const startGroup = L.marker([YOUR_LAT, YOUR_LON]).addTo(map).bindPopup("Bạn ở đây");
        const endGroup = L.marker([routingItem.lat, routingItem.lon]).addTo(map).bindPopup("Đích đến");

        let routeLayer = null;
        if (finalPath.length > 0) {
            routeLayer = L.polyline(finalPath, { color: 'blue', weight: 5, opacity: 0.8 }).addTo(map);
        }

        const forceUpdateMap = () => {
            if (!map) return;
            map.invalidateSize();
            if (routeLayer) map.fitBounds(routeLayer.getBounds(), { padding: [50, 50], animate: false });
            else map.fitBounds(L.featureGroup([startGroup, endGroup]).getBounds(), { padding: [50, 50] });
        };

        setTimeout(forceUpdateMap, 100);
        setTimeout(forceUpdateMap, 500);
    } catch (e) {
        console.error("Lỗi Map:", e);
    }
}

// =======================================================
// 4. SỰ KIỆN (EVENT LISTENERS) - PHẦN QUAN TRỌNG NHẤT
// =======================================================

// A. Nút "Tìm đường" ở Bước 1
document.getElementById("btn-find-route").addEventListener("click", () => {
    executeFindRoute(); // Gọi hàm chung
});

// B. Dropdown thay đổi ở Bước 2
const quickSelect = document.getElementById("quick-transport-change");
if (quickSelect) {
    quickSelect.addEventListener("change", (e) => {
        console.log("🔄 Phát hiện thay đổi Dropdown:", e.target.value);
        executeFindRoute(); // Gọi hàm chung ngay lập tức
    });
} else {
    console.error("❌ Không tìm thấy element #quick-transport-change");
}

// C. Các nút điều hướng khác
document.getElementById("btn-back-step1").addEventListener("click", () => switchView(1));
document.getElementById("btn-close-step1").addEventListener("click", () => {
    document.getElementById("routing-overlay").classList.add("hidden");
});
document.getElementById("routing-overlay").addEventListener("click", (e) => {
    if (e.target.id === "routing-overlay") {
        document.getElementById("routing-overlay").classList.add("hidden");
    }
});