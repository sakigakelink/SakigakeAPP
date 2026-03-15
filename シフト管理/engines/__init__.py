# engines package
# 病棟別ソルバーエンジンを登録

from engines.nibyoutou.solver import NibyoutouSolver
from engines.ichiboutou.solver import IchiboutouSolver
from engines.sanbyoutou.solver import SanbyoutouSolver

ENGINES = {
    'ichiboutou': IchiboutouSolver,
    'nibyoutou': NibyoutouSolver,
    'sanbyoutou': SanbyoutouSolver,
}


def get_engine(ward: str):
    """
    病棟IDに対応するソルバーエンジンのインスタンスを取得

    Args:
        ward: 病棟ID ('nibyoutou', 'ichiboutou', 'sanbyoutou')

    Returns:
        ソルバーエンジンのインスタンス

    Raises:
        ValueError: 未知の病棟IDの場合
    """
    if ward not in ENGINES:
        raise ValueError(f"Unknown ward: {ward}. Available: {list(ENGINES.keys())}")
    return ENGINES[ward]()
