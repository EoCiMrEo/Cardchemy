"""Networkless, provider-free, load-only admission for the public model bundle.

Run in a credential-free disposable container with --network none, four CPUs,
2 GiB memory and a read-only bundle mount. This script NEVER calls model.run().
It is not a quality score or permission to change an Ask runtime policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

REPOSITORY = 'mixedbread-ai/mxbai-rerank-xsmall-v1'
REVISION = 'd1ba0a474aeed7c9fa96c3f57b128277580c5fae'
MODEL = 'onnx/model_quantized.onnx'
MODEL_SHA256 = '15ef19a6de90be7d52b627f2c784107bd806e64826450f41fb75fa4f0179ab30'
REQUIRED = frozenset({MODEL, 'config.json', 'tokenizer.json', 'README.md', 'LICENSE'})
ALLOWED = REQUIRED | {'tokenizer_config.json', 'special_tokens_map.json'}
MAX_BYTES = 160 * 1024**2
MAX_STARTUP_SECONDS = 20.0
MAX_PAIR_TOKENS = 256


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _read_json(path: Path, max_bytes: int):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError('manifest_invalid')
    return json.loads(path.read_text(encoding='utf-8'))


def verify_bundle(root: Path):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('bundle_identity')
    manifest_path = root / 'manifest.json'
    manifest = _read_json(manifest_path, 32_768)
    files = manifest.get('files')
    if (manifest.get('schema') != 'reading_usefulness_bundle_v1'
            or manifest.get('repository') != REPOSITORY
            or manifest.get('revision') != REVISION
            or not isinstance(files, dict)
            or not REQUIRED <= set(files) <= ALLOWED):
        raise ValueError('manifest_identity')
    total = 0
    for name, pin in files.items():
        path = root / name
        if (any(part.is_symlink() for part in (path, *path.parents))
                or not isinstance(pin, dict)
                or type(pin.get('size')) is not int
                or pin['size'] <= 0
                or not path.is_file()
                or path.stat().st_size != pin['size']
                or digest(path) != pin.get('sha256')):
            raise ValueError('artifact_identity')
        total += pin['size']
    if total > MAX_BYTES or files[MODEL]['sha256'] != MODEL_SHA256:
        raise ValueError('bundle_budget')
    license_text = (root / 'LICENSE').read_text(encoding='utf-8')
    card_text = (root / 'README.md').read_text(encoding='utf-8')
    if ('Apache License' not in license_text or 'Version 2.0' not in license_text
            or 'apache-2.0' not in card_text.lower()):
        raise ValueError('license_identity')
    return {'files': len(files), 'bytes': total, 'manifest_sha256': digest(manifest_path)}


def peak_rss():
    for line in Path('/proc/self/status').read_text(encoding='utf-8').splitlines():
        if line.startswith('VmHWM:'):
            return int(line.split()[1]) * 1024
    raise ValueError('memory_measurement_unavailable')


def load_only(root: Path):
    started = perf_counter()
    bundle = verify_bundle(root)
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(root / 'tokenizer.json'))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    encoded = tokenizer.encode('What is the definition?',
                               'Definition: A term has a stated meaning.',
                               add_special_tokens=True)
    if not 0 < len(encoded.ids) <= MAX_PAIR_TOKENS:
        raise ValueError('pair_token_budget')
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 4
    session = ort.InferenceSession(str(root / MODEL), sess_options=options,
                                   providers=['CPUExecutionProvider'])
    input_names = {entry.name for entry in session.get_inputs()}
    if not {'input_ids', 'attention_mask'} <= input_names <= {
            'input_ids', 'attention_mask', 'token_type_ids'}:
        raise ValueError('model_inputs')
    output_names = [entry.name for entry in session.get_outputs()]
    if len(output_names) != 1:
        raise ValueError('model_outputs')
    elapsed = perf_counter() - started
    if not math.isfinite(elapsed) or elapsed > MAX_STARTUP_SECONDS:
        raise ValueError('startup_budget')
    return {**bundle, 'startup_ms': round(elapsed * 1000, 3),
            'peak_rss_bytes': peak_rss(), 'pair_tokens': len(encoded.ids),
            'input_names': sorted(input_names), 'output_count': len(output_names),
            'model_run_calls': 0, 'network_requests': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = {'status': 'load_only_ready', **load_only(args.bundle)}
    except (OSError, ValueError, ImportError):
        result = {'status': 'load_only_unavailable', 'model_run_calls': 0,
                  'network_requests': 0}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result['status'] == 'load_only_ready' else 1


if __name__ == '__main__':
    raise SystemExit(main())
