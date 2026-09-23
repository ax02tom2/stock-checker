import streamlit as st
import pandas as pd
import yfinance as yf
import re
import twstock
import sqlite3
import hashlib

# 設定網頁寬度與標題
st.set_page_config(
    page_title="QUANT DASHBOARD | 智慧持股健檢儀表板",
    page_icon="⚡",
    layout="wide"
)

# --- 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect('quant_portfolio.db', check_same_thread=False)
    c = conn.cursor()
    # 使用者帳號表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    ''')
    # 使用者持股表
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolios (
            username TEXT,
            ticker TEXT,
            chinese_name TEXT,
            market TEXT,
            shares REAL,
            cost REAL,
            tp REAL,
            sl REAL,
            PRIMARY KEY (username, ticker)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 密碼加密
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_user(username, password):
    conn = sqlite3.connect('quant_portfolio.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    data = c.fetchone()
    conn.close()
    if data and data[0] == make_hash(password):
        return True
    return False

def register_user(username, password):
    conn = sqlite3.connect('quant_portfolio.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username, password) VALUES (?, ?)', (username, make_hash(password)))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

# 從資料庫載入特定使用者的持股
def load_user_portfolio(username):
    conn = sqlite3.connect('quant_portfolio.db', check_same_thread=False)
    df = pd.read_sql('SELECT ticker as "股票代號", chinese_name as "中文名稱", market as "市場", shares as "買入股數", cost as "買入均價", tp as "停利目標價", sl as "停損目標價" FROM portfolios WHERE username = ?', conn, params=(username,))
    conn.close()
    return df

# 儲存特定使用者的持股到資料庫
def save_user_portfolio(username, df):
    conn = sqlite3.connect('quant_portfolio.db', check_same_thread=False)
    c = conn.cursor()
    # 先刪除該使用者舊資料，再全部寫入最新資料
    c.execute('DELETE FROM portfolios WHERE username = ?', (username,))
    for _, row in df.iterrows():
        c.execute('''
            INSERT OR REPLACE INTO portfolios (username, ticker, chinese_name, market, shares, cost, tp, sl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, row["股票代號"], row["中文名稱"], row["市場"], row["買入股數"], row["買入均價"], row["停利目標價"], row["停損目標價"]))
    conn.commit()
    conn.close()

# --- 注入科技感 CSS ---
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
    .metric-title { color: #9ca3af; font-size: 14px; font-weight: 600; text-transform: uppercase; }
    .metric-value { color: #f3f4f6; font-size: 24px; font-weight: 700; margin-top: 5px; }
    .stTabs [data-baseweb="tab"] { background-color: #1f2937; border-radius: 8px 8px 0px 0px; color: #d1d5db; padding: 10px 20px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 登入控制系統 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.title("⚡ QUANT PORTFOLIO | 系統登入")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("🔑 會員登入")
        log_user = st.text_input("帳號", key="log_u")
        log_pass = st.text_input("密碼", type="password", key="log_p")
        if st.button("登入"):
            if check_user(log_user, log_pass):
                st.session_state.logged_in = True
                st.session_state.username = log_user
                st.rerun()
            else:
                st.error("帳號或密碼錯誤！")
    with col2:
        st.subheader("📝 註冊新帳號")
        reg_user = st.text_input("設定帳號", key="reg_u")
        reg_pass = st.text_input("設定密碼", type="password", key="reg_p")
        if st.button("註冊"):
            if reg_user and reg_pass:
                if register_user(reg_user, reg_pass):
                    st.success("註冊成功！請直接在左側登入。")
                else:
                    st.error("此帳號已被註冊過！")
            else:
                st.warning("請輸入完整帳號密碼。")
    st.stop()

# --- 登入後的主畫面 ---
st.sidebar.success(q_user := f"歡迎回來，{st.session_state.username}！")
if st.sidebar.button("登出帳號"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

st.title("⚡ QUANT PORTFOLIO | 智慧持股健檢儀表板")

# 載入該使用者的持股資料庫
current_user = st.session_state.username
db_portfolio = load_user_portfolio(current_user)

# 技術指標計算函數
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

def resolve_ticker(user_input):
    clean_input = str(user_input).strip()
    digits = re.findall(r'\d+', clean_input)
    if digits:
        code = digits[0]
        ticker = code + ".TW"
        name = twstock.codes[code].name if code in twstock.codes else clean_input
        market = "台股"
    else:
        ticker = clean_input.upper()
        try:
            stock = yf.Ticker(ticker)
            name = stock.info.get('shortName') or ticker
        except:
            name = ticker
        market = "美股/其他"
    return ticker, name, market

# --- 新增持股區塊 ---
st.subheader("📝 新增持股部位")
with st.form("add_form", clear_on_submit=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: t_input = st.text_input("名稱或代號 (例: 旺宏 或 2337)", value="")
    with c2: s_input = st.number_input("買入股數", min_value=1, value=1000)
    with c3: c_input = st.number_input("買入均價", min_value=0.0, value=25.0)
    with c4: tp_input = st.number_input("停利目標價 (0表自動)", min_value=0.0, value=0.0)
    with c5: sl_input = st.number_input("停損目標價 (0表自動)", min_value=0.0, value=0.0)
    
    add_btn = st.form_submit_button("➕ 加入清單")
    if add_btn and t_input:
        ticker, stock_name, market = resolve_ticker(t_input)
        new_row = pd.DataFrame({
            "股票代號": [ticker],
            "中文名稱": [stock_name],
            "市場": [market],
            "買入股數": [s_input],
            "買入均價": [c_input],
            "停利目標價": [tp_input],
            "停損目標價": [sl_input]
        })
        if not db_portfolio.empty:
            updated_df = pd.concat([db_portfolio[db_portfolio["股票代號"] != ticker], new_row]).reset_index(drop=True)
        else:
            updated_df = new_row
        save_user_portfolio(current_user, updated_df)
        st.success(f"成功新增：{ticker} {stock_name}")
        st.rerun()

# --- 持股管理與刪除 ---
if not db_portfolio.empty:
    st.markdown("---")
    st.subheader("🛠️ 現有持股管理（可直接修改或刪除，修改後點下方按鈕儲存）")
    
    edited_portfolio = st.data_editor(
        db_portfolio,
        num_rows="dynamic",
        use_container_width=True,
        key="portfolio_editor"
    )
    
    if st.button("💾 儲存表格變更"):
        save_user_portfolio(current_user, edited_portfolio)
        st.success("變更已永久儲存至資料庫！")
        st.rerun()

    # --- 盤勢健檢與儀表板計算 ---
    st.markdown("---")
    st.subheader("📊 多指標智慧買賣點戰情室")
    
    portfolio_df = edited_portfolio.copy()
    current_prices, total_market_values, total_costs, profits, profit_pcts, final_tps, final_sls, recommendations, alerts = [], [], [], [], [], [], [], [], []

    for index, row in portfolio_df.iterrows():
        ticker = row["股票代號"]
        shares = row["買入股數"]
        cost = row["買入均價"]
        user_tp = row["停利目標價"]
        user_sl = row["停損目標價"]
        
        current_price = cost
        ma20, ma60, rsi, m_val, s_val, u_val, l_val = cost, cost, 50, 0, 0, cost, cost
        
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
        except:
            pass
            
        suggested_tp = user_tp if user_tp > 0 else round(max(u_val, cost * 1.15), 2)
        suggested_sl = user_sl if user_sl > 0 else round(min(l_val, cost * 0.92), 2)

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

        if score >= 3: rec_msg = f"🟢 【強力買點】支撐區約 {l_val:.1f}~{ma60:.1f}"
        elif score >= 1: rec_msg = f"🟡 【逢低關注】回測月線({ma20:.1f})"
        elif score <= -3: rec_msg = f"🔴 【強力賣點】接近上軌({u_val:.1f})"
        elif score <= -1: rec_msg = f"🟠 【偏弱注意】短線動能轉弱"
        else: rec_msg = f"⚪ 【震盪觀望】多空交錯區間操作"

        alert_msg = "正常監控"
        if current_price >= suggested_tp: alert_msg = "🎯 達停利目標！"
        elif current_price <= suggested_sl: alert_msg = "⚠️ 停損警戒！"

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
            tw_cost, tw_value = tw_df["總成本"].sum(), tw_df["市值"].sum()
            tw_profit = tw_value - tw_cost
            tw_profit_pct = (tw_profit / tw_cost) * 100 if tw_cost > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f'<div class="metric-card"><div class="metric-title">台股總投資成本</div><div class="metric-value">${tw_cost:,.2f}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><div class="metric-title">台股目前總市值</div><div class="metric-value">${tw_value:,.2f}</div></div>', unsafe_allow_html=True)
            with c3: 
                color_style = "color: #34d399;" if tw_profit >= 0 else "color: #f87171;"
                st.markdown(f'<div class="metric-card"><div class="metric-title">台股總未實現損益</div><div class="metric-value" style="{color_style}">${tw_profit:,.2f} ({tw_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
        else:
            st.info("目前尚無台股持股紀錄。")

    with tab_us:
        us_df = portfolio_df[portfolio_df["市場"] == "美股/其他"]
        if not us_df.empty:
            st.dataframe(us_df.drop(columns=["市場"]), use_container_width=True)
            us_cost, us_value = us_df["總成本"].sum(), us_df["市值"].sum()
            us_profit = us_value - us_cost
            us_profit_pct = (us_profit / us_cost) * 100 if us_cost > 0 else 0
            
            u1, u2, u3 = st.columns(3)
            with u1: st.markdown(f'<div class="metric-card"><div class="metric-title">美股總投資成本</div><div class="metric-value">${us_cost:,.2f}</div></div>', unsafe_allow_html=True)
            with u2: st.markdown(f'<div class="metric-card"><div class="metric-title">美股目前總市值</div><div class="metric-value">${us_value:,.2f}</div></div>', unsafe_allow_html=True)
            with u3: 
                color_style = "color: #34d399;" if us_profit >= 0 else "color: #f87171;"
                st.markdown(f'<div class="metric-card"><div class="metric-title">美股總未實現損益</div><div class="metric-value" style="{color_style}">${us_profit:,.2f} ({us_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
        else:
            st.info("目前尚無美股/其他持股紀錄。")
