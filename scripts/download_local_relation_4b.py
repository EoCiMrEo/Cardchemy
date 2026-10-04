"""Bounded public-only download for the one explicitly approved CPU experiment.

Read literal public pins without importing application settings. Never retries automatically,
overwrites existing files, prints redirect URLs or loads a model.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import stat
from pathlib import Path
from time import monotonic, sleep
import threading
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'artifacts' / 'local-relation-4b-experiment-20260926'
MAX_BYTES = 3 * 1024**3
MAX_SECONDS = 1800.0
MAX_RESUME_SECONDS = 7200.0
SEGMENT_BYTES = 64 * 1024**2
MAX_SEGMENT_REQUESTS = 10
MAX_SEGMENT_SECONDS = 900.0
MAX_SEGMENTED_SECONDS = 7200.0
# The third mode is deliberately bound to the public, stopped state reviewed
# after the first two one-shot continuations. It cannot silently start over.
SEGMENTED_DATA_OFFSET = 2_636_841_394
SEGMENTED_TRANSFER_BYTES = 260_032_571
SEGMENTED_MARKER = '.segmented-continuation-used'
MAX_SMALL_FILES_SECONDS = 1800.0
MAX_SMALL_FILE_SECONDS = 600.0
MAX_SMALL_FILE_BYTES = 16 * 1024**2
MAX_SMALL_FILE_REQUESTS = 6
SMALL_FILES_TRANSFER_BYTES = 11_439_085
SMALL_FILES_MARKER = '.six-small-files-used'
LOCAL_FINALIZE_ATTEMPTS = 3
LOCAL_FINALIZE_DELAY_SECONDS = 0.25
README_NAME = 'README.md'
README_BYTES = 519
README_MARKER = '.readme-only-used'
CORRECTED_README_MARKER = '.corrected-readme-used'
MAX_README_SECONDS = 600.0
MAX_README_CALL_SECONDS = 120.0
FROZEN_BUNDLE_BYTES = 2_897_393_599
EXPORT_FILES = frozenset({
    'model.onnx', 'model.onnx.data', 'tokenizer.json', 'config.json',
    'genai_config.json', 'tokenizer_config.json', 'chat_template.jinja',
})
PUBLIC_FILES = EXPORT_FILES | {README_NAME}


def manifest():
    tree = ast.parse((ROOT / 'scripts' / 'local_relation_4b_candidate.py').read_text(encoding='utf-8'))
    wanted = {'PINS', 'REPOSITORY', 'REVISION', 'REPOSITORY_DIRECTORY'}
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    values[target.id] = ast.literal_eval(node.value)
    if (set(values) != wanted or values['REPOSITORY'] != 'onnx-community/Qwen3-4B-ONNX'
        or values['REVISION'] != '98ddba15d05dede4435afb63f13280abcdbc2a48'
        or values['REPOSITORY_DIRECTORY'] != 'onnxruntime/cpu_and_mobile/cpu-int4-kld-block-128'
        or set(values['PINS']) != PUBLIC_FILES
        or sum(size for size, _digest in values['PINS'].values()) > MAX_BYTES):
        raise ValueError('download_manifest_invalid')
    return values


def public_artifact_url(values, name):
    if name not in PUBLIC_FILES or name not in values['PINS']:
        raise ValueError('download_manifest_invalid')
    relative_path = (name if name == README_NAME
                     else f"{values['REPOSITORY_DIRECTORY']}/{name}")
    return (f"https://huggingface.co/{values['REPOSITORY']}/resolve/{values['REVISION']}/"
            f"{relative_path}")


def check_destination():
    absolute = DESTINATION.absolute()
    if (absolute.parent != (ROOT / 'artifacts').absolute()
        or any(path.is_symlink() for path in (absolute, *absolute.parents))):
        raise ValueError('download_destination_invalid')
    absolute.mkdir(parents=True, exist_ok=True)
    return absolute


def verify_file(path, size, digest):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() == digest


def _segmented_preflight(values, destination):
    pins = values['PINS']
    if 'model.onnx' not in pins or 'model.onnx.data' not in pins:
        raise ValueError('download_manifest_invalid')
    expected = {'.range-continuation-used', '.range-continuation-2-used',
                'model.onnx', 'model.onnx.data.part'}
    if {entry.name for entry in destination.iterdir()} != expected:
        raise ValueError('download_segmented_state_changed')
    for marker_name in ('.range-continuation-used', '.range-continuation-2-used'):
        marker = destination / marker_name
        if marker.is_symlink() or not marker.is_file():
            raise ValueError('download_prior_continuation_missing')
    graph_size, graph_digest = pins['model.onnx']
    if not verify_file(destination / 'model.onnx', graph_size, graph_digest):
        raise ValueError('download_existing_mismatch')
    partial = destination / 'model.onnx.data.part'
    if partial.is_symlink() or not partial.is_file():
        raise ValueError('download_partial_invalid')
    saved_stat = partial.stat()
    if (not stat.S_ISREG(saved_stat.st_mode) or saved_stat.st_nlink != 1
        or saved_stat.st_size != SEGMENTED_DATA_OFFSET):
        raise ValueError('download_segmented_state_changed')
    transfer_bytes = sum(size for name, (size, _digest) in pins.items()
                         if name != 'model.onnx') - SEGMENTED_DATA_OFFSET
    requests = sum((size - (SEGMENTED_DATA_OFFSET if name == 'model.onnx.data' else 0)
                    + SEGMENT_BYTES - 1) // SEGMENT_BYTES
                   for name, (size, _digest) in pins.items() if name != 'model.onnx')
    if (transfer_bytes != SEGMENTED_TRANSFER_BYTES or requests > MAX_SEGMENT_REQUESTS
        or sum(size for size, _digest in pins.values()) > MAX_BYTES):
        raise ValueError('download_segmented_budget_invalid')
    return graph_size, (saved_stat.st_dev, saved_stat.st_ino)


def _download_segmented(values, destination):
    started, requests, transferred, verified = monotonic(), 0, 0, 0
    stage = 'preflight'
    try:
        verified, data_identity = _segmented_preflight(values, destination)
        with (destination / SEGMENTED_MARKER).open('x', encoding='ascii') as marker:
            marker.write('one separately approved bounded public segmented continuation\n')
        for name, (size, digest) in values['PINS'].items():
            if name == 'model.onnx':
                continue
            if Path(name).name != name or name in {'.', '..'}:
                raise ValueError('download_manifest_invalid')
            path = destination / name
            partial = destination / (name + '.part')
            offset = SEGMENTED_DATA_OFFSET if name == 'model.onnx.data' else 0
            identity = data_identity if offset else None
            hasher = hashlib.sha256()
            if offset:
                stage = 'disk_read'
                with partial.open('rb') as saved:
                    current = os.fstat(saved.fileno())
                    if ((current.st_dev, current.st_ino) != identity
                        or current.st_nlink != 1 or not stat.S_ISREG(current.st_mode)
                        or current.st_size != offset):
                        raise ValueError('download_partial_changed')
                    remaining_prefix = offset
                    while remaining_prefix:
                        block = saved.read(min(1024 * 1024, remaining_prefix))
                        if not block:
                            raise ValueError('download_partial_changed')
                        hasher.update(block)
                        remaining_prefix -= len(block)
                        if monotonic() - started > MAX_SEGMENTED_SECONDS:
                            stage = 'budget'
                            raise ValueError('download_time_budget')
                    if saved.read(1):
                        raise ValueError('download_partial_changed')
            while offset < size:
                stage = 'budget'
                remaining_total = MAX_SEGMENTED_SECONDS - (monotonic() - started)
                if remaining_total <= 0 or requests >= MAX_SEGMENT_REQUESTS:
                    raise ValueError('download_budget_exceeded')
                end = min(size - 1, offset + SEGMENT_BYTES - 1)
                expected_length = end - offset + 1
                url = public_artifact_url(values, name)
                request = Request(url, headers={
                    'User-Agent': 'Cardchemy-approved-public-artifact/1',
                    'Accept-Encoding': 'identity', 'Range': f'bytes={offset}-{end}',
                })
                request_started = monotonic()
                stage = 'transport_open'
                requests += 1
                def abort_segment():
                    print(json.dumps({'status': 'download_unavailable', 'failure_stage': 'budget',
                                      'verified_bytes': verified, 'transferred_bytes': transferred,
                                      'artifact_requests': requests, 'model_loaded': False,
                                      'provider_requests': 0}, separators=(',', ':')), flush=True)
                    os._exit(1)
                segment_watchdog = threading.Timer(MAX_SEGMENT_SECONDS, abort_segment)
                segment_watchdog.daemon = True
                segment_watchdog.start()
                try:
                    with urlopen(request, timeout=min(60.0, remaining_total, MAX_SEGMENT_SECONDS)) as response:
                        if monotonic() - request_started > MAX_SEGMENT_SECONDS:
                            stage = 'budget'
                            raise ValueError('download_segment_time_budget')
                        stage = 'response_contract'
                        encoding = response.headers.get('Content-Encoding', 'identity')
                        if (response.status != 206 or encoding.strip().lower() != 'identity'
                            or response.headers.get('Content-Range') != f'bytes {offset}-{end}/{size}'
                            or response.headers.get('Content-Length') != str(expected_length)):
                            raise ValueError('download_segment_response_invalid')
                        stage = 'disk_write'
                        with partial.open('ab' if offset else 'xb') as output:
                            current = os.fstat(output.fileno())
                            if (partial.is_symlink() or not stat.S_ISREG(current.st_mode)
                                or current.st_nlink != 1 or output.tell() != offset
                                or (identity is not None and
                                    (current.st_dev, current.st_ino) != identity)):
                                raise ValueError('download_partial_changed')
                            identity = (current.st_dev, current.st_ino)
                            segment_bytes = 0
                            read = getattr(response, 'read1', response.read)
                            while True:
                                stage = 'transport_read'
                                block = read(64 * 1024)
                                if (monotonic() - started > MAX_SEGMENTED_SECONDS
                                    or monotonic() - request_started > MAX_SEGMENT_SECONDS):
                                    stage = 'budget'
                                    raise ValueError('download_segment_time_budget')
                                if not block:
                                    break
                                stage = 'response_length'
                                if len(block) > expected_length - segment_bytes:
                                    raise ValueError('download_segment_overflow')
                                stage = 'disk_write'
                                if output.write(block) != len(block):
                                    raise ValueError('download_short_write')
                                hasher.update(block)
                                segment_bytes += len(block)
                                transferred += len(block)
                                if (transferred > SEGMENTED_TRANSFER_BYTES
                                    or verified + offset + segment_bytes > MAX_BYTES
                                    or monotonic() - started > MAX_SEGMENTED_SECONDS
                                    or monotonic() - request_started > MAX_SEGMENT_SECONDS):
                                    stage = 'budget'
                                    raise ValueError('download_budget_exceeded')
                            stage = 'response_length'
                            if segment_bytes != expected_length:
                                raise ValueError('download_segment_short')
                finally:
                    segment_watchdog.cancel()
                offset = end + 1
            stage = 'digest'
            if hasher.hexdigest() != digest or not verify_file(partial, size, digest):
                raise ValueError('download_digest_invalid')
            stage = 'finalize'
            if path.exists() or path.is_symlink():
                raise ValueError('download_destination_race')
            partial.rename(path)
            verified += size
            print(json.dumps({'progress': 'public_file_verified', 'file': name,
                              'bytes': size}, separators=(',', ':')), flush=True)
        stage = 'bundle_digest'
        if (transferred != SEGMENTED_TRANSFER_BYTES
            or verified != sum(size for size, _digest in values['PINS'].values())):
            raise ValueError('download_bundle_incomplete')
        for name, (size, digest) in values['PINS'].items():
            if monotonic() - started > MAX_SEGMENTED_SECONDS:
                stage = 'budget'
                raise ValueError('download_time_budget')
            if not verify_file(destination / name, size, digest):
                raise ValueError('download_bundle_digest_invalid')
        return {'status': 'download_completed', 'bundle_bytes': verified,
                'artifact_requests': requests, 'transferred_bytes': transferred,
                'elapsed_ms': round((monotonic() - started) * 1000, 2),
                'model_loaded': False, 'provider_requests': 0}
    except Exception:
        # A fixed stage helps diagnose an interrupted public transfer without
        # exposing signed redirects, exception bodies, or private content.
        return {'status': 'download_unavailable', 'failure_stage': stage,
                'verified_bytes': verified, 'transferred_bytes': transferred,
                'artifact_requests': requests, 'model_loaded': False, 'provider_requests': 0}


def _small_files_preflight(values, destination):
    pins = values['PINS']
    expected = {'.range-continuation-used', '.range-continuation-2-used',
                SEGMENTED_MARKER, 'model.onnx', 'model.onnx.data'}
    if {entry.name for entry in destination.iterdir()} != expected:
        raise ValueError('download_small_files_state_changed')
    for marker_name in ('.range-continuation-used', '.range-continuation-2-used', SEGMENTED_MARKER):
        marker = destination / marker_name
        if marker.is_symlink() or not marker.is_file():
            raise ValueError('download_prior_continuation_missing')
    big_bytes = 0
    for name in ('model.onnx', 'model.onnx.data'):
        size, digest = pins[name]
        if not verify_file(destination / name, size, digest):
            raise ValueError('download_existing_mismatch')
        big_bytes += size
    small = [(name, size, digest) for name, (size, digest) in pins.items()
             if name not in {'model.onnx', 'model.onnx.data'}]
    if (len(small) != MAX_SMALL_FILE_REQUESTS
        or sum(size for _name, size, _digest in small) != SMALL_FILES_TRANSFER_BYTES
        or any(size <= 0 or size > MAX_SMALL_FILE_BYTES or Path(name).name != name
               or name in {'.', '..'} for name, size, _digest in small)
        or big_bytes + SMALL_FILES_TRANSFER_BYTES > MAX_BYTES):
        raise ValueError('download_small_files_budget_invalid')
    return big_bytes, small


def _download_six_small_files(values, destination):
    started, requests, transferred, verified = monotonic(), 0, 0, 0
    stage = 'preflight'
    try:
        verified, small = _small_files_preflight(values, destination)
        with (destination / SMALL_FILES_MARKER).open('x', encoding='ascii') as marker:
            marker.write('one separately approved public six-file completion\n')
        for name, size, digest in small:
            stage = 'budget'
            remaining_total = MAX_SMALL_FILES_SECONDS - (monotonic() - started)
            if remaining_total <= 0 or requests >= MAX_SMALL_FILE_REQUESTS:
                raise ValueError('download_small_files_budget_exceeded')
            url = public_artifact_url(values, name)
            request = Request(url, headers={'User-Agent': 'Cardchemy-approved-public-artifact/1',
                                            'Accept-Encoding': 'identity'})
            request_started = monotonic()
            requests += 1
            stage = 'transport_open'
            def abort_file():
                print(json.dumps({'status': 'download_unavailable', 'failure_stage': 'budget',
                                  'verified_bytes': verified, 'transferred_bytes': transferred,
                                  'artifact_requests': requests, 'model_loaded': False,
                                  'provider_requests': 0}, separators=(',', ':')), flush=True)
                os._exit(1)
            file_watchdog = threading.Timer(MAX_SMALL_FILE_SECONDS, abort_file)
            file_watchdog.daemon = True
            file_watchdog.start()
            partial = destination / (name + '.part')
            path = destination / name
            hasher = hashlib.sha256()
            try:
                with urlopen(request, timeout=min(60.0, remaining_total, MAX_SMALL_FILE_SECONDS)) as response:
                    if monotonic() - request_started > MAX_SMALL_FILE_SECONDS:
                        stage = 'budget'
                        raise ValueError('download_small_file_time_budget')
                    stage = 'response_contract'
                    encoding = response.headers.get('Content-Encoding', 'identity')
                    if (response.status != 200 or encoding.strip().lower() != 'identity'
                        or response.headers.get('Content-Length') != str(size)):
                        raise ValueError('download_small_file_response_invalid')
                    stage = 'disk_write'
                    with partial.open('xb') as output:
                        current = os.fstat(output.fileno())
                        if (partial.is_symlink() or not stat.S_ISREG(current.st_mode)
                            or current.st_nlink != 1 or output.tell() != 0):
                            raise ValueError('download_partial_changed')
                        partial_identity = (current.st_dev, current.st_ino)
                        count = 0
                        read = getattr(response, 'read1', response.read)
                        while True:
                            stage = 'transport_read'
                            block = read(64 * 1024)
                            if (monotonic() - started > MAX_SMALL_FILES_SECONDS
                                or monotonic() - request_started > MAX_SMALL_FILE_SECONDS):
                                stage = 'budget'
                                raise ValueError('download_small_file_time_budget')
                            if not block:
                                break
                            stage = 'response_length'
                            if len(block) > size - count:
                                raise ValueError('download_small_file_overflow')
                            stage = 'disk_write'
                            if output.write(block) != len(block):
                                raise ValueError('download_short_write')
                            hasher.update(block)
                            count += len(block)
                            transferred += len(block)
                            if (transferred > SMALL_FILES_TRANSFER_BYTES
                                or verified + count > MAX_BYTES):
                                stage = 'budget'
                                raise ValueError('download_small_files_budget_exceeded')
                        stage = 'response_length'
                        if count != size:
                            raise ValueError('download_small_file_short')
            finally:
                file_watchdog.cancel()
            stage = 'digest'
            if hasher.hexdigest() != digest or not verify_file(partial, size, digest):
                raise ValueError('download_small_file_digest_invalid')
            # A bounded local rename retry does not repeat the HTTP request;
            # recheck source identity and both digests before accepting it.
            for local_attempt in range(LOCAL_FINALIZE_ATTEMPTS):
                stage = 'finalize'
                if monotonic() - started > MAX_SMALL_FILES_SECONDS:
                    stage = 'budget'
                    raise ValueError('download_time_budget')
                if path.exists() or path.is_symlink() or partial.is_symlink() or not partial.is_file():
                    raise ValueError('download_destination_race')
                current = partial.stat()
                if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                    or current.st_size != size
                    or (current.st_dev, current.st_ino) != partial_identity):
                    raise ValueError('download_partial_changed')
                stage = 'digest'
                if not verify_file(partial, size, digest):
                    raise ValueError('download_disk_digest_invalid')
                stage = 'finalize'
                try:
                    partial.rename(path)
                except OSError:
                    if local_attempt + 1 == LOCAL_FINALIZE_ATTEMPTS:
                        raise
                    sleep(LOCAL_FINALIZE_DELAY_SECONDS * (local_attempt + 1))
                    continue
                stage = 'digest'
                if not verify_file(path, size, digest):
                    raise ValueError('download_final_digest_invalid')
                break
            verified += size
            print(json.dumps({'progress': 'public_file_verified', 'file': name,
                              'bytes': size}, separators=(',', ':')), flush=True)
        stage = 'bundle_digest'
        if (requests != MAX_SMALL_FILE_REQUESTS or transferred != SMALL_FILES_TRANSFER_BYTES
            or verified != sum(size for size, _digest in values['PINS'].values())):
            raise ValueError('download_bundle_incomplete')
        for name, (size, digest) in values['PINS'].items():
            if monotonic() - started > MAX_SMALL_FILES_SECONDS:
                stage = 'budget'
                raise ValueError('download_time_budget')
            if not verify_file(destination / name, size, digest):
                raise ValueError('download_bundle_digest_invalid')
        return {'status': 'download_completed', 'bundle_bytes': verified,
                'artifact_requests': requests, 'transferred_bytes': transferred,
                'elapsed_ms': round((monotonic() - started) * 1000, 2),
                'model_loaded': False, 'provider_requests': 0}
    except Exception:
        return {'status': 'download_unavailable', 'failure_stage': stage,
                'verified_bytes': verified, 'transferred_bytes': transferred,
                'artifact_requests': requests, 'model_loaded': False, 'provider_requests': 0}


def _readme_preflight(values, destination, *, corrected=False):
    pins = values['PINS']
    if README_NAME not in pins or pins[README_NAME][0] != README_BYTES or len(pins) != 8:
        raise ValueError('download_readme_manifest_invalid')
    prior_markers = {'.range-continuation-used', '.range-continuation-2-used',
                     SEGMENTED_MARKER, SMALL_FILES_MARKER}
    if corrected:
        prior_markers.add(README_MARKER)
    expected = prior_markers | (set(pins) - {README_NAME})
    if {entry.name for entry in destination.iterdir()} != expected:
        raise ValueError('download_readme_state_changed')
    for marker_name in prior_markers:
        marker = destination / marker_name
        if marker.is_symlink() or not marker.is_file():
            raise ValueError('download_prior_continuation_missing')
    verified = 0
    for name, (size, digest) in pins.items():
        if Path(name).name != name or name in {'.', '..'}:
            raise ValueError('download_manifest_invalid')
        if name != README_NAME:
            if not verify_file(destination / name, size, digest):
                raise ValueError('download_existing_mismatch')
            verified += size
    if verified + README_BYTES > MAX_BYTES or verified + README_BYTES != FROZEN_BUNDLE_BYTES:
        raise ValueError('download_readme_budget_invalid')
    return verified


def _download_readme_only(values, destination, *, corrected=False):
    started, requests, transferred, verified = monotonic(), 0, 0, 0
    stage = 'preflight'
    try:
        verified = _readme_preflight(values, destination, corrected=corrected)
        marker_name = CORRECTED_README_MARKER if corrected else README_MARKER
        with (destination / marker_name).open('x', encoding='ascii') as marker:
            marker.write('one separately approved public README completion\n')
        stage = 'budget'
        remaining_total = MAX_README_SECONDS - (monotonic() - started)
        if remaining_total <= 0:
            raise ValueError('download_readme_time_budget')
        size, digest = values['PINS'][README_NAME]
        url = public_artifact_url(values, README_NAME)
        request = Request(url, headers={'User-Agent': 'Cardchemy-approved-public-artifact/1',
                                        'Accept-Encoding': 'identity'})
        partial = destination / (README_NAME + '.part')
        path = destination / README_NAME
        hasher = hashlib.sha256()
        request_started = monotonic()
        requests = 1
        stage = 'transport_open'
        def abort_call():
            print(json.dumps({'status': 'download_unavailable', 'failure_stage': 'budget',
                              'verified_bytes': verified, 'transferred_bytes': transferred,
                              'artifact_requests': requests, 'model_loaded': False,
                              'provider_requests': 0}, separators=(',', ':')), flush=True)
            os._exit(1)
        call_watchdog = threading.Timer(MAX_README_CALL_SECONDS, abort_call)
        call_watchdog.daemon = True
        call_watchdog.start()
        try:
            with urlopen(request, timeout=min(60.0, remaining_total, MAX_README_CALL_SECONDS)) as response:
                if monotonic() - request_started > MAX_README_CALL_SECONDS:
                    stage = 'budget'
                    raise ValueError('download_readme_call_budget')
                stage = 'response_contract'
                encoding = response.headers.get('Content-Encoding', 'identity')
                if (response.status != 200 or encoding.strip().lower() != 'identity'
                    or response.headers.get('Content-Length') != str(size)):
                    raise ValueError('download_readme_response_invalid')
                stage = 'disk_write'
                with partial.open('xb') as output:
                    current = os.fstat(output.fileno())
                    if (partial.is_symlink() or not stat.S_ISREG(current.st_mode)
                        or current.st_nlink != 1 or output.tell() != 0):
                        raise ValueError('download_partial_changed')
                    identity = (current.st_dev, current.st_ino)
                    read = getattr(response, 'read1', response.read)
                    while True:
                        stage = 'transport_read'
                        block = read(64 * 1024)
                        if (monotonic() - started > MAX_README_SECONDS
                            or monotonic() - request_started > MAX_README_CALL_SECONDS):
                            stage = 'budget'
                            raise ValueError('download_readme_time_budget')
                        if not block:
                            break
                        stage = 'response_length'
                        if len(block) > size - transferred:
                            raise ValueError('download_readme_overflow')
                        stage = 'disk_write'
                        if output.write(block) != len(block):
                            raise ValueError('download_short_write')
                        hasher.update(block)
                        transferred += len(block)
                    stage = 'response_length'
                    if transferred != size:
                        raise ValueError('download_readme_short')
        finally:
            call_watchdog.cancel()
        stage = 'digest'
        if hasher.hexdigest() != digest or not verify_file(partial, size, digest):
            raise ValueError('download_readme_digest_invalid')
        for local_attempt in range(LOCAL_FINALIZE_ATTEMPTS):
            stage = 'finalize'
            if monotonic() - started > MAX_README_SECONDS:
                stage = 'budget'
                raise ValueError('download_readme_time_budget')
            if path.exists() or path.is_symlink() or partial.is_symlink() or not partial.is_file():
                raise ValueError('download_destination_race')
            current = partial.stat()
            if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                or current.st_size != size or (current.st_dev, current.st_ino) != identity):
                raise ValueError('download_partial_changed')
            stage = 'digest'
            if not verify_file(partial, size, digest):
                raise ValueError('download_disk_digest_invalid')
            stage = 'finalize'
            try:
                partial.rename(path)
            except OSError:
                if local_attempt + 1 == LOCAL_FINALIZE_ATTEMPTS:
                    raise
                sleep(LOCAL_FINALIZE_DELAY_SECONDS * (local_attempt + 1))
                continue
            stage = 'digest'
            if not verify_file(path, size, digest):
                raise ValueError('download_final_digest_invalid')
            break
        verified += size
        stage = 'bundle_digest'
        for name, (file_size, file_digest) in values['PINS'].items():
            if monotonic() - started > MAX_README_SECONDS:
                stage = 'budget'
                raise ValueError('download_readme_time_budget')
            if not verify_file(destination / name, file_size, file_digest):
                raise ValueError('download_bundle_digest_invalid')
        return {'status': 'download_completed', 'bundle_bytes': verified,
                'artifact_requests': requests, 'transferred_bytes': transferred,
                'elapsed_ms': round((monotonic() - started) * 1000, 2),
                'model_loaded': False, 'provider_requests': 0}
    except Exception:
        return {'status': 'download_unavailable', 'failure_stage': stage,
                'verified_bytes': verified, 'transferred_bytes': transferred,
                'artifact_requests': requests, 'model_loaded': False, 'provider_requests': 0}


def download(*, resume_public_partial=False, approved_second_continuation=False,
             approved_segmented_continuation=False, approved_six_small_files=False,
             approved_readme_only=False, approved_corrected_readme=False):
    if os.getenv('CARDCH_PUBLIC_4B_DOWNLOAD_APPROVED') != 'ONE_PINNED_PUBLIC_BUNDLE_NO_RETRY':
        return {'status': 'download_not_authorized', 'artifact_requests': 0}
    if approved_second_continuation and (
        not resume_public_partial
        or os.getenv('CARDCH_PUBLIC_4B_SECOND_CONTINUATION_APPROVED') != 'ONE_MORE_PINNED_RANGE_NO_RETRY'
    ):
        return {'status': 'download_not_authorized', 'artifact_requests': 0}
    if approved_segmented_continuation and (
        not resume_public_partial or approved_second_continuation
        or os.getenv('CARDCH_PUBLIC_4B_SEGMENTED_CONTINUATION_APPROVED')
            != 'ONE_FROZEN_SEGMENTED_RANGE_NO_RETRY'
    ):
        return {'status': 'download_not_authorized', 'artifact_requests': 0}
    if approved_six_small_files and (
        resume_public_partial or approved_second_continuation or approved_segmented_continuation
        or os.getenv('CARDCH_PUBLIC_4B_SIX_SMALL_FILES_APPROVED') != 'ONE_FROZEN_SIX_FILES_NO_RETRY'
    ):
        return {'status': 'download_not_authorized', 'artifact_requests': 0}
    if approved_readme_only and (
        resume_public_partial or approved_second_continuation or approved_segmented_continuation
        or approved_six_small_files or approved_corrected_readme
        or os.getenv('CARDCH_PUBLIC_4B_README_ONLY_APPROVED')
            != 'ONE_FROZEN_PUBLIC_README_NO_RETRY'
    ):
        return {'status': 'download_not_authorized', 'artifact_requests': 0}
    if approved_corrected_readme and (
        resume_public_partial or approved_second_continuation or approved_segmented_continuation
        or approved_six_small_files or approved_readme_only
        or os.getenv('CARDCH_PUBLIC_4B_CORRECTED_README_APPROVED')
            != 'ONE_CORRECTED_ROOT_README_NO_RETRY'
    ):
        return {'status': 'download_not_authorized', 'artifact_requests': 0}
    if approved_segmented_continuation:
        try:
            values, destination = manifest(), check_destination()
        except Exception:
            return {'status': 'download_unavailable', 'failure_stage': 'preflight',
                    'verified_bytes': 0, 'transferred_bytes': 0,
                    'artifact_requests': 0, 'model_loaded': False, 'provider_requests': 0}
        return _download_segmented(values, destination)
    if approved_six_small_files:
        try:
            values, destination = manifest(), check_destination()
        except Exception:
            return {'status': 'download_unavailable', 'failure_stage': 'preflight',
                    'verified_bytes': 0, 'transferred_bytes': 0,
                    'artifact_requests': 0, 'model_loaded': False, 'provider_requests': 0}
        return _download_six_small_files(values, destination)
    if approved_readme_only:
        try:
            values, destination = manifest(), check_destination()
        except Exception:
            return {'status': 'download_unavailable', 'failure_stage': 'preflight',
                    'verified_bytes': 0, 'transferred_bytes': 0,
                    'artifact_requests': 0, 'model_loaded': False, 'provider_requests': 0}
        return _download_readme_only(values, destination)
    if approved_corrected_readme:
        try:
            values, destination = manifest(), check_destination()
        except Exception:
            return {'status': 'download_unavailable', 'failure_stage': 'preflight',
                    'verified_bytes': 0, 'transferred_bytes': 0,
                    'artifact_requests': 0, 'model_loaded': False, 'provider_requests': 0}
        return _download_readme_only(values, destination, corrected=True)
    values = manifest()
    destination = check_destination()
    started, requests, total = monotonic(), 0, 0
    limit = MAX_RESUME_SECONDS if resume_public_partial else MAX_SECONDS
    try:
        if resume_public_partial:
            # Preserve the earlier marker as history. A separately approved
            # second continuation gets its own one-shot marker and opt-in.
            # The caller first proves the preceding downloader has exited.
            if approved_second_continuation:
                if not (destination / '.range-continuation-used').is_file():
                    raise ValueError('download_prior_continuation_missing')
                marker_name = '.range-continuation-2-used'
            else:
                marker_name = '.range-continuation-used'
            with (destination / marker_name).open('x', encoding='ascii') as marker:
                marker.write('one bounded approved public continuation\n')
        for name, (size, digest) in values['PINS'].items():
            if Path(name).name != name or name in {'.', '..'}:
                raise ValueError('download_manifest_invalid')
            path = destination / name
            partial = destination / (name + '.part')
            if path.exists() or path.is_symlink():
                if not verify_file(path, size, digest):
                    raise ValueError('download_existing_mismatch')
                total += size
                continue
            offset, hasher, saved_identity = 0, hashlib.sha256(), None
            if partial.exists() or partial.is_symlink():
                if not resume_public_partial or partial.is_symlink() or not partial.is_file():
                    raise ValueError('download_partial_exists')
                with partial.open('rb') as saved:
                    saved_stat = os.fstat(saved.fileno())
                    if saved_stat.st_nlink != 1 or not stat.S_ISREG(saved_stat.st_mode):
                        raise ValueError('download_partial_invalid')
                    saved_identity = (saved_stat.st_dev, saved_stat.st_ino)
                    offset = saved.seek(0, 2)
                    if not 0 < offset <= size:
                        raise ValueError('download_partial_invalid')
                    saved.seek(0)
                    while block := saved.read(1024 * 1024):
                        hasher.update(block)
                        if monotonic() - started > limit:
                            raise ValueError('download_time_budget')
                if offset == size:
                    if hasher.hexdigest() != digest:
                        raise ValueError('download_digest_invalid')
                    partial.rename(path)
                    total += size
                    continue
            remaining = limit - (monotonic() - started)
            if remaining <= 0:
                raise ValueError('download_time_budget')
            url = public_artifact_url(values, name)
            headers = {'User-Agent': 'Cardchemy-approved-public-artifact/1', 'Accept-Encoding': 'identity'}
            if offset:
                headers['Range'] = f'bytes={offset}-'
            request = Request(url, headers=headers)
            requests += 1
            count = offset
            with urlopen(request, timeout=min(60.0, remaining)) as response:
                if response.status != (206 if offset else 200):
                    raise ValueError('download_response_invalid')
                if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                    raise ValueError('download_encoding_invalid')
                if offset and response.headers.get('Content-Range') != f'bytes {offset}-{size - 1}/{size}':
                    raise ValueError('download_range_invalid')
                length = response.headers.get('Content-Length')
                if length is not None and int(length) != size - offset:
                    raise ValueError('download_length_invalid')
                with partial.open('ab' if offset else 'xb') as output:
                    if offset:
                        current = os.fstat(output.fileno())
                        if (partial.is_symlink() or not stat.S_ISREG(current.st_mode)
                            or current.st_nlink != 1 or output.tell() != offset
                            or (current.st_dev, current.st_ino) != saved_identity):
                            raise ValueError('download_partial_changed')
                    read = getattr(response, 'read1', response.read)
                    while block := read(64 * 1024):
                        count += len(block)
                        if count > size or total + count > MAX_BYTES or monotonic() - started > limit:
                            raise ValueError('download_budget_exceeded')
                        output.write(block)
                        hasher.update(block)
            if count != size or hasher.hexdigest() != digest:
                raise ValueError('download_digest_invalid')
            if not verify_file(partial, size, digest):
                raise ValueError('download_disk_digest_invalid')
            # No other experiment process writes this directory; never replace
            # an existing finalized file even if it appeared during download.
            if path.exists() or path.is_symlink():
                raise ValueError('download_destination_race')
            partial.rename(path)
            total += size
            print(json.dumps({'progress': 'public_file_verified', 'file': name,
                              'bytes': size}, separators=(',', ':')), flush=True)
        return {'status': 'download_completed', 'bundle_bytes': total,
                'artifact_requests': requests, 'elapsed_ms': round((monotonic() - started) * 1000, 2),
                'model_loaded': False, 'provider_requests': 0}
    except Exception:
        # Keep a task-owned partial as diagnostic evidence; no automatic replay
        # or unverified reuse. Never emit exceptions or signed CDN URLs.
        return {'status': 'download_unavailable', 'verified_bytes': total,
                'artifact_requests': requests, 'model_loaded': False, 'provider_requests': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-public-partial', action='store_true',
                        help='One deliberate bounded Range continuation after the previous downloader has stopped.')
    parser.add_argument('--second-approved-continuation', action='store_true',
                        help='Separately owner-approved second and final bounded Range continuation.')
    parser.add_argument('--segmented-approved-continuation', action='store_true',
                        help='Separately owner-approved frozen-state segmented Range continuation.')
    parser.add_argument('--six-small-files-approved', action='store_true',
                        help='Separately owner-approved frozen-state six small public files only.')
    parser.add_argument('--readme-only-approved', action='store_true',
                        help='Separately owner-approved frozen-state public README only.')
    parser.add_argument('--corrected-readme-approved', action='store_true',
                        help='Separately owner-approved corrected root README after prior marker use.')
    args = parser.parse_args()
    if args.second_approved_continuation and not args.resume_public_partial:
        parser.error('--second-approved-continuation requires --resume-public-partial')
    if args.segmented_approved_continuation and not args.resume_public_partial:
        parser.error('--segmented-approved-continuation requires --resume-public-partial')
    if args.segmented_approved_continuation and args.second_approved_continuation:
        parser.error('continuation modes are mutually exclusive')
    if args.six_small_files_approved and (args.resume_public_partial
                                          or args.second_approved_continuation
                                          or args.segmented_approved_continuation):
        parser.error('small-file completion is a separate mode')
    if args.readme_only_approved and (args.resume_public_partial
                                      or args.second_approved_continuation
                                      or args.segmented_approved_continuation
                                      or args.six_small_files_approved):
        parser.error('README completion is a separate mode')
    if args.corrected_readme_approved and (args.resume_public_partial
                                           or args.second_approved_continuation
                                           or args.segmented_approved_continuation
                                           or args.six_small_files_approved
                                           or args.readme_only_approved):
        parser.error('corrected README completion is a separate mode')
    def abort():
        result = {'status': 'download_watchdog_timeout', 'model_loaded': False,
                  'provider_requests': 0, 'artifact_requests': None}
        if (args.segmented_approved_continuation or args.six_small_files_approved
            or args.readme_only_approved or args.corrected_readme_approved):
            result['failure_stage'] = 'budget'
        print(json.dumps(result), flush=True)
        os._exit(1)
    watchdog = threading.Timer((MAX_README_SECONDS if (args.readme_only_approved
                                                      or args.corrected_readme_approved)
                                else MAX_SMALL_FILES_SECONDS if args.six_small_files_approved
                                else MAX_SEGMENTED_SECONDS if args.segmented_approved_continuation
                                else MAX_RESUME_SECONDS if args.resume_public_partial else MAX_SECONDS), abort)
    watchdog.daemon = True
    watchdog.start()
    result = download(resume_public_partial=args.resume_public_partial,
                      approved_second_continuation=args.second_approved_continuation,
                      approved_segmented_continuation=args.segmented_approved_continuation,
                      approved_six_small_files=args.six_small_files_approved,
                      approved_readme_only=args.readme_only_approved,
                      approved_corrected_readme=args.corrected_readme_approved)
    watchdog.cancel()
    print(json.dumps(result, separators=(',', ':')))
    raise SystemExit(0 if result['status'] == 'download_completed' else 1)
