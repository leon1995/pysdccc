"""Python wrapper to the sdccc tool for testing SDC devices."""

from pysdccc.result_parser import TestCase, TestSuite
from pysdccc.runner import (
    DEFAULT_STORAGE_DIRECTORY,
    MAX_REDIRECT_COUNT,
    SdcccRunner,
    check_requirements,
    download,
    local_path_from_url,
    parse_results,
)

__version__ = "0.0.0"

__all__ = [
    "TestSuite",
    "TestCase",
    "SdcccRunner",
    "DEFAULT_STORAGE_DIRECTORY",
    "MAX_REDIRECT_COUNT",
    "download",
    "local_path_from_url",
    "check_requirements",
    "parse_results",
]
