// ================================================================
// DISPLAY REC RESULTS - Updated for New Data Structure
// ================================================================

function renderResults(results) {
    console.log("🎨 renderResults gọi với", results.length, "kết quả");

    const list = document.getElementById("results-list");
    if (!list) return;
    list.innerHTML = "";

    // Lưu biến toàn cục để dùng cho map modal
    window.homeResults = results;

    results.forEach((item, index) => {
        const card = createAccommodationCard(item, index);
        list.appendChild(card);
    });
}

function createAccommodationCard(item, index) {
    const div = document.createElement("div");
    div.className = "accommodation-card";
    // Inline CSS cho nhanh, hoặc bạn move vào css file
    div.style.cssText = `
        background: white; border-radius: 12px; padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px;
        border: 1px solid #eee; transition: all 0.2s; position: relative;
    `;

    // --- 1. XỬ LÝ BADGE ĐIỂM SỐ (Match Score từ Backend) ---
    let scoreBadge = "";
    if (item.match_score) {
        // Backend trả về 0.0 -> 1.0 (ví dụ 0.854)
        const percent = Math.round(item.match_score * 100);
        let color = percent >= 80 ? "#28a745" : (percent >= 60 ? "#ffc107" : "#6c757d");
        
        scoreBadge = `
            <div style="position: absolute; top: 20px; right: 20px; text-align: right;">
                <div style="font-size: 1.5rem; font-weight: 800; color: ${color}; line-height: 1;">
                    ${percent}<small style="font-size: 0.8rem">%</small>
                </div>
                <div style="font-size: 0.75rem; color: #888;">Độ phù hợp</div>
            </div>
        `;
    }

    // --- 2. XỬ LÝ HẠNG SAO (Stars) ---
    // Backend trả về item.stars (float), ví dụ 4.0 hoặc 5.0
    let starsHtml = "";
    if ((item.type === "hotel" || item.type === "resort") && item.stars > 0) {
        const starCount = Math.round(item.stars);
        starsHtml = `<span style="color: #f39c12; margin-right: 8px;">${"⭐".repeat(starCount)}</span>`;
    }

    // --- 3. TIỆN ÍCH ---
    let amenitiesHtml = "";
    if (Array.isArray(item.amenities) && item.amenities.length > 0) {
        amenitiesHtml = item.amenities.slice(0, 5).map(a => 
            `<span style="background:#f1f3f5; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; color: #495057;">
                ${formatAmenityName(a)}
            </span>`
        ).join(" ");
        if(item.amenities.length > 5) amenitiesHtml += `<span style="font-size:0.8rem; color:#999;">+${item.amenities.length - 5}</span>`;
    } else {
        amenitiesHtml = '<span style="color:#999; font-size:0.8rem; font-style:italic;">Đang cập nhật tiện ích...</span>';
    }

    // --- 4. FORMAT GIÁ ---
    let priceDisplay = "Liên hệ";
    if (item.price && item.price > 0) {
        priceDisplay = Number(item.price).toLocaleString('vi-VN') + " ₫";
    }

    // --- 5. RATING & REVIEWS ---
    // item.rating (0-5), item.reviews (int)
    let reviewText = item.reviews > 0 ? `(${item.reviews} đánh giá)` : "";
    let ratingBadge = item.rating > 0 
        ? `<span style="background: #3b5bfd; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold;">${item.rating.toFixed(1)}</span>`
        : `<span style="color:#999; font-size:0.9rem;">Chưa có rating</span>`;

    // --- 6. HTML CONTENT ---
    div.innerHTML = `
        ${scoreBadge}
        <div style="padding-right: 80px;"> <h3 style="margin: 0 0 5px 0; color: #2c3e50; font-size: 1.3rem;">
                ${index + 1}. ${item.name}
            </h3>
            
            <div style="margin-bottom: 8px; font-size: 0.95rem; color: #666;">
                ${starsHtml}
                <span style="text-transform: capitalize; background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem;">
                    ${item.type}
                </span>
            </div>

            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                ${ratingBadge}
                <span style="color: #666; font-size: 0.9rem;">${reviewText}</span>
            </div>

            <p style="margin: 0 0 8px 0; color: #555; font-size: 0.9rem;">
                📍 ${item.address || "Chưa có địa chỉ cụ thể"}
            </p>
            
            ${item.distance_km ? 
                `<p style="margin: 0 0 10px 0; font-size: 0.9rem; color: #666;">
                    📏 Cách trung tâm: <strong style="color: #3b5bfd;">${item.distance_km.toFixed(2)} km</strong>
                </p>` 
            : ''}

            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 15px;">
                ${amenitiesHtml}
            </div>
        </div>

        <div style="border-top: 1px solid #f0f0f0; padding-top: 15px; margin-top: auto; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="font-size: 0.85rem; color: #888;">Giá trung bình/đêm</span><br>
                <span style="color: #d63031; font-weight: 700; font-size: 1.3rem;">${priceDisplay}</span>
            </div>
            
            <button class="btn-routing" data-index="${index}" style="
                background: #3b5bfd; color: white; border: none; padding: 10px 20px;
                border-radius: 8px; cursor: pointer; font-weight: 600;
                display: flex; align-items: center; gap: 6px; box-shadow: 0 4px 6px rgba(59, 91, 253, 0.2);
            ">
                🗺️ Chỉ đường
            </button>
        </div>
    `;

    // Event Listener cho nút Chỉ đường
    const btn = div.querySelector(".btn-routing");
    btn.addEventListener("click", (e) => {
        e.stopPropagation(); // Tránh click nhầm vào card nếu sau này card có sự kiện click
        if (typeof openRoutingModal === 'function') {
            openRoutingModal(index); // Gọi hàm bên file routing_rec_page.js
        } else {
            alert("Chức năng chỉ đường đang được tải...");
        }
    });

    return div;
}

// Helper: Format tên tiện ích cho đẹp
function formatAmenityName(code) {
    const map = {
        "wifi": "Wifi Free",
        "breakfast": "Bữa sáng",
        "pool": "Hồ bơi",
        "parking": "Đỗ xe",
        "gym": "Gym",
        "spa": "Spa",
        "restaurant": "Nhà hàng",
        "bar": "Bar",
        "air_conditioning": "Điều hoà",
        "airport_shuttle": "Xe đưa đón"
    };
    return map[code] || code.charAt(0).toUpperCase() + code.slice(1);
}

// Export module (cho Nodejs env nếu cần)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { renderResults };
}