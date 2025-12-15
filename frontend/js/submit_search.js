// ================================================================
// SUBMIT SEARCH - Đã sửa lỗi Mapping dữ liệu Backend
// ================================================================

function submitSearch() {
    // 1. Thu thập dữ liệu Cơ bản
    const city = document.getElementById("city").value;
    const priceMin = parseFloat(document.getElementById("price-min").value) || 0;
    const priceMax = parseFloat(document.getElementById("price-max").value) || 10000000;
    
    // 2. Thu thập Checkbox & Select
    const types = Array.from(document.querySelectorAll(".type-checkbox:checked")).map(c => c.value);
    
    const starCheckboxes = Array.from(document.querySelectorAll(".star-checkbox:checked")).map(c => parseInt(c.value));
    const starsMin = starCheckboxes.length > 0 ? Math.min(...starCheckboxes) : 0;

    const ratingEl = document.querySelector('input[name="min_rating"]:checked');
    const ratingMin = ratingEl ? parseFloat(ratingEl.value) : 3;

    const radiusEl = document.querySelector('input[name="radius"]:checked');
    const radiusKm = radiusEl ? parseFloat(radiusEl.value) : 5;

    const amenitiesPreferred = Array.from(document.querySelectorAll(".amenity-preferred:checked")).map(c => c.value);
    const priority = document.getElementById("priority")?.value || "price";

    // 3. Tạo Payload chuẩn
    const payload = {
        city: city,
        price_min: priceMin,
        price_max: priceMax,
        types: types,
        rating_min: ratingMin,
        radius_km: radiusKm,
        amenities_preferred: amenitiesPreferred,
        stars_min: starsMin,
        priority: priority
    };

    console.log("📤 Sending Payload:", payload);

    // Hiển thị loading
    showLoading(true);
    const relaxationNote = document.getElementById("relaxation-note");
    if(relaxationNote) relaxationNote.style.display = 'none';

    const BASE_URL = 'http://127.0.0.1:8000'; 

    fetch(`${BASE_URL}/api/recommend-hotel`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    })
    .then(res => {
        console.log("📡 Response status:", res.status);
        console.log("📡 Response headers:", res.headers);
        
        // ✅ IMPROVED: Log raw response text before parsing
        return res.text().then(text => {
            console.log("📄 Raw response:", text);
            
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}: ${text}`);
            }
            
            // Try to parse JSON
            try {
                return JSON.parse(text);
            } catch (e) {
                console.error("❌ JSON Parse Error:", e);
                throw new Error(`Invalid JSON response: ${text.substring(0, 100)}`);
            }
        });
    })
    .then(response => {
        console.log("✅ Backend Response:", response);
        showLoading(false);

        // Xử lý note
        const noteText = response.note || response.relaxation_note;
        
        if (noteText) {
            const noteDiv = document.getElementById("relaxation-note");
            if (noteDiv) {
                noteDiv.innerHTML = `<strong>⚠️ Lưu ý:</strong> ${noteText}`;
                noteDiv.style.display = 'block';
            }
        }

        // Xử lý center location
        if (response.center) {
            window.search_center = {
                lon: response.center.lon,
                lat: response.center.lat
            };
        } else if (response.city_center) {
            window.search_center = {
                lon: response.city_center[0],
                lat: response.city_center[1]
            };
        }

        // XỬ LÝ KẾT QUẢ
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
                renderResults(displayList, noteText); 
            } else {
                console.error("❌ renderResults function not found!");
                showSimpleResults(displayList);
            }
        } else {
            console.warn("⚠️ No results found");
            showNoResults();
        }
    })
    .catch(err => {
        console.error("❌ API Error:", err);
        console.error("❌ Error stack:", err.stack);
        showLoading(false);
        
        // ✅ IMPROVED: Better error message
        let errorMsg = "Lỗi kết nối với server.";
        
        if (err.message.includes("Failed to fetch")) {
            errorMsg = "Không thể kết nối đến server. Hãy kiểm tra:\n" +
                      "1. Server đã chạy tại http://127.0.0.1:8000?\n" +
                      "2. CORS đã được cấu hình đúng?\n" +
                      "3. Firewall/Antivirus có chặn không?";
        } else if (err.message.includes("JSON")) {
            errorMsg = `Server trả về dữ liệu không hợp lệ:\n${err.message}`;
        } else {
            errorMsg = `Lỗi: ${err.message}`;
        }
        
        alert(errorMsg);
    });
}

function showLoading(isLoading) {
    const list = document.getElementById("results-list");
    if (!list) return;
    if (isLoading) {
        list.innerHTML = `
            <div style="text-align:center; padding:50px;">
                <div class="spinner" style="font-size:30px;">⏳</div>
                <p>Đang tìm kiếm & xếp hạng...</p>
            </div>`;
    }
}

function showNoResults() {
    const list = document.getElementById("results-list");
    if (!list) return;
    list.innerHTML = `
        <div style="text-align:center; padding:40px; background:white; border-radius:8px; margin:20px;">
            <h3>🚫 Không tìm thấy kết quả</h3>
            <p>Hãy thử:</p>
            <ul style="text-align:left; display:inline-block;">
                <li>Tìm thành phố lớn: Hồ Chí Minh, Hà Nội, Đà Nẵng</li>
                <li>Mở rộng khoảng giá</li>
                <li>Giảm yêu cầu về rating</li>
            </ul>
        </div>`;
}

// ✅ Fallback rendering if renderResults not available
function showSimpleResults(results) {
    const list = document.getElementById("results-list");
    if (!list) return;
    
    list.innerHTML = results.map(hotel => `
        <div style="border:1px solid #ddd; padding:15px; margin:10px; border-radius:8px; background:white;">
            <h3>${hotel.name}</h3>
            <p>📍 ${hotel.address}</p>
            <p>💰 Giá: ${hotel.price.toLocaleString()} VNĐ</p>
            <p>⭐ Rating: ${hotel.rating} (${hotel.reviews} reviews)</p>
            <p>🏷️ Type: ${hotel.type}</p>
        </div>
    `).join('');
}