import azure.functions as func
import json
import logging
from datetime import datetime

from shared_code.migration import migrate_existing_alerts_to_table
from shared_code.table_storage import AlertTableStorage
from shared_code.utils import get_alerts_from_azure
from telegram_logging_handler import app_logger


async def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to check migration status and optionally trigger migration
    
    GET /api/migrate_alerts - Check migration status
    POST /api/migrate_alerts - Trigger migration
    """
    app_logger.info('Migration endpoint called')
    
    try:
        if req.method == 'GET':
            # Check migration status
            return await check_migration_status()
        elif req.method == 'POST':
            # Trigger migration
            return await trigger_migration()
        else:
            return func.HttpResponse(
                json.dumps({"error": "Only GET and POST methods are allowed"}),
                status_code=405,
                mimetype="application/json"
            )
            
    except Exception as e:
        app_logger.error(f"Error in migration endpoint: {e}")
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "details": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )


async def check_migration_status() -> func.HttpResponse:
    """Check current migration status"""
    try:
        # Check JSON file alerts
        json_alerts = get_alerts_from_azure("alerts.json")
        json_count = len(json_alerts) if json_alerts else 0
        
        # Check table storage alerts
        table_storage = AlertTableStorage()
        price_count = 0
        indicator_count = 0
        table_available = False
        
        if table_storage.service_client:
            table_available = True
            # Check price alerts table
            price_table = table_storage.get_table_client("pricealerts")
            if price_table:
                try:
                    price_entities = list(price_table.list_entities())
                    price_count = len(price_entities)
                except Exception as e:
                    app_logger.warning(f"Could not count price alerts: {e}")
            
            # Check indicator alerts table  
            indicator_table = table_storage.get_table_client("indicatoralerts")
            if indicator_table:
                try:
                    indicator_entities = list(indicator_table.list_entities())
                    indicator_count = len(indicator_entities)
                except Exception as e:
                    app_logger.warning(f"Could not count indicator alerts: {e}")
        
        # Determine migration status
        migration_needed = json_count > 0 and price_count == 0
        migration_completed = json_count > 0 and price_count > 0
        
        if not table_available:
            status = "TABLE_STORAGE_UNAVAILABLE"
            message = "Azure Table Storage is not available - check configuration"
        elif migration_needed:
            status = "MIGRATION_NEEDED"
            message = f"Migration required: {json_count} alerts in JSON, {price_count} in table storage"
        elif migration_completed:
            status = "MIGRATION_COMPLETED"
            message = f"Migration completed: {price_count} price alerts, {indicator_count} indicator alerts in table storage"
        elif json_count == 0 and price_count == 0:
            status = "NO_ALERTS"
            message = "No alerts found (fresh installation or no alerts created yet)"
        else:
            status = "USING_TABLE_STORAGE"
            message = f"Using table storage: {price_count} price alerts, {indicator_count} indicator alerts"
        
        response_data = {
            "status": status,
            "message": message,
            "details": {
                "json_alerts_count": json_count,
                "table_price_alerts_count": price_count,
                "table_indicator_alerts_count": indicator_count,
                "migration_needed": migration_needed,
                "migration_completed": migration_completed,
                "table_storage_available": table_available
            },
            "timestamp": datetime.now().isoformat(),
            "actions": {
                "check_status": "GET /api/migrate_alerts",
                "trigger_migration": "POST /api/migrate_alerts"
            }
        }
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        app_logger.error(f"Error checking migration status: {e}")
        return func.HttpResponse(
            json.dumps({
                "error": "Failed to check migration status",
                "details": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )


async def trigger_migration() -> func.HttpResponse:
    """Trigger the migration process"""
    try:
        app_logger.info("Triggering migration...")
        
        # Check if table storage is available
        table_storage = AlertTableStorage()
        if not table_storage.service_client:
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "message": "Azure Table Storage not available - check configuration",
                    "error": "TABLE_STORAGE_UNAVAILABLE"
                }),
                status_code=503,
                mimetype="application/json"
            )
        
        # Check if migration is needed first
        json_alerts = get_alerts_from_azure("alerts.json")
        json_count = len(json_alerts) if json_alerts else 0
        
        if json_count == 0:
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "message": "No alerts found in JSON file - migration not needed",
                    "json_alerts_count": json_count
                }),
                status_code=200,
                mimetype="application/json"
            )
        
        # Run the migration
        app_logger.info(f"Starting migration of {json_count} alerts...")
        
        # Capture migration output
        migration_start = datetime.now()
        try:
            migrate_existing_alerts_to_table()
            migration_success = True
            migration_error = None
        except Exception as migration_exception:
            migration_success = False
            migration_error = str(migration_exception)
            app_logger.error(f"Migration function failed: {migration_exception}")
        
        migration_end = datetime.now()
        migration_duration = (migration_end - migration_start).total_seconds()
        
        if not migration_success:
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "message": "Migration failed during execution",
                    "error": migration_error,
                    "duration_seconds": migration_duration
                }),
                status_code=500,
                mimetype="application/json"
            )
        
        # Verify migration success
        price_count = 0
        indicator_count = 0
        
        price_table = table_storage.get_table_client("pricealerts")
        if price_table:
            try:
                price_entities = list(price_table.list_entities())
                price_count = len(price_entities)
            except Exception as e:
                app_logger.warning(f"Could not verify price alerts after migration: {e}")
        
        indicator_table = table_storage.get_table_client("indicatoralerts")
        if indicator_table:
            try:
                indicator_entities = list(indicator_table.list_entities())
                indicator_count = len(indicator_entities)
            except Exception as e:
                app_logger.warning(f"Could not count indicator alerts after migration: {e}")
        
        app_logger.info(f"Migration completed: {price_count} alerts in table storage")
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "message": "Migration completed successfully",
                "details": {
                    "json_alerts_migrated": json_count,
                    "table_price_alerts_count": price_count,
                    "table_indicator_alerts_count": indicator_count,
                    "migration_timestamp": migration_end.isoformat(),
                    "duration_seconds": migration_duration
                }
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        app_logger.error(f"Migration endpoint failed: {e}")
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "message": "Migration endpoint failed",
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
