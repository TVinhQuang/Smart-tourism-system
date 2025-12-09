// display_results.js

function renderResults(results, note) {
    const container = document.getElementById("results-list");
    if (!container) return;
    container.innerHTML = "";

    if (note) {
        console.log("Note:", note);
    }

    if (!results || results.length === 0) {
        container.innerHTML = "<p>Không tìm thấy kết quả phù hợp.</p>";
        document.getElementById("results-container").style.display = "block";
        return;
    }

    results.forEach(item => {
        const distance = item.distance_km ?? item.distance ?? '—';
        const rating = (typeof item.rating === 'number') ? item.rating.toFixed(1) : item.rating;

        const div = document.createElement("div");
        div.className = "result-item";
        div.innerHTML = `
            <h3>${item.name}</h3>
            <p>Giá: ${Number(item.price).toLocaleString()} VNĐ</p>
            <p>Rating: ${rating}</p>
            <p>Khoảng cách: ${distance} km</p>
            <p>Tiện ích: ${Array.isArray(item.amenities) ? item.amenities.join(", ") : (item.amenities || '')}</p>
            <p>Địa chỉ: ${item.address || ''}</p>
        `;
        container.appendChild(div);
    });

    document.getElementById("results-container").style.display = "block";
}

function viewMap(dstLat, dstLon, dstName) {

    // Giả sử user đứng tại city center, backend đã trả về center
    const src = window.search_center; 

    if (!src) {
        alert("Chưa có vị trí xuất phát!");
        return;
    }

    const payload = {
        src: { lat: src.lat, lon: src.lon, name: "Điểm xuất phát" },
        dst: { lat: dstLat, lon: dstLon, name: dstName }
    };

    fetch("http://127.0.0.1:5000/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.map_url) {
            window.open("http://127.0.0.1:5000" + data.map_url, "_blank");
        } else {
            alert("Không vẽ được bản đồ!");
        }
    })
    .catch(err => {
        console.error("Route error:", err);
        alert("Không lấy được dữ liệu tuyến đường!");
    });
}
