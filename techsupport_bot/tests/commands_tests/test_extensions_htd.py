"""
This is a file to test the extensions/htd.py file
This contains 46 tests
"""

from __future__ import annotations

from typing import Self

import pytest
from commands import htd


class Test_SplitNicely:
    """A set of tests to test split_nicely"""

    def test_single_number(self: Self) -> None:
        """A test to ensure that when just a single number is passed,
        only a single entry is returned"""

        # Step 2 - Call the function
        output = htd.split_nicely("5")

        # Step 3 - Assert that everything works
        assert output == ["5"]

    def test_simple_equation(self: Self) -> None:
        """A test to ensure that equations are split properly"""

        # Step 2 - Call the function
        output = htd.split_nicely("5+5")

        # Step 3 - Assert that everything works
        assert output == ["5", "+", "5"]

    def test_negative(self: Self) -> None:
        """A test to ensure that negatives are handled properly"""

        # Step 2 - Call the function
        output = htd.split_nicely("-2")

        # Step 3 - Assert that everything works
        assert output == ["-2"]

    def test_double_minus(self: Self) -> None:
        """A test to ensure that 2 minus signs in a row are handled properly"""

        # Step 2 - Call the function
        output = htd.split_nicely("5--8")

        # Step 3 - Assert that everything works
        assert output == ["5", "-", "-8"]

    def test_every_operator(self: Self) -> None:
        """A test to ensure that every operator is recognized"""

        # Step 2 - Call the function
        output = htd.split_nicely("1+2-3*4/5")

        # Step 3 - Assert that everything works
        assert output == ["1", "+", "2", "-", "3", "*", "4", "/", "5"]

    def test_long_number(self: Self) -> None:
        """A test to ensure that long numbers are added correctly"""

        # Step 2 - Call the function
        output = htd.split_nicely("3276856238658273658724658247658245")

        # Step 3 - Assert that everything works
        assert output == ["3276856238658273658724658247658245"]


class Test_ConvertToInt:
    """Tests for convert_value_to_integer"""

    def test_simple_hexadecimal(self: Self) -> None:
        """Test that a simple hex value is properly converted"""

        # Step 2 - Call the function
        output = htd.convert_value_to_integer("0x5")

        # Step 3 - Assert that everything works
        assert output == 5

    def test_complex_hexadecimal(self: Self) -> None:
        """Test that a complex hex value is properly converted"""

        # Step 2 - Call the function
        output = htd.convert_value_to_integer("0xFBA34")

        # Step 3 - Assert that everything works
        assert output == 1030708

    def test_simple_binary(self: Self) -> None:
        """Test that a simple binary value is properly converted"""

        # Step 2 - Call the function
        output = htd.convert_value_to_integer("0b1")

        # Step 3 - Assert that everything works
        assert output == 1

    def test_complex_binary(self: Self) -> None:
        """Test that a complex binary value is properly converted"""

        # Step 2 - Call the function
        output = htd.convert_value_to_integer("0b10101010100110")

        # Step 3 - Assert that everything works
        assert output == 10918

    def test_simple_decimal(self: Self) -> None:
        """Test that a simple deciaml value is properly converted"""

        # Step 2 - Call the function
        output = htd.convert_value_to_integer("8")

        # Step 3 - Assert that everything works
        assert output == 8

    def test_complex_decimal(self: Self) -> None:
        """Test that a complex deciaml value is properly converted"""

        # Step 2 - Call the function
        output = htd.convert_value_to_integer("58934275971834685")

        # Step 3 - Assert that everything works
        assert output == 58934275971834685

    def test_float_handling(self: Self) -> None:
        """Test that a float is turned into an integer"""

        # Step 2 - Call the function
        output = htd.convert_value_to_integer("1.2")

        # Step 3 - Assert that everything works
        assert output == 1


class Test_PerformOperator:
    """Tests to test perform_op_on_list"""

    def test_single_integer(self: Self) -> None:
        """A test to ensure that a single integer input is not modified"""

        # Step 2 - Call the function
        output = htd.perform_op_on_list([1])

        # Step 3 - Assert that everything works
        assert output == 1

    def test_single_operator(self: Self) -> None:
        """A test to ensure that operations work as expected"""

        # Step 2 - Call the function
        output = htd.perform_op_on_list([3, "+", 4])

        # Step 3 - Assert that everything works
        assert output == 7

    def test_multiple_operator(self: Self) -> None:
        """A test to ensure that multiple operators work"""

        # Step 2 - Call the function
        output = htd.perform_op_on_list([3, "+", 4, "-", 5])

        # Step 3 - Assert that everything works
        assert output == 2

    def test_all_operator(self: Self) -> None:
        """A test to ensure that all operators work"""

        # Step 2 - Call the function
        output = htd.perform_op_on_list([3, "+", 4, "-", 5, "*", 6, "/", 2])

        # Step 3 - Assert that everything works
        assert output == 6

    def test_negative_number(self: Self) -> None:
        """A test to ensure that negative numbers work"""

        # Step 2 - Call the function
        output = htd.perform_op_on_list([-3, "+", 4])

        # Step 3 - Assert that everything works
        assert output == 1


class Test_CleanInput:
    """A set of tests to test clean_input"""

    def test_replacing_hex(self: Self) -> None:
        """A test to ensure that # is replaced with 0x"""

        # Step 2 - Call the function
        output = htd.clean_input("#124")

        # Step 3 - Assert that everything works
        assert output == "0x124"

    def test_stripping_spaces(self: Self) -> None:
        """A test to ensure that spaces are removed from the string"""

        # Step 2 - Call the function
        output = htd.clean_input("5                  +                      5")

        # Step 3 - Assert that everything works
        assert output == "5+5"

    def test_stripping_quotes(self: Self) -> None:
        """A test to ensure that quotes are removed from the string"""

        # Step 2 - Call the function
        output = htd.clean_input("\"5'")

        # Step 3 - Assert that everything works
        assert output == "5"


class Test_ConvertList:
    """Tests to test convert_list_to_ints"""

    def test_single_int(self: Self) -> None:
        """A test to ensure that just a single int is correctly converted"""

        # Step 2 - Call the function
        output = htd.convert_list_to_ints(["5"])

        # Step 3 - Assert that everything works
        assert output == [5]

    def test_equations(self: Self) -> None:
        """A test to ensure that just a single int is correctly converted"""

        # Step 2 - Call the function
        output = htd.convert_list_to_ints(["5", "+", "5"])

        # Step 3 - Assert that everything works
        assert output == [5, "+", 5]


class Test_IntToHex:
    """Tests to test integer_to_hexadecimal"""

    def test_simple_hex(self: Self) -> None:
        """This tests to ensure that a basic hex conversion works"""

        # Step 2 - Call the function
        output = htd.integer_to_hexadecimal(16)

        # Step 3 - Assert that everything works
        assert output == "0x10"

    def test_complex_hex(self: Self) -> None:
        """This tests to ensure that a complex hex conversion works"""

        # Step 2 - Call the function
        output = htd.integer_to_hexadecimal(847653289450)

        # Step 3 - Assert that everything works
        assert output == "0xc55c12bdea"

    def test_hex_styling(self: Self) -> None:
        """This tests to ensure that the styling works"""

        # Step 2 - Call the function
        output = htd.integer_to_hexadecimal(5)

        # Step 3 - Assert that everything works
        assert output == "0x05"

    def test_negative_hex(self: Self) -> None:
        """This tests to ensure that the hex maintains it's negative"""

        # Step 2 - Call the function
        output = htd.integer_to_hexadecimal(-5)

        # Step 3 - Assert that everything works
        assert output == "-0x05"


class Test_IntToBin:
    """Tests to test integer_to_binary"""

    def test_simple_bin(self: Self) -> None:
        """This tests to ensure that a basic binary conversion works"""

        # Step 2 - Call the function
        output = htd.integer_to_binary(1)

        # Step 3 - Assert that everything works
        assert output == "0b1"

    def test_complex_bin(self: Self) -> None:
        """This tests to ensure that a complex binary conversion works"""

        # Step 2 - Call the function
        output = htd.integer_to_binary(98235671235)

        # Step 3 - Assert that everything works
        assert output == "0b1011011011111010011010110001011000011"

    def test_negative_hex(self: Self) -> None:
        """This tests to ensure that the binary maintains it's negative"""

        # Step 2 - Call the function
        output = htd.integer_to_binary(-5)

        # Step 3 - Assert that everything works
        assert output == "-0b101"


class Test_IntToAscii:
    """Tests to test integer_to_ascii"""

    def test_simple_ascii(self: Self) -> None:
        """This tests to ensure that a basic ascii conversion works"""

        # Step 2 - Call the function
        output = htd.integer_to_ascii(65)

        # Step 3 - Assert that everything works
        assert output == "A"

    def test_complex_ascii(self: Self) -> None:
        """This tests to ensure that a complex ascii conversion works"""

        # Step 2 - Call the function
        output = htd.integer_to_ascii(18946016917865816)

        # Step 3 - Assert that everything works
        assert output == "COMPLEX"

    def test_invalid_ascii(self: Self) -> None:
        with pytest.raises(ValueError):
            htd.integer_to_ascii(1)


class Test_FormatEmbedField:
    """Tests to test format_embed_field"""

    def test_short_string(self: Self) -> None:
        """A test to ensure that a short string is not touched"""

        # Step 2 - Call the function
        output = htd.format_embed_field("ABCD")

        # Step 3 - Assert that everything works
        assert output == "ABCD"

    def test_1024_string(self: Self) -> None:
        """A test to ensure that a string of lenght 1024 is not touched"""
        # Step 2 - Call the function
        output = htd.format_embed_field("A" * 1024)

        # Step 3 - Assert that everything works
        assert output == "A" * 1024

    def test_long_string(self: Self) -> None:
        """A test to ensure that a long string is cropped"""

        # Step 2 - Call the function
        output = htd.format_embed_field("A" * 2024)

        # Step 3 - Assert that everything works
        assert output == "A" * 1021 + "..."
