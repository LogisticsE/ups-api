"""
Database Manager - SQLite operations for tracking data
Maintains the 12-column structure from the existing application
"""

import sqlite3
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any
import os

class DatabaseManager:
    def __init__(self, db_path: str = "tracking_data.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self._create_tables()
    
    def _create_tables(self):
        """Create tracking table with 12-column structure"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create main tracking table (12 columns matching existing app)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracking_data (
                -- Columns 1-5: Excel data (original input)
                tracking_number TEXT PRIMARY KEY,
                planned_pickup_date DATE NOT NULL,
                destination TEXT,
                reference_number TEXT,
                shipper_info TEXT,
                
                -- Columns 6-8: Calculated fields
                days_until_pickup INTEGER,
                days_since_pickup INTEGER,
                estimated_delivery_date DATE,
                
                -- Columns 9-10: Status fields
                internal_status TEXT,
                ups_status TEXT,
                
                -- Columns 11-12: Delivery data
                actual_delivery_date DATE,
                actual_delivery_time TEXT,
                
                -- Metadata
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                api_call_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create audit log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracking_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT NOT NULL,
                status_change TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tracking_number) REFERENCES tracking_data(tracking_number)
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_planned_pickup 
            ON tracking_data(planned_pickup_date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_internal_status 
            ON tracking_data(internal_status)
        ''')
        
        conn.commit()
        conn.close()
        
        logging.info("✓ Database tables initialized")
    
    def add_new_tracking_numbers(self, excel_data: Dict[str, Dict[str, Any]]) -> int:
        """
        Add new tracking numbers from Excel that don't exist in database
        
        Args:
            excel_data: Dictionary with tracking_number as key, row data as value
            
        Returns:
            Number of new tracking numbers added
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        new_count = 0
        
        for tracking_number, data in excel_data.items():
            # Check if tracking number already exists
            cursor.execute(
                'SELECT tracking_number FROM tracking_data WHERE tracking_number = ?',
                (tracking_number,)
            )
            
            if cursor.fetchone() is None:
                # Insert new tracking number
                cursor.execute('''
                    INSERT INTO tracking_data (
                        tracking_number, planned_pickup_date, destination,
                        reference_number, shipper_info, internal_status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    tracking_number,
                    data.get('planned_pickup_date'),
                    data.get('destination', ''),
                    data.get('reference_number', ''),
                    data.get('shipper_info', ''),
                    'Pending API Call'
                ))
                new_count += 1
        
        conn.commit()
        conn.close()
        
        return new_count
    
    def get_active_tracking_numbers(self, max_pickup_date: date) -> List[Dict[str, Any]]:
        """
        Get tracking numbers that need updates based on constraints:
        1. NOT delivered
        2. planned_pickup_date <= max_pickup_date (today)
        
        Args:
            max_pickup_date: Maximum pickup date to include (typically today)
            
        Returns:
            List of dictionaries with tracking data
        """
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                tracking_number, planned_pickup_date, destination,
                reference_number, shipper_info, internal_status, ups_status,
                last_updated, api_call_count
            FROM tracking_data
            WHERE 
                -- Constraint 1: Not delivered
                (internal_status IS NULL OR LOWER(internal_status) NOT LIKE '%delivered%')
                -- Constraint 2: Pickup date is today or before
                AND planned_pickup_date <= ?
            ORDER BY planned_pickup_date ASC
        ''', (max_pickup_date,))
        
        results = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return results
    
    def update_tracking_record(self, tracking_number: str, processed_data: Dict) -> None:
        """Update tracking record with latest information"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the planned_pickup_date to calculate days_since_pickup
        cursor.execute(
            'SELECT planned_pickup_date FROM tracking_data WHERE tracking_number = ?',
            (tracking_number,)
        )
        result = cursor.fetchone()
        
        if not result:
            logging.warning(f"Tracking number {tracking_number} not found in database")
            conn.close()
            return
        
        planned_pickup_date = datetime.strptime(result[0], '%Y-%m-%d').date()
        today = datetime.now().date()
        
        # Calculate days
        days_until_pickup = (planned_pickup_date - today).days if planned_pickup_date > today else 0
        days_since_pickup = (today - planned_pickup_date).days if planned_pickup_date <= today else 0
        
        cursor.execute('''
            UPDATE tracking_data 
            SET ups_status = ?,
                internal_status = ?,
                estimated_delivery_date = ?,
                actual_delivery_date = ?,
                actual_delivery_time = ?,
                days_until_pickup = ?,
                days_since_pickup = ?,
                last_updated = ?,
                api_call_count = api_call_count + 1
            WHERE tracking_number = ?
        ''', (
            processed_data['ups_status'],
            processed_data['internal_status'],
            processed_data.get('estimated_delivery_date'),
            processed_data.get('actual_delivery_date'),
            processed_data.get('actual_delivery_time'),
            days_until_pickup,
            days_since_pickup,
            datetime.now(),
            tracking_number
        ))
        
        conn.commit()
        conn.close()
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about the database for monitoring"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total records
        cursor.execute('SELECT COUNT(*) FROM tracking_data')
        total = cursor.fetchone()[0]
        
        # Active (not delivered)
        cursor.execute('''
            SELECT COUNT(*) FROM tracking_data 
            WHERE internal_status IS NULL OR LOWER(internal_status) NOT LIKE '%delivered%'
        ''')
        active = cursor.fetchone()[0]
        
        # Delivered
        cursor.execute('''
            SELECT COUNT(*) FROM tracking_data 
            WHERE LOWER(internal_status) LIKE '%delivered%'
        ''')
        delivered = cursor.fetchone()[0]
        
        # Last update time
        cursor.execute('SELECT MAX(last_updated) FROM tracking_data')
        last_update = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_records": total,
            "active_shipments": active,
            "delivered_shipments": delivered,
            "last_update": last_update
        }