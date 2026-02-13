"""
This is a file to test the extensions/burn.py file
This contains tests for all extracted helper functions
"""

from __future__ import annotations

from typing import Self
from unittest.mock import patch

import pytest
from commands import burn


class Test_BuildBurnReactions:
    """Tests for build_burn_reactions"""

    def test_reaction_list(self: Self) -> None:
        """Ensures reaction list is in the expected order"""
        # Step 1 - Call the function
        reactions = burn.build_burn_reactions()

        # Step 2 - Assert that everything works
        assert reactions == ["🔥", "🚒", "👨‍🚒"]


class Test_NormalizePhrasePool:
    """Tests for normalize_phrase_pool"""

    def test_normalize_phrase_pool(self: Self) -> None:
        """Ensures phrase pool is trimmed, deduplicated, and cleaned"""
        # Step 1 - Call the function
        normalized = burn.normalize_phrase_pool(
            ["  test phrase  ", "", "test phrase", "another phrase", "   "]
        )

        # Step 2 - Assert that everything works
        assert normalized == ["test phrase", "another phrase"]


class Test_ValidatePhrasePool:
    """Tests for validate_phrase_pool"""

    def test_empty_phrase_pool(self: Self) -> None:
        """Ensures empty phrase pools are rejected"""
        # Step 1 - Call the function
        error_message = burn.validate_phrase_pool([])

        # Step 2 - Assert that everything works
        assert error_message == "There are no burn phrases configured"

    def test_populated_phrase_pool(self: Self) -> None:
        """Ensures non-empty phrase pools pass validation"""
        # Step 1 - Call the function
        error_message = burn.validate_phrase_pool(["value"])

        # Step 2 - Assert that everything works
        assert error_message is None


class Test_ChoosePhraseIndex:
    """Tests for choose_phrase_index"""

    def test_choose_phrase_index(self: Self) -> None:
        """Ensures a selected index is returned from the phrase chooser"""
        # Step 1 - Call the function
        with patch("commands.burn.random.randint", return_value=1):
            index = burn.choose_phrase_index(["a", "b", "c"])

        # Step 2 - Assert that everything works
        assert index == 1

    def test_choose_phrase_index_empty(self: Self) -> None:
        """Ensures a ValueError is raised with no phrase values"""
        # Step 1 / 2 - Assert that everything works
        with pytest.raises(ValueError):
            burn.choose_phrase_index([])


class Test_BuildBurnDescription:
    """Tests for build_burn_description"""

    def test_build_burn_description(self: Self) -> None:
        """Ensures phrase wrapper formatting is correct"""
        # Step 1 - Call the function
        description = burn.build_burn_description(
            ["Sick BURN!", "BURN ALERT!"], chosen_index=1
        )

        # Step 2 - Assert that everything works
        assert description == "🔥🔥🔥 BURN ALERT! 🔥🔥🔥"


class Test_BuildBurnNotFoundMessage:
    """Tests for build_burn_not_found_message"""

    def test_build_burn_not_found_message(self: Self) -> None:
        """Ensures not-found message content matches expectation"""
        # Step 1 - Call the function
        output = burn.build_burn_not_found_message()

        # Step 2 - Assert that everything works
        assert output == "I could not find a message to reply to"


class Test_ResolveBurnTargetForContextMenu:
    """Tests for resolve_burn_target_for_context_menu"""

    def test_resolve_author(self: Self) -> None:
        """Ensures valid message author IDs are selected"""
        # Step 1 - Call the function
        target = burn.resolve_burn_target_for_context_menu(10, 20)

        # Step 2 - Assert that everything works
        assert target == 10

    def test_resolve_invoker_on_invalid_author(self: Self) -> None:
        """Ensures invalid message author IDs use the invoker as fallback"""
        # Step 1 - Call the function
        target = burn.resolve_burn_target_for_context_menu(0, 20)

        # Step 2 - Assert that everything works
        assert target == 20
