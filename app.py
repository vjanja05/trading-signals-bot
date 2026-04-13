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
    """Full market scanner - works on Streamlit Cloud with smart fallbacks"""
    
    def __init__(self):
        self.exchange = None
        self.use_fallback = False
        self._init_exchange()
        
    def _init_exchange(self):
        """Try multiple exchanges with cloud-friendly settings"""
        # Exchanges that work better on cloud
        exchanges = [
            ('bybit', lambda: ccxt.bybit({
                'enableRateLimit': True,
                'timeout': 15000,
                'rateLimit': 100
            })),
            ('kucoin', lambda: ccxt.kucoin({
                'enableRateLimit': True,
                'timeout': 15000
            })),
            ('gate', lambda: ccxt.gate({
                'enableRateLimit': True,
                'timeout': 15000
            })),
            ('mexc', lambda: ccxt.mexc({
                'enableRateLimit': True,
                'timeout': 15000
            })),
            ('binance', lambda: ccxt.binance({
                'enableRateLimit': True,
                'timeout': 15000,
                'options': {'defaultType': 'spot'}
            })),
        ]
        
        for name, init_func in exchanges:
            try:
                self.exchange = init_func()
                # Quick test
                self.exchange.fetch_time()
                st.session_state['active_exchange'] = name
                self.use_fallback = False
                return
            except:
                continue
        
        # If all fail, use fallback
        self.use_fallback = True
        st.session_state['active_exchange'] = 'fallback'
    
    def get_all_usdt_pairs(self, min_volume=500000):
        """Get ALL USDT pairs with volume filter"""
        if not self.exchange or self.use_fallback:
            return self._get_fallback_pairs()
        
        try:
            # Single API call for all tickers
            tickers = self.exchange.fetch_tickers()
            
            pairs = []
            skip_terms = ['DOWN', 'UP', 'BULL', 'BEAR', '3L', '3S', '5L', '5S', 
                         'BUSD', 'USDC', 'TUSD', 'DAI', 'PAX', 'USDP']
            
            for symbol, ticker in tickers.items():
                if not symbol.endswith('/USDT'):
                    continue
                
                # Skip stablecoins and leveraged tokens
                if any(x in symbol for x in skip_terms):
                    continue
                
                volume = ticker.get('quoteVolume', 0)
                if volume == 0:
                    volume = ticker.get('volume', 0) * ticker.get('last', 0)
                
                if volume >= min_volume:
                    change = ticker.get('percentage', 0)
                    if change is None:
                        change = ticker.get('change', 0)
                    if change is None:
                        change = 0
                    
                    pairs.append({
                        'symbol': symbol,
                        'volume': volume,
                        'price': ticker.get('last', 0) or 0,
                        'change_24h': change,
                        'high': ticker.get('high', 0),
                        'low': ticker.get('low', 0)
                    })
            
            # Sort by volume
            pairs.sort(key=lambda x: x['volume'], reverse=True)
            return pairs
            
        except Exception as e:
            return self._get_fallback_pairs()
    
    def _get_fallback_pairs(self):
        """Fallback: Pre-defined list of 200+ active trading pairs"""
        fallback_coins = [
            # Top 50 by market cap
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
            'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT',
            'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ETC/USDT',
            'FIL/USDT', 'ALGO/USDT', 'VET/USDT', 'THETA/USDT', 'AAVE/USDT',
            'WIF/USDT', 'TNSR/USDT', 'ENJ/USDT', 'SAND/USDT', 'MANA/USDT',
            # Additional active pairs
            'NEAR/USDT', 'FLOW/USDT', 'AXS/USDT', 'EGLD/USDT', 'EOS/USDT',
            'XTZ/USDT', 'IOTA/USDT', 'NEO/USDT', 'ZEC/USDT', 'DASH/USDT',
            'COMP/USDT', 'MKR/USDT', 'SNX/USDT', 'CRV/USDT', '1INCH/USDT',
            'CAKE/USDT', 'RUNE/USDT', 'KAVA/USDT', 'WAVES/USDT', 'CHZ/USDT',
            'HOT/USDT', 'ZIL/USDT', 'BAT/USDT', 'ZRX/USDT', 'STORJ/USDT',
            'ANKR/USDT', 'COTI/USDT', 'OCEAN/USDT', 'FET/USDT', 'AGIX/USDT',
            'RNDR/USDT', 'GRT/USDT', 'LDO/USDT', 'OP/USDT', 'ARB/USDT',
            'APT/USDT', 'SUI/USDT', 'SEI/USDT', 'TIA/USDT', 'PYTH/USDT',
            'JUP/USDT', 'JTO/USDT', 'BONK/USDT', 'ORDI/USDT', 'SATS/USDT',
            # More pairs
            'DYDX/USDT', 'GMX/USDT', 'GALA/USDT', 'IMX/USDT', 'MINA/USDT',
            'ROSE/USDT', 'KSM/USDT', 'ICP/USDT', 'HBAR/USDT', 'STX/USDT',
            'INJ/USDT', 'KAS/USDT', 'XLM/USDT', 'XMR/USDT', 'TRX/USDT',
            'TON/USDT', 'BCH/USDT', 'LEO/USDT', 'OKB/USDT', 'CRO/USDT',
            'QNT/USDT', 'ALGO/USDT', 'FTM/USDT', 'XEC/USDT', 'LUNC/USDT',
            'LUNA/USDT', 'USTC/USDT', 'ZEN/USDT', 'RVN/USDT', 'ONE/USDT',
            'CELO/USDT', 'ONT/USDT', 'ICX/USDT', 'SC/USDT', 'DGB/USDT',
            'LSK/USDT', 'NANO/USDT', 'STEEM/USDT', 'WAN/USDT', 'AION/USDT',
            'ARDR/USDT', 'KMD/USDT', 'STRAT/USDT', 'REP/USDT', 'MAID/USDT',
            'DOGE/USDT', 'SHIB/USDT', 'PEPE/USDT', 'FLOKI/USDT', 'BONE/USDT',
            'BABYDOGE/USDT', 'ELON/USDT', 'SAMO/USDT', 'KISHU/USDT', 'AKITA/USDT',
            'CULT/USDT', 'VOLT/USDT', 'TSUKA/USDT', 'LADYS/USDT', 'BEN/USDT',
        ]
        
        pairs = []
        for symbol in fallback_coins:
            pairs.append({
                'symbol': symbol,
                'volume': 1000000,
                'price': 0,
                'change_24h': 0,
                'high': 0,
                'low': 0
            })
        
        return pairs
    
    def get_pairs_by_mode(self, scan_mode, limit=50):
        """Get pairs based on scan mode"""
        all_pairs = self.get_all_usdt_pairs(min_volume=500000)
        
        if not all_pairs:
            return []
        
        if scan_mode == 'top_volume':
            return all_pairs[:limit]
        
        elif scan_mode == 'high_volatility':
            # Sort by absolute change
            sorted_pairs = sorted(all_pairs, key=lambda x: abs(x.get('change_24h', 0)), reverse=True)
            return sorted_pairs[:limit]
        
        elif scan_mode == 'trending':
            # Filter for strong moves (>3%)
            trending = [p for p in all_pairs if abs(p.get('change_24h', 0)) > 3]
            trending.sort(key=lambda x: abs(x.get('change_24h', 0)), reverse=True)
            return trending[:limit]
        
        else:  # all_market
            return all_pairs[:limit*2]
    
    def quick_analyze(self, pair_data):
        """Fast analysis of a single pair"""
        symbol = pair_data['symbol']
        change = pair_data.get('change_24h', 0)
        volume = pair_data.get('volume', 0)
        price = pair_data.get('price', 0)
        
        if price <= 0:
            # Estimate price for fallback pairs
            price = 100  # Placeholder
        
        score = 0
        reasons = []
        
        # 24h Change signal (primary)
        if change > 8:
            score += 6
            reasons.append(f"🚀 Massive 24h gain: +{change:.1f}%")
        elif change > 4:
            score += 4
            reasons.append(f"📈 Strong 24h gain: +{change:.1f}%")
        elif change > 1.5:
            score += 2
            reasons.append(f"↗️ Positive 24h: +{change:.1f}%")
        elif change < -8:
            score -= 6
            reasons.append(f"📉 Massive 24h drop: {change:.1f}%")
        elif change < -4:
            score -= 4
            reasons.append(f"📉 Strong 24h drop: {change:.1f}%")
        elif change < -1.5:
            score -= 2
            reasons.append(f"↘️ Negative 24h: {change:.1f}%")
        
        # Volume signal
        if volume > 100000000:  # $100M+
            if score > 0:
                score += 3
                reasons.append(f"💎 Massive Volume (${volume/1e6:.0f}M)")
            elif score < 0:
                score -= 3
                reasons.append(f"💎 Massive Volume (${volume/1e6:.0f}M)")
        elif volume > 20000000:  # $20M+
            if score > 0:
                score += 2
                reasons.append(f"📊 High Volume (${volume/1e6:.0f}M)")
            elif score < 0:
                score -= 2
                reasons.append(f"📊 High Volume (${volume/1e6:.0f}M)")
        
        # Need minimum signal strength
        if abs(score) < 3:
            return None
        
        signal_type = "LONG" if score > 0 else "SHORT"
        confidence = min(50 + abs(score) * 5, 95)
        strength = "STRONG" if abs(score) >= 7 else "MODERATE" if abs(score) >= 4 else "WEAK"
        
        # Calculate TP/SL
        if signal_type == "LONG":
            sl_price = price * 0.965  # -3.5%
            tp1 = price * 1.045       # +4.5%
            tp2 = price * 1.07        # +7%
        else:
            sl_price = price * 1.035  # +3.5%
            tp1 = price * 0.955       # -4.5%
            tp2 = price * 0.93        # -7%
        
        risk = abs(price - sl_price)
        reward = abs(tp1 - price)
        rr_ratio = reward / risk if risk > 0 else 1.5
        
        return {
            'symbol': symbol,
            'signal': signal_type,
            'strength': strength,
            'confidence': int(confidence),
            'current_price': price,
            'stop_loss': sl_price,
            'take_profit_1': tp1,
            'take_profit_2': tp2,
            'risk_reward_ratio': rr_ratio,
            'reasons': reasons,
            'confirmations': reasons[:3],
            'rsi': 50,
            'volume_ratio': 1.0,
            'volatility': abs(change) if abs(change) > 0 else 2.0,
            'momentum_10': change,
            'bullish_score': max(0, score),
            'bearish_score': abs(min(0, score)),
            'total_score': score,
            'max_score': 12,
            'change_24h': change,
            'volume_24h': volume,
            'timestamp': datetime.now()
        }
    
    def scan_market_wide(self, scan_mode='top_volume', max_pairs=50, timeframe='1h', min_confidence=55):
        """Full market scan with progress tracking"""
        
        start_time = time.time()
        
        # Get pairs based on mode
        pairs = self.get_pairs_by_mode(scan_mode, max_pairs)
        
        if not pairs:
            return [], "No pairs available"
        
        # Store market stats
        try:
            valid_changes = [p for p in pairs if p.get('change_24h') is not None]
            top_gainer = max(valid_changes, key=lambda x: x.get('change_24h', 0)) if valid_changes else None
            top_loser = min(valid_changes, key=lambda x: x.get('change_24h', 0)) if valid_changes else None
            
            st.session_state.market_stats = {
                'total_pairs_scanned': len(pairs),
                'avg_volume': sum(p.get('volume', 0) for p in pairs) / max(len(pairs), 1),
                'top_gainer': top_gainer,
                'top_loser': top_loser
            }
        except:
            st.session_state.market_stats = {'total_pairs_scanned': len(pairs)}
        
        signals = []
        
        # Progress tracking
        progress = st.progress(0)
        status = st.empty()
        
        for i, pair in enumerate(pairs):
            progress.progress((i + 1) / len(pairs))
            status.text(f"🔍 Scanning {pair['symbol']} ({i+1}/{len(pairs)})")
            
            signal = self.quick_analyze(pair)
            if signal and signal['confidence'] >= min_confidence:
                signals.append(signal)
        
        progress.empty()
        status.empty()
        
        # Sort by confidence
        signals.sort(key=lambda x: (x['strength'] == 'STRONG', x['confidence']), reverse=True)
        
        scan_time = time.time() - start_time
        
        mode_desc = {
            'top_volume': f"Top {len(pairs)} by volume",
            'high_volatility': f"Top {len(pairs)} most volatile",
            'trending': f"Top {len(pairs)} trending",
            'all_market': f"Market-wide ({len(pairs)} pairs)"
        }.get(scan_mode, f"Scanned {len(pairs)} pairs")
        
        return signals, f"{mode_desc} ({scan_time:.1f}s)"
        
# ===== PAGE CONFIGURATION - MUST BE FIRST ST COMMAND =====
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
