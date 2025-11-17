from flask import Flask, render_template, request, jsonify
from pytrends.request import TrendReq
import matplotlib
matplotlib.use('Agg')  # Important: Set backend before pyplot
import matplotlib.pyplot as plt
import pandas as pd
import time
import random
import os
import traceback
from datetime import datetime, timedelta

app = Flask(__name__)

# Global variable for rate limiting
last_request_time = 0

def generate_demo_data(keyword):
    """Generate realistic demo data when Google Trends fails"""
    # Create dates for the last 90 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create realistic trend data with some variation
    base_trend = [50, 55, 60, 65, 70, 75, 80, 85, 90, 85, 80, 75, 70, 65, 60]
    values = []
    
    for i in range(len(dates)):
        # Repeat the base trend pattern
        pattern_value = base_trend[i % len(base_trend)]
        # Add some random variation
        random_variation = random.randint(-10, 10)
        value = max(10, pattern_value + random_variation)  # Ensure minimum value of 10
        values.append(value)
    
    data = pd.DataFrame({
        'date': dates,
        keyword: values
    })
    data.set_index('date', inplace=True)
    
    return data

def get_trends_data(keyword):
    """Try to get real Google Trends data, fall back to demo data if it fails"""
    try:
        # Initialize pytrends
        pytrend = TrendReq(hl='en-US', tz=360, timeout=10)
        
        # Try different timeframes
        timeframes = ["now 7-d", "today 1-m", "today 3-m"]
        
        for timeframe in timeframes:
            try:
                print(f"Trying Google Trends with timeframe: {timeframe}")
                pytrend.build_payload([keyword], timeframe=timeframe)
                data = pytrend.interest_over_time()
                
                if not data.empty and keyword in data.columns and data[keyword].sum() > 0:
                    print(f"✅ Successfully got real data from Google Trends")
                    return data, timeframe, True
            except Exception as e:
                print(f"❌ Google Trends failed for {timeframe}: {e}")
                continue
        
        # If all Google Trends attempts fail, use demo data
        print("🔄 Using demo data as fallback")
        data = generate_demo_data(keyword)
        return data, "demo (last 3 months)", False
        
    except Exception as e:
        print(f"💥 All Google Trends attempts failed: {e}")
        # Fall back to demo data
        data = generate_demo_data(keyword)
        return data, "demo (last 3 months)", False

@app.route("/", methods=["GET", "POST"])
def index():
    global last_request_time
    results = None
    error = None
    is_demo_data = False

    if request.method == "POST":
        keyword = request.form.get("keyword", "").strip()

        if not keyword:
            error = "Please enter a keyword to search."
        else:
            try:
                current_time = time.time()
                
                # Rate limiting - wait at least 10 seconds between requests
                if current_time - last_request_time < 10:
                    wait_time = 10 - (current_time - last_request_time)
                    time.sleep(wait_time)
                    print(f"⏳ Waited {wait_time:.1f}s due to rate limit")

                # Get data (either real or demo)
                data, timeframe_used, is_real_data = get_trends_data(keyword)
                is_demo_data = not is_real_data

                if data is not None and not data.empty and keyword in data.columns:
                    # Ensure static directory exists
                    os.makedirs('static', exist_ok=True)
                    
                    # Plot graph
                    plt.figure(figsize=(12, 6))
                    plt.plot(data.index, data[keyword], linewidth=2, color="#4361ee")
                    
                    if is_real_data:
                        plt.title(f'Google Trends: "{keyword}"', fontsize=16, pad=20)
                    else:
                        plt.title(f'Demo Trend Data: "{keyword}"', fontsize=16, pad=20)
                        
                    plt.xlabel("Date")
                    plt.ylabel("Search Interest")
                    plt.grid(True, alpha=0.3)
                    plt.xticks(rotation=45)
                    plt.tight_layout()

                    # Save plot
                    plt.savefig("static/chart.png", dpi=100, bbox_inches="tight")
                    plt.close()

                    # Prepare table data
                    recent = data.tail(10).copy()
                    recent.reset_index(inplace=True)
                    recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")

                    results = recent[["date", keyword]].to_html(
                        classes="data-table",
                        index=False,
                        border=0,
                        header=["Date", "Search Interest"]
                    )
                    
                    print(f"✅ Successfully generated data for: {keyword}")
                    
                    # Add demo data notice to results
                    if is_demo_data:
                        demo_notice = """
                        <div class="info-box" style="margin-bottom: 1rem;">
                            <h3>📊 Demo Data</h3>
                            <p style="color: #4361ee; font-size: 0.9rem; margin: 0;">
                                <strong>Note:</strong> Showing demo data as Google Trends is currently unavailable. 
                                Real data will be shown when the service recovers.
                            </p>
                        </div>
                        """
                        results = demo_notice + results
                    
                else:
                    error = f"No trend data found for '{keyword}'.<br><br>"
                    error += "<strong>Possible reasons:</strong><br>"
                    error += "• Keyword is too niche or has no search volume<br>"
                    error += "• Google Trends API is temporarily unavailable<br>"
                    error += "• Try more common keywords like 'python', 'music', or 'travel'<br>"
                    error += "• Wait 10+ seconds between searches"

                # Update last request time
                last_request_time = time.time()

            except Exception as e:
                error = f"Error processing your request: {str(e)}<br>Please try again in 30 seconds."
                print(f"❌ Error: {e}")
                print(traceback.format_exc())

    return render_template("index.html", results=results, error=error)

@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({
        'status': 'success',
        'message': 'API is working correctly',
        'timestamp': time.time()
    })

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        keyword = request.form.get('keyword', '').strip()
        
        if not keyword:
            return jsonify({'error': 'Please enter a keyword'}), 400
        
        global last_request_time
        current_time = time.time()
        
        # Rate limiting
        if current_time - last_request_time < 10:
            wait_time = 10 - (current_time - last_request_time)
            time.sleep(wait_time)

        # Get data (either real or demo)
        data, timeframe_used, is_real_data = get_trends_data(keyword)

        if data is not None and not data.empty and keyword in data.columns:
            # Save chart
            os.makedirs('static', exist_ok=True)
            plt.figure(figsize=(12, 6))
            plt.plot(data.index, data[keyword], linewidth=2, color="#4361ee")
            
            if is_real_data:
                plt.title(f'Google Trends: "{keyword}"', fontsize=16, pad=20)
            else:
                plt.title(f'Demo Trend Data: "{keyword}"', fontsize=16, pad=20)
                
            plt.xlabel("Date")
            plt.ylabel("Search Interest")
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig("static/chart.png", dpi=100, bbox_inches="tight")
            plt.close()

            # Prepare JSON response
            result = {
                "dates": [str(d.date()) for d in data.index],
                "values": data[keyword].fillna(0).astype(int).tolist(),
                "timeframe_used": timeframe_used,
                "keyword": keyword,
                "is_demo_data": not is_real_data
            }
            
            last_request_time = time.time()
            return jsonify(result)
        else:
            return jsonify({
                'error': f'No trend data found for "{keyword}". Try more common keywords like "python", "music", or "travel".'
            }), 404

    except Exception as e:
        print(f"Error in analyze endpoint: {e}")
        return jsonify({
            'error': f'Server error: {str(e)}. Please try again later.'
        }), 500

if __name__ == "__main__":
    print("🚀 Starting Flask server...")
    print("📝 Open your browser and go to: http://127.0.0.1:5000")
    print("⏹️  To stop the server, press CTRL+C")
    app.run(debug=True, host='127.0.0.1', port=5000)