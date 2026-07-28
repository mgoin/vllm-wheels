from unittest import TestCase

from vllm_wheels.http import FetchError
from vllm_wheels.sources.vllm_index import WheelsIndexSource


class FakeClient:
    def __init__(self) -> None:
        self.text = {
            "https://wheels.vllm.ai/0.26.0/": (
                '<a href="cpu/">cpu</a>'
                '<a href="cu130/">cu130</a>'
                '<a href="vllm/">vllm</a>'
            ),
            "https://wheels.vllm.ai/rocm/0.26.0/": (
                '<a href="rocm723/">rocm723</a>'
            ),
        }
        default = {
            "package_name": "vllm",
            "version": "0.26.0",
            "build_tag": None,
            "python_tag": "cp38",
            "abi_tag": "abi3",
            "platform_tag": "manylinux_2_28_x86_64",
            "variant": None,
            "filename": "vllm-0.26.0-cp38-abi3-manylinux_2_28_x86_64.whl",
            "path": "../../abcabcabcabcabcabcabcabcabcabcabcabcabca/"
            "vllm-0.26.0-cp38-abi3-manylinux_2_28_x86_64.whl",
        }
        self.json = {
            "https://wheels.vllm.ai/0.26.0/vllm/metadata.json": [default],
            "https://wheels.vllm.ai/0.26.0/cu130/vllm/metadata.json": [default],
            "https://wheels.vllm.ai/0.26.0/cpu/vllm/metadata.json": [
                {
                    **default,
                    "python_tag": "cp312",
                    "abi_tag": "cp312",
                    "platform_tag": "macosx_11_0_arm64",
                    "variant": "cpu",
                    "filename": "vllm-0.26.0+cpu-cp312-cp312-macosx_11_0_arm64.whl",
                    "path": "../../../abcabcabcabcabcabcabcabcabcabcabcabcabca/"
                    "vllm-0.26.0%2Bcpu-cp312-cp312-macosx_11_0_arm64.whl",
                }
            ],
            "https://wheels.vllm.ai/rocm/0.26.0/rocm723/vllm/metadata.json": [
                {
                    **default,
                    "python_tag": "cp312",
                    "abi_tag": "cp312",
                    "platform_tag": "manylinux_2_34_x86_64",
                    "variant": "rocm723",
                    "filename": (
                        "vllm-0.26.0+rocm723-cp312-cp312-"
                        "manylinux_2_34_x86_64.whl"
                    ),
                    "path": "../../../abcabcabcabcabcabcabcabcabcabcabcabcabca/"
                    "vllm-0.26.0%2Brocm723-cp312-cp312-"
                    "manylinux_2_34_x86_64.whl",
                }
            ],
        }

    def get_text(self, url: str) -> str:
        if url not in self.text:
            raise FetchError(url, "not found", 404)
        return self.text[url]

    def get_json(self, url: str):
        if url not in self.json:
            raise FetchError(url, "not found", 404)
        return self.json[url]


class WheelsIndexSourceTests(TestCase):
    def setUp(self) -> None:
        self.source = WheelsIndexSource(FakeClient())  # type: ignore[arg-type]

    def test_discovers_default_and_variant_indexes(self) -> None:
        records, warnings = self.source.scrape_reference(
            "0.26.0",
            channel="release",
        )

        self.assertEqual(warnings, [])
        self.assertEqual(len(records), 3)
        self.assertEqual(
            {record.index_variant for record in records},
            {"default", "cpu", "cu130"},
        )
        cpu = next(record for record in records if record.index_variant == "cpu")
        self.assertEqual(cpu.architecture, "arm64")
        self.assertEqual(cpu.operating_system, "macOS")
        self.assertIn("%2Bcpu", cpu.download_url)
        self.assertIn("--torch-backend cpu", cpu.install_command)
        self.assertIn("--index-strategy first-index", cpu.install_command)

    def test_preserves_alias_index_variant(self) -> None:
        records, _ = self.source.scrape_reference("0.26.0", channel="release")
        alias = next(record for record in records if record.index_variant == "cu130")

        self.assertIsNone(alias.wheel_variant)
        self.assertEqual(alias.effective_variant, "cu130")
        self.assertEqual(alias.index_url, "https://wheels.vllm.ai/0.26.0/cu130")

    def test_discovers_rocm_family(self) -> None:
        records, warnings = self.source.scrape_reference(
            "0.26.0",
            channel="release",
            family="rocm",
        )

        self.assertEqual(warnings, [])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].index_family, "rocm")
        self.assertEqual(records[0].effective_variant, "rocm723")

