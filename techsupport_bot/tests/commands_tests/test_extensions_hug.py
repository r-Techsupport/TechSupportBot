"""
This is a file to test the extensions/hug.py file
This contains helper function tests for hug.py
"""

from __future__ import annotations

from typing import Self
from unittest.mock import patch

from commands import hug


class Test_IsValidHugTarget:
    """Tests for is_valid_hug_target"""

    def test_valid_target(self: Self) -> None:
        """Ensures different author and target IDs are valid"""
        # Step 1 - Call the function
        result = hug.is_valid_hug_target(1, 2)

        # Step 2 - Assert that everything works
        assert result

    def test_invalid_target(self: Self) -> None:
        """Ensures identical author and target IDs are invalid"""
        # Step 1 - Call the function
        result = hug.is_valid_hug_target(1, 1)

        # Step 2 - Assert that everything works
        assert not result


class Test_NormalizeHugTemplates:
    """Tests for normalize_hug_templates"""

    def test_normalize_hug_templates(self: Self) -> None:
        """Ensures blank templates are removed and values are trimmed"""
        # Step 1 - Call the function
        normalized = hug.normalize_hug_templates(
            ["  one  ", "", "two", "   ", "three  "]
        )

        # Step 2 - Assert that everything works
        assert normalized == ["one", "two", "three"]


class Test_PickHugTemplate:
    """Tests for pick_hug_template"""

    def test_pick_hug_template(self: Self) -> None:
        """Ensures a template can be selected from a non-empty list"""
        # Step 1 - Call the function
        with patch("commands.hug.random.choice", return_value="selected"):
            selected = hug.pick_hug_template(["one", "two"])

        # Step 2 - Assert that everything works
        assert selected == "selected"

    def test_pick_hug_template_empty(self: Self) -> None:
        """Ensures empty template lists return no selected template"""
        # Step 1 - Call the function
        selected = hug.pick_hug_template([])

        # Step 2 - Assert that everything works
        assert selected is None


class Test_BuildHugPhrase:
    """Tests for build_hug_phrase"""

    def test_build_hug_phrase(self: Self) -> None:
        """Ensures hug phrase placeholders are formatted correctly"""
        # Step 1 - Call the function
        phrase = hug.build_hug_phrase(
            "{user_giving_hug} hugs {user_to_hug}",
            "<@1>",
            "<@2>",
        )

        # Step 2 - Assert that everything works
        assert phrase == "<@1> hugs <@2>"


class Test_BuildHugFailureMessage:
    """Tests for build_hug_failure_message"""

    def test_build_hug_failure_message(self: Self) -> None:
        """Ensures failure message text is stable"""
        # Step 1 - Call the function
        message = hug.build_hug_failure_message()

        # Step 2 - Assert that everything works
        assert message == "Let's be serious"


class Test_BuildHugEmbedData:
    """Tests for build_hug_embed_data"""

    def test_build_hug_embed_data(self: Self) -> None:
        """Ensures embed title/description payload is formed correctly"""
        # Step 1 - Call the function
        payload = hug.build_hug_embed_data("hug text")

        # Step 2 - Assert that everything works
        assert payload == {"title": "You've been hugged!", "description": "hug text"}
