// ================================================================
// SUBMIT SEARCH - Đã lược bỏ Ngày & Số lượng khách
// ================================================================

function submitSearch() {
    // 1. Thu thập dữ liệu Cơ bản
    const city = document.getElementById("city").value;
    
    // Xử lý giá tiền (Nếu không nhập thì lấy mặc định)
    const priceMin = parseFloat(document.getElementById("price-min").value) || 0;
    const priceMax = parseFloat(document.getElementById("price-max").value) || 10000000;
    
    // 2. Thu thập Checkbox & Select (Loại hình, Hạng sao)
    const types = Array.from(document.querySelectorAll(".type-checkbox:checked")).map(c => c.value);
    
    // Xử lý Hạng sao tối thiểu
    const starCheckboxes = Array.from(document.querySelectorAll(".star-checkbox:checked")).map(c => parseInt(c.value));
    const starsMin = starCheckboxes.length > 0 ? Math.min(...starCheckboxes) : 0;

    // Xử lý Đánh giá (Rating) & Bán kính (Radius)
    const ratingEl = document.querySelector('input[name="min_rating"]:checked');
    const ratingMin = ratingEl ? parseFloat(ratingEl.value) : 3; // Mặc định 3 sao

    const radiusEl = document.querySelector('input[name="radius"]:checked');
    const radiusKm = radiusEl ? parseFloat(radiusEl.value) : 5;  // Mặc định 5km

    const amenitiesPreferred = Array.from(document.querySelectorAll(".amenity-preferred:checked")).map(c => c.value);
    const priority = document.getElementById("priority").value;

    // 3. Tạo Payload chuẩn (Đã bỏ group_size, checkin, checkout)
    const payload = {
        city: city,
        price_min: priceMin,
        price_max: priceMax,
        types: types,
        rating_min: ratingMin,
        stars_min: starsMin,
        amenities_preferred: amenitiesPreferred,
        radius_km: radiusKm,
        priority: priority
    };

    console.log("📤 Sending Payload:", payload);

    // Hiển thị loading
    showLoading(true);
    const relaxationNote = document.getElementById("relaxation-note");
    if(relaxationNote) relaxationNote.style.display = 'none';

    // Lưu ý: Đổi URL nếu deploy lên server thật (ví dụ: https://your-app.railway.app)
    // Nếu chạy local thì giữ nguyên http://127.0.0.1:8000
    const BASE_URL = 'http://127.0.0.1:8000'; 

    fetch(`${BASE_URL}/api/recommend-hotel`,{
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    })
    .then(res => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return res.json();
    })
    .then(response => {
        console.log("✅ Backend Response:", response);
        showLoading(false);

        // Xử lý Relaxation Note
        if (response.relaxation_note) {
            const noteDiv = document.getElementById("relaxation-note");
            if (noteDiv) {
                noteDiv.innerHTML = `<strong>⚠️ Lưu ý:</strong> ${response.relaxation_note}`;
                noteDiv.style.display = 'block';
            }
        }

        // Lưu tâm bản đồ
        if (response.city_center) {
            window.search_center = {
                lon: response.city_center[0],
                lat: response.city_center[1]
            };
        }

        // XỬ LÝ DỮ LIỆU KẾT QUẢ
        let displayList = [];
        if (response.results && response.results.length > 0) {
            displayList = response.results.map(item => {
                let acc = item.accommodation ? item.accommodation : item;
                if (item.score !== undefined) {
                    acc.match_score = item.score;
                }
                return acc;
            });

            console.log("🎨 Rendering list:", displayList);
            if (typeof renderResults === 'function') {
                renderResults(displayList, city); 
            }
        } else {
            showNoResults();
        }
    })
    .catch(err => {
        console.error("❌ API Error:", err);
        showLoading(false);
        alert("Lỗi kết nối Server. Vui lòng kiểm tra lại backend.");
    });
}

// Helper: Loading UI
function showLoading(isLoading) {
    const list = document.getElementById("results-list");
    if (isLoading) {
        list.innerHTML = `
            <div style="text-align:center; padding:50px;">
                <div class="spinner" style="font-size:30px;">⏳</div>
                <p>Đang tìm kiếm & xếp hạng theo thời gian thực...</p>
                <small style="color:#666;">Hệ thống đang lấy dữ liệu mới nhất từ Google...</small>
            </div>`;
    }
}

// Helper: No Results
function showNoResults() {
    const list = document.getElementById("results-list");
    list.innerHTML = `
        <div style="text-align:center; padding:40px; background:white; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <h3>🚫 Không tìm thấy kết quả phù hợp</h3>
            <p>Vui lòng thử nới lỏng tiêu chí (giá, bán kính) hoặc chọn thành phố khác.</p>
        </div>`;
}