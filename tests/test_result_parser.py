"""test for module result_parser.py."""

import pathlib
from typing import Type
import uuid
from unittest import mock

import pytest
from junitparser import JUnitXml, junitparser  # pyright: ignore [reportPrivateImportUsage]
from junitparser import TestCase as JUnitTestCase  # pyright: ignore [reportPrivateImportUsage]
from junitparser import TestSuite as JUnitTestSuite  # pyright: ignore [reportPrivateImportUsage]

from pysdccc._result_parser import TestCase, TestDescriptionElement, TestIdentifierElement, TestSuite


def test_test_identifier_element_text():
    """Test that the text property of TestIdentifierElement returns the correct text."""
    text = uuid.uuid4().hex
    element = TestIdentifierElement()
    element._elem = mock.Mock()  # noqa: SLF001
    element._elem.text = text  # noqa: SLF001
    assert element.text == text


def test_test_description_element_text():
    """Test that the text property of TestDescriptionElement returns the correct text."""
    text = uuid.uuid4().hex
    element = TestDescriptionElement()
    element._elem = mock.Mock()  # noqa: SLF001
    element._elem.text = text  # noqa: SLF001
    assert element.text == text


def test_test_case_test_identifier():
    """Test that the test_identifier property of TestCase returns the correct identifier."""
    text = uuid.uuid4().hex
    test_case = TestCase()
    test_case._elem = mock.Mock()  # noqa: SLF001
    test_case.child = mock.Mock(return_value=TestIdentifierElement())
    test_case.child()._elem = mock.Mock()  # noqa: SLF001
    test_case.child()._elem.text = text  # noqa: SLF001
    assert test_case.test_identifier == text


def test_test_case_test_description():
    """Test that the test_description property of TestCase returns the correct description."""
    text = uuid.uuid4().hex
    test_case = TestCase()
    test_case._elem = mock.Mock()  # noqa: SLF001
    test_case.child = mock.Mock(return_value=TestDescriptionElement())
    test_case.child()._elem = mock.Mock()  # noqa: SLF001
    test_case.child()._elem.text = text  # noqa: SLF001
    assert test_case.test_description == text


def test_test_suite_iter():
    """Test that the TestSuite iterator returns TestCase instances."""
    test_cases = [JUnitTestCase(), JUnitTestCase()]
    suite = TestSuite()
    suite._elem = mock.Mock()  # noqa: SLF001
    suite._elem.iterfind = lambda _: iter(test_cases)  # noqa: SLF001
    assert len(test_cases) == len(suite)
    for case in suite:
        assert isinstance(case, TestCase)


@mock.patch('pysdccc._result_parser.junitparser.JUnitXml.fromfile')
def test_test_suite_from_file(mock_fromfile: mock.MagicMock):
    """Test that the from_file method of TestSuite returns a TestSuite instance."""
    mock_suite = JUnitTestSuite()
    mock_fromfile.return_value = mock_suite
    suite = TestSuite.from_file('dummy_path')
    assert isinstance(suite, TestSuite)
    assert suite == mock_suite

    mock_fromfile.return_value = JUnitXml()
    with pytest.raises(TypeError, match=f'Expected class {junitparser.TestSuite}, got {type(JUnitXml())}'):
        TestSuite.from_file('dummy_path')


def test_result_file_parser():
    """Test whether the test identifier and description is correctly parsed."""
    data = (
        (
            'BICEPS.R5039',
            'Sends a get context states message with empty handle ref and verifies that the response '
            'contains all context states of the mdib.',
        ),
        (
            'BICEPS.R5040',
            'Verifies that for every known context descriptor handle the corresponding context states are returned.',
        ),
        (
            'BICEPS.R5041',
            'Verifies that for every known context state handle the corresponding context state is returned.',
        ),
        ('SDCccTestRunValidity', 'SDCcc Test Run Validity'),
    )
    suite = TestSuite.from_file(pathlib.Path(__file__).parent.joinpath('sdccc_result.xml'))
    assert isinstance(suite, TestSuite)
    assert len(data) == len(suite)
    for test_case, (identifier, description) in zip(suite, data, strict=True):
        assert test_case.test_identifier == identifier
        assert test_case.test_description == description
