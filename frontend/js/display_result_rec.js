// File: js/display_results.js

function renderResults(results, note) {
    // 1. Xác định nơi chứa kết quả
    const list = document.getElementById("results-list"); 
    if (!list) return;

    list.innerHTML = "";
    
    // Lưu dữ liệu vào biến toàn cục để Modal có thể đọc được (Giống Homepage)
    window.homeResults = results; 

    // 2. Hiển thị ghi chú (nếu có)
    if (note) {
        const noteDiv = document.createElement("div");
        noteDiv.innerHTML = `<em>💡 Lưu ý: ${note}</em>`;
        noteDiv.style.color = "#d9534f";
        noteDiv.style.marginBottom = "15px";
        noteDiv.style.gridColumn = "1 / -1"; // Tràn hết chiều ngang nếu dùng Grid
        list.appendChild(noteDiv);
    }

    if (!results || results.length === 0) {
        list.innerHTML = "<div style='text-align:center; padding:20px; color:#666;'>🚫 Không tìm thấy kết quả phù hợp.</div>";
        return;
    }

    // 3. Vẽ từng thẻ Card (Giống cấu trúc Homepage nhưng bỏ ảnh)
    results.forEach((item, index) => {
        const card = document.createElement("div");
        
        // Thêm class 'card-no-image' để CSS nhận diện đây là Rec Page
        card.className = "accommodation-card card-no-image"; 

        // Xử lý tiện ích (Amenities)
        let amenitiesHtml = "";
        if (Array.isArray(item.amenities) && item.amenities.length > 0) {
            amenitiesHtml = item.amenities.slice(0, 3).map(a => 
                `<span style="background:#f1f1f1; padding:2px 8px; border-radius:4px; font-size:0.8rem; margin-right:5px; color:#555;">${a}</span>`
            ).join("");
        }

        // Tạo nội dung HTML (BỎ PHẦN IMG)
        card.innerHTML = `
            <div class="accommodation-content" style="padding: 15px; display: flex; flex-direction: column; flex-grow: 1;">
                
                <div style="display:flex; justify-content:space-between; align-items:start;">
                    <h3 class="accommodation-title" style="margin:0;">${index + 1}. ${item.name}</h3>
                    <div class="accommodation-rating" style="color: #f39c12; font-weight: bold; white-space: nowrap;">
                        ★ ${item.rating || 'N/A'}
                    </div>
                </div>

                <p style="margin: 8px 0; color: #666; font-size: 0.9rem;">
                    📍 ${item.address || "Đà Nẵng"}
                </p>

                <div style="margin-bottom: 12px; min-height: 25px;">
                    ${amenitiesHtml}
                </div>
                
                <div style="margin-top: auto; padding-top: 15px; border-top: 1px solid #eee;">
                    <div class="price-rating-row" style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="accommodation-price">${Number(item.price).toLocaleString()} VND</div>
                        
                        <button onclick="openRoutingModal(${index})" 
                            style="background:#3b5bfd; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-weight:600;">
                            🗺️ Xem bản đồ
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        list.appendChild(card);
    });
}