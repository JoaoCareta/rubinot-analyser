"""Fachada de compatibilidade; responsabilidade no contexto modular."""
import sys
from rubinot.configuracao_combate import estado as _implementacao
sys.modules[__name__] = _implementacao
