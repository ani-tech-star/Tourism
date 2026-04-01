# Du lịch Miền Trung — Web App

Hệ thống dự báo mức độ đông đúc và gợi ý thời điểm du lịch cho Đà Nẵng, Hội An, Huế.

## Tính năng
- **Trang gợi ý** (`/`): Khách nhập thành phố + tháng → nhận dự báo + lời khuyên
- **Dashboard** (`/dashboard`): Cảnh báo real-time cho ban quản lý
- **API real-time**: Gọi Open-Meteo lấy thời tiết hôm nay tự động
- **So sánh 3 thành phố**: Gợi ý nơi ít đông nhất

## Deploy lên Render (miễn phí)

### Bước 1 — Tạo GitHub repo
1. Vào github.com → New repository → đặt tên `tourism-app`
2. Upload toàn bộ file trong folder này lên

### Bước 2 — Deploy trên Render
1. Vào render.com → đăng ký miễn phí
2. New → Web Service → Connect GitHub repo
3. Điền:
   - **Name**: tourism-mientrung
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. Click Deploy → đợi 2-3 phút → có URL dạng `https://tourism-mientrung.onrender.com`

## Chạy local (test trước)
```bash
pip install -r requirements.txt
python app.py
# Mở http://localhost:5000
```

## Stack
- **Backend**: Flask (Python)
- **Frontend**: HTML/CSS/JavaScript thuần (Chart.js)
- **Data**: Open-Meteo API (thời tiết real-time)
- **Model**: Rule-based + seasonality từ Random Forest B6
- **Deploy**: Render.com (free tier)
