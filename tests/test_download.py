import io
import pathlib
import uuid
from unittest import mock

import httpx
import pytest

from pysdccc._download import _download_to_stream, _download_to_stream_async, download, download_async


def test_download_to_stream():
    """Test that the executable is correctly downloaded to a stream."""
    stream = io.BytesIO()
    data = uuid.uuid4().hex
    with mock.patch("httpx.stream") as mock_conn:
        response_mock = mock.MagicMock()

        def _iter_bytes():
            for b in data:
                yield b.encode()

        response_mock.iter_bytes = _iter_bytes
        mock_conn.return_value.__enter__.return_value = response_mock
        _download_to_stream(mock.MagicMock(), stream)
        assert stream.getvalue() == data.encode()


def test_download():
    """Test that the download function correctly downloads and extracts the executable."""
    url = httpx.URL(uuid.uuid4().hex)
    exe_path = pathlib.Path(uuid.uuid4().hex)
    with (
        mock.patch("pysdccc._download._download_to_stream"),
        mock.patch("zipfile.ZipFile"),
        mock.patch("pysdccc._runner._get_exe_path") as mock_get_exe_path,
    ):
        mock_get_exe_path.return_value = exe_path
        assert download(url) == exe_path


@pytest.mark.asyncio
async def test_download_to_stream_async():
    """Test that the executable is correctly downloaded to a stream."""
    stream = io.BytesIO()
    data = uuid.uuid4().hex
    with mock.patch("httpx.AsyncClient.stream") as mock_conn:
        response_mock = mock.MagicMock()

        async def _aiter_bytes():
            for b in data:
                yield b.encode()

        response_mock.aiter_bytes = _aiter_bytes
        mock_conn.return_value.__aenter__.return_value = response_mock
        await _download_to_stream_async(mock.MagicMock(), stream)
        assert stream.getvalue() == data.encode()


@pytest.mark.asyncio
async def test_download_async():
    """Test that the download function correctly downloads and extracts the executable."""
    url = httpx.URL(uuid.uuid4().hex)
    exe_path = pathlib.Path(uuid.uuid4().hex)
    with (
        mock.patch("pysdccc._download._download_to_stream_async"),
        mock.patch("zipfile.ZipFile"),
        mock.patch("pysdccc._runner._get_exe_path") as mock_get_exe_path,
    ):
        mock_get_exe_path.return_value = exe_path
        assert (await download_async(url)) == exe_path