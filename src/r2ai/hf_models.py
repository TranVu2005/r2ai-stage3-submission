"""Pinned Hugging Face models, resolved by (repo id, revision) through huggingface_hub (cache: HF_HOME).

    from r2ai.hf_models import QWEN3_RERANKER_06B, snapshot
    path = snapshot(*QWEN3_RERANKER_06B)

Order: the snapshot of that revision in the HF cache; else a download of that revision (public models, no token) unless
HF_HUB_OFFLINE is set; else the copy the development machine keeps at DATA_DIR/hf_model_cache (fallback only). Every caller
reads the pinned commit, never a branch, so the files are the ones MODELS.md lists.
"""
from __future__ import annotations

from r2ai import paths

from pathlib import Path

BGE_M3 = ('BAAI/bge-m3', '5617a9f61b028005a4858fdac845db406aefb181')
BGE_RERANKER_V2_M3 = ('BAAI/bge-reranker-v2-m3', '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e')
QWEN3_RERANKER_06B = ('Qwen/Qwen3-Reranker-0.6B', 'e61197ed45024b0ed8a2d74b80b4d909f1255473')
QWEN3_RERANKER_4B = ('Qwen/Qwen3-Reranker-4B', '22e683669bc0f0bd69640a1354a6d0aebcfeede5')
JINA_RERANKER_V35 = ('jinaai/jina-reranker-v3.5', 'e8a93f33f0b22108f8c2364f8484ce3422552fbc')
PINNED = {repo: rev for repo, rev in (BGE_M3, BGE_RERANKER_V2_M3, QWEN3_RERANKER_06B, QWEN3_RERANKER_4B, JINA_RERANKER_V35)}


def legacy_snapshot(repo: str, revision: str) -> Path:
    """DATA_DIR/hf_model_cache/models--<org>--<name>/snapshots/<revision> (HF cache layout under the data root)."""
    return paths.DATA_DIR / 'hf_model_cache' / ('models--' + repo.replace('/', '--')) / 'snapshots' / revision


def _offline() -> bool:
    from huggingface_hub import constants
    return bool(constants.HF_HUB_OFFLINE)


def snapshot(repo: str, revision: str) -> Path:
    if len(revision) != 40:
        raise ValueError(f'{repo}: pin a 40-character commit, not {revision!r}')
    from huggingface_hub import snapshot_download
    try:
        return Path(snapshot_download(repo, revision=revision, local_files_only=True))
    except Exception as cached_error:
        error = cached_error
    if not _offline():
        try:
            return Path(snapshot_download(repo, revision=revision))
        except Exception as download_error:
            error = download_error
    legacy = legacy_snapshot(repo, revision)
    if (legacy / 'config.json').is_file():
        return legacy
    raise FileNotFoundError(f'{repo}@{revision} is not in the Hugging Face cache (HF_HOME) nor at {legacy}. Download it once with '
                            f'HF_HUB_OFFLINE unset: hf download {repo} --revision {revision}') from error
