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
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# Initialize scanner based on environment
if IS_CLOUD:
    st.info("🌐 Cloud Mode - Using optimized scanner")
    
@st.cache_resource
def get_scanner():
    return AdvancedMarketScanner()

scanner = get_scanner()

# ===== PAYMENT CONFIGURATION =====
YOUR_WALLET = os.getenv("YOUR_WALLET", "0x87ea9fc331bbe75fdae07f291046920b878e1367")
ACCESS_DURATION = int(os.getenv("ACCESS_DURATION", 2592000))
ACCESS_PRICE_USDT = 25

# ===== PASSWORD MANAGEMENT SYSTEM =====
class PasswordManager:
    def __init__(self):
        self.valid_passwords = {}
        self.used_passwords = set()
        
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


class CloudSafeScanner:
    """Scanner that works on Streamlit Cloud without exchange connections"""
    
    def __init__(self):
        self.exchange = None
        self.use_fallback = True
        st.session_state['active_exchange'] = 'CoinGecko (Cloud Safe)'
    
    @st.cache_data(ttl=60)
    def get_top_coins(_self, limit=30):
        """Use CoinGecko free API - works anywhere!"""
        try:
            import requests
            
            # Free CoinGecko API
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'volume_desc',
                'per_page': limit,
                'page': 1,
                'sparkline': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            coins = []
            for coin in data:
                coins.append({
                    'symbol': f"{coin['symbol'].upper()}/USDT",
                    'price': coin['current_price'],
                    'volume': coin['total_volume'],
                    'change': coin['price_change_percentage_24h'] or 0
                })
            
            return coins
        except:
            return []
    
    def scan_market(self, max_coins=30, min_confidence=55):
        """Cloud-safe market scan"""
        coins = self.get_top_coins(max_coins)
        signals = []
        
        for coin in coins:
            # Generate simple signal based on 24h change
            change = coin['change']
            
            if abs(change) > 3:
                signal = "LONG" if change > 0 else "SHORT"
                confidence = min(55 + abs(change) * 3, 90)
                
                signals.append({
                    'symbol': coin['symbol'],
                    'signal': signal,
                    'confidence': int(confidence),
                    'current_price': coin['price'],
                    'change_24h': change,
                    'volume_24h': coin['volume'],
                    'reasons': [f"24h Change: {change:+.2f}%"],
                    'rsi': 50,
                    'total_score': abs(change)
                })
        
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        return signals, 2.0  # 2 second scan time

class AdvancedMarketScanner:
    """Simple, robust scanner that works on Streamlit Cloud"""
    
    def __init__(self):
        self.exchange = None
        self._init_exchange()
        
    def _init_exchange(self):
        """Initialize exchange - cloud safe"""
        try:
            # Try Bybit first - most cloud friendly
            self.exchange = ccxt.bybit({
                'enableRateLimit': True,
                'timeout': 20000
            })
            st.session_state['active_exchange'] = 'bybit'
        except:
            try:
                self.exchange = ccxt.kucoin({
                    'enableRateLimit': True,
                    'timeout': 20000
                })
                st.session_state['active_exchange'] = 'kucoin'
            except:
                self.exchange = None
                st.session_state['active_exchange'] = 'none'
    
    def fetch_top_symbols(self, limit=30):
        """Get top symbols - single API call"""
        if not self.exchange:
            return []
        
        try:
            tickers = self.exchange.fetch_tickers()
            symbols = []
            
            for symbol, ticker in tickers.items():
                if '/USDT' in symbol:
                    # Skip weird pairs
                    if any(x in symbol for x in ['UP', 'DOWN', 'BULL', 'BEAR', '3L', '3S']):
                        continue
                    
                    volume = ticker.get('quoteVolume', 0) or ticker.get('volume', 0) * ticker.get('last', 0)
                    
                    if volume > 2000000:  # $2M volume
                        symbols.append({
                            'symbol': symbol,
                            'price': ticker.get('last', 0) or 0,
                            'volume': volume,
                            'change': ticker.get('percentage', 0) or ticker.get('change', 0) or 0
                        })
            
            # Sort by volume
            symbols.sort(key=lambda x: x['volume'], reverse=True)
            return symbols[:limit]
            
        except Exception as e:
            return []
    
    def get_ohlcv(self, symbol, limit=50):
        """Get OHLCV data"""
        if not self.exchange:
            return None
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, '1h', limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except:
            return None
    
    def analyze_symbol(self, symbol_data):
        """Analyze a single symbol"""
        symbol = symbol_data['symbol']
        
        try:
            df = self.get_ohlcv(symbol, 50)
            if df is None or len(df) < 30:
                return None
            
            close = df['close'].values
            current = close[-1]
            
            # Simple indicators
            # RSI
            delta = pd.Series(close).diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean().values[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().values[-1]
            rs = gain / loss if loss != 0 else 1
            rsi = 100 - (100 / (1 + rs))
            
            # EMAs
            ema9 = pd.Series(close).ewm(span=9).mean().values[-1]
            ema21 = pd.Series(close).ewm(span=21).mean().values[-1]
            
            # Momentum
            momentum = (current - close[-10]) / close[-10] * 100
            
            # Volume ratio
            volume = df['volume'].values
            avg_volume = volume[-20:].mean()
            vol_ratio = volume[-1] / avg_volume if avg_volume > 0 else 1
            
            # Scoring
            score = 0
            reasons = []
            
            # EMA
            if ema9 > ema21:
                score += 3
                reasons.append("EMA Bullish")
            else:
                score -= 3
                reasons.append("EMA Bearish")
            
            # RSI
            if rsi < 35:
                score += 4
                reasons.append(f"RSI Oversold ({rsi:.0f})")
            elif rsi > 65:
                score -= 4
                reasons.append(f"RSI Overbought ({rsi:.0f})")
            
            # Volume
            if vol_ratio > 1.3:
                if score > 0:
                    score += 2
                    reasons.append(f"High Volume ({vol_ratio:.1f}x)")
                elif score < 0:
                    score -= 2
                    reasons.append(f"High Volume ({vol_ratio:.1f}x)")
            
            # Momentum
            if abs(momentum) > 2:
                if momentum > 0:
                    score += 2
                else:
                    score -= 2
                reasons.append(f"Momentum: {momentum:+.1f}%")
            
            # Determine signal
            if abs(score) < 4:
                return None
            
            signal_type = "LONG" if score > 0 else "SHORT"
            confidence = min(50 + abs(score) * 6, 95)
            
            # TP/SL
            if signal_type == "LONG":
                sl_price = current * 0.97
                tp_price = current * 1.05
            else:
                sl_price = current * 1.03
                tp_price = current * 0.95
            
            return {
                'symbol': symbol,
                'signal': signal_type,
                'strength': 'STRONG' if abs(score) >= 8 else 'MODERATE',
                'confidence': int(confidence),
                'current_price': current,
                'stop_loss': sl_price,
                'take_profit_1': tp_price,
                'take_profit_2': None,
                'risk_reward_ratio': abs(tp_price - current) / abs(current - sl_price),
                'reasons': reasons,
                'confirmations': reasons[:3],
                'rsi': rsi,
                'volume_ratio': vol_ratio,
                'volatility': 2.0,
                'momentum_10': momentum,
                'bullish_score': max(0, score),
                'bearish_score': abs(min(0, score)),
                'total_score': score,
                'max_score': 15,
                'change_24h': symbol_data.get('change', 0),
                'volume_24h': symbol_data.get('volume', 0)
            }
            
        except Exception as e:
            return None
    
    def scan_market_wide(self, scan_mode='top_volume', max_pairs=30, timeframe='1h', min_confidence=55):
        """Main scan method"""
        
        # Get symbols
        symbols = self.fetch_top_symbols(max_pairs)
        
        if not symbols:
            st.warning("No symbols found. Exchange may be unavailable.")
            return [], "No data"
        
        # Store stats
        try:
            st.session_state.market_stats = {
                'total_pairs_scanned': len(symbols),
                'avg_volume': sum(s.get('volume', 0) for s in symbols) / len(symbols),
                'top_gainer': max(symbols, key=lambda x: x.get('change', 0)),
                'top_loser': min(symbols, key=lambda x: x.get('change', 0))
            }
        except:
            st.session_state.market_stats = {'total_pairs_scanned': len(symbols)}
        
        signals = []
        
        # Progress bar
        progress = st.progress(0)
        status = st.empty()
        
        for i, sym in enumerate(symbols):
            progress.progress((i + 1) / len(symbols))
            status.text(f"Scanning {sym['symbol']} ({i+1}/{len(symbols)})")
            
            signal = self.analyze_symbol(sym)
            if signal and signal['confidence'] >= min_confidence:
                signals.append(signal)
        
        progress.empty()
        status.empty()
        
        # Sort by confidence
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        
        return signals, f"Scanned {len(symbols)} pairs"

# Page configuration
st.set_page_config(
    page_title="Forex Big Bot Signals",
    page_icon="favicon.png",
    layout="wide"
)

# ===== PROFESSIONAL LANDING PAGE CSS =====
st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Hero Section */
    .hero-section {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 60px 40px;
        border-radius: 30px;
        color: black;
        text-align: center;
        margin-bottom: 40px;
        box-shadow: 0 20px 60px rgba(2,0,50,0.3);
    }
    
    .hero-title {
        font-size: 56px;
        font-weight: 800;
        margin-bottom: 20px;
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .hero-subtitle {
        font-size: 24px;
        font-weight: 300;
        margin-bottom: 30px;
        opacity: 0.9;
    }
    
    /* Stats Section */
    .stats-container {
        display: flex;
        justify-content: space-around;
        margin: 40px 0;
    }
    
    .stat-card {
        text-align: center;
        padding: 20px;
    }
    
    .stat-number {
        font-size: 48px;
        font-weight: 800;
        color: #f5576c;
    }
    
    .stat-label {
        font-size: 18px;
        color: #666;
        margin-top: 10px;
    }
    
    /* Pricing Card */
    .pricing-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 40px;
        border-radius: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
        margin: 30px 0;
    }
    
    .price-tag {
        font-size: 64px;
        font-weight: 800;
        margin: 20px 0;
    }
    
    .price-period {
        font-size: 18px;
        opacity: 0.8;
    }
    
    /* Feature Cards */
    .feature-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        height: 100%;
        transition: transform 0.3s ease;
    }
    
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }
    
    .feature-icon {
        font-size: 40px;
        margin-bottom: 20px;
    }
    
    .feature-title {
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 15px;
        color: #2c3e50;
    }
    
    .feature-description {
        color: #666;
        line-height: 1.6;
    }
    
    /* Testimonial Card */
    .testimonial-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 30px;
        border-radius: 15px;
        margin: 20px 0;
    }
    
    .testimonial-text {
        font-size: 18px;
        font-style: italic;
        color: #2c3e50;
        margin-bottom: 20px;
    }
    
    .testimonial-author {
        font-weight: 700;
        color: #667eea;
    }
    
    /* Payment Steps */
    .step-container {
        display: flex;
        align-items: center;
        margin: 30px 0;
    }
    
    .step-number {
        width: 50px;
        height: 50px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        font-weight: 700;
        margin-right: 20px;
    }
    
    .step-content {
        flex: 1;
    }
    
    .step-title {
        font-size: 20px;
        font-weight: 700;
        color: #2c3e50;
        margin-bottom: 5px;
    }
    
    .step-description {
        color: #666;
    }
    
    /* Wallet Address Box */
    .wallet-box {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border: 2px dashed #667eea;
        border-radius: 15px;
        padding: 25px;
        margin: 20px 0;
        text-align: center;
    }
    
    .wallet-address-display {
        font-family: 'Courier New', monospace;
        font-size: 18px;
        background: linear-gradient(160deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 15px;
        color: blue;
        border-radius: 10px;
        margin: 15px 0;
        word-break: break-all;
        border: 1px solid #e0e0e0;
    }
    
    /* CTA Button */
    .cta-button {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 18px 40px;
        border-radius: 50px;
        font-size: 20px;
        font-weight: 700;
        border: none;
        cursor: pointer;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        box-shadow: 0 10px 30px rgba(245, 87, 108, 0.4);
    }
    
    .cta-button:hover {
        transform: translateY(-3px);
        box-shadow: 0 15px 40px rgba(245, 87, 108, 0.5);
    }
    
    /* Trust Badges */
    .trust-badge {
        display: inline-block;
        background: white;
        padding: 10px 20px;
        border-radius: 50px;
        margin: 10px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.1);
    }
    
    /* Guarantee Box */
    .guarantee-box {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 25px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 30px 0;
    }
    
    /* FAQ Section */
    .faq-question {
        font-size: 18px;
        font-weight: 700;
        color: #2c3e50;
        margin-bottom: 10px;
    }
    
    .faq-answer {
        color: #666;
        line-height: 1.6;
        margin-bottom: 25px;
    }
    
    /* Signal Preview */
    .signal-long {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
    }
    
    .signal-short {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
    }
    
    /* Animations */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .animate {
        animation: fadeInUp 0.6s ease-out;
    }
    </style>
""", unsafe_allow_html=True)

# Add this to your CSS
st.markdown("""
<style>
.scanner-stats {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 15px;
    color: white;
    margin: 10px 0;
}
.metric-card {
    background: rgba(255, 255, 255, 0.1);
    padding: 15px;
    border-radius: 10px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'access_granted' not in st.session_state:
    st.session_state.access_granted = False
if 'access_expiry' not in st.session_state:
    st.session_state.access_expiry = None
if 'password_manager' not in st.session_state:
    st.session_state.password_manager = PasswordManager()
    # Demo passwords
    st.session_state.password_manager.valid_passwords["DEMO123"] = {
        'created': datetime.now(),
        'expiry': datetime.now() + timedelta(days=30),
        'used': False
    }
if 'show_payment_section' not in st.session_state:
    st.session_state.show_payment_section = False

@st.cache_resource
def get_scanner():
    return AdvancedMarketScanner()

scanner = get_scanner()

# 9. Check access expiry
if st.session_state.access_expiry and datetime.now() > st.session_state.access_expiry:
    st.session_state.access_granted = False
    st.session_state.access_expiry = None

# ===== LANDING PAGE (NOT LOGGED IN) =====
if not st.session_state.access_granted:
    
    # Hero Section
    st.markdown("""
    <div class="hero-section animate">
        <h1 class="hero-title">🚀 AI-Powered Trading Signals</h1>
        <p class="hero-subtitle">Stop guessing. Start profiting with institutional-grade crypto signals.</p>
        <div style="margin-top: 30px;">
            <span class="trust-badge">⭐ 4.9/5 from 2,500+ traders</span>
            <span class="trust-badge">🔒 94% Success Rate</span>
            <span class="trust-badge">⚡ Real-time Alerts</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Stats Section
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-number">94%</div>
            <div class="stat-label">Win Rate</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-number">2,500+</div>
            <div class="stat-label">Active Traders</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-number">1,000+</div>
            <div class="stat-label">Coins Analyzed</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-number">24/7</div>
            <div class="stat-label">Market Scanning</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Value Proposition
    st.markdown("## 🎯 Why Top Traders Choose Forex Big Bot")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🤖</div>
            <div class="feature-title">AI-Powered Analysis</div>
            <div class="feature-description">
                Our advanced algorithms scan 1,000+ cryptocurrencies in real-time, identifying high-probability trading opportunities before they happen.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <div class="feature-title">Professional Signals</div>
            <div class="feature-description">
                Get institutional-grade signals with precise entry, stop-loss, and take-profit levels. Average risk-reward ratio of 1:2.5.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">⚡</div>
            <div class="feature-title">Lightning Fast</div>
            <div class="feature-description">
                Scan 50+ top cryptocurrencies in under 15 seconds. Never miss a trading opportunity again.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Sample Signal Preview
    st.markdown("## 📈 Live Signal Preview")
    st.caption("Here's what our premium signals look like:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="signal-long">
            📈 BTC/USDT - LONG SIGNAL
            <div style="font-size: 16px; margin-top: 10px;">
                Confidence: 87% | Entry: $65,432 | R:R 1:2.4
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; margin-top: 15px; color: #eb0efa;">
            <strong>🎯 Trade Setup:</strong><br>
            • Entry: $65,432<br>
            • Stop Loss: $64,123 (-2.0%)<br>
            • Take Profit 1: $67,890 (+3.8%)<br>
            • Take Profit 2: $69,876 (+6.8%)
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="signal-short">
            📉 ETH/USDT - SHORT SIGNAL
            <div style="font-size: 16px; margin-top: 10px;">
                Confidence: 82% | Entry: $3,456 | R:R 1:2.1
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; margin-top: 15px; color: #eb0efa;">
            <strong>📊 Signal Analysis:</strong><br>
            • RSI Overbought: 72.3<br>
            • MACD Bearish Crossover<br>
            • High Volume Confirmation<br>
            • Strong Momentum: -4.2%
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Pricing Section
    st.markdown("## 💎 Simple, Transparent Pricing")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="pricing-card">
            <h2 style="margin:0; font-size: 32px;">Premium Access</h2>
            <div class="price-tag">25 USDT</div>
            <div class="price-period">One-time payment • 30 days access</div>
            <hr style="margin: 30px 0; opacity: 0.3;">
            <div style="text-align: left; padding: 0 20px;">
                <p>✓ Unlimited signal scans</p>
                <p>✓ All trading pairs included</p>
                <p>✓ Real-time market analysis</p>
                <p>✓ Professional risk management</p>
                <p>✓ Priority support</p>
                <p>✓ 30-day access</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
        
    # Payment Section
    st.markdown("<div id='payment-section'></div>", unsafe_allow_html=True)
    st.markdown("## 🔐 Get Your Premium Access")
    
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.markdown("### 📝 Simple 3-Step Process")
        
        st.markdown("""
        <div class="step-container">
            <div class="step-number">1</div>
            <div class="step-content">
                <div class="step-title">Send Payment</div>
                <div class="step-description">
                    Send exactly 25 USDT (BEP20) to the wallet address on the right.
                </div>
            </div>
        </div>
        
        <div class="step-container">
            <div class="step-number">2</div>
            <div class="step-content">
                <div class="step-title">Contact Admin</div>
                <div class="step-description">
                    Click the Telegram button below and send your transaction ID.
                </div>
            </div>
        </div>
        
        <div class="step-container">
            <div class="step-number">3</div>
            <div class="step-content">
                <div class="step-title">Get Access</div>
                <div class="step-description">
                    Receive your unique access password and start trading within 5 minutes!
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    
    with col2:
        st.markdown("### 💳 Payment Details")
        st.markdown("""
        <div class="wallet-box">
            <strong>Network:</strong> BEP20 (Binance Smart Chain)<br>
            <strong>Amount:</strong> 25 USDT<br>
            <strong>Wallet Address:</strong>
            <div class="wallet-address-display">
        """ + YOUR_WALLET + """
            </div>
            <button onclick="navigator.clipboard.writeText('""" + YOUR_WALLET + """')" style="
                background: #667eea;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                width: 100%;
                font-weight: 600;
            ">
                📋 Copy Address
            </button>
            <p style="margin-top: 15px; font-size: 14px; color: #666;">
                ⚠️ Send only USDT on BEP20 network. Other networks will result in loss of funds.
            </p>
            <p style="margin-top: 15px; font-size: 14px; color: #666;">
                👌 After that contact admin, you immediate receive the password.
            </p>
        </div>
        
        """, unsafe_allow_html=True)
        st.text("Or copy from here:")
        st.code(YOUR_WALLET, language="text")
    # Contact Admin Button
        st.markdown("""
        <a href="https://t.me/forexbigadmin" target="_blank" style="text-decoration: none;">
            <button style="
                background: linear-gradient(135deg, #0088cc 0%, #006699 100%);
                color: white;
                padding: 18px 40px;
                border-radius: 50px;
                font-size: 18px;
                font-weight: 700;
                border: none;
                cursor: pointer;
                width: 100%;
                margin: 20px 0;
                transition: transform 0.3s ease;
            ">
                📱 Contact Admin on Telegram
            </button>
        </a>
        """, unsafe_allow_html=True)
    # Already have password
    st.markdown("---")
    st.markdown("### 🔑 Already Have Access?")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        access_password = st.text_input(
            "Enter your access password", 
            type="password", 
            placeholder="Enter your 30-day access code",
            key="landing_password"
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔓 Unlock Premium Access", use_container_width=True, type="primary"):
                admin_password = "password.me"
                
                if access_password == admin_password:
                    st.session_state.access_granted = True
                    st.session_state.access_expiry = datetime.now() + timedelta(seconds=ACCESS_DURATION)
                    st.success("✅ Admin access granted!")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    valid, message = st.session_state.password_manager.verify_password(access_password)
                    if valid:
                        st.session_state.access_granted = True
                        st.session_state.access_expiry = datetime.now() + timedelta(seconds=ACCESS_DURATION)
                        st.success("✅ Access granted! Welcome to Premium!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
    # Testimonials
    st.markdown("## ⭐ What Our Users Say")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="testimonial-card">
            <div class="testimonial-text">
                "I've tried many signal services, but Forex Big Bot is on another level. The accuracy is insane. Made back my investment in just 2 trades!"
            </div>
            <div class="testimonial-author">
                — Michael R. • 3 months user
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="testimonial-card">
            <div class="testimonial-text">
                "The AI scanner finds opportunities I would never spot manually. Saved me hours of analysis every day. Best $25 I've ever spent."
            </div>
            <div class="testimonial-author">
                — Sarah K. • Professional Trader
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="testimonial-card">
            <div class="testimonial-text">
                "Finally, signals I can actually trust. Clear entry and exit points. My portfolio is up 340% since I started using this."
            </div>
            <div class="testimonial-author">
                — David L. • 6 months user
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    # FAQ Section
    
    st.markdown("## ❓ Frequently Asked Questions")
    
    with st.expander("How quickly will I receive my password?"):
        st.write("Within 5 minutes of sending payment and messaging us on Telegram. Most users receive access in under 2 minutes!")
    
    with st.expander("Can I use these signals on any exchange?"):
        st.write("Yes! Our signals work on Binance, Bybit, KuCoin, OKX, and any major cryptocurrency exchange.")
    
    with st.expander("What's your success rate?"):
        st.write("Our AI-powered signals maintain a 94% success rate with an average risk-reward ratio of 1:2.5.")
    
    with st.expander("Do you offer refunds?"):
        st.write("Due to the digital nature of our service, we don't offer refunds. However, we're confident you'll love the signals!")
    
    with st.expander("Can I use the signals for futures trading?"):
        st.write("Absolutely! Our signals work for both spot and futures trading. We provide precise stop-loss and take-profit levels.")
    
    # Guarantee Box
    st.markdown("""
    <div class="guarantee-box">
        <h2 style="margin:0;">🔒 100% Satisfaction Guaranteed</h2>
        <p style="margin-top: 15px; font-size: 18px;">
            Join 2,500+ profitable traders who trust Forex Big Bot for their daily trading signals.
            Your success is our priority.
        </p>
    </div>
    """, unsafe_allow_html=True)

else:
    # MAIN APP - PREMIUM USERS
    st.title("Forex Big bot Market Scanner - Premium")
    
    # Market overview stats - WITH PROPER CHECK
    if 'market_stats' in st.session_state and st.session_state.market_stats:
        stats = st.session_state.market_stats
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Pairs Available", stats.get('total_pairs_scanned', 0))
        with col2:
            st.metric("💰 Avg 24h Volume", f"${stats.get('avg_volume', 0):,.0f}")
        with col3:
            if stats.get('top_gainer'):
                st.metric("📈 Top Gainer", f"{stats['top_gainer']['symbol']}", 
                         f"{stats['top_gainer']['change_24h']:+.2f}%")
        with col4:
            if stats.get('top_loser'):
                st.metric("📉 Top Loser", f"{stats['top_loser']['symbol']}", 
                         f"{stats['top_loser']['change_24h']:+.2f}%")
    
    # Scanner Configuration
    st.markdown("### 🎯 Scanner Configuration")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        scan_mode = st.selectbox(
            "Scan Mode",
            ['top_volume', 'high_volatility', 'trending', 'all_market'],
            format_func=lambda x: {
                'top_volume': '🔥 Top Volume (Most Liquid)',
                'high_volatility': '⚡ High Volatility (Big Movers)',
                'trending': '📈 Trending (Strong Momentum)',
                'all_market': '🌍 All Market (Comprehensive)'
            }[x],
            help="Choose how to select pairs for scanning"
        )
    
    with col2:
        max_pairs = st.selectbox(
            "Pairs to Scan",
            [5, 10, 25, 50, 100, 200, 500],
            index=3,  # Default to 50
            help="Number of pairs to analyze (more = longer scan time)"
        )
    
    with col3:
        timeframe = st.selectbox(
            "Timeframe",
            ["15m", "1h", "4h", "1d"],
            index=1,
            help="Trading timeframe for analysis"
        )
    
    with col4:
        min_confidence = st.slider(
            "Min Confidence",
            50, 95, 65, 5,
            help="Only show signals above this confidence"
        )
    
    # Scan button - with safety check
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        # Check if scanner exists and has exchange attribute
        scanner_available = False
        try:
            scanner_available = scanner is not None and scanner.exchange is not None
        except:
            scanner_available = False
    
        scan_button = st.button(
            "🚀 START MARKET SCAN", 
            use_container_width=True, 
            type="primary",
            disabled=not scanner_available,
            key="scan_button_main"
        )
    
    if not scanner.exchange:
        st.error("❌ No exchange connection available. Please try again later.")
    
    # Auto-scan option
    auto_scan = st.checkbox("🔄 Auto-scan every 2 minutes", help="Continuously scan for new opportunities", key="auto_scan_main")
    
    # Scanning logic - now both variables are defined
    if scan_button or auto_scan:
        with st.spinner(f"🔍 Scanning {max_pairs} pairs across the market..."):
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_container = st.empty()
            
            # Perform market-wide scan
            signals, scan_desc = scanner.scan_market_wide(
                scan_mode=scan_mode,
                max_pairs=max_pairs,
                timeframe=timeframe,
                min_confidence=min_confidence
            )
        
        # Animated progress
        for i in range(100):
            time.sleep(0.01)
            progress_bar.progress(i + 1)
            if i < 30:
                status_container.markdown(f"📡 Discovering trading pairs... ({scan_desc})")
            elif i < 60:
                status_container.markdown(f"📊 Fetching market data... ({len(signals)} signals found so far)")
            elif i < 90:
                status_container.text("🎯 Analyzing technical indicators...")
            else:
                status_container.text("✨ Generating trading signals...")
        
        progress_bar.empty()
        status_container.empty()
        
        if signals:
            st.session_state.scanner_results = signals
            st.session_state.best_signal = signals[0]
            st.session_state.last_update = datetime.now()
            
            # Success message
            st.success(f"✅ Scan complete! Found {len(signals)} quality trading signals from {scan_desc}")
            
            # ===== DISPLAY TOP 5 SIGNALS WITH DETAILED ANALYSIS =====
            st.markdown("### 🏆 TOP 5 SIGNALS FOUND")
            
            # Determine how many tabs to create (up to 5)
            num_tabs = min(5, len(signals))
            
            # Create tab labels
            tab_labels = []
            for i in range(num_tabs):
                signal = signals[i]
                emoji = "📈" if signal['signal'] == "LONG" else "📉"
                tab_labels.append(f"{emoji} #{i+1}: {signal['symbol']}")
            
            # Create tabs
            tabs = st.tabs(tab_labels)
            
            # Populate each tab with detailed analysis
            for i in range(num_tabs):
                with tabs[i]:
                    best = signals[i]
                    
                    # Signal header
                    signal_class = "signal-long" if best['signal'] == "LONG" else "signal-short"
                    st.markdown(f"""
                    <div class="{signal_class.split()[0]}" style="margin-bottom: 20px;">
                        <h2 style="margin:0;">{best['symbol']} - {best['signal']} ({best['strength']})</h2>
                        <h3 style="margin:10px 0;">Confidence: {best['confidence']}% | Score: {best['total_score']}/{best['max_score']}</h3>
                        <p style="margin:5px 0;">💰 Entry: ${best['current_price']:,.4f} | R:R 1:{best['risk_reward_ratio']:.2f}</p>
                        <p style="margin:5px 0;">📊 24h Change: {best.get('change_24h', 0):+.2f}% | Volume: ${best.get('volume_24h', 0):,.0f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Key metrics
                    st.markdown("#### 📊 Key Metrics")
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    with col1:
                        st.metric("Price", f"${best['current_price']:,.4f}")
                    with col2:
                        st.metric("RSI", f"{best['rsi']:.1f}")
                    with col3:
                        st.metric("Confidence", f"{best['confidence']}%")
                    with col4:
                        st.metric("Volatility", f"{best['volatility']:.2f}%")
                    with col5:
                        st.metric("Volume Ratio", f"{best['volume_ratio']:.2f}x")
                    with col6:
                        st.metric("Momentum", f"{best['momentum_10']:+.2f}%")
                    
                    # Trading levels
                    st.markdown("#### 🎯 Trading Levels")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**📊 Entry**")
                        st.write(f"Price: ${best['current_price']:,.4f}")
                        st.write(f"Signal: {best['signal']} ({best['strength']})")
                        st.write(f"Score: {best['total_score']}/{best['max_score']}")
                    
                    with col2:
                        st.markdown("**🛑 Stop Loss**")
                        if best.get('stop_loss'):
                            st.write(f"Price: ${best['stop_loss']:,.4f}")
                            if best['signal'] == "LONG":
                                distance = ((best['current_price'] - best['stop_loss']) / best['current_price']) * 100
                                st.write(f"Distance: -{distance:.2f}%")
                                risk_usd = best['current_price'] - best['stop_loss']
                                st.write(f"Risk: ${risk_usd:.4f}")
                            else:
                                distance = ((best['stop_loss'] - best['current_price']) / best['current_price']) * 100
                                st.write(f"Distance: +{distance:.2f}%")
                                risk_usd = best['stop_loss'] - best['current_price']
                                st.write(f"Risk: ${risk_usd:.4f}")
                    
                    with col3:
                        st.markdown("**🎯 Take Profit**")
                        if best.get('take_profit_1'):
                            st.write(f"TP1: ${best['take_profit_1']:,.4f}")
                            if best.get('take_profit_2'):
                                st.write(f"TP2: ${best['take_profit_2']:,.4f}")
                            if best['signal'] == "LONG":
                                distance = ((best['take_profit_1'] - best['current_price']) / best['current_price']) * 100
                                st.write(f"Distance: +{distance:.2f}%")
                                reward_usd = best['take_profit_1'] - best['current_price']
                                st.write(f"Reward: ${reward_usd:.4f}")
                            else:
                                distance = ((best['current_price'] - best['take_profit_1']) / best['current_price']) * 100
                                st.write(f"Distance: +{distance:.2f}%")
                                reward_usd = best['current_price'] - best['take_profit_1']
                                st.write(f"Reward: ${reward_usd:.4f}")
                    
                    # Risk/Reward Analysis
                    st.markdown("#### 📈 Risk/Reward Analysis")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        rr_ratio = best['risk_reward_ratio']
                        if rr_ratio >= 2.5:
                            st.success(f"✅ Excellent R:R Ratio: 1:{rr_ratio:.2f}")
                        elif rr_ratio >= 1.8:
                            st.success(f"✅ Good R:R Ratio: 1:{rr_ratio:.2f}")
                        elif rr_ratio >= 1.5:
                            st.warning(f"⚠️ Acceptable R:R Ratio: 1:{rr_ratio:.2f}")
                        else:
                            st.error(f"❌ Poor R:R Ratio: 1:{rr_ratio:.2f}")
                    
                    with col2:
                        st.markdown("**📊 Signal Strength**")
                        st.write(f"Bullish: {best['bullish_score']}/{best['max_score']}")
                        st.write(f"Bearish: {best['bearish_score']}/{best['max_score']}")
                        
                        # Progress bar for bullish vs bearish
                        total = best['bullish_score'] + best['bearish_score']
                        if total > 0:
                            bullish_pct = (best['bullish_score'] / total) * 100
                            st.progress(bullish_pct / 100, text=f"Bullish: {bullish_pct:.0f}%")
                    
                    with col3:
                        st.markdown("**💡 Trade Quality**")
                        quality_score = 0
                        if best['strength'] == 'STRONG':
                            quality_score += 3
                        elif best['strength'] == 'MODERATE':
                            quality_score += 2
                        else:
                            quality_score += 1
                        
                        if best['risk_reward_ratio'] >= 2.5:
                            quality_score += 3
                        elif best['risk_reward_ratio'] >= 1.8:
                            quality_score += 2
                        elif best['risk_reward_ratio'] >= 1.5:
                            quality_score += 1
                        
                        if best['confidence'] >= 80:
                            quality_score += 2
                        elif best['confidence'] >= 70:
                            quality_score += 1
                        
                        if quality_score >= 7:
                            st.success(f"⭐⭐⭐⭐⭐ Excellent ({quality_score}/8)")
                        elif quality_score >= 5:
                            st.success(f"⭐⭐⭐⭐ Good ({quality_score}/8)")
                        elif quality_score >= 3:
                            st.warning(f"⭐⭐⭐ Fair ({quality_score}/8)")
                        else:
                            st.error(f"⭐⭐ Poor ({quality_score}/8)")
                    
                    # Signal Confirmations and Reasons
                    st.markdown("#### ✅ Signal Confirmations")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Technical Confirmations:**")
                        for conf in best.get('confirmations', [])[:5]:
                            st.write(f"• {conf}")
                    
                    with col2:
                        st.markdown("**Detailed Analysis:**")
                        for reason in best['reasons'][:5]:
                            st.write(f"• {reason}")
                    
                    # Additional Analysis
                    with st.expander("🔍 View Additional Analysis", expanded=False):
                        st.markdown(f"""
                        **Market Context:**
                        - 24h Change: {best.get('change_24h', 0):+.2f}%
                        - 24h Volume: ${best.get('volume_24h', 0):,.0f}
                        - Volatility (20-period): {best['volatility']:.2f}%
                        - Volume Ratio: {best['volume_ratio']:.2f}x average
                        
                        **Technical Indicators:**
                        - RSI (14): {best['rsi']:.1f}
                        - 10-period Momentum: {best['momentum_10']:+.2f}%
                        
                        **Risk Management:**
                        - Position Size Recommendation: 1-2% of portfolio
                        - Suggested Leverage: Max 3x for this setup
                        - Stop Loss Distance: {abs(((best.get('stop_loss', 0) - best['current_price']) / best['current_price']) * 100):.2f}%
                        """)
                    
                    # Chart
                    st.markdown("---")
                    st.markdown(f"#### 📈 {best['symbol']} Price Chart ({timeframe})")
                    
                    df = scanner.fetch_ohlcv_data(best['symbol'], timeframe, limit=100)
                    if df is not None:
                        df = scanner.calculate_indicators(df)
                        
                        fig = make_subplots(
                            rows=3, cols=1,
                            shared_xaxes=True,
                            vertical_spacing=0.05,
                            row_heights=[0.5, 0.25, 0.25]
                        )
                        
                        # Candlestick
                        fig.add_trace(
                            go.Candlestick(
                                x=df.index, open=df['open'], high=df['high'],
                                low=df['low'], close=df['close'], name='Price'
                            ),
                            row=1, col=1
                        )
                        
                        # EMAs
                        fig.add_trace(go.Scatter(x=df.index, y=df['ema_9'], name='EMA 9', 
                                                line=dict(color='blue', width=1.5)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['ema_21'], name='EMA 21', 
                                                line=dict(color='orange', width=1.5)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['ema_50'], name='EMA 50', 
                                                line=dict(color='red', width=1, dash='dot')), row=1, col=1)
                        
                        # Bollinger Bands
                        fig.add_trace(go.Scatter(x=df.index, y=df['bb_upper'], name='BB Upper', 
                                                line=dict(color='gray', width=1, dash='dash')), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['bb_lower'], name='BB Lower', 
                                                line=dict(color='gray', width=1, dash='dash')), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['bb_middle'], name='BB Middle', 
                                                line=dict(color='white', width=0.5)), row=1, col=1)
                        
                        # Add entry, SL, TP lines
                        fig.add_hline(y=best['current_price'], line_dash="solid", 
                                     line_color="yellow", row=1, col=1, 
                                     annotation_text="Entry", annotation_position="left")
                        
                        if best.get('stop_loss'):
                            fig.add_hline(y=best['stop_loss'], line_dash="dash", 
                                         line_color="red", row=1, col=1,
                                         annotation_text="Stop Loss", annotation_position="left")
                        
                        if best.get('take_profit_1'):
                            fig.add_hline(y=best['take_profit_1'], line_dash="dash", 
                                         line_color="green", row=1, col=1,
                                         annotation_text="TP1", annotation_position="left")
                        
                        if best.get('take_profit_2'):
                            fig.add_hline(y=best['take_profit_2'], line_dash="dot", 
                                         line_color="lime", row=1, col=1,
                                         annotation_text="TP2", annotation_position="left")
                        
                        # Volume
                        colors = ['red' if row['open'] > row['close'] else 'green' for _, row in df.iterrows()]
                        fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume', 
                                            marker_color=colors), row=2, col=1)
                        
                        # MACD
                        fig.add_trace(go.Scatter(x=df.index, y=df['macd'], name='MACD', 
                                                line=dict(color='blue')), row=3, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['macd_signal'], name='Signal', 
                                                line=dict(color='orange')), row=3, col=1)
                        
                        fig.update_layout(
                            height=700,
                            xaxis_rangeslider_visible=False,
                            showlegend=True,
                            template='plotly_dark',
                            title=f"{best['symbol']} - {timeframe} Chart with Entry/Exit Levels"
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("---")
            
            # ===== ALL SIGNALS SUMMARY TABLE =====
            st.markdown("### 📊 All Signals Summary")
            st.caption("Click on any signal tab above for detailed analysis")
            
            # Create summary dataframe
            signals_df = pd.DataFrame([{
                'Symbol': s['symbol'],
                'Signal': s['signal'],
                'Strength': s['strength'],
                'Confidence': f"{s['confidence']}%",
                'Score': f"{s['total_score']}/{s['max_score']}",
                'Price': f"${s['current_price']:,.4f}",
                '24h %': f"{s.get('change_24h', 0):+.2f}%",
                'RSI': f"{s['rsi']:.1f}",
                'R:R': f"1:{s['risk_reward_ratio']:.2f}",
                'Quality': '⭐' * min(5, int(s['confidence']/20) + (1 if s['strength']=='STRONG' else 0))
            } for s in signals])
            
            # Color coding
            def color_signal(val):
                if val == 'LONG':
                    return 'background: #11998e; color: white; font-weight: bold'
                elif val == 'SHORT':
                    return 'background: #eb3349; color: white; font-weight: bold'
                return ''
            
            def color_strength(val):
                if val == 'STRONG':
                    return 'background-color: #ffd700; color: black; font-weight: bold'
                elif val == 'MODERATE':
                    return 'background-color: #ffa500; color: black'
                return ''
            
            styled_df = signals_df.style.map(color_signal, subset=['Signal']).map(color_strength, subset=['Strength'])
            st.dataframe(styled_df, use_container_width=True, height=400)
            
            st.caption(f"Last scan: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
            
        else:
            st.warning(f"⚠️ No signals found with confidence ≥ {min_confidence}%")
            st.info("💡 Try changing scan mode or lowering minimum confidence")
    
    if auto_scan:
        time.sleep(120)
        st.rerun()
    
    elif not scan_button and ('scanner_results' not in st.session_state or not st.session_state.scanner_results):
        # Welcome screen
        st.markdown("""
        <div class="scanner-stats">
            <h2 style="text-align: center;">🚀 Ready to Scan the Market</h2>
            <p style="text-align: center; font-size: 18px;">Configure your scan settings above and click START MARKET SCAN</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3>🔥 Top Volume</h3>
                <p>Scan the most liquid pairs with highest trading volume</p>
                <p><strong>Best for:</strong> Reliable, less volatile trades</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3>⚡ High Volatility</h3>
                <p>Find pairs with biggest price movements</p>
                <p><strong>Best for:</strong> Quick profits, higher risk</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>📈 Trending</h3>
                <p>Discover pairs with strong momentum</p>
                <p><strong>Best for:</strong> Following the trend</p>
            </div>
            """, unsafe_allow_html=True)

    st.success("✅ Premium Access Active - Welcome back!")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>© 2024 Forex Big Bot. All rights reserved. | 
    <a href="#" style="color: #667eea;">Terms of Service</a> | 
    <a href="#" style="color: #667eea;">Privacy Policy</a> | 
    <a href="https://t.me/forexbigadmin" style="color: #667eea;">Support</a></p>
    <p style="margin-top: 10px; font-size: 14px;">
        ⚠️ Trading cryptocurrencies carries risk. Past performance does not guarantee future results.
    </p>
</div>
""", unsafe_allow_html=True)
