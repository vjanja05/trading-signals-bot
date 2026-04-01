import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ccxt
import ta
from datetime import datetime, timedelta
import time
import json
import os
from dotenv import load_dotenv
from io import BytesIO
import qrcode
import hashlib
import hmac
import secrets
import requests
from pathlib import Path

is_mobile = st.query_params.get("mobile", False)

# Page config with mobile settings
st.set_page_config(
    page_title="Futures Big Bot",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)
# Load environment variables
load_dotenv()
# ===== TELEGRAM IMAGE SENDER FUNCTION =====
def send_telegram_photo(photo_data, caption=""):
    """Send photo to YOUR personal Telegram inbox"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        your_chat_id = os.getenv("TELEGRAM_CHAT_ID")  # YOUR personal numeric ID
        
        if not bot_token or not your_chat_id:
            return False, "Telegram not configured"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        
        # Send photo from memory
        files = {'photo': ('payment_proof.png', photo_data, 'image/png')}
        data = {
            'chat_id': your_chat_id,  # This sends to YOUR Telegram inbox
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            return True, "Sent to your Telegram!"
        else:
            return False, f"Error: {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

# ===== ENHANCED PASSWORD REQUEST SYSTEM WITH TELEGRAM =====
with col2:
    st.markdown("### 📤 Submit Payment Proof")
    
    # File uploader for screenshot
    uploaded_file = st.file_uploader(
        "Upload payment screenshot", 
        type=['png', 'jpg', 'jpeg'],
        help="Take a screenshot of your successful 25 USDT payment and upload it here"
    )
    
    # Optional: Add transaction ID for easier verification
    tx_id = st.text_input(
        "Transaction ID (optional)", 
        placeholder="Paste your transaction ID here if available",
        help="This helps us verify faster"
    )
    
    # Optional: User contact info
    col_a, col_b = st.columns(2)
    with col_a:
        user_telegram = st.text_input("Your Telegram (optional)", placeholder="@username", 
                                      help="So we can send you the password faster")
    with col_b:
        user_email = st.text_input("Your Email (optional)", placeholder="email@example.com")
    
    # Submit button
    if st.button("📨 Submit Payment Proof", use_container_width=True, type="primary"):
        if uploaded_file is not None:
            with st.spinner("Sending payment proof to admin..."):
                try:
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    random_id = secrets.token_hex(4)
                    filename = f"{PAYMENT_PROOFS_DIR}/payment_{timestamp}_{random_id}.png"
                    
                    # Save the file locally
                    with open(filename, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Prepare caption for Telegram
                    caption = f"🔔 *NEW PAYMENT PROOF RECEIVED*\n\n"
                    caption += f"⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    caption += f"💰 *Amount:* 25 USDT (BEP20)\n"
                    caption += f"🔑 *TXID:* {tx_id or 'Not provided'}\n"
                    caption += f"📱 *Telegram:* {user_telegram or 'Not provided'}\n"
                    caption += f"📧 *Email:* {user_email or 'Not provided'}\n"
                    caption += f"🆔 *File:* {filename}\n\n"
                    caption += f"✅ *Action:* Reply with password or use admin panel"
                    
                    # Send to Telegram
                    success, message = send_telegram_photo(filename, caption)
                    
                    if success:
                        st.success("✅ Payment proof sent to admin! You'll receive your password soon.")
                        
                        # Show next steps
                        st.info(f"""
                        **📱 Next steps:**
                        1. ✅ Admin received your payment proof
                        2. 🔐 Password will be sent within 5 minutes
                        3. 📨 Check your Telegram {user_telegram or 'messages'}
                        4. 🔓 Enter password above to unlock access
                        
                        **⏱️ Expected response time: 2-5 minutes**
                        """)
                        
                        st.balloons()
                    else:
                        st.error(f"❌ Failed to send to Telegram: {message}")
                        st.warning("Please contact admin directly via the button below")
                        
                        # Save metadata for manual processing
                        metadata_file = f"{PAYMENT_PROOFS_DIR}/payment_{timestamp}_{random_id}.txt"
                        with open(metadata_file, "w") as f:
                            f.write(f"Submission Time: {datetime.now()}\n")
                            f.write(f"Transaction ID: {tx_id or 'Not provided'}\n")
                            f.write(f"Telegram: {user_telegram or 'Not provided'}\n")
                            f.write(f"Email: {user_email or 'Not provided'}\n")
                            f.write(f"Status: Pending Manual Verification\n")
                        
                except Exception as e:
                    st.error(f"Error processing your request: {str(e)}")
        else:
            st.warning("Please upload a screenshot of your payment")

# ===== PAYMENT CONFIGURATION =====
YOUR_WALLET = os.getenv("YOUR_WALLET", "0x87ea9fc331bbe75fdae07f291046920b878e1367")  # Your BEP20 wallet
ACCESS_DURATION = int(os.getenv("ACCESS_DURATION", 2592000))  # 30 days in seconds
ACCESS_PRICE_USDT = 25  # $25 USDT


# ===== PASSWORD MANAGEMENT SYSTEM =====
class PasswordManager:
    def __init__(self):
        self.valid_passwords = {}
        self.used_passwords = set()
        
    def generate_password(self, days=30):
        """Generate a unique password for new user"""
        # Create a random password (8 characters hex)
        password = secrets.token_hex(4).upper()  # e.g., "A1B2C3D4"
        
        # Store with expiry
        expiry = datetime.now() + timedelta(days=days)
        self.valid_passwords[password] = {
            'created': datetime.now(),
            'expiry': expiry,
            'used': False
        }
        return password
    
    def verify_password(self, password):
        """Verify if password is valid and not used"""
        if password in self.valid_passwords:
            if not self.valid_passwords[password]['used']:
                if datetime.now() <= self.valid_passwords[password]['expiry']:
                    # Mark as used
                    self.valid_passwords[password]['used'] = True
                    return True, "Valid password"
                else:
                    return False, "Password expired"
            else:
                return False, "Password already used"
        return False, "Invalid password"
    
    def list_active_passwords(self):
        """Show all active unused passwords (for admin)"""
        active = []
        for pwd, data in self.valid_passwords.items():
            if not data['used'] and datetime.now() <= data['expiry']:
                active.append({
                    'password': pwd,
                    'expires': data['expiry'].strftime('%Y-%m-%d')
                })
        return active

# Page configuration
st.set_page_config(
    page_title="Futures Big Bot",
    page_icon="favicon.png",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .signal-long {
        background-color: #d4edda;
        padding: 10px;
        border-radius: 5px;
        color: #155724;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
    }
    .signal-short {
        background-color: #f8d7da;
        padding: 10px;
        border-radius: 5px;
        color: #721c24;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
    }
    .payment-box {
        background: linear-gradient(135deg, #F3BA2F 0%, #F0B90B 100%);
        padding: 30px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .access-badge {
        background-color: #28a745;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .wallet-address {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        font-family: monospace;
        font-size: 16px;
        border: 2px dashed #F3BA2F;
        margin: 10px 0;
        word-break: break-all;
    }
    .step-box {
        background-color: #e9ecef;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #F3BA2F;
    }
    .copy-button {
        background-color: #F3BA2F;
        color: black;
        padding: 10px;
        border: none;
        border-radius: 5px;
        width: 100%;
        cursor: pointer;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .copy-button:hover {
        background-color: #e5a72f;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'signals' not in st.session_state:
    st.session_state.signals = []
if 'multi_signals' not in st.session_state:
    st.session_state.multi_signals = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()
if 'selected_coins' not in st.session_state:
    st.session_state.selected_coins = ["BTC/USDT", "ETH/USDT"]
if 'access_granted' not in st.session_state:
    st.session_state.access_granted = False
if 'access_expiry' not in st.session_state:
    st.session_state.access_expiry = None
if 'payment_verified' not in st.session_state:
    st.session_state.payment_verified = False
if 'payment_address_copied' not in st.session_state:
    st.session_state.payment_address_copied = False
if 'password_manager' not in st.session_state:
    st.session_state.password_manager = PasswordManager()
    
    # Add some demo passwords (remove in production)
    st.session_state.password_manager.valid_passwords["DEMO123"] = {
        'created': datetime.now(),
        'expiry': datetime.now() + timedelta(days=30),
        'used': False
    }
    st.session_state.password_manager.valid_passwords["TEST456"] = {
        'created': datetime.now(),
        'expiry': datetime.now() + timedelta(days=30),
        'used': False
    }


class TradingSignalBot:
    """Trading signal bot with multiple data source fallbacks"""
    
    def __init__(self):
        self.data_sources = []
        self.current_source = 0
        self._init_data_sources()
    
    def _init_data_sources(self):
        """Initialize multiple data source options, skipping problematic exchanges"""
        self.data_sources = []
        
        # Option 1: Bybit (usually works globally)
        try:
            bybit = ccxt.bybit({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            bybit.load_markets()
            self.data_sources.append(('bybit', bybit))
        except Exception as e:
            pass
        
        # Option 2: Kraken
        try:
            kraken = ccxt.kraken({'enableRateLimit': True})
            kraken.load_markets()
            self.data_sources.append(('kraken', kraken))
        except:
            pass
        
        # Option 3: KuCoin
        try:
            kucoin = ccxt.kucoin({'enableRateLimit': True})
            kucoin.load_markets()
            self.data_sources.append(('kucoin', kucoin))
        except:
            pass
        
        # Option 4: OKX
        try:
            okx = ccxt.okx({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            okx.load_markets()
            self.data_sources.append(('okx', okx))
        except:
            pass
    
    def _format_symbol(self, symbol, source_name):
        """Format symbol based on exchange requirements"""
        try:
            base, quote = symbol.split('/')
            
            if source_name == 'bybit':
                return f"{base}{quote}"
            elif source_name == 'kraken':
                if base == 'BTC':
                    base = 'XBT'
                return f"{base}/{quote}"
            elif source_name in ['kucoin', 'okx']:
                return f"{base}-{quote}"
            else:
                return symbol
        except:
            return symbol
    
    def fetch_data(self, symbol='BTC/USDT', timeframe='1h', limit=100):
        """Try multiple data sources until one works"""
        
        if not self.data_sources:
            st.error("No data sources available.")
            return None
        
        timeframe_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w'
        }
        
        for source_name, exchange in self.data_sources:
            try:
                formatted_symbol = self._format_symbol(symbol, source_name)
                tf = timeframe_map.get(timeframe, timeframe)
                
                ohlcv = exchange.fetch_ohlcv(formatted_symbol, tf, limit=limit)
                
                if ohlcv and len(ohlcv) > 0:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)
                    
                    st.session_state['data_source'] = source_name
                    st.caption(f"📡 Data from: {source_name}")
                    return df
                    
            except Exception as e:
                continue
        
        st.error("⚠️ Could not fetch market data. Please try again.")
        return None
    
    def calculate_indicators(self, df):
        """Calculate technical indicators"""
        if df is None or len(df) < 20:
            return df
        
        try:
            df['ema_9'] = ta.trend.ema_indicator(df['close'], window=9)
            df['ema_21'] = ta.trend.ema_indicator(df['close'], window=21)
            df['ema_50'] = ta.trend.ema_indicator(df['close'], window=50)
            df['rsi'] = ta.momentum.rsi(df['close'], window=14)
            
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_lower'] = bb.bollinger_lband()
            
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            
        except Exception as e:
            st.warning(f"Error calculating indicators: {e}")
        
        return df
    
    def generate_signal(self, df):
        """Generate trading signal based on multiple factors"""
        if df is None or len(df) < 50:
            return None
        
        try:
            latest = df.iloc[-1]
            
            bullish_score = 0
            bearish_score = 0
            reasons = []
            
            # EMA trend
            if not pd.isna(latest.get('ema_9', np.nan)) and not pd.isna(latest.get('ema_21', np.nan)):
                if latest['ema_9'] > latest['ema_21']:
                    bullish_score += 3
                    reasons.append("📈 Bullish EMA trend")
                else:
                    bearish_score += 3
                    reasons.append("📉 Bearish EMA trend")
            
            # RSI
            if not pd.isna(latest.get('rsi', np.nan)):
                if latest['rsi'] < 30:
                    bullish_score += 4
                    reasons.append(f"💪 Oversold RSI: {latest['rsi']:.1f}")
                elif latest['rsi'] > 70:
                    bearish_score += 4
                    reasons.append(f"⚠️ Overbought RSI: {latest['rsi']:.1f}")
                elif latest['rsi'] > 50:
                    bullish_score += 1
                    reasons.append(f"📊 Bullish RSI: {latest['rsi']:.1f}")
                else:
                    bearish_score += 1
                    reasons.append(f"📊 Bearish RSI: {latest['rsi']:.1f}")
            
            # Determine signal
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
            
            # Calculate TP/SL
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
                'volume': latest['volume'],
                'timestamp': datetime.now(),
                'volatility': f"{volatility:.2f}%"
            }
            
        except Exception as e:
            st.error(f"Error generating signal: {e}")
            return None

# Initialize bot
@st.cache_resource
def get_bot():
    bot = TradingSignalBot()
    # Store available sources in session state for debugging
    st.session_state.available_sources = [name for name, _ in bot.data_sources]
    return bot

bot = get_bot()

# Create a directory for payment proofs if it doesn't exist
PAYMENT_PROOFS_DIR = "payment_proofs"
os.makedirs(PAYMENT_PROOFS_DIR, exist_ok=True)

# ===== PASSWORD-BASED ACCESS SYSTEM =====
# Check access expiry
if st.session_state.access_expiry:
    if datetime.now() > st.session_state.access_expiry:
        st.session_state.access_granted = False
        st.session_state.access_expiry = None
        st.session_state.payment_verified = False

# Create two columns only if access NOT granted
if not st.session_state.access_granted:
    col_left, col_right = st.columns([1, 2])
else:
    # If access granted, use full width for content
    col_left, col_right = None, st.container()

# LEFT COLUMN - Payment Stuff (Only shown when NOT granted)
if not st.session_state.access_granted and col_left:
    with col_left:
        st.image("favicon.png", width=50)
        st.markdown("### 🔐 BEP20 USDT Access")
        
        # Show current status
        if st.session_state.access_granted and st.session_state.access_expiry:
            days_left = (st.session_state.access_expiry - datetime.now()).days
            hours_left = ((st.session_state.access_expiry - datetime.now()).seconds // 3600)
            
            st.markdown(f"""
            <div style="background-color: #d4edda; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <span class="access-badge">✅ ACTIVE</span>
                <p style="margin-top: 10px; margin-bottom: 0;">
                <strong>Expires:</strong> {st.session_state.access_expiry.strftime('%Y-%m-%d %H:%M')}<br>
                <strong>Time left:</strong> {days_left} days {hours_left} hours
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #f8d7da; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <span style="background-color: #dc3545; color: white; padding: 5px 15px; border-radius: 20px;">🔒 LOCKED</span>
                <p style="margin-top: 10px; margin-bottom: 0;">Complete payment below for 30 days access</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Payment Section
        st.markdown("### 💰 Purchase Access - 25 USDT")
        
        st.markdown(f"""
        <div class="payment-box">
            <h2 style="margin: 0;">25 USDT</h2>
            <p style="margin: 5px 0;">BEP20 (Binance Smart Chain)</p>
            <p style="margin: 0;"><strong>30 Days Premium Access</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        # ===== FIXED COPY SECTION =====
        st.markdown("### 📋 Your Payment Address")
        
        # Method 1: st.code (easiest to copy)
        st.code(YOUR_WALLET, language="text")
        
        st.markdown("""
        **📋 Copy Instructions:**
        1. Click inside the code box above
        2. Press **Ctrl+A** (Windows) or **Cmd+A** (Mac)
        3. Press **Ctrl+C** (Windows) or **Cmd+C** (Mac)
        4. Paste into Binance app
        """)
        
        # Method 2: Text input (backup)
        st.text_input(
            "✏️ Backup copy field:", 
            value=YOUR_WALLET, 
            key="backup_copy",
            disabled=True,
            help="Select the text and press Ctrl+C to copy"
        )
        
        # Warning
        st.error("⚠️ Send exactly 25 USDT on BEP20 network")
        
        st.markdown("---")
        
        # QR Code (optional - using your image)
        with st.expander("📱 Show QR Code"):
            try:
                st.image(
                    "qr_code.jpeg",
                    caption="Scan with Binance app",
                    width=200
                )
                st.caption("Make sure you're sending 25 USDT on BEP20 network")
                st.markdown("""
                **Binance App Users:**  
                1. Open Binance app
                2. Go to Wallet → Transfer → Send
                3. Tap the scan icon
                4. Scan the QR code above
                """)
            except:
                st.warning("QR code image not found. Please use the wallet address above.")
        
        st.markdown("---")
        
        # ===== PASSWORD ACCESS SYSTEM =====
        st.markdown("### 🔑 Enter Access Password")
        
        # Password input (hidden characters)
        access_password = st.text_input(
            "Password:", 
            type="password",
            placeholder="Enter your 30-day access password",
            key="access_password_input",
            help="After sending payment, you'll receive a password"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔓 Unlock Access", use_container_width=True, type="primary"):
                if access_password:
                    # Admin override password (change this!)
                    admin_password = "password.me"
                    
                    if access_password == admin_password:
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
        



# RIGHT COLUMN - Payment Proof Upload (Only shown when NOT granted)
if not st.session_state.access_granted and col_right:
    with col_right:
        st.markdown("### 📤 Submit Payment Proof")
        
        # File uploader for screenshot
        uploaded_file = st.file_uploader(
            "Upload payment screenshot", 
            type=['png', 'jpg', 'jpeg'],
            help="Take a screenshot of your successful 25 USDT payment and upload it here"
        )
        
        # Submit button
        if st.button("📨 Submit Payment Proof", use_container_width=True, type="primary"):
            if uploaded_file is not None:
                with st.spinner("Sending payment proof to admin..."):
                    try:
                        # Generate unique filename
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        random_id = secrets.token_hex(4)
                        filename = f"{PAYMENT_PROOFS_DIR}/payment_{timestamp}_{random_id}.png"
                        
                        # Save the file locally
                        with open(filename, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Prepare caption for Telegram
                        caption = f"🔔 *NEW PAYMENT PROOF RECEIVED*\n\n"
                        caption += f"⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        caption += f"💰 *Amount:* 25 USDT (BEP20)\n"
                        caption += f"🔑 *TXID:* {tx_id or 'Not provided'}\n"
                        caption += f"📱 *Telegram:* {user_telegram or 'Not provided'}\n"
                        caption += f"📧 *Email:* {user_email or 'Not provided'}\n"
                        caption += f"🆔 *File:* {filename}\n\n"
                        caption += f"✅ *Action:* Reply with password or use admin panel"
                        
                        # Send to Telegram
                        success, message = send_telegram_photo(filename, caption)
                        
                        if success:
                            st.success("✅ Payment proof sent to admin! You'll receive your password soon.")
                            
                            # Show next steps
                            st.info(f"""
                            **📱 Next steps:**
                            1. ✅ Admin received your payment proof
                            2. 🔐 Password will be sent within 5 minutes
                            3. 📨 Check your Telegram {user_telegram or 'messages'}
                            4. 🔓 Enter password above to unlock access
                            
                            **⏱️ Expected response time: 2-5 minutes**
                            """)
                            
                            st.balloons()
                        else:
                            st.error(f"❌ Failed to send to Telegram: {message}")
                            st.warning("Please contact admin directly via the button below")
                            
                            # Save metadata for manual processing
                            metadata_file = f"{PAYMENT_PROOFS_DIR}/payment_{timestamp}_{random_id}.txt"
                            with open(metadata_file, "w") as f:
                                f.write(f"Submission Time: {datetime.now()}\n")
                                f.write(f"Transaction ID: {tx_id or 'Not provided'}\n")
                                f.write(f"Telegram: {user_telegram or 'Not provided'}\n")
                                f.write(f"Email: {user_email or 'Not provided'}\n")
                                f.write(f"Status: Pending Manual Verification\n")
                            
                    except Exception as e:
                        st.error(f"Error processing your request: {str(e)}")
            else:
                st.warning("Please upload a screenshot of your payment")
        # Direct contact button (backup)
        st.markdown("""
        <a href="https://t.me/vubajanja" target="_blank">
            <button style="background-color: #0088cc; color: white; padding: 10px; border: none; border-radius: 5px; width: 100%; cursor: pointer; margin-top: 10px;">
                📱 Contact Admin Directly
            </button>
        </a>
        """, unsafe_allow_html=True)        
# ===== PASSWORD-BASED ACCESS SYSTEM =====
# Check access expiry
if st.session_state.access_expiry:
    if datetime.now() > st.session_state.access_expiry:
        st.session_state.access_granted = False
        st.session_state.access_expiry = None
        st.session_state.payment_verified = False

# Create two columns only if access NOT granted
if not st.session_state.access_granted:
    col_left, col_right = st.columns([1, 2])
else:
    # If access granted, use full width for content
    col_left, col_right = None, st.container()



# RIGHT COLUMN - Content (Payment stuff hidden after login)
content_container = col_right if not st.session_state.access_granted else st.container()

with content_container:
    if st.session_state.access_granted:
        # PAID USERS - Show signals (FULL WIDTH, NO PAYMENT STUFF)
        st.title("🤖 AI Trading Signals - Premium Access")
        
        # SINGLE COIN SEARCH - Simplified
        st.markdown("### 🔍 Search Single Coin")
        
        # Coin selection dropdown (single selection)
        available_coins = [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", 
            "ADA/USDT", "XRP/USDT", "DOGE/USDT", "DOT/USDT",
            "LINK/USDT", "AVAX/USDT", "MATIC/USDT"
        ]
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            selected_coin = st.selectbox(
                "Select Coin",
                available_coins,
                index=0,
                key="coin_selector_single"
            )
        
        with col2:
            timeframe = st.selectbox(
                "Timeframe",
                ["15m", "1h", "4h", "1d"],
                index=1,
                key="timeframe_selector_single"
            )
        
        with col3:
            st.write("")  # Spacing
            st.write("")  # Spacing
            search_button = st.button("🔍 Search", use_container_width=True, type="primary", key="search_button")
        
        # Auto-refresh option
        auto_refresh = st.checkbox("🔄 Auto-refresh (30s)", key="auto_refresh_single")
        
        # Generate signal for single coin
        if search_button:
            with st.spinner(f"🔍 Analyzing {selected_coin}..."):
                df = bot.fetch_data(selected_coin, timeframe)
                if df is not None:
                    df = bot.calculate_indicators(df)
                    signal = bot.generate_signal(df)
                    if signal:
                        signal['coin'] = selected_coin
                        st.session_state.multi_signals = [signal]  # Replace with single signal
                        st.session_state.last_update = datetime.now()
        
        # Display single signal
        if st.session_state.multi_signals:
            signal = st.session_state.multi_signals[0]  # Get the single signal
            
            # Signal header
            if signal['signal'] == "LONG":
                st.markdown(f'<div class="signal-long">📈 {signal["coin"]} - LONG SIGNAL (Confidence: {signal["confidence"]}%)</div>', unsafe_allow_html=True)
            elif signal['signal'] == "SHORT":
                st.markdown(f'<div class="signal-short">📉 {signal["coin"]} - SHORT SIGNAL (Confidence: {signal["confidence"]}%)</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="signal-neutral">⏸️ {signal["coin"]} - NEUTRAL (Confidence: {signal["confidence"]}%)</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Key metrics in columns
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
            
            # Trading details in columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("📊 Entry")
                st.write(f"**Price:** ${signal['current_price']:,.2f}")
            
            with col2:
                st.subheader("🛑 Stop Loss")
                if signal.get('stop_loss'):
                    st.write(f"**Price:** ${signal['stop_loss']:,.2f}")
                    if signal['signal'] == "LONG":
                        distance = ((signal['current_price'] - signal['stop_loss']) / signal['current_price']) * 100
                        st.write(f"**Distance:** {distance:.2f}% 🔴")
                    elif signal['signal'] == "SHORT":
                        distance = ((signal['stop_loss'] - signal['current_price']) / signal['current_price']) * 100
                        st.write(f"**Distance:** {distance:.2f}% 🔴")
                else:
                    st.write("**Price:** N/A")
            
            with col3:
                st.subheader("🎯 Take Profit")
                if signal.get('take_profit'):
                    st.write(f"**Price:** ${signal['take_profit']:,.2f}")
                    if signal['signal'] == "LONG":
                        distance = ((signal['take_profit'] - signal['current_price']) / signal['current_price']) * 100
                        st.write(f"**Distance:** +{distance:.2f}% ✅")
                    elif signal['signal'] == "SHORT":
                        distance = ((signal['current_price'] - signal['take_profit']) / signal['current_price']) * 100
                        st.write(f"**Distance:** +{distance:.2f}% ✅")
                else:
                    st.write("**Price:** N/A")
            
            st.markdown("---")
            
            # Risk/Reward
            if signal.get('risk_reward_ratio'):
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📈 Risk/Reward")
                    st.write(f"**Ratio:** 1:{signal['risk_reward_ratio']:.2f}")
                    
                    if signal['risk_reward_ratio'] >= 2:
                        st.success("✅ Good risk/reward")
                    elif signal['risk_reward_ratio'] >= 1.5:
                        st.warning("⚠️ Acceptable risk/reward")
                    else:
                        st.error("❌ Poor risk/reward")
            
            # Analysis reasons
            st.subheader("🔍 Analysis Reasons")
            for reason in signal['reasons']:
                st.write(f"• {reason}")
            
            st.markdown("---")
            
            # Price chart
            st.subheader("📈 Price Chart")
            
            # Fetch data for chart
            df = bot.fetch_data(signal['coin'], timeframe, limit=100)
            if df is not None:
                df = bot.calculate_indicators(df)
                
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.6, 0.2, 0.2]
                )
                
                # Candlestick chart
                fig.add_trace(
                    go.Candlestick(
                        x=df.index,
                        open=df['open'],
                        high=df['high'],
                        low=df['low'],
                        close=df['close'],
                        name='Price'
                    ),
                    row=1, col=1
                )
                
                # Add EMAs
                fig.add_trace(
                    go.Scatter(x=df.index, y=df['ema_9'], name='EMA 9', line=dict(color='blue', width=1)),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(x=df.index, y=df['ema_21'], name='EMA 21', line=dict(color='orange', width=1)),
                    row=1, col=1
                )
                
                # Add Bollinger Bands
                fig.add_trace(
                    go.Scatter(x=df.index, y=df['bb_upper'], name='BB Upper', line=dict(color='gray', width=1, dash='dash')),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(x=df.index, y=df['bb_lower'], name='BB Lower', line=dict(color='gray', width=1, dash='dash')),
                    row=1, col=1
                )
                
                # Volume bars
                colors = ['red' if row['open'] > row['close'] else 'green' for index, row in df.iterrows()]
                fig.add_trace(
                    go.Bar(x=df.index, y=df['volume'], name='Volume', marker_color=colors),
                    row=2, col=1
                )
                
                # RSI
                fig.add_trace(
                    go.Scatter(x=df.index, y=df['rsi'], name='RSI', line=dict(color='purple')),
                    row=3, col=1
                )
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                
                fig.update_layout(
                    height=800,
                    xaxis_rangeslider_visible=False,
                    showlegend=True,
                    template='plotly_dark'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Last update time
            st.caption(f"Last updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Auto-refresh
            if auto_refresh:
                time.sleep(30)
                st.rerun()
        
        
        # Sample preview
        st.markdown("---")
        st.subheader("📊 Sample Signal Preview")
        st.caption("Complete payment on the left to unlock real signals")
        
        preview_data = pd.DataFrame({
            'Coin': ['BTC/USDT', 'ETH/USDT'],
            'Signal': ['LONG', 'SHORT'],
            'Confidence': ['87%', '76%'],
            'Entry': ['$65,432', '$3,456'],
            'R:R': ['1:2.4', '1:1.8']
        })
        st.dataframe(preview_data, use_container_width=True)

# Final footer
st.markdown("---")
st.caption("© 2024 Futures Big Bot. All rights reserved.")
st.caption("🔧 Admin panel is always available at help")
