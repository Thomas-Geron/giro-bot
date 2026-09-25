"""Termo de riscos: o texto oficial vem do Giro (GET /api/bot/termo).

Aqui ficam só os títulos dos riscos, para o aviso fixo da janela aparecer mesmo
sem internet, e a regra do nome completo (a mesma do site).
"""

RISCOS_PADRAO = [
    "Seu número pode ser bloqueado pelo WhatsApp",
    "Suas contas no Facebook e nos sites de anúncio podem ser bloqueadas",
    "Você pode perder clientes e vendas",
    "O bot pode falhar ou errar",
    "O cliente vê a mensagem como lida",
    "Conversas pessoais podem ir para o Giro",
    "O computador passa a dar acesso ao WhatsApp da loja",
    "Envio em massa é o que mais leva a bloqueio",
    "Não é oficial e pode deixar de existir",
]


def nome_valido(nome: str) -> bool:
    """Nome completo: ao menos duas palavras com duas letras ou mais."""
    return len([p for p in (nome or "").split() if len(p) >= 2]) >= 2


def texto(termo: dict) -> str:
    """Texto corrido do termo para a janela de aceite."""
    linhas = [termo.get("titulo", ""), f"Versão de {termo.get('versao_legivel', '')}", ""]
    for secao in termo.get("secoes", []):
        lista = secao.get("titulo", "").startswith("2.")
        linhas += [secao.get("titulo", ""), ""]
        linhas += [("• " if lista else "") + p + "\n" for p in secao.get("paragrafos", [])]
    return "\n".join(linhas).strip()


if __name__ == "__main__":
    assert nome_valido("Maria Silva") and not nome_valido("Maria") and not nome_valido("a b")
    exemplo = {"titulo": "T", "versao_legivel": "1", "secoes": [
        {"titulo": "1. A", "paragrafos": ["p1"]}, {"titulo": "2. Riscos", "paragrafos": ["r1"]}]}
    assert "• r1" in texto(exemplo) and "p1" in texto(exemplo) and "• p1" not in texto(exemplo)
    print("termo ok")
