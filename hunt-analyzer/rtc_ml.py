"""Fachada compatível; implementação no contexto de planejamento."""
import sys
from rubinot.planejamento import modelos as _implementacao
sys.modules[__name__] = _implementacao
