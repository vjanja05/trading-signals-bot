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

# Load environment variables
load_dotenv()

# ===== TELEGRAM IMAGE SENDER FUNCTION - DEFINED FIRST =====
def send_telegram_photo(photo_path, caption=""):
    """Send photo to admin Telegram"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            print("Telegram not configured - missing tokens")  # This will show in console
            return False, "Telegram not configured. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
            response = requests.post(url, files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            return True, "Photo sent successfully"
        else:
            return False, f"Telegram error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Error sending to Telegram: {str(e)}"

# ===== PAYMENT CONFIGURATION =====
YOUR_WALLET = os.getenv("YOUR_WALLET", "0x87ea9fc331bbe75fdae07f291046920b878e1367")  # Your BEP20 wallet
ACCESS_DURATION = int(os.getenv("ACCESS_DURATION", 2592000))  # 30 days in seconds
ACCESS_PRICE_USDT = 25  # $25 USDT

# Create directory for payment proofs
PAYMENT_PROOFS_DIR = "payment_proofs"
os.makedirs(PAYMENT_PROOFS_DIR, exist_ok=True)


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
    """Trading signal bot"""
    
    def __init__(self):
        # List of alternative Binance hosts that might work
        self.hosts = [
            'https://data-api.binance.vision',
            'https://api1.binance.com',
            'https://api2.binance.com',
            'https://api3.binance.com',
            'https://api.binance.com'
          ]
      self.current_host_index = 0
      self._init_exchange()
    
    def _init_exchange(self):
      """Initialize exchange with current host"""
     self.exchange = ccxt.binance({
         'enableRateLimit': True,
         'options': {'defaultType': 'future'},
         'urls': {
             'api': {
                 'public': f'{self.hosts[self.current_host_index]}/api/v3'
             }
         }
     })

    def fetch_data(self, symbol='BTC/USDT', timeframe='1h', limit=100):
       """Fetch with fallback to different hosts"""
      for attempt in range(len(self.hosts)):
          try:
             self._init_exchange()
             ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
             df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
             df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
             df.set_index('timestamp', inplace=True)
             return df
         except Exception as e:
             if "451" in str(e) and attempt < len(self.hosts) - 1:
                 self.current_host_index = (self.current_host_index + 1) % len(self.hosts)
                 continue
             else:
                 st.error(f"Error fetching data from all hosts: {e}")
                 return None
    
    def calculate_indicators(self, df):
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
        return df
    
    def generate_signal(self, df):
        if df is None or len(df) < 50:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        bullish_score = 0
        bearish_score = 0
        reasons = []
        
        # EMA trend
        if latest['ema_9'] > latest['ema_21']:
            bullish_score += 3
            reasons.append("📈 Bullish EMA trend")
        else:
            bearish_score += 3
            reasons.append("📉 Bearish EMA trend")
        
        # RSI
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
        
        # MACD
        if latest['macd'] > latest['macd_signal']:
            bullish_score += 2
            reasons.append("🟢 MACD bullish")
        else:
            bearish_score += 2
            reasons.append("🔴 MACD bearish")
        
        # Bollinger Bands
        if latest['close'] < latest['bb_lower']:
            bullish_score += 3
            reasons.append("📉 Price below lower BB")
        elif latest['close'] > latest['bb_upper']:
            bearish_score += 3
            reasons.append("📈 Price above upper BB")
        
        # Volume
        volume_sma = df['volume'].rolling(window=20).mean().iloc[-1]
        if latest['volume'] > volume_sma * 1.5:
            reasons.append("📊 High volume confirmation")
            if bullish_score > bearish_score:
                bullish_score += 2
            else:
                bearish_score += 2
        
        # Determine signal
        total_score = bullish_score - bearish_score
        
        if total_score >= 3:
            signal = "LONG"
            confidence = min(50 + (total_score * 5), 95)
        elif total_score <= -3:
            signal = "SHORT"
            confidence = min(50 + (abs(total_score) * 5), 95)
        else:
            if latest['rsi'] > 50:
                signal = "LONG"
                confidence = 55
            else:
                signal = "SHORT"
                confidence = 55
        
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
        else:
            stop_loss = current_price * (1 + sl_percent)
            take_profit = current_price * (1 - tp_percent)
        
        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
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
            'rsi': latest['rsi'],
            'volume': latest['volume'],
            'timestamp': datetime.now(),
            'volatility': f"{volatility:.2f}%"
        }

# Initialize bot
@st.cache_resource
def get_bot():
    return TradingSignalBot()

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

# Create two columns - Payment/Status on left, Content on right
col_left, col_right = st.columns([1, 2])

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
    
    # Direct contact button (backup)
    st.markdown("""
    <a href="https://t.me/vubajanja" target="_blank">
        <button style="background-color: #0088cc; color: white; padding: 10px; border: none; border-radius: 5px; width: 100%; cursor: pointer; margin-top: 10px;">
            📱 Contact Admin Directly
        </button>
    </a>
    """, unsafe_allow_html=True)
# ===== ADMIN PANEL WITH PAYMENT PROOFS VIEWER =====
with st.expander("👑 Admin Panel - Payment Proofs"):
    admin_auth = st.text_input("Admin Password:", type="password", key="admin_proofs_auth")
    
    if admin_auth == "ADMIN123":  # Change this to your admin password
        st.success("✅ Admin authenticated")
        
        tab1, tab2, tab3 = st.tabs(["📂 Pending Proofs", "🔑 Generate Password", "✅ Grant Access"])
        
        with tab1:
            # Show pending payment proofs
            if os.path.exists(PAYMENT_PROOFS_DIR):
                files = os.listdir(PAYMENT_PROOFS_DIR)
                proof_files = [f for f in files if f.endswith('.png') or f.endswith('.jpg') or f.endswith('.jpeg')]
                
                if proof_files:
                    st.write(f"**📊 {len(proof_files)} pending verifications**")
                    
                    for file in sorted(proof_files, reverse=True)[:10]:  # Show latest 10
                        with st.container():
                            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                            
                            with col1:
                                st.write(f"📄 {file}")
                            
                            with col2:
                                # View button
                                if st.button(f"👁️ View", key=f"view_{file}"):
                                    image_path = os.path.join(PAYMENT_PROOFS_DIR, file)
                                    st.image(image_path, caption=file, width=300)
                            
                            with col3:
                                # Check for metadata
                                meta_file = file.replace('.png', '.txt').replace('.jpg', '.txt').replace('.jpeg', '.txt')
                                if os.path.exists(os.path.join(PAYMENT_PROOFS_DIR, meta_file)):
                                    if st.button(f"📋 Info", key=f"info_{file}"):
                                        with open(os.path.join(PAYMENT_PROOFS_DIR, meta_file), 'r') as f:
                                            content = f.read()
                                        st.text(content)
                            
                            with col4:
                                # Mark as verified
                                if st.button(f"✅ Verify", key=f"verify_{file}"):
                                    st.session_state.current_verifying = file
                                    st.rerun()
                            
                            st.divider()
                else:
                    st.info("No pending payment proofs")
        
        with tab2:
            st.subheader("🔑 Generate Access Password")
            days = st.number_input("Access days:", min_value=1, max_value=365, value=30, key="admin_days")
            if st.button("🎲 Generate New Password", key="admin_generate"):
                new_pwd = st.session_state.password_manager.generate_password(days)
                st.success(f"New password generated:")
                st.code(new_pwd, language="text")
                st.caption(f"Valid for {days} days - expires {datetime.now() + timedelta(days=days)}")
        
        with tab3:
            st.subheader("✅ Manually Grant Access")
            if st.button("🔓 Grant Access to Current User", key="admin_grant"):
                st.session_state.access_granted = True
                st.session_state.access_expiry = datetime.now() + timedelta(seconds=ACCESS_DURATION)
                st.success("Access granted manually!")
                st.rerun()
    
    # Quick guide for finding TXID
    with st.expander("❓ Where to find Transaction ID?"):
        st.markdown("""
        **In Binance App:**
        1. Go to **Wallet** → **Spot** → **Transaction History**
        2. Find your USDT transfer
        3. Tap on it to see details
        4. Copy the **TxID** (long string starting with 0x...)
        
        **In MetaMask:**
        1. Click on the transaction
        2. Click **View on BSCScan**
        3. Copy the Transaction Hash from the URL
        """)

# ===== MAIN CONTENT (Only for paid users) =====
with col_right:
    if st.session_state.access_granted:
        st.title("AI Trading Signals")
        
        # Trading controls
        col1, col2, col3 = st.columns(3)
        
        with col1:
            available_coins = [
                "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", 
                "ADA/USDT", "XRP/USDT", "DOGE/USDT", "DOT/USDT",
                "LINK/USDT", "AVAX/USDT", "MATIC/USDT"
            ]
            selected_coins = st.multiselect(
                "📊 Select Coins",
                available_coins,
                default=["BTC/USDT", "ETH/USDT"],
                key="coin_selector"
            )
            st.session_state.selected_coins = selected_coins
        
        with col2:
            timeframe = st.selectbox(
                "⏱️ Timeframe",
                ["15m", "1h", "4h", "1d"],
                index=1,
                key="timeframe_selector"
            )
        
        with col3:
            st.write("")  # Spacing
            st.write("")  # Spacing
            auto_refresh = st.checkbox("🔄 Auto-refresh (30s)", key="auto_refresh_checkbox")
            scan_button = st.button("🚀 Generate Signals", use_container_width=True, type="primary", key="scan_button")
        
        # Generate signals
        if scan_button and selected_coins:
            with st.spinner(f"🔍 Analyzing {len(selected_coins)} coins..."):
                all_signals = []
                progress_bar = st.progress(0)
                
                for i, coin in enumerate(selected_coins):
                    progress_bar.progress((i + 1) / len(selected_coins))
                    df = bot.fetch_data(coin, timeframe)
                    if df is not None:
                        df = bot.calculate_indicators(df)
                        signal = bot.generate_signal(df)
                        if signal:
                            signal['coin'] = coin
                            all_signals.append(signal)
                
                all_signals.sort(key=lambda x: x['confidence'], reverse=True)
                st.session_state.multi_signals = all_signals
                st.session_state.last_update = datetime.now()
        
        # Display signals
        if st.session_state.multi_signals:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Coins Scanned", len(st.session_state.multi_signals))
            with col2:
                bullish = sum(1 for s in st.session_state.multi_signals if s['signal'] == "LONG")
                st.metric("🟢 Bullish", bullish)
            with col3:
                bearish = sum(1 for s in st.session_state.multi_signals if s['signal'] == "SHORT")
                st.metric("🔴 Bearish", bearish)
            with col4:
                best_conf = max([s['confidence'] for s in st.session_state.multi_signals])
                st.metric("⭐ Best Confidence", f"{best_conf}%")
            
            st.markdown("---")
            
            # Top signals table
            signal_data = []
            for s in st.session_state.multi_signals[:10]:
                signal_data.append({
                    "Coin": s['coin'],
                    "Signal": s['signal'],
                    "Confidence": f"{s['confidence']}%",
                    "Entry": f"${s['current_price']:,.2f}",
                    "Stop Loss": f"${s['stop_loss']:,.2f}",
                    "Take Profit": f"${s['take_profit']:,.2f}",
                    "R:R": f"1:{s['risk_reward_ratio']:.2f}"
                })
            
            signal_df = pd.DataFrame(signal_data)
            
            # Color code signals
            def color_signal(val):
                if val == "LONG":
                    return 'background-color: #d4edda; color: #155724'
                elif val == "SHORT":
                    return 'background-color: #f8d7da; color: #721c24'
                return ''
            
            styled_df = signal_df.style.applymap(color_signal, subset=['Signal'])
            st.dataframe(styled_df, use_container_width=True, height=400)
            
            # Best signal details
            if st.session_state.multi_signals:
                best = st.session_state.multi_signals[0]
                st.markdown("---")
                st.subheader(f"🏆 Best Signal: {best['coin']}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Signal:** {best['signal']}")
                    st.info(f"**Confidence:** {best['confidence']}%")
                with col2:
                    st.info(f"**Entry:** ${best['current_price']:,.2f}")
                    st.info(f"**Stop Loss:** ${best['stop_loss']:,.2f}")
                with col3:
                    st.info(f"**Take Profit:** ${best['take_profit']:,.2f}")
                    st.info(f"**Risk/Reward:** 1:{best['risk_reward_ratio']:.2f}")
                
                with st.expander("📊 Analysis Details"):
                    for reason in best['reasons']:
                        st.write(f"• {reason}")
            
            # Last update time
            st.caption(f"Last updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        
        else:
            st.info("👈 Select coins and click 'Generate Signals' to start")
        
        # Auto-refresh
        if auto_refresh and st.session_state.multi_signals:
            time.sleep(30)
            st.rerun()
    
    else:
        # FREE USERS - Show preview
        st.title("🤖 Premium Trading Signals")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            ### 🚀 Get AI-Powered Trading Signals
            
            **✨ What you get:**
            - 📊 Real-time signals for 10+ trading pairs
            - 🎯 Entry, Stop Loss, and Take Profit levels
            - 📈 Multiple timeframes (15m, 1h, 4h, 1d)
            - 🔍 Detailed AI analysis with reasoning
            - 💰 Risk/Reward ratios for each trade
            - 🏆 Top signals ranked by confidence
            
            **💎 Price: 25 USDT (BEP20) for 30 days access**
            """)
        
        with col2:
            st.markdown(f"""
            <div class="payment-box">
                <h2>💰 Price</h2>
                <h1>25 USDT</h1>
                <p>BEP20 Network</p>
                <hr>
                <p><strong>30 Days Access</strong></p>
                <p>⚡ Instant activation with password</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Sample preview
        st.markdown("---")
        st.subheader("📊 Sample Signal Preview")
        st.caption("Complete payment on the left to unlock real signals")
        
        preview_data = pd.DataFrame({
            'Coin': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT'],
            'Signal': ['LONG', 'SHORT', 'LONG', 'LONG'],
            'Confidence': ['87%', '76%', '82%', '79%'],
            'Entry': ['$65,432', '$3,456', '$612', '$145'],
            'Stop Loss': ['$64,123', '$3,525', '$600', '$142'],
            'Take Profit': ['$67,890', '$3,387', '$642', '$152'],
            'R:R': ['1:2.4', '1:1.8', '1:2.1', '1:2.0']
        })
        st.dataframe(preview_data, use_container_width=True)
        
        # Quick instructions
        with st.expander("📖 Quick Start Guide"):
            st.markdown("""
            1. **Copy** the wallet address from the left panel
            2. **Send 25 USDT** (BEP20) to that address from Binance
            3. **Contact us** on Telegram with proof of payment
            4. **Receive password** and enter it above
            5. **Click Unlock Access** - instant 30 days access!
            
            Need help? Contact us on Telegram: @vubajanja
            """)
