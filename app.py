import streamlit as st
import pandas as pd
import yfinance as yf
import re
import twstock

# 設定網頁寬度與標題
st.set_page_config(
    page_title="QUANT DASHBOARD | 智慧持股健檢儀表板",
    page_icon="⚡",
    layout="wide"
)

# 注入科技感暗色系與儀表板專用 CSS
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        text-align: center;
        margin-bottom: 15px;
    }
    .metric-title {
        color: #9ca3af;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    .metric-value {
        color: #f3f4f6;
        font-size: 26px;
        font-weight: 700;
        margin-top: 5px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1f2937;
        border-radius: 8px 8px 0px 0px;
        color: #d1d5db;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ QUANT PORTFOLIO | 智慧持股健檢儀表板")
st.markdown("支援直接輸入 **`旺宏(2337)`**、**`2337`** 或美股代號（如 `AAPL`），系統將自動解析並提供中文名稱與多指標分析！")

# --- 技術指標計算函數 ---
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

# 智慧解析輸入（完美支援 旺宏(2337)、2337、AAPL）
def resolve_ticker(user_input):
    clean_input = user_input.strip()
    
    # 利用正規表達式抓出輸入中的數字（例如從 "旺宏(2337)" 中抓出 "2337"）
    digits = re.findall(r'\d+', clean_input)
    
    if digits:
        code = digits[0] # 取出第一個數字組合當作台股代號
        ticker = code + ".TW"
        # 透過 twstock 取得精準繁體中文名稱
        if code in twstock.codes:
            name = twstock.codes[code].name
        else:
            name = clean_input
        market = "台股"
    else:
        # 如果沒有數字，視為美股或其他英文代號
        ticker = clean_input.upper()
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            name = info.get('shortName') or ticker
        except:
            name = ticker
        market = "美股/其他"
        
    return ticker, name, market

# --- 主畫面：控制面板 ---
st.subheader("📝 新增 / 更新持股部位")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(
        columns=["股票代號", "中文名稱", "市場", "買入股數", "買入均價", "停利目標價", "停損目標價"]
    )

with st.form("stock_form", clear_on_submit=False):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        ticker_input = st.text_input("輸入名稱或代號 (例: 旺宏(2337))", value="旺宏(2337)")
    with col2:
        shares_input = st.number_input("買入股數", min_value=1, value=1000)
    with col3:
        cost_input = st.number_input("買入均價", min_value=0.0, value=25.0)
    with col4:
        tp_input = st.number_input("停利目標價 (0表自動)", min_value=0.0, value=0.0)
    with col5:
        sl_input = st.number_input("停損目標價 (0表自動)", min_value=0.0, value=0.0)
    
    submitted = st.form_submit_button("⚡ 執行加入 / 更新部位")
    if submitted:
        ticker, stock_name, market = resolve_ticker(ticker_input)
        display_name = f"{ticker.split('.')[0]} {stock_name}"
        
        new_data = pd.DataFrame({
            "股票代號": [ticker],
            "中文名稱": [display_name],
            "市場": [market],
            "買入股數": [shares_input],
            "買入均價": [cost_input],
            "停利目標價": [tp_input],
            "停損目標價": [sl_input]
        })
        
        st.session_state.portfolio = pd.concat(
            [st.session_state.portfolio[st.session_state.portfolio["股票代號"] != ticker], new_data]
        ).reset_index(drop=True)
        st.success(f"已成功載入部位：{display_name}！")

# 顯示持股總覽與儀表板
if not st.session_state.portfolio.empty:
    st.markdown("---")
    st.subheader("📊 盤勢監控與智慧買賣點儀表板")
    
    portfolio_df = st.session_state.portfolio.copy()
    
    current_prices = []
    total_market_values = []
    total_costs = []
    profits = []
    profit_pcts = []
    final_tps = []
    final_sls = []
    recommendations = []
    alerts = []

    for index, row in portfolio_df.iterrows():
        ticker = row["股票代號"]
        shares = row["買入股數"]
        cost = row["買入均價"]
        user_tp = row["停利目標價"]
        user_sl = row["停損目標價"]
        
        current_price = cost
        ma20, ma60, rsi, m_val, s_val, u_val, l_val = cost, cost, 50, 0, 0, cost, cost
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            
            if not hist.empty and len(hist) > 10:
                close = hist['Close']
                current_price = float(close.iloc[-1])
                
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
                u_val = float(upper_bb_s.iloc[-1]) if not upper_bb_s.empty else cost * 1.1
                l_val = float(lower_bb_s.iloc[-1]) if not lower_bb_s.empty else cost * 0.9
        except Exception:
            pass
            
        if user_tp > 0:
            suggested_tp = user_tp
        else:
            suggested_tp = round(max(u_val, cost * 1.15), 2)

        if user_sl > 0:
            suggested_sl = user_sl
        else:
            suggested_sl = round(min(l_val, cost * 0.92), 2)

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
            rec_msg = f"🟢 【強力買點】支撐區約 {l_val:.1f}~{ma60:.1f} 逢低佈局"
        elif score >= 1:
            rec_msg = f"🟡 【逢低關注】回測月線({ma20:.1f})支撐"
        elif score <= -3:
            rec_msg = f"🔴 【強力賣點】接近上軌({u_val:.1f})建議停利"
        elif score <= -1:
            rec_msg = f"🟠 【偏弱注意】短線動能轉弱"
        else:
            rec_msg = f"⚪ 【震盪觀望】多空交錯區間操作"

        alert_msg = "正常監控中"
        if current_price >= suggested_tp:
            alert_msg = "🎯 達停利目標！"
        elif current_price <= suggested_sl:
            alert_msg = "⚠️ 觸停損警戒！"

        current_prices.append(round(current_price, 2))
        total_market_values.append(round(market_value, 2))
        total_costs.append(round(total_cost, 2))
        profits.append(round(profit, 2))
        profit_pcts.append(round(profit_pct, 2))
        final_tps.append(suggested_tp)
        final_sls.append(suggested_sl)
        recommendations.append(rec_msg)
        alerts.append(alert_msg)

    portfolio_df["標的名稱"] = portfolio_df["中文名稱"]
    portfolio_df = portfolio_df.drop(columns=["股票代號", "中文名稱"])

    portfolio_df["現價"] = current_prices
    portfolio_df["市值"] = total_market_values
    portfolio_df["總成本"] = total_costs
    portfolio_df["未實現損益"] = profits
    portfolio_df["報酬率 (%)"] = profit_pcts
    portfolio_df["建議停利價"] = final_tps
    portfolio_df["建議停損價"] = final_sls
    portfolio_df["多指標綜合建議"] = recommendations
    portfolio_df["狀態"] = alerts

    # 分頁呈現
    tab_tw, tab_us = st.tabs(["🇹🇼 台股監控儀表板", "🇺🇸 美股/其他監控儀表板"])

    with tab_tw:
        tw_df = portfolio_df[portfolio_df["市場"] == "台股"]
        if not tw_df.empty:
            st.dataframe(tw_df.drop(columns=["市場"]), use_container_width=True)
            tw_cost = tw_df["總成本"].sum()
            tw_value = tw_df["市值"].sum()
            tw_profit = tw_value - tw_cost
            tw_profit_pct = (tw_profit / tw_cost) * 100 if tw_cost > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f'<div class="metric-card"><div class="metric-title">台股總投資成本</div><div class="metric-value">${tw_cost:,.2f}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-card"><div class="metric-title">台股目前總市值</div><div class="metric-value">${tw_value:,.2f}</div></div>', unsafe_allow_html=True)
            with c3:
                color_style = "color: #34d399;" if tw_profit >= 0 else "color: #f87171;"
                st.markdown(f'<div class="metric-card"><div class="metric-title">台股總未實現損益</div><div class="metric-value" style="{color_style}">${tw_profit:,.2f} ({tw_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
        else:
            st.info("目前尚無台股持股紀錄。")

    with tab_us:
        us_df = portfolio_df[portfolio_df["市場"] == "美股/其他"]
        if not us_df.empty:
            st.dataframe(us_df.drop(columns=["市場"]), use_container_width=True)
            us_cost = us_df["總成本"].sum()
            us_value = us_df["市值"].sum()
            us_profit = us_value - us_cost
            us_profit_pct = (us_profit / us_cost) * 100 if us_cost > 0 else 0
            
            u1, u2, u3 = st.columns(3)
            with u1:
                st.markdown(f'<div class="metric-card"><div class="metric-title">美股總投資成本</div><div class="metric-value">${us_cost:,.2f}</div></div>', unsafe_allow_html=True)
            with u2:
                st.markdown(f'<div class="metric-card"><div class="metric-title">美股目前總市值</div><div class="metric-value">${us_value:,.2f}</div></div>', unsafe_allow_html=True)
            with u3:
                color_style = "color: #34d399;" if us_profit >= 0 else "color: #f87171;"
                st.markdown(f'<div class="metric-card"><div class="metric-title">美股總未實現損益</div><div class="metric-value" style="{color_style}">${us_profit:,.2f} ({us_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
        else:
            st.info("目前尚無美股/其他持股紀錄。")

    # 全體總結
    st.markdown("---")
    sum_cost = portfolio_df["總成本"].sum()
    sum_value = portfolio_df["市值"].sum()
    total_profit = sum_value - sum_cost
    total_profit_pct = (total_profit / sum_cost) * 100 if sum_cost > 0 else 0

    st.subheader("🌐 總體資產戰情室 (Dashboard)")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f'<div class="metric-card"><div class="metric-title">總投資成本</div><div class="metric-value">${sum_cost:,.2f}</div></div>', unsafe_allow_html=True)
    with col_b:
        st.markdown(f'<div class="metric-card"><div class="metric-title">目前總市值</div><div class="metric-value">${sum_value:,.2f}</div></div>', unsafe_allow_html=True)
    with col_c:
        tot_color = "color: #34d399;" if total_profit >= 0 else "color: #f87171;"
        st.markdown(f'<div class="metric-card"><div class="metric-title">全體總未實現損益</div><div class="metric-value" style="{tot_color}">${total_profit:,.2f} ({total_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
