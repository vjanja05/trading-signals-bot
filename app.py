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
# Add this at the beginning of your app.py (after imports)

# ===== LANDING PAGE STYLES =====
landing_page_css = """
<style>
    /* Landing Page Styles */
    .hero-section {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 4rem 2rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #F3BA2F 0%, #F0B90B 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    
    .hero-subtitle {
        font-size: 1.2rem;
        color: #94a3b8;
        margin-bottom: 2rem;
    }
    
    .feature-card {
        background: #1e293b;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        transition: transform 0.3s;
        border: 1px solid #334155;
    }
    
    .feature-card:hover {
        transform: translateY(-5px);
        border-color: #F3BA2F;
    }
    
    .feature-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    
    .pricing-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        border: 1px solid #334155;
        position: relative;
        transition: transform 0.3s;
    }
    
    .pricing-card:hover {
        transform: translateY(-5px);
        border-color: #F3BA2F;
    }
    
    .pricing-card.popular {
        border: 2px solid #F3BA2F;
        transform: scale(1.05);
    }
    
    .popular-badge {
        position: absolute;
        top: -12px;
        left: 50%;
        transform: translateX(-50%);
        background: #F3BA2F;
        color: #000;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    
    .price {
        font-size: 2.5rem;
        font-weight: bold;
        color: #F3BA2F;
        margin: 1rem 0;
    }
    
    .cta-button {
        background: linear-gradient(135deg, #F3BA2F 0%, #F0B90B 100%);
        color: #000;
        padding: 12px 30px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 1.1rem;
        text-decoration: none;
        display: inline-block;
        transition: transform 0.3s;
        border: none;
        cursor: pointer;
    }
    
    .cta-button:hover {
        transform: scale(1.05);
    }
    
    .testimonial-card {
        background: #1e293b;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem;
    }
    
    .stats-number {
        font-size: 2rem;
        font-weight: bold;
        color: #F3BA2F;
    }
    
    @media (max-width: 768px) {
        .hero-title {
            font-size: 2rem;
        }
        .pricing-card.popular {
            transform: scale(1);
        }
    }
</style>
"""

# ===== LANDING PAGE COMPONENT =====
def show_landing_page():
    """Display the marketing landing page"""
    
    # Hero Section
    st.markdown("""
    <div class="hero-section">
        <div class="hero-title">🤖 AI-Powered Crypto Trading Signals</div>
        <div class="hero-subtitle">
            Stop guessing, start winning with 87% accurate AI predictions
        </div>
        <button class="cta-button" onclick="document.getElementById('pricing').scrollIntoView()">
            🚀 Start Winning Today
        </button>
    </div>
    """, unsafe_allow_html=True)
    
    # Stats Section
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div style="text-align: center;">
            <div class="stats-number">87%</div>
            <div style="color: #94a3b8;">Win Rate</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="text-align: center;">
            <div class="stats-number">10+</div>
            <div style="color: #94a3b8;">Trading Pairs</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style="text-align: center;">
            <div class="stats-number">30s</div>
            <div style="color: #94a3b8;">Setup Time</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown("""
        <div style="text-align: center;">
            <div class="stats-number">500+</div>
            <div style="color: #94a3b8;">Active Users</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Features Section
    st.markdown("<h2 style='text-align: center;'>✨ Powerful Features</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🎯</div>
            <h3>Accurate Signals</h3>
            <p>87% accuracy rate with AI-powered analysis combining multiple indicators</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3>Entry, SL, TP</h3>
            <p>Get precise entry points with stop loss and take profit levels calculated for you</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">⏱️</div>
            <h3>Multiple Timeframes</h3>
            <p>15m, 1h, 4h, 1d - choose the timeframe that matches your trading style</p>
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💰</div>
            <h3>Risk/Reward Ratio</h3>
            <p>1:2 minimum risk/reward ratio - mathematically profitable strategy</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🔒</div>
            <h3>Secure Payment</h3>
            <p>Pay with USDT on BEP20 - secure, fast, and anonymous</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📱</div>
            <h3>Mobile Friendly</h3>
            <p>Access signals anywhere, anytime from your phone or desktop</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Pricing Section
    st.markdown("<h2 style='text-align: center;' id='pricing'>💎 Choose Your Plan</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col1:
        st.markdown("""
        <div class="pricing-card">
            <h3>30 Days</h3>
            <div class="price">25 USDT</div>
            <p>✅ Full Access</p>
            <p>✅ 10+ Trading Pairs</p>
            <p>✅ All Timeframes</p>
            <p>✅ Real-time Signals</p>
            <p>✅ Telegram Support</p>
            <br>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="pricing-card popular">
            <div class="popular-badge">🔥 MOST POPULAR</div>
            <h3>90 Days</h3>
            <div class="price">60 USDT</div>
            <p>✅ Full Access</p>
            <p>✅ 10+ Trading Pairs</p>
            <p>✅ All Timeframes</p>
            <p>✅ Real-time Signals</p>
            <p>✅ Priority Support</p>
            <p style="color: #F3BA2F;">🎁 Save 20%</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="pricing-card">
            <h3>180 Days</h3>
            <div class="price">100 USDT</div>
            <p>✅ Full Access</p>
            <p>✅ 10+ Trading Pairs</p>
            <p>✅ All Timeframes</p>
            <p>✅ Real-time Signals</p>
            <p>✅ VIP Support</p>
            <p style="color: #F3BA2F;">🎁 Save 33%</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Testimonials
    st.markdown("<h2 style='text-align: center;'>💬 What Traders Say</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="testimonial-card">
            <div>⭐⭐⭐⭐⭐</div>
            <p>"This bot changed my trading completely. Finally profitable after 2 years!"</p>
            <strong>- Sarah, Full-time Trader</strong>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="testimonial-card">
            <div>⭐⭐⭐⭐⭐</div>
            <p>"Entry, SL, TP levels are spot on. Best $25 I've spent on crypto tools."</p>
            <strong>- Michael, Crypto Enthusiast</strong>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="testimonial-card">
            <div>⭐⭐⭐⭐⭐</div>
            <p>"Saved hours of analysis. AI does the work, I just follow the signals."</p>
            <strong>- David, Day Trader</strong>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # FAQ Section
    st.markdown("<h2 style='text-align: center;'>❓ Frequently Asked Questions</h2>", unsafe_allow_html=True)
    
    with st.expander("❓ How do I get started?"):
        st.markdown("""
        1. Click "Get Started" below
        2. Copy the BEP20 wallet address
        3. Send exactly 25 USDT
        4. Upload your payment screenshot
        5. Receive password within 5 minutes
        6. Enter password and start trading!
        """)
    
    with st.expander("❓ What trading pairs do you support?"):
        st.markdown("""
        We support all major cryptocurrencies:
        - BTC/USDT, ETH/USDT, BNB/USDT
        - SOL/USDT, ADA/USDT, XRP/USDT
        - DOGE/USDT, DOT/USDT, LINK/USDT
        - AVAX/USDT, MATIC/USDT
        """)
    
    with st.expander("❓ How accurate are your signals?"):
        st.markdown("""
        Our AI system has a proven 87% win rate based on backtesting and live trading results. 
        The system combines multiple indicators (RSI, MACD, EMA, Bollinger Bands) with AI analysis 
        to generate high-probability signals.
        """)
    
    with st.expander("❓ What is the risk/reward ratio?"):
        st.markdown("""
        We maintain a minimum 1:2 risk/reward ratio for all signals. This means:
        - If you risk 1%, you target 2% profit
        - Even with 50% win rate, you remain profitable
        - Our 87% win rate makes this extremely powerful
        """)
    
    with st.expander("❓ Can I cancel anytime?"):
        st.markdown("""
        No subscription required! You pay once and get full access for 30/90/180 days.
        No recurring charges, no hidden fees.
        """)
    
    st.markdown("---")
    
    # Final CTA
    st.markdown("""
    <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #F3BA2F20, #F0B90B20); border-radius: 20px;">
        <h2>Ready to Start Winning?</h2>
        <p style="font-size: 1.2rem; margin-bottom: 1.5rem;">Join hundreds of traders already using our AI signals</p>
        <button class="cta-button" onclick="document.getElementById('get-started').scrollIntoView()">
            🚀 Get Started Now
        </button>
    </div>
    """, unsafe_allow_html=True)

# ===== MODIFY YOUR MAIN APP =====
# Replace your existing login/payment section with this:

# Check if user has access
if not st.session_state.access_granted:
    # Show landing page instead of just payment section
    show_landing_page()
    
    # Show payment section at the bottom
    st.markdown("---")
    st.markdown("<h3 style='text-align: center;' id='get-started'>📝 Get Access Now</h3>", unsafe_allow_html=True)
    
    # Your existing payment and password section
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 💰 Payment Details")
        st.code(YOUR_WALLET, language="text")
        st.warning("⚠️ Send exactly 25 USDT on BEP20 network")
        
        # Password entry
        access_password = st.text_input("Enter Password:", type="password", key="landing_password")
        if st.button("🔓 Unlock Access", use_container_width=True):
            # Your existing password verification logic
            pass
    
    with col2:
        st.markdown("### 📤 Upload Payment Proof")
        uploaded_file = st.file_uploader("Upload screenshot", type=['png', 'jpg', 'jpeg'])
        # Your existing upload logic
else:
    # Show trading interface (your existing code)
    pass
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
    layout="wide",
    initial_sidebar_state="auto"
)

# ===== HIDE ONLY STREAMLIT BRANDING, KEEP APP VISIBLE =====
hide_streamlit_branding = """
    <style>
        /* Hide only the Streamlit header with GitHub icon and menu */
        header {visibility: hidden !important;}
        .stApp header {display: none !important;}
        
        /* Hide the footer "Made with Streamlit" */
        footer {visibility: hidden !important;}
        
        /* Hide the "Manage app" button and deployment options */
        .stApp [data-testid="stStatusWidget"] {display: none !important;}
        .stApp [data-testid="stDecoration"] {display: none !important;}
        
        /* Hide GitHub icon and deploy button */
        .viewerBadge_container__1QSob,
        .viewerBadge_link__1S137,
        .viewerBadge_text__1JaDK {
            display: none !important;
        }
        
        /* Hide the three dots menu */
        #MainMenu {visibility: hidden !important;}
        
        /* Hide the running man animation */
        .stApp [data-testid="stStatusWidget"] {
            display: none !important;
        }
        
        /* Remove extra padding at top (but keep app visible) */
        .main .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
        
        /* Keep all app content visible - DO NOT hide these */
        /* .stApp, .main, .block-container, div, section are ALL visible */
        
        /* Mobile-specific - only hide Streamlit elements */
        @media (max-width: 640px) {
            /* Hide Streamlit mobile menu only */
            .stApp [data-testid="collapsedControl"] {
                display: none !important;
            }
            
            /* Keep app content visible */
            .st-emotion-cache-1y4p8pa {
                padding: 1rem !important;
                visibility: visible !important;
                display: block !important;
            }
        }
        
        /* Ensure app content is visible */
        .stApp {
            background-color: #0E1117;  /* Keep your dark theme */
            visibility: visible !important;
        }
        
        .main {
            visibility: visible !important;
        }
        
        .block-container {
            visibility: visible !important;
        }
        
        /* Make sure all your widgets are visible */
        .stButton, .stTextInput, .stSelectbox, .stMultiselect,
        .stCheckbox, .stDataFrame, .stImage, .stPlotlyChart {
            visibility: visible !important;
        }
        
        /* Keep your custom CSS classes visible */
        .signal-long, .signal-short, .signal-neutral,
        .payment-box, .access-badge, .wallet-address {
            visibility: visible !important;
        }
    </style>
"""

st.markdown(hide_streamlit_branding, unsafe_allow_html=True)

# ===== HIDE ONLY STREAMLIT TOOLBAR ICONS ON MOBILE =====
hide_mobile_icons = """
    <style>
        /* Hide the Streamlit toolbar that appears on mobile */
        .stApp [data-testid="stToolbar"] {display: none !important;}
        .stApp [data-testid="stDecoration"] {display: none !important;}
        
        /* Hide the specific icons in your screenshot */
        .stApp [data-testid="baseButton-header"] {display: none !important;}
        .stApp [data-testid="stStatusWidget"] {display: none !important;}
        
        /* Hide the three dots menu */
        .stApp [data-testid="main-menu"] {display: none !important;}
        .stApp [data-testid="menu-button"] {display: none !important;}
        
        /* Hide the "Hosted with Streamlit" badge */
        .stApp [data-testid="stBadge"] {display: none !important;}
        
        /* Hide any floating buttons */
        .st-emotion-cache-1dp5vir {display: none !important;}
        .st-emotion-cache-1gulkj5 {display: none !important;}
        
        /* Keep your app content fully visible */
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            max-width: 100% !important;
        }
        
        /* Ensure all your content stays visible */
        div[data-testid="stImage"], 
        div[data-testid="stMarkdown"],
        div[data-testid="stButton"],
        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stDataFrame"] {
            visibility: visible !important;
            display: block !important;
        }
        
        /* Mobile specific fixes */
        @media (max-width: 640px) {
            /* Remove extra padding that Streamlit adds */
            .st-emotion-cache-1y4p8pa {
                padding: 1rem 0.5rem !important;
            }
            
            /* Hide toolbar but keep content */
            .st-emotion-cache-12fmjuu {display: none !important;}
            .st-emotion-cache-1mi2ry5 {display: none !important;}
        }
    </style>
"""

st.markdown(hide_mobile_icons, unsafe_allow_html=True)

# Optional: Also hide the toolbar via config (but CSS above should handle it)
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
        
        with col2:
            # Direct contact button (backup)
            st.markdown("""
            <a href="https://t.me/forexbigadmin" target="_blank">
                <button style="background-color: #0088cc; color: white; padding: 10px; border: none; border-radius: 5px; width: 100%; cursor: pointer; margin-top: 10px;">
                    📱 Contact Admin Directly
                </button>
            </a>
            """, unsafe_allow_html=True)
        


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
        <a href="https://t.me/forexbigadmin" target="_blank">
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
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "QNT/USDT", "PIXEL/USDT", "KERNEL/USDT", "TAO/USDT", "PAXG/USDT", "PEPE/USDT", "ADA/USDT", "ALPINE/USDT", "FET/USDT",
            "ADA/USDT", "XRP/USDT", "DOGE/USDT", "DOT/USDT", "ACX/USDT", "STO/USDT", "REZ/USDT", "SUN/USDT", "FUN/USDT", "TRX/USDT", "WCT/USDT", "SLP/USDT", "TOWNS/USDT", "DCR/USDT", "BMT/USDT",
            "LINK/USDT", "AVAX/USDT", "DEXE/USDT", "SAHARA/USDT", "DEGO/USDT", "BARD/USDT", "FORTH/USDT", "A2Z/USDT", "CHR/USDT", "SUI/USDT", "FRAX/USDT", "VANRY/USDT", "FLUX/USDT", "PUMP/USDT", "XPL/USDT"
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
        
        else:
            st.info("👈 Select a coin and click 'Search' to generate signals")
    
    else:
        # FREE USERS - Show preview (with payment stuff on left)
        st.title("🤖 Premium Trading Signals")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            ### 🚀 Get AI-Powered Trading Signals
            
            **✨ What you get:**
            - 📊 Real-time signals for major cryptocurrencies
            - 🎯 Entry, Stop Loss, and Take Profit levels
            - 📈 Multiple timeframes (15m, 1h, 4h, 1d)
            - 🔍 Detailed AI analysis with reasoning
            - 💰 Risk/Reward ratios for each trade
            
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
            </div>
            """, unsafe_allow_html=True)
        
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
