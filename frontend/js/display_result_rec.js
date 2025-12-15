// ================================================================
// DISPLAY REC RESULTS - Modified Layout (Score + Better Rating Position)
// ================================================================

function renderResults(results, note) {
    console.log("🎨 renderResults được gọi với", results.length, "kết quả");

    const list = document.getElementById("results-list");
    if (!list) {
        console.error("❌ Không tìm thấy #results-list");
        return;
    }

    list.innerHTML = "";

    // Xử lý khi không có kết quả
    if (!results || results.length === 0) {
        list.innerHTML = `
            <div style='text-align:center; padding:40px; color:#666; background:white; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1);'>
                🚫 Không tìm thấy kết quả phù hợp.
                <br><br>
                <button onclick="window.location.reload()" style="padding:10px 20px; background:#3b5bfd; color:white; border:none; border-radius:8px; cursor:pointer;">
                    🔄 Tìm kiếm lại
                </button>
            </div>
        `;
        return;
    }

    // Lưu dữ liệu vào biến toàn cục
    window.homeResults = results;
    
    // Vẽ thẻ Card
    results.forEach((item, index) => {
        const card = createAccommodationCard(item, index);
        list.appendChild(card);
    });
}

// ================================================================
// CREATE ACCOMMODATION CARD (New Layout)
// ================================================================
function createAccommodationCard(item, index) {
    const div = document.createElement("div");
    div.className = "accommodation-card card-no-image";
    div.style.cssText = `
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
        margin-bottom: 15px;
        border: 1px solid #eee;
    `;

    // Hover effect
    div.onmouseenter = () => {
        div.style.transform = "translateY(-3px)";
        div.style.boxShadow = "0 8px 16px rgba(0,0,0,0.1)";
        div.style.borderColor = "#3b5bfd";
    };
    div.onmouseleave = () => {
        div.style.transform = "translateY(0)";
        div.style.boxShadow = "0 2px 8px rgba(0,0,0,0.1)";
        div.style.borderColor = "#eee";
    };

    // --- 1. TÍNH TOÁN SCORE & MÀU SẮC ---
    let scoreHtml = "";
    if (item.score) {
        const percent = Math.round(item.score * 100);
        let color = "#28a745"; // Xanh (Cao)
        let bg = "#e6f8eb";
        
        if(percent < 75) { color = "#ffc107"; bg = "#fff8e1"; } // Vàng (Khá)
        if(percent < 50) { color = "#dc3545"; bg = "#f8d7da"; } // Đỏ (Thấp)

        scoreHtml = `
            <span style="
                background: ${bg}; 
                color: ${color}; 
                padding: 4px 10px; 
                border-radius: 6px; 
                font-size: 0.85rem; 
                font-weight: 700;
                display: inline-flex;
                align-items: center;
                gap: 5px;
            ">
                🎯 ${percent}% phù hợp
            </span>
        `;
    }

    // --- 2. XỬ LÝ TIỆN ÍCH ---
    let amenitiesHtml = "";
    if (Array.isArray(item.amenities) && item.amenities.length > 0) {
        amenitiesHtml = item.amenities.slice(0, 5).map(a => // Chỉ lấy tối đa 5 tiện ích để gọn
            `<span style="background:#f8f9fa; border: 1px solid #e9ecef; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; color: #666;">
                ${a.charAt(0).toUpperCase() + a.slice(1)}
            </span>`
        ).join(" ");
        if(item.amenities.length > 5) amenitiesHtml += `<span style="font-size:0.8rem; color:#999;">+${item.amenities.length - 5}</span>`;
    } else {
        amenitiesHtml = '<span style="color:#999; font-size:0.85rem; font-style:italic;">Đang cập nhật tiện ích...</span>';
    }

    // --- 3. HTML CẤU TRÚC MỚI ---
    div.innerHTML = `
        <div class="accommodation-content">
            
            <h3 class="accommodation-title" style="margin: 0 0 8px 0; font-size: 1.25rem; color: #2c3e50; line-height: 1.4;">
                ${item.name}
            </h3>

            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                ${scoreHtml}
                
                <div style="display: flex; align-items: center; gap: 4px; font-weight: 600; color: #444; font-size: 0.9rem;">
                    <span style="color: #f39c12;">⭐</span> ${item.rating || "N/A"}
                    <span style="color: #999; font-weight: normal; font-size: 0.8rem;">(Rating)</span>
                </div>
            </div>

            <div style="border-left: 3px solid #eee; padding-left: 10px; margin-bottom: 12px;">
                <p style="margin: 0 0 4px 0; color: #555; font-size: 0.9rem; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden;">
                    📍 ${item.address || "Chưa có địa chỉ"}
                </p>
                ${item.distance_km ? 
                    `<p style="margin: 0; font-size: 0.9rem; color: #666;">
                        📏 Cách trung tâm: <strong style="color: #3b5bfd;">${parseFloat(item.distance_km).toFixed(2)} km</strong>
                    </p>` 
                : ''}
            </div>
            
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 15px;">
                ${amenitiesHtml}
            </div>

            <div style="
                border-top: 1px solid #f0f0f0; 
                padding-top: 15px; 
                margin-top: auto; 
                display: flex; 
                justify-content: space-between; 
                align-items: center;
            ">
                <div class="accommodation-price">
                    <span style="font-size: 0.85rem; color: #888;">Giá mỗi đêm</span><br>
                    <span style="color: #d63031; font-weight: 700; font-size: 1.2rem;">
                        ${item.price ? Number(item.price).toLocaleString() + " ₫" : "Liên hệ"}
                    </span>
                </div>
                
                <button 
                    class="btn-routing"
                    data-index="${index}"
                    style="
                        background: linear-gradient(135deg, #3b5bfd 0%, #2541d1 100%);
                        color: white;
                        border: none;
                        padding: 10px 24px;
                        border-radius: 8px;
                        cursor: pointer;
                        font-weight: 600;
                        font-size: 0.95rem;
                        box-shadow: 0 4px 10px rgba(59, 91, 253, 0.3);
                        transition: all 0.2s;
                        display: flex; align-items: center; gap: 6px;
                    "
                    onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 6px 12px rgba(59, 91, 253, 0.4)';"
                    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 10px rgba(59, 91, 253, 0.3)';"
                >
                    🗺️ Chỉ đường
                </button>
            </div>
        </div>
    `;

    // Click event
    const btn = div.querySelector(".btn-routing");
    btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (typeof openRoutingModal === 'function') {
            openRoutingModal(index);
        } else {
            console.error("❌ Hàm openRoutingModal chưa được định nghĩa!");
            alert("Lỗi: Không thể mở modal.");
        }
    });

    return div;
}

// Export module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { renderResults };
}