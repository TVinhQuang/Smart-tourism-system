// Global variable
let selectedMode = "driving"; 

function submitSearch() {
    // 1. Thu thập dữ liệu từ Form
    const data = {
        city: document.getElementById("city").value,
        group_size: parseInt(document.getElementById("group-size").value) || 1,
        price_min: parseFloat(document.getElementById("price-min").value) || 0,
        price_max: parseFloat(document.getElementById("price-max").value) || 10000000,
        types: Array.from(document.querySelectorAll(".type-checkbox:checked")).map(c => c.value),
        rating_min: parseFloat(document.getElementById("min-rating").value) || 0,
        amenities_required: Array.from(document.querySelectorAll(".amenity-required:checked")).map(c => c.value),
        amenities_preferred: Array.from(document.querySelectorAll(".amenity-preferred:checked")).map(c => c.value),
        radius_km: parseFloat(document.getElementById("radius").value) || 5,
        priority: document.getElementById("priority").value
    };

    console.log("Sending Data:", data); // Debug

    // 2. Gọi API (Giả lập hoặc gọi thật)
    fetch("http://localhost:5000/api/recommend", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(response => {
        console.log("Backend Response:", response);

        // Lưu tâm bản đồ nếu có
        if (response.center) {
            window.search_center = response.center;
        }

        // Render kết quả
        if (response.results) {
            renderResults(response.results, response.relaxation_note);
        } else {
            alert("Không có dữ liệu trả về!");
        }
    })
    .catch(err => {
        console.error("API Error:", err);
        // --- CHẾ ĐỘ GIẢ LẬP (FALLBACK) ---
        // Nếu không có Backend, tự hiển thị dữ liệu mẫu để test giao diện
        console.warn("Đang sử dụng dữ liệu mẫu do lỗi API...");
        const mockResults = [
            { name: "Sena Homestay", type: "Homestay", address: "Sơn Trà, Đà Nẵng", rating: 9.6, price: 300000, amenities: ["Wifi", "Gần biển"] },
            { name: "City Hostel", type: "Hostel", address: "Hải Châu, Đà Nẵng", rating: 9.0, price: 325000, amenities: ["Wifi", "Bữa sáng"] },
            { name: "Luxury Hotel", type: "Hotel", address: "Ngũ Hành Sơn", rating: 8.5, price: 1200000, amenities: ["Pool", "Parking"] }
        ];
        renderResults(mockResults, "Gợi ý dựa trên dữ liệu mẫu.");
    });
}

function renderResults(results, relaxationNote) {
    // SỬA LỖI 1: Target vào đúng #results-list để giữ lại tiêu đề h2 bên ngoài
    const listContainer = document.getElementById("results-list");
    
    if (!listContainer) {
        console.error("Không tìm thấy div #results-list!");
        return;
    }

    listContainer.innerHTML = ""; // Xóa kết quả cũ

    // Hiển thị thông báo nới lỏng tiêu chí (nếu có) - Thêm vào đầu list hoặc alert
    if (relaxationNote) {
        alert("Lưu ý: " + relaxationNote);
    }

    if (results.length === 0) {
        listContainer.innerHTML = "<p>Không tìm thấy kết quả phù hợp.</p>";
        return;
    }

    results.forEach((place, index) => {
        // SỬA LỖI 2: Tạo cấu trúc HTML khớp với CSS .accommodation-card
        const card = document.createElement("div");
        card.className = "accommodation-card card-no-image"; // Class khớp CSS
        
        // Xử lý amenities hiển thị đẹp hơn
        const amenitiesHTML = place.amenities 
            ? place.amenities.slice(0, 3).map(a => `<span style="background:#eee; padding:2px 6px; border-radius:4px; font-size:12px; margin-right:4px;">${a}</span>`).join("") 
            : "";

        card.innerHTML = `
            <div class="accommodation-content">
                <h3>${index + 1}. ${place.name || "Chỗ ở không tên"}</h3>
                <p style="font-size:0.9rem; color:#777;">📍 ${place.address || "Chưa cập nhật địa chỉ"}</p>
                <div style="margin-top:8px;">${amenitiesHTML}</div>
            </div>
            
            <div class="price-rating-row">
                <span class="price">${place.price ? place.price.toLocaleString() + ' VNĐ' : "Liên hệ"}</span>
                <span class="rating">★ ${place.rating || "N/A"}</span>
            </div>

            <button class="route-btn" style="margin-top:10px; width:100%; padding:8px; background:#eef2ff; color:#667eea; border:none; border-radius:6px; cursor:pointer; font-weight:bold;">
                🚗 Chỉ đường
            </button>
        `;
        
        // SỬA LỖI 3: Gán sự kiện click cho nút "Chỉ đường" để mở Modal
        const btn = card.querySelector(".route-btn");
        // Hàm openRoutingModal này sẽ gọi từ file routing_rec_page.js
        btn.addEventListener("click", () => {
            if (typeof openRoutingModal === "function") {
                openRoutingModal(place); 
            } else {
                console.error("Chưa load được hàm openRoutingModal từ file routing_rec_page.js");
            }
        });

        listContainer.appendChild(card);
    });
}
