import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ccxt
import ta
from datetime import datetime, timedelta
import time
import os
import secrets
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ===== TELEGRAM IMAGE SENDER FUNCTION =====
def send_to_telegram(photo_data, caption=""):
    """Send photo and message to your personal Telegram inbox"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        your_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not bot_token or not your_chat_id:
            return False, "Telegram not configured"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        files = {'photo': ('payment_proof.png', photo_data, 'image/png')}
        data = {
            'chat_id': your_chat_id,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            return True, "Sent to admin!"
        else:
            return False, f"Error: {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

# ===== PAYMENT CONFIGURATION =====
YOUR_WALLET = os.getenv("YOUR_WALLET", "0x87ea9fc331bbe75fdae07f291046920b878e1367")
ACCESS_DURATION = int(os.getenv("ACCESS_DURATION", 2592000))

# ===== PASSWORD MANAGEMENT SYSTEM =====
class PasswordManager:
    def __init__(self):
        self.valid_passwords = {}
        
    def generate_password(self, days=30):
        password = secrets.token_hex(4).upper()
        expiry = datetime.now() + timedelta(days=days)
        self.valid_passwords[password] = {
            'created': datetime.now(),
            'expiry': expiry,
            'used': False
        }
        return password
    
    def verify_password(self, password):
        if password in self.valid_passwords:
            if not self.valid_passwords[password]['used']:
                if datetime.now() <= self.valid_passwords[password]['expiry']:
                    self.valid_passwords[password]['used'] = True
                    return True, "Valid password"
                else:
                    return False, "Password expired"
            else:
                return False, "Password already used"
        return False, "Invalid password"

# ===== TRADING BOT CLASS =====
class TradingSignalBot:
    def __init__(self):
        self.exchanges = []
        self._init_exchanges()
    
    def _init_exchanges(self):
        # Try Bybit first (most reliable globally)
        try:
            bybit = ccxt.bybit({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
            self.exchanges.append(('bybit', bybit))
        except:
            pass
        
        # Try OKX
        try:
            okx = ccxt.okx({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
            self.exchanges.append(('okx', okx))
        except:
            pass
        
        # Try Kraken
        try:
            kraken = ccxt.krakenfutures({'enableRateLimit': True})
            self.exchanges.append(('kraken', kraken))
        except:
            pass
        
        # Try KuCoin
        try:
            kucoin = ccxt.kucoinfutures({'enableRateLimit': True})
            self.exchanges.append(('kucoin', kucoin))
        except:
            pass
    
    def fetch_data(self, symbol='BTC/USDT', timeframe='1h', limit=100):
        for name, exchange in self.exchanges:
            try:
                formatted_symbol = self._format_symbol(symbol, name)
                ohlcv = exchange.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)
                if ohlcv:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)
                    st.caption(f"📡 Data source: {name}")
                    return df
            except Exception as e:
                continue
        
        st.error("⚠️ Could not fetch market data. Please try again later.")
        return None
    
    def _format_symbol(self, symbol, exchange_name):
        base, quote = symbol.split('/')
        if exchange_name in ['bybit', 'okx']:
            return f"{base}{quote}"
        elif exchange_name == 'kraken':
            return f"PI_{base}{quote}"
        return f"{base}-{quote}"
    def fetch_data(self, symbol='BTC/USDT', timeframe='1h', limit=100):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return None
    
    def calculate_indicators(self, df):
        if df is None or len(df) < 20:
            return df
        try:
            df['ema_9'] = ta.trend.ema_indicator(df['close'], window=9)
            df['ema_21'] = ta.trend.ema_indicator(df['close'], window=21)
            df['rsi'] = ta.momentum.rsi(df['close'], window=14)
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_lower'] = bb.bollinger_lband()
        except:
            pass
        return df
    
    def generate_signal(self, df):
        if df is None or len(df) < 50:
            return None
        try:
            latest = df.iloc[-1]
            bullish_score = 0
            bearish_score = 0
            reasons = []
            
            if not pd.isna(latest.get('ema_9', np.nan)) and not pd.isna(latest.get('ema_21', np.nan)):
                if latest['ema_9'] > latest['ema_21']:
                    bullish_score += 3
                    reasons.append("📈 Bullish EMA trend")
                else:
                    bearish_score += 3
                    reasons.append("📉 Bearish EMA trend")
            
            if not pd.isna(latest.get('rsi', np.nan)):
                if latest['rsi'] < 30:
                    bullish_score += 4
                    reasons.append(f"💪 Oversold RSI: {latest['rsi']:.1f}")
                elif latest['rsi'] > 70:
                    bearish_score += 4
                    reasons.append(f"⚠️ Overbought RSI: {latest['rsi']:.1f}")
                elif latest['rsi'] > 50:
                    bullish_score += 1
                else:
                    bearish_score += 1
            
            total_score = bullish_score - bearish_score
            
            if total_score >= 3:
                signal = "LONG"
                confidence = min(50 + (total_score * 5), 95)
            elif total_score <= -3:
                signal = "SHORT"
                confidence = min(50 + (abs(total_score) * 5), 95)
            else:
                signal = "NEUTRAL"
                confidence = 50
            
            current_price = latest['close']
            volatility = df['close'].pct_change().std() * 100
            
            if volatility > 3:
                sl_percent = 0.035
                tp_percent = 0.07
            elif volatility < 1.5:
                sl_percent = 0.015
                tp_percent = 0.03
            else:
                sl_percent = 0.025
                tp_percent = 0.05
            
            if signal == "LONG":
                stop_loss = current_price * (1 - sl_percent)
                take_profit = current_price * (1 + tp_percent)
            elif signal == "SHORT":
                stop_loss = current_price * (1 + sl_percent)
                take_profit = current_price * (1 - tp_percent)
            else:
                stop_loss = None
                take_profit = None
            
            risk = abs(current_price - stop_loss) if stop_loss else 0
            reward = abs(take_profit - current_price) if take_profit else 0
            rr_ratio = reward / risk if risk > 0 else 2.0
            
            reasons.append(f"📊 Score: Bullish {bullish_score} - Bearish {bearish_score} = {total_score}")
            
            return {
                'signal': signal,
                'confidence': int(confidence),
                'current_price': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_reward_ratio': rr_ratio,
                'reasons': reasons,
                'rsi': latest.get('rsi', 50),
                'volatility': f"{volatility:.2f}%"
            }
        except Exception as e:
            st.error(f"Error generating signal: {e}")
            return None

# Page configuration
st.set_page_config(page_title="Futures Big Bot", page_icon="favicon.png", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .signal-long { background-color: #d4edda; padding: 10px; border-radius: 5px; color: #155724; text-align: center; font-size: 24px; font-weight: bold; }
    .signal-short { background-color: #f8d7da; padding: 10px; border-radius: 5px; color: #721c24; text-align: center; font-size: 24px; font-weight: bold; }
    .signal-neutral { background-color: #fff3cd; padding: 10px; border-radius: 5px; color: #856404; text-align: center; font-size: 24px; font-weight: bold; }
    .payment-box { background: linear-gradient(135deg, #F3BA2F 0%, #F0B90B 100%); padding: 30px; border-radius: 15px; color: white; text-align: center; margin: 20px 0; }
    .access-badge { background-color: #28a745; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; display: inline-block; }
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    .stApp header {display: none !important;}
    .stApp [data-testid="stToolbar"] {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'multi_signals' not in st.session_state:
    st.session_state.multi_signals = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()
if 'access_granted' not in st.session_state:
    st.session_state.access_granted = False
if 'access_expiry' not in st.session_state:
    st.session_state.access_expiry = None
if 'password_manager' not in st.session_state:
    st.session_state.password_manager = PasswordManager()

# Initialize bot
@st.cache_resource
def get_bot():
    return TradingSignalBot()
bot = get_bot()

# Check access expiry
if st.session_state.access_expiry and datetime.now() > st.session_state.access_expiry:
    st.session_state.access_granted = False
    st.session_state.access_expiry = None

# ===== MAIN APP LAYOUT =====
if not st.session_state.access_granted:
    # NOT LOGGED IN - Show payment and upload
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.image("https://cryptologos.cc/logos/binance-coin-bnb-logo.png", width=50)
        st.markdown("### 🔐 BEP20 USDT Access")
        st.markdown("""
        <div style="background-color: #f8d7da; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
            <span style="background-color: #dc3545; color: white; padding: 5px 15px; border-radius: 20px;">🔒 LOCKED</span>
            <p style="margin-top: 10px;">Complete payment below for 30 days access</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 💰 Purchase Access - 25 USDT")
        st.markdown(f"""
        <div class="payment-box">
            <h2>25 USDT</h2>
            <p>BEP20 (Binance Smart Chain)</p>
            <p><strong>30 Days Premium Access</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📋 Your Payment Address")
        st.code(YOUR_WALLET, language="text")
        
        st.markdown("""
        **📋 Copy Instructions:**
        1. Click inside the code box above
        2. Press **Ctrl+A** (Windows) or **Cmd+A** (Mac)
        3. Press **Ctrl+C** (Windows) or **Cmd+C** (Mac)
        4. Paste into Binance app
        """)
        
        st.error("⚠️ Send exactly 25 USDT on BEP20 network")
        st.markdown("---")
        
        st.markdown("### 🔑 Enter Access Password")
        access_password = st.text_input("Password:", type="password", placeholder="Enter your password", key="login_password")
        
        if st.button("🔓 Unlock Access", use_container_width=True, type="primary"):
            if access_password:
                if access_password == "password.me":
                    st.session_state.access_granted = True
                    st.session_state.access_expiry = datetime.now() + timedelta(seconds=ACCESS_DURATION)
                    st.success("✅ Admin access granted!")
                    st.balloons()
                    st.rerun()
                else:
                    valid, message = st.session_state.password_manager.verify_password(access_password)
                    if valid:
                        st.session_state.access_granted = True
                        st.session_state.access_expiry = datetime.now() + timedelta(seconds=ACCESS_DURATION)
                        st.success("✅ Access granted! Welcome to Premium!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            else:
                st.warning("Please enter a password")
    
    with col_right:
        st.markdown("### 📤 Submit Payment Proof")
        
        uploaded_file = st.file_uploader("Upload payment screenshot", type=['png', 'jpg', 'jpeg'])
        tx_id = st.text_input("Transaction ID (optional)", placeholder="Paste your transaction ID here")
        
        col_a, col_b = st.columns(2)
        with col_a:
            user_telegram = st.text_input("Your Telegram (optional)", placeholder="@username")
        with col_b:
            user_email = st.text_input("Your Email (optional)", placeholder="email@example.com")
        
        if st.button("📨 Send Payment Proof", use_container_width=True, type="primary"):
            if uploaded_file:
                with st.spinner("Sending..."):
                    try:
                        caption = f"""
🔔 NEW PAYMENT PROOF

💰 Amount: 25 USDT (BEP20)
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔑 TXID: {tx_id or 'Not provided'}

User Contact:
📱 Telegram: {user_telegram or 'Not provided'}
📧 Email: {user_email or 'Not provided'}
"""
                        photo_bytes = uploaded_file.getvalue()
                        success, message = send_to_telegram(photo_bytes, caption)
                        
                        if success:
                            st.success("✅ Payment proof sent! You'll receive your password soon.")
                            st.balloons()
                        else:
                            st.error(f"❌ Failed: {message}")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            else:
                st.warning("Please upload a screenshot")
        
        st.markdown("""
        <a href="https://t.me/forexbigadmin" target="_blank">
            <button style="background-color: #0088cc; color: white; padding: 10px; border: none; border-radius: 5px; width: 100%; cursor: pointer;">
                📱 Contact Admin Directly
            </button>
        </a>
        """, unsafe_allow_html=True)

else:
    # LOGGED IN - Show trading interface
    st.title("🤖 AI Trading Signals - Premium Access")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    available_coins = [
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT",
        "XRP/USDT", "DOGE/USDT", "LINK/USDT", "AVAX/USDT", "MATIC/USDT"
    ]
    
    with col1:
        selected_coin = st.selectbox("Select Coin", available_coins, index=0, key="coin_select")
    with col2:
        timeframe = st.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=1, key="timeframe_select")
    with col3:
        st.write("")
        st.write("")
        search_button = st.button("🔍 Generate Signal", use_container_width=True, type="primary")
    
    auto_refresh = st.checkbox("🔄 Auto-refresh (30s)")
    
    if search_button:
        with st.spinner(f"Analyzing {selected_coin}..."):
            df = bot.fetch_data(selected_coin, timeframe)
            if df is not None:
                df = bot.calculate_indicators(df)
                signal = bot.generate_signal(df)
                if signal:
                    signal['coin'] = selected_coin
                    st.session_state.multi_signals = [signal]
                    st.session_state.last_update = datetime.now()
    
    if st.session_state.multi_signals:
        signal = st.session_state.multi_signals[0]
        
        if signal['signal'] == "LONG":
            st.markdown(f'<div class="signal-long">📈 {signal["coin"]} - LONG SIGNAL ({signal["confidence"]}%)</div>', unsafe_allow_html=True)
        elif signal['signal'] == "SHORT":
            st.markdown(f'<div class="signal-short">📉 {signal["coin"]} - SHORT SIGNAL ({signal["confidence"]}%)</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="signal-neutral">⏸️ {signal["coin"]} - NEUTRAL ({signal["confidence"]}%)</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Price", f"${signal['current_price']:,.2f}")
        with col2:
            st.metric("RSI (14)", f"{signal['rsi']:.1f}")
        with col3:
            st.metric("Confidence", f"{signal['confidence']}%")
        with col4:
            st.metric("Volatility", signal['volatility'])
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("📊 Entry")
            st.write(f"**Price:** ${signal['current_price']:,.2f}")
        with col2:
            st.subheader("🛑 Stop Loss")
            if signal.get('stop_loss'):
                st.write(f"**Price:** ${signal['stop_loss']:,.2f}")
            else:
                st.write("N/A")
        with col3:
            st.subheader("🎯 Take Profit")
            if signal.get('take_profit'):
                st.write(f"**Price:** ${signal['take_profit']:,.2f}")
            else:
                st.write("N/A")
        
        if signal.get('risk_reward_ratio'):
            st.markdown("---")
            st.subheader("📈 Risk/Reward")
            st.write(f"**Ratio:** 1:{signal['risk_reward_ratio']:.2f}")
        
        st.markdown("---")
        st.subheader("🔍 Analysis")
        for reason in signal['reasons']:
            st.write(f"• {reason}")
        
        st.caption(f"Last updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if auto_refresh:
            time.sleep(30)
            st.rerun()
    else:
        st.info("👈 Select a coin and click 'Generate Signal'")

# ===== ADMIN PANEL =====
st.markdown("---")
with st.expander("👑 Admin Panel", expanded=False):
    admin_pass = st.text_input("Admin Password:", type="password", key="admin_pass")
    
    if admin_pass == "ADMIN123":
        st.success("✅ Admin access")
        
        tab1, tab2 = st.tabs(["🔑 Generate Password", "✅ Grant Access"])
        
        with tab1:
            days = st.number_input("Access days:", min_value=1, max_value=365, value=30)
            if st.button("Generate Password"):
                new_pwd = st.session_state.password_manager.generate_password(days)
                st.code(new_pwd, language="text")
                st.caption(f"Expires in {days} days")
        
        with tab2:
            if st.button("Grant Access"):
                st.session_state.access_granted = True
                st.session_state.access_expiry = datetime.now() + timedelta(seconds=ACCESS_DURATION)
                st.success("Access granted!")
                st.rerun()

st.markdown("---")
st.caption("© 2024 Futures Big Bot. All rights reserved.")
