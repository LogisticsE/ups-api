"""
Data Processor - Process raw UPS API responses into structured format
Determines internal status based on UPS codes and business rules
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, date

class DataProcessor:
    def __init__(self):
        """Initialize data processor"""
        pass
    
    def process_tracking_data(self, tracking_number: str, raw_data: Any, excel_data: Dict) -> Dict:
        """
        Process raw UPS API response into structured format
        
        Args:
            tracking_number: The tracking number
            raw_data: Raw response from UPS API
            excel_data: Data from Excel for this tracking number
            
        Returns:
            Processed data dictionary ready for database
        """
        
        # Handle error responses (string instead of dict)
        if isinstance(raw_data, str):
            logging.warning(f"UPS API returned error for {tracking_number}: {raw_data}")
            return {
                'ups_status': 'API Error',
                'internal_status': 'API Error',
                'estimated_delivery_date': None,
                'actual_delivery_date': None,
                'actual_delivery_time': None
            }
        
        # Handle None or empty response
        if not raw_data or not isinstance(raw_data, dict):
            return {
                'ups_status': 'No Response',
                'internal_status': 'No Tracking Data',
                'estimated_delivery_date': None,
                'actual_delivery_date': None,
                'actual_delivery_time': None
            }
        
        try:
            # Extract tracking response
            track_response = raw_data.get('trackResponse', {})
            
            # Check if shipment data exists
            if not track_response or 'shipment' not in track_response:
                logging.warning(f"No trackResponse for {tracking_number}")
                return {
                    'ups_status': 'No Tracking Info',
                    'internal_status': 'Label Created - Not in System',
                    'estimated_delivery_date': None,
                    'actual_delivery_date': None,
                    'actual_delivery_time': None
                }
            
            shipments = track_response.get('shipment', [])
            
            # Check if shipment array is empty
            if not shipments or len(shipments) == 0:
                logging.warning(f"Empty shipment array for {tracking_number}")
                return {
                    'ups_status': 'No Tracking Info',
                    'internal_status': 'Label Created - Not Scanned',
                    'estimated_delivery_date': None,
                    'actual_delivery_date': None,
                    'actual_delivery_time': None
                }
            
            shipment = shipments[0]
            
            # Check if package data exists
            packages = shipment.get('package', [])
            if not packages or len(packages) == 0:
                logging.warning(f"Empty package array for {tracking_number}")
                return {
                    'ups_status': 'No Package Info',
                    'internal_status': 'Label Created - Not Scanned',
                    'estimated_delivery_date': None,
                    'actual_delivery_date': None,
                    'actual_delivery_time': None
                }
            
            package = packages[0]
            
            # Get current status
            current_status = package.get('currentStatus', {})
            if not current_status:
                logging.warning(f"No currentStatus for {tracking_number}")
                return {
                    'ups_status': 'Status Unknown',
                    'internal_status': 'In Transit - Status Unknown',
                    'estimated_delivery_date': None,
                    'actual_delivery_date': None,
                    'actual_delivery_time': None
                }
            
            status_type = current_status.get('type', '')
            status_code = current_status.get('code', '')
            status_description = current_status.get('description', '')
            
            # Get delivery information
            delivery_date = package.get('deliveryDate', [{}])[0] if package.get('deliveryDate') else {}
            delivery_time = package.get('deliveryTime', {})
            
            # Extract dates
            actual_delivery_date = delivery_date.get('date') if delivery_date else None
            actual_delivery_time = delivery_time.get('endTime') if delivery_time else None
            
            # Get estimated delivery
            estimated_delivery = None
            if 'rescheduledDeliveryDate' in shipment:
                estimated_delivery = shipment['rescheduledDeliveryDate']
            elif 'scheduledDeliveryDate' in shipment:
                estimated_delivery = shipment['scheduledDeliveryDate']
            
            # Determine internal status
            internal_status = self._determine_internal_status(
                status_code,
                status_type,
                status_description,
                actual_delivery_date,
                excel_data
            )
            
            # Build UPS status string
            ups_status_str = ''
            if status_code and status_description:
                ups_status_str = f"{status_code} - {status_description}"
            elif status_description:
                ups_status_str = status_description
            elif status_code:
                ups_status_str = f"Code: {status_code}"
            else:
                ups_status_str = 'Status Available'
            
            logging.info(f"✓ Processed {tracking_number}: {internal_status} | {ups_status_str}")
            
            return {
                'ups_status': ups_status_str,
                'internal_status': internal_status,
                'estimated_delivery_date': estimated_delivery,
                'actual_delivery_date': actual_delivery_date,
                'actual_delivery_time': actual_delivery_time
            }
            
        except Exception as e:
            logging.error(f"Error processing tracking data for {tracking_number}: {str(e)}")
            return {
                'ups_status': 'Processing Error',
                'internal_status': 'Data Processing Error',
                'estimated_delivery_date': None,
                'actual_delivery_date': None,
                'actual_delivery_time': None
            }
    
    def _determine_internal_status(
        self, 
        status_code: str, 
        status_type: str,
        status_description: str,
        actual_delivery_date: Optional[str],
        excel_data: Dict
    ) -> str:
        """
        Determine internal status based on UPS status codes and business rules
        
        Args:
            status_code: UPS status code
            status_type: UPS status type
            status_description: UPS status description
            actual_delivery_date: Actual delivery date if delivered
            excel_data: Original Excel data for this tracking number
            
        Returns:
            Internal status string for color coding in UI
        """
        
        # Convert to lowercase for comparison
        code = status_code.lower() if status_code else ''
        type_lower = status_type.lower() if status_type else ''
        desc = status_description.lower() if status_description else ''
        
        # Priority 1: Delivered
        if actual_delivery_date or 'delivered' in desc or 'delivered' in type_lower:
            return 'Delivered'
        
        # Priority 2: Delivery attempt failed
        if 'delivery attempt' in desc or 'attempted' in desc:
            return 'Delivery Attempt Failed'
        
        # Priority 3: Out for delivery
        if 'out for delivery' in desc or code == 'od':
            return 'Out for Delivery'
        
        # Priority 4: Exception / Issues
        if 'exception' in desc or 'exception' in type_lower:
            return 'Exception - Action Required'
        
        if 'held' in desc or 'hold' in desc:
            return 'Held at Facility'
        
        # Priority 5: In transit
        if 'in transit' in desc or 'transit' in type_lower:
            return 'In Transit'
        
        if 'arrived' in desc or 'arrival' in desc:
            return 'Arrived at Facility'
        
        # Priority 6: Origin / Pickup
        if 'origin' in desc or 'picked up' in desc or 'pickup' in desc:
            return 'Picked Up - Origin'
        
        if 'manifested' in desc or 'manifest' in desc:
            return 'Manifest Received'
        
        # Priority 7: Label created but not scanned
        if 'label' in desc or 'created' in desc:
            return 'Label Created - Not Scanned'
        
        # Default: Unknown with some info
        if status_code or status_description:
            return f'In Transit - {status_code}' if status_code else 'In Transit - Status Unknown'
        
        return 'Unknown Status'