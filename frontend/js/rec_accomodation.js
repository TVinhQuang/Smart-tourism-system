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
    });
}
