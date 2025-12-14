// display_results.js - PHIÊN BẢN CHUẨN (ĐÃ XÓA CODE RÁC GÂY LỖI)

function renderResults(results, note) {
    // 1. Xác định container (Ưu tiên ID của trang tìm kiếm)
    let list = document.getElementById("results-list");
    let isHomepage = false;

    // Nếu không thấy, tìm ID của trang chủ
    if (!list) {
        list = document.getElementById("accommodation-list");
        if (list) isHomepage = true;
    }

    if (!list) return;
    list.innerHTML = "";

    // 2. Hiển thị ghi chú (chỉ cho trang tìm kiếm)
    if (note && !isHomepage) {
        const noteDiv = document.createElement("div");
        noteDiv.innerHTML = `<em>💡 Lưu ý: ${note}</em>`;
        noteDiv.style.color = "#d9534f";
        noteDiv.style.marginBottom = "15px";
        noteDiv.style.padding = "0 10px";
        list.appendChild(noteDiv);
    }

    // 3. Xử lý khi không có kết quả
    if (!results || results.length === 0) {
        list.innerHTML = "<div style='text-align:center; padding:20px; color:#666;'>🚫 Không tìm thấy kết quả phù hợp.</div>";
        return;
    }

    // --- QUAN TRỌNG: Lưu dữ liệu vào biến toàn cục để routing.js sử dụng ---
    window.homeResults = results; 

    // 4. Vẽ thẻ Card
    results.forEach((item, index) => {
        const div = document.createElement("div");
        
        // Dùng class chuẩn để ăn CSS đẹp
        div.className = "accommodation-card"; 
        
        // Logic: Homepage có ảnh, Search page (API) thường không có ảnh -> Thêm class no-image
        const hasImage = isHomepage || (item.img && item.img.length > 10);
        if (!hasImage) {
            div.classList.add("card-no-image");
        }

        // Xử lý tiện ích
        let amenitiesHtml = "";
        if (Array.isArray(item.amenities) && item.amenities.length > 0) {
            amenitiesHtml = item.amenities.map(a => 
                `<span style="background:#f1f1f1; padding:2px 8px; border-radius:4px; font-size:0.8rem; margin-right:5px; color:#555;">${a}</span>`
            ).join("");
        }

        // Phần Hình ảnh (Chỉ hiện nếu có)
        let imagePart = "";
        if (hasImage) {
            imagePart = `
                <div style="height: 200px; overflow: hidden;">
                    <img src="${item.img}" alt="${item.name}" style="width: 100%; height: 100%; object-fit: cover;">
                </div>
            `;
        }

        // Nội dung thẻ Card
        div.innerHTML = `
            ${imagePart}
            <div class="accommodation-content" style="padding: 15px;">
                <div class="price-rating-row" style="margin-bottom: 5px; display: flex; justify-content: space-between; align-items: center;">
                     <h3 class="accommodation-title" style="margin:0; font-size:1.2rem;">${item.name}</h3>
                     <div class="accommodation-rating" style="color: #f39c12; font-weight: bold;">
                        <span class="star">★</span> ${item.rating}
                     </div>
                </div>

                <p class="accommodation-description" style="margin-bottom: 8px; color: #666; font-size: 0.9rem;">
                    📍 ${item.address}
                </p>

                ${!hasImage && item.distance_km ? 
                    `<p style="font-size:0.9rem; color:#666; margin-bottom:8px;">📏 Cách trung tâm: <b>${parseFloat(item.distance_km).toFixed(2)} km</b></p>` 
                    : ''}
                
                <div style="margin-bottom: 12px;">
                    ${amenitiesHtml}
                </div>

                <div class="price-rating-row" style="margin-top:auto; padding-top:10px; border-top:1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
                    <div class="accommodation-price" style="color: #3b5bfd; font-weight: bold; font-size: 1.1rem;">${Number(item.price).toLocaleString()} VNĐ</div>
                    
                    <button onclick="openRoutingModal(${index})" style="background:#3b5bfd; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-weight:600;">
                        🗺️ Chỉ đường
                    </button>
                </div>
            </div>
        `;
        
        list.appendChild(div);
    });
}
// ========================
// VIEW MAP FUNCTION
// ========================
function viewMap(dstLat, dstLon, dstName) {

    const src = window.search_center;
    if (!src) {
        alert("Chưa có vị trí xuất phát!");
        return;
    }

    const payload = {
        src: { lat: src.lat, lon: src.lon, name: "Điểm xuất phát" },
        dst: { lat: dstLat, lon: dstLon, name: dstName }
    };

    // Lưu ý: Không có dấu / ở cuối domain nếu trong đường dẫn đã có /
    const BASE_URL = 'https://smart-tourism-system-production.up.railway.app';

    fetch(`${BASE_URL}/api/recommend-hotel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.map_url) {
            window.open("http://localhost:5000" + data.map_url, "_blank");
        } else {
            alert("Không vẽ được bản đồ!");
        }
    })
    .catch(err => {
        console.error("Route error:", err);
        alert("Không lấy được dữ liệu tuyến đường!");
    });
}

// ========================
// SHOW MAP POPUP + STEPS
// ========================
function showMapAndRoute(data) {
    const popup = document.getElementById("map-popup");
    popup.style.display = "block";

    document.getElementById("main-route").innerText = data.main_route;

    const detailBox = document.getElementById("detail-steps");
    detailBox.innerHTML = data.steps.map(s => `<li>${s}</li>`).join("");

    document.getElementById("toggle-details").onclick = () => {
        detailBox.style.display = (detailBox.style.display === "none") ? "block" : "none";
    };

    let map = L.map("map").setView([data.start_lat, data.start_lng], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);
    L.polyline(data.polyline, { color: "blue" }).addTo(map);
}

// ========================
// CLICK LISTENER
// ========================
document.addEventListener("click", function(event) {
    if (event.target.classList.contains("view-map-btn")) {
        const lat = event.target.getAttribute("data-lat");
        const lng = event.target.getAttribute("data-lng");
        viewMap(lat, lng, "Điểm đến");
    }
});
