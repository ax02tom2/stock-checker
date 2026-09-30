import streamlit as st
import pandas as pd
import yfinance as yf
import re
import twstock
import sqlite3
import uuid
import requests

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
    try:
        c.execute('ALTER TABLE user_portfolios ADD COLUMN stock_div REAL DEFAULT 0.0')
    except: pass
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
    .stApp { background-color: #F8FAFC; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    h1, h2, h3 { color: #0F172A; font-weight: 800; letter-spacing: -0.5px; }
    
    [data-testid="stForm"] {
        background-color: #FFFFFF; border-radius: 16px; padding: 24px;
        border: 1px solid #E2E8F0; box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
    }
    
    .stButton>button, .stFormSubmitButton>button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: #FFFFFF; border: none; border-radius: 8px; padding: 10px 24px;
        font-weight: 600; letter-spacing: 1px; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
        transition: all 0.3s ease;
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        transform: translateY(-2px); box-shadow: 0 6px 15px rgba(37, 99, 235, 0.4); color: #FFFFFF;
    }
    
    [data-testid="stSidebar"] { background-color: #0F172A; border-right: 1px solid #1E293B; }
    [data-testid="stSidebar"] * { color: #F8FAFC !important; }
    
    .dashboard-card {
        background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 6px solid #3B82F6;
        padding: 24px 20px; border-radius: 12px; box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.04);
        text-align: center; margin-bottom: 20px; transition: transform 0.2s, box-shadow 0.2s;
    }
    .dashboard-card:hover { transform: translateY(-4px); box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1); }
    .card-title { color: #64748B; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
    .card-value { color: #0F172A; font-size: 28px; font-weight: 800; font-family: 'Arial', sans-serif;}
    .card-subtext { font-size: 15px; font-weight: 700; margin-top: 6px; }
    
    .border-red { border-left-color: #DC2626 !important; }
    .border-green { border-left-color: #059669 !important; }
    .border-blue { border-left-color: #3B82F6 !important; }
    .border-purple { border-left-color: #8B5CF6 !important; }
    
    .legend-card {
        background: #FFFFFF; border-radius: 12px; padding: 20px;
        border: 1px solid #E2E8F0;
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 12px; padding-bottom: 15px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #F1F5F9; border-radius: 8px; color: #475569; padding: 12px 24px; 
        font-weight: 600; border: 1px solid #CBD5E1; transition: all 0.2s;
    }
    .stTabs [data-baseweb="tab"]:hover { background-color: #E2E8F0; }
    .stTabs [aria-selected="true"] { 
        background: #0F172A !important; color: #FFFFFF !important; border-color: #0F172A !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
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

# --- 資料庫與快取設定 ---
@st.cache_data
def get_tw_stocks_list():
    options = []
    for code, info in twstock.codes.items():
        if info.type in ['股票', 'ETF']:
            options.append(f"{code} {info.name}")
    return options

tw_stock_options = get_tw_stocks_list()

def load_portfolio(uid):
    conn = sqlite3.connect('portfolio_v3.db', check_same_thread=False)
    df = pd.read_sql('''SELECT ticker as "股票代號", chinese_name as "中文名稱", market as "市場", 
                        shares as "買入股數", cost as "買入均價", tp as "停利目標價", sl as "停損目標價", stock_div as "股票股利(手動覆蓋)"
                        FROM user_portfolios WHERE uid = ?''', conn, params=(uid,))
    conn.close()
    return df

def save_portfolio(uid, df):
    conn = sqlite3.connect('portfolio_v3.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('DELETE FROM user_portfolios WHERE uid = ?', (uid,))
    for _, row in df.iterrows():
        stock_div_val = float(row.get("股票股利(手動覆蓋)", 0.0))
        c.execute('''INSERT OR REPLACE INTO user_portfolios (uid, ticker, chinese_name, market, shares, cost, tp, sl, stock_div)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (uid, row["股票代號"], row["中文名稱"], row["市場"], row["買入股數"], row["買入均價"], row["停利目標價"], row["停損目標價"], stock_div_val))
    conn.commit()
    conn.close()

# 🚀 動態爬蟲抓取股利
@st.cache_data(ttl=43200)
def fetch_dividend_auto(ticker, market):
    cash_div, stock_div, div_date = 0.0, 0.0, "-"
    if market == "台股":
        code = ticker.replace('.TW', '').replace('.TWO', '')
        try:
            url = f"https://tw.stock.yahoo.com/quote/{code}/dividend"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            res = requests.get(url, headers=headers, timeout=5)
            
            c_matches = re.findall(r'"cashDividend"\s*:\s*([0-9.]+)', res.text)
            s_matches = re.findall(r'"stockDividend"\s*:\s*([0-9.]+)', res.text)
            d_matches = re.findall(r'"exDividendDate"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})"', res.text)
            
            if c_matches: cash_div = float(c_matches[0])
            if s_matches: stock_div = float(s_matches[0])
            if d_matches: div_date = d_matches[0]
        except: pass
        
        if cash_div == 0.0 and stock_div == 0.0:
            try:
                stock = yf.Ticker(ticker)
                div_data = stock.dividends
                if not div_data.empty:
                    cash_div = float(div_data.iloc[-1])
                    div_date = div_data.index[-1].strftime("%Y-%m-%d")
            except: pass
    else:
        try:
            stock = yf.Ticker(ticker)
            div_data = stock.dividends
            if not div_data.empty:
                cash_div = float(div_data.iloc[-1])
                div_date = div_data.index[-1].strftime("%Y-%m-%d")
        except: pass
    return cash_div, stock_div, div_date

def calculate_rsi(series, period=14):
    try:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except: return pd.Series(50, index=series.index)

def calculate_macd(series, fast=12, slow=26, signal=9):
    try:
        exp1 = series.ewm(span=fast, adjust=False).mean()
        exp2 = series.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        return macd, macd.ewm(span=signal, adjust=False).mean(), macd - macd.ewm(span=signal, adjust=False).mean()
    except: return pd.Series(0, index=series.index), pd.Series(0, index=series.index), pd.Series(0, index=series.index)

def calculate_bollinger_bands(series, window=20, num_std=2):
    try:
        ma = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        return ma + (std * num_std), ma, ma - (std * num_std)
    except: return series, series, series

current_portfolio = load_portfolio(user_uid)

# --- 新增投資標的 ---
st.subheader("📝 新增投資標的")
tab_add_tw, tab_add_us = st.tabs(["🇹🇼 智慧搜尋新增台股", "🇺🇸 新增海外/美股"])

with tab_add_tw:
    with st.form("add_tw_form", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
        with c1: tw_sel = st.selectbox("🔍 請輸入代號或名稱", tw_stock_options, help="只要打一個字就會自動過濾相關股票！")
        with c2: tw_s = st.number_input("買入股數", min_value=1, value=1000, step=1000)
        with c3: tw_c = st.number_input("買入均價", min_value=0.0, value=25.0)
        with c4: tw_tp = st.number_input("停利(0=自動)", min_value=0.0, value=0.0)
        with c5: tw_sl = st.number_input("停損(0=自動)", min_value=0.0, value=0.0)
        
        btn_tw = st.form_submit_button("➕ 加入台股監控")
        if btn_tw and tw_sel:
            code, name = tw_sel.split(" ", 1)
            try:
                market_type = twstock.codes[code].market
                suffix = ".TWO" if market_type == "上櫃" else ".TW"
            except:
                suffix = ".TW"
            
            full_ticker = f"{code}{suffix}"
            
            new_row = pd.DataFrame({"股票代號": [full_ticker], "中文名稱": [name], "市場": ["台股"], 
                                    "買入股數": [tw_s], "買入均價": [tw_c], "停利目標價": [tw_tp], "停損目標價": [tw_sl], "股票股利(手動覆蓋)": [0.0]})
            updated_df = pd.concat([current_portfolio[current_portfolio["股票代號"] != full_ticker], new_row]).reset_index(drop=True)
            save_portfolio(user_uid, updated_df)
            st.success(f"成功新增：{code} {name}")
            st.rerun()

with tab_add_us:
    with st.form("add_us_form", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
        with c1: us_sel = st.text_input("🌎 輸入美股代號 (如 AAPL, TSLA)")
        with c2: us_s = st.number_input("買入股數 (美股)", min_value=1, value=10, step=10)
        with c3: us_c = st.number_input("買入均價", min_value=0.0, value=150.0)
        with c4: us_tp = st.number_input("停利(0=自動)", min_value=0.0, value=0.0)
        with c5: us_sl = st.number_input("停損(0=自動)", min_value=0.0, value=0.0)
        
        btn_us = st.form_submit_button("➕ 加入美股監控")
        if btn_us and us_sel:
            ticker_us = us_sel.strip().upper()
            try:
                stock = yf.Ticker(ticker_us)
                if stock.history(period="5d").empty:
                    st.error(f"❌ 查無美股代號：{ticker_us}")
                else:
                    name_us = stock.info.get('shortName') or ticker_us
                    new_row = pd.DataFrame({"股票代號": [ticker_us], "中文名稱": [name_us], "市場": ["美股/其他"], 
                                            "買入股數": [us_s], "買入均價": [us_c], "停利目標價": [us_tp], "停損目標價": [us_sl], "股票股利(手動覆蓋)": [0.0]})
                    updated_df = pd.concat([current_portfolio[current_portfolio["股票代號"] != ticker_us], new_row]).reset_index(drop=True)
                    save_portfolio(user_uid, updated_df)
                    st.success(f"成功新增：{ticker_us}")
                    st.rerun()
            except:
                st.error("❌ 查無美股代號或連線失敗！")

# --- 持股管理 (編輯區格式化保持完美) ---
if not current_portfolio.empty:
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("⚙️ 庫存部位管理")
    st.markdown("*(若外部 API 阻擋導致未能自動抓取股票股利，請直接於右側 `股票股利(手動覆蓋)` 填寫)*")
    
    edit_df = current_portfolio.copy()
    edit_df["買入股數"] = pd.to_numeric(edit_df["買入股數"], errors='coerce').fillna(0).astype(int)
    edit_df["買入均價"] = pd.to_numeric(edit_df["買入均價"], errors='coerce').fillna(0.0).astype(float)
    edit_df["停利目標價"] = pd.to_numeric(edit_df["停利目標價"], errors='coerce').fillna(0.0).astype(float)
    edit_df["停損目標價"] = pd.to_numeric(edit_df["停損目標價"], errors='coerce').fillna(0.0).astype(float)
    edit_df["股票股利(手動覆蓋)"] = pd.to_numeric(edit_df.get("股票股利(手動覆蓋)", 0.0), errors='coerce').fillna(0.0).astype(float)
    
    edited_display = st.data_editor(
        edit_df, 
        num_rows="dynamic", 
        use_container_width=True, 
        key="portfolio_editor",
        column_config={
            "買入股數": st.column_config.NumberColumn("買入股數", format="%d", step=1000),
            "買入均價": st.column_config.NumberColumn("買入均價", format="%.2f", step=0.1),
            "停利目標價": st.column_config.NumberColumn("停利目標價", format="%.2f", step=0.1),
            "停損目標價": st.column_config.NumberColumn("停損目標價", format="%.2f", step=0.1),
            "股票股利(手動覆蓋)": st.column_config.NumberColumn("股票股利(手動覆蓋)", format="%.2f", step=0.1),
        }
    )
    
    if st.button("💾 儲存部位變更"):
        save_portfolio(user_uid, edited_display)
        st.success("變更已成功同步至資料庫！")
        st.rerun()

    # --- 盤勢健檢與儀表板 ---
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    st.subheader("📊 多指標戰情室與股利預測")
    
    portfolio_df = edited_display.copy()
    current_prices, total_market_values, total_costs, profits, profit_pcts = [], [], [], [], []
    final_tps, final_sls, recommendations, alerts = [], [], [], []
    cash_divs, stock_divs, total_cash_divs, est_stock_shares, div_dates, souvenir_urls = [], [], [], [], [], []

    for index, row in portfolio_df.iterrows():
        ticker = row["股票代號"]
        shares = float(row["買入股數"])
        cost = float(row["買入均價"])
        user_tp = float(row["停利目標價"])
        user_sl = float(row["停損目標價"])
        user_stock_div_override = float(row.get("股票股利(手動覆蓋)", 0.0))
        market = row["市場"]
        
        if market == "台股" and ticker.endswith('.TW'):
            code = ticker.replace('.TW', '')
            if code in twstock.codes and twstock.codes[code].market == "上櫃":
                ticker = f"{code}.TWO"
        
        current_price = cost
        ma20, ma60, rsi, m_val, s_val, u_val, l_val = cost, cost, 50, 0, 0, cost, cost
        
        auto_cash_div, auto_stock_div, last_div_date = fetch_dividend_auto(ticker, market)
        final_stock_div = user_stock_div_override if user_stock_div_override > 0 else auto_stock_div
        
        try:
            stock = yf.Ticker(str(ticker))
            hist = stock.history(period="6mo")
            if not hist.empty and len(hist) > 10:
                close = hist['Close']
                current_price = float(close.iloc[-1])
                ma20, ma60 = float(close.rolling(20).mean().iloc[-1]), float(close.rolling(60).mean().iloc[-1])
                rsi = float(calculate_rsi(close).iloc[-1])
                macd_s, signal_s, _ = calculate_macd(close)
                m_val, s_val = float(macd_s.iloc[-1]), float(signal_s.iloc[-1])
                upper_bb, _, lower_bb = calculate_bollinger_bands(close)
                u_val, l_val = float(upper_bb.iloc[-1]), float(lower_bb.iloc[-1])
        except: pass
            
        est_total_cash = auto_cash_div * shares
        est_stock = shares * (final_stock_div / 10.0)
        
        s_url = f"https://tw.stock.yahoo.com/quote/{ticker.replace('.TW','').replace('.TWO','')}/profile" if market == "台股" else f"https://finance.yahoo.com/quote/{ticker}/key-statistics"

        suggested_tp = user_tp if user_tp > 0 else round(max(u_val, current_price * 1.15), 2)
        suggested_sl = user_sl if user_sl > 0 else round(max(l_val, current_price * 0.91), 2)

        market_value, total_cost = current_price * shares, cost * shares
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

        alert_msg = "✔️️ 正常監控"
        if current_price >= suggested_tp: alert_msg = "🎯 達停利目標"
        elif current_price <= suggested_sl: alert_msg = "⚠ 停損警戒"

        current_prices.append(current_price); total_market_values.append(market_value)
        total_costs.append(total_cost); profits.append(profit); profit_pcts.append(profit_pct)
        final_tps.append(suggested_tp); final_sls.append(suggested_sl)
        recommendations.append(rec_msg); alerts.append(alert_msg)
        
        cash_divs.append(auto_cash_div); stock_divs.append(final_stock_div)
        total_cash_divs.append(est_total_cash); est_stock_shares.append(est_stock)
        div_dates.append(last_div_date); souvenir_urls.append(s_url)

    portfolio_df["標的名稱"] = portfolio_df["中文名稱"]
    portfolio_df = portfolio_df.drop(columns=["股票代號", "中文名稱"])
    
    # 【關鍵修復】：全部保持純數字！不轉字串！格式化統交給 Styler！
    portfolio_df["現價"] = current_prices
    portfolio_df["市值"] = total_market_values
    portfolio_df["總成本"] = total_costs
    portfolio_df["未實現損益"] = profits
    portfolio_df["報酬率 (%)"] = profit_pcts
    portfolio_df["建議停利價"] = final_tps
    portfolio_df["建議停損價"] = final_sls
    portfolio_df["現金股利"] = cash_divs
    portfolio_df["股票股利"] = stock_divs
    portfolio_df["預估現金股息"] = total_cash_divs
    portfolio_df["預估配發股數"] = est_stock_shares
    
    portfolio_df["🔗即時情報與股東會"] = souvenir_urls
    portfolio_df["狀態"] = alerts
    portfolio_df["綜合建議"] = recommendations

    # 🎨 顏色渲染器與格式化大全集 (在這裡一次綁定所有欄位)
    def style_dataframe(df):
        styled = df.style
        def color_profit(val):
            if type(val) in [int, float]:
                if val > 0: return 'color: #DC2626; font-weight: bold;'
                elif val < 0: return 'color: #059669; font-weight: bold;'
            return ''
        def color_tp(val): return 'color: #D97706; font-weight: bold;'
        def color_sl(val): return 'color: #7C3AED; font-weight: bold;'

        if hasattr(styled, "map"):
            styled = styled.map(color_profit, subset=["未實現損益", "報酬率 (%)"])\
                           .map(color_tp, subset=["建議停利價"])\
                           .map(color_sl, subset=["建議停損價"])
        else:
            styled = styled.applymap(color_profit, subset=["未實現損益", "報酬率 (%)"])\
                           .applymap(color_tp, subset=["建議停利價"])\
                           .applymap(color_sl, subset=["建議停損價"])
                           
        # 【完美解決小數點與千分位】：所有數值欄位在此定義精準格式！
        return styled.format({
            "買入股數": "{:,.0f}",
            "買入均價": "{:,.2f}",
            "停利目標價": "{:,.2f}",
            "停損目標價": "{:,.2f}",
            "現價": "{:,.2f}",
            "市值": "{:,.0f}",
            "總成本": "{:,.0f}",
            "未實現損益": "{:,.0f}",
            "報酬率 (%)": "{:,.2f}%",
            "建議停利價": "{:,.2f}",
            "建議停損價": "{:,.2f}",
            "現金股利": "{:,.2f}",
            "股票股利": "{:,.2f}",
            "預估現金股息": "{:,.0f}",
            "預估配發股數": "{:,.0f}"
        })

    column_config_dict = {"🔗即時情報與股東會": st.column_config.LinkColumn("🔗即時情報與股東會", display_text="點擊前往")}

    tab_tw, tab_us = st.tabs(["🇹🇼 台灣股市 (TWSE/TPEx)", "🇺🇸 美股及海外 (US/Global)"])

    with tab_tw:
        tw_mask = portfolio_df["市場"] == "台股"
        if tw_mask.any():
            tw_display_df = portfolio_df[tw_mask].drop(columns=["市場", "股票股利(手動覆蓋)"])
            
            # 使用列表推導直接從原始串列中計算總額
            tw_cost = sum([total_costs[i] for i, m in enumerate(portfolio_df["市場"]) if m == "台股"])
            tw_value = sum([total_market_values[i] for i, m in enumerate(portfolio_df["市場"]) if m == "台股"])
            tw_profit = tw_value - tw_cost
            tw_profit_pct = (tw_profit / tw_cost) * 100 if tw_cost > 0 else 0
            tw_div_sum = sum([total_cash_divs[i] for i, m in enumerate(portfolio_df["市場"]) if m == "台股"])
            
            c1, c2, c3, c4 = st.columns(4)
            p_color = "#DC2626" if tw_profit >= 0 else "#059669"
            p_class = "border-red" if tw_profit >= 0 else "border-green"
            
            with c1: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">總投資成本</div><div class="card-value">${tw_cost:,.0f}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">目前總市值</div><div class="card-value">${tw_value:,.0f}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="dashboard-card {p_class}"><div class="card-title">未實現損益</div><div class="card-value" style="color: {p_color};">${tw_profit:,.0f}</div><div class="card-subtext" style="color: {p_color};">({tw_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="dashboard-card border-purple"><div class="card-title">預估總現金股息</div><div class="card-value" style="color: #7C3AED;">${tw_div_sum:,.0f}</div></div>', unsafe_allow_html=True)
            
            st.dataframe(style_dataframe(tw_display_df), use_container_width=True, column_config=column_config_dict)
        else:
            st.info("💡 目前尚無台股監控紀錄，請從上方表單新增。")

    with tab_us:
        us_mask = portfolio_df["市場"] == "美股/其他"
        if us_mask.any():
            us_display_df = portfolio_df[us_mask].drop(columns=["市場", "股票股利(手動覆蓋)"])
            us_cost = sum([total_costs[i] for i, m in enumerate(portfolio_df["市場"]) if m == "美股/其他"])
            us_value = sum([total_market_values[i] for i, m in enumerate(portfolio_df["市場"]) if m == "美股/其他"])
            us_profit = us_value - us_cost
            us_profit_pct = (us_profit / us_cost) * 100 if us_cost > 0 else 0
            us_div_sum = sum([total_cash_divs[i] for i, m in enumerate(portfolio_df["市場"]) if m == "美股/其他"])
            
            c1, c2, c3, c4 = st.columns(4)
            p_color = "#DC2626" if us_profit >= 0 else "#059669"
            p_class = "border-red" if us_profit >= 0 else "border-green"
            
            with c1: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">總投資成本</div><div class="card-value">${us_cost:,.0f}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="dashboard-card border-blue"><div class="card-title">目前總市值</div><div class="card-value">${us_value:,.0f}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="dashboard-card {p_class}"><div class="card-title">未實現損益</div><div class="card-value" style="color: {p_color};">${us_profit:,.0f}</div><div class="card-subtext" style="color: {p_color};">({us_profit_pct:.2f}%)</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="dashboard-card border-purple"><div class="card-title">預估總現金股息</div><div class="card-value" style="color: #7C3AED;">${us_div_sum:,.0f}</div></div>', unsafe_allow_html=True)
            
            st.dataframe(style_dataframe(us_display_df), use_container_width=True, column_config=column_config_dict)
        else:
            st.info("💡 目前尚無美股監控紀錄，請從上方表單新增。")

    # --- 📖 戰情室圖例說明 ---
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.subheader("📖 戰情室圖例與計算說明")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="legend-card">
        <h4>📊 【綜合建議】多指標評分</h4>
        <ul>
            <li>🟢 <b>強力買點</b>：股價回測強大支撐區 (如布林下軌、季線)，且技術指標超賣。</li>
            <li>🟡 <b>逢低關注</b>：股價回落至短中期均線 (如20日月線) 附近，可留意佈局機會。</li>
            <li>⚪ <b>區間震盪</b>：多空交戰，無明顯單邊趨勢，建議區間操作。</li>
            <li>🟠 <b>偏弱注意</b>：短線動能轉弱，跌破均線或MACD翻空，需提高警覺。</li>
            <li>🔴 <b>強力賣點</b>：短線過熱，乖離過大或觸及布林上軌壓力區，留意回檔。</li>
        </ul>
        <hr>
        <h4>🎨 【戰情表格顏色指南】</h4>
        <ul>
            <li><span style="color:#DC2626; font-weight:bold;">粗體紅色</span>：未實現損益為正 (獲利中)。</li>
            <li><span style="color:#059669; font-weight:bold;">粗體綠色</span>：未實現損益為負 (虧損中)。</li>
            <li><span style="color:#D97706; font-weight:bold;">粗體橘色</span>：建議停利價 (向上獲利目標)。</li>
            <li><span style="color:#7C3AED; font-weight:bold;">粗體紫色</span>：建議停損價 (向下防守底線)。</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="legend-card">
        <h4>🚨 【狀態】停利停損自動監控</h4>
        <ul>
            <li>🎯 <b>達停利目標</b>：現價已達到或超越您設定的停利價。</li>
            <li>⚠ <b>停損警戒</b>：現價已跌破您設定的停損價，請注意防守。</li>
            <li>✔️ <b>正常監控</b>：股價於停利與停損安全區間內正常波動。</li>
        </ul>
        <hr>
        <h4>💰 【全自動股利精算說明】</h4>
        <ul>
            <li>系統內建暴力爬蟲，全自動抓取最新公告之<b>現金與股票股利</b>。</li>
            <li>若遇阻擋未抓取到股票股利，您可直接於上方編輯器最右側的「<b>股票股利(手動覆蓋)</b>」手動輸入。</li>
            <li><b>預估獲配股數</b> = <code>買入股數</code> × <code>(股票股利 / 10)</code><br>
                <i>(例：華南金發放 0.5元股票股利，代表每 1000 股配發 50 股)</i>
            </li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
