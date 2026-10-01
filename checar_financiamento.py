"""Confere a janela do simulador de financiamento (sem rede; config em pasta temporária).
Rodar:  python checar_financiamento.py"""
import sys
import tempfile
import tkinter as tk
from pathlib import Path

import config

PASTA = Path(tempfile.mkdtemp())
config.CONFIG_DIR, config.CONFIG_FILE, config.LOG_FILE = PASTA, PASTA / "config.json", PASTA / "bot.log"

import financiamento as fin  # noqa: E402
import ui_financiamento as uif  # noqa: E402
import ui_tema  # noqa: E402

falhas = []


def checar(cond, msg):
    print(("  OK   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def filhos(tv):
    return tv.get_children()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    uif.messagebox.showinfo = lambda *a, **k: None
    uif.messagebox.showwarning = lambda *a, **k: None
    uif.messagebox.askyesno = lambda *a, **k: True

    print("[config: guarda e lê as financeiras]")
    config.salvar_financeiras([fin.Financeira("Banco X", 0.019, prazos=[24, 48], idade_max_veiculo=10)])
    lidas = config.carregar_financeiras()
    checar(len(lidas) == 1 and lidas[0].nome == "Banco X" and lidas[0].prazos == [24, 48]
           and lidas[0].idade_max_veiculo == 10, "ida e volta pelo config.json")

    ui_tema.preparar_dpi()
    root = tk.Tk()
    ui_tema.aplicar_tema(root)
    root.withdraw()

    print("[simular]")
    jan = uif.JanelaFinanciamento(root)
    jan.withdraw()
    for ent, val in ((jan.ent_valor, "50.000"), (jan.ent_entrada, "10.000"),
                     (jan.ent_renda, "5.000"), (jan.ent_ano, "2020")):
        ent.delete(0, "end"); ent.insert(0, val)
    jan._simular()
    pais = filhos(jan.tv)
    checar(len(pais) == 1, "uma financeira no resultado")
    prazos = filhos(jan.tv, ) and jan.tv.get_children(pais[0])
    checar(len(prazos) == 2, "dois prazos (24 e 48)")
    linhas = [jan.tv.item(p, "values") for p in prazos]
    checar(all(v[0].startswith("R$") for v in linhas), "cada prazo tem parcela em reais")
    checar(any(v[3] == "Cabe" for v in linhas) and any(v[3] == "Não cabe" for v in linhas),
           "48x cabe na renda de 5.000 e 24x não")
    cabe = jan.tv.item(pais[0], "values")[3]
    checar(cabe.startswith("Aprova at"), f"cabeçalho mostra o limite ({cabe})")

    print("[entrada >= valor: avisa e não simula]")
    jan.ent_entrada.delete(0, "end"); jan.ent_entrada.insert(0, "60.000")
    jan._simular()
    checar(len(filhos(jan.tv)) == 1, "resultado não muda (entrada alta demais)")

    print("[gerenciar: exemplos e remover]")
    ger = uif.JanelaFinanceiras(jan, jan._atualizar_contagem)
    ger.withdraw()
    n0 = len(ger.financeiras)
    ger._exemplos()
    checar(len(config.carregar_financeiras()) == n0 + 3, "3 exemplos adicionados e salvos")
    ger.tv.selection_set(ger.tv.get_children()[0])
    ger._remover()
    checar(len(config.carregar_financeiras()) == n0 + 2, "remover apaga a selecionada")

    print("[formulário: valida e grava]")
    salvos = []
    form = uif._FormFinanceira(ger, None, salvos.append)
    form.withdraw()
    form.campos["nome"].delete(0, "end"); form.campos["nome"].insert(0, "Nova Fin")
    form.campos["taxa"].delete(0, "end"); form.campos["taxa"].insert(0, "2,1")
    form.campos["prazos"].delete(0, "end"); form.campos["prazos"].insert(0, "36/60")
    form.campos["ltv"].delete(0, "end"); form.campos["ltv"].insert(0, "95")
    form._salvar()
    checar(len(salvos) == 1 and salvos[0].nome == "Nova Fin"
           and abs(salvos[0].taxa_am - 0.021) < 1e-9 and salvos[0].prazos == [36, 60]
           and abs(salvos[0].ltv_max - 0.95) < 1e-9, "financeira criada a partir do formulário")

    print("[carros que cabem]")
    financeiras = [fin.Financeira("A", 0.019, prazos=[48], ltv_max=0.90, comprometimento_max=0.30)]
    carros = [{"id": 1, "titulo": "Fiat Uno", "ano": 2020, "km": 50000, "valor": 35000},
              {"id": 2, "titulo": "BMW X5", "ano": 2022, "km": 10000, "valor": 300000}]
    jc = uif.JanelaCarros(jan, carros, financeiras, 10000, 8000, jan._usar_carro)
    jc.withdraw()
    iids = jc.tv.get_children()
    checar(len(iids) == 2, "duas linhas (um carro por linha)")
    tags = {jc._iid[i]["titulo"]: jc.tv.item(i, "tags")[0] for i in iids}
    checar(tags.get("Fiat Uno") == "cabe" and tags.get("BMW X5") == "nao",
           "o Uno cabe e a BMW (cara, renda baixa) não")
    bmw = next(i for i in iids if jc._iid[i]["titulo"] == "BMW X5")
    checar("Entrada ≥" in jc.tv.item(bmw, "values")[3], "a BMW mostra a entrada mínima")
    uno = next(i for i in iids if jc._iid[i]["titulo"] == "Fiat Uno")
    jc.tv.selection_set(uno)
    jc._escolher()
    checar(jan.ent_valor.get().startswith("35") and jan.ent_ano.get() == "2020"
           and len(jan.tv.get_children()) == 1,
           "duplo clique leva o carro para a simulação detalhada")

    root.destroy()
    print("\nRESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
