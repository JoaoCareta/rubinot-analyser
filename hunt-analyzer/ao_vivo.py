"""Fachada de compatibilidade; responsabilidade no contexto modular."""
import sys
from rubinot.hunt import aplicacao as _implementacao
if __name__ == "__main__":
    _implementacao._demo()
else:
    sys.modules[__name__] = _implementacao
