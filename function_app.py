import azure.functions as func
import logging
from datetime import datetime, date
import json

# Import Table Storage Manager instead of SQLite
from modules.table_storage_manager import TableStorageManager
from modules.excel_reader import ExcelReader
from modules.ups_tracker import UPSTracker
from modules.data_processor import DataProcessor

app = func.FunctionApp()

@app.function_name(name="hourly_tracking_update")
@app.timer_trigger(schedule="0 0 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False) 
def hourly_tracking_update(myTimer: func.TimerRequest) -> None:
    """Main hourly tracking update function - runs every hour"""
    
    timestamp = datetime.now().isoformat()
    logging.info(f"🚀 Tracking update started at {timestamp}")
    
    try:
        # Initialize components with Table Storage
        db = TableStorageManager()
        excel_reader = ExcelReader()
        ups_tracker = UPSTracker()
        data_processor = DataProcessor()
        
        # Step 1: Load tracking numbers from Excel
        logging.info("📊 Loading tracking numbers from Excel...")
        excel_data = excel_reader.load_tracking_numbers()
        logging.info(f"✓ Found {len(excel_data)} tracking numbers in Excel")
        
        # Step 2: Add new tracking numbers to database
        logging.info("💾 Adding new tracking numbers to database...")
        new_count = db.add_new_tracking_numbers(excel_data)
        logging.info(f"✓ Added {new_count} new tracking numbers")
        
        # Step 3: Get active tracking numbers that need updates
        today = date.today()
        active_records = db.get_active_tracking_numbers(max_pickup_date=today)
        logging.info(f"📦 Found {len(active_records)} active shipments to update")
        
        if not active_records:
            logging.info("✅ No active shipments to update")
            return
        
        # Step 4: Get UPS tracking data
        tracking_numbers = [record['tracking_number'] for record in active_records]
        logging.info(f"🔍 Querying UPS API for {len(tracking_numbers)} tracking numbers...")
        
        ups_data = ups_tracker.get_tracking_data(tracking_numbers)
        logging.info(f"✓ Received {len(ups_data)} responses from UPS")
        
        # Step 5: Process and update each tracking number
        success_count = 0
        error_count = 0
        
        for tracking_number, raw_data in ups_data.items():
            try:
                # Get corresponding Excel data
                excel_record = excel_data.get(tracking_number, {})
                
                # Process the UPS data
                processed_data = data_processor.process_tracking_data(
                    tracking_number=tracking_number,
                    raw_data=raw_data,
                    excel_data=excel_record
                )
                
                # Update database
                db.update_tracking_record(tracking_number, processed_data)
                success_count += 1
                
            except Exception as e:
                logging.error(f"❌ Error processing {tracking_number}: {str(e)}")
                error_count += 1
        
        # Final summary
        logging.info(f"✅ Tracking update completed:")
        logging.info(f"   • Success: {success_count}")
        logging.info(f"   • Errors: {error_count}")
        logging.info(f"   • Total processed: {success_count + error_count}")
        
    except Exception as e:
        logging.error(f"❌ Critical error in tracking update: {str(e)}", exc_info=True)
        raise


@app.function_name(name="health_check")
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint - returns database stats"""
    
    try:
        db = TableStorageManager()
        stats = db.get_database_stats()
        
        response_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": stats,
            "version": "1.0.0"
        }
        
        return func.HttpResponse(
            body=json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        error_response = {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
        
        return func.HttpResponse(
            body=json.dumps(error_response, indent=2),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="manual_trigger")
@app.route(route="trigger", methods=["POST"])
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """Manual trigger for testing - runs the tracking update immediately"""
    
    try:
        logging.info("🔧 Manual trigger initiated")
        
        # Run the update function
        hourly_tracking_update(None)
        
        response_data = {
            "status": "success",
            "message": "Tracking update completed successfully",
            "timestamp": datetime.now().isoformat()
        }
        
        return func.HttpResponse(
            body=json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Manual trigger failed: {str(e)}")
        error_response = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        return func.HttpResponse(
            body=json.dumps(error_response, indent=2),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="get_tracking_status")
@app.route(route="tracking/{tracking_number}", methods=["GET"])
def get_tracking_status(req: func.HttpRequest) -> func.HttpResponse:
    """Get status of a specific tracking number"""
    
    tracking_number = req.route_params.get('tracking_number')
    
    if not tracking_number:
        return func.HttpResponse(
            body=json.dumps({"error": "Tracking number required"}),
            status_code=400,
            mimetype="application/json"
        )
    
    try:
        db = TableStorageManager()
        entity = db.table_client.get_entity(
            partition_key="tracking",
            row_key=tracking_number
        )
        
        return func.HttpResponse(
            body=json.dumps(dict(entity), indent=2, default=str),
            status_code=200,
            mimetype="application/json"
        )
            
    except Exception as e:
        logging.error(f"Error retrieving tracking status: {str(e)}")
        return func.HttpResponse(
            body=json.dumps({"error": "Tracking number not found"}),
            status_code=404,
            mimetype="application/json"
        )
