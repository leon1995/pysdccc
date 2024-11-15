"""Implements the runner for the SDCcc executable.

This module provides the `SdcccRunner` class to manage and execute the SDCcc tests. It handles the configuration,
requirements, and execution of the SDCcc executable, as well as parsing the test results.

Classes
-------

SdcccRunner
    Runner for the SDCcc tests.

Functions
---------

local_path_from_url(url: urllib.parse.ParseResult) -> pathlib.Path
    Get the local path where the version from the URL is stored.

download(url: urllib.parse.ParseResult, proxy: tuple[str, int] | None = None, timeout: int = 60) -> pathlib.Path
    Download the specified version from the default URL to a temporary directory.

check_requirements(provided: dict[str, dict[str, bool]], available: dict[str, dict[str, bool]]) -> None
    Check if the provided requirements are supported by the available requirements.

Usage
-----

.. code-block:: python

    from pysdccc import SdcccRunner
    import pathlib

    # Initialize the runner with the path to the SDCcc executable and the test run directory
    runner = SdcccRunner(
        exe=pathlib.Path("/absolute/path/to/sdccc-executable"),
        test_run_dir=pathlib.Path("/absolute/path/to/test-run-directory")
    )

    # Load the default configuration
    config = runner.get_config()

    # Load the default requirements
    requirements = runner.get_requirements()

    # Check user-provided requirements against the SDCcc provided requirements
    runner.check_requirements(pathlib.Path("/absolute/path/to/user-requirements.toml"))

    # Run the SDCcc executable with the specified configuration and requirements
    exit_code = runner.run(
        config=pathlib.Path("/absolute/path/to/config.toml"),
        requirements=pathlib.Path("/absolute/path/to/requirements.toml"),
        timeout=3600  # 1 hour timeout
    )

    # Get the parsed results of the test run
    direct_results, invariant_results = runner.get_result()
"""

import contextlib
import http.client
import io
import logging
import os
import pathlib
import ssl
import subprocess
import tempfile
import threading
import typing
import urllib.parse
import zipfile

import toml

from pysdccc.result_parser import TestSuite

DIRECT_TEST_RESULT_FILE_NAME = "TEST-SDCcc_direct.xml"
INVARIANT_TEST_RESULT_FILE_NAME = "TEST-SDCcc_invariant.xml"
MAX_REDIRECT_COUNT = 4
"""Maximum number of redirects to follow before aborting the download."""
DEFAULT_STORAGE_DIRECTORY = pathlib.Path(tempfile.gettempdir()).joinpath("sdccc")
"""Default directory to store the downloaded sdccc versions."""

logger = logging.getLogger("pysdccc")


def _get_version_from_url(url: urllib.parse.ParseResult) -> str:
    """Extract the version string from the given URL.

    This function takes a parsed URL and extracts the version string from the path component of the URL.
    The version string is assumed to be the stem (i.e., the filename without the extension) of the last part of the path.

    :param url: The parsed URL from which to extract the version string.
    :return: The extracted version string.
    """
    return pathlib.Path(url.path).stem


def _get_local_path(version: str) -> pathlib.Path:
    """Get the local path for the specified version.

    This function constructs the local path where the specified version of the SDCcc executable is stored.
    The path is constructed by joining the default storage directory with the version string.

    :param version: The version string for which the local path is to be constructed.
    :return: The constructed local path as a `pathlib.Path` object.
    """
    return DEFAULT_STORAGE_DIRECTORY.joinpath(version)


def _get_exe_path(local_path: pathlib.Path) -> pathlib.Path:
    """Get the path to the SDCcc executable.

    This function searches the specified local path for the SDCcc executable file. It expects exactly one executable
    file matching the pattern "sdccc-*.exe" to be present in the directory. If no such file or more than one file is found,
    a FileNotFoundError is raised.

    :param local_path: The local path where the SDCcc executable is expected to be found.
    :return: The path to the SDCcc executable file.
    :raises FileNotFoundError: If no executable file or more than one executable file is found in the specified path.
    """
    files = [f for f in local_path.glob("sdccc-*.exe") if f.is_file()]
    if not len(files) == 1:
        raise FileNotFoundError(f"Expected one exe file, got {len(files)} in path {local_path}")
    return files[0]


def _load_configuration(path: pathlib.Path) -> dict[str, typing.Any]:
    """Load the configuration from the specified file.

    This function reads a TOML configuration file from the given local path and returns its contents as a dictionary.

    :param path: The path to the directory containing the configuration file.
    :return: A dictionary containing the configuration data.
    """
    return dict(toml.load(path))


@contextlib.contextmanager
def _cwd(path: str | pathlib.Path) -> typing.Generator[None, None, None]:
    """Change the current working directory to the specified path on context enter and revert to the original directory on context exit.

    :param path: The path to change the working directory to.
    """
    origin = pathlib.Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)


def _download_version_to_stream(
    url: urllib.parse.ParseResult,
    stream: io.IOBase,
    proxy: tuple[str, int] | None = None,
    timeout: int = 60,
    redirect_counter: int = 0,
) -> None:
    """Download the SDCcc executable from the specified URL to the provided stream.

    This function handles the download of the SDCcc executable from a given URL, optionally using a proxy and with a specified timeout.
    It follows redirects up to a maximum defined by `MAX_REDIRECT_COUNT`.

    :param url: The parsed URL from which to download the executable.
    :param stream: The stream where the downloaded executable will be written.
    :param proxy: Optional proxy to be used for the download, specified as a tuple (host, port).
    :param timeout: The timeout in seconds for the download operation.
    :param redirect_counter: The current count of redirects followed. Used internally to limit the number of redirects.
    :raises http.client.HTTPException: If an HTTP error occurs or the maximum number of redirects is exceeded.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.load_default_certs()
    if proxy:
        connection = http.client.HTTPSConnection(proxy[0], proxy[1], context=context, timeout=timeout)
        connection.set_tunnel(url.netloc, url.port)
    else:
        connection = http.client.HTTPSConnection(url.netloc, url.port, context=context, timeout=timeout)
    request_url = f"{url.path}?{url.query}"
    try:
        connection.request("GET", request_url)
        response = connection.getresponse()
        if 400 <= (code := response.getcode()) < 600:  # noqa: PLR2004
            raise http.client.HTTPException(f'Got unexpected status code "{code} for url {url}')
        if 300 <= code < 400:  # noqa: PLR2004
            # follow the redirect
            if redirect_counter > MAX_REDIRECT_COUNT:
                raise http.client.HTTPException(f"Redirection count exceeded maximum of {MAX_REDIRECT_COUNT}")
            _download_version_to_stream(
                urllib.parse.urlparse(response.getheader("Location")),  # type: ignore[arg-type]
                stream,
                proxy=proxy,
                timeout=timeout,
                redirect_counter=redirect_counter + 1,
            )
            return
        content_length = int(response.headers.get("Content-Length", 0)) / 1024 / 1024  # content length in MB
        i = 0.0
        while chunk := response.read(2 ** (8 + 16)):  # 16 MiB steps
            stream.write(chunk)
            i += len(chunk) / 1024 / 1024
            logger.debug(f"Downloaded {i:.2f}/{content_length:.2f} MB.")  # noqa: G004

    finally:
        connection.close()


def local_path_from_url(url: urllib.parse.ParseResult) -> pathlib.Path:
    """Get the local path where the version from the URL is stored.

    This function constructs the local path for the version specified in the URL. It extracts the version string from the URL
    and uses it to determine the local storage path.

    :param url: The parsed URL from which to extract the version string.
    :return: The local path where the version is stored.
    """
    return _get_local_path(_get_version_from_url(url))


def download(url: urllib.parse.ParseResult, proxy: tuple[str, int] | None = None, timeout: int = 60) -> pathlib.Path:
    """Download the specified version from the default URL to a temporary directory.

    This function downloads the SDCcc executable from the given URL to a temporary directory. It optionally uses a proxy and a specified timeout for the download operation. The downloaded file is extracted to a local path determined by the version string in the URL.

    :param url: The parsed URL from which to download the executable.
    :param proxy: Optional proxy to be used for the download, specified as a tuple (host, port).
    :param timeout: The timeout in seconds for the download operation.
    :return: The path to the downloaded executable.
    :raises http.client.HTTPException: If an HTTP error occurs or the maximum number of redirects is exceeded.
    """
    logger.info("Downloading sdccc from %s.", url.geturl())
    with tempfile.NamedTemporaryFile("wb", suffix=".zip", delete=False) as temporary_file:
        _download_version_to_stream(url, temporary_file, proxy=proxy, timeout=timeout)  # type: ignore[arg-type]
    extraction_path = local_path_from_url(url)
    logger.info("Extracting sdccc to %s.", extraction_path)
    with zipfile.ZipFile(temporary_file.name) as f:
        f.extractall(extraction_path)
    return _get_exe_path(extraction_path)


def check_requirements(provided: dict[str, dict[str, bool]], available: dict[str, dict[str, bool]]) -> None:
    """Check if the provided requirements are supported by the available requirements.

    This function verifies that all the requirements specified in the `provided` dictionary are supported by the
    requirements in the `available` dictionary. If any requirement in `provided` is not found in `available`, a KeyError
    is raised.

    :param provided: A dictionary of provided requirements to be verified. The keys are standard names, and the values
                     are dictionaries where the keys are requirement IDs and the values are booleans indicating whether
                     the requirement is enabled.
    :param available: A dictionary of available requirements provided by sdccc. The keys are standard names, and the
                      values are dictionaries where the keys are requirement IDs and the values are booleans indicating
                      whether the requirement is enabled.
    :raise KeyError: If a standard or requirement provided by the user is not found in the sdccc provided requirements.
    """
    for standard, requirements in provided.items():
        if standard not in available:
            raise KeyError(f'Unsupported standard "{standard}". Supported standards are "{list(available)}"')
        provided_enabled = [req for req, enabled in requirements.items() if enabled]
        available_enabled = [a for a, enabled in available[standard].items() if enabled]
        for req in provided_enabled:
            if req not in available_enabled:
                raise KeyError(f'Requirement id "{standard}.{req}" not found')


def _log_sdccc_stdout(pipe: io.TextIOWrapper) -> None:
    """Log the stdout of the SDCcc process.

    This function reads lines from the provided stdout pipe of the SDCcc process and logs each line as an info message.

    :param pipe: The stdout pipe of the SDCcc process.
    """
    with pipe:
        for line in iter(pipe.readline, b""):  # b'\n'-separated lines
            logger.info(line.rstrip())


def _log_sdccc_stderr(pipe: io.TextIOWrapper) -> None:
    """Log the stderr of the SDCcc process.

    This function reads lines from the provided stderr pipe of the SDCcc process and logs each line as an error message.

    :param pipe: The stderr pipe of the SDCcc process.
    """
    with pipe:
        for line in iter(pipe.readline, b""):  # b'\n'-separated lines
            logger.error(line.rstrip())


def _run_sdccc(exe_path: pathlib.Path, timeout: float | None, **kwargs: typing.Any) -> int:
    """Run the SDCcc executable using the specified configurations.

    This function executes the SDCcc executable with the provided command line arguments and configurations.
    It logs the stdout and stderr of the process and waits for the process to complete or timeout.

    :param exe_path: The path to the SDCcc executable.
    :param timeout: The timeout in seconds for the SDCcc process. If None, wait indefinitely.
    :param kwargs: Additional command line arguments to be passed to the SDCcc executable.
    :return: The exit code of the SDCcc process.
    """
    kwargs["no_subdirectories"] = "true"
    args = " ".join(f"--{arg} {value}" for arg, value in kwargs.items())
    logger.info('Executing "%s %s"', exe_path, args)
    with (
        _cwd(exe_path.parent),
        subprocess.Popen(  # noqa: S603
            f"{exe_path} {args}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            encoding="utf-8",
        ) as proc,
    ):
        std_out_logger = threading.Thread(target=_log_sdccc_stdout, args=(proc.stdout,), daemon=True)
        std_err_logger = threading.Thread(target=_log_sdccc_stderr, args=(proc.stderr,), daemon=True)
        std_out_logger.start()
        std_err_logger.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
        finally:
            # close pipe manually to avoid console spam
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
    std_out_logger.join(1)
    std_err_logger.join(1)
    return proc.returncode


def parse_results(test_artifacts_directory: pathlib.Path) -> tuple[TestSuite, TestSuite]:
    """Parse result files from the given path.

    This function reads the direct and invariant test result files from the specified directory
    and returns them as `TestSuite` objects.

    :param test_artifacts_directory: The path to the directory containing the test result files.
    :return: A tuple containing the parsed direct and invariant test results as `TestSuite` objects.
    """
    return (
        TestSuite.from_file(test_artifacts_directory.joinpath(DIRECT_TEST_RESULT_FILE_NAME)),
        TestSuite.from_file(test_artifacts_directory.joinpath(INVARIANT_TEST_RESULT_FILE_NAME)),
    )


class SdcccRunner:
    """Runner for the SDCcc tests.

    This class provides methods to manage and execute the SDCcc tests. It handles the configuration, requirements,
    and execution of the SDCcc executable, as well as parsing the test results.
    """

    def __init__(self, exe: pathlib.Path, test_run_dir: pathlib.Path):
        """Initialize the SdcccRunner object.

        :param exe: The path to the SDCcc executable. Must be an absolute path.
        :param test_run_dir: The path to the directory where the test run results are to be stored. Must be an absolute path.
        :raises ValueError: If the provided paths are not absolute.
        """
        if not exe.is_absolute():
            raise ValueError("Path to executable must be absolute")
        if not test_run_dir.is_absolute():
            raise ValueError("Path to test run directory must be absolute")
        self.exe = exe
        self.test_run_dir = test_run_dir

    def get_config(self) -> dict[str, typing.Any]:
        """Get the default configuration.

        This method loads the default configuration from the SDCcc executable's directory.

        :return: A dictionary containing the configuration data.
        """
        return _load_configuration(self.exe.parent.joinpath("configuration").joinpath("config.toml"))

    def get_requirements(self) -> dict[str, dict[str, bool]]:
        """Get the default requirements.

        This method loads the default requirements from the SDCcc executable's directory.

        :return: A dictionary containing the requirements data.
        """
        return _load_configuration(self.exe.parent.joinpath("configuration").joinpath("test_configuration.toml"))

    def get_test_parameter(self) -> dict[str, typing.Any]:
        """Get the default test parameter.

        This method loads the default test parameters from the SDCcc executable's directory.

        :return: A dictionary containing the test parameter data.
        """
        return _load_configuration(self.exe.parent.joinpath("configuration").joinpath("test_parameter.toml"))

    def check_requirements(self, path: pathlib.Path) -> None:
        """Check the requirements from the given file against the requirements provided by the SDCcc version.

        This method verifies that all the requirements specified in the user's requirements file are supported by the
        requirements provided by the SDCcc version. If any requirement is not found, a KeyError is raised.

        :param path: The path to the user's requirements file.
        :raises KeyError: If a standard or requirement provided by the user is not found in the SDCcc provided requirements.
        """
        sdccc_provided_requirements = self.get_requirements()
        user_provided_requirements = toml.load(path)
        check_requirements(user_provided_requirements, sdccc_provided_requirements)

    def run(
        self,
        config: pathlib.Path,
        requirements: pathlib.Path,
        timeout: float | None = None,
        **kwargs: typing.Any,
    ) -> int:
        """Run the SDCcc executable using the specified configuration and requirements.

        This method executes the SDCcc executable with the provided configuration and requirements files,
        and additional command line arguments. It logs the stdout and stderr of the process and waits for the
        process to complete or timeout.
        Checkout more parameter under https://github.com/draegerwerk/sdccc?tab=readme-ov-file#running-sdccc

        :param config: The path to the configuration file. Must be an absolute path.
        :param requirements: The path to the requirements file. Must be an absolute path.
        :param timeout: The timeout in seconds for the SDCcc process. If None, wait indefinitely.
        :param kwargs: Additional command line arguments to be passed to the SDCcc executable.
        :return: The exit code of the SDCcc process.
        :raises ValueError: If the provided paths are not absolute.
        """
        if not config.is_absolute():
            raise ValueError("Path to config file must be absolute")
        if not requirements.is_absolute():
            raise ValueError("Path to requirements file must be absolute")
        return _run_sdccc(
            self.exe,
            timeout,
            config=config,
            testconfig=requirements,
            test_run_directory=self.test_run_dir,
            **kwargs,
        )

    def get_result(self) -> tuple[TestSuite, TestSuite]:
        """Get the parsed results of the test run.

        This method reads the direct and invariant test result files from the test run directory and returns them
        as TestSuite objects.

        :return: A tuple containing the parsed direct and invariant test results as TestSuite objects.
        """
        return parse_results(self.test_run_dir)
