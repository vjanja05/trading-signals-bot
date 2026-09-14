"""
worker.py — Autonomous payment verifier.

Runs on a schedule (see render.yaml: a Render Cron Job, every 5 minutes).
Independent of any user's browser session — this is what makes access
activation fully hands-off.

What it does each run:
  1. Expires any pending requests older than 2 hours (frees their unique
     amount slot for reuse).
  2. Pulls recent BEP20 USDT transfers into YOUR_WALLET from BscScan.
  3. Matches each transfer's exact amount against a pending request.
  4. On match: generates an access password, marks the request 'completed',
     sets access_expires_at = now() + 30 days.

Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, YOUR_WALLET,
BSCSCAN_API_KEY.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

import requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
YOUR_WALLET = os.environ["YOUR_WALLET"].lower()
BSCSCAN_API_KEY = os.environ["BSCSCAN_API_KEY"]

# Binance-Peg USDT (BEP20) contract on BSC mainnet — 18 decimals.
USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
USDT_DECIMALS = 18

# Amounts can drift by fractions of a cent due to gas/rounding on some
# wallets — allow a tiny tolerance when matching.
AMOUNT_TOLERANCE = 0.00005

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def expire_stale_requests():
    now_iso = datetime.now(timezone.utc).isoformat()
    sb.table("signal_access_requests") \
        .update({"status": "expired"}) \
        .eq("status", "pending") \
        .lt("request_expires_at", now_iso) \
        .execute()


def fetch_recent_usdt_transfers(limit=50):
    """Recent BEP20 USDT transfers INTO our wallet, newest first."""
    url = "https://api.bscscan.com/api"
    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": USDT_BEP20_CONTRACT,
        "address": YOUR_WALLET,
        "sort": "desc",
        "page": 1,
        "offset": limit,
        "apikey": BSCSCAN_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "1":
        return []

    transfers = []
    for tx in data.get("result", []):
        if tx.get("to", "").lower() != YOUR_WALLET:
            continue  # incoming only
        amount = int(tx["value"]) / (10 ** USDT_DECIMALS)
        transfers.append({
            "hash": tx["hash"],
            "amount": amount,
            "confirmations": int(tx.get("confirmations", 0)),
        })
    return transfers


def already_used(tx_hash):
    res = sb.table("signal_access_requests") \
        .select("id") \
        .eq("matched_tx_hash", tx_hash) \
        .execute()
    return len(res.data) > 0


def get_pending_requests():
    res = sb.table("signal_access_requests") \
        .select("*") \
        .eq("status", "pending") \
        .execute()
    return res.data


def activate_request(request_id, tx_hash):
    password = secrets.token_hex(4).upper()
    now = datetime.now(timezone.utc)
    sb.table("signal_access_requests") \
        .update({
            "status": "completed",
            "matched_tx_hash": tx_hash,
            "access_password": password,
            "access_expires_at": (now + timedelta(days=30)).isoformat(),
        }) \
        .eq("id", request_id) \
        .execute()
    return password


def run():
    expire_stale_requests()

    pending = get_pending_requests()
    if not pending:
        print("No pending requests.")
        return

    transfers = fetch_recent_usdt_transfers()
    print(f"Checked {len(transfers)} recent transfers against {len(pending)} pending requests.")

    for tx in transfers:
        # Require a couple confirmations before trusting it (avoids acting
        # on a transaction that could still be reorged out).
        if tx["confirmations"] < 3:
            continue
        if already_used(tx["hash"]):
            continue

        for req in pending:
            if abs(tx["amount"] - float(req["expected_amount"])) <= AMOUNT_TOLERANCE:
                password = activate_request(req["id"], tx["hash"])
                print(f"MATCHED: request {req['id']} <- tx {tx['hash']} -> password {password}")
                pending.remove(req)
                break


if __name__ == "__main__":
    run()
