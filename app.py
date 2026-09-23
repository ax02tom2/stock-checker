import streamlit as st
import pandas as pd
import yfinance as yf
import requests

# 設定網頁標題
st.set_page_title("個人持股健檢與智慧買賣點系統", layout="wide")

st.title("📈 個人持股健檢與智慧買賣點面板")
st.markdown("輸入持股後，系統將結合現價與技術指標（MA均線、RSI），自動評估當前最適合的買賣點參考！")

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

# 計算 RSI 技術指標的輔助函數
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

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

# 顯示目前持股表格與健檢
if not st.session_state.portfolio.empty:
    st.subheader("📊 持股健檢與智慧買賣點總覽")
    
    portfolio_df = st.session_state.portfolio.copy()
    
    current_prices = []
    total_market_values = []
    total_costs = []
    profits = []
    profit_pcts = []
    recommendations = []
    alerts = []

    for index, row in portfolio_df.iterrows():
        ticker = row["股票代號"]
        shares = row["買入股數"]
        cost = row["買入均價"]
        tp = row["停利目標價"]
        sl = row["停損目標價"]
        
        try:
            # 抓取近半年歷史資料來計算技術指標
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                ma60 = hist['Close'].rolling(window=60).mean().iloc[-1]
                rsi_series = calculate_rsi(hist['Close'])
                rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50
                recent_high = hist['High'].rolling(window=20).max().iloc[-1]
            else:
                current_price = cost
                ma20, ma60, rsi, recent_high = cost, cost, 50, cost

        except Exception:
            current_price = cost
            ma20, ma60, rsi, recent_high = cost, cost, 50, cost
            
        market_value = current_price * shares
        total_cost = cost * shares
        profit = market_value - total_cost
        profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        # --- 自動評估買賣點建議 ---
        if current_price <= ma60 * 1.03 and rsi < 45:
            rec_msg = f"💡 [買點參考] 貼近季線支撐(約{ma60:.1f})且RSI偏低({rsi:.1f})，可考慮逢低分批加碼"
        elif rsi > 70:
            rec_msg = f"🚨 [賣點參考] RSI過熱({rsi:.1f})，短線乖離過大，建議注意風險、分批停利"
        elif current_price >= recent_high * 0.98:
            rec_msg = f"⚠️ [賣點參考] 接近近期高點壓力區({recent_high:.1f})，留意調節"
        else:
            rec_msg = f"⏳ [觀望] 處於多空震盪區間 (季線: {ma60:.1f}, RSI: {rsi:.1f})"

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
        alerts.append(alert_msg)

    portfolio_df["現價"] = current_prices
    portfolio_df["市值"] = total_market_values
    portfolio_df["總成本"] = total_costs
    portfolio_df["未實現損益"] = profits
    portfolio_df["報酬率 (%)"] = profit_pcts
    portfolio_df["智慧買賣點建議"] = recommendations
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
        msg = "\n📌 【持股健檢智慧通知】\n"
        for index, row in portfolio_df.iterrows():
            if "達成" in row["狀態"] or "觸及" in row["狀態"] or "買點" in row["智慧買賣點建議"] or "賣點" in row["智慧買賣點建議"]:
                msg += f"\n• 股票: {row['股票代號']}\n  現價: {row['現價']}\n  建議: {row['智慧買賣點建議']}\n"
                notification_sent = True
        
        if notification_sent:
            success = send_line_notify(line_token, msg)
            if success:
                st.success("LINE 通知發送成功！")
            else:
                st.error("發送失敗，請檢查 LINE Token 是否正確。")
        else:
            st.info("目前沒有股票觸及重要買賣點。")
