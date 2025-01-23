from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from azure.monitor.opentelemetry import AzureMonitorMetricExporter

import os

# Load connection string from environment
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

# Create the Azure Monitor exporter
exporter = AzureMonitorMetricExporter.from_connection_string(connection_string)

# Set up the OpenTelemetry MeterProvider
reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)  # Exports every minute
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

# Get a meter to create and record metrics
meter = metrics.get_meter("custom-metrics")

# Create a metric instrument
ratio_metric = meter.create_observable_gauge(
    name="custom.ratio.metric",
    description="Tracks the ratio for a specific symbol pair",
    callbacks=[]
)

# Function to observe and record ratio
def log_custom_metric(symbol1, symbol2, ratio):
    ratio_metric.add_callback(lambda: ratio)  # Push ratio dynamically
    print(f"Logged custom metric: Ratio for {symbol1}/{symbol2} = {ratio}")