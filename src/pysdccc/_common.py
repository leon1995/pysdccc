import locale
import os
import sys
import typing

PATH_TYPE = typing.Union[str, os.PathLike[str]]  # noqa: UP007

ENCODING = 'utf-8' if sys.flags.utf8_mode else locale.getencoding()


def build_command(*args: str, **kwargs: typing.Any) -> list[str]:
    """Build the command string from the arguments and keyword arguments."""
    command = list(args)
    for arg, value in kwargs.items():
        if value is True:
            command.append(f'--{arg}')
        elif value is not False:
            command.append(f'--{arg}')
            command.append(str(value))
    return command
