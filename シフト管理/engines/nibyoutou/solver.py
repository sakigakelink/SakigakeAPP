"""
Sakigake Shift - 2病棟エンジン
ソルバーはメインsolver.pyに統合済み。ユーティリティメソッドのみ提供。
"""
from engines.base import WardEngine


class NibyoutouSolver(WardEngine):
    WARD_ID = 'nibyoutou'
