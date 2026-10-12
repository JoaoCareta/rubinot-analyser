"""Fachada de compatibilidade; responsabilidade no contexto modular."""
import sys
from rubinot.adapters import servidor as _implementacao
if __name__ == "__main__":
    _implementacao._demo() if "--demo" in sys.argv else _implementacao.main()
else:
    sys.modules[__name__] = _implementacao
