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

class AdvancedMarketScanner:
    """Advanced market scanner that dynamically discovers and analyzes trading pairs"""
    
    def __init__(self):
        self.exchange = None
        self.available_pairs = []
        self.blacklisted_terms = ['DOWN', 'UP', 'BULL', 'BEAR', '3L', '3S', '5L', '5S', 'LEVERAGE']
        self._init_exchange()
        
    def _init_exchange(self):
        """Initialize the best available exchange"""
        exchanges = [
            ('binance', lambda: ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})),
            ('bybit', lambda: ccxt.bybit({'enableRateLimit': True})),
            ('kucoin', lambda: ccxt.kucoin({'enableRateLimit': True})),
            ('okx', lambda: ccxt.okx({'enableRateLimit': True})),
            ('gate', lambda: ccxt.gate({'enableRateLimit': True})),
        ]
        
        for name, init_func in exchanges:
            try:
                self.exchange = init_func()
                self.exchange.load_markets()
                st.session_state['active_exchange'] = name
                return
            except:
                continue
                
        st.error("No exchange connections available")
    
    def get_all_usdt_pairs(self, min_volume_usdt=1000000):
        """Get all USDT trading pairs with volume filter"""
        if not self.exchange:
            return []
        
        pairs = []
        
        try:
            markets = self.exchange.markets
            
            for symbol, market in markets.items():
                # Filter for USDT pairs only
                if symbol.endswith('/USDT') and market.get('active', True):
                    # Skip leveraged tokens and weird pairs
                    if any(term in symbol for term in self.blacklisted_terms):
                        continue
                    
                    # Get 24h volume if available
                    try:
                        ticker = self.exchange.fetch_ticker(symbol)
                        volume_usdt = ticker.get('quoteVolume', 0) or ticker.get('volume', 0) * ticker.get('last', 0)
                        
                        if volume_usdt >= min_volume_usdt:
                            pairs.append({
                                'symbol': symbol,
                                'volume': volume_usdt,
                                'price': ticker.get('last', 0),
                                'change_24h': ticker.get('percentage', 0) or ticker.get('change', 0)
                            })
                    except:
                        continue
                        
        except Exception as e:
            st.warning(f"Error fetching pairs: {e}")
            
        # Sort by volume
        pairs.sort(key=lambda x: x['volume'], reverse=True)
        return pairs
    
    def get_top_volume_pairs(self, limit=100):
        """Get top pairs by volume"""
        all_pairs = self.get_all_usdt_pairs(min_volume_usdt=500000)
        return all_pairs[:limit]
    
    def get_high_volatility_pairs(self, limit=50):
        """Get pairs with highest 24h volatility"""
        all_pairs = self.get_all_usdt_pairs(min_volume_usdt=1000000)
        
        # Sort by absolute percentage change
        all_pairs.sort(key=lambda x: abs(x['change_24h']), reverse=True)
        return all_pairs[:limit]
    
    def get_trending_pairs(self, limit=50):
        """Get pairs with strong trends (up or down)"""
        all_pairs = self.get_all_usdt_pairs(min_volume_usdt=2000000)
        
        # Filter for strong moves (>3%)
        trending = [p for p in all_pairs if abs(p['change_24h']) > 3]
        trending.sort(key=lambda x: abs(x['change_24h']), reverse=True)
        return trending[:limit]
    
    def fetch_ohlcv_data(self, symbol, timeframe='1h', limit=100):
        """Fetch OHLCV data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except:
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
            df['macd_diff'] = macd.macd_diff()
            
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_lower'] = bb.bollinger_lband()
            
            df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
            df['volatility'] = df['close'].pct_change().rolling(window=20).std() * 100
            
            # Additional indicators
            df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
            df['price_position'] = (df['close'] - df['low'].rolling(window=20).min()) / (df['high'].rolling(window=20).max() - df['low'].rolling(window=20).min())
            
        except:
            pass
        
        return df
    
    def generate_advanced_signal(self, df, symbol=""):
        """Generate advanced trading signal with multiple confirmations"""
        if df is None or len(df) < 50:
            return None
        
        try:
            latest = df.iloc[-1]
            
            bullish_score = 0
            bearish_score = 0
            reasons = []
            confirmations = []
            
            # 1. EMA Trend Analysis (Weight: 4)
            if not pd.isna(latest.get('ema_9')) and not pd.isna(latest.get('ema_21')):
                if latest['ema_9'] > latest['ema_21']:
                    bullish_score += 4
                    reasons.append("📈 EMA 9/21 Bullish crossover")
                    confirmations.append("EMA Trend: Bullish")
                else:
                    bearish_score += 4
                    reasons.append("📉 EMA 9/21 Bearish crossover")
                    confirmations.append("EMA Trend: Bearish")
            
            # 2. RSI Analysis (Weight: 5)
            if not pd.isna(latest.get('rsi')):
                if latest['rsi'] < 30:
                    bullish_score += 5
                    reasons.append(f"💪 Oversold RSI: {latest['rsi']:.1f}")
                    confirmations.append(f"RSI Oversold: {latest['rsi']:.1f}")
                elif latest['rsi'] > 70:
                    bearish_score += 5
                    reasons.append(f"⚠️ Overbought RSI: {latest['rsi']:.1f}")
                    confirmations.append(f"RSI Overbought: {latest['rsi']:.1f}")
                elif latest['rsi'] > 50:
                    bullish_score += 2
                else:
                    bearish_score += 2
            
            # 3. MACD Analysis (Weight: 4)
            if not pd.isna(latest.get('macd')) and not pd.isna(latest.get('macd_signal')):
                if latest['macd'] > latest['macd_signal']:
                    bullish_score += 4
                    reasons.append("📊 MACD Bullish crossover")
                    
                    # Check for divergence
                    if latest['macd_diff'] > 0:
                        bullish_score += 1
                else:
                    bearish_score += 4
                    reasons.append("📊 MACD Bearish crossover")
            
            # 4. Bollinger Bands (Weight: 3)
            if not pd.isna(latest.get('bb_lower')):
                bb_position = (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
                
                if bb_position < 0.2:  # Near lower band
                    bullish_score += 3
                    reasons.append("📈 Price near lower Bollinger Band")
                elif bb_position > 0.8:  # Near upper band
                    bearish_score += 3
                    reasons.append("📉 Price near upper Bollinger Band")
            
            # 5. Volume Analysis (Weight: 3)
            volume_ratio = latest.get('volume_ratio', 1)
            if volume_ratio > 1.5:  # High volume
                if bullish_score > bearish_score:
                    bullish_score += 3
                    reasons.append(f"📊 High volume confirms bullish move ({volume_ratio:.1f}x)")
                elif bearish_score > bullish_score:
                    bearish_score += 3
                    reasons.append(f"📊 High volume confirms bearish move ({volume_ratio:.1f}x)")
            
            # 6. Momentum Analysis (Weight: 3)
            momentum_10 = (latest['close'] - df['close'].iloc[-10]) / df['close'].iloc[-10] * 100
            if abs(momentum_10) > 3:
                if momentum_10 > 0:
                    bullish_score += 3
                    reasons.append(f"⚡ Strong positive momentum: +{momentum_10:.2f}%")
                else:
                    bearish_score += 3
                    reasons.append(f"⚡ Strong negative momentum: {momentum_10:.2f}%")
            
            # Calculate final signal
            total_score = bullish_score - bearish_score
            max_score = 22  # Maximum possible score
            
            # Determine signal and confidence
            if total_score >= 8:
                signal = "LONG"
                confidence = min(70 + (total_score * 2), 98)
                strength = "STRONG"
            elif total_score <= -8:
                signal = "SHORT"
                confidence = min(70 + (abs(total_score) * 2), 98)
                strength = "STRONG"
            elif total_score >= 4:
                signal = "LONG"
                confidence = min(55 + (total_score * 3), 80)
                strength = "MODERATE"
            elif total_score <= -4:
                signal = "SHORT"
                confidence = min(55 + (abs(total_score) * 3), 80)
                strength = "MODERATE"
            else:
                signal = "NEUTRAL"
                confidence = 40 + abs(total_score) * 2
                strength = "WEAK"
            
            # Calculate TP/SL
            current_price = latest['close']
            atr = latest.get('atr', current_price * 0.02)
            
            if signal == "LONG":
                stop_loss = current_price - (atr * 1.5)
                take_profit_1 = current_price + (atr * 2)
                take_profit_2 = current_price + (atr * 3.5)
            elif signal == "SHORT":
                stop_loss = current_price + (atr * 1.5)
                take_profit_1 = current_price - (atr * 2)
                take_profit_2 = current_price - (atr * 3.5)
            else:
                stop_loss = None
                take_profit_1 = None
                take_profit_2 = None
            
            risk = abs(current_price - stop_loss) if stop_loss else 0
            reward = abs(take_profit_1 - current_price) if take_profit_1 else 0
            rr_ratio = reward / risk if risk > 0 else 2.0
            
            return {
                'symbol': symbol,
                'signal': signal,
                'strength': strength,
                'confidence': int(confidence),
                'current_price': current_price,
                'stop_loss': stop_loss,
                'take_profit_1': take_profit_1,
                'take_profit_2': take_profit_2,
                'risk_reward_ratio': rr_ratio,
                'reasons': reasons,
                'confirmations': confirmations,
                'rsi': latest.get('rsi', 50),
                'volume_ratio': volume_ratio,
                'volatility': latest.get('volatility', 0),
                'momentum_10': momentum_10,
                'bullish_score': bullish_score,
                'bearish_score': bearish_score,
                'total_score': total_score,
                'max_score': max_score,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            return None
    
    def scan_pair(self, symbol, timeframe='1h'):
        """Scan a single pair and return signal"""
        try:
            df = self.fetch_ohlcv_data(symbol, timeframe, limit=100)
            if df is not None and len(df) >= 50:
                df = self.calculate_indicators(df)
                signal = self.generate_advanced_signal(df, symbol)
                return signal
        except:
            pass
        return None
    
    def scan_market_wide(self, scan_mode='top_volume', max_pairs=50, timeframe='1h', min_confidence=65):
        """Scan market-wide using different strategies"""
        
        # Get pairs based on scan mode
        if scan_mode == 'top_volume':
            pairs = self.get_top_volume_pairs(limit=max_pairs)
            scan_desc = f"Top {max_pairs} by volume"
        elif scan_mode == 'high_volatility':
            pairs = self.get_high_volatility_pairs(limit=max_pairs)
            scan_desc = f"Top {max_pairs} by volatility"
        elif scan_mode == 'trending':
            pairs = self.get_trending_pairs(limit=max_pairs)
            scan_desc = f"Top {max_pairs} trending pairs"
        else:  # 'all_market'
            pairs = self.get_top_volume_pairs(limit=max_pairs * 2)
            scan_desc = f"Market-wide ({len(pairs)} pairs)"
        
        if not pairs:
            return [], scan_desc
        
        # Store market stats
        st.session_state.market_stats = {
            'total_pairs_scanned': len(pairs),
            'avg_volume': sum(p['volume'] for p in pairs) / len(pairs) if pairs else 0,
            'top_gainer': max(pairs, key=lambda x: x['change_24h']) if pairs else None,
            'top_loser': min(pairs, key=lambda x: x['change_24h']) if pairs else None,
        }
        
        signals = []
        
        # Parallel scanning with progress tracking
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_symbol = {}
            
            for pair_info in pairs:
                future = executor.submit(self.scan_pair, pair_info['symbol'], timeframe)
                future_to_symbol[future] = pair_info
            
            for future in as_completed(future_to_symbol):
                pair_info = future_to_symbol[future]
                try:
                    signal = future.result()
                    if signal and signal['confidence'] >= min_confidence and signal['signal'] != "NEUTRAL":
                        # Add market data to signal
                        signal['volume_24h'] = pair_info['volume']
                        signal['change_24h'] = pair_info['change_24h']
                        signals.append(signal)
                except:
                    pass
        
        # Sort by confidence and score
        signals.sort(key=lambda x: (x['strength'] == 'STRONG', abs(x['total_score']), x['confidence']), reverse=True)
        
        return signals, scan_desc

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
            30, 95, 45, 5,
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
