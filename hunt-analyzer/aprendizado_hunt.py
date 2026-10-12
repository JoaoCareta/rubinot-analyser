"""Fachada compatível; implementação no contexto de planejamento."""
import sys
from rubinot.planejamento import registro as _implementacao
sys.modules[__name__] = _implementacao
