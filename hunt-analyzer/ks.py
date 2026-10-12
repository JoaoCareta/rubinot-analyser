"""Fachada de compatibilidade; responsabilidade no contexto modular."""
import sys
from rubinot.conflitos import detector as _implementacao
if __name__ == "__main__":
    _implementacao.main()
else:
    sys.modules[__name__] = _implementacao
