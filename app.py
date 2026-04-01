from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import joblib, os, json

app = Flask(__name__)

# ── Thresholds ──
THRESHOLDS = {
    'Da Nang': {'warning': 33000, 'critical': 50000},
    'Hoi An':  {'warning': 14000, 'critical': 20000},
    'Hue':     {'warning': 12000, 'critical': 18000},
}
CITY_LABELS = {'Da Nang': 'Đà Nẵng', 'Hoi An': 'Hội An', 'Hue': 'Huế'}
COORDS = {
    'Da Nang': (16.0544, 108.2022),
    'Hoi An':  (15.8801, 108.3380),
    'Hue':     (16.4637, 107.5909),
}

# ── Seasonality data (từ B3 model) ──
# TB khách/ngày theo tháng × thành phố
MONTHLY_AVG = {
    'Da Nang': [18000,20000,22000,26000,27000,33000,43000,39000,31000,24000,24000,27000],
    'Hoi An':  [9000, 11000,13000,14000,14000,13000,15000,15000,12000,10000, 7000, 5000],
    'Hue':     [8000, 9000, 10000,12000,11000,11000,11000,12000,12000,11000,12000,13000],
}
BEST_MONTHS = {
    'Da Nang': {'best': [3,4,5], 'avoid': [7,8]},
    'Hoi An':  {'best': [2,3,4], 'avoid': [10,11]},
    'Hue':     {'best': [1,2,3], 'avoid': [9,10]},
}
MONTH_NAMES = ['','Tháng 1','Tháng 2','Tháng 3','Tháng 4','Tháng 5','Tháng 6',
               'Tháng 7','Tháng 8','Tháng 9','Tháng 10','Tháng 11','Tháng 12']

def get_weather(lat, lon):
    """Lấy thời tiết hôm nay từ Open-Meteo (free, no key)"""
    try:
        url = 'https://api.open-meteo.com/v1/forecast'
        params = {
            'latitude': lat, 'longitude': lon,
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max',
            'timezone': 'Asia/Bangkok', 'forecast_days': 3
        }
        r = requests.get(url, params=params, timeout=5).json()['daily']
        result = []
        for i in range(3):
            tmax = r['temperature_2m_max'][i]
            tmin = r['temperature_2m_min'][i]
            rain = r['precipitation_sum'][i] or 0
            wind = r['windspeed_10m_max'][i] or 0
            t_score = 1.0 if 24<=tmax<=30 else (0.8 if tmax<24 else 0.6)
            r_score = 1.0 if rain<=5 else (0.7 if rain<=20 else 0.3)
            w_score = round(t_score*0.5 + r_score*0.5, 3)
            result.append({'tmax':tmax,'tmin':tmin,'rain':rain,'wind':wind,'score':w_score})
        return result
    except:
        return [{'tmax':30,'tmin':24,'rain':5,'wind':15,'score':0.8}]*3

def predict_level(city, month, is_weekend, is_holiday, w_score):
    """Dự báo mức độ đông dựa trên rule + seasonality"""
    base = MONTHLY_AVG[city][month-1]
    mult = 1.0
    if is_weekend: mult *= 1.35
    if is_holiday: mult *= 2.2
    mult *= (0.4 + 0.6 * w_score)
    est = int(base * mult)
    t = THRESHOLDS[city]
    if est >= t['critical']:   level = 'critical'
    elif est >= t['warning']:  level = 'warning'
    else:                      level = 'normal'
    return est, level

def get_suggestion(city, month):
    """Gợi ý thời điểm tốt nhất"""
    bm = BEST_MONTHS[city]
    avoid = bm['avoid']
    best  = bm['best']
    if month in avoid:
        alt = [MONTH_NAMES[m] for m in best]
        return f"⚠️ {MONTH_NAMES[month]} thường đông và dễ quá tải. Nên đi vào: {', '.join(alt)}"
    elif month in best:
        return f"✅ {MONTH_NAMES[month]} là thời điểm lý tưởng — ít đông, thời tiết đẹp!"
    else:
        return f"🟡 {MONTH_NAMES[month]} ở mức trung bình — không quá đông, không quá vắng."

# ════════════════════════════
# ROUTES
# ════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/today')
def api_today():
    """Real-time: thời tiết + dự báo hôm nay cho 3 thành phố"""
    today = datetime.now()
    result = {}
    holidays = ['01-01','04-30','05-01','09-02']
    is_hol = today.strftime('%m-%d') in holidays

    for city, (lat, lon) in COORDS.items():
        wx = get_weather(lat, lon)
        w = wx[0]
        est, level = predict_level(
            city, today.month,
            today.weekday() >= 5, is_hol, w['score']
        )
        t = THRESHOLDS[city]
        pct = min(round(est / t['critical'] * 100), 120)
        result[city] = {
            'label':      CITY_LABELS[city],
            'est':        est,
            'level':      level,
            'pct':        pct,
            'tmax':       w['tmax'],
            'tmin':       w['tmin'],
            'rain':       w['rain'],
            'w_score':    w['score'],
            'threshold':  t,
            'is_weekend': today.weekday() >= 5,
            'is_holiday': is_hol,
            'forecast':   wx,  # 3 ngày tới
        }
    return jsonify({
        'updated': today.strftime('%d/%m/%Y %H:%M'),
        'cities': result
    })

@app.route('/api/suggest', methods=['POST'])
def api_suggest():
    """Gợi ý cho khách: chọn thành phố + tháng → dự báo + lời khuyên"""
    data = request.json
    city   = data.get('city', 'Da Nang')
    month  = int(data.get('month', datetime.now().month))
    is_we  = data.get('is_weekend', False)
    is_hol = data.get('is_holiday', False)

    # Thời tiết dự báo (lấy proxy từ lịch sử)
    lat, lon = COORDS[city]
    wx = get_weather(lat, lon)
    w_score = wx[0]['score']

    est, level = predict_level(city, month, is_we, is_hol, w_score)
    suggestion = get_suggestion(city, month)

    # So sánh cả năm
    monthly_data = []
    for m in range(1, 13):
        v, lv = predict_level(city, m, False, False, 0.8)
        monthly_data.append({'month': m, 'name': MONTH_NAMES[m], 'est': v, 'level': lv})

    return jsonify({
        'city':        city,
        'label':       CITY_LABELS[city],
        'month':       month,
        'month_name':  MONTH_NAMES[month],
        'est':         est,
        'level':       level,
        'suggestion':  suggestion,
        'monthly':     monthly_data,
        'best_months': BEST_MONTHS[city],
        'threshold':   THRESHOLDS[city],
    })

@app.route('/api/compare', methods=['POST'])
def api_compare():
    """So sánh 3 thành phố cùng thời điểm"""
    data  = request.json
    month = int(data.get('month', datetime.now().month))
    is_we = data.get('is_weekend', False)

    result = []
    for city in ['Da Nang', 'Hoi An', 'Hue']:
        v, lv = predict_level(city, month, is_we, False, 0.8)
        t = THRESHOLDS[city]
        result.append({
            'city':  city,
            'label': CITY_LABELS[city],
            'est':   v, 'level': lv,
            'pct':   min(round(v/t['critical']*100), 110),
        })
    # Sort: ít đông nhất trước → gợi ý phân luồng
    result.sort(key=lambda x: x['est'])
    return jsonify({
        'month':      month,
        'month_name': MONTH_NAMES[month],
        'cities':     result,
        'recommend':  result[0]['label'],  # ít đông nhất
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
