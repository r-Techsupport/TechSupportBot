"""
This is a file to test the extensions/translate.py file
This contains tests for helper functions in translate.py
"""

from __future__ import annotations

from typing import Self

from commands import translate


class Test_NormalizeTranslationInput:
    """Tests for normalize_translation_input"""

    def test_normalization(self: Self) -> None:
        """Ensures message whitespace is trimmed and language codes are lowercased"""
        # Step 1 - Call the function
        normalized_message, normalized_src, normalized_dest = (
            translate.normalize_translation_input("  Hello world  ", " EN ", " ES ")
        )

        # Step 2 - Assert that everything works
        assert normalized_message == "Hello world"
        assert normalized_src == "en"
        assert normalized_dest == "es"


class Test_ValidateTranslationInputs:
    """Tests for validate_translation_inputs"""

    def test_missing_message(self: Self) -> None:
        """Ensures missing message input is rejected"""
        # Step 1 - Call the function
        error_message = translate.validate_translation_inputs("", "en", "es")

        # Step 2 - Assert that everything works
        assert error_message == "You need to provide a message to translate"

    def test_missing_source(self: Self) -> None:
        """Ensures missing source code is rejected"""
        # Step 1 - Call the function
        error_message = translate.validate_translation_inputs("hello", "", "es")

        # Step 2 - Assert that everything works
        assert error_message == "You need to provide a source language code"

    def test_missing_dest(self: Self) -> None:
        """Ensures missing destination code is rejected"""
        # Step 1 - Call the function
        error_message = translate.validate_translation_inputs("hello", "en", "")

        # Step 2 - Assert that everything works
        assert error_message == "You need to provide a destination language code"

    def test_valid_inputs(self: Self) -> None:
        """Ensures valid translation values pass validation"""
        # Step 1 - Call the function
        error_message = translate.validate_translation_inputs("hello", "en", "es")

        # Step 2 - Assert that everything works
        assert error_message is None


class Test_BuildTranslateUrl:
    """Tests for build_translate_url"""

    def test_build_translate_url(self: Self) -> None:
        """Ensures URL template is formatted correctly"""
        # Step 1 - Call the function
        url = translate.build_translate_url(
            "https://example.com?q={}&langpair={}|{}", "hello", "en", "es"
        )

        # Step 2 - Assert that everything works
        assert url == "https://example.com?q=hello&langpair=en|es"


class Test_ExtractTranslatedText:
    """Tests for extract_translated_text"""

    def test_valid_translated_text(self: Self) -> None:
        """Ensures translated text is returned when response shape is valid"""
        # Step 1 - Setup env
        response = {"responseData": {"translatedText": "hola"}}

        # Step 2 - Call the function
        translated = translate.extract_translated_text(response)

        # Step 3 - Assert that everything works
        assert translated == "hola"

    def test_invalid_translated_text(self: Self) -> None:
        """Ensures None is returned for malformed responses"""
        # Step 1 - Setup env
        response = {"responseData": {}}

        # Step 2 - Call the function
        translated = translate.extract_translated_text(response)

        # Step 3 - Assert that everything works
        assert translated is None


class Test_BuildTranslationFailureMessage:
    """Tests for build_translation_failure_message"""

    def test_build_translation_failure_message(self: Self) -> None:
        """Ensures translation failure text is consistent"""
        # Step 1 - Call the function
        message = translate.build_translation_failure_message()

        # Step 2 - Assert that everything works
        assert message == "I could not translate your message"
