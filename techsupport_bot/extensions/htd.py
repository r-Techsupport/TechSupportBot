"""
Convert a value or evalute a mathematical expression to decimal, hex, binary, and ascii encoding
"""
import base
import discord
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """
    boilerplate to load htd class
    """
    await bot.add_cog(Htd(bot=bot))


class Htd(base.BaseCog):
    """
    perform calculations on cross-base numbers and convert between them
    """

    OPERATORS = ["+", "-", "*", "/"]

    def split_nicely(self, str_to_split: str) -> list:
        """Takes an input string of an equation, and
            returns a list with numbers and operators in seperate parts

        Args:
            str_to_split (str): The equation to parse

        Returns:
            list: A list containing strings of the operators and numbers
        """

        parsed_list: list = []
        val_buffer = ""

        for character in str_to_split:
            if character == "-" and not val_buffer:
                # If the buffer is empty, we have just found either a number or operator
                # In this case, if the next character is a '-', it must be a negative
                # in a properly formed equation
                val_buffer += character
            elif character in self.OPERATORS:
                # If the character is an operator, we add the finished character to the list
                # And then we add the operator to the list
                parsed_list.append(val_buffer)
                parsed_list.append(character)
                val_buffer = ""
            else:
                # Otherwise, we add the character to the buffer, as it must be part of a number
                val_buffer += character

        # At the end of the string, whatever we have left must be the last number in the equation
        # So, we must append it
        parsed_list.append(val_buffer)

        return parsed_list

    def convert_value_to_integer(self, val: str) -> int:
        """Converts a given value as hex, binary, or decimal into an integer type

        Args:
            val (str): The given value to convert

        Returns:
            int: The value represeted as an integer
        """

        if val.replace("-", "").startswith("0x"):
            # input detected as hex
            num_base = 16
        elif val.replace("-", "").startswith("0b"):
            # input detected as binary
            num_base = 2
        else:
            # assume the input is detected as an int
            num_base = 10
        # special handling is needed for floats
        if "." in val:
            return int(float(val))

        return int(val, num_base)

    def perform_op_on_list(self, equation_list: list) -> int:
        """This will compute an equation if passed as a list
        This does not use eval()
        This expected a list of integers and OPERATORS only

        Args:
            equation_list (list): The equation in a list form

        Raises:
            ValueError: If the operator is not valid, this is raised

        Returns:
            int: The integer value of the computed equation
        """

        running_value = equation_list[0]
        current_operator = ""
        for index, value in enumerate(equation_list):
            if index == 0:
                continue
            if index % 2 == 1:
                # Odd position must be an operator
                current_operator = value
            else:
                # Even position, must be a number
                if current_operator == "+":
                    running_value = running_value + value
                elif current_operator == "-":
                    running_value = running_value - value
                elif current_operator == "*":
                    running_value = running_value * value
                elif current_operator == "/":
                    running_value = int(running_value / value)
                else:
                    raise ValueError("Invalid Equation")
        return running_value

    @commands.command(
        name="htd",
        brief="Convert values to different bases",
        description="Takes a value and returns the value in different bases\
             and encodings (bianary, hex, base 10, and ascii)",
        usage="`htd [value]`\nAccepts numbers in the following formats:\n0x \
            (hex)\n0b (binary) \nNo prefix (assumed ascii)",
    )
    async def htd(self, ctx, *, val_to_convert):
        """This discord command for .htd

        Args:
            ctx (commands.Context): The context in which the command was called at
            val_to_convert (str): The raw conversion request
        """
        await self.htd_command(ctx, val_to_convert)

    def clean_input(self, input: str) -> str:
        """A method to clean up input to be better processed by later functions
        This replaces "#" with "0x" to recoginzed "#" as hex
        It also removes quotes and spaces

        Args:
            input (str): The raw input from the user

        Returns:
            str: The cleaned up string
        """
        input = input.replace("#", "0x")
        input = input.replace("'", "")
        input = input.replace('"', "")
        input = input.replace(" ", "")
        return input

    def convert_list_to_ints(self, raw_list: list) -> list:
        """This converts the values in an equation list into ints

        Args:
            raw_list (list): An equation formatted as a list

        Returns:
            list: The same list you passed in, but with only ints
        """
        for index, value in enumerate(raw_list):
            if index % 2 == 1:
                continue
            raw_list[index] = self.convert_value_to_integer(value)
        return raw_list

    def integer_to_hexadecimal(self, integer: int) -> str:
        """Takes an integer in and returns a string representation in hex
        This will return in the format of "0x05"

        Args:
            integer (int): The integer to convert to hex

        Returns:
            str: The hexadecimal representation of the input
        """
        raw_hex = hex(integer)
        compare_value = 1
        if raw_hex.startswith("-"):
            compare_value = 0

        if len(raw_hex) % 2 == compare_value:
            raw_hex = raw_hex.replace("0x", "0x0")

        return raw_hex

    def integer_to_binary(self, integer: int) -> str:
        """Takes an integer in and returns a string representation in binary

        Args:
            integer (int): The integer to convert to binary

        Returns:
            str: The binary representation of the input
        """
        return bin(integer)

    def integer_to_ascii(self, integer: int) -> str:
        """Takes an integer in and returns a string representation in ascii

        Args:
            integer (int): The integer to convert to ascii

        Returns:
            str: The ascii representation of the input
        """
        raw_hex = hex(integer)
        raw_hex = raw_hex.replace("0x", "")
        raw_hex = raw_hex.replace("-", "")
        hex_bytes = str(bytes.fromhex(raw_hex).decode("unicode_escape"))
        return hex_bytes

    def format_embed_field(self, data: str) -> str:
        """Turns an input string into a formatted string ready to be added to the embed
        The length of the field cannot be more than 1024, so if the length is greater than
        1024, we replace the last 3 characters with full stops

        Args:
            data (str): The raw input to ormat

        Returns:
            str: The string output, either left alone or cropped
        """
        if len(data) <= 1024:
            return data
        return data[:1021] + "..."

    def custom_embed_generation(
        self, raw_input: str, val_to_convert: int
    ) -> discord.Embed:
        """Generates, but does not send, a formatted embed

        Args:
            raw_input (str): The raw input from the user, to display in the embed
            val_to_convert (int): The value to convert from

        Returns:
            discord.Embed: The formatted embed
        """
        embed = auxiliary.generate_basic_embed(
            title="Your conversion results",
            description=f"Converting `{raw_input}`",
            color=discord.Color.green(),
        )
        # Start by adding decimal
        embed.add_field(
            name="Decimal:",
            value=self.format_embed_field(str(val_to_convert)),
            inline=False,
        )

        # Next, add hex
        embed.add_field(
            name="Hexadecimal:",
            value=self.format_embed_field(self.integer_to_hexadecimal(val_to_convert)),
            inline=False,
        )

        # Next, add binary
        embed.add_field(
            name="Binary:",
            value=self.format_embed_field(self.integer_to_binary(val_to_convert)),
            inline=False,
        )

        try:
            ascii_value = self.format_embed_field(self.integer_to_ascii(val_to_convert))
        except ValueError:
            ascii_value = "No ascii representation could be made"

        # Finally, add ascii encoding

        embed.add_field(
            name="Ascii encoding:",
            value=ascii_value,
            inline=False,
        )

        return embed

    async def htd_command(self, ctx: commands.Context, val_to_convert: str) -> None:
        """The main logic for the htd command

        Args:
            ctx (command.Context): The context in which the command was run it
            val_to_convert (str): The raw user input
        """
        val_to_convert = self.clean_input(val_to_convert)

        # Convert the input into a list, splitting on operators and numbers
        # A non-equation input will have a list size of one
        parsed_list = self.split_nicely(val_to_convert)

        # Convert the list to all ints
        try:
            int_list = self.convert_list_to_ints(parsed_list.copy())
        except ValueError:
            await auxiliary.send_deny_embed(
                message="Unable to convert value, are you sure it's valid?",
                channel=ctx.channel,
            )
            return

        # Attempt to parse the given equation and return a single integer answer
        try:
            calced_val = self.perform_op_on_list(int_list)
        except ValueError:
            await auxiliary.send_deny_embed(
                message="Unable to perform calculation, are you sure that equation is valid?",
                channel=ctx.channel,
            )
            return

        embed = self.custom_embed_generation(val_to_convert, calced_val)
        await ctx.send(embed=embed)
