import express from "express";
import cors from "cors";

const app = express();
app.use(cors());
app.use(express.json());

// API nhận vị trí + khách sạn → trả route
app.post("/api/route", async (req, res) => {
    try {
        const { start, end, mode } = req.body;

        // ---- GIẢ LẬP GIỐNG GOOGLE MAPS ----
        return res.json({
            distance: "4.37 km",
            time: "6 phút",
            mapUrl: "https://www.openstreetmap.org/",

            mainSteps: [
                "Đi thẳng 500m",
                "Rẽ trái vào đường chính",
                "Đi 2km qua cầu",
                "Rẽ phải đến trung tâm",
                "Đi thêm 200m đến nơi"
            ],

            detailSteps: [
                "Đi 190m rồi rẽ phải",
                "Đi 289m rồi rẽ trái",
                "Đi 662m rồi rẽ trái",
                "Đi thêm 1.6km"
            ]
        });

    } catch (err) {
        res.status(500).json({ error: "Route API Error" });
    }
});

app.listen(5000, () => console.log("🚀 Backend chạy tại http://localhost:5000"));
