"""
Azure Function App - UPS Tracking Updater
Runs every hour to update tracking information
"""

import azure.functions as func
import logging
from datetime import datetime, timedelta
import sys
import os


# Add modules folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

from database_manager import DatabaseManager
from excel_reader import ExcelReader
from ups_tracker import UPSTracker
from data_processor import DataProcessor

app = func.FunctionApp()

@app.timer_trigger(
    schedule="0 0 * * * *",  # Every hour at minute 0
    arg_name="timer", 
    run_on_startup=False,
    use_monitor=False
)
def hourly_tracking_update(timer: func.TimerRequest) -> None:
    """
    Main function that runs hourly to update tracking information
    
    Process:
    1. Check for new tracking numbers in Excel
    2. Add new numbers to database
    3. Filter active tracking numbers (not delivered, pickup date <= today)
    4. Call UPS API for each active tracking number
    5. Update database with latest tracking information
    """
    
    timestamp = datetime.now().isoformat()
    logging.info(f"🚀 Tracking update started at {timestamp}")
    
    try:
        # Initialize components
        db = DatabaseManager()
        excel_reader = ExcelReader()
        ups_tracker = UPSTracker()
        processor = DataProcessor()
        
        # Step 1: Load tracking numbers from Excel
        logging.info("📊 Loading tracking numbers from Excel...")
        excel_data = excel_reader.load_tracking_numbers()
        logging.info(f"✓ Found {len(excel_data)} tracking numbers in Excel")
        
        # Step 2: Check for new tracking numbers and add to database
        logging.info("🔍 Checking for new tracking numbers...")
        new_count = db.add_new_tracking_numbers(excel_data)
        if new_count > 0:
            logging.info(f"✓ Added {new_count} new tracking numbers to database")
        else:
            logging.info("✓ No new tracking numbers found")
        
        # Step 3: Get active tracking numbers (constraints applied)
        today = datetime.now().date()
        logging.info("📋 Retrieving active tracking numbers...")
        active_numbers = db.get_active_tracking_numbers(max_pickup_date=today)
        logging.info(f"✓ Found {len(active_numbers)} active tracking numbers to update")
        
        if len(active_numbers) == 0:
            logging.info("✓ No tracking numbers require updates")
            return
        
        # Step 4: Call UPS API and update database
        logging.info("🔄 Updating tracking information from UPS API...")
        updated_count = 0
        error_count = 0
        
        # Process in batches of 50 for better performance
        batch_size = 50
        for i in range(0, len(active_numbers), batch_size):
            batch = active_numbers[i:i + batch_size]
            batch_numbers = [item['tracking_number'] for item in batch]
            
            logging.info(f"Processing batch {i//batch_size + 1} ({len(batch_numbers)} numbers)...")
            logging.info(f"📞 Calling UPS API for: {batch_numbers[:3]}...")  # Show first 3
            
            # Get tracking data from UPS API
            tracking_results = ups_tracker.get_tracking_data(batch_numbers)
            
            logging.info(f"✓ Got {len(tracking_results)} results from UPS API")
            
            # Process each result
            for tracking_number, raw_data in tracking_results.items():
                try:
                    # Process raw API data into structured format
                    processed_data = processor.process_tracking_data(
                        tracking_number, 
                        raw_data,
                        excel_data.get(tracking_number, {})
                    )
                    
                    # Update database
                    db.update_tracking_record(tracking_number, processed_data)
                    updated_count += 1
                    
                except Exception as e:
                    logging.error(f"✗ Error processing {tracking_number}: {str(e)}")
                    error_count += 1
        
        # Step 5: Log summary
        logging.info("=" * 60)
        logging.info(f"✅ Tracking update completed at {datetime.now().isoformat()}")
        logging.info(f"📊 Summary:")
        logging.info(f"   - Total in Excel: {len(excel_data)}")
        logging.info(f"   - New numbers added: {new_count}")
        logging.info(f"   - Active numbers: {len(active_numbers)}")
        logging.info(f"   - Successfully updated: {updated_count}")
        logging.info(f"   - Errors: {error_count}")
        logging.info("=" * 60)
        
    except Exception as e:
        logging.error(f"❌ Critical error in tracking update: {str(e)}")
        raise


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint for monitoring"""
    
    try:
        db = DatabaseManager()
        stats = db.get_database_stats()
        
        return func.HttpResponse(
            body=str({
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "database_stats": stats
            }),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        return func.HttpResponse(
            body=str({"status": "unhealthy", "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="trigger", methods=["POST"])
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Manually trigger the tracking update for testing"""
    
    timestamp = datetime.now().isoformat()
    logging.info(f"🎯 Manual trigger initiated at {timestamp}")
    
    try:
        # Call the hourly update function with None timer (manual trigger)
        hourly_tracking_update(None)
        
        return func.HttpResponse(
            body=f"✅ Tracking update completed at {timestamp}! Check logs for details.",
            status_code=200
        )
    except Exception as e:
        logging.error(f"❌ Manual trigger failed: {str(e)}")
        return func.HttpResponse(
            body=f"❌ Error: {str(e)}",
            status_code=500
        )