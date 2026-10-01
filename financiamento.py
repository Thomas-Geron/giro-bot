"""Simulador de financiamento do Giro Bot — contas locais, sem acessar financeira nenhuma.

O lojista cadastra as taxas e regras das financeiras com que JÁ trabalha (cada uma tem
as suas, do contrato) e informa os dados do cliente que está na loja e autorizou a
consulta. O módulo calcula, por financeira e por prazo: a parcela, o total, os juros e
até quanto a financeira aceitaria financiar (pelo valor do carro e pela renda).

É uma ESTIMATIVA pela Tabela Price com a taxa nominal. O número que vale é o CET que a
financeira devolve na simulação oficial (inclui IOF, tarifa de cadastro e seguro).
"""
from dataclasses import asdict, dataclass, field

PRAZOS_PADRAO = [24, 36, 48, 60]


@dataclass
class Financeira:
    nome: str
    taxa_am: float                      # juros ao mês, em fração: 1,9% = 0.019
    prazos: list = field(default_factory=lambda: list(PRAZOS_PADRAO))
    ltv_max: float = 0.90               # financia até 90% do valor do veículo
    comprometimento_max: float = 0.30   # a parcela cabe em até 30% da renda
    idade_max_veiculo: int = 0          # anos; 0 = sem limite
    financiado_min: float = 0.0
    financiado_max: float = 0.0         # 0 = sem limite

    @staticmethod
    def de_dict(d: dict) -> "Financeira":
        campos = {f: d[f] for f in Financeira.__dataclass_fields__ if f in d}
        f = Financeira(**campos)
        f.prazos = sorted({int(p) for p in (f.prazos or PRAZOS_PADRAO) if int(p) > 0}) or list(PRAZOS_PADRAO)
        return f


def parcela(financiado: float, taxa_am: float, n: int) -> float:
    """Parcela fixa da Tabela Price."""
    if n <= 0 or financiado <= 0:
        return 0.0
    if taxa_am <= 0:                     # taxa zero: divide igual
        return financiado / n
    return financiado * taxa_am / (1 - (1 + taxa_am) ** -n)


def financiavel_por_parcela(parcela_max: float, taxa_am: float, n: int) -> float:
    """Quanto dá para financiar com uma parcela de no máximo `parcela_max` (valor presente)."""
    if n <= 0 or parcela_max <= 0:
        return 0.0
    if taxa_am <= 0:
        return parcela_max * n
    return parcela_max * (1 - (1 + taxa_am) ** -n) / taxa_am


def simular(fin: Financeira, valor_veiculo: float, entrada: float,
            renda: float = 0.0, idade_veiculo: int | None = None) -> dict:
    """Situação de UMA financeira + as opções por prazo. Dinheiro em R$; renda e idade
    são opcionais (0/None não limitam)."""
    financiado = max(0.0, valor_veiculo - entrada)
    recusa = None
    if idade_veiculo is not None and fin.idade_max_veiculo and idade_veiculo > fin.idade_max_veiculo:
        recusa = f"Aceita veículo com até {fin.idade_max_veiculo} anos (este tem {idade_veiculo})."
    teto_ltv = fin.ltv_max * valor_veiculo
    if fin.financiado_max:
        teto_ltv = min(teto_ltv, fin.financiado_max)

    opcoes = []
    for n in sorted(set(fin.prazos)):
        p = parcela(financiado, fin.taxa_am, n)
        total = entrada + p * n
        teto_renda = financiavel_por_parcela(fin.comprometimento_max * renda, fin.taxa_am, n) if renda else None
        limite = teto_ltv if teto_renda is None else min(teto_ltv, teto_renda)
        cabe = (recusa is None and 0 < financiado <= limite + 0.5
                and (not fin.financiado_min or financiado >= fin.financiado_min))
        opcoes.append({"prazo": n, "parcela": round(p, 2), "total": round(total, 2),
                       "juros": round(total - valor_veiculo, 2),
                       "limite_financiado": round(limite, 2), "cabe": cabe})
    return {
        "financeira": fin.nome,
        "financiado": round(financiado, 2),
        "recusa": recusa,
        "aprova": recusa is None and any(o["cabe"] for o in opcoes),
        # o máximo que financiaria: o melhor prazo (prazo maior cabe mais na renda, até o teto do LTV)
        "limite_financiado": round(max((o["limite_financiado"] for o in opcoes), default=teto_ltv), 2),
        "opcoes": opcoes,
    }


def simular_todas(financeiras: list, valor_veiculo: float, entrada: float,
                  renda: float = 0.0, idade_veiculo: int | None = None) -> list:
    return [simular(f, valor_veiculo, entrada, renda, idade_veiculo) for f in financeiras]


# ── leitura e exibição de valores em reais ────────────────────────────────────
def ler_dinheiro(texto) -> float:
    """Aceita '45000', '45.000', '45000,50', '45.000,50', 'R$ 1.234.567,89'."""
    if isinstance(texto, (int, float)):
        return float(texto)
    limpo = "".join(c for c in str(texto) if c.isdigit() or c in ",.")
    if not limpo:
        return 0.0
    if "," in limpo:                                   # vírgula = decimal (pt-BR); pontos são milhar
        limpo = limpo.replace(".", "").replace(",", ".")
    elif limpo.count(".") == 1 and len(limpo.split(".")[1]) in (1, 2):
        pass                                           # um ponto com 1-2 casas = decimal (ex.: 45000.50)
    else:
        limpo = limpo.replace(".", "")                 # pontos de milhar (ex.: 45.000)
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def fmt_dinheiro(valor: float) -> str:
    return "R$ " + f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(fracao: float) -> str:
    return f"{fracao * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


EXEMPLOS = [  # modelos para o lojista editar com as taxas REAIS das financeiras dele
    asdict(Financeira("Financeira A", 0.0189, idade_max_veiculo=12)),
    asdict(Financeira("Financeira B", 0.0215, ltv_max=0.95)),
    asdict(Financeira("Financeira C", 0.0169, comprometimento_max=0.25, idade_max_veiculo=8)),
]


if __name__ == "__main__":
    # a parcela está certa se o valor presente das n parcelas, na taxa, volta ao financiado
    def vp(pmt, i, n):
        return sum(pmt / (1 + i) ** k for k in range(1, n + 1))

    for F, i, n in [(40000, 0.019, 48), (12345.67, 0.0215, 36), (80000, 0.0169, 60)]:
        p = parcela(F, i, n)
        assert abs(vp(p, i, n) - F) < 0.01, (F, i, n, p, vp(p, i, n))
        assert abs(financiavel_por_parcela(p, i, n) - F) < 0.01   # é a volta de `parcela`

    assert parcela(30000, 0, 10) == 3000 and financiavel_por_parcela(3000, 0, 10) == 30000  # taxa zero
    assert parcela(0, 0.02, 48) == 0 and parcela(1000, 0.02, 0) == 0                        # casos vazios

    fin = Financeira("Teste", 0.019, prazos=[48], ltv_max=0.90, comprometimento_max=0.30)
    r = simular(fin, 50000, 10000, renda=5000)
    o = r["opcoes"][0]
    assert r["financiado"] == 40000 and o["prazo"] == 48
    assert abs(o["total"] - (10000 + o["parcela"] * 48)) < 0.01
    assert o["juros"] > 0 and o["cabe"] and r["aprova"]

    # entrada baixa: 40k > 90% de 42k → não cabe pelo LTV
    assert not simular(fin, 42000, 2000, renda=99999)["opcoes"][0]["cabe"]
    # renda baixa: a parcela não cabe em 30% de 1000 → não aprova
    assert not simular(fin, 50000, 10000, renda=1000)["aprova"]
    # veículo velho: recusa em todos os prazos
    velho = simular(Financeira("X", 0.019, idade_max_veiculo=10), 50000, 10000, renda=9000, idade_veiculo=15)
    assert velho["recusa"] and not velho["aprova"]
    # entrada >= valor: financiado zero, nada a financiar
    assert simular(fin, 30000, 30000)["financiado"] == 0 and not simular(fin, 30000, 30000)["aprova"]

    assert ler_dinheiro("45.000") == 45000 and ler_dinheiro("45000,50") == 45000.50
    assert ler_dinheiro("R$ 1.234.567,89") == 1234567.89 and ler_dinheiro("45000.50") == 45000.50
    assert ler_dinheiro("") == 0 and ler_dinheiro(50000) == 50000
    assert fmt_dinheiro(1234567.8) == "R$ 1.234.567,80" and fmt_pct(0.019) == "1,9%"
    print("financiamento: contas e leitura ok")
