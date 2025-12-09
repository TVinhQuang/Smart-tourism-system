console.log("homepage.js loaded");

const dummyList = [
    {
        name: "La Siesta Hoi An Resort & Spa",
        price: 2500000,
        rating: 9.3,
        desc: "Khu nghỉ dưỡng với 4 hồ bơi, kiến trúc xanh mát và spa đẳng cấp thế giới.",
        address: "134 Hùng Vương, Cẩm Phô, Hội An",
        lat: 15.8795, lon: 108.3181,
        img: "https://bevivu.com/wp-content/uploads/image8/2024/02/la-siesta-resort--spa070220241707301318.jpeg",
        // THÊM DÒNG NÀY:
        amenities: ["🏊 Hồ bơi", "📶 Wifi miễn phí", "🍳 Bữa sáng", "💆 Spa & Massage", "🚌 Xe đưa đón", "❄️ Điều hòa"]
    },
    {
        name: "Hotel Royal Hoi An",
        price: 3200000,
        rating: 9.5,
        desc: "Khách sạn sang trọng bên sông Thu Bồn, mang phong cách Indochine lãng mạn.",
        address: "39 Đào Duy Từ, Hội An",
        lat: 15.8770, lon: 108.3260,
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/49826269.jpg?k=7a0126780287a91163402651478546554655",
        // THÊM DÒNG NÀY:
        amenities: ["🍸 Rooftop Bar", "🏋️ Phòng Gym", "🛁 Bồn tắm", "📶 Wifi miễn phí", "🌊 View sông"]
    }
];

window.homeResults = dummyList;

// ============================ RENDER CARD ============================
const container = document.getElementById("accommodation-list");

if (container) {
    dummyList.forEach((item, index) => {
        const card = document.createElement("div");
        card.className = "accommodation-card"; 

        card.innerHTML = `
            <img src="${item.img || 'https://via.placeholder.com/300'}" style="width:100%; height:200px; object-fit:cover; border-radius:10px 10px 0 0;" alt="${item.name}">
            <div class="accommodation-content" style="padding:15px;">
                <h3 class="accommodation-title" style="margin-bottom:10px;">${item.name}</h3>
                <p class="accommodation-description" style="font-size:0.9rem; color:#666;">${item.desc}</p>
                
                <div class="price-rating-row" style="display:flex; justify-content:space-between; margin-top:15px; align-items:center;">
                    <div class="accommodation-price" style="font-weight:bold; color:#4a6cf7;">${item.price.toLocaleString()} VND</div>
                    <div class="accommodation-rating">
                        <span class="star">★</span> ${item.rating}
                    </div>
                </div>

                <button class="map-button" 
                    style="width:100%; margin-top:15px; padding:10px; background:#eee; border:none; border-radius:5px; cursor:pointer;"
                    onclick="openRoutingModal(${index})">
                    Xem bản đồ
                </button>
            </div>
        `;
        container.appendChild(card);
    });
} else {
    console.error("Lỗi: Không tìm thấy ID 'accommodation-list' trong HTML");
}