"""
Sakigake Shift - 1病棟エンジン
ソルバーはメインsolver.pyに統合済み。ユーティリティメソッドのみ提供。
"""
from engines.base import WardEngine


class IchiboutouSolver(WardEngine):
    WARD_ID = 'ichiboutou'
