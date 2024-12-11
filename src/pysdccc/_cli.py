import io
import pathlib
import tempfile
import zipfile
from typing import Any

import httpx

from pysdccc import _runner

try:
    import click
except ImportError as e:
    raise ImportError("Cli not installed. Please install using 'pip install pysdccc[cli].") from e


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
@click.version_option()
def cli():
    pass


@click.command(help="Install the SDCcc executable from the specified URL.")
@click.argument("url", type=URL)
@click.option("--proxy", help="Proxy server to use for the download.", type=PROXY)
def install(url: httpx.URL, proxy: httpx.Proxy | None):
    """Download the specified version from the default URL to a temporary directory.

    This function downloads the SDCcc executable from the given URL to a temporary directory. It optionally uses a proxy and a specified timeout for the download operation. The downloaded file is extracted to a local path determined by the version string in the URL.

    :param url: The parsed URL from which to download the executable.
    :param proxy: Optional proxy to be used for the download.
    """
    _download(url, _runner.DEFAULT_STORAGE_DIRECTORY, proxy)


@click.command(help="Uninstall the SDCcc executable by removing the specified directory.")
def uninstall():
    """Uninstall the SDCcc executable.

    This function removes the SDCcc executable from the specified directory.
    """
    import shutil

    try:
        shutil.rmtree(_runner.DEFAULT_STORAGE_DIRECTORY)
        click.echo("SDCcc has been uninstalled.")
    except FileNotFoundError:
        click.echo("SDCcc is not installed. Nothing to uninstall.")


@click.command()
def version():
    """Print the version of the SDCcc executable."""
    version_ = _runner.SdcccRunner(pathlib.Path().absolute()).get_version()
    if version_:
        click.echo(version_)
    else:
        import sys
        click.echo("Unable to detect version of SDCcc executable.", err=True)
        sys.exit(1)


cli.add_command(install)
cli.add_command(uninstall)
cli.add_command(version)
