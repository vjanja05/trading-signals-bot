@"
# 🤖 AI Trading Signals Bot

Premium trading signals bot with 25 USDT BEP20 payment system.

## Features
- Real-time AI trading signals for multiple cryptocurrencies
- 25 USDT BEP20 payment for 30 days access
- Telegram integration for payment verification
- Multiple timeframes (15m, 1h, 4h, 1d)
- Entry, Stop Loss, and Take Profit levels
- Risk/Reward analysis

## Setup
1. Copy `.env.example` to `.env` and add your credentials
2. Install requirements: `pip install -r requirements.txt`
3. Run: `streamlit run app.py`

## Technologies Used
- Streamlit
- CCXT (Binance API)
- Technical Analysis Library (ta)
- Plotly for charts
- Telegram Bot API
"@ | Out-File -FilePath README.md -Encoding utf8