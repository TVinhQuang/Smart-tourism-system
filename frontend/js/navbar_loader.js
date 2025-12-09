fetch("../components/navbar.html")
    .then(res => res.text())
    .then(html => {
        document.getElementById("navbar-root").innerHTML = html;
    })
    .catch(() => console.warn("Không load được navbar"));

function changeLanguage(lang) {
    localStorage.setItem("lang", lang);
    location.reload();  // load lại trang để dùng language mới
}
