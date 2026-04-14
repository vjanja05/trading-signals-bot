#!/bin/bash
mkdir -p ~/.streamlit
echo "[server]
headless = true
port = $PORT
enableCORS = false
" > ~/.streamlit/config.toml
pip install --upgrade pip
pip install -r requirements.txt
