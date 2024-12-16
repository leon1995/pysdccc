import io
import logging
import pathlib
import subprocess
import tempfile
import zipfile

import httpx

from pysdccc import _runner

logger = logging.getLogger("pysdccc.download")


def _download_to_stream(
    url: httpx.URL,
    stream: io.IOBase,
    proxy: httpx.Proxy | None = None,
    timeout: float | None = None,
) -> None:
    with httpx.stream("GET", url, follow_redirects=True, proxy=proxy, timeout=timeout) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            stream.write(chunk)


def download(
    url: httpx.URL | str,
    proxy: httpx.Proxy | None = None,
    timeout: float | None = None,
    output: pathlib.Path | None = None,
) -> pathlib.Path:
    """Download the specified version from the default URL to the specified `output` directory or the `runner.DEFAULT_STORAGE_DIRECTORY`.

    :param url: The parsed URL from which to download the executable.
    :param proxy: Optional proxy to be used for the download.
    :param timeout: The timeout in seconds for the download operation.
    :param output: The path to the directory where the downloaded executable will be extracted. If None, the default storage directory is used.
    """
    url = httpx.URL(url)
    logger.info("Downloading sdccc from %s.", url)
    with tempfile.NamedTemporaryFile("wb", suffix=".zip", delete=False) as temporary_file:
        _download_to_stream(url, temporary_file, proxy=proxy, timeout=timeout)  # type: ignore[arg-type]
    output = output or _runner.DEFAULT_STORAGE_DIRECTORY
    logger.info("Extracting sdccc to %s.", output)
    with zipfile.ZipFile(temporary_file.name) as f:
        f.extractall(output)
    return _runner.get_exe_path(output)


def is_downloaded(version: str) -> bool:
    """Check if the SDCcc version is already downloaded.

    This function checks if the SDCcc executable is already downloaded.

    :return: True if the executable is already downloaded, False otherwise.
    """
    try:
        return _runner.SdcccRunner(pathlib.Path().absolute()).get_version() == version
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


async def _download_to_stream_async(
    url: httpx.URL,
    stream: io.IOBase,
    proxy: httpx.Proxy | None = None,
    timeout: float | None = None,
) -> None:
    client = httpx.AsyncClient(follow_redirects=True, proxy=proxy)
    async with client.stream("GET", url, timeout=timeout) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            stream.write(chunk)


async def download_async(
    url: httpx.URL | str,
    proxy: httpx.Proxy | None = None,
    timeout: float | None = None,
    output: pathlib.Path | None = None,
) -> pathlib.Path:
    url = httpx.URL(url)
    logger.info("Downloading sdccc from %s.", url)
    with tempfile.NamedTemporaryFile("wb", suffix=".zip", delete=False) as temporary_file:
        await _download_to_stream_async(url, temporary_file, proxy=proxy, timeout=timeout)  # type: ignore[arg-type]
    output = output or _runner.DEFAULT_STORAGE_DIRECTORY
    logger.info("Extracting sdccc to %s.", output)
    with zipfile.ZipFile(temporary_file.name) as f:
        f.extractall(output)
    return _runner.get_exe_path(output)


async def is_downloaded_async(version: str) -> bool:
    """Check if the SDCcc version is already downloaded.

    This function checks if the SDCcc executable is already downloaded.

    :return: True if the executable is already downloaded, False otherwise.
    """
    try:
        return await _runner.SdcccRunnerAsync(pathlib.Path().absolute()).get_version() == version
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
