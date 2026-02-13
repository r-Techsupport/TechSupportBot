"""
This is a file to test the extensions/hangman.py file
This contains tests for all extracted helper functions
"""

from __future__ import annotations

from typing import Self

import discord
from commands import hangman


class FakeOwner:
    """A simple fake owner object with a deterministic string output"""

    def __str__(self: Self) -> str:
        return "owner-user"


class Test_NormalizeSecretWord:
    """Tests for normalize_secret_word"""

    def test_normalize_secret_word(self: Self) -> None:
        """Ensures the start word is stripped and lowercased"""
        # Step 1 - Call the function
        output = hangman.normalize_secret_word("  HeLLo  ")

        # Step 2 - Assert that everything works
        assert output == "hello"


class Test_ValidateStartWordInput:
    """Tests for validate_start_word_input"""

    def test_empty_word(self: Self) -> None:
        """Ensures empty start words are rejected"""
        # Step 1 - Call the function
        output = hangman.validate_start_word_input("  ")

        # Step 2 - Assert that everything works
        assert output == "A word must be provided"

    def test_long_word(self: Self) -> None:
        """Ensures overlong start words are rejected"""
        # Step 1 - Call the function
        output = hangman.validate_start_word_input("a" * 85)

        # Step 2 - Assert that everything works
        assert output == "The word must be 84 characters or fewer"

    def test_non_alpha_word(self: Self) -> None:
        """Ensures non-alphabetical start words are rejected"""
        # Step 1 - Call the function
        output = hangman.validate_start_word_input("hello123")

        # Step 2 - Assert that everything works
        assert output == "The word can only contain letters"

    def test_valid_word(self: Self) -> None:
        """Ensures valid start words pass"""
        # Step 1 - Call the function
        output = hangman.validate_start_word_input("Banana")

        # Step 2 - Assert that everything works
        assert output is None


class Test_ValidateLetterGuessInput:
    """Tests for validate_letter_guess_input"""

    def test_multiple_characters(self: Self) -> None:
        """Ensures multi-character letters are rejected"""
        # Step 1 - Call the function
        output = hangman.validate_letter_guess_input("ab")

        # Step 2 - Assert that everything works
        assert output == "You can only guess a single letter"

    def test_non_alpha_character(self: Self) -> None:
        """Ensures non-alphabetical letters are rejected"""
        # Step 1 - Call the function
        output = hangman.validate_letter_guess_input("1")

        # Step 2 - Assert that everything works
        assert output == "You can only guess alphabetic letters"

    def test_valid_letter(self: Self) -> None:
        """Ensures single alphabetical letters pass"""
        # Step 1 - Call the function
        output = hangman.validate_letter_guess_input("a")

        # Step 2 - Assert that everything works
        assert output is None


class Test_ValidateSolveGuessInput:
    """Tests for validate_solve_guess_input"""

    def test_non_alpha_solve_guess(self: Self) -> None:
        """Ensures non-alphabetical solve guesses are rejected"""
        # Step 1 - Call the function
        output = hangman.validate_solve_guess_input("word123")

        # Step 2 - Assert that everything works
        assert output == "The guessed word can only contain letters"

    def test_valid_solve_guess(self: Self) -> None:
        """Ensures alphabetical solve guesses pass"""
        # Step 1 - Call the function
        output = hangman.validate_solve_guess_input("Word")

        # Step 2 - Assert that everything works
        assert output is None


class Test_GameControlHelpers:
    """Tests for game control helper functions"""

    def test_decide_start_conflict_owner(self: Self) -> None:
        """Ensures owners can choose to overwrite"""
        # Step 1 - Call the function
        output = hangman.decide_start_conflict(caller_id=1, owner_id=1)

        # Step 2 - Assert that everything works
        assert output == "confirm-overwrite"

    def test_decide_start_conflict_non_owner(self: Self) -> None:
        """Ensures non-owners are denied overwrite"""
        # Step 1 - Call the function
        output = hangman.decide_start_conflict(caller_id=1, owner_id=2)

        # Step 2 - Assert that everything works
        assert output == "deny"

    def test_evaluate_solve_attempt(self: Self) -> None:
        """Ensures solve attempts are case-insensitive"""
        # Step 1 - Call the function
        output = hangman.evaluate_solve_attempt("Banana", "banana")

        # Step 2 - Assert that everything works
        assert output

    def test_build_letter_guess_result(self: Self) -> None:
        """Ensures letter result text renders for misses"""
        # Step 1 - Call the function
        output = hangman.build_letter_guess_result("A", False)

        # Step 2 - Assert that everything works
        assert output == "Letter `a` not in word"

    def test_build_solve_result(self: Self) -> None:
        """Ensures solve result text renders for hits"""
        # Step 1 - Call the function
        output = hangman.build_solve_result(" APPLE ", True)

        # Step 2 - Assert that everything works
        assert output == "`apple` is correct"

    def test_build_add_guesses_result(self: Self) -> None:
        """Ensures add-guesses result text is formatted"""
        # Step 1 - Call the function
        output = hangman.build_add_guesses_result(2, 5)

        # Step 2 - Assert that everything works
        assert output == "2 guesses have been added! Total guesses remaining: 5"


class Test_StopPermission:
    """Tests for build_stop_permission_denial"""

    def test_owner_allowed(self: Self) -> None:
        """Ensures game owners can always stop their own game"""
        # Step 1 - Call the function
        output = hangman.build_stop_permission_denial(
            caller_id=1,
            owner_id=1,
            configured_role_names=[],
            caller_role_names=[],
        )

        # Step 2 - Assert that everything works
        assert output is None

    def test_no_configured_roles_denied(self: Self) -> None:
        """Ensures non-owners are denied when no admin roles are configured"""
        # Step 1 - Call the function
        output = hangman.build_stop_permission_denial(
            caller_id=2,
            owner_id=1,
            configured_role_names=[],
            caller_role_names=["Moderator"],
        )

        # Step 2 - Assert that everything works
        assert output == "No hangman admin roles are configured"

    def test_matching_role_allowed(self: Self) -> None:
        """Ensures configured role match grants stop permission"""
        # Step 1 - Call the function
        output = hangman.build_stop_permission_denial(
            caller_id=2,
            owner_id=1,
            configured_role_names=["Moderator"],
            caller_role_names=["moderator"],
        )

        # Step 2 - Assert that everything works
        assert output is None


class Test_BuildGameDisplayData:
    """Tests for build_game_display_data"""

    def test_running_game_payload(self: Self) -> None:
        """Ensures running games include guess and color details"""
        # Step 1 - Setup env
        game = hangman.HangmanGame("apple")
        game.guesses.add("a")

        # Step 2 - Call the function
        output = hangman.build_game_display_data(game, FakeOwner())

        # Step 3 - Assert that everything works
        assert output["color"] == discord.Color.gold()
        assert output["remaining_guesses"] == 6
        assert output["guessed_letters"] == "a"
        assert str(output["footer"]).startswith("Game started by")

    def test_failed_game_payload(self: Self) -> None:
        """Ensures failed games return fail coloring and footer"""
        # Step 1 - Setup env
        game = hangman.HangmanGame("apple")
        game.step = game.max_guesses

        # Step 2 - Call the function
        output = hangman.build_game_display_data(game, FakeOwner())

        # Step 3 - Assert that everything works
        assert output["color"] == discord.Color.red()
        assert output["footer"] == "Game over! The word was `apple`!"
