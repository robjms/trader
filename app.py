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

# FIXED: Correct project root and file paths
PROJECT_ROOT = "/Users/robertsteinegger/Desktop/BevaixBot"
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

print(f"🔍 Loading .env from: {ENV_PATH} at {datetime.now().strftime('%H:%M:%S')}")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f"✅ .env loaded successfully from {ENV_PATH}")
else:
    print(f"❌ .env file not found at {ENV_PATH}")

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FIXED: Correct file paths that match Swift bot output
DASHBOARD_JSON_PATH = os.path.join(PROJECT_ROOT, "dashboard.json")
TRADE_LOG_PATH = os.path.join(PROJECT_ROOT, "Output", "trade_log.csv")
ALERTS_CSV_PATH = os.path.join(PROJECT_ROOT, "Output", "alerts.csv")

@app.route('/')
def home():
    return "BevaixBot Flask Server is Running! ✅"

@app.route('/sentiment', methods=['POST'])
def sentiment():
    """Sentiment endpoint for Swift bot"""
    try:
        data = request.get_json()
        pair = data.get('pair', 'BTC-USDT')
        # Return neutral sentiment score for testing
        sentiment_score = 0.1
        logger.info(f"📈 Sentiment request for {pair}: {sentiment_score}")
        return jsonify({"sentiment_score": sentiment_score}), 200
    except Exception as e:
        logger.error(f"Sentiment error: {e}")
        return jsonify({"sentiment_score": 0.0}), 200

@app.route('/new_dashboard')
def new_dashboard():
    return render_template('dashboard.html')

@app.route('/api/new_dashboard')
def api_new_dashboard():
    logger.info(f"🔄 [Dashboard API] Called at {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        # 1. LOAD LIVE DATA from Swift bot's dashboard.json
        dashboard_data = {}
        live_prices = {}
        balances = {"kucoin": 0.0, "bybit": 0.0}
        
        try:
            if os.path.exists(DASHBOARD_JSON_PATH):
                with open(DASHBOARD_JSON_PATH, 'r') as f:
                    dashboard_data = json.load(f)
                    
                balances = {
                    'kucoin': float(dashboard_data.get('kucoinBalance', 0.0)),
                    'bybit': float(dashboard_data.get('bybitBalance', 0.0))
                }
                
                # Extract live prices
                live_prices = dashboard_data.get('livePrices', {})
                
                logger.info(f"✅ [Dashboard] Loaded live data: {len(live_prices)} pairs, KuCoin=${balances['kucoin']:.2f}, Bybit=${balances['bybit']:.2f}")
            else:
                logger.warning(f"⚠️ [Dashboard] dashboard.json not found at {DASHBOARD_JSON_PATH}")
                
        except Exception as e:
            logger.error(f"❌ [Dashboard] Error loading dashboard.json: {e}")

        # 2. LOAD REAL TRADES from trade_log.csv
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
                    logger.info(f"✅ [Dashboard] Loaded {len(trades)} real trades")
                else:
                    logger.info("ℹ️ [Dashboard] Trade CSV is empty")
            else:
                logger.info(f"ℹ️ [Dashboard] No trade CSV found at {TRADE_LOG_PATH}")
                
        except Exception as e:
            logger.error(f"❌ [Dashboard] Trade load error: {e}")

        # 3. LOAD REAL ALERTS from alerts.csv
        alerts = []
        try:
            if os.path.exists(ALERTS_CSV_PATH):
                with open(ALERTS_CSV_PATH, 'r') as f:
                    csv_reader = csv.reader(f)
                    for row in csv_reader:
                        if len(row) >= 2:
                            alerts.append([row[0], row[1]])
                alerts = alerts[-15:] if alerts else []
                logger.info(f"✅ [Dashboard] Loaded {len(alerts)} real alerts")
            else:
                logger.info(f"ℹ️ [Dashboard] No alerts CSV found at {ALERTS_CSV_PATH}")
                
        except Exception as e:
            logger.error(f"❌ [Dashboard] Alert load error: {e}")

        # 4. CALCULATE REAL METRICS
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

        # 5. BUILD PER-PAIR SUMMARY
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
            
            for pair, data in pair_data.items():
                win_rate_pair = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0.0
                per_pair_summary.append({
                    "pair": pair,
                    "trades": data['trades'],
                    "win_rate": win_rate_pair,
                    "profit": data['profit'],
                    "fees": data['fees']
                })

        # 6. FORMAT LIVE PRICES for dashboard (use live_prices from Swift bot)
        formatted_prices = {}
        if live_prices:
            formatted_prices = live_prices
        else:
            # Only show fallback message, don't create fake data
            logger.warning("⚠️ [Dashboard] No live price data available from Swift bot")

        # 7. BUILD FINAL RESPONSE
        response = {
            "timestamp": datetime.now().isoformat(),
            "prices": formatted_prices,
            "balances": balances,
            "metrics": metrics,
            "trades": trades,
            "per_pair_summary": per_pair_summary,
            "alerts": alerts,
            "status": {
                "dashboard_json_exists": os.path.exists(DASHBOARD_JSON_PATH),
                "trade_log_exists": os.path.exists(TRADE_LOG_PATH),
                "alerts_csv_exists": os.path.exists(ALERTS_CSV_PATH),
                "live_pairs_count": len(formatted_prices),
                "total_pairs": len(os.environ.get('ACTIVE_PAIRS', '').split(','))
            }
        }

        logger.info(f"✅ [Dashboard] API SUCCESS: {total_trades} trades, {len(alerts)} alerts, {len(formatted_prices)} live prices at {datetime.now().strftime('%H:%M:%S')}")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"❌ [Dashboard] API ERROR: {str(e)} at {datetime.now().strftime('%H:%M:%S')}")
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
            "status": {"error": True}
        }), 200

@app.route('/debug/status')
def debug_status():
    """Debug endpoint to check file paths and status"""
    status = {
        "server_time": datetime.now().isoformat(),
        "project_root": PROJECT_ROOT,
        "dashboard_json_path": DASHBOARD_JSON_PATH,
        "dashboard_json_exists": os.path.exists(DASHBOARD_JSON_PATH),
        "trade_log_exists": os.path.exists(TRADE_LOG_PATH),
        "alerts_csv_exists": os.path.exists(ALERTS_CSV_PATH),
        "env_file_exists": os.path.exists(ENV_PATH),
        "active_pairs": os.environ.get('ACTIVE_PAIRS', 'Not found'),
    }
    return jsonify(status)

@app.route('/debug/dashboard-raw')
def debug_dashboard_raw():
    """Debug endpoint to see raw dashboard.json content"""
    try:
        if os.path.exists(DASHBOARD_JSON_PATH):
            with open(DASHBOARD_JSON_PATH, 'r') as f:
                data = json.load(f)
            return f"<pre>{json.dumps(data, indent=2)}</pre>"
        else:
            return f"<pre>dashboard.json not found at: {DASHBOARD_JSON_PATH}</pre>"
    except Exception as e:
        return f"<pre>Error reading dashboard.json: {str(e)}</pre>"

if __name__ == '__main__':
    logger.info(f"🚀 [Flask] Starting BevaixBot Dashboard Server at {datetime.now().strftime('%H:%M:%S')}")
    logger.info(f"📁 [Flask] Project root: {PROJECT_ROOT}")
    logger.info(f"📄 [Flask] Dashboard JSON: {DASHBOARD_JSON_PATH}")
    logger.info(f"📊 [Flask] Trade log: {TRADE_LOG_PATH}")
    logger.info(f"🚨 [Flask] Alerts CSV: {ALERTS_CSV_PATH}")
    logger.info("📍 Routes available:")
    logger.info("   http://127.0.0.1:5001/new_dashboard")
    logger.info("   http://127.0.0.1:5001/api/new_dashboard")
    logger.info("   http://127.0.0.1:5001/sentiment")
    logger.info("   http://127.0.0.1:5001/debug/status")
    logger.info("   http://127.0.0.1:5001/debug/dashboard-raw")
    
    app.run(host='127.0.0.1', port=5001, debug=True)
