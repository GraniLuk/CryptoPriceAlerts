from opencensus.ext.azure.common import AzureMonitorContext
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.metrics_exporter import new_metrics_exporter
from opencensus.metrics.transport import get_exporter_thread
from opencensus.metrics import label_key, label_value, measure, metric, view, aggregation

from opencensus.stats import stats as stats_module
from opencensus.tags import tag_map as tag_map_module

from opencensus.ext.azure.metrics_exporter import MetricsExporter

# Use TelemetryClient to send custom metrics
from opencensus.ext.azure import telemetry_client

connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

telemetry_client = telemetry_client.TelemetryClient(connection_string)

def log_ratio_metric(symbol1, symbol2, ratio):
    metric_name = f"Ratio_{symbol1}_{symbol2}"
    telemetry_client.track_metric(name=metric_name, value=ratio)
    telemetry_client.flush()  # Immediately send the metric
