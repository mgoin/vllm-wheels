import json
import tempfile
from pathlib import Path
from unittest import TestCase

from vllm_wheels.models import WheelRecord
from vllm_wheels.output import write_outputs


def sample_record() -> WheelRecord:
    return WheelRecord(
        source="wheels.vllm.ai",
        channel="release",
        filename="vllm-0.26.0-cp38-abi3-manylinux_2_28_x86_64.whl",
        version="0.26.0",
        release="0.26.0",
        python_tag="cp38",
        abi_tag="abi3",
        platform_tag="manylinux_2_28_x86_64",
        architecture="x86_64",
        operating_system="Linux",
        index_family="main",
        index_variant="default",
        index_url="https://wheels.vllm.ai/0.26.0",
        download_url="https://wheels.vllm.ai/abc/vllm.whl",
        source_url="https://wheels.vllm.ai/0.26.0",
    )


class OutputTests(TestCase):
    def test_writes_normalized_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            stats = write_outputs(output_dir, [sample_record()], [])
            dataset = json.loads((output_dir / "wheels.json").read_text())

            self.assertEqual(stats["latest_release"], "0.26.0")
            self.assertEqual(dataset["schema_version"], 2)
            self.assertEqual(dataset["wheels"][0]["effective_variant"], "default")
            self.assertIn("vllm==0.26.0", dataset["wheels"][0]["install_command"])
            self.assertTrue((output_dir / "wheels.csv").exists())
            self.assertTrue((output_dir / "stats.json").exists())
            self.assertTrue((output_dir / "schema.json").exists())
