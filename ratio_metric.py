import os
from opencensus.ext.azure.metrics_exporter import new_metrics_exporter

connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
exporter = new_metrics_exporter(connection_string=connection_string)

def log_ratio_metric(symbol1, symbol2, ratio):
    metric_name = f"Ratio_{symbol1}_{symbol2}"
    exporter.add_metric(metric_name, ratio)
    exporter.export_metrics()
