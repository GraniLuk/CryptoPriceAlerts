from opentelemetry import metrics
from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

import os

# Load connection string from environment
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

# Initialize the exporter
exporter = AzureMonitorMetricExporter(connection_string=connection_string)

# Create a metric reader
reader = PeriodicExportingMetricReader(exporter)

# Set up the meter provider
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

# Create a meter
meter = metrics.get_meter(__name__)


def log_custom_metric(name, value, attributes=None):
    gauge = meter.create_gauge(name)
    gauge.set(value, attributes or {})
