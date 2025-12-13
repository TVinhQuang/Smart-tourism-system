// ================================================================
// DISPLAY REC RESULTS - For Recommendation Page (No Images)
// ================================================================

function renderResults(results, note) {
    console.log("🎨 renderResults được gọi với", results.length, "kết quả");

    // 1. Tìm container
    const list = document.getElementById("results-list");
    if (!list) {
        console.error("❌ Không tìm thấy #results-list");
        return;
    }

    list.innerHTML = "";

    // 3. Xử lý khi không có kết quả
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

    // --- LƯU DỮ LIỆU VÀO BIẾN TOÀN CỤC ---
    window.homeResults = results;
    console.log("✅ Đã lưu", results.length, "kết quả vào window.homeResults");

    // 4. Vẽ thẻ Card (KHÔNG CÓ HÌNH ẢNH)
    results.forEach((item, index) => {
        const card = createAccommodationCard(item, index);
        list.appendChild(card);
    });
}

// ================================================================
// CREATE ACCOMMODATION CARD (No Image Version)
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
    `;

    // Hover effect
    div.onmouseenter = () => {
        div.style.transform = "translateY(-2px)";
        div.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
    };
    div.onmouseleave = () => {
        div.style.transform = "translateY(0)";
        div.style.boxShadow = "0 2px 8px rgba(0,0,0,0.1)";
    };

    // Xử lý tiện ích
    let amenitiesHtml = "";
    if (Array.isArray(item.amenities) && item.amenities.length > 0) {
        amenitiesHtml = item.amenities.map(a => 
            `<span style="background:#f1f1f1; padding:4px 10px; border-radius:15px; font-size:0.85rem; margin-right:5px; color:#555; display:inline-block; margin-bottom:5px;">${a}</span>`
        ).join("");
    } else {
        amenitiesHtml = '<span style="color:#999; font-size:0.9rem;">Không có thông tin tiện ích</span>';
    }

    // Nội dung thẻ Card
    div.innerHTML = `
        <div class="accommodation-content">
            <!-- Header: Tên & Rating -->
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                <h3 class="accommodation-title" style="margin:0; font-size:1.3rem; color:#333; flex:1;">
                    ${item.name}
                </h3>
                <div class="accommodation-rating" style="color:#f39c12; font-weight:bold; font-size:1.1rem; margin-left:10px;">
                    ⭐ ${item.rating || "N/A"}
                </div>
            </div>

            <!-- Địa chỉ -->
            <p class="accommodation-description" style="margin:8px 0; color:#666; font-size:0.95rem;">
                📍 ${item.address || "Chưa có địa chỉ"}
            </p>

            <!-- Khoảng cách (nếu có) -->
            ${item.distance_km ? 
                `<p style="font-size:0.9rem; color:#666; margin:5px 0;">
                    📏 Cách trung tâm: <b style="color:#3b5bfd;">${parseFloat(item.distance_km).toFixed(2)} km</b>
                </p>` 
                : ''}
            
            <!-- Tiện ích -->
            <div style="margin:12px 0;">
                ${amenitiesHtml}
            </div>

            <!-- Footer: Giá & Nút chỉ đường -->
            <div class="price-rating-row" style="margin-top:15px; padding-top:15px; border-top:1px solid #eee; display:flex; justify-content:space-between; align-items:center;">
                <div class="accommodation-price" style="color:#3b5bfd; font-weight:bold; font-size:1.2rem;">
                    ${item.price ? Number(item.price).toLocaleString() + " VNĐ" : "Liên hệ"}
                </div>
                
                <button 
                    class="btn-routing"
                    data-index="${index}"
                    style="
                        background:#3b5bfd;
                        color:white;
                        border:none;
                        padding:10px 20px;
                        border-radius:8px;
                        cursor:pointer;
                        font-weight:600;
                        font-size:0.95rem;
                        transition:background 0.2s;
                    "
                    onmouseover="this.style.background='#2a4ad4'"
                    onmouseout="this.style.background='#3b5bfd'"
                >
                    🗺️ Chỉ đường
                </button>
            </div>
        </div>
    `;

    // Click event cho nút chỉ đường
    const btn = div.querySelector(".btn-routing");
    btn.addEventListener("click", (e) => {
        e.stopPropagation();
        console.log("🔍 Click chỉ đường cho:", item.name, "index:", index);
        
        // Gọi hàm openRoutingModal từ display_result_rec.js
        if (typeof openRoutingModal === 'function') {
            openRoutingModal(index);
        } else {
            console.error("❌ Hàm openRoutingModal chưa được định nghĩa!");
            alert("Lỗi: Không thể mở modal. Vui lòng kiểm tra console.");
        }
    });

    return div;
}

// ================================================================
// INIT
// ================================================================
console.log("✅ Display rec results module loaded");

// Export để test
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { renderResults };
}