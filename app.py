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
    page_icon="📈",
    layout="wide"
)

# --- 資料庫初始化 ---
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

# --- 核心機制：網址 UID 與還原碼 ---
query_params = st.query_params
if "uid" not in query_params or not query_params["uid"]:
    new_uid = str(uuid.uuid4())[:8].upper() 
    st.query_params["uid"] = new_uid
    user_uid = new_uid
else:
    user_uid = query_params["uid"].upper()

# --- 🚀 注入全新 Fintech 專業級 SaaS CSS 設計 ---
st.markdown("""
    <style>
    /* 全局背景色 - 淺灰藍色系，提升質感 */
    .stApp {
        background-color: #F8FAFC;
    }
    
    /* 隱藏預設的主選單與 footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 標題字體與顏色 */
    h1, h2, h3 {
        color: #0F172A;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    
    /* 讓 Form 變成一張有質感的白底立體卡片 */
    [data-testid="stForm"] {
        background-color: #FFFFFF;
        border-radius: 16px;
        padding: 24px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
    }
    
    /* 按鈕大改造 (漸層 + 圓角 + 陰影) */
    .stButton>button, .stFormSubmitButton>button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
        letter-spacing: 1px;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
        transition: all 0.3s ease;
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(37, 99, 235, 0.4);
        color: #FFFFFF;
    }
    
    /* 側邊欄設計 - 暗黑對比風格 */
    [data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #1E293B;
    }
    [data-testid="stSidebar"] * {
        color: #F8FAFC !important;
    }
    
    /* 戰情室數據卡片 (側邊飾條立體設計) */
    .dashboard-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 6px solid #3B82F6; /* 預設藍色左側飾條 */
        padding: 24px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.04);
        text-align: center;
        margin-bottom: 20px;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .dashboard-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
    }
    .card-title { color: #64748B; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
    .card-value { color: #0F172A; font-size: 28px; font-weight: 800; font-family: 'Arial', sans-serif;}
    .card-subtext { font-size: 15px; font-weight: 700; margin-top: 6px; }
    
    /* 特殊卡片飾條顏色 */
    .border-red { border-left-color: #DC2626 !important; }
    .border-green { border-left-color: #059669 !important; }
    .border-blue { border-left-color: #3B82F6 !important; }
    .border-purple { border-left-color: #8B5CF6 !important; }
    
    /* 分頁籤 (膠囊按鈕風格) */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 12px; 
        padding-bottom: 15px;
    }
    .stTabs [data-baseweb="tab"] { 
        background-color: #F1F5F9; 
        border-radius: 8px; 
        color: #475569; 
        padding: 12px 24px; 
        font-weight: 600; 
        border: 1px solid #CBD5E1; 
        transition: all 0.2s;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #E2E8F0;
    }
    .stTabs [aria-selected="true"] { 
        background: #0F172A !important; 
        color: #FFFFFF !important; 
        border-color: #0F172A !important;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- 側邊欄：資料還原區 ---
st.sidebar.title("🔐 系統與資料安全")
st.sidebar.markdown(f"您的專屬授權碼：\n# **`{user_uid}`**")
st.sidebar.info("💡 **貼心提醒**：\n此授權碼即為您的資料庫鑰匙。請將本網址「加入書籤」，或記下此代碼。")
st.sidebar.markdown("---")
st.sidebar.subheader("🔄 跨裝置還原資料")
restore_uid = st.sidebar.text_input("輸入 8 碼授權碼：", placeholder="例如: A1B2C3D4")
if st.sidebar.button("載入雲端持股"):
    if restore_uid:
        st.query_params["uid"] = restore_uid.strip().upper()
        st.rerun()

st.title("📈 智慧持股健檢與戰情分析儀表板")
st.markdown("歡迎使用專業級個人資產管理系統。資料採用 UID 加密隔離，重新整理絕不遺失。")

# --- 資料庫存取函數 ---
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

current_portfolio = load_portfolio(user_uid)

# --- 新增持股區塊 ---
st.subheader("📝 新增投資標的")
with st.form("add_form", clear_on_submit=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: t_input = st.text_input("名稱或代號 (例: 旺宏 或 2337)", value="")
    with c2: s_input = st.number_input("買入股數", min_value=1, value=1000, step=1000)
    with c3: c_input = st.number_input("買入均價", min_value=0.0, value=25.0)
    with c4: tp_input = st.number_input("停利目標價 (0表自動)", min_value=0.0, value=0.0)
    with c5: sl_input = st.number_input("停損目標價 (0表自動)", min_value=0.0, value=0.0)
    
    add_btn = st.form_submit_button("➕ 加入監控清單")
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
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("⚙️ 庫存部位管理")
    st.markdown("*(可直接於表格內點擊修改數字，或勾選最左側核取方塊後按 `Delete` 刪除，完成後請點擊下方儲存)*")
    
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
    
    if st.button("💾 儲存部位變更"):
        save_portfolio(user_uid, working_portfolio)
        st.success("變更已成功同步至資料庫！")
        st.rerun()

    # --- 盤勢健檢與儀表板計算 ---
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    st.subheader("📊 多指標戰情室與股利預測")
    
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
            
            div_data = stock.dividends
            if not div_data.empty:
                last_div = float(div_data.iloc[-1])
                last_div_date = div_data.index[-1].strftime("%Y-%m-%d")
        except:
            pass
            
        est_total_div = last_div * shares

        if market == "台股":
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

        if score >= 3: rec_msg = f"🟢 強力買點 (支撐約 {l_val:.1f})"
        elif score >= 1: rec_msg = f"🟡 逢低關注 (回測月線)"
        elif score <= -3: rec_msg = f"🔴 強力賣點 (近上軌 {u_val:.1f})"
        elif score <= -1: rec_msg = f"🟠 偏弱注意"
        else: rec_msg = f"⚪ 區間震盪"

        alert_msg = "正常監控"
        if current_price >= suggested_tp: alert_msg = "🎯 達停利目標"
        elif current_price <= suggested_sl: alert_msg = "⚠️ 停損警戒"

        current_prices.append(current_price)
        total_market_values.append(market_value)
        total_costs.append(total_cost)
        profits.append(profit)
        profit_pcts.append(profit_pct)
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
    portfolio_df["股東會與情報"] = souvenir_urls
    portfolio_df["狀態"] = alerts
    portfolio_df["綜合建議"] = recommendations

    # 數值格式化 (保留小數點給單價，總額去小數點)
    display_df = portfolio_df.copy()
    display_df["買入股數"] = display_df["買入股數"].apply(lambda x: f"{int(x):,}")
    display_df["買入均價"] = display_df["買入均價"].apply(lambda x: f"{x:,.2f}")
    display_df["現價"] = display_df["現價"].apply(lambda x: f"{x:,.2f}")
    display_df["市值"] = display_df["市值"].apply(lambda x: f"{int(x):,}")            
    display_df["總成本"] = display_df["總成本"].apply(lambda x: f"{int(x):,}")          
    display_df["未實現損益"] = display_df["未實現損益"].apply(lambda x: f"{int(x):,}")    
    display_df["報酬率 (%)"] = display_df["報酬率 (%)"].apply(lambda x: f"{x:,.2f}%")
    display_df["建議停利價"] = display_df["建議停利價"].apply(lambda x: f"{x:,.2f}")
    display_df["建議停損價"] = display_df["建議停損價"].apply(lambda x: f"{x:,.2f}")
    display_df["每股最近股利"] = display_df["每股最近股利"].apply(lambda x: f"{x:,.2f}")
    display_df["預估領取總股息"] = display_df["預估領取總股息"].apply(lambda x: f"{int(x):,}") 

    column_config_dict = {
        "股東會與情報": st.column_config.LinkColumn("股東會與情報", display_text="🔗 前往查詢")
    }

    # 專業膠囊分頁呈現
    tab_tw, tab_us = st.tabs(["🇹🇼 台灣股市 (TWSE/TPEx)", "🇺🇸 美股及海外 (US/Global)"])

    with tab_tw:
        tw_mask = portfolio_df["市場"] == "台股"
        if tw_mask.any():
            tw_display_df = display_df[tw_mask].drop(columns=["市場"])
            
            tw_cost = portfolio_df.loc[tw_mask, "總成本"].sum()
            tw_value = portfolio_df.loc[tw_mask, "市值"].sum()
            tw_profit = tw_value - tw_cost
            tw_profit_pct = (tw_profit / tw_cost) * 100 if tw_cost > 0 else 0
            tw_div_sum = portfolio_df.loc[tw_mask, "預估領取總股息"].sum()
            
            # HTML 手刻高質感指標卡片
            c1, c2, c3, c4 = st.columns(4)
            # 台股邏輯：紅賺綠賠
            p_color = "#DC2626" if tw_profit >= 0 else "#059669"
            p_class = "border-red" if tw_profit >= 0 else "border-green"
            
            with c1: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">總投資成本</div><div class="card-value">${tw_cost:,.0f}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">目前總市值</div><div class="card-value">${tw_value:,.0f}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="dashboard-card {p_class}"><div class="card-title">未實現損益</div><div class="card-value" style="color: {p_color};">${tw_profit:,.0f}</div><div class="card-subtext" style="color: {p_color};">({tw_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="dashboard-card border-purple"><div class="card-title">預估可領總股息</div><div class="card-value" style="color: #7C3AED;">${tw_div_sum:,.0f}</div></div>', unsafe_allow_html=True)
            
            st.dataframe(tw_display_df, use_container_width=True, column_config=column_config_dict)
        else:
            st.info("💡 目前尚無台股監控紀錄，請從上方表單新增。")

    with tab_us:
        us_mask = portfolio_df["市場"] == "美股/其他"
        if us_mask.any():
            us_display_df = display_df[us_mask].drop(columns=["市場"])
            
            us_cost = portfolio_df.loc[us_mask, "總成本"].sum()
            us_value = portfolio_df.loc[us_mask, "市值"].sum()
            us_profit = us_value - us_cost
            us_profit_pct = (us_profit / us_cost) * 100 if us_cost > 0 else 0
            us_div_sum = portfolio_df.loc[us_mask, "預估領取總股息"].sum()
            
            c1, c2, c3, c4 = st.columns(4)
            p_color = "#DC2626" if us_profit >= 0 else "#059669"
            p_class = "border-red" if us_profit >= 0 else "border-green"
            
            with c1: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">總投資成本</div><div class="card-value">${us_cost:,.0f}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">目前總市值</div><div class="card-value">${us_value:,.0f}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="dashboard-card {p_class}"><div class="card-title">未實現損益</div><div class="card-value" style="color: {p_color};">${us_profit:,.0f}</div><div class="card-subtext" style="color: {p_color};">({us_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="dashboard-card border-purple"><div class="card-title">預估可領總股息</div><div class="card-value" style="color: #7C3AED;">${us_div_sum:,.0f}</div></div>', unsafe_allow_html=True)
            
            st.dataframe(us_display_df, use_container_width=True, column_config=column_config_dict)
        else:
            st.info("💡 目前尚無美股監控紀錄，請從上方表單新增。")
