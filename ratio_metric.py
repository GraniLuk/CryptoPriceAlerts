# Use TelemetryClient to send custom metrics
from opencensus.ext.azure import telemetry_client

connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

telemetry_client = telemetry_client.TelemetryClient(connection_string)

def log_ratio_metric(symbol1, symbol2, ratio):
    metric_name = f"Ratio_{symbol1}_{symbol2}"
    telemetry_client.track_metric(name=metric_name, value=ratio)
    telemetry_client.flush()  # Immediately send the metric
