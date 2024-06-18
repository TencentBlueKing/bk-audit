from typing import Dict

from apps.notice.builders.error import ErrorBuilder
from apps.notice.builders.risk import RiskBuilder
from apps.notice.constants import RelateType

BUILDERS: Dict = {
    RelateType.RISK: RiskBuilder,
    RelateType.ERROR: ErrorBuilder,
}
