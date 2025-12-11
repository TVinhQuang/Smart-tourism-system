function submitSearch() {
    const data = {
        city: document.getElementById("city").value,
        group_size: parseInt(document.getElementById("group-size").value),
        price_min: parseFloat(document.getElementById("price-min").value),
        price_max: parseFloat(document.getElementById("price-max").value),
        types: Array.from(document.querySelectorAll(".type-checkbox:checked")).map(c => c.value),
        rating_min: parseFloat(document.getElementById("min-rating").value),
        amenities_required: Array.from(document.querySelectorAll(".amenity-required:checked")).map(c => c.value),
        amenities_preferred: Array.from(document.querySelectorAll(".amenity-preferred:checked")).map(c => c.value),
        radius_km: parseFloat(document.getElementById("radius").value),
        priority: document.getElementById("priority").value
    };

    fetch("http://localhost:5000/api/recommend", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(response => {
        renderResults(response.results, response.relaxation_note);
    })
    .catch(err => {
        console.error("Error:", err);
    })
    .then(response => {
    console.log("Backend:", response);

    // LƯU CENTER CHO ROUTING
    window.search_center = response.center;

    renderResults(response.results, response.relaxation_note);
    });
 
<<<<<<< HEAD
}

async function findRoute() {
    try {
        const body = {
            start: document.getElementById("inputStart").value,
            end: document.getElementById("inputEnd").value,
            mode: selectedMode
        };

        const res = await fetch("http://localhost:5000/api/route", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(body)
        });

        const data = await res.json();

        renderRouteUI(data);
    } catch {
        alert("Lỗi kết nối Server!");
    }
}

function renderRouteUI(data) {
    document.getElementById("routeBox").style.display = "block";

    document.getElementById("routeMap").src = data.mapUrl;
    document.getElementById("kmText").textContent = data.distance;
    document.getElementById("timeText").textContent = data.time;

    const mainList = document.getElementById("mainStepsList");
    const detailList = document.getElementById("detailStepsList");

    mainList.innerHTML = "";
    detailList.innerHTML = "";

    data.mainSteps.forEach(step => {
        mainList.innerHTML += `<li>${step}</li>`;
    });

    data.detailSteps.forEach(step => {
        detailList.innerHTML += `<li>${step}</li>`;
    });
}

function toggleDetailSteps() {
    const box = document.getElementById("detailStepsList");
    const btn = document.getElementById("toggleDetailBtn");

    if (box.style.display === "none") {
        box.style.display = "block";
        btn.textContent = "- Ẩn đường đi cụ thể";
    } else {
        box.style.display = "none";
        btn.textContent = "+ Đường đi cụ thể";
    }
=======
>>>>>>> f0c156c360d21604ab314e098d0e4754e6450580
}

async function findRoute() {
    try {
        const body = {
            start: document.getElementById("inputStart").value,
            end: document.getElementById("inputEnd").value,
            mode: selectedMode
        };

        const res = await fetch("http://localhost:5000/api/route", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(body)
        });

        const data = await res.json();

        renderRouteUI(data);
    } catch {
        alert("Lỗi kết nối Server!");
    }
}

function renderRouteUI(data) {
    document.getElementById("routeBox").style.display = "block";

    document.getElementById("routeMap").src = data.mapUrl;
    document.getElementById("kmText").textContent = data.distance;
    document.getElementById("timeText").textContent = data.time;

    const mainList = document.getElementById("mainStepsList");
    const detailList = document.getElementById("detailStepsList");

    mainList.innerHTML = "";
    detailList.innerHTML = "";

    data.mainSteps.forEach(step => {
        mainList.innerHTML += `<li>${step}</li>`;
    });

    data.detailSteps.forEach(step => {
        detailList.innerHTML += `<li>${step}</li>`;
    });
}

function toggleDetailSteps() {
    const box = document.getElementById("detailStepsList");
    const btn = document.getElementById("toggleDetailBtn");

    if (box.style.display === "none") {
        box.style.display = "block";
        btn.textContent = "- Ẩn đường đi cụ thể";
    } else {
        box.style.display = "none";
        btn.textContent = "+ Đường đi cụ thể";
    }
}