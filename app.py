import streamlit as st
import pandas as pd
import yfinance as yf
import requests

# 設定網頁標題
st.set_page_title("個人持股健檢與多指標智慧買賣點系統", layout="wide")

st.title("📈 個人持股健檢與多指標智慧買賣點面板")
st.markdown("系統自動綜合 **MA均線、RSI、MACD 與布林通道** 四大主流指標，為你進行深度交叉分析，並給出具體的買賣點與價位建議！")

# --- 側邊欄：LINE Notify 設定 ---
st.sidebar.header("🔔 LINE 通知設定")
line_token = st.sidebar.text_input("輸入 LINE Notify 權杖 (Token)", type="password")
st.sidebar.markdown("[如何取得 LINE Token？](https://notify-bot.line.me/)")

def send_line_notify(token, message):
    """發送 LINE 通知函式"""
    if not token:
        return False
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}
    response = requests.post(url, headers=headers, data=data)
    return response.status_code == 200

# --- 技術指標計算函數 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - signal_line
    return macd, signal_line, hist

def calculate_bollinger_bands(series, window=20, num_std=2):
    ma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = ma + (std * num_std)
    lower = ma - (std * num_std)
    return upper, ma, lower

# --- 主畫面：輸入持股資料 ---
st.subheader("📝 輸入你的持股清單")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(
        columns=["股票代號", "買入股數", "買入均價", "停利目標價", "停損目標價"]
    )

with st.form("stock_form"):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        ticker_input = st.text_input("股票代號 (例: 2330.TW)", value="2330.TW")
    with col2:
        shares_input = st.number_input("買入股數", min_value=1, value=1000)
    with col3:
        cost_input = st.number_input("買入均價", min_value=0.0, value=600.0)
    with col4:
        tp_input = st.number_input("停利目標價", min_value=0.0, value=700.0)
    with col5:
        sl_input = st.number_input("停損目標價", min_value=0.0, value=550.0)
    
    submitted = st.form_submit_button("新增 / 更新持股")
    if submitted:
        new_data = pd.DataFrame({
            "股票代號": [ticker_input.upper()],
            "買入股數": [shares_input],
            "買入均價": [cost_input],
            "停利目標價": [tp_input],
            "停損目標價": [sl_input]
        })
        st.session_state.portfolio = pd.concat(
            [st.session_state.portfolio[st.session_state.portfolio["股票代號"] != ticker_input.upper()], new_data]
        ).reset_index(drop=True)
        st.success(f"已成功加入/更新 {ticker_input.upper()}！")

# 顯示目前持股表格與多指標健檢
if not st.session_state.portfolio.empty:
    st.subheader("📊 持股健檢與多指標綜合分析總覽")
    
    portfolio_df = st.session_state.portfolio.copy()
    
    current_prices = []
    total_market_values = []
    total_costs = []
    profits = []
    profit_pcts = []
    recommendations = []
    indicators_info = []
    alerts = []

    for index, row in portfolio_df.iterrows():
        ticker = row["股票代號"]
        shares = row["買入股數"]
        cost = row["買入均價"]
        tp = row["停利目標價"]
        sl = row["停損目標價"]
        
        try:
            # 抓取歷史資料（至少半年以計算完整指標）
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            
            if not hist.empty and len(hist) > 60:
                close = hist['Close']
                current_price = close.iloc[-1]
                
                # 計算各指標
                ma20 = close.rolling(window=20).mean().iloc[-1]
                ma60 = close.rolling(window=60).mean().iloc[-1]
                rsi = calculate_rsi(close).iloc[-1]
                macd, signal, hist_macd = calculate_macd(close)
                m_val = macd.iloc[-1]
                s_val = signal.iloc[-1]
                upper_bb, mid_bb, lower_bb = calculate_bollinger_bands(close)
                u_val = upper_bb.iloc[-1]
                l_val = lower_bb.iloc[-1]
            else:
                current_price = cost
                ma20, ma60, rsi, m_val, s_val, u_val, l_val = cost, cost, 50, 0, 0, cost, cost
        except Exception:
            current_price = cost
            ma20, ma60, rsi, m_val, s_val, u_val, l_val = cost, cost, 50, 0, 0, cost, cost
            
        market_value = current_price * shares
        total_cost = cost * shares
        profit = market_value - total_cost
        profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        # --- 多指標綜合評分與買賣點判定 ---
        score = 0 # 正分代表偏多/買點，負分代表偏空/賣點
        reasons = []

        # 1. 均線判斷 (MA60 季線支撐與 MA20 月線)
        if current_price <= ma60 * 1.02 and current_price >= ma60 * 0.98:
            score += 2
            reasons.append(f"貼近季線支撐({ma60:.1f})")
        elif current_price < ma60:
            score -= 1
            reasons.append("跌破季線")
            
        # 2. RSI 動能判斷
        if rsi < 35:
            score += 2
            reasons.append(f"RSI超賣({rsi:.1f})")
        elif rsi > 70:
            score -= 2
            reasons.append(f"RSI過熱({rsi:.1f})")

        # 3. MACD 趨勢判斷
        if m_val > s_val:
            score += 1
            reasons.append("MACD多頭")
        else:
            score -= 1
            reasons.append("MACD空頭")

        # 4. 布林通道位置判斷
        if current_price <= l_val * 1.01:
            score += 2
            reasons.append(f"觸及布林下軌({l_val:.1f})")
        elif current_price >= u_val * 0.99:
            score -= 2
            reasons.append(f"觸及布林上軌({u_val:.1f})")

        # 綜合建議產出
        if score >= 3:
            rec_msg = f"🟢 【強力買點參考】多項指標顯示超跌或強支撐。綜合建議參考價位：約 {l_val:.1f} ~ {ma60:.1f} 附近逢低分批佈局。"
        elif score >= 1:
            rec_msg = f"🟡 【逢低關注】短線回測支撐，可觀察月線({ma20:.1f})附近有無守住。"
        elif score <= -3:
            rec_msg = f"🔴 【強力賣點參考】多指標過熱或結構轉弱。建議參考價位：逢高調節或於上軌({u_val:.1f})附近分批停利。"
        elif score <= -1:
            rec_msg = f"🟠 【偏弱注意】短線動能轉弱，留意乖離與風險控制。"
        else:
            rec_msg = f"⚪ 【震盪觀望】多空交錯，暫時區間操作 (季線: {ma60:.1f}, RSI: {rsi:.1f})"

        # 停利停損警示
        alert_msg = "正常"
        if current_price >= tp:
            alert_msg = "🎯 達成停利目標！"
        elif current_price <= sl:
            alert_msg = "⚠️ 觸及停損警戒！"

        current_prices.append(round(current_price, 2))
        total_market_values.append(round(market_value, 2))
        total_costs.append(round(total_cost, 2))
        profits.append(round(profit, 2))
        profit_pcts.append(round(profit_pct, 2))
        recommendations.append(rec_msg)
        indicators_info.append(f"RSI:{rsi:.1f} | MA60:{ma60:.1f} | 布林下:{l_val:.1f}")
        alerts.append(alert_msg)

    portfolio_df["現價"] = current_prices
    portfolio_df["市值"] = total_market_values
    portfolio_df["總成本"] = total_costs
    portfolio_df["未實現損益"] = profits
    portfolio_df["報酬率 (%)"] = profit_pcts
    portfolio_df["指標數據摘要"] = indicators_info
    portfolio_df["智慧買賣點綜合建議"] = recommendations
    portfolio_df["狀態"] = alerts

    st.dataframe(portfolio_df, use_container_width=True)

    # 總結數據
    sum_cost = portfolio_df["總成本"].sum()
    sum_value = portfolio_df["市值"].sum()
    total_profit = sum_value - sum_cost
    total_profit_pct = (total_profit / sum_cost) * 100 if sum_cost > 0 else 0

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("總投資成本", f"${sum_cost:,.2f}")
    col_b.metric("目前總市值", f"${sum_value:,.2f}")
    col_c.metric("總未實現損益", f"${total_profit:,.2f}", f"{total_profit_pct:.2f}%")

    # LINE 通知按鈕
    if st.button("🚀 檢查並發送 LINE 提醒"):
        notification_sent = False
        msg = "\n📌 【多指標持股健檢通知】\n"
        for index, row in portfolio_df.iterrows():
            if "達成" in row["狀態"] or "觸及" in row["狀態"] or "強力買點" in row["智慧買賣點綜合建議"] or "強力賣點" in row["智慧買賣點綜合建議"]:
                msg += f"\n• 股票: {row['股票代號']}\n  現價: {row['現價']}\n  建議: {row['智慧買賣點綜合建議']}\n"
                notification_sent = True
        
        if notification_sent:
            success = send_line_notify(line_token, msg)
            if success:
                st.success("LINE 通知發送成功！")
            else:
                st.error("發送失敗，請檢查 LINE Token 是否正確。")
        else:
            st.info("目前沒有股票觸及極端的買賣點或停利停損價。")
