import sys
import types

import pytest

from r2ai import hf_models as H

REPO, REV = H.QWEN3_RERANKER_06B


def _hub(monkeypatch, cached=None, downloaded=None, offline=False):
    """Fake huggingface_hub: `cached` / `downloaded` = path returned by the local-only / network call (None = it raises)."""
    calls = []

    def snapshot_download(repo, revision=None, local_files_only=False):
        calls.append((repo, revision, local_files_only))
        got = cached if local_files_only else downloaded
        if got is None:
            raise OSError('not available')
        return str(got)

    hub = types.ModuleType('huggingface_hub')
    hub.snapshot_download = snapshot_download
    hub.constants = types.SimpleNamespace(HF_HUB_OFFLINE=offline)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    return calls


def _legacy(tmp_path, monkeypatch):
    monkeypatch.setattr(H.paths, 'DATA_DIR', tmp_path)
    snap = H.legacy_snapshot(REPO, REV)
    snap.mkdir(parents=True)
    (snap / 'config.json').write_text('{}', encoding='utf-8')
    return snap


def test_every_pin_is_a_full_commit_and_matches_the_model_modules():
    from r2ai.s29 import qwen_judge
    from r2ai.s35 import jina
    assert all(len(rev) == 40 for rev in H.PINNED.values())
    assert H.PINNED[qwen_judge.MODEL_ID] == qwen_judge.MODEL_REVISION
    assert H.PINNED[jina.MODEL_ID] == jina.REVISION


def test_cached_revision_wins_over_the_data_dir_copy(tmp_path, monkeypatch):
    _legacy(tmp_path, monkeypatch)
    calls = _hub(monkeypatch, cached=tmp_path / 'hub-snap')
    assert H.snapshot(REPO, REV) == tmp_path / 'hub-snap'
    assert calls == [(REPO, REV, True)]


def test_download_of_the_pinned_revision_when_not_cached_and_online(tmp_path, monkeypatch):
    _legacy(tmp_path, monkeypatch)
    calls = _hub(monkeypatch, downloaded=tmp_path / 'dl-snap')
    assert H.snapshot(REPO, REV) == tmp_path / 'dl-snap'
    assert calls == [(REPO, REV, True), (REPO, REV, False)]


def test_data_dir_copy_is_only_the_fallback(tmp_path, monkeypatch):
    snap = _legacy(tmp_path, monkeypatch)
    calls = _hub(monkeypatch, offline=True)
    assert H.snapshot(REPO, REV) == snap
    assert calls == [(REPO, REV, True)]                      # offline: no network call


def test_missing_everywhere_names_the_download_command(tmp_path, monkeypatch):
    monkeypatch.setattr(H.paths, 'DATA_DIR', tmp_path)
    _hub(monkeypatch, offline=True)
    with pytest.raises(FileNotFoundError, match=f'hf download {REPO} --revision {REV}'):
        H.snapshot(REPO, REV)


def test_branch_names_are_refused():
    with pytest.raises(ValueError, match='40-character'):
        H.snapshot(REPO, 'main')


def test_qwen_tokenizer_path_goes_through_the_pinned_snapshot(tmp_path, monkeypatch):
    from r2ai.s29 import qwen_judge
    snap = tmp_path / 'snap'
    snap.mkdir()
    (snap / 'tokenizer.json').write_text('{}', encoding='utf-8')
    seen = []
    monkeypatch.setattr(H, 'snapshot', lambda repo, rev: seen.append((repo, rev)) or snap)
    monkeypatch.setattr(qwen_judge.paths, 'OUT_DIR', tmp_path / 'no-out')
    assert qwen_judge._model_path() == snap
    assert seen == [(REPO, REV)]
