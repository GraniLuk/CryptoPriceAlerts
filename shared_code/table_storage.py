from azure.data.tables import TableServiceClient, TableClient
from azure.core.credentials import AzureNamedKeyCredential
import os
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional
from telegram_logging_handler import app_logger

class AlertTableStorage:
    """Central class for managing all Azure Table Storage operations"""
    
    def __init__(self):
        self.account_name = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT")
        self.account_key = os.environ.get("AZURE_STORAGE_STORAGE_ACCOUNT_KEY")
        
        if not self.account_name or not self.account_key:
            app_logger.warning("Azure Storage credentials not set, some features may be limited")
            self.service_client = None
            return
        
        # Check if we're using Azurite (local development)
        if self.account_name == "devstoreaccount1":
            # Use Azurite endpoint for local development
            endpoint = "http://127.0.0.1:10002/devstoreaccount1"
            app_logger.info("Using Azurite (local storage emulator) for table storage")
        else:
            # Use Azure cloud endpoint
            endpoint = f"https://{self.account_name}.table.core.windows.net"
            app_logger.info(f"Using Azure cloud storage account: {self.account_name}")
            
        self.credential = AzureNamedKeyCredential(self.account_name, self.account_key)
        self.service_client = TableServiceClient(
            endpoint=endpoint,
            credential=self.credential
        )
        
        # Initialize all required tables
        self._initialize_tables()
        
    def _initialize_tables(self):
        """Initialize all required tables for the alert system"""
        if not self.service_client:
            app_logger.warning("Table service client not available, skipping table initialization")
            return
            
        tables = [
            "pricealerts",      # Migrated price alerts
            "indicatoralerts",  # New indicator-based alerts
            "candledata"        # Historical candle data for indicators
        ]
        
        for table_name in tables:
            self.create_table_if_not_exists(table_name)
        
    def get_table_client(self, table_name: str) -> Optional[TableClient]:
        """Get a table client for the specified table"""
        if not self.service_client:
            app_logger.error("Table service client not available")
            return None
        return self.service_client.get_table_client(table_name)
    
    def create_table_if_not_exists(self, table_name: str):
        """Create a table if it doesn't exist"""
        try:
            if not self.service_client:
                app_logger.warning(f"Cannot create table {table_name} - service client not available")
                return
                
            self.service_client.create_table_if_not_exists(table_name)
            app_logger.info(f"Table {table_name} ready")
        except Exception as e:
            app_logger.error(f"Error creating table {table_name}: {e}")
            
    def cleanup_old_candle_data(self, days_to_keep: int = 30):
        """Clean up old candle data to manage storage costs"""
        try:
            if not self.service_client:
                app_logger.warning("Cannot cleanup candle data - service client not available")
                return
                
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            candle_table = self.get_table_client("candledata")
            
            if not candle_table:
                return
            
            filter_query = f"Timestamp lt datetime'{cutoff_date.isoformat()}'"
            old_entities = candle_table.query_entities(filter_query)
            
            deleted_count = 0
            for entity in old_entities:
                candle_table.delete_entity(entity["PartitionKey"], entity["RowKey"])
                deleted_count += 1
                
            app_logger.info(f"Cleaned up {deleted_count} old candle records")
            
        except Exception as e:
            app_logger.error(f"Error cleaning up old candle data: {e}")
