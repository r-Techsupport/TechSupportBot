"""
Convert a value or evalute a mathematical expression to decimal, hex, binary, and ascii encoding
"""
import discord
from discord.ext import commands

import base



def setup(bot):
    """
    boilerplate to load htd class
    """
    bot.add_cog(Htd(bot=bot))


class Htd(base.BaseCog):
    """
    perform calculations on cross-base numbers and convert between them
    """
    @commands.command(
        name="htd",
        brief="Convert values to different bases",
        description="Takes a value and returns the value in different bases\
             and encodings (bianary, hex, base 10, and ascii)",
        usage="`htd [value]`\nAccepts numbers in the following formats:\n0x \
            (hex)\n0b (binary) \nNo prefix (assumed ascii)"
    )
    async def htd(self, ctx, *, val_to_convert):
        """
        perform calculations on cross base numbers and convert between bases
        """
        def split_nicely(str_to_split: str) -> list:
            """
            take an input string, divide it at operators and spaces,\
                 and return a list of neatly formatted divisions
            """
            mostly_parsed_list: list = []
            # everything between control characters
            val_buffer = []
            while len(str_to_split) > 0:
                if str_to_split[0] == " ":
                    # a space isn't an operator, just a formatting indicator,
                    #  so we don't want to process it
                    # dump the value stored in the buffer into the return list
                    # return_list.append("".join(val_buffer))
                    # val_buffer.clear()
                    str_to_split = str_to_split[1:]

                elif str_to_split[0] in ["+", "-", "*", "/"]:
                    # +-*/ are operators, so they're added to the list
                    if val_buffer:
                        mostly_parsed_list.append("".join(val_buffer))
                    val_buffer.clear()
                    mostly_parsed_list.append(str_to_split[0])
                    str_to_split = str_to_split[1:]
                else:
                    # assume it's part of a value
                    val_buffer.append(str_to_split[0])
                    str_to_split = str_to_split[1:]

            mostly_parsed_list.append("".join(val_buffer))

            # because arabic numerals suck and - is both a value indicator and and operand,
            # some extra parsing needs to be applied
            return_list = []
            range_to_iter_over = iter(list(range(len(mostly_parsed_list))))
            for i in range_to_iter_over:
                if mostly_parsed_list[i] == "-":
                    # first value in the list won't have something before it to
                    # operate against, assume negative
                    if i == 0:
                        # replace first two items with a concatenation of the
                        # two
                        return_list.append(
                            mostly_parsed_list[i] + mostly_parsed_list[i + 1])
                        next(range_to_iter_over)
                        continue
                    # if it's preceeded by another operator, assume negative
                    if mostly_parsed_list[i - 1] in ["+", "-", "*", "/"]:
                        return_list.append(
                            mostly_parsed_list[i] + mostly_parsed_list[i + 1])
                        next(range_to_iter_over)
                        continue

                    return_list.append(mostly_parsed_list[i])
                else:
                    return_list.append(mostly_parsed_list[i])

            return return_list

        def convert_str_to_int(val) -> int:
            """
            Take a string that's int, hex, or dec and convert it to an int as the int type
            """
            # to handle negatives, we selectively figure it out using code n'
            # stuff
            ref_val = val

            if ref_val[0] == "-":
                ref_val = ref_val[1:]

            if ref_val[:2] == "0x" or ref_val[:3] == "-0x":
                # input detected as hex
                num_base = 16
            elif ref_val[:2] == "0b":
                # input detected as binary
                num_base = 2
            else:
                # assume the input is detected as an int
                num_base = 10
            # special handling is needed for floats
            if "." in ref_val:
                return int(float(val))

            return int(val, num_base)


        def gen_embed_from_val(val, return_all=False) -> discord.Embed:
            """
            Take in a value as a string, EG: "0b1011 or "0xf00" and generate a discord embed\
             with the appropriate conversions applied
            """
            # Return embed
            embed = discord.Embed()
            # calculated values for each
            input_as = {
                "Decimal": 0,
                "Hexadecimal": "0x0",
                "Binary": "0b0",
                "Ascii Encoding": "Something is messed up if you're seeing this"
            }

            def clean_up_hex(str_to_clean: str):
                """
                fromhex doesn't like it when it gets hex as 0x. (EG: `0xff`
                is wrong, `ff` is right)
                """

                cleaned_up_hex = str_to_clean
                if str_to_clean[0] == "-":
                    # this is used because fromhex doesn't like 0x
                    cleaned_up_hex = cleaned_up_hex[3:]
                    if len(cleaned_up_hex) % 2:
                        str_to_clean = "-0x0" + cleaned_up_hex
                else:
                    cleaned_up_hex = cleaned_up_hex[2:]
                    if len(cleaned_up_hex) % 2:
                        str_to_clean = "0x0" + cleaned_up_hex
                # first item is with 0x, second is not
                cleaned_up_vals = []
                cleaned_up_vals.append(str_to_clean)
                cleaned_up_vals.append(cleaned_up_hex)
                return cleaned_up_vals

            try:
                input_as["Decimal"] = convert_str_to_int(val)
                # Make sure you don't get invalid bytes, EG: 0xF is not a valid
                # byte and should be represented as 0x0F
                input_as["Hexadecimal"] = hex(input_as["Decimal"])
                input_as["Binary"] = bin(input_as["Decimal"])


                # the negative messes with the hacky modulus fix, this area
                # could probably be improved
                cleaned_up_hex = clean_up_hex(input_as["Hexadecimal"])
                input_as["Hexadecimal"] = cleaned_up_hex[0]


                try:
                    input_as["Ascii Encoding"] = "\"" + \
                        bytes.fromhex(cleaned_up_hex[1]).decode(
                            "unicode_escape") + "\""
                except BaseException:
                    input_as["Ascii Encoding"] = "Invalid Ascii representation"
                # remove the detected input type and notate it with a color
                ref_val = val
                if ref_val[0] == "-":
                    ref_val = ref_val[1:]

                if ref_val[:2] == "0b":
                    if not return_all:
                        del input_as["Binary"]
                    embed.color = discord.Color.teal()
                elif ref_val[:2] == "0x":
                    if not return_all:
                        del input_as["Hexadecimal"]
                    embed.color = discord.Color.dark_teal()
                else:
                    if not return_all:
                        del input_as["Decimal"]
                    embed.color = discord.Color.green()

                # add all the values to the embed
                for key, i in input_as.items():
                    # ensure we're under discord embed length limits
                    if len(str(i)) > 1024 - 3:
                        i = str(i)[:(1024 - 3)] + "..."
                    embed.add_field(name=key + ":", value=i, inline=False)

            # catch all if something breaks
            except ValueError:
                embed = discord.Embed(color=discord.Color.red(
                ), title="Unable to convert value, are you sure it's valid?")

            return embed

        def perform_op_on_list(parsed_list) -> int:
            """
            Function that treats a list like an equation, so [1, "+", 1] would return two.\
             The list must have 3 items
            """

            first_val = convert_str_to_int(parsed_list[0])
            second_val = convert_str_to_int(parsed_list[2])
            if parsed_list[1] == "+":
                return first_val + second_val
            if parsed_list[1] == "-":
                return first_val - second_val
            if parsed_list[1] == "*":
                return first_val * second_val
            if parsed_list[1] == "/":
                return int(first_val / second_val)
            raise Exception("Invalid equation")

        # figure out whether or not the input is an equation
        is_equation = False
        for pos, i in enumerate(val_to_convert):
            if i in ["+", "*", "/"]:
                is_equation = True
            if i == "-" and pos > 0:
                is_equation = True
                # this accounts for inputs like "-0xff"
                # not very efficient, but see if there's any other operators
                # if it's not 0 than assumed equation

        if is_equation:
            # only accounting for one operation, so if there's not 3 arguments,
            # they messed up
            parsed_list = split_nicely(val_to_convert)
            try:
                calced_val = str(perform_op_on_list(parsed_list))
                await ctx.send(embed=gen_embed_from_val(calced_val, True))
            except ValueError:
                await ctx.send_deny_embed("Unable to perform calculation, are you sure that \
                equation is valid?")
        else:
            await ctx.send(embed=gen_embed_from_val(val_to_convert))
