"""tests for module runner.py."""

import asyncio
import io
import pathlib
import random
import tempfile
import uuid
from unittest import mock

import pytest
import toml

from pysdccc._result_parser import TestSuite
from pysdccc._runner import (
    SdcccRunner,
    SdcccRunnerAsync,
    _BaseRunner,
    _cwd,
    _get_exe_path,
    _load_configuration,
    _run_sdccc,
    check_requirements,
    parse_results,
)


def test_get_exe_path():
    """Test that the executable path is correctly identified."""
    assert not pathlib.Path("sdccc-1.0.0.exe").exists()
    with mock.patch.object(pathlib, "Path") as mock_path:
        mock_path.glob = lambda _: [pathlib.Path("sdccc-1.0.0.exe")]
        assert _get_exe_path(mock_path) == pathlib.Path("sdccc-1.0.0.exe")

    with pytest.raises(FileNotFoundError):
        _get_exe_path(pathlib.Path("sdccc-1.0.0.exe"))


def test_load_configuration():
    """Test that the configuration is correctly loaded from a TOML file."""
    with mock.patch("toml.load") as mock_load:
        mock_load.return_value = {"key": "value"}
        assert _load_configuration(pathlib.Path("config.toml")) == {"key": "value"}


def test_cwd():
    """Test that the current working directory is correctly changed and restored."""
    original_cwd = pathlib.Path.cwd()
    temp_dir = pathlib.Path(tempfile.gettempdir())
    with _cwd(temp_dir):
        assert pathlib.Path.cwd() == temp_dir
    assert pathlib.Path.cwd() == original_cwd


def test_check_requirements():
    """Test that the requirements are correctly checked against the provided requirements."""
    provided = {"biceps": {"b1": True}}
    available = {"biceps": {"b1": True, "b2": True}}
    check_requirements(provided, available)

    provided["biceps"]["b3"] = True
    with pytest.raises(KeyError):
        check_requirements(provided, available)

    provided["biceps"]["b3"] = False
    check_requirements(provided, available)

    provided["mdpws"] = {}
    provided["mdpws"]["m1"] = True
    with pytest.raises(KeyError):
        check_requirements(provided, available)

    provided["mdpws"]["m1"] = False
    with pytest.raises(KeyError):
        check_requirements(provided, available)


def test_run_sdccc():
    """Test that the SDCcc executable runs correctly and returns the expected return code."""
    return_code = random.randint(0, 255)
    exe_path = pathlib.Path("sdccc-1.0.0.exe")
    std_out = io.StringIO("stdout")
    std_err = io.StringIO("stderr")
    # close pipes to avoid console spam
    std_out.close()
    std_err.close()
    with mock.patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value.__enter__.return_value.stdout = std_out
        mock_popen.return_value.__enter__.return_value.stderr = std_err
        mock_popen.return_value.__enter__.return_value.wait.return_value = 0
        mock_popen.return_value.__enter__.return_value.returncode = return_code
        assert _run_sdccc(exe_path, mock.MagicMock(), None) == return_code


def test_parse_results():
    """Test that the test results are correctly parsed from the result files."""
    with mock.patch("pysdccc.result_parser.TestSuite.from_file") as mock_from_file:
        mock_from_file.side_effect = ["direct_result", "invariant_result"]
        assert parse_results(pathlib.Path()) == ("direct_result", "invariant_result")


def test_sdccc_runner_init():
    """Test that the SdcccRunner is correctly initialized and raises ValueError for relative paths."""
    with pytest.raises(ValueError, match="Path to test run directory must be absolute"):
        _BaseRunner(pathlib.Path(), pathlib.Path().absolute())
    with pytest.raises(ValueError, match="Path to executable must be absolute"):
        _BaseRunner(pathlib.Path().absolute(), pathlib.Path())
    runner = _BaseRunner(pathlib.Path().absolute(), pathlib.Path().absolute())
    assert runner.exe == pathlib.Path().absolute()
    assert runner.test_run_dir == pathlib.Path().absolute()
    with pytest.raises(ValueError, match="Path to requirements file must be absolute"):
        runner._prepare_execution_command(pathlib.Path().absolute(), pathlib.Path())  # noqa: SLF001
    with pytest.raises(ValueError, match="Path to config file must be absolute"):
        runner._prepare_execution_command(pathlib.Path(), pathlib.Path().absolute())  # noqa: SLF001


def test_sdccc_runner_get_config():
    """Test that the SdcccRunner correctly loads the configuration."""
    runner = _BaseRunner(pathlib.Path().absolute(), pathlib.Path().absolute())
    with mock.patch("pysdccc.runner._load_configuration") as mock_load_config:
        mock_load_config.return_value = {"key": "value"}
        assert runner.get_config() == {"key": "value"}


def test_sdccc_runner_get_requirements():
    """Test that the SdcccRunner correctly loads the requirements."""
    runner = _BaseRunner(pathlib.Path().absolute(), pathlib.Path().absolute())
    with mock.patch("pysdccc.runner._load_configuration") as mock_load_config:
        mock_load_config.return_value = {"key": "value"}
        assert runner.get_requirements() == {"key": "value"}


def test_sdccc_runner_get_test_parameter():
    """Test that the SdcccRunner correctly loads the test parameters."""
    runner = _BaseRunner(pathlib.Path().absolute(), pathlib.Path().absolute())
    with mock.patch("pysdccc.runner._load_configuration") as mock_load_config:
        mock_load_config.return_value = {"key": "value"}
        assert runner.get_test_parameter() == {"key": "value"}


def test_sdccc_runner_check_requirements():
    """Test that the SdcccRunner correctly checks the requirements."""
    runner = _BaseRunner(pathlib.Path().absolute(), pathlib.Path().absolute())
    with mock.patch("pysdccc.SdcccRunner.check_requirements") as mock_check_requirements:
        runner.check_requirements(pathlib.Path("requirements.toml"))
        mock_check_requirements.assert_called_once()


def test_sdccc_runner_get_result():
    """Test that the SdcccRunner correctly parses the test results."""
    runner = _BaseRunner(pathlib.Path().absolute(), pathlib.Path().absolute())
    with mock.patch("pysdccc.runner.parse_results") as mock_parse_results:
        mock_parse_results.return_value = ("direct_result", "invariant_result")
        assert runner.get_result() == ("direct_result", "invariant_result")


def test_configuration():
    """Test that the SdcccRunner correctly loads the configuration from the SDCcc executable's directory."""
    run = _BaseRunner(mock.MagicMock(), pathlib.Path(__file__).parent.joinpath("testversion/sdccc.exe"))
    loaded_config = run.get_config()
    provided_config = """
[SDCcc]
CIMode=false
GraphicalPopups=true
TestExecutionLogging=true
EnableMessageEncodingCheck=true
SummarizeMessageEncodingErrors=true

[SDCcc.TLS]
FileDirectory="./configuration"
KeyStorePassword="whatever"
TrustStorePassword="whatever"
ParticipantPrivatePassword="dummypass"
EnabledProtocols = ["TLSv1.2", "TLSv1.3"]
EnabledCiphers = [
    # TLS 1.2
    "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
    "TLS_DHE_RSA_WITH_AES_128_GCM_SHA256",
    "TLS_DHE_RSA_WITH_AES_256_GCM_SHA384",
    # TLS 1.3
    "TLS_AES_128_GCM_SHA256",
    "TLS_AES_256_GCM_SHA384",
]

[SDCcc.Network]
InterfaceAddress="127.0.0.1"
MaxWait=10
MulticastTTL=128

[SDCcc.Consumer]
Enable=true
DeviceEpr="urn:uuid:857bf583-8a51-475f-a77f-d0ca7de69b11"
# DeviceLocationBed="bed32"
# DeviceLocationPointOfCare="poc32"
# etc.

[SDCcc.Provider]
Enable=false

[SDCcc.gRPC]
ServerAddress="localhost:50051"

[SDCcc.TestParameter]
Biceps547TimeInterval=5
    """
    assert toml.loads(provided_config) == loaded_config


def test_requirements():
    """Test that the SdcccRunner correctly loads the requirements from the SDCcc executable's directory."""
    run = SdcccRunner(mock.MagicMock(), pathlib.Path(__file__).parent.joinpath("testversion/sdccc.exe"))
    loaded_config = run.get_requirements()
    provided_config = """
[MDPWS]
R0006=false
R0008=true
R0010=true
R0011=true
R0012=true
R0013=true
R0014=true
R0015=true

[BICEPS]
R0007_0=true
R0021=true
R0023=true
R0025_0=true
R0029_0=true
R0033=true
R0034_0=true
R0038_0=true
R0055_0=false
R0062=true
R0064=true
R0066=true
R0068=true
R0069=true
R0097=true
R0098_0=true
R0100=false
R0101=true
R0104=true
R0105_0=true
R0116=true
R0119=false
R0124=true
R0125=true
R0133=true
R5003=true
R5006=true
B-6_0=true
B-128=false
B-284_0=true
B-402_0=true
C-5=true
C-7=true
C-11=true
C-12=true
C-13=true
C-14=true
C-15=true
C-55_0=true
C-62=true
R5024=true
R5025_0=true
R5039=true
R5040=true
R5041=true
R5042=true
R5046_0=true
R5051=true
R5052=true
R5053=true
5-4-7_0_0=true
5-4-7_1=true
5-4-7_2=true
5-4-7_3=true
5-4-7_4=true
5-4-7_5=true
5-4-7_6_0=true
5-4-7_7=true
5-4-7_8=true
5-4-7_9=true
5-4-7_10=true
5-4-7_11=true
5-4-7_12_0=true
5-4-7_13=true
5-4-7_14=true
5-4-7_15=true
5-4-7_16=true
5-4-7_17=true

[DPWS]
R0001=false
R0013=false
R0019=false
R0031=false
R0034=false
R0040=false

[GLUE]
13=true
8-1-3=true
R0010_0=true
R0011=true
R0012_0_0=true
R0013=false
R0034_0=true
R0036_0=true
R0042_0=true
R0056=true
R0072=false
R0078_0=true
R0080=true
    """
    assert toml.loads(provided_config) == loaded_config


def test_parse_result():
    """Test that the SdcccRunner correctly parses the test results from the SDCcc executable's directory."""
    invariant = (
        (
            "BICEPS.R6039",
            "Sends a get context states message with empty handle ref and verifies that the response "
            "contains all context states of the mdib.",
        ),
        (
            "BICEPS.R6040",
            "Verifies that for every known context descriptor handle the corresponding context states are returned.",
        ),
        (
            "BICEPS.R6041",
            "Verifies that for every known context state handle the corresponding context state is returned.",
        ),
        ("SDCccTestRunValidity", "SDCcc Test Run Validity"),
    )
    direct = (
        (
            "MDPWS.R5039",
            "Sends a get context states message with empty handle ref and verifies that the response "
            "contains all context states of the mdib.",
        ),
        (
            "MDPWS.R5040",
            "Verifies that for every known context descriptor handle the corresponding context states are returned.",
        ),
        (
            "MDPWS.R5041",
            "Verifies that for every known context state handle the corresponding context state is returned.",
        ),
        ("SDCccTestRunValidity", "SDCcc Test Run Validity"),
    )
    run = _BaseRunner(pathlib.Path(__file__).parent.joinpath("result").absolute(), mock.MagicMock())
    direct_results, invariant_results = run.get_result()

    def verify_suite(suite: TestSuite, data: tuple[tuple[str, str], ...]):
        assert isinstance(suite, TestSuite)
        assert len(data) == len(suite)

    verify_suite(direct_results, direct)
    verify_suite(invariant_results, invariant)


def test_is_downloaded():
    """Test that the download status is correctly determined."""
    assert not SdcccRunner(pathlib.Path().absolute()).is_downloaded(uuid.uuid4().hex)
    with mock.patch("pysdccc.runner.SdcccRunner.get_version") as mock_func:
        version = uuid.uuid4().hex
        mock_func.return_value = version
        assert SdcccRunner(pathlib.Path().absolute()).is_downloaded(version)


@pytest.mark.asyncio
async def test_is_downloaded_async():
    """Test that the download status is correctly determined."""
    assert not (await SdcccRunnerAsync(pathlib.Path().absolute()).is_downloaded(uuid.uuid4().hex))
    with mock.patch("pysdccc.runner.SdcccRunnerAsync.get_version") as mock_func:
        version = uuid.uuid4().hex
        mock_func.return_value = version
        assert await SdcccRunnerAsync(pathlib.Path().absolute()).is_downloaded(version)


def test_sdccc_runner_version():
    """Test that the SdcccRunner correctly loads the version."""
    runner = SdcccRunner(pathlib.Path().absolute())
    with mock.patch("subprocess.check_output") as mock_check_output:
        version = uuid.uuid4().hex
        mock_check_output.return_value = version
        assert runner.get_version() == version


@pytest.mark.asyncio
async def test_sdccc_runner_version_async():
    """Test that the SdcccRunner correctly loads the version."""
    runner = SdcccRunnerAsync(pathlib.Path().absolute())
    with mock.patch("asyncio.create_subprocess_exec") as mock_check_output:
        version = uuid.uuid4().hex
        fut = asyncio.Future()
        mock_check_output.return_value.communicate = lambda: fut
        fut.set_result((version.encode(), b""))
        assert (await runner.get_version()) == version


def test_sdccc_runner_run():
    """Test that the SdcccRunner correctly runs the SDCcc executable."""
    runner = SdcccRunner(pathlib.Path().absolute())
    with mock.patch("pysdccc.runner._run_sdccc") as mock_run_sdccc:
        mock_run_sdccc.return_value = 0
        assert runner.run(pathlib.Path("config.toml").absolute(), pathlib.Path("requirements.toml").absolute()) == 0


@pytest.mark.asyncio
async def test_sdccc_runner_run_async1():
    """Test that the SdcccRunner correctly runs the SDCcc executable."""
    runner = SdcccRunnerAsync(pathlib.Path().absolute())
    with (
        mock.patch("asyncio.get_running_loop") as mock_get_loop,
        mock.patch("asyncio.AbstractEventLoop.subprocess_exec") as mock_subprocess_exec,
        mock.patch("pysdccc.runner._SdcccSubprocessProtocol") as mock_protocol,
        mock.patch("pysdccc.runner._cwd"),
    ):
        mock_loop = mock.MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_transport = mock.MagicMock()
        mock_protocol_instance = mock_protocol.return_value
        mock_subprocess_exec.return_value = (mock_transport, mock_protocol_instance)

        mock_protocol_instance.closed_event.wait = mock.AsyncMock()
        mock_transport.get_returncode.return_value = 0

        config = pathlib.Path("/absolute/path/to/config.toml").absolute()
        requirements = pathlib.Path("/absolute/path/to/requirements.toml").absolute()

        exit_code = await runner.run(config, requirements)

        assert exit_code == 0
        mock_subprocess_exec.assert_called_once_with(mock.ANY, runner.exe, mock.ANY, stdin=None)
        mock_protocol_instance.closed_event.wait.assert_called_once()
