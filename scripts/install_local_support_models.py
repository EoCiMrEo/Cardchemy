"""Install Cardchemy's pinned local Ask support artifacts.

Downloads are restricted to immutable Hugging Face revisions and accepted only
after exact size and SHA-256 verification. Course content and credentials are
never read by this installer.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "runtime-data" / "local-support" / "v1"
POLICY_VERSION = "local_nli_qa_v1"
ARTIFACTS = (
    {
        "relative_path": "nli/model.onnx",
        "url": "https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall/resolve/a150876415327c80daeff35ca6f68f5ed8cf5c24/onnx/model_quint8_avx2.onnx?download=true",
        "size": 87_377_068,
        "sha256": "21b14751a95520953bfcc607ceeb617de7cbeaeb6d60f4c8966716c743985337",
    },
    {
        "relative_path": "nli/tokenizer.json",
        "url": "https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall/resolve/a150876415327c80daeff35ca6f68f5ed8cf5c24/tokenizer.json?download=true",
        "size": 8_656_624,
        "sha256": "5124ef2ead1a10a717703bc436de7f353da76d6340e4587719b42b1693707964",
    },
    {
        "relative_path": "qa/model.onnx",
        "url": "https://huggingface.co/onnx-community/tinyroberta-squad2-ONNX/resolve/7c9f69b7e6228375169a4553bcfa6639152e3a69/onnx/model_int8.onnx?download=true",
        "size": 82_141_214,
        "sha256": "4db70e7a019e32bf652fb9d30a5c24d18b6949fae2f1dd00d9fe6d43052b77cd",
    },
    {
        "relative_path": "qa/tokenizer.json",
        "url": "https://huggingface.co/onnx-community/tinyroberta-squad2-ONNX/resolve/7c9f69b7e6228375169a4553bcfa6639152e3a69/tokenizer.json?download=true",
        "size": 3_558_647,
        "sha256": "7b62d797c95d1563d3467f48daad0eca3e150f2d587e7e687b557c9ef1b25473",
    },
)


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def _matches(path: Path, item: dict[str, object]) -> bool:
    return (
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == item["size"]
        and _digest(path) == item["sha256"]
    )


def _download(item: dict[str, object], destination: Path) -> None:
    request = Request(str(item["url"]), headers={"User-Agent": "Cardchemy-local-support-installer/1"})
    digest = sha256()
    size = 0
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:  # noqa: S310 - pinned HTTPS URLs
        if response.geturl().split(":", 1)[0].lower() != "https":
            raise RuntimeError("Artifact download did not remain on HTTPS")
        while block := response.read(1024 * 1024):
            size += len(block)
            if size > int(item["size"]):
                raise RuntimeError(f"Artifact exceeded its pinned size: {item['relative_path']}")
            digest.update(block)
            output.write(block)
    if size != item["size"] or digest.hexdigest() != item["sha256"]:
        raise RuntimeError(f"Artifact verification failed: {item['relative_path']}")


def install(target: Path) -> None:
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and all(_matches(target / str(item["relative_path"]), item) for item in ARTIFACTS):
        print(f"Verified existing local support bundle at {target}")
        return
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f"Refusing to overwrite non-matching local support bundle: {target}")

    with tempfile.TemporaryDirectory(prefix="cardchemy-local-support-", dir=target.parent) as temporary:
        staging = Path(temporary) / "bundle"
        for item in ARTIFACTS:
            destination = staging / str(item["relative_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            _download(item, destination)
        manifest = {
            "policy_version": POLICY_VERSION,
            "models": [
                {
                    "id": "cross-encoder/nli-deberta-v3-xsmall",
                    "revision": "a150876415327c80daeff35ca6f68f5ed8cf5c24",
                    "license": "Apache-2.0",
                },
                {
                    "id": "onnx-community/tinyroberta-squad2-ONNX",
                    "revision": "7c9f69b7e6228375169a4553bcfa6639152e3a69",
                    "license": "CC-BY-4.0",
                },
            ],
            "artifacts": [
                {key: item[key] for key in ("relative_path", "size", "sha256")}
                for item in ARTIFACTS
            ],
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if target.exists():
            target.rmdir()
        # Copy into a newly created destination so Windows inherits the parent
        # directory ACL. Moving TemporaryDirectory's owner-only directory would
        # make the normal worker account unable to read the artifacts.
        shutil.copytree(staging, target)
    print(f"Installed and verified local support bundle at {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    install(args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
