import streamlit as st
import pandas as pd
import yfinance as yf
import re
import twstock
import sqlite3
import uuid

# 設定網頁寬度與標題
st.set_page_config(
    page_title="智慧持股健檢儀表板",
    page_icon="⚡",
    layout="wide"
)

# --- 資料庫初始化（確保 F5 重新整理資料不丟失） ---
def init_db():
    conn = sqlite3.connect('portfolio_v3.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_portfolios (
            uid TEXT,
            ticker TEXT,
            chinese_name TEXT,
            market TEXT,
            shares REAL,
            cost REAL,
            tp REAL,
            sl REAL,
            PRIMARY KEY (uid, ticker)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 確保每個瀏覽器分頁都有專屬且持久的 UID
query_params = st.query_params
if "uid" not in query_params or not query_params["uid"]:
    new_uid = str(uuid.uuid4())[:8]
    st.query_params["uid"] = new_uid
    user_uid = new_uid
else:
    user_uid = query_params["uid"]

def load_portfolio(uid):
    conn = sqlite3.connect('portfolio_v3.db', check_same_thread=False)
    df = pd.read_sql('''
        SELECT ticker as "股票代號", chinese_name as "中文名稱", market as "市場", 
               shares as "買入股數", cost as "買入均價", tp as "停利目標價", sl as "停損目標價" 
        FROM user_portfolios WHERE uid = ?
    ''', conn, params=(uid,))
    conn.close()
    return df

def save_portfolio(uid, df):
    conn = sqlite3.connect('portfolio_v3.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('DELETE FROM user_portfolios WHERE uid = ?', (uid,))
    for _, row in df.iterrows():
        c.execute('''
            INSERT OR REPLACE INTO user_portfolios (uid, ticker, chinese_name, market, shares, cost, tp, sl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (uid, row["股票代號"], row["中文名稱"], row["市場"], row["買入股數"], row["買入均價"], row["停利目標價"], row["停損目標價"]))
    conn.commit()
    conn.close()

# 注入科技感暗色系與台股紅綠習慣 CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        text-align: center;
        margin-bottom: 15px;
    }
    .metric-title { color: #9ca3af; font-size: 14px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .metric-value { color: #f3f4f6; font-size: 24px; font-weight: 700; margin-top: 5px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1f2937; border-radius: 8px 8px 0px 0px; color: #d1d5db; padding: 10px 20px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ 智慧持股健檢儀表板")

# --- 技術指標計算函數 ---
def calculate_rsi(series, period=14):
    try:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except Exception:
        return pd.Series(50, index=series.index)

def calculate_macd(series, fast=12, slow=26, signal=9):
    try:
        exp1 = series.ewm(span=fast, adjust=False).mean()
        exp2 = series.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line, macd - signal_line
    except Exception:
        zero_series = pd.Series(0, index=series.index)
        return zero_series, zero_series, zero_series

def calculate_bollinger_bands(series, window=20, num_std=2):
    try:
        ma = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        return ma + (std * num_std), ma, ma - (std * num_std)
    except Exception:
        return series, series, series

# 驗證輸入代號
def resolve_and_verify_ticker(user_input):
    clean_input = str(user_input).strip()
    digits = re.findall(r'\d+', clean_input)
    
    if digits:
        code = digits[0]
        ticker = code + ".TW"
        if code in twstock.codes:
            name = twstock.codes[code].name
            market = "台股"
        else:
            return None, None, None
    else:
        ticker = clean_input.upper()
        market = "美股/其他"
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")
            if hist.empty:
                return None, None, None
            name = stock.info.get('shortName') or ticker
        except:
            return None, None, None
            
    return ticker, name, market

# 載入當前使用者的持股資料庫
current_portfolio = load_portfolio(user_uid)

# --- 新增持股區塊 ---
st.subheader("📝 新增持股部位")
with st.form("add_form", clear_on_submit=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: t_input = st.text_input("名稱或代號 (例: 旺宏 或 2337)", value="")
    with c2: s_input = st.number_input("買入股數", min_value=1, value=1000, step=1000)
    with c3: c_input = st.number_input("買入均價", min_value=0.0, value=25.0)
    with c4: tp_input = st.number_input("停利目標價 (0表自動)", min_value=0.0, value=0.0)
    with c5: sl_input = st.number_input("停損目標價 (0表自動)", min_value=0.0, value=0.0)
    
    add_btn = st.form_submit_button("➕ 加入清單")
    if add_btn and t_input:
        ticker, stock_name, market = resolve_and_verify_ticker(t_input)
        
        if ticker is None:
            st.error(f"❌ 查無此股票代號（「{t_input}」），請確認輸入是否正確！")
        else:
            new_row = pd.DataFrame({
                "股票代號": [ticker],
                "中文名稱": [stock_name],
                "市場": [market],
                "買入股數": [s_input],
                "買入均價": [c_input],
                "停利目標價": [tp_input],
                "停損目標價": [sl_input]
            })
            if not current_portfolio.empty:
                updated_df = pd.concat([current_portfolio[current_portfolio["股票代號"] != ticker], new_row]).reset_index(drop=True)
            else:
                updated_df = new_row
            save_portfolio(user_uid, updated_df)
            st.success(f"成功新增：{ticker} {stock_name}")
            st.rerun()

# --- 持股管理與刪除 ---
if not current_portfolio.empty:
    st.markdown("---")
    st.subheader("🛠️ 現有持股管理（可直接修改或刪除，修改後點下方按鈕儲存）")
    
    display_portfolio = current_portfolio.copy()
    for col in ["買入股數", "買入均價", "停利目標價", "停損目標價"]:
        display_portfolio[col] = pd.to_numeric(display_portfolio[col], errors='coerce').fillna(0)
    
    display_portfolio["買入股數"] = display_portfolio["買入股數"].apply(lambda x: f"{int(x):,}")
    display_portfolio["買入均價"] = display_portfolio["買入均價"].apply(lambda x: f"{float(x):,.2f}")
    display_portfolio["停利目標價"] = display_portfolio["停利目標價"].apply(lambda x: f"{float(x):,.2f}")
    display_portfolio["停損目標價"] = display_portfolio["停損目標價"].apply(lambda x: f"{float(x):,.2f}")
    
    edited_display = st.data_editor(
        display_portfolio,
        num_rows="dynamic",
        use_container_width=True,
        key="portfolio_editor"
    )
    
    working_portfolio = edited_display.copy()
    for col in ["買入股數", "買入均價", "停利目標價", "停損目標價"]:
        working_portfolio[col] = working_portfolio[col].astype(str).str.replace(',', '', regex=False)
        working_portfolio[col] = pd.to_numeric(working_portfolio[col], errors='coerce').fillna(0)
    
    if st.button("💾 儲存表格變更"):
        save_portfolio(user_uid, working_portfolio)
        st.success("變更已成功同步至資料庫！")
        st.rerun()

    # --- 盤勢健檢與儀表板計算 ---
    st.markdown("---")
    st.subheader("📊 多指標智慧買賣點戰情室 (含股利與紀念品)")
    
    portfolio_df = working_portfolio.copy()
    current_prices, total_market_values, total_costs, profits, profit_pcts = [], [], [], [], []
    final_tps, final_sls, recommendations, alerts = [], [], [], []
    recent_divs, total_divs, div_dates, souvenir_urls = [], [], [], []

    for index, row in portfolio_df.iterrows():
        ticker = row["股票代號"]
        shares = float(row["買入股數"])
        cost = float(row["買入均價"])
        user_tp = float(row["停利目標價"])
        user_sl = float(row["停損目標價"])
        market = row["市場"]
        
        current_price = cost
        ma20, ma60, rsi, m_val, s_val, u_val, l_val = cost, cost, 50, 0, 0, cost, cost
        last_div = 0.0
        last_div_date = "-"
        
        try:
            stock = yf.Ticker(str(ticker))
            hist = stock.history(period="6mo")
            if not hist.empty and len(hist) > 10:
                close = hist['Close']
                current_price = float(close.iloc[-1])
                ma20 = float(close.rolling(20).mean().iloc[-1])
                ma60 = float(close.rolling(60).mean().iloc[-1])
                rsi = float(calculate_rsi(close).iloc[-1])
                macd_s, signal_s, _ = calculate_macd(close)
                m_val, s_val = float(macd_s.iloc[-1]), float(signal_s.iloc[-1])
                upper_bb, _, lower_bb = calculate_bollinger_bands(close)
                u_val, l_val = float(upper_bb.iloc[-1]), float(lower_bb.iloc[-1])
            
            # 取得最新除權息資料
            div_data = stock.dividends
            if not div_data.empty:
                last_div = float(div_data.iloc[-1])
                last_div_date = div_data.index[-1].strftime("%Y-%m-%d")
        except:
            pass
            
        est_total_div = last_div * shares

        # 🚀 修正 404 問題：改為串接穩定且手機排版友善的 Yahoo奇摩股市
        if market == "台股":
            # Yahoo Finance 台灣版的專屬頁面
            s_url = f"https://tw.stock.yahoo.com/quote/{ticker}/profile"
        else:
            s_url = f"https://finance.yahoo.com/quote/{ticker}/key-statistics"

        if user_tp > 0:
            suggested_tp = user_tp
        else:
            suggested_tp = round(max(u_val, current_price * 1.15), 2)

        if user_sl > 0:
            suggested_sl = user_sl
        else:
            suggested_sl = round(max(l_val, current_price * 0.91), 2)

        market_value = current_price * shares
        total_cost = cost * shares
        profit = market_value - total_cost
        profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        score = 0
        if current_price <= ma60 * 1.02 and current_price >= ma60 * 0.98: score += 2
        elif current_price < ma60: score -= 1
        if rsi < 35: score += 2
        elif rsi > 70: score -= 2
        if m_val > s_val: score += 1
        else: score -= 1
        if current_price <= l_val * 1.01: score += 2
        elif current_price >= u_val * 0.99: score -= 2

        if score >= 3: rec_msg = f"🟢 【強力買點】支撐約 {l_val:.1f}~{ma60:.1f}"
        elif score >= 1: rec_msg = f"🟡 【逢低關注】回測月線({ma20:.1f})"
        elif score <= -3: rec_msg = f"🔴 【強力賣點】接近上軌({u_val:.1f})"
        elif score <= -1: rec_msg = f"🟠 【偏弱注意】短線動能轉弱"
        else: rec_msg = f"⚪ 【震盪觀望】多空交錯區間操作"

        alert_msg = "正常監控"
        if current_price >= suggested_tp: alert_msg = "🎯 達停利目標"
        elif current_price <= suggested_sl: alert_msg = "⚠️ 停損警戒"

        current_prices.append(round(current_price, 2))
        total_market_values.append(round(market_value, 2))
        total_costs.append(round(total_cost, 2))
        profits.append(round(profit, 2))
        profit_pcts.append(round(profit_pct, 2))
        final_tps.append(suggested_tp)
        final_sls.append(suggested_sl)
        recommendations.append(rec_msg)
        alerts.append(alert_msg)
        recent_divs.append(last_div)
        total_divs.append(est_total_div)
        div_dates.append(last_div_date)
        souvenir_urls.append(s_url)

    portfolio_df["標的名稱"] = portfolio_df["中文名稱"]
    portfolio_df = portfolio_df.drop(columns=["股票代號", "中文名稱"])
    
    portfolio_df["現價"] = current_prices
    portfolio_df["市值"] = total_market_values
    portfolio_df["總成本"] = total_costs
    portfolio_df["未實現損益"] = profits
    portfolio_df["報酬率 (%)"] = profit_pcts
    portfolio_df["建議停利價"] = final_tps
    portfolio_df["建議停損價"] = final_sls
    portfolio_df["每股最近股利"] = recent_divs
    portfolio_df["預估領取總股息"] = total_divs
    portfolio_df["最近除息日"] = div_dates
    portfolio_df["股東會與即時情報"] = souvenir_urls
    portfolio_df["狀態"] = alerts
    portfolio_df["綜合建議"] = recommendations

    # 建立戰情室顯示用的千分位格式 DataFrame
    display_df = portfolio_df.copy()
    display_df["買入股數"] = display_df["買入股數"].apply(lambda x: f"{int(x):,}")
    display_df["買入均價"] = display_df["買入均價"].apply(lambda x: f"{x:,.2f}")
    display_df["現價"] = display_df["現價"].apply(lambda x: f"{x:,.2f}")
    display_df["市值"] = display_df["市值"].apply(lambda x: f"{x:,.2f}")
    display_df["總成本"] = display_df["總成本"].apply(lambda x: f"{x:,.2f}")
    display_df["未實現損益"] = display_df["未實現損益"].apply(lambda x: f"{x:,.2f}")
    display_df["報酬率 (%)"] = display_df["報酬率 (%)"].apply(lambda x: f"{x:,.2f}%")
    display_df["建議停利價"] = display_df["建議停利價"].apply(lambda x: f"{x:,.2f}")
    display_df["建議停損價"] = display_df["建議停損價"].apply(lambda x: f"{x:,.2f}")
    display_df["每股最近股利"] = display_df["每股最近股利"].apply(lambda x: f"{x:,.2f}")
    display_df["預估領取總股息"] = display_df["預估領取總股息"].apply(lambda x: f"{x:,.2f}")

    # 定義表格特殊欄位渲染 (加入超連結樣式)
    column_config_dict = {
        "股東會與即時情報": st.column_config.LinkColumn("股東會與即時情報", display_text="🔗 點擊看股東會資訊")
    }

    # 分頁呈現
    tab_tw, tab_us = st.tabs(["🇹🇼 台股監控儀表板", "🇺🇸 美股/其他監控儀表板"])

    with tab_tw:
        tw_mask = portfolio_df["市場"] == "台股"
        if tw_mask.any():
            tw_display_df = display_df[tw_mask].drop(columns=["市場"])
            st.dataframe(tw_display_df, use_container_width=True, column_config=column_config_dict)
            
            tw_cost = portfolio_df.loc[tw_mask, "總成本"].sum()
            tw_value = portfolio_df.loc[tw_mask, "市值"].sum()
            tw_profit = tw_value - tw_cost
            tw_profit_pct = (tw_profit / tw_cost) * 100 if tw_cost > 0 else 0
            tw_div_sum = portfolio_df.loc[tw_mask, "預估領取總股息"].sum()
            
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f'<div class="metric-card"><div class="metric-title">台股總投資成本</div><div class="metric-value">${tw_cost:,.2f}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><div class="metric-title">台股目前總市值</div><div class="metric-value">${tw_value:,.2f}</div></div>', unsafe_allow_html=True)
            with c3: 
                color_style = "color: #f87171;" if tw_profit >= 0 else "color: #34d399;"
                st.markdown(f'<div class="metric-card"><div class="metric-title">台股總未實現損益</div><div class="metric-value" style="{color_style}">${tw_profit:,.2f} ({tw_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card"><div class="metric-title">總預估可領股息</div><div class="metric-value" style="color: #60a5fa;">${tw_div_sum:,.2f}</div></div>', unsafe_allow_html=True)
        else:
            st.info("目前尚無台股持股紀錄。")

    with tab_us:
        us_mask = portfolio_df["市場"] == "美股/其他"
        if us_mask.any():
            us_display_df = display_df[us_mask].drop(columns=["市場"])
            st.dataframe(us_display_df, use_container_width=True, column_config=column_config_dict)
            
            us_cost = portfolio_df.loc[us_mask, "總成本"].sum()
            us_value = portfolio_df.loc[us_mask, "市值"].sum()
            us_profit = us_value - us_cost
            us_profit_pct = (us_profit / us_cost) * 100 if us_cost > 0 else 0
            us_div_sum = portfolio_df.loc[us_mask, "預估領取總股息"].sum()
            
            u1, u2, u3, u4 = st.columns(4)
            with u1: st.markdown(f'<div class="metric-card"><div class="metric-title">美股總投資成本</div><div class="metric-value">${us_cost:,.2f}</div></div>', unsafe_allow_html=True)
            with u2: st.markdown(f'<div class="metric-card"><div class="metric-title">美股目前總市值</div><div class="metric-value">${us_value:,.2f}</div></div>', unsafe_allow_html=True)
            with u3: 
                color_style = "color: #f87171;" if us_profit >= 0 else "color: #34d399;"
                st.markdown(f'<div class="metric-card"><div class="metric-title">美股總未實現損益</div><div class="metric-value" style="{color_style}">${us_profit:,.2f} ({us_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
            with u4: st.markdown(f'<div class="metric-card"><div class="metric-title">總預估可領股息</div><div class="metric-value" style="color: #60a5fa;">${us_div_sum:,.2f}</div></div>', unsafe_allow_html=True)
        else:
            st.info("目前尚無美股/其他持股紀錄。")
