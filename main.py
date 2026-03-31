import streamlit as st
import yfinance as yf
from fredapi import Fred
import requests  # 서버 통신을 위해 최상단으로 이동

# =========================
# 🔑 설정 
# =========================
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]
FRED_API_KEY = st.secrets["FRED_API_KEY"]

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
# 📨 텔레그램 발송 함수
# =========================
def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.get(url, params=params, timeout=5) # 타임아웃 추가로 무한대기 방지
    except Exception as e:
        st.error(f"텔레그램 발송 실패: {e}")

# =========================
# 📊 데이터 가져오기
# =========================
@st.cache_data(ttl=300)
def get_data():
    # 데이터 수집 로직 (기존과 동일)
    us10y = fred.get_series_latest_release('DGS10')[-1]
    hy_spread = fred.get_series_latest_release('BAMLH0A0HYM2')[-1]
    dxy = yf.Ticker("DX-Y.NYB").history(period="1d")['Close'].iloc[-1]
    usdkrw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
    jpyusd = yf.Ticker("JPY=X").history(period="1d")['Close'].iloc[-1]
    jpykrw = (1 / jpyusd) * usdkrw
    vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    oil = yf.Ticker("CL=F").history(period="1d")['Close'].iloc[-1]
    sp500 = yf.Ticker("^GSPC").history(period="1y")
    sp_now = sp500['Close'].iloc[-1]
    sp_ma200 = sp500['Close'].rolling(200).mean().iloc[-1]

    return {
        "us10y": us10y, "hy_spread": hy_spread, "dxy": dxy,
        "usdkrw": usdkrw, "jpykrw": jpykrw, "vix": vix,
        "oil": oil, "sp_now": sp_now, "sp_ma200": sp_ma200
    }
# =========================
# 🚨 위험 및 행동 판단
# =========================
def analyze(data):
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
    if risk <= 2: return "🟢 매수 유지 / 분할 매수 진행"
    elif risk <= 4:
        return "🟡 관망 + 일부 비중 축소" if vix < 25 else "🟡 현금 비중 확대 준비"
    else:
        if vix > 30: return "🔴 공포 구간 → 분할 매수 시작 (1차)"
        elif trend == "하락추세": return "🔴 하락 진행 → 추가 하락 대기"
        else: return "🔴 방어 유지 (현금/금)"
# =========================
# 🎨 UI (색상 및 카드 스타일 적용)
# =========================
st.set_page_config(layout="wide")
st.title("📊 시장 자동 판단 시스템")

data = get_data()
risk, details, trend = analyze(data)

# 상단 상태 알림창 (위험도에 따라 색상 변경)
if risk >= 4:
    st.error(f"🚨 현재 위험 신호: {risk}개 (매우 위험)")
elif risk >= 2:
    st.warning(f"⚠️ 현재 위험 신호: {risk}개 (주의)")
else:
    st.success(f"✅ 현재 위험 신호: {risk}개 (안정)")

# 행동 가이드
signal = action_signal(risk, data["vix"], trend)
st.info(f"🎯 행동 가이드: {signal}")

# 핵심 지표 표시 (색상 메트릭 적용)
cols = st.columns(4)
labels = {
    "us10y": "미국채 10Y",
    "hy_spread": "하이일드 스프레드",
    "dxy": "달러 인덱스",
    "usdkrw": "원/달러 환율",
    "jpykrw": "엔/원 환율",
    "vix": "VIX 지수",
    "oil": "국제 유가"
}

for i, key in enumerate(labels):
    col = cols[i % 4]
    is_risk = details[key] == "위험"
    
    # 지표값이 기준치보다 높으면 빨간색(inverse), 낮으면 초록색(normal)으로 표시
    col.metric(
        label=labels[key], 
        value=f"{data[key]:.2f}", 
        delta=details[key], 
        delta_color="inverse" if is_risk else "normal"
    )
# S&P500 추세 섹션
st.divider()
sp_color = "red" if trend == "하락추세" else "green"
st.markdown(f"### S&P500 추세: :{sp_color}[{trend}]")
st.write(f"현재가: {data['sp_now']:.2f} / 200일선: {data['sp_ma200']:.2f}")

# =========================
# 📢 텔레그램 알림 실행
# =========================
if risk >= 3: 
    alert_msg = f"🚨 [위험] 신호 {risk}개 발생!\n🎯 가이드: {signal}\n📉 추세: {trend}"
    send_telegram_msg(alert_msg)
