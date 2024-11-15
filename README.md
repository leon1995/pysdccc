# pysdccc

This python packages provides a convenient way to execute the [sdccc test suite](https://github.com/Draegerwerk/sdccc/).

This wrapper is only compatible with sdccc versions based on the commit [ebe0e09](https://github.com/Draegerwerk/SDCcc/commit/ebe0e094ff92649d0bda1988b0d1c1b08403aea4) or later.

## Installation

Download from pypi using `pip install pysdccc`

### Development

For this open source project the [Contributor License Agreement](Contributor_License_Agreement.md) governs all relevant activities and your contributions. By contributing to the project you agree to be bound by this Agreement and to licence your work accordingly.

1. clone the repository
2. `pip install -e .[dev]`

## Usage

### Basic usage

```python
import pathlib
import pysdccc

runner = pysdccc.SdcccRunner(
    pathlib.Path('/path/to/sdccc/executable'),
    pathlib.Path('/path/to/sdccc/result/directory'),
)

exit_code = runner.run(
    pathlib.Path('/path/to/configuration/file.toml'),
    pathlib.Path('/path/to/requirements/file.toml'),
)

if exit_code > 1:  # https://github.com/Draegerwerk/SDCcc/?tab=readme-ov-file#exit-codes
    raise Exception("Test run execution was not successful")

direct_result, invariant_results = runner.get_result()
for test_case in direct_result + invariant_results:
    # add handling if test_case passed or failed...
    print(f'{test_case.name}: {test_case.is_passed}')
```

### Download an sdccc executable

```python
import pysdccc
import urllib.parse

url = urllib.parse.urlparse('https://url/to/sdccc.zip')
# only download if the local directory does not exist
if not pysdccc.local_path_from_url(url).exists():
    pysdccc.download(url)
```

### Create configuration file

Configure the test consumer. Check the [test consumer configuration](https://github.com/Draegerwerk/SDCcc/?tab=readme-ov-file#test-consumer-configuration) for more information.

```python
import pathlib
import toml
import pysdccc

config = {
    'SDCcc': {
        ...  # add all relevant config parameter
    }
}
config_path = pathlib.Path('/path/to/configuration/file.toml')
config_path.write_text(toml.dumps(config))

runner = pysdccc.SdcccRunner(
    pathlib.Path('/path/to/sdccc/executable'),
    pathlib.Path('/path/to/sdccc/result/directory'),
)

runner.run(
    config_path,
    pathlib.Path('/path/to/requirements/file.toml'),
)

# or if you have already downloaded the version
config = runner.get_config()  # load default configuration
config['SDCcc']['Consumer']['DeviceEpr'] = "urn:uuid:12345678-1234-1234-1234-123456789012"  # e.g. change device epr
# save and run as above
```

### Create requirements file

Enable or disable specific requirements. Check the [test requirements](https://github.com/Draegerwerk/SDCcc/?tab=readme-ov-file#enabling-tests) for more information.

```python
import pathlib
import toml
import pysdccc

requirements = {
    'BICEPS': {
        ...  # add all requirements to be tested
    }
}
requirements_path = pathlib.Path('/path/to/configuration/file.toml')
requirements_path.write_text(toml.dumps(requirements))

runner = pysdccc.SdcccRunner(
    pathlib.Path('/path/to/sdccc/executable'),
    pathlib.Path('/path/to/sdccc/result/directory'),
)
# optionally, check whether you did not add a requirement that is not available
runner.check_requirements(requirements_path)
runner.run(
    pathlib.Path('/path/to/configuration/file.toml'),
    requirements_path,
)

# or, if you have already downloaded the version
requirements = runner.get_requirements()  # load default configuration
requirements['BICEPS']['R0033'] = False  # e.g. disable biceps R0033
# save and run as above
```

### Create test parameter configuration

Some tests require individual parameters. Check the [test parameter configuration](https://github.com/Draegerwerk/SDCcc/?tab=readme-ov-file#test-parameter-configuration) for more information.

```python
import pathlib
import toml
import pysdccc

config = {
    'TestParameter': {
        ...
    }
}
requirements_path = pathlib.Path('/path/to/configuration/file.toml')
requirements_path.write_text(toml.dumps(config))

runner = pysdccc.SdcccRunner(
    pathlib.Path('/path/to/sdccc/executable'),
    pathlib.Path('/path/to/sdccc/result/directory'),
)
runner.run(
    pathlib.Path('/path/to/configuration/file.toml'),
    pathlib.Path('/path/to/requirements/file.toml'),
    testparam=requirements_path,
)

# or, if you have already downloaded the version
requirements = runner.get_test_parameter()  # load default configuration
requirements['TestParameter']['Biceps547TimeInterval'] = 10
# save and run as above
```

### Logging

A logger is available to log the output of the test suite `logging.getLogger('pysdccc')`.
Please note that each line of the test suite output is logged as a separate log message.

## Notices

`pysdccc` is not intended for use in medical products, clinical trials, clinical studies, or in clinical routine.

### ISO 9001

`pysdccc` was not developed according to ISO 9001.

## License

[MIT](https://choosealicense.com/licenses/mit/)
