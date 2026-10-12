"""Fachada de compatibilidade; responsabilidade no contexto modular."""
import sys
from rubinot.observacao import execucao as _implementacao
sys.modules[__name__] = _implementacao
