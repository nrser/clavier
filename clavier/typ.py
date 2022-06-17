##############################################################################
# Typings
# ============================================================================
#
# Per the `typing` built-in module.
#
# This module should not have any in-package dependencies; it should be
# importable by any other module at any time.
#
##############################################################################

from typing import Tuple, Type
from types import TracebackType


TExcInfo = Tuple[Type[BaseException], BaseException, TracebackType]
