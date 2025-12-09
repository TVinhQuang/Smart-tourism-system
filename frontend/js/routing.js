let routingItem = null;
let map = null;      // Biến giữ đối tượng bản đồ
let marker = null;   // Biến giữ cái ghim đỏ
let routeLine = null; // Biến giữ đường vẽ màu xanh

// Tọa độ giả lập của người dùng (Ví dụ: Hà Nội)
// Trong thực tế bạn dùng navigator.geolocation để lấy
const YOUR_LAT = 21.0285;
const YOUR_LON = 105.8542;

function openRoutingModal(index) {
    if (!window.homeResults || !window.homeResults[index]) return;
    const item = window.homeResults[index];
    routingItem = item;

    // 1. Điền text thông tin (như cũ)
    document.getElementById("rt-name").innerText = item.name;
    document.getElementById("rt-address").innerText = "📍 " + item.address;
    document.getElementById("rt-price").innerText = "💵 " + Number(item.price).toLocaleString() + " VNĐ";
    document.getElementById("rt-rating").innerText = "⭐ " + item.rating;

    // 2. Hiển thị Modal trước để bản đồ tính toán được kích thước
    document.getElementById("routing-overlay").classList.remove("hidden");

    // 3. Khởi tạo bản đồ Leaflet (Nếu chưa có)
    if (!map) {
        // Tạo map tại div id="rt-map-frame"
        map = L.map('rt-map-frame').setView([item.lat, item.lon], 15);
        
        // Thêm lớp nền OpenStreetMap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
    } else {
        // Nếu map đã có rồi thì chỉ cần bay đến vị trí mới
        map.setView([item.lat, item.lon], 15);
        
        // Fix lỗi hiển thị map bị xám khi ẩn/hiện modal
        setTimeout(() => { map.invalidateSize(); }, 200);
    }

    // 4. Thêm Marker (Ghim đỏ) tại vị trí khách sạn
    if (marker) map.removeLayer(marker); // Xóa marker cũ
    if (routeLine) map.removeLayer(routeLine); // Xóa đường vẽ cũ

    marker = L.marker([item.lat, item.lon]).addTo(map)
        .bindPopup(`<b>${item.name}</b>`).openPopup();
}

// === PHẦN TÍCH HỢP API CHỈ ĐƯỜNG CỦA BẠN ===
document.getElementById("rt-show-route").addEventListener("click", () => {
    const mode = document.getElementById("rt-transport").value;
    const btn = document.getElementById("rt-show-route");
    btn.innerText = "⏳ Đang tính toán...";
    btn.disabled = true;

    fetch("http://localhost:5000/api/route", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            src: { lat: YOUR_LAT, lon: YOUR_LON },
            dst: { lat: routingItem.lat, lon: routingItem.lon },
            profile: mode
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            // 1. Vẽ đường đi lên Map
            if (routeLine) map.removeLayer(routeLine);
            routeLine = L.polyline(data.path, {color: 'blue', weight: 6, opacity: 0.7}).addTo(map);
            map.fitBounds(routeLine.getBounds(), {padding: [50, 50]});

            // 2. Hiển thị thông tin phân tích (Alert hoặc chèn vào HTML)
            const info = data.info;
            let msg = `✅ Đã tìm thấy đường!\n\n`;
            msg += `📏 Khoảng cách: ${info.distance_text}\n`;
            msg += `⏱ Thời gian: ${info.duration_text}\n`;
            msg += `📊 Độ khó: ${info.complexity}\n`;
            msg += `💡 Gợi ý: ${info.recommendation}\n`;
            
            // Nếu bạn muốn hiện hướng dẫn chi tiết bước đầu tiên
            if (data.instructions.length > 0) {
                msg += `\n🚀 Bước đầu: ${data.instructions[0]}`;
            }

            alert(msg);
            
            // (Nâng cao) Bạn có thể render danh sách instructions vào một div trong modal thay vì alert
        } else {
            alert("Không tìm thấy đường đi!");
        }
    })
    .catch(err => {
        console.error(err);
        alert("Lỗi kết nối Server!");
    })
    .finally(() => {
        btn.innerText = "🗺️ Chỉ đường";
        btn.disabled = false;
    });
});