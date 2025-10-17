import azure.functions as func
import logging
from datetime import datetime
import sys
import os

# Add modules folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

app = func.FunctionApp()

@app.function_name(name="hourly_tracking_update")
@app.timer_trigger(schedule="0 0 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False) 
def hourly_tracking_update(myTimer: func.TimerRequest) -> None:
    """Main hourly tracking update function"""
    
    timestamp = datetime.now().isoformat()
    logging.info(f"🚀 Tracking update started at {timestamp}")
    
    try:
        from database_manager import DatabaseManager
        from excel_reader import ExcelReader
        from ups_tracker import UPSTracker
        from data_processor import DataProcessor
        
        # Your existing tracking logic here
        db = DatabaseManager()
        excel_reader = ExcelReader()
        
        logging.info("📊 Loading tracking numbers from Excel...")
        excel_data = excel_reader.load_tracking_numbers()
        logging.info(f"✓ Found {len(excel_data)} tracking numbers")
        
        logging.info("✅ Tracking update completed")
        
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        raise


@app.function_name(name="health_check")
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    return func.HttpResponse(
        body='{"status": "healthy", "timestamp": "' + datetime.now().isoformat() + '"}',
        status_code=200,
        mimetype="application/json"
    )


@app.function_name(name="manual_trigger")
@app.route(route="trigger", methods=["POST"])
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Manual trigger for testing"""
    try:
        hourly_tracking_update(None)
        return func.HttpResponse("✅ Tracking update completed!", status_code=200)
    except Exception as e:
        return func.HttpResponse(f"❌ Error: {str(e)}", status_code=500)
