"""Module for the win error dictionary extension for the discord bot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Setup extensions held in this file:
    WindowsError

    Args:
        bot (bot.TechSupportBot): The bot to register the extensions
    """

    await bot.add_cog(WindowsError(bot=bot, extension_name="winerror"))


@dataclass
class Error:
    """The data to pull for the error.

    Attrs:
        name (str): the name of the error
        source (str): the header file where the error is from
        description (str): the description of the error
    """

    name: str
    source: str
    description: str


@dataclass
class ErrorCategory:
    """A category of errors, based on how the error was found
    This contains the name of the category and a list of errors

    Attrs:
        name (str): The name of the category of errors
        errors (list[Error]): The list of errors in the category

    """

    name: str
    errors: list[Error]


class WindowsError(cogs.BaseCog):
    """The core of the /winerror extension"""

    async def preconfig(self: Self) -> None:
        """Loads the winerrors.json file as self.errors"""
        errors_file = "resources/winerrors.json"
        with open(errors_file, "r", encoding="utf-8") as file:
            self.errors = json.load(file)

    @app_commands.command(
        name="winerror",
        description="Searches the windows error database based on input",
        extras={"module": "winerror"},
    )
    async def winerror(
        self: Self, interaction: discord.Interaction, search_term: str
    ) -> None:
        """The heart of the winerror command
        This process in input and calls functions to search for errors

        Args:
            interaction (discord.Interaction): The interaction that started the command
            search_term (str): The decimal or hex value to search for

        Raises:
            ValueError: In the event the hex is invalid
        """
        # Convert entry into decimal and hex
        decimal_code = self.try_parse_decimal(search_term)
        hex_code = self.try_parse_hex(search_term)

        # winerror searches for the full error code as well as an HRESULT structure. Here we pad
        # out the given argument to ensure the string is 10 digits (0x), then break out the padded
        # code into its HRESULT structure.
        padded_hex_code = self.pad_hex(hex(hex_code))
        trunc_hex_code = int(padded_hex_code[6:10], 16)
        severity = "FAILURE (1)"
        facility_code = 0x0
        upper_sixteen = padded_hex_code[2:6]
        try:
            if int(upper_sixteen[0], 16) > 7:
                facility_code = int(upper_sixteen, 16) - 0x8000
            else:
                severity = "SUCCESS (0)"
                facility_code = upper_sixteen
        except ValueError as exc:
            # this should never happen. the 32-bit checks in tryParseHex along with the 10 digit
            # check in padhex() should prevent the failure. The catch is here just in case I
            # missed an edge case.
            raise ValueError(
                f"ValueError: {padded_hex_code}, {hex_code}, {upper_sixteen}"
            ) from exc

        # A list of all categories with at least one error
        categories: list[ErrorCategory] = []

        # Hex errors - this must exist
        hex_errors = self.handle_hex_errors(hex_code)
        if hex_errors:
            categories.append(hex_errors)

        # hresult error - this might exist
        if hex_code != trunc_hex_code:
            hresult_errors = self.handle_hresult_errors(
                trunc_hex_code, severity, facility_code
            )
            if hresult_errors:
                categories.append(hresult_errors)

        # Decimal error - this might exist
        if decimal_code > 0 and hex_code != hex(decimal_code):
            decimal_errors = self.handle_decimal_errors(decimal_code)
            if decimal_errors:
                categories.append(decimal_errors)

        if len(categories) == 0:
            embed = auxiliary.prepare_deny_embed(
                f"No errors could be found for search term '{search_term}`"
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed()
        embed.title = "Windows error search results"
        embed.description = f"Search results for `{search_term}`"
        embed.color = discord.Color.blue()

        cat_count = 1
        # For every category, add a category header and then
        # loop through all errors in the category
        for category in categories:
            embed.add_field(
                name=f"Category {cat_count}", value=category.name, inline=False
            )
            cat_count += 1
            for error in category.errors:
                embed.add_field(
                    name=f"{error.name} - {error.source}",
                    value=error.description,
                    inline=False,
                )

        await interaction.response.send_message(embed=embed)

    def handle_hresult_errors(
        self: Self, trunc_hex_code: int, severity: str, facility_code: int
    ) -> ErrorCategory:
        """Searches for and returns the hresult errors

        Args:
            trunc_hex_code (int): _description_
            severity (str): _description_
            facility_code (int): _description_

        Returns:
            ErrorCategory: The category with header and array of hresult errors
        """
        valid_errors_trunc = [
            x
            for x in self.errors
            if x["hex"] == hex(trunc_hex_code)
            and (x["header"] == "winerror.h" or x["header"] == "winbio_err.h")
        ]
        if len(valid_errors_trunc) == 0:
            return None

        category = ErrorCategory(
            f"As an HRESULT: Severity: {severity}, Facility: {hex(facility_code)},"
            f" Code: {hex(trunc_hex_code)}",
            [],
        )
        for error in valid_errors_trunc:
            category.errors.append(
                Error(error["name"], error["header"], error["description"])
            )
        return category

    def handle_decimal_errors(self: Self, decimal_code: int) -> ErrorCategory:
        """Searches for errors based on a decimal input

        Args:
            decimal_code (int): The decimal number to match errors to

        Returns:
            ErrorCategory: The category with header and array of decimal errors
        """
        valid_errors_decimal = [x for x in self.errors if x["hex"] == hex(decimal_code)]
        if len(valid_errors_decimal) == 0:
            return None
        category = ErrorCategory(
            f"For decimal {decimal_code} / hex {hex(decimal_code)}", []
        )
        for error in valid_errors_decimal:
            category.errors.append(
                Error(error["name"], error["header"], error["description"])
            )
        return category

    def handle_hex_errors(self: Self, hex_code: int) -> ErrorCategory:
        """Searches for errors based on a hex input

        Args:
            hex_code (int): The hex number to match errors to

        Returns:
            ErrorCategory: The category with header and array of hex errors
        """
        valid_errors_hex = [x for x in self.errors if x["hex"] == hex(hex_code)]
        if len(valid_errors_hex) == 0:
            return None
        category = ErrorCategory(
            f"For hex {hex(hex_code)} / decimal {self.twos_comp(hex_code, 32)}", []
        )
        for error in valid_errors_hex:
            category.errors.append(
                Error(error["name"], error["header"], error["description"])
            )
        return category

    def twos_comp(self: Self, original_value: int, bits: int) -> int:
        """Compute the two's complement of an integer value.

        Args:
            original_value (int): The original integer value.
            bits (int): How many bits need to be shifted.

        Returns:
            int: The two's complement of the original integer value.
        """
        if (
            original_value & (1 << (bits - 1)) != 0
        ):  # if sign bit is set e.g., 8bit: 128-255
            original_value = original_value - (1 << bits)  # compute negative value
        return original_value

    def reverse_twos_comp(self: Self, original_value: int, bits: int) -> int:
        """Gets the reverse twos complement for the given input

        Args:
            original_value (int): The value to find the unsigned value for
            bits (int): How many bits need to be shifted

        Returns:
            int: The value with a reverse twos complement
        """
        return (1 << bits) - 1 - ~original_value

    def try_parse_decimal(self: Self, original_value: str) -> int:
        """Parse a string input into a decimal value. If this fails, 0 is returned

        Args:
            original_value (str): The string input to turn into a decimal

        Returns:
            int: 0, or the properly converted string
        """
        # check if the target error code is a base 10 integer
        try:
            return_val = int(original_value, 10)
            # Error codes are unsigned. If a negative number is input, the only code we're
            # interested in is the hex equivalent.
            if return_val <= 0:
                return 0
            return return_val
        except ValueError:
            return 0  # 0 will not be checked when searching for the code's definition.

    # Check if the error code is a valid hex number.
    # Returns 0xFFFF, or CDERR_DIALOGFAILURE upon invalid code.
    def try_parse_hex(self: Self, original_value: str) -> int:
        """Parse a string input into a hex value. If this fails, 0xFFFF is returned

        Args:
            original_value (str): The string input to turn into a hex

        Returns:
            int: 0xFFFF, or the properly converted string
        """
        # check if the target error code is a base 16 integer
        try:
            # if the number is a negative decimal number, we need its unsigned hexadecimal
            # equivalent.
            if int(original_value, 16) < 0:
                if abs(int(original_value)) > 0xFFFFFFFF:
                    return 0xFFFF
                # the integer conversion here is deliberately a base 10 conversion. The command
                # should fail if a negative hex number is queried.
                return self.reverse_twos_comp(int(original_value), 32)
            # check if the number is larger than 32 bits
            if abs(int(original_value, 16)) > 0xFFFFFFFF:
                return 0xFFFF

            return int(original_value, 16)

        except ValueError:
            return 0xFFFF

    def pad_hex(self: Self, hex_code_input: str) -> str:
        """Pads a hex value

        Args:
            hex_code_input (str): The input value to add 0s to

        Returns:
            str: The padded value
        """
        # this string should never be over 10 characters, however this check is here
        # just in case there's a bug in the code.
        if len(hex_code_input) > 10:
            return "0xFFFF"

        return "0x" + hex_code_input[2:].zfill(8)
