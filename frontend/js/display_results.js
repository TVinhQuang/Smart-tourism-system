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
