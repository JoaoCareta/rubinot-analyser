"""Decodificação do contrato JSON da borda HTTP local."""
import json

LIMITE_JSON = 4_000_000


class EntradaInvalida(ValueError):
    def __init__(self, mensagem, status=400):
        super().__init__(mensagem)
        self.status = status


def ler_objeto(cabecalhos, fluxo):
    try:
        tamanho = int(cabecalhos.get('Content-Length', '0'))
    except (ValueError, TypeError):
        raise EntradaInvalida('Content-Length inválido.') from None
    if tamanho < 0:
        raise EntradaInvalida('Content-Length inválido.')
    if tamanho > LIMITE_JSON:
        raise EntradaInvalida('Corpo excede o limite local.', 413)
    corpo = fluxo.read(tamanho)
    if len(corpo) != tamanho:
        raise EntradaInvalida('Corpo incompleto.')
    try:
        dados = json.loads(corpo or b'{}')
    except (ValueError, UnicodeError):
        raise EntradaInvalida('JSON inválido.') from None
    if not isinstance(dados, dict):
        raise EntradaInvalida('O corpo deve ser um objeto JSON.')
    return dados
