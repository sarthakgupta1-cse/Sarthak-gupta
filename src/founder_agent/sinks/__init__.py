"""Where leads land."""

from .base import Sink
from .csv_ import CsvSink
from .gsheets import GoogleSheetsSink
from .sqlite import SqliteSink

SINKS = {"csv": CsvSink, "sqlite": SqliteSink, "gsheets": GoogleSheetsSink}

__all__ = ["SINKS", "CsvSink", "GoogleSheetsSink", "Sink", "SqliteSink"]
