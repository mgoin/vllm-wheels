from unittest import TestCase

from vllm_wheels.versions import sort_versions


class VersionSortingTests(TestCase):
    def test_versions_are_sorted_with_pep_440_semantics(self) -> None:
        versions = [
            "0.9.2",
            "0.26.0",
            "0.10.0",
            "0.26.0rc1",
            "0.9.0.1",
        ]

        self.assertEqual(
            sort_versions(versions),
            ["0.26.0", "0.26.0rc1", "0.10.0", "0.9.2", "0.9.0.1"],
        )

