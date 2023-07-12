"""
This is a file to test the extensions/htd.py file
This contains 46 tests
"""

import importlib
from unittest.mock import AsyncMock, MagicMock, call, patch

import discord
import pytest
from base import auxiliary
from extensions import htd

from . import config_for_tests


def setup_local_extension(bot=None):
    """A simple function to setup an instance of the htd extension

    Args:
        bot (MockBot, optional): A fake bot object. Should be used if using a
        fake_discord_env in the test. Defaults to None.

    Returns:
        HTD: The instance of the htd class
    """
    with patch("asyncio.create_task", return_value=None):
        return htd.Htd(bot)


class Test_SplitNicely:
    """A set of tests to test split_nicely"""

    def test_single_number(self):
        """A test to ensure that when just a single number is passed,
        only a single entry is returned"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("5")

        # Step 3 - Assert that everything works
        assert output == ["5"]

    def test_simple_equation(self):
        """A test to ensure that equations are split properly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("5+5")

        # Step 3 - Assert that everything works
        assert output == ["5", "+", "5"]

    def test_negative(self):
        """A test to ensure that negatives are handled properly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("-2")

        # Step 3 - Assert that everything works
        assert output == ["-2"]

    def test_double_minus(self):
        """A test to ensure that 2 minus signs in a row are handled properly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("5--8")

        # Step 3 - Assert that everything works
        assert output == ["5", "-", "-8"]

    def test_every_operator(self):
        """A test to ensure that every operator is recognized"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("1+2-3*4/5")

        # Step 3 - Assert that everything works
        assert output == ["1", "+", "2", "-", "3", "*", "4", "/", "5"]

    def test_long_number(self):
        """A test to ensure that long numbers are added correctly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("3276856238658273658724658247658245")

        # Step 3 - Assert that everything works
        assert output == ["3276856238658273658724658247658245"]


class Test_ConvertToInt:
    """Tests for convert_value_to_integer"""

    def test_simple_hexadecimal(self):
        """Test that a simple hex value is properly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.convert_value_to_integer("0x5")

        # Step 3 - Assert that everything works
        assert output == 5

    def test_complex_hexadecimal(self):
        """Test that a complex hex value is properly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.convert_value_to_integer("0xFBA34")

        # Step 3 - Assert that everything works
        assert output == 1030708

    def test_simple_binary(self):
        """Test that a simple binary value is properly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.convert_value_to_integer("0b1")

        # Step 3 - Assert that everything works
        assert output == 1

    def test_complex_binary(self):
        """Test that a complex binary value is properly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.convert_value_to_integer("0b10101010100110")

        # Step 3 - Assert that everything works
        assert output == 10918

    def test_simple_decimal(self):
        """Test that a simple deciaml value is properly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.convert_value_to_integer("8")

        # Step 3 - Assert that everything works
        assert output == 8

    def test_complex_decimal(self):
        """Test that a complex deciaml value is properly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.convert_value_to_integer("58934275971834685")

        # Step 3 - Assert that everything works
        assert output == 58934275971834685

    def test_float_handling(self):
        """Test that a float is turned into an integer"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.convert_value_to_integer("1.2")

        # Step 3 - Assert that everything works
        assert output == 1


class Test_PerformOperator:
    """Tests to test perform_op_on_list"""

    def test_single_integer(self):
        """A test to ensure that a single integer input is not modified"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.perform_op_on_list([1])

        # Step 3 - Assert that everything works
        assert output == 1

    def test_single_operator(self):
        """A test to ensure that operations work as expected"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.perform_op_on_list([3, "+", 4])

        # Step 3 - Assert that everything works
        assert output == 7

    def test_multiple_operator(self):
        """A test to ensure that multiple operators work"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.perform_op_on_list([3, "+", 4, "-", 5])

        # Step 3 - Assert that everything works
        assert output == 2

    def test_all_operator(self):
        """A test to ensure that all operators work"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.perform_op_on_list([3, "+", 4, "-", 5, "*", 6, "/", 2])

        # Step 3 - Assert that everything works
        assert output == 6

    def test_negative_number(self):
        """A test to ensure that negative numbers work"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.perform_op_on_list([-3, "+", 4])

        # Step 3 - Assert that everything works
        assert output == 1


class Test_CleanInput:
    """A set of tests to test clean_input"""

    def test_replacing_hex(self):
        """A test to ensure that # is replaced with 0x"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.clean_input("#124")

        # Step 3 - Assert that everything works
        assert output == "0x124"

    def test_stripping_spaces(self):
        """A test to ensure that spaces are removed from the string"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.clean_input("5                  +                      5")

        # Step 3 - Assert that everything works
        assert output == "5+5"

    def test_stripping_quotes(self):
        """A test to ensure that quotes are removed from the string"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.clean_input("\"5'")

        # Step 3 - Assert that everything works
        assert output == "5"


class Test_ConvertList:
    """Tests to test convert_list_to_ints"""

    def test_single_int(self):
        """A test to ensure that just a single int is correctly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()
        hextodec.convert_value_to_integer = MagicMock(return_value=5)

        # Step 2 - Call the function
        output = hextodec.convert_list_to_ints(["5"])

        # Step 3 - Assert that everything works
        assert output == [5]

    def test_equations(self):
        """A test to ensure that just a single int is correctly converted"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()
        hextodec.convert_value_to_integer = MagicMock(return_value=5)

        # Step 2 - Call the function
        output = hextodec.convert_list_to_ints(["5", "+", "5"])

        # Step 3 - Assert that everything works
        assert output == [5, "+", 5]


class Test_IntToHex:
    """Tests to test integer_to_hexadecimal"""

    def test_simple_hex(self):
        """This tests to ensure that a basic hex conversion works"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_hexadecimal(16)

        # Step 3 - Assert that everything works
        assert output == "0x10"

    def test_complex_hex(self):
        """This tests to ensure that a complex hex conversion works"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_hexadecimal(847653289450)

        # Step 3 - Assert that everything works
        assert output == "0xc55c12bdea"

    def test_hex_styling(self):
        """This tests to ensure that the styling works"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_hexadecimal(5)

        # Step 3 - Assert that everything works
        assert output == "0x05"

    def test_negative_hex(self):
        """This tests to ensure that the hex maintains it's negative"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_hexadecimal(-5)

        # Step 3 - Assert that everything works
        assert output == "-0x05"


class Test_IntToBin:
    """Tests to test integer_to_binary"""

    def test_simple_bin(self):
        """This tests to ensure that a basic binary conversion works"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_binary(1)

        # Step 3 - Assert that everything works
        assert output == "0b1"

    def test_complex_bin(self):
        """This tests to ensure that a complex binary conversion works"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_binary(98235671235)

        # Step 3 - Assert that everything works
        assert output == "0b1011011011111010011010110001011000011"

    def test_negative_hex(self):
        """This tests to ensure that the binary maintains it's negative"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_binary(-5)

        # Step 3 - Assert that everything works
        assert output == "-0b101"


class Test_IntToAscii:
    """Tests to test integer_to_ascii"""

    def test_simple_ascii(self):
        """This tests to ensure that a basic ascii conversion works"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_ascii(65)

        # Step 3 - Assert that everything works
        assert output == "A"

    def test_complex_ascii(self):
        """This tests to ensure that a complex ascii conversion works"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.integer_to_ascii(18946016917865816)

        # Step 3 - Assert that everything works
        assert output == "COMPLEX"


class Test_FormatEmbedField:
    """Tests to test format_embed_field"""

    def test_short_string(self):
        """A test to ensure that a short string is not touched"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.format_embed_field("ABCD")

        # Step 3 - Assert that everything works
        assert output == "ABCD"

    def test_1024_string(self):
        """A test to ensure that a short string is not touched"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.format_embed_field("A" * 1024)

        # Step 3 - Assert that everything works
        assert output == "A" * 1024

    def test_long_string(self):
        """A test to ensure that a short string is not touched"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.format_embed_field("A" * 2024)

        # Step 3 - Assert that everything works
        assert output == "A" * 1021 + "..."


class Test_CustomEmbed:
    """A set of tests for custom_embed_generation"""

    def test_basic_embed_called(self):
        """A test to ensure that the basic embed is generated correctly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()
        auxiliary.generate_basic_embed = MagicMock()
        hextodec.format_embed_field = MagicMock()
        hextodec.integer_to_hexadecimal = MagicMock()
        hextodec.integer_to_binary = MagicMock()
        hextodec.integer_to_ascii = MagicMock()

        # Step 2 - Call the function
        hextodec.custom_embed_generation("raw", 5)

        # Step 3 - Assert that everything works
        auxiliary.generate_basic_embed.assert_called_once_with(
            title="Your conversion results",
            description="Converting `raw`",
            color=discord.Color.green(),
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    def test_fields_correct(self):
        """A test to ensure that the basic embed is generated correctly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()
        fakeembed = MagicMock()
        fakeembed.add_field = MagicMock()
        auxiliary.generate_basic_embed = MagicMock(return_value=fakeembed)
        hextodec.format_embed_field = MagicMock(return_value="value")
        hextodec.integer_to_hexadecimal = MagicMock()
        hextodec.integer_to_binary = MagicMock()
        hextodec.integer_to_ascii = MagicMock()

        # Step 2 - Call the function
        hextodec.custom_embed_generation("raw", 5)

        # Step 3 - Assert that everything works
        expected_calls = [
            call(
                name="Decimal:",
                value="value",
                inline=False,
            ),
            call(
                name="Hexadecimal:",
                value="value",
                inline=False,
            ),
            call(
                name="Binary:",
                value="value",
                inline=False,
            ),
            call(
                name="Ascii encoding:",
                value="value",
                inline=False,
            ),
        ]
        fakeembed.add_field.assert_has_calls(expected_calls)

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    def test_ascii_error(self):
        """A test to ensure that the basic embed is generated correctly,
        even if int to ascii has a ValueError"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()
        fakeembed = MagicMock()
        fakeembed.add_field = MagicMock()
        auxiliary.generate_basic_embed = MagicMock(return_value=fakeembed)
        hextodec.format_embed_field = MagicMock(return_value="value")
        hextodec.integer_to_hexadecimal = MagicMock()
        hextodec.integer_to_binary = MagicMock()
        hextodec.integer_to_ascii = MagicMock(side_effect=ValueError)

        # Step 2 - Call the function
        hextodec.custom_embed_generation("raw", 5)

        # Step 3 - Assert that everything works
        expected_calls = [
            call(
                name="Decimal:",
                value="value",
                inline=False,
            ),
            call(
                name="Hexadecimal:",
                value="value",
                inline=False,
            ),
            call(
                name="Binary:",
                value="value",
                inline=False,
            ),
            call(
                name="Ascii encoding:",
                value="No ascii representation could be made",
                inline=False,
            ),
        ]
        fakeembed.add_field.assert_has_calls(expected_calls)

        # Step 4 - Cleanup
        importlib.reload(auxiliary)


class Test_HTDCommand:
    """A set of tests to test htd_command"""

    @pytest.mark.asyncio
    async def test_cleaninput_call(self):
        """A test to ensure that clean_input is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock()
        hextodec.split_nicely = MagicMock()
        hextodec.convert_list_to_ints = MagicMock()
        hextodec.perform_op_on_list = MagicMock()
        hextodec.custom_embed_generation = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "     test       ")

        # Step 3 - Assert that everything works
        hextodec.clean_input.assert_called_once_with("     test       ")

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_splitnicely_call(self):
        """A test to ensure that split_nicely is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock(return_value="clean")
        hextodec.split_nicely = MagicMock()
        hextodec.convert_list_to_ints = MagicMock()
        hextodec.perform_op_on_list = MagicMock()
        hextodec.custom_embed_generation = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "test")

        # Step 3 - Assert that everything works
        hextodec.split_nicely.assert_called_once_with("clean")

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_convertints_call(self):
        """A test to ensure that convert_list_to_ints is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock()
        hextodec.split_nicely = MagicMock(return_value=["1", "+", "1"])
        hextodec.convert_list_to_ints = MagicMock()
        hextodec.perform_op_on_list = MagicMock()
        hextodec.custom_embed_generation = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "test")

        # Step 3 - Assert that everything works
        hextodec.convert_list_to_ints.assert_called_once_with(["1", "+", "1"])

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_convertints_error(self):
        """A test to ensure that convert_list_to_ints error is handled correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock()
        hextodec.split_nicely = MagicMock(return_value=["1", "+", "1"])
        hextodec.convert_list_to_ints = MagicMock(side_effect=ValueError)
        hextodec.perform_op_on_list = MagicMock()
        hextodec.custom_embed_generation = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "test")

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="Unable to convert value, are you sure it's valid?",
            channel=discord_env.context.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_performop_call(self):
        """A test to ensure that perform_op_on_list is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock()
        hextodec.split_nicely = MagicMock()
        hextodec.convert_list_to_ints = MagicMock(return_value=[1, "+", 1])
        hextodec.perform_op_on_list = MagicMock()
        hextodec.custom_embed_generation = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "test")

        # Step 3 - Assert that everything works
        hextodec.perform_op_on_list.assert_called_once_with([1, "+", 1])

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_perform_op_error(self):
        """A test to ensure that perform_op_on_list error is handled correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock()
        hextodec.split_nicely = MagicMock()
        hextodec.convert_list_to_ints = MagicMock()
        hextodec.perform_op_on_list = MagicMock(side_effect=ValueError)
        hextodec.custom_embed_generation = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "test")

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="Unable to perform calculation, are you sure that equation is valid?",
            channel=discord_env.context.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_customembed_call(self):
        """A test to ensure that custom_embed_generation is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock(return_value="1")
        hextodec.split_nicely = MagicMock()
        hextodec.convert_list_to_ints = MagicMock()
        hextodec.perform_op_on_list = MagicMock(return_value=1)
        hextodec.custom_embed_generation = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "test")

        # Step 3 - Assert that everything works
        hextodec.custom_embed_generation.assert_called_once_with("1", 1)

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_send_call(self):
        """A test to ensure that perform_op_on_list is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hextodec = setup_local_extension(discord_env.bot)
        hextodec.clean_input = MagicMock()
        hextodec.split_nicely = MagicMock()
        hextodec.convert_list_to_ints = MagicMock()
        hextodec.perform_op_on_list = MagicMock()
        hextodec.custom_embed_generation = MagicMock(return_value="Fake Embed")
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hextodec.htd_command(discord_env.context, "test")

        # Step 3 - Assert that everything works
        discord_env.context.send.assert_called_once_with(embed="Fake Embed")

        # Step 4 - Cleanup
        importlib.reload(auxiliary)
