// display_results.js

function renderResults(results, note) {
    const container = document.getElementById("results-list");
    if (!container) return;
    container.innerHTML = "";

    if (note) console.log("Note:", note);

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
            <button class="view-map-btn"
                data-lat="${item.latitude}"
                data-lng="${item.longitude}">
                🗺 Xem bản đồ
            </button>
        `;
        container.appendChild(div);
    });

    document.getElementById("results-container").style.display = "block";
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

    fetch("http://localhost:5000/api/route", {
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
