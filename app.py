import os
import sys
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
import json
import logging
from datetime import datetime
import pandas as pd
import csv
import traceback

# Get project root (parent of Python directory)
PROJECT_ROOT = "/Users/robertsteinegger/Desktop/BevaixBot"
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

print(f"Loading .env from: {ENV_PATH} at {datetime.now().strftime('%H:%M:%S')}")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f"✅ .env loaded successfully from {ENV_PATH}")
else:
    print(f"❌ .env file not found at {ENV_PATH}")

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File paths
DASHBOARD_JSON_PATH = "dashboard.json"
TRADE_LOG_PATH = os.path.join("Output", "trade_log.csv")
ALERTS_CSV_PATH = os.path.join("Output", "alerts.csv")

@app.route('/')
def home():
    return "BevaixBot Flask Server is Running!"

@app.route('/sentiment', methods=['POST'])
def sentiment():
    """Sentiment endpoint for Swift bot"""
    try:
        data = request.get_json()
        pair = data.get('pair', 'BTC-USDT')
        # Return mock sentiment score
        sentiment_score = 0.1  # Neutral to slightly positive
        return jsonify({"sentiment_score": sentiment_score}), 200
    except Exception as e:
        logger.error(f"Sentiment error: {e}")
        return jsonify({"sentiment_score": 0.0}), 200

@app.route('/new_dashboard')
def new_dashboard():
    return render_template('dashboard.html')

@app.route('/api/new_dashboard')
def api_new_dashboard():
    logger.info(f"🔄 [Python] API called - returning REAL data at {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        # 1. LOAD REAL BALANCES FROM DASHBOARD.JSON
        balances = {"kucoin": 0.0, "bybit": 0.0}
        live_prices = {}
        real_pairs = []
        
        try:
            if os.path.exists(DASHBOARD_JSON_PATH):
                with open(DASHBOARD_JSON_PATH, 'r') as f:
                    dashboard_data = json.load(f)
                    
                    # Get real balances
                    balances['kucoin'] = float(dashboard_data.get('kucoinBalance', 0.0))
                    balances['bybit'] = float(dashboard_data.get('bybitBalance', 0.0))
                    
                    # Get real prices and pairs
                    if 'livePrices' in dashboard_data:
                        for price_entry in dashboard_data['livePrices']:
                            pair = price_entry.get('pair', '')
                            if pair:
                                real_pairs.append(pair)
                                live_prices[pair] = {
                                    "kucoin_spot": float(price_entry.get('kucoinSpot', 0.0)),
                                    "kucoin_futures": float(price_entry.get('kucoinFutures', 0.0)),
                                    "bybit_spot": float(price_entry.get('bybitSpot', 0.0)),
                                    "bybit_futures": float(price_entry.get('bybitFutures', 0.0))
                                }
                    
                    logger.info(f"✅ [Python] Loaded REAL data: KuCoin=${balances['kucoin']:.2f}, Bybit=${balances['bybit']:.2f}, Pairs={len(real_pairs)}")
            else:
                logger.warning(f"❌ [Python] dashboard.json not found at {DASHBOARD_JSON_PATH}")
        except Exception as e:
            logger.error(f"❌ [Python] Error loading dashboard.json: {e}")

        # 2. FALLBACK TO ENV PAIRS IF NO LIVE DATA
        if not real_pairs:
            env_pairs = os.getenv('ACTIVE_PAIRS', 'BTC-USDT,ETH-USDT,SOL-USDT,LINK-USDT,FLOKI-USDT,TON-USDT,NEAR-USDT,ARB-USDT,WIF-USDT,PEPE-USDT,BONK-USDT,SHIB-USDT,XRP-USDT,ADA-USDT,DOGE-USDT,AVAX-USDT,DOT-USDT,MATIC-USDT,SUI-USDT,APT-USDT,INJ-USDT,OP-USDT')
            real_pairs = [pair.strip() for pair in env_pairs.split(',')]
            logger.warning(f"⚠️ [Python] Using fallback pairs from .env: {len(real_pairs)} pairs")

        # 3. LOAD REAL TRADES
        trades = []
        try:
            if os.path.exists(TRADE_LOG_PATH):
                df = pd.read_csv(TRADE_LOG_PATH)
                if not df.empty:
                    for _, row in df.tail(20).iterrows():
                        trades.append([
                            str(row.get('timestamp', '')),
                            str(row.get('pair', '')),
                            str(row.get('strategy', '')),
                            str(row.get('exchange', '')),
                            float(row.get('spot_price', 0.0)),
                            float(row.get('futures_price', 0.0)),
                            float(row.get('trade_amount', 0.0)),
                            float(row.get('profit', 0.0)),
                            float(row.get('fees', 0.0))
                        ])
                    logger.info(f"✅ [Python] Loaded {len(trades)} real trades")
        except Exception as e:
            logger.error(f"❌ [Python] Error loading trades: {e}")

        # 4. LOAD REAL ALERTS
        alerts = []
        try:
            if os.path.exists(ALERTS_CSV_PATH):
                with open(ALERTS_CSV_PATH, 'r') as f:
                    csv_reader = csv.reader(f)
                    for row in csv_reader:
                        if len(row) >= 2:
                            alerts.append([row[0], row[1]])
                alerts = alerts[-15:] if alerts else []
                logger.info(f"✅ [Python] Loaded {len(alerts)} real alerts")
        except Exception as e:
            logger.error(f"❌ [Python] Error loading alerts: {e}")

        # 5. CALCULATE REAL METRICS
        total_profit = sum(float(trade[7]) for trade in trades) if trades else 0.0
        total_fees = sum(float(trade[8]) for trade in trades) if trades else 0.0
        total_trades = len(trades)
        win_rate = (sum(1 for trade in trades if float(trade[7]) > 0) / total_trades * 100) if total_trades > 0 else 0.0
        
        metrics = {
            "total_profit": total_profit,
            "total_fees": total_fees,
            "total_trades": total_trades,
            "win_rate": win_rate
        }

        # 6. GENERATE PER-PAIR SUMMARY FROM REAL DATA
        per_pair_summary = []
        if trades:
            pair_data = {}
            for trade in trades:
                pair = trade[1]
                profit = float(trade[7])
                fees = float(trade[8])
                
                if pair not in pair_data:
                    pair_data[pair] = {'trades': 0, 'profit': 0.0, 'fees': 0.0, 'wins': 0}
                
                pair_data[pair]['trades'] += 1
                pair_data[pair]['profit'] += profit
                pair_data[pair]['fees'] += fees
                if profit > 0:
                    pair_data[pair]['wins'] += 1
            
            for pair in real_pairs:  # Use all real pairs, not just traded ones
                data = pair_data.get(pair, {'trades': 0, 'profit': 0.0, 'fees': 0.0, 'wins': 0})
                win_rate_pair = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0.0
                per_pair_summary.append({
                    "pair": pair,
                    "trades": data['trades'],
                    "win_rate": win_rate_pair,
                    "profit": data['profit'],
                    "fees": data['fees']
                })

        # 7. BUILD RESPONSE WITH REAL DATA
        response = {
            "timestamp": datetime.now().isoformat(),
            "prices": live_prices,  # REAL PRICES FROM SWIFT BOT
            "balances": balances,   # REAL BALANCES FROM SWIFT BOT
            "metrics": metrics,
            "trades": trades,
            "per_pair_summary": per_pair_summary,
            "alerts": alerts,
            "active_pairs": real_pairs,  # REAL PAIRS FROM ENV
            "data_source": "live" if live_prices else "fallback"
        }

        logger.info(f"✅ [Python] API SUCCESS: {total_trades} trades, {len(alerts)} alerts, {len(live_prices)} live prices, {len(real_pairs)} pairs at {datetime.now().strftime('%H:%M:%S')}")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"❌ [Python] API ERROR: {str(e)} at {datetime.now().strftime('%H:%M:%S')}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return jsonify({
            "error": f"Server error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "prices": {},
            "balances": {"kucoin": 0.0, "bybit": 0.0},
            "metrics": {"total_profit": 0.0, "total_fees": 0.0, "total_trades": 0, "win_rate": 0.0},
            "trades": [],
            "per_pair_summary": [],
            "alerts": [],
            "data_source": "error"
        }), 200

@app.route('/debug/status')
def debug_status():
    """Debug endpoint"""
    status = {
        "server_time": datetime.now().isoformat(),
        "current_dir": os.getcwd(),
        "trade_log_exists": os.path.exists(TRADE_LOG_PATH),
        "alerts_csv_exists": os.path.exists(ALERTS_CSV_PATH),
        "dashboard_json_exists": os.path.exists(DASHBOARD_JSON_PATH),
        "env_file_exists": os.path.exists(".env"),
        "active_pairs_env": os.getenv('ACTIVE_PAIRS', 'Not found'),
        "routes": [rule.rule for rule in app.url_map.iter_rules()]
    }
    return jsonify(status)

@app.route('/debug/api')
def debug_api():
    """Test API directly"""
    try:
        response_data, status_code = api_new_dashboard()
        data = response_data.get_json()
        return f"<pre>{json.dumps(data, indent=2)}</pre>"
    except Exception as e:
        return f"<pre>Debug Error: {str(e)} at {datetime.now().strftime('%H:%M:%S')}</pre>"

if __name__ == '__main__':
    logger.info(f"🚀 [Python] Starting Flask Server at {datetime.now().strftime('%H:%M:%S')}")
    logger.info(f"📁 [Python] Working directory: {os.getcwd()}")
    logger.info(f"📄 [Python] .env file exists: {os.path.exists('.env')}")
    logger.info(f"💰 [Python] Active pairs from env: {os.getenv('ACTIVE_PAIRS', 'Not found')}")
    logger.info("📍 Routes available:")
    logger.info("   http://127.0.0.1:5001/new_dashboard")
    logger.info("   http://127.0.0.1:5001/api/new_dashboard")
    logger.info("   http://127.0.0.1:5001/sentiment")
    logger.info("   http://127.0.0.1:5001/debug/status")
    logger.info("   http://127.0.0.1:5001/debug/api")
    
    app.run(host='127.0.0.1', port=5001, debug=True)
