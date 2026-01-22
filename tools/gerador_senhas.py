import random
import string

from strands import tool


@tool
def gerador_de_senhas(
    tamanho: int, incluir_numeros: bool = True, incluir_simbolos: bool = True
):
    """Gera uma senha aleatória e segura.
    Args:
        tamanho: O número de caracteres da senha. Deve ser entre 8 e 128.
        incluir_numeros: Se True, a senha incluirá números.
        incluir_simbolos: Se True, a senha incluirá símbolos de pontuação.
    """
    if not 8 <= tamanho <= 128:
        return "Erro: O tamanho da senha deve ser entre 8 e 128 caracteres."
    caracteres = string.ascii_letters
    if incluir_numeros:
        caracteres += string.digits
    if incluir_simbolos:
        caracteres += string.punctuation

    senha = "".join(random.choice(caracteres) for i in range(tamanho))
    return f"Senha gerada com sucesso: {senha}"
