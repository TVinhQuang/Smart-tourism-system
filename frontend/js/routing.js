let routingItem = null;
let map = null;
let routeLine = null;
let markerStart = null;
let markerEnd = null;

// Tọa độ giả lập (Nhà bạn)
const YOUR_LAT = 21.0075535;
const YOUR_LON = 105.8427515;

// === 1. MỞ MODAL (VÀO BƯỚC 1) ===
// File: routing.js

// ... (Giữ nguyên các biến global ở trên)

function openRoutingModal(index) {
    if (!window.homeResults || !window.homeResults[index]) return;
    const item = window.homeResults[index];
    routingItem = item;

    // Reset giao diện về Bước 1
    switchView(1);

    // 1. Điền thông tin cơ bản
    document.getElementById("info-img").src = item.img || 'https://via.placeholder.com/300';
    document.getElementById("info-name").innerText = item.name;
    document.getElementById("info-address").innerText = item.address;
    document.getElementById("info-price").innerText = Number(item.price).toLocaleString() + " VNĐ";
    document.getElementById("info-rating").innerText = item.rating;
    document.getElementById("info-desc").innerText = item.desc;
    document.getElementById("target-dest").value = item.name;

    // 2. XỬ LÝ TIỆN ÍCH (MỚI)
    const amenityContainer = document.getElementById("info-amenities");
    amenityContainer.innerHTML = ""; // Xóa các tiện ích cũ

    if (item.amenities && item.amenities.length > 0) {
        item.amenities.forEach(am => {
            // Tạo thẻ span cho mỗi tiện ích
            const span = document.createElement("span");
            span.className = "amenity-tag";
            span.innerText = am;
            amenityContainer.appendChild(span);
        });
    } else {
        amenityContainer.innerHTML = "<span style='color:#999; font-style:italic'>Đang cập nhật...</span>";
    }
    // 3. Xử lý Input "Vị trí của bạn"
    const startInput = document.querySelector('.input-readonly');
    // Gán giá trị từ file ngôn ngữ
    if(startInput) {
        startInput.value = window.langData["val_my_location"];
    }

    // Hiển thị modal
    document.getElementById("routing-overlay").classList.remove("hidden");
}

// ... (Các phần còn lại giữ nguyên)

// === 2. XỬ LÝ TÌM ĐƯỜNG (CHUYỂN SANG BƯỚC 2) ===
document.getElementById("btn-find-route").addEventListener("click", () => {
    // Lấy phương tiện đang chọn
    const mode = document.querySelector('input[name="transport"]:checked').value;
    
    // Hiển thị loading
    const btn = document.getElementById("btn-find-route");
    btn.innerText = "⏳ Đang xử lý...";
    btn.disabled = true;

    // Gọi API
    fetch("http://localhost:5000/api/route", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            src: { lat: YOUR_LAT, lon: YOUR_LON },
            dst: { lat: routingItem.lat, lon: routingItem.lon },
            profile: mode
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            // Chuyển sang Bước 2
            switchView(2);
            
            // Đồng bộ select box ở bước 2 với lựa chọn ở bước 1
            document.getElementById("quick-transport-change").value = mode;

            // Render dữ liệu phân tích
            renderAnalysis(data.info);
            renderSteps(data.instructions);
            
            // Render Bản đồ
            initMap(data.path, mode);

        } else {
            alert("❌ Không tìm thấy đường đi! (" + data.message + ")");
        }
    })
    .catch(err => {
        console.error(err);
        alert("Lỗi kết nối Server!");
    })
    .finally(() => {
        btn.innerText = "🗺️ Tìm đường đi";
        btn.disabled = false;
    });
});

// === CÁC HÀM HỖ TRỢ ===

function switchView(step) {
    if (step === 1) {
        document.getElementById("view-step-1").classList.remove("hidden");
        document.getElementById("view-step-2").classList.add("hidden");
    } else {
        document.getElementById("view-step-1").classList.add("hidden");
        document.getElementById("view-step-2").classList.remove("hidden");
    }
}

function renderAnalysis(info) {
    document.getElementById("res-distance").innerText = info.distance_text;
    document.getElementById("res-duration").innerText = info.duration_text;
    
    const labelEl = document.getElementById("res-label");
    labelEl.innerText = info.complexity_label;
    labelEl.style.color = (info.complexity_level === 'low') ? 'green' : (info.complexity_level === 'medium' ? 'orange' : 'red');

    document.getElementById("res-summary").innerText = info.complexity_summary;
    document.getElementById("res-advice").innerText = info.recommendation_msg;

    const ul = document.getElementById("res-details");
    ul.innerHTML = "";
    info.analysis_details.forEach(detail => {
        const li = document.createElement("li");
        li.innerText = detail;
        ul.appendChild(li);
    });
}

function renderSteps(instructions) {
    const list = document.getElementById("steps-list");
    list.innerHTML = "";
    instructions.forEach((stepText, i) => {
        const div = document.createElement("div");
        div.className = "step-item";
        
        // Thêm delay cho từng phần tử để chúng hiện ra lần lượt
        // Phần tử 1 trễ 0s, phần tử 2 trễ 0.05s, phần tử 3 trễ 0.1s...
        div.style.animationDelay = `${i * 0.05}s`; 
        
        div.innerHTML = `
            <div class="step-icon">${i + 1}.</div>
            <div class="step-text">${stepText}</div>
        `;
        list.appendChild(div);
    });
}

function initMap(pathCoords, mode) {
    // 1. Khởi tạo map nếu chưa có
    if (!map) {
        map = L.map('rt-map-frame');
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
    }
    
    // Quan trọng: Phải gọi invalidateSize khi hiện map trong div ẩn trước đó
    setTimeout(() => { map.invalidateSize(); }, 100);

    // 2. Vẽ Marker
    if (markerStart) map.removeLayer(markerStart);
    if (markerEnd) map.removeLayer(markerEnd);
    
    markerStart = L.marker([YOUR_LAT, YOUR_LON]).addTo(map).bindPopup("Xuất phát").openPopup();
    markerEnd = L.marker([routingItem.lat, routingItem.lon]).addTo(map).bindPopup(routingItem.name);

    // 3. Vẽ đường đi
    if (routeLine) map.removeLayer(routeLine);
    routeLine = L.polyline(pathCoords, {color: 'blue', weight: 6, opacity: 0.8}).addTo(map);
    
    // Zoom vừa khít
    map.fitBounds(routeLine.getBounds(), {padding: [50, 50]});
}

// === CÁC NÚT ĐIỀU KHIỂN KHÁC ===

// Nút Quay lại (Từ B2 -> B1)
document.getElementById("btn-back-step1").addEventListener("click", () => {
    switchView(1);
});

// Nút Đóng Modal
document.getElementById("btn-close-step1").addEventListener("click", () => {
    document.getElementById("routing-overlay").classList.add("hidden");
});

// Đóng khi click ra ngoài
document.getElementById("routing-overlay").addEventListener("click", (e) => {
    if (e.target.id === "routing-overlay") {
        document.getElementById("routing-overlay").classList.add("hidden");
    }
});

// (Option) Xử lý đổi phương tiện nhanh ở Bước 2
document.getElementById("quick-transport-change").addEventListener("change", (e) => {
    // Kích hoạt lại nút Tìm đường ở B1 với giá trị mới rồi giả lập click
    const mode = e.target.value;
    document.querySelector(`input[name="transport"][value="${mode}"]`).checked = true;
    document.getElementById("btn-find-route").click(); // Gọi lại API
});