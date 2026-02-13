"""
This is a file to test the extensions/google.py file
This contains tests for helper functions in google.py
"""

from __future__ import annotations

from typing import Self

import munch
from commands import google


class Test_BuildParamHelpers:
    """Tests for parameter builder helpers"""

    def test_build_google_search_params(self: Self) -> None:
        """Ensures Google search params are generated correctly"""
        # Step 1 - Call the function
        params = google.build_google_search_params("CSE", "KEY", "query")

        # Step 2 - Assert that everything works
        assert params == {"cx": "CSE", "q": "query", "key": "KEY"}

    def test_build_google_image_params(self: Self) -> None:
        """Ensures Google image params include image search type"""
        # Step 1 - Call the function
        params = google.build_google_image_params("CSE", "KEY", "query")

        # Step 2 - Assert that everything works
        assert params == {
            "cx": "CSE",
            "q": "query",
            "key": "KEY",
            "searchType": "image",
        }

    def test_build_youtube_params(self: Self) -> None:
        """Ensures YouTube params are generated correctly"""
        # Step 1 - Call the function
        params = google.build_youtube_params("KEY", "query")

        # Step 2 - Assert that everything works
        assert params == {"q": "query", "key": "KEY", "type": "video"}


class Test_ExtractionHelpers:
    """Tests for response extraction helpers"""

    def test_extract_google_search_fields(self: Self) -> None:
        """Ensures links/snippets are extracted and cleaned"""
        # Step 1 - Setup env
        items = [
            munch.munchify(
                {"link": "https://example.com/1", "snippet": "line1\nline2"}
            ),
            munch.munchify({"link": "https://example.com/2"}),
            munch.munchify({"snippet": "missing link"}),
        ]

        # Step 2 - Call the function
        fields = google.extract_google_search_fields(items, "query")

        # Step 3 - Assert that everything works
        assert fields == [
            ("https://example.com/1", "line1line2"),
            ("https://example.com/2", "No details available for query"),
        ]

    def test_extract_image_links(self: Self) -> None:
        """Ensures malformed image results are skipped"""
        # Step 1 - Setup env
        items = [
            munch.munchify({"link": "https://img.example.com/1.jpg"}),
            munch.munchify({}),
            munch.munchify({"link": "https://img.example.com/2.jpg"}),
        ]

        # Step 2 - Call the function
        links = google.extract_image_links(items)

        # Step 3 - Assert that everything works
        assert links == [
            "https://img.example.com/1.jpg",
            "https://img.example.com/2.jpg",
        ]

    def test_extract_youtube_links(self: Self) -> None:
        """Ensures malformed youtube results are skipped"""
        # Step 1 - Setup env
        items = [
            munch.munchify({"id": {"videoId": "abc"}}),
            munch.munchify({"id": {}}),
            munch.munchify({"id": {"videoId": "xyz"}}),
        ]

        # Step 2 - Call the function
        links = google.extract_youtube_links(items)

        # Step 3 - Assert that everything works
        assert links == ["http://youtu.be/abc", "http://youtu.be/xyz"]


class Test_ChunkSearchFields:
    """Tests for chunk_search_fields"""

    def test_chunk_search_fields(self: Self) -> None:
        """Ensures fields are chunked by max size"""
        # Step 1 - Setup env
        fields = [("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")]

        # Step 2 - Call the function
        chunks = google.chunk_search_fields(fields, 2)

        # Step 3 - Assert that everything works
        assert chunks == [[("a", "1"), ("b", "2")], [("c", "3"), ("d", "4")]]

    def test_chunk_search_fields_minimum_size(self: Self) -> None:
        """Ensures non-positive max size is normalized to one item per chunk"""
        # Step 1 - Setup env
        fields = [("a", "1"), ("b", "2")]

        # Step 2 - Call the function
        chunks = google.chunk_search_fields(fields, 0)

        # Step 3 - Assert that everything works
        assert chunks == [[("a", "1")], [("b", "2")]]


class Test_MessageHelpers:
    """Tests for no-results and parse error message builders"""

    def test_build_no_results_message(self: Self) -> None:
        """Ensures search-kind-specific no-result messages are returned"""
        # Step 1 - Call the function
        default_message = google.build_no_results_message("search", "abc")
        image_message = google.build_no_results_message("image", "abc")
        video_message = google.build_no_results_message("video", "abc")

        # Step 2 - Assert that everything works
        assert default_message == "No search results found for: *abc*"
        assert image_message == "No image search results found for: *abc*"
        assert video_message == "No video results found for: *abc*"

    def test_build_google_parse_error_message(self: Self) -> None:
        """Ensures parse error message text is stable"""
        # Step 1 - Call the function
        message = google.build_google_parse_error_message()

        # Step 2 - Assert that everything works
        assert (
            message == "I had an issue processing Google's response... try again later!"
        )
