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

import asyncio
import io
import logging
import pathlib
import subprocess
import threading
import typing

import toml

from pysdccc._result_parser import TestSuite

DIRECT_TEST_RESULT_FILE_NAME = "TEST-SDCcc_direct.xml"
INVARIANT_TEST_RESULT_FILE_NAME = "TEST-SDCcc_invariant.xml"
DEFAULT_STORAGE_DIRECTORY = pathlib.Path(__file__).parent.joinpath("_sdccc")
"""Default directory to store the downloaded sdccc versions."""

logger = logging.getLogger("pysdccc")


def get_exe_path(local_path: pathlib.Path) -> pathlib.Path:
    """Get the path to the SDCcc executable.

    This function searches the specified local path for the SDCcc executable file. It expects exactly one executable
    file matching the pattern "sdccc-*.exe" to be present in the directory. If no such file or more than one file is found,
    a FileNotFoundError is raised.

    :param local_path: The local path where the SDCcc executable is expected to be found.
    :return: The path to the SDCcc executable file.
    :raises FileNotFoundError: If no executable file or more than one executable file is found in the specified path.
    """
    files = [f for f in local_path.glob("*.exe") if f.is_file()]
    if not len(files) == 1:
        raise FileNotFoundError(f"Unable to determine correct executable file, got {files} in path {local_path}")
    return files[0]


def _load_configuration(path: pathlib.Path) -> dict[str, typing.Any]:
    """Load the configuration from the specified file.

    This function reads a TOML configuration file from the given local path and returns its contents as a dictionary.

    :param path: The path to the directory containing the configuration file.
    :return: A dictionary containing the configuration data.
    """
    return dict(toml.load(path))


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


def _log_pipe(pipe: io.TextIOWrapper, log_method: typing.Callable[[str], None]) -> None:
    """Log the pipe of the rbt process.

    :param pipe: The pipe of the rbt process.
    :param log_method: The logging method to use for logging the pipe output.
    """
    try:
        with pipe:
            for line in iter(pipe.readline, b""):  # b'\n'-separated lines
                log_method(line.rstrip())
    except ValueError:
        pass  # pipe closed


def _run_sdccc(exe_path: pathlib.Path, args: str, timeout: float | None) -> int:
    """Run the SDCcc executable using the specified configurations.

    This function executes the SDCcc executable with the provided command line arguments and configurations.
    It logs the stdout and stderr of the process and waits for the process to complete or timeout.

    :param exe_path: The path to the SDCcc executable.
    :param timeout: The timeout in seconds for the SDCcc process. If None, wait indefinitely.
    :param args: Arguments formatted as a string.
    :return: The exit code of the SDCcc process.
    """
    logger.info('Executing "%s %s"', exe_path, args)
    with subprocess.Popen(  # noqa: S603
        f"{exe_path} {args}",
        cwd=exe_path.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        encoding="utf-8",
    ) as proc:
        std_out_logger = threading.Thread(target=_log_pipe, args=(proc.stdout, logger.info), daemon=True)
        std_err_logger = threading.Thread(target=_log_pipe, args=(proc.stderr, logger.error), daemon=True)
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


class _BaseRunner:
    """Runner for the SDCcc tests.

    This class provides methods to manage and execute the SDCcc tests. It handles the configuration, requirements,
    and execution of the SDCcc executable, as well as parsing the test results.
    """

    def __init__(self, test_run_dir: pathlib.Path, exe: pathlib.Path | None = None):
        """Initialize the SdcccRunner object.

        :param exe: The path to the SDCcc executable. Must be an absolute path.
        :param test_run_dir: The path to the directory where the test run results are to be stored. Must be an absolute path.
        :raises ValueError: If the provided paths are not absolute.
        """
        try:
            self.exe = exe or get_exe_path(DEFAULT_STORAGE_DIRECTORY).absolute()
        except FileNotFoundError as e:
            raise FileNotFoundError("Have you downloaded sdccc?") from e
        if not self.exe.is_absolute():
            raise ValueError("Path to executable must be absolute")
        if not self.exe.is_file():
            raise FileNotFoundError(f"No executable found under {self.exe}")
        if not test_run_dir.is_absolute():
            raise ValueError("Path to test run directory must be absolute")
        if not test_run_dir.is_dir():
            raise ValueError("Test run directory is not a directory")
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

    def get_result(self) -> tuple[TestSuite, TestSuite]:
        """Get the parsed results of the test run.

        This method reads the direct and invariant test result files from the test run directory and returns them
        as TestSuite objects.

        :return: A tuple containing the parsed direct and invariant test results as TestSuite objects.
        """
        return parse_results(self.test_run_dir)

    def _prepare_execution_command(self, config: pathlib.Path, requirements: pathlib.Path, **kwargs: typing.Any) -> str:
        if not config.is_absolute():
            raise ValueError("Path to config file must be absolute")
        if not requirements.is_absolute():
            raise ValueError("Path to requirements file must be absolute")

        kwargs["no_subdirectories"] = "true"
        kwargs["test_run_directory"] = self.test_run_dir
        kwargs["config"] = config
        kwargs["testconfig"] = requirements
        return " ".join(f"--{arg} {value}" for arg, value in kwargs.items())


class SdcccRunner(_BaseRunner):
    """Synchronous runner for sdccc."""

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
        args = self._prepare_execution_command(config, requirements, **kwargs)
        return _run_sdccc(self.exe, args=args, timeout=timeout)

    def get_version(self) -> str:
        """Get the version of the SDCcc executable."""
        # use capture_output = True to get stdout and stderr instead of check_output which only collects stdout
        process = subprocess.run([str(self.exe), "--version"], check=True, capture_output=True, cwd=self.exe.parent)  # noqa: S603
        return process.stdout.decode().strip()


class _SdcccSubprocessProtocol(asyncio.SubprocessProtocol):
    _STDOUT = 1
    _STDERR = 2

    def __init__(self):
        self.closed_event = asyncio.Event()

    def pipe_data_received(self, fd: int, data: bytes):
        if fd == self._STDOUT:
            logger.info(data.decode("utf-8").rstrip())
        elif fd == self._STDERR:
            logger.error(data.decode("utf-8").rstrip())
        else:
            raise RuntimeError(f"Unexpected file descriptor {fd}")

    def connection_lost(self, exc: Exception | None):
        self.closed_event.set()
        if exc:
            raise exc


class SdcccRunnerAsync(_BaseRunner):
    """Asynchronous runner for sdccc."""

    async def run(
        self,
        config: pathlib.Path,
        requirements: pathlib.Path,
        timeout: float | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
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
        :param loop: The event loop to run the SDCcc process in. If None, the current running loop is used.
        :param kwargs: Additional command line arguments to be passed to the SDCcc executable.
        :return: The exit code of the SDCcc process.
        :raises ValueError: If the provided paths are not absolute.
        """
        args = self._prepare_execution_command(config, requirements, **kwargs)
        logger.info('Executing "%s %s"', self.exe, args)
        loop = loop or asyncio.get_running_loop()
        transport, protocol = await loop.subprocess_exec(
            _SdcccSubprocessProtocol,
            self.exe,
            args,
            stdin=None,
            cwd=self.exe.parent,
        )
        try:
            await asyncio.wait_for(protocol.closed_event.wait(), timeout=timeout)
        except TimeoutError:
            transport.kill()
        finally:
            transport.close()
        await protocol.closed_event.wait()
        return_code = transport.get_returncode()
        if return_code is None:
            raise RuntimeError("Process did not exit")
        return return_code

    async def get_version(self) -> str | None:
        """Get the version of the SDCcc executable."""
        process = await asyncio.create_subprocess_exec(
            self.exe,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.exe.parent,
        )
        stdout, stderr = await process.communicate()
        if process.returncode:
            error = subprocess.CalledProcessError(process.returncode, f"{self.exe} --version")
            error.stdout = stdout
            error.stderr = stderr
            raise error
        return stdout.decode("utf-8").strip() if stdout else None
