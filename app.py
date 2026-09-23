import streamlit as st
import pandas as pd
import yfinance as yf

# 設定網頁寬度與標題
st.set_page_config(page_title="個人持股健檢與多指標智慧買賣點系統", layout="wide")

st.title("📈 個人持股健檢與多指標智慧買賣點面板")
st.markdown("系統自動分類 **台股與美股**，抓取中文名稱，並綜合 **MA均線、RSI、MACD 與布林通道** 四大指標提供智慧買賣點建議！")

# --- 技術指標計算函數（強化防錯） ---
def calculate_rsi(series, period=14):
    try:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except Exception:
        return pd.Series(50, index=series.index)

def calculate_macd(series, fast=12, slow=26, signal=9):
    try:
        exp1 = series.ewm(span=fast, adjust=False).mean()
        exp2 = series.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        hist = macd - signal_line
        return macd, signal_line, hist
    except Exception:
        zero_series = pd.Series(0, index=series.index)
        return zero_series, zero_series, zero_series

def calculate_bollinger_bands(series, window=20, num_std=2):
    try:
        ma = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        upper = ma + (std * num_std)
        lower = ma - (std * num_std)
        return upper, ma, lower
    except Exception:
        return series, series, series

# 取得股票名稱的輔助函數
def get_stock_name(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get('longName') or info.get('shortName') or ticker
        return name
    except Exception:
        return ticker

# --- 主畫面：輸入持股資料 ---
st.subheader("📝 輸入你的持股清單")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(
        columns=["股票代號", "股票名稱", "市場", "買入股數", "買入均價", "停利目標價", "停損目標價"]
    )

with st.form("stock_form"):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        ticker_input = st.text_input("股票代號 (台股例: 2330.TW / 美股例: AAPL)", value="2330.TW")
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
        clean_ticker = ticker_input.upper().strip()
        market = "台股" if (".TW" in clean_ticker or ".TWO" in clean_ticker) else "美股"
        stock_name = get_stock_name(clean_ticker)
        
        new_data = pd.DataFrame({
            "股票代號": [clean_ticker],
            "股票名稱": [stock_name],
            "市場": [market],
            "買入股數": [shares_input],
            "買入均價": [cost_input],
            "停利目標價": [tp_input],
            "停損目標價": [sl_input]
        })
        
        st.session_state.portfolio = pd.concat(
            [st.session_state.portfolio[st.session_state.portfolio["股票代號"] != clean_ticker], new_data]
        ).reset_index(drop=True)
        st.success(f"已成功加入/更新 {clean_ticker} ({stock_name})！")

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
        
        # 預設值
        current_price = cost
        ma20, ma60, rsi, m_val, s_val, u_val, l_val = cost, cost, 50, 0, 0, cost, cost
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            
            if not hist.empty and len(hist) > 10:
                close = hist['Close']
                current_price = float(close.iloc[-1])
                
                # 計算各指標
                ma20_s = close.rolling(window=min(20, len(close))).mean()
                ma60_s = close.rolling(window=min(60, len(close))).mean()
                rsi_s = calculate_rsi(close)
                macd_s, signal_s, _ = calculate_macd(close)
                upper_bb_s, _, lower_bb_s = calculate_bollinger_bands(close)
                
                ma20 = float(ma20_s.iloc[-1]) if not ma20_s.empty else cost
                ma60 = float(ma60_s.iloc[-1]) if not ma60_s.empty else cost
                rsi = float(rsi_s.iloc[-1]) if not rsi_s.empty else 50
                m_val = float(macd_s.iloc[-1]) if not macd_s.empty else 0
                s_val = float(signal_s.iloc[-1]) if not signal_s.empty else 0
                u_val = float(upper_bb_s.iloc[-1]) if not upper_bb_s.empty else cost
                l_val = float(lower_bb_s.iloc[-1]) if not lower_bb_s.empty else cost
        except Exception:
            # 發生任何例外時保持預設成本價，不讓程式崩潰
            pass
            
        market_value = current_price * shares
        total_cost = cost * shares
        profit = market_value - total_cost
        profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        score = 0
        if current_price <= ma60 * 1.02 and current_price >= ma60 * 0.98:
            score += 2
        elif current_price < ma60:
            score -= 1
            
        if rsi < 35:
            score += 2
        elif rsi > 70:
            score -= 2

        if m_val > s_val:
            score += 1
        else:
            score -= 1

        if current_price <= l_val * 1.01:
            score += 2
        elif current_price >= u_val * 0.99:
            score -= 2

        if score >= 3:
            rec_msg = f"🟢 【強力買點參考】建議參考價位：約 {l_val:.1f} ~ {ma60:.1f} 附近逢低分批佈局。"
        elif score >= 1:
            rec_msg = f"🟡 【逢低關注】短線回測支撐，可觀察月線({ma20:.1f})附近。"
        elif score <= -3:
            rec_msg = f"🔴 【強力賣點參考】建議於上軌({u_val:.1f})附近分批停利。"
        elif score <= -1:
            rec_msg = f"🟠 【偏弱注意】短線動能轉弱，留意風險控制。"
        else:
            rec_msg = f"⚪ 【震盪觀望】多空交錯，區間操作 (季線: {ma60:.1f}, RSI: {rsi:.1f})"

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

    # --- 分頁籤呈現：台股與美股分開 ---
    tab_tw, tab_us = st.tabs(["🇹🇼 台股持股專區", "🇺🇸 美股持股專區"])

    with tab_tw:
        tw_df = portfolio_df[portfolio_df["市場"] == "台股"]
        if not tw_df.empty:
            st.dataframe(tw_df.drop(columns=["市場"]), use_container_width=True)
            tw_cost = tw_df["總成本"].sum()
            tw_value = tw_df["市值"].sum()
            tw_profit = tw_value - tw_cost
            tw_profit_pct = (tw_profit / tw_cost) * 100 if tw_cost > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("台股總投資成本", f"${tw_cost:,.2f}")
            c2.metric("台股目前總市值", f"${tw_value:,.2f}")
            c3.metric("台股總未實現損益", f"${tw_profit:,.2f}", f"{tw_profit_pct:.2f}%")
        else:
            st.info("目前尚無台股持股紀錄。")

    with tab_us:
        us_df = portfolio_df[portfolio_df["市場"] == "美股"]
        if not us_df.empty:
            st.dataframe(us_df.drop(columns=["市場"]), use_container_width=True)
            us_cost = us_df["總成本"].sum()
            us_value = us_df["市值"].sum()
            us_profit = us_value - us_cost
            us_profit_pct = (us_profit / us_cost) * 100 if us_cost > 0 else 0
            
            u1, u2, u3 = st.columns(3)
            u1.metric("美股總投資成本", f"${us_cost:,.2f}")
            u2.metric("美股目前總市值", f"${us_value:,.2f}")
            u3.metric("美股總未實現損益", f"${us_profit:,.2f}", f"{us_profit_pct:.2f}%")
        else:
            st.info("目前尚無美股持股紀錄。")

    # 全體總結
    st.markdown("---")
    sum_cost = portfolio_df["總成本"].sum()
    sum_value = portfolio_df["市值"].sum()
    total_profit = sum_value - sum_cost
    total_profit_pct = (total_profit / sum_cost) * 100 if sum_cost > 0 else 0

    st.subheader("🌐 全體資產總結")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("總投資成本", f"${sum_cost:,.2f}")
    col_b.metric("目前總市值", f"${sum_value:,.2f}")
    col_c.metric("總未實現損益", f"${total_profit:,.2f}", f"{total_profit_pct:.2f}%")
