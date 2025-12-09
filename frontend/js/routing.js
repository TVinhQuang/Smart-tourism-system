let routingItem = null;

// Tọa độ giả lập của người dùng (Ví dụ: Hà Nội)
// Sau này bạn có thể dùng navigator.geolocation.getCurrentPosition để lấy thật
const YOUR_LAT = 21.0285;
const YOUR_LON = 105.8542;

function openRoutingModal(index) {
    // Lấy data từ biến toàn cục đã gán ở homepage.js
    if (!window.homeResults || !window.homeResults[index]) {
        console.error("Không tìm thấy dữ liệu tại index:", index);
        return;
    }

    const item = window.homeResults[index];
    routingItem = item;

    // Gán thông tin text
    document.getElementById("rt-name").innerText = item.name;
    document.getElementById("rt-address").innerText = "📍 " + item.address;
    document.getElementById("rt-price").innerText = "💵 Giá: " + Number(item.price).toLocaleString() + " VNĐ";
    document.getElementById("rt-rating").innerText = "⭐ Rating: " + item.rating;

    // Hiển thị Map
    // Lưu ý: Google Maps Embed cần API Key mới chạy được, nếu không sẽ lỗi.
    // Tôi đổi tạm sang OpenStreetMap để bạn test được ngay giao diện.
    const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${item.lon-0.01},${item.lat-0.01},${item.lon+0.01},${item.lat+0.01}&layer=mapnik&marker=${item.lat},${item.lon}`;
    
    document.getElementById("rt-map-frame").src = mapUrl;

    // Hiển thị modal
    document.getElementById("routing-overlay").classList.remove("hidden");
}

// Xử lý nút Đóng
document.addEventListener("click", e => {
    if (e.target.id === "rt-close" || e.target.id === "routing-overlay") {
        document.getElementById("routing-overlay").classList.add("hidden");
        document.getElementById("rt-map-frame").src = ""; // Dừng load map
    }
});

// Nút hiển thị routing
const btnRoute = document.getElementById("rt-show-route");
if (btnRoute) {
    btnRoute.addEventListener("click", () => {
        const mode = document.getElementById("rt-transport").value;

        // Code backend cũ của bạn giữ nguyên
        fetch("http://localhost:5000/api/route", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                src: {lat: YOUR_LAT, lon: YOUR_LON}, 
                dst: {lat: routingItem.lat, lon: routingItem.lon},
                profile: mode
            })
        })
        .then(r => r.json())
        .then(data => {
            console.log(data);
            alert("Đã gửi request tới Backend OSRM! (Kiểm tra Console)");
        })
        .catch(err => {
            alert("Lỗi kết nối Backend (Chắc chưa chạy server Python?)");
            console.error(err);
        });
    });
}