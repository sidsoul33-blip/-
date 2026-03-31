import streamlit as st
import yfinance as yf
from fredapi import Fred
import requests
import pandas as pd

# =========================
# 🔑 1. 설정 및 API 키
# =========================
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]
FRED_API_KEY = st.secrets["FRED_API_KEY"]

# 위험 판단 기준치 (쉼표 및 괄호 완벽 검수)
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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            st.toast("✅ 텔레그램 발송 성공!")
    except Exception as e:
        st.error(f"⚠️ 발송 오류: {e}")

@st.cache_data(ttl=300)
def get_data():
    # 1. FRED 데이터 (금리 및 스프레드 속도 계산)
    us10y_series = fred.get_series('DGS10').dropna()
    hy_series = fred.get_series('BAMLH0A0HYM2').dropna()
    
    us10y = us10y_series.iloc[-1]
    us10y_diff = us10y - us10y_series.iloc[-2]
    hy_spread = hy_series.iloc[-1]
    hy_diff = hy_spread - hy_series.iloc[-2]
    
    # 2. S&P 500 데이터 (현재가 및 200일선)
    sp500 = yf.Ticker("^GSPC").history(period="1y")
    sp_now = sp500['Close'].iloc[-1]
    sp_prev = sp500['Close'].iloc[-2]
    sp_diff = sp_now - sp_prev
    sp_ma200 = sp500['Close'].rolling(200).mean().iloc[-1]
    
    # 3. 기타 지표
    dxy = yf.Ticker("DX-Y.NYB").history(period="1d")['Close'].iloc[-1]
    usdkrw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
    jpyusd = yf.Ticker("JPY=X").history(period="1d")['Close'].iloc[-1]
    jpykrw = (1 / jpyusd) * usdkrw
    vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    oil = yf.Ticker("CL=F").history(period="1d")['Close'].iloc[-1]

    return {
        "us10y": us10y, "us10y_diff": us10y_diff,
        "hy_spread": hy_spread, "hy_diff": hy_diff,
        "sp_now": sp_now, "sp_diff": sp_diff, "sp_ma200": sp_ma200,
        "dxy": dxy, "usdkrw": usdkrw, "jpykrw": jpykrw,
        "vix": vix, "oil": oil
    }

def analyze(data):
    risk = 0
    details = {}
    for key in THRESHOLDS:
        if data[key] > THRESHOLDS[key]:
            risk += 1
            details[key] = "위험"
        else:
            details[key] = "정상"
    
    # S&P 500 추세 판단 로직
    trend = "하락추세" if data["sp_now"] < data["sp_ma200"] else "상승추세"
    if trend == "하락추세": risk += 1
    
    return risk, details, trend

def action_signal(risk, vix, trend):
    if risk <= 2: return "🟢 매수 유지 / 분할 매수"
    elif risk <= 4: return "🟡 관망 및 비중 축소 준비"
    else: return "🔴 현금 확보 및 방어 포지션"

# =========================
# 🎨 3. 화면 구성 (UI)
# =========================
st.set_page_config(layout="wide", page_title="Market Guardian")
st.title("📊 시장 지표 및 위험 감지 시스템")

try:
    data = get_data()
    risk, details, trend = analyze(data)
    signal = action_signal(risk, data["vix"], trend)

    # --- [섹션 1] 가장 신뢰하는 핵심 지표 (3개 배치) ---
    st.subheader("🔥 핵심 모니터링: 변동 속도")
    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.metric(label="🇺🇸 미국채 10년물 금리", value=f"{data['us10y']:.2f}%", 
                  delta=f"{data['us10y_diff']:+.3f}", delta_color="inverse")
    with m2:
        st.metric(label="📉 하이일드 스프레드", value=f"{data['hy_spread']:.2f}%", 
                  delta=f"{data['hy_diff']:+.3f}", delta_color="inverse")
    with m3:
        # S&P 500 지수 현황 추가
        st.metric(label="📈 S&P 500 지수", value=f"{data['sp_now']:,.2f}", 
                  delta=f"{data['sp_diff']:+.2f}", delta_color="normal")

    st.divider()

    # --- [섹션 2] 상태 요약 및 발송 버튼 ---
    c1, c2 = st.columns([3, 1])
    with c1:
        status_color = "red" if trend == "하락추세" else "green"
        st.markdown(f"### 현재 추세: :{status_color}[{trend}] (200일선 대비)")
        st.info(f"🎯 **행동 가이드:** {signal} (위험 신호 {risk}개)")
    with c2:
        st.write("") # 간격 맞춤용
        if st.button("🚀 텔레그램 발송", use_container_width=True):
            msg = (f"🚨 [시장 분석 보고]\n- 위험도: {risk}개\n- 가이드: {signal}\n"
                   f"- S&P500: {data['sp_now']:,.2f} ({trend})\n"
                   f"- 10Y금리: {data['us10y']:.2f}% ({data['us10y_diff']:+.3f})\n"
                   f"- HY스프레드: {data['hy_spread']:.2f}% ({data['hy_diff']:+.3f})")
            send_telegram_msg(msg)

    # --- [섹션 3] 기타 경제 지표 ---
    st.divider()
    cols = st.columns(4)
    other = {"dxy": "달러 인덱스", "usdkrw": "환율", "vix": "VIX 지수", "oil": "국제 유가"}
    for i, (k, v) in enumerate(other.items()):
        cols[i % 4].metric(label=v, value=f"{data[k]:.2f}", delta=details[k], delta_color="inverse")

except Exception as e:
    st.error(f"데이터 로딩 중 오류가 발생했습니다: {e}")
