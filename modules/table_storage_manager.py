"""
Azure Table Storage Manager - Replaces SQLite for persistent storage
"""

from azure.data.tables import TableServiceClient, TableEntity
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import logging
import os

class TableStorageManager:
    def __init__(self):
        """Initialize Azure Table Storage connection"""
        connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING not configured")
        
        self.table_service = TableServiceClient.from_connection_string(connection_string)
        self.table_name = "TrackingData"
        
        # Create table if it doesn't exist
        try:
            self.table_client = self.table_service.create_table_if_not_exists(self.table_name)
        except Exception:
            self.table_client = self.table_service.get_table_client(self.table_name)
        
        logging.info("✓ Table Storage initialized")
    
    def add_new_tracking_numbers(self, excel_data: Dict[str, Dict[str, Any]]) -> int:
        """Add new tracking numbers that don't exist in storage"""
        new_count = 0
        
        for tracking_number, data in excel_data.items():
            try:
                # Check if exists
                existing = self.table_client.get_entity(
                    partition_key="tracking",
                    row_key=tracking_number
                )
            except:
                # Doesn't exist, create it
                entity = {
                    'PartitionKey': 'tracking',
                    'RowKey': tracking_number,
                    'tracking_number': tracking_number,
                    'planned_pickup_date': data.get('planned_pickup_date').isoformat() if data.get('planned_pickup_date') else None,
                    'destination': data.get('destination', ''),
                    'reference_number': data.get('reference_number', ''),
                    'shipper_info': data.get('shipper_info', ''),
                    'internal_status': 'Pending API Call',
                    'created_at': datetime.now().isoformat()
                }
                
                self.table_client.create_entity(entity)
                new_count += 1
        
        return new_count
    
    def get_active_tracking_numbers(self, max_pickup_date: date) -> List[Dict[str, Any]]:
        """Get tracking numbers that need updates"""
        query_filter = f"PartitionKey eq 'tracking' and planned_pickup_date le '{max_pickup_date.isoformat()}'"
        
        entities = self.table_client.query_entities(query_filter)
        
        results = []
        for entity in entities:
            # Skip delivered items
            status = entity.get('internal_status', '').lower()
            if 'delivered' not in status:
                results.append(dict(entity))
        
        return results
    
    def update_tracking_record(self, tracking_number: str, processed_data: Dict) -> None:
        """Update tracking record with latest information"""
        try:
            # Get existing entity
            entity = self.table_client.get_entity(
                partition_key="tracking",
                row_key=tracking_number
            )
            
            # Update fields
            entity['ups_status'] = processed_data['ups_status']
            entity['internal_status'] = processed_data['internal_status']
            entity['estimated_delivery_date'] = processed_data.get('estimated_delivery_date')
            entity['actual_delivery_date'] = processed_data.get('actual_delivery_date')
            entity['actual_delivery_time'] = processed_data.get('actual_delivery_time')
            entity['last_updated'] = datetime.now().isoformat()
            entity['api_call_count'] = entity.get('api_call_count', 0) + 1
            
            # Calculate days
            if entity.get('planned_pickup_date'):
                pickup_date = datetime.fromisoformat(entity['planned_pickup_date']).date()
                today = date.today()
                entity['days_until_pickup'] = (pickup_date - today).days if pickup_date > today else 0
                entity['days_since_pickup'] = (today - pickup_date).days if pickup_date <= today else 0
            
            # Update in storage
            self.table_client.update_entity(entity, mode='replace')
            
        except Exception as e:
            logging.error(f"Error updating {tracking_number}: {str(e)}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about the database"""
        all_entities = list(self.table_client.list_entities())
        
        total = len(all_entities)
        delivered = sum(1 for e in all_entities if 'delivered' in e.get('internal_status', '').lower())
        active = total - delivered
        
        last_update = max(
            (e.get('last_updated', '') for e in all_entities),
            default=None
        )
        
        return {
            "total_records": total,
            "active_shipments": active,
            "delivered_shipments": delivered,
            "last_update": last_update
        }
