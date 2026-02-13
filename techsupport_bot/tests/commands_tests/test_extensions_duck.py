"""
This is a file to test the extensions/duck.py file
This contains helper function tests for duck.py
"""

from __future__ import annotations

import datetime
from typing import Self

from commands import duck


class Test_ComputeDurationValues:
    """Tests for compute_duration_values"""

    def test_compute_duration_values(self: Self) -> None:
        """Ensures second and exact durations are computed"""
        # Step 1 - Setup env
        duration = datetime.timedelta(seconds=12, microseconds=345678)

        # Step 2 - Call the function
        duration_seconds, duration_exact = duck.compute_duration_values(duration)

        # Step 3 - Assert that everything works
        assert duration_seconds == 12
        assert duration_exact == 12.345678


class Test_BuildWinnerFooter:
    """Tests for build_winner_footer"""

    def test_new_personal_and_global(self: Self) -> None:
        """Ensures footer text includes personal and global notices"""
        # Step 1 - Call the function
        footer_text, update_personal = duck.build_winner_footer(5.2, 7.1, 6.0)

        # Step 2 - Assert that everything works
        assert "New personal record" in footer_text
        assert "New global record" in footer_text
        assert update_personal

    def test_regular_time(self: Self) -> None:
        """Ensures non-record runs return exact-time footer"""
        # Step 1 - Call the function
        footer_text, update_personal = duck.build_winner_footer(8.0, 7.1, 6.0)

        # Step 2 - Assert that everything works
        assert footer_text == "Exact time: 8.0 seconds."
        assert not update_personal

    def test_first_record_from_sentinel(self: Self) -> None:
        """Ensures a -1 personal record sentinel is treated as no existing record"""
        # Step 1 - Call the function
        footer_text, update_personal = duck.build_winner_footer(8.0, -1.0, None)

        # Step 2 - Assert that everything works
        assert "New personal record" in footer_text
        assert update_personal


class Test_BuildStatsFooter:
    """Tests for build_stats_footer"""

    def test_with_global_record(self: Self) -> None:
        """Ensures global record holder text is included when applicable"""
        # Step 1 - Call the function
        footer_text = duck.build_stats_footer(2.5, 2.5)

        # Step 2 - Assert that everything works
        assert "Speed record: 2.5 seconds" in footer_text
        assert "You hold the current global record!" in footer_text

    def test_without_global_record(self: Self) -> None:
        """Ensures only speed text appears when global record differs"""
        # Step 1 - Call the function
        footer_text = duck.build_stats_footer(2.5, 1.0)

        # Step 2 - Assert that everything works
        assert footer_text == "Speed record: 2.5 seconds"


class Test_ChunkDuckUsers:
    """Tests for chunk_duck_users"""

    def test_chunk_duck_users(self: Self) -> None:
        """Ensures user records are split into pages by limit"""
        # Step 1 - Call the function
        chunks = duck.chunk_duck_users([1, 2, 3, 4, 5], items_per_page=3)

        # Step 2 - Assert that everything works
        assert chunks == [[1, 2, 3], [4, 5]]


class Test_BuildMessages:
    """Tests for standardized duck helper messages"""

    def test_build_not_participated_message(self: Self) -> None:
        """Ensures not-participated message is stable"""
        # Step 1 - Call the function
        message = duck.build_not_participated_message()

        # Step 2 - Assert that everything works
        assert message == "You have not participated in the duck hunt yet."

    def test_build_manipulation_disabled_message(self: Self) -> None:
        """Ensures manipulation-disabled message is stable"""
        # Step 1 - Call the function
        message = duck.build_manipulation_disabled_message()

        # Step 2 - Assert that everything works
        assert message == "This command is disabled in this server"

    def test_build_spawn_permission_denial(self: Self) -> None:
        """Ensures spawn deny message is stable"""
        # Step 1 - Call the function
        message = duck.build_spawn_permission_denial()

        # Step 2 - Assert that everything works
        assert message == "It looks like you don't have permissions to spawn a duck"


class Test_ValidationHelpers:
    """Tests for duck validation helper functions"""

    def test_validate_donation_target(self: Self) -> None:
        """Ensures bot and self donation restrictions are enforced"""
        # Step 1 - Call the function
        bot_target = duck.validate_donation_target(1, 2, True)
        self_target = duck.validate_donation_target(1, 1, False)
        valid_target = duck.validate_donation_target(1, 2, False)

        # Step 2 - Assert that everything works
        assert bot_target == "The only ducks I accept are plated with gold!"
        assert self_target == "You can't donate a duck to yourself"
        assert valid_target is None

    def test_validate_duck_inventory(self: Self) -> None:
        """Ensures inventory checks are action-specific"""
        # Step 1 - Call the function
        invalid_inventory = duck.validate_duck_inventory(0, "release")
        valid_inventory = duck.validate_duck_inventory(2, "release")

        # Step 2 - Assert that everything works
        assert invalid_inventory == "You have no ducks to release."
        assert valid_inventory is None

    def test_can_spawn_duck(self: Self) -> None:
        """Ensures spawn permission lookup supports int/string IDs"""
        # Step 1 - Call the function
        allowed = duck.can_spawn_duck(25, [25, "30"])
        denied = duck.can_spawn_duck(99, [25, "30"])

        # Step 2 - Assert that everything works
        assert allowed
        assert not denied

    def test_build_random_choice_weights(self: Self) -> None:
        """Ensures success/failure weights sum correctly"""
        # Step 1 - Call the function
        weights = duck.build_random_choice_weights(70)

        # Step 2 - Assert that everything works
        assert weights == (70, 30)
