"""
共通キャッシュユーティリティ
元ファイルのmtimeと照合し、差分がなければ再解析をスキップする。
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


def load_cache(cache_path, source_map):
    """キャッシュJSONを読み込み、sourcesのmtimeが全て一致すれば結果を返す。不一致ならNone。

    Args:
        cache_path: キャッシュJSONのパス
        source_map: 現在の {relative_path: mtime} マップ
    Returns:
        キャッシュされたデータ、または不一致時はNone
    """
    if not os.path.isfile(cache_path):
        return None
    try:
        with open(cache_path, encoding='utf-8') as f:
            cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    cached_sources = cache.get('sources', {})
    rounded = {k: round(v, 2) for k, v in source_map.items()}
    if cached_sources != rounded:
        return None
    return cache.get('data')


def save_cache(cache_path, data, source_map):
    """解析結果とソースマップをアトミック書き込み。

    Args:
        cache_path: キャッシュJSONのパス
        data: 保存するデータ
        source_map: {relative_path: mtime} マップ
    """
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cache = {
        'sources': {k: round(v, 2) for k, v in source_map.items()},
        'data': data,
    }
    tmp = cache_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, cache_path)
