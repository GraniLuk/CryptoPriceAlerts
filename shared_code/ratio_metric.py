import os
import logging

logger = logging.getLogger(__name__)

# Try to import Azure Monitor dependencies, but don't fail if they're not available
try:
    from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    # Load connection string from environment
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if connection_string:
        # Initialize the exporter
        exporter = AzureMonitorMetricExporter(connection_string=connection_string)

        # Create a metric reader
        reader = PeriodicExportingMetricReader(exporter)

        # Set up the meter provider
        provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(provider)

        # Create a meter
        meter = metrics.get_meter(__name__)
        
        METRICS_AVAILABLE = True
        logger.info("Azure Monitor metrics initialized successfully")
    else:
        METRICS_AVAILABLE = False
        logger.warning("Application Insights connection string not found, metrics disabled")
        
except ImportError as e:
    METRICS_AVAILABLE = False
    logger.warning(f"Azure Monitor dependencies not available, metrics disabled: {e}")
except Exception as e:
    METRICS_AVAILABLE = False
    logger.warning(f"Failed to initialize Azure Monitor metrics: {e}")


def log_custom_metric(name, value, attributes=None):
    """Log a custom metric if Azure Monitor is available, otherwise log to console"""
    if METRICS_AVAILABLE:
        try:
            gauge = meter.create_gauge(name)
            gauge.set(value, attributes or {})
        except Exception as e:
            logger.error(f"Failed to log metric {name}: {e}")
    else:
        # Fallback to logging the metric
        logger.info(f"Metric {name}: {value} (attributes: {attributes})")
