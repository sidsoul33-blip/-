import streamlit as st
import yfinance as yf
from fredapi import Fred
import requests
import pandas as pd

# =========================
# 🔑 1. 설정 및 API 키 (st.secrets 사용)
# =========================
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]
FRED_API_KEY = st.secrets["FRED_API_KEY"]

# 위험 판단 기준치
THRESHOLDS = {
    "us10y": 4.5,
    "hy_spread": 6.0,
    "dxy": 110,
    "usdkrw": 1450,
    "jpykrw": 1000,
    "vix": 24,
    "oil": 100
}

fred = Fred(api_key=FRED_API_KEY)

# =========================
# 📨 2. 기능 함수 정의
# =========================

def send_telegram_msg(text):
    """버튼 클릭 시 실행될 텔레그램 발송 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            st.toast("✅ 텔레그램 메시지 전송 성공!")
        else:
            st.error("❌ 발송 실패: 봇 토큰이나 ID를 확인하세요.")
    except Exception as e:
        st.error(f"⚠️ 연결 오류: {e}")

@st.cache_data(ttl=300)
def get_data():
    """데이터 수집 및 변화 속도 계산"""
    # FRED 데이터 (최근 5일치 가져와서 마지막 2일 비교)
    us10y_series = fred.get_series('DGS10').dropna()
    hy_series = fred.get_series('BAMLH0A0HYM2').dropna()
    
    us10y = us10y_series.iloc[-1]
    us10y_prev = us10y_series.iloc[-2]
    hy_spread = hy_series.iloc[-1]
    hy_prev = hy_series.iloc[-2]
    
    # 변화 속도 계산 (현재값 - 전일값)
    us10y_diff = us10y - us10y_prev
    hy_diff = hy_spread - hy_prev
    
    # Yahoo Finance 데이터
    dxy = yf.Ticker("DX-Y.NYB").history(period="1d")['Close'].iloc[-1]
    usdkrw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
    jpyusd = yf.Ticker("JPY=X").history(period="1d")['Close'].iloc[-1]
    jpykrw = (1 / jpyusd) * usdkrw
    vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    oil = yf.Ticker("CL=F").history(period="1d")['Close'].iloc[-1]
    
    # S&P500 추세 (200일선)
    sp500 = yf.Ticker("^GSPC").history(period="1y")
    sp_now = sp500['Close'].iloc[-1]
    sp_ma200 = sp500['Close'].rolling(200).mean().iloc[-1]

    return {
        "us10y": us10y, "us10y_diff": us10y_diff,
        "hy_spread": hy_spread, "hy_diff": hy_diff,
        "dxy": dxy, "usdkrw": usdkrw, "jpykrw": jpykrw,
        "vix": vix, "oil": oil, "sp_now": sp_now, "sp_ma200": sp_ma200
    }

def analyze(data):
    """위험 신호 개수 파악"""
    risk = 0
    details = {}
    for key in THRESHOLDS:
        if data[key] > THRESHOLDS[key]:
            risk += 1
            details[key] = "위험"
        else:
            details[key] = "정상"
    
    trend = "하락추세" if data["sp_now"] < data["sp_ma200"] else "상승추세"
    if trend == "하락추세": risk += 1
    
    return risk, details, trend

def action_signal(risk, vix, trend):
    """최종 행동 가이드"""
    if risk <= 2: return "🟢 매수 유지 / 분할 매수"
    elif risk <= 4: return "🟡 관망 및 비중 축소 준비"
    else: return "🔴 현금 확보 및 방어 포지션"

# =========================
# 🎨 3. 화면 구성 (UI)
# =========================
st.set_page_config(layout="wide", page_title="Market Guardian")
st.title("📊 시장 지표 및 위험 감지 시스템")

# 데이터 로드
try:
    data = get_data()
    risk, details, trend = analyze(data)
    signal = action_signal(risk, data["
