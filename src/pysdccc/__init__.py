"""Python wrapper to the sdccc tool for testing SDC devices."""

from pysdccc._download import download, download_async, is_downloaded, is_downloaded_async
from pysdccc._result_parser import TestCase, TestSuite
from pysdccc._runner import (
    DEFAULT_STORAGE_DIRECTORY,
    SdcccRunner,
    SdcccRunnerAsync,
    check_requirements,
)

__version__ = '0.0.0'

__all__ = [
    'DEFAULT_STORAGE_DIRECTORY',
    'SdcccRunner',
    'SdcccRunnerAsync',
    'TestCase',
    'TestSuite',
    'check_requirements',
    'download',
    'download_async',
    'is_downloaded',
    'is_downloaded_async',
]
