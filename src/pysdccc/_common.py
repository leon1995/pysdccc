import locale
import os
import sys
import typing

PATH_TYPE = typing.Union[str, os.PathLike[str]]  # noqa: UP007

ENCODING = 'utf-8' if sys.flags.utf8_mode else locale.getencoding()


def build_command(*args: str, **kwargs: typing.Any) -> str:
    """Build the command string from the arguments and keyword arguments."""
    flags = ' '.join(f'--{arg}' for arg, value in kwargs.items() if value is True)
    kwargs_string = ' '.join(f'--{arg} "{value}"' for arg, value in kwargs.items() if value not in (True, False))
    return ' '.join(part for part in [*args, flags, kwargs_string] if part)  # omit empty parts
