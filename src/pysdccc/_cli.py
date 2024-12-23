import io
import locale
import pathlib
import subprocess
import sys
import tempfile
import zipfile
from typing import Any

import httpx

from pysdccc import _runner

try:
    import click
except ImportError as import_error:
    raise ImportError("Cli not installed. Please install using 'pip install pysdccc[cli].") from import_error


class UrlType(click.ParamType):
    name = "url"

    def convert(self, value: str, param: Any, ctx: Any) -> httpx.URL:
        try:
            return httpx.URL(value)
        except Exception as e:  # noqa: BLE001
            self.fail(f"{value!r} is not a valid proxy: {e}", param, ctx)


URL = UrlType()


class ProxyType(click.ParamType):
    name = "proxy"

    def convert(self, value: str, param: Any, ctx: Any) -> httpx.Proxy:
        try:
            return httpx.Proxy(value)
        except Exception as e:  # noqa: BLE001
            self.fail(f"{value!r} is not a valid proxy: {e}", param, ctx)


PROXY = ProxyType()

_ENCODING = "utf-8" if sys.flags.utf8_mode else locale.getencoding()


def _download_to_stream(
    url: httpx.URL,
    stream: io.IOBase,
    proxy: httpx.Proxy | None = None,
) -> None:
    with httpx.stream("GET", url, follow_redirects=True, proxy=proxy) as response:
        total = int(response.headers["Content-Length"])
        with click.progressbar(length=total, label="Downloading", show_eta=True, width=0) as progress:
            num_bytes_downloaded = response.num_bytes_downloaded
            for chunk in response.iter_bytes():
                stream.write(chunk)
                progress.update(response.num_bytes_downloaded - num_bytes_downloaded)
                num_bytes_downloaded = response.num_bytes_downloaded


def _download(
    url: httpx.URL,
    output: pathlib.Path,
    proxy: httpx.Proxy | None = None,
):
    click.echo(f"Downloading sdccc from {url}.")
    with tempfile.NamedTemporaryFile("wb", suffix=".zip", delete=False) as temporary_file:
        _download_to_stream(url, temporary_file, proxy=proxy)  # type: ignore[arg-type]
    click.echo(f"Extracting sdccc to {output}.")
    with (
        zipfile.ZipFile(temporary_file.name) as f,
        click.progressbar(f.infolist(), label="Extracting", width=0) as progress,
    ):
        for member in progress:
            f.extract(member, output)


@click.group()
@click.version_option(message="%(version)s")
def cli():
    pass


@click.command(
    short_help="Install the SDCcc executable from the specified URL. Releases can be found at https://github.com/Draegerwerk/SDCcc/releases.",
)
@click.argument("url", type=URL)
@click.option("--proxy", help="Proxy server to use for the download.", type=PROXY)
def install(url: httpx.URL, proxy: httpx.Proxy | None):
    """Download the specified version from the default URL to a temporary directory.

    This function downloads the SDCcc executable from the given URL to a temporary directory. It optionally uses a proxy and a specified timeout for the download operation. The downloaded file is extracted to a local path determined by the version string in the URL.

    :param url: The parsed URL from which to download the executable.
    :param proxy: Optional proxy to be used for the download.
    """
    try:
        _download(url, _runner.DEFAULT_STORAGE_DIRECTORY, proxy)
    except Exception as e:
        raise click.ClickException(f"Failed to download and extract SDCcc from {url}: {e}.") from e


@click.command(short_help="Uninstall the SDCcc executable by removing the specified directory.")
def uninstall():
    """Uninstall the SDCcc executable.

    This function removes the SDCcc executable from the specified directory.
    """
    import shutil

    shutil.rmtree(_runner.DEFAULT_STORAGE_DIRECTORY, ignore_errors=True)


cli.add_command(install)
cli.add_command(uninstall)


def sdccc():
    try:
        sdccc_exe = _runner.get_exe_path(_runner.DEFAULT_STORAGE_DIRECTORY)
        #with _runner.cwd(_runner.DEFAULT_STORAGE_DIRECTORY):
        subprocess.run(  # noqa: S603
            f"{sdccc_exe} {' '.join(sys.argv[1:])}",
            check=True,
            cwd=sdccc_exe.parent,
        )
    except FileNotFoundError as e:
        click.ClickException("sdccc is not installed. Please install using 'pysdccc install <url>'.").show()
        raise SystemExit(1) from e
    except subprocess.CalledProcessError as e:
        click.echo(e, err=True)
        raise SystemExit(e.returncode) from e
