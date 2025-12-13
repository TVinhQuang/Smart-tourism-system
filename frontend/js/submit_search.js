// ================================================================
// SUBMIT SEARCH - Sử dụng renderResults từ display_results.js
// ================================================================

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

    console.log("📤 Sending Data:", data);

    // Hiển thị loading (nếu có element)
    const loadingEl = document.getElementById("search-loading");
    if (loadingEl) loadingEl.style.display = "block";

    // 2. Gọi API
    fetch("http://localhost:5000/api/recommend", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data)
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
    })
    .then(response => {
        console.log("✅ Backend Response:", response);

        // Ẩn loading
        if (loadingEl) loadingEl.style.display = "none";

        // Lưu tâm bản đồ nếu có
        if (response.center) {
            window.search_center = response.center;
            console.log("📍 Search center:", window.search_center);
        }

        // Render kết quả (Gọi hàm từ display_results.js)
        if (response.results && response.results.length > 0) {
            console.log("🎨 Rendering", response.results.length, "results");
            
            // ✅ Gọi hàm renderResults từ display_results.js
            if (typeof renderResults === 'function') {
                renderResults(response.results, response.relaxation_note);
            } else {
                console.error("❌ Hàm renderResults chưa được load! Kiểm tra file display_results.js");
            }
        } else {
            console.warn("⚠️ Không có kết quả");
            showNoResults();
        }
    })
    .catch(err => {
        console.error("❌ API Error:", err);
        
        // Ẩn loading
        if (loadingEl) loadingEl.style.display = "none";
        
        // --- FALLBACK: Dữ liệu mẫu ---
        console.warn("⚠️ Đang sử dụng dữ liệu mẫu do lỗi API...");
        
        const mockResults = [
            { 
                name: "KHANG HOMESTAY ĐÀ NẴNG", 
                type: "Homestay", 
                address: "152/4 Trưng Nữ Vương, Phước Ninh, Hải Châu, Đà Nẵng",
                rating: 9,
                price: 950000,
                amenities: ["wifi"],
                lat: 16.0579016,
                lon: 108.2203421,
                distance_km: 1.01,
                id: "mock-1"
            },
            { 
                name: "Sena Homestay", 
                type: "Homestay", 
                address: "Sơn Trà, Đà Nẵng",
                rating: 9.6,
                price: 300000,
                amenities: ["wifi", "beach"],
                lat: 16.0854,
                lon: 108.2497,
                distance_km: 3.2,
                id: "mock-2"
            },
            { 
                name: "City Hostel", 
                type: "Hostel", 
                address: "Hải Châu, Đà Nẵng",
                rating: 9.0,
                price: 325000,
                amenities: ["wifi", "breakfast"],
                lat: 16.0544,
                lon: 108.2022,
                distance_km: 0.5,
                id: "mock-3"
            },
            { 
                name: "Luxury Hotel", 
                type: "Hotel", 
                address: "Ngũ Hành Sơn, Đà Nẵng",
                rating: 8.5,
                price: 1200000,
                amenities: ["pool", "parking", "spa"],
                lat: 16.0010,
                lon: 108.2620,
                distance_km: 7.8,
                id: "mock-4"
            }
        ];

        // Lưu center giả lập
        window.search_center = {
            lat: 16.0544,
            lon: 108.2022,
            name: "Đà Nẵng"
        };

        // ✅ Gọi hàm renderResults từ display_results.js
        if (typeof renderResults === 'function') {
            renderResults(mockResults, "⚠️ Dữ liệu mẫu (Server không khả dụng)");
        } else {
            console.error("❌ Hàm renderResults chưa được load!");
            alert("Lỗi: Không thể hiển thị kết quả. Vui lòng kiểm tra console.");
        }
    });
}

// ================================================================
// HELPER FUNCTION - Hiển thị khi không có kết quả
// ================================================================
function showNoResults() {
    const container = document.getElementById("results-list") || 
                     document.getElementById("accommodation-list");
    
    if (!container) {
        console.error("❌ Không tìm thấy container để hiển thị thông báo");
        return;
    }

    container.innerHTML = `
        <div style="
            text-align:center;
            padding:60px 20px;
            background:white;
            border-radius:12px;
            box-shadow:0 2px 8px rgba(0,0,0,0.1);
            margin:20px 0;
        ">
            <div style="font-size:4rem; margin-bottom:20px;">🔍</div>
            <h3 style="color:#333; margin-bottom:10px; font-size:1.5rem;">
                Không tìm thấy kết quả phù hợp
            </h3>
            <p style="color:#666; margin-bottom:20px; font-size:1rem;">
                Vui lòng thử lại với điều kiện tìm kiếm khác
            </p>
            <button 
                onclick="window.location.reload()"
                style="
                    padding:12px 24px;
                    background:#3b5bfd;
                    color:white;
                    border:none;
                    border-radius:8px;
                    font-size:1rem;
                    cursor:pointer;
                    transition:background 0.2s;
                "
                onmouseover="this.style.background='#2a4ad4'"
                onmouseout="this.style.background='#3b5bfd'"
            >
                🔄 Tìm kiếm lại
            </button>
        </div>
    `;
}

// ================================================================
// INIT
// ================================================================
console.log("✅ Submit search module loaded");

// Kiểm tra xem renderResults đã được load chưa
document.addEventListener('DOMContentLoaded', () => {
    if (typeof renderResults !== 'function') {
        console.warn("⚠️ Hàm renderResults chưa được tìm thấy. Đảm bảo display_results.js được load trước submit_search.js");
    }
});