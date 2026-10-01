"""Janela do simulador de financiamento (contas locais; nada é enviado às financeiras).

Abre a partir do atalho "Financiamento" na lateral. O lojista cadastra as financeiras
com que trabalha (taxas e regras do contrato) e simula, para o cliente que está na loja
e autorizou, quanto cada uma financiaria e as parcelas por prazo.
"""
import tkinter as tk
from tkinter import messagebox, ttk

import config
import financiamento as fin
import ui_tema
from ui_componentes import Cartao, placeholder

C = ui_tema.CORES


def _ler_pct(texto, padrao=0.0) -> float:
    try:
        return float(str(texto).replace("%", "").replace(",", ".").strip()) / 100
    except (ValueError, AttributeError):
        return padrao


def _campo(pai, rotulo, dica="", largura=16):
    """Rótulo + Entry numa coluna. Devolve o Entry."""
    caixa = ttk.Frame(pai, style="Superficie.TFrame")
    ttk.Label(caixa, text=rotulo, style="Rotulo.TLabel").pack(anchor="w")
    ent = ttk.Entry(caixa, width=largura)
    ent.pack(anchor="w", pady=(ui_tema.px(pai, 4), 0))
    if dica:
        ui_tema.texto_suave(caixa, dica).pack(anchor="w")
    return caixa, ent


class JanelaFinanciamento(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app, bg=C["fundo"])
        self.app = app
        self.title("Giro Bot — Simulador de financiamento")
        ui_tema.icone(self)
        ui_tema.geometria(self, 1080, 780, minimo=(900, 620), centralizar=True)
        self.transient(app)
        px = lambda v: ui_tema.px(self, v)  # noqa: E731

        topo = tk.Frame(self, bg=C["fundo"])
        topo.pack(fill="x", padx=px(24), pady=(px(20), px(6)))
        tk.Label(topo, text="Simulador de financiamento", bg=C["fundo"], fg=C["texto"],
                 font=(ui_tema.FONTE_FORTE, 16)).pack(anchor="w")
        tk.Label(topo, bg=C["fundo"], fg=C["texto_suave"], font=(ui_tema.FONTE, 9), justify="left",
                 wraplength=px(940), anchor="w",
                 text="Estimativa pela Tabela Price, só para comparar as financeiras. O valor que vale é o "
                      "da simulação oficial de cada uma (o CET inclui IOF, tarifa e seguro). Use com o "
                      "cliente presente, que autorizou a consulta dos dados dele.").pack(anchor="w", pady=(px(2), 0))

        corpo = tk.Frame(self, bg=C["fundo"])
        corpo.pack(fill="both", expand=True, padx=px(24), pady=px(10))
        corpo.columnconfigure(0, weight=0)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(0, weight=1)

        # ── esquerda: dados ──
        cartao = Cartao(corpo, "Dados", numero=1)
        cartao.grid(row=0, column=0, sticky="nsew", padx=(0, px(12)))
        d = cartao.corpo
        cx_valor, self.ent_valor = _campo(d, "Valor do veículo", "Ex.: 45.000")
        cx_valor.pack(anchor="w", fill="x")
        cx_entrada, self.ent_entrada = _campo(d, "Entrada", "Quanto o cliente dá de entrada")
        cx_entrada.pack(anchor="w", fill="x", pady=(px(12), 0))
        cx_renda, self.ent_renda = _campo(d, "Renda do cliente (opcional)", "Para calcular quanto cabe na renda")
        cx_renda.pack(anchor="w", fill="x", pady=(px(12), 0))
        cx_ano, self.ent_ano = _campo(d, "Ano do veículo (opcional)", "Para checar o limite de idade", largura=10)
        cx_ano.pack(anchor="w", fill="x", pady=(px(12), 0))
        for ent, exemplo in ((self.ent_valor, "45.000"), (self.ent_entrada, "10.000"),
                             (self.ent_renda, "5.000"), (self.ent_ano, "2018")):
            placeholder(ent, exemplo)

        ttk.Button(d, text="Simular", style="Primario.TButton", cursor="hand2",
                   command=self._simular).pack(anchor="w", pady=(px(18), 0))
        ttk.Button(d, text="Financeiras…", style="Secundario.TButton", cursor="hand2",
                   command=self._gerenciar).pack(anchor="w", pady=(px(8), 0))
        self.lbl_qtd = ui_tema.texto_suave(d, "")
        self.lbl_qtd.pack(anchor="w", pady=(px(10), 0))

        # ── direita: resultado ──
        res = Cartao(corpo, "Resultado por financeira", numero=2)
        res.grid(row=0, column=1, sticky="nsew")
        moldura = ttk.Frame(res.corpo, style="Superficie.TFrame")
        moldura.pack(fill="both", expand=True)
        moldura.rowconfigure(0, weight=1)
        moldura.columnconfigure(0, weight=1)
        cols = ("parcela", "total", "juros", "situacao")
        self.tv = ttk.Treeview(moldura, columns=cols, show="tree headings", height=16)
        self.tv.heading("#0", text="Financeira / prazo")
        self.tv.heading("parcela", text="Parcela")
        self.tv.heading("total", text="Total a pagar")
        self.tv.heading("juros", text="Juros")
        self.tv.heading("situacao", text="Situação")
        self.tv.column("#0", width=px(170), minwidth=px(120), anchor="w")
        self.tv.column("parcela", width=px(115), anchor="e")
        self.tv.column("total", width=px(130), anchor="e")
        self.tv.column("juros", width=px(120), anchor="e")
        self.tv.column("situacao", width=px(165), minwidth=px(120), anchor="w")
        self.tv.tag_configure("cabe", foreground=C["sucesso_texto"])
        self.tv.tag_configure("nao", foreground=C["texto_suave"])
        self.tv.tag_configure("fin", font=(ui_tema.FONTE_FORTE, 10))
        barra = ttk.Scrollbar(moldura, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=barra.set)
        self.tv.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")
        self.lbl_vazio = ui_tema.texto_suave(
            res.corpo, "Cadastre as financeiras, preencha os dados e clique em Simular.")
        self.lbl_vazio.pack(anchor="w", pady=(px(8), 0))

        self._atualizar_contagem()
        self.ent_valor.focus_set()

    # ── ações ──
    def _atualizar_contagem(self):
        n = len(config.carregar().get("financeiras", []))
        self.lbl_qtd.configure(text=f"{n} financeira(s) cadastrada(s)." if n else
                               "Nenhuma financeira ainda — clique em Financeiras.")

    def _gerenciar(self):
        JanelaFinanceiras(self, self._atualizar_contagem)

    def _simular(self):
        financeiras = config.carregar_financeiras()
        if not financeiras:
            messagebox.showinfo("Financiamento", "Cadastre ao menos uma financeira primeiro "
                                "(botão Financeiras).", parent=self)
            return self._gerenciar()
        valor = fin.ler_dinheiro(self.ent_valor.get())
        entrada = fin.ler_dinheiro(self.ent_entrada.get())
        renda = fin.ler_dinheiro(self.ent_renda.get())
        if valor <= 0:
            return messagebox.showwarning("Financiamento", "Informe o valor do veículo.", parent=self)
        if entrada >= valor:
            return messagebox.showwarning("Financiamento",
                                          "A entrada é igual ou maior que o valor: não há o que financiar.", parent=self)
        idade = None
        ano = "".join(c for c in self.ent_ano.get() if c.isdigit())
        if len(ano) == 4:
            from datetime import datetime
            idade = max(0, datetime.now().year - int(ano))

        self.tv.delete(*self.tv.get_children())
        self.lbl_vazio.pack_forget()
        resultados = fin.simular_todas(financeiras, valor, entrada, renda, idade)
        resultados.sort(key=lambda r: (not r["aprova"], r["opcoes"][0]["parcela"] if r["opcoes"] else 0))
        for r in resultados:
            if r["recusa"]:
                cab = "Recusa o veículo"
            elif r["aprova"]:
                cab = "Aprova até " + fin.fmt_dinheiro(r["limite_financiado"]).rsplit(",", 1)[0]
            else:
                cab = "Não cabe"
            pai = self.tv.insert("", "end", text=f"  {r['financeira']}", values=("", "", "", cab),
                                 open=True, tags=("fin",))
            for o in r["opcoes"]:
                self.tv.insert(pai, "end", text=f"{o['prazo']}x",
                               values=(fin.fmt_dinheiro(o["parcela"]), fin.fmt_dinheiro(o["total"]),
                                       fin.fmt_dinheiro(o["juros"]), "Cabe" if o["cabe"] else "Não cabe"),
                               tags=("cabe",) if o["cabe"] else ("nao",))


class JanelaFinanceiras(tk.Toplevel):
    """Cadastro das financeiras do lojista (nome, taxa e regras)."""

    def __init__(self, pai, ao_mudar):
        super().__init__(pai, bg=C["fundo"])
        self.ao_mudar = ao_mudar
        self.title("Financeiras")
        ui_tema.icone(self)
        ui_tema.geometria(self, 720, 520, minimo=(600, 420), centralizar=True)
        self.transient(pai)
        self.grab_set()
        px = lambda v: ui_tema.px(self, v)  # noqa: E731

        tk.Label(self, text="Financeiras", bg=C["fundo"], fg=C["texto"],
                 font=(ui_tema.FONTE_FORTE, 14)).pack(anchor="w", padx=px(20), pady=(px(18), px(2)))
        tk.Label(self, bg=C["fundo"], fg=C["texto_suave"], font=(ui_tema.FONTE, 9), anchor="w",
                 justify="left", wraplength=px(660),
                 text="Use as taxas e regras REAIS dos seus contratos. A taxa é ao mês. "
                      "LTV é quanto financia do valor do carro; comprometimento é quanto a parcela pode "
                      "tomar da renda.").pack(anchor="w", padx=px(20))

        moldura = ttk.Frame(self, style="Superficie.TFrame")
        moldura.pack(fill="both", expand=True, padx=px(20), pady=px(12))
        moldura.rowconfigure(0, weight=1)
        moldura.columnconfigure(0, weight=1)
        cols = ("taxa", "prazos", "ltv", "renda", "idade")
        self.tv = ttk.Treeview(moldura, columns=cols, show="headings", height=10)
        for c, t, w in (("taxa", "Taxa a.m.", 90), ("prazos", "Prazos", 150), ("ltv", "LTV", 80),
                        ("renda", "Comprom.", 90), ("idade", "Idade máx.", 90)):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=px(w), anchor="center")
        self.tv.heading("#0", text="")
        barra = ttk.Scrollbar(moldura, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=barra.set)
        self.tv.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")
        self.tv.bind("<Double-1>", lambda _e: self._editar())

        acoes = tk.Frame(self, bg=C["fundo"])
        acoes.pack(fill="x", padx=px(20), pady=(0, px(16)))
        ttk.Button(acoes, text="Adicionar", style="Primario.TButton", cursor="hand2",
                   command=self._adicionar).pack(side="left")
        ttk.Button(acoes, text="Editar", style="Secundario.TButton", cursor="hand2",
                   command=self._editar).pack(side="left", padx=(px(8), 0))
        ttk.Button(acoes, text="Remover", style="Perigo.TButton", cursor="hand2",
                   command=self._remover).pack(side="left", padx=(px(8), 0))
        ttk.Button(acoes, text="Preencher com exemplos", style="FantasmaCartao.TButton", cursor="hand2",
                   command=self._exemplos).pack(side="right")

        self.financeiras = config.carregar_financeiras()
        self._listar()

    def _listar(self):
        self.tv.delete(*self.tv.get_children())
        for i, f in enumerate(self.financeiras):
            self.tv.insert("", "end", iid=str(i), text=f.nome, values=(
                fin.fmt_pct(f.taxa_am), "/".join(str(p) for p in f.prazos) + "x",
                fin.fmt_pct(f.ltv_max), fin.fmt_pct(f.comprometimento_max),
                f"{f.idade_max_veiculo} anos" if f.idade_max_veiculo else "—"))
        # o nome fica na coluna da árvore: liga show de novo? usamos #0 como nome
        self.tv.configure(show="tree headings")
        self.tv.heading("#0", text="Financeira")
        self.tv.column("#0", width=ui_tema.px(self, 150), anchor="w")

    def _selecionada(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _salvar(self):
        config.salvar_financeiras(self.financeiras)
        self._listar()
        if self.ao_mudar:
            self.ao_mudar()

    def _adicionar(self):
        _FormFinanceira(self, None, self._guardar)

    def _editar(self):
        i = self._selecionada()
        if i is None:
            return messagebox.showinfo("Financeiras", "Escolha uma financeira na lista.", parent=self)
        _FormFinanceira(self, self.financeiras[i], lambda f: self._guardar(f, i))

    def _guardar(self, financeira, indice=None):
        if indice is None:
            self.financeiras.append(financeira)
        else:
            self.financeiras[indice] = financeira
        self._salvar()

    def _remover(self):
        i = self._selecionada()
        if i is None:
            return messagebox.showinfo("Financeiras", "Escolha uma financeira na lista.", parent=self)
        if messagebox.askyesno("Remover", f"Remover {self.financeiras[i].nome}?", parent=self):
            del self.financeiras[i]
            self._salvar()

    def _exemplos(self):
        if self.financeiras and not messagebox.askyesno(
                "Exemplos", "Isto adiciona financeiras de exemplo para você editar. Continuar?", parent=self):
            return
        self.financeiras += [fin.Financeira.de_dict(d) for d in fin.EXEMPLOS]
        self._salvar()


class _FormFinanceira(tk.Toplevel):
    """Formulário de uma financeira."""

    def __init__(self, pai, financeira, ao_salvar):
        super().__init__(pai, bg=C["cartao"])
        self.ao_salvar = ao_salvar
        self.title("Editar financeira" if financeira else "Nova financeira")
        ui_tema.icone(self)
        ui_tema.geometria(self, 440, 560, centralizar=True)
        self.transient(pai)
        self.grab_set()
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        f = financeira or fin.Financeira("", 0.019)

        wrap = tk.Frame(self, bg=C["cartao"])
        wrap.pack(fill="both", expand=True, padx=px(22), pady=px(20))
        self.campos = {}

        def linha(chave, rotulo, valor, dica=""):
            tk.Label(wrap, text=rotulo, bg=C["cartao"], fg=C["texto"],
                     font=(ui_tema.FONTE_FORTE, 10)).pack(anchor="w", pady=(px(10), px(2)))
            ent = ttk.Entry(wrap)
            ent.insert(0, valor)
            ent.pack(fill="x")
            if dica:
                tk.Label(wrap, text=dica, bg=C["cartao"], fg=C["texto_suave"],
                         font=(ui_tema.FONTE, 8), anchor="w", justify="left", wraplength=px(390)).pack(anchor="w")
            self.campos[chave] = ent

        linha("nome", "Nome", f.nome, "Como aparece na simulação.")
        linha("taxa", "Taxa de juros ao mês (%)", fin.fmt_pct(f.taxa_am).replace("%", ""), "Ex.: 1,9")
        linha("prazos", "Prazos (meses)", "/".join(str(p) for p in f.prazos), "Separados por barra: 24/36/48/60")
        linha("ltv", "Financia até (% do valor do carro)", fin.fmt_pct(f.ltv_max).replace("%", ""), "Ex.: 90")
        linha("renda", "Parcela até (% da renda)", fin.fmt_pct(f.comprometimento_max).replace("%", ""), "Ex.: 30")
        linha("idade", "Idade máxima do veículo (anos)", str(f.idade_max_veiculo or ""), "Vazio = sem limite.")

        botoes = tk.Frame(self, bg=C["cartao"])
        botoes.pack(fill="x", padx=px(22), pady=(0, px(18)))
        ttk.Button(botoes, text="Salvar", style="Primario.TButton", cursor="hand2",
                   command=self._salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", style="Secundario.TButton", cursor="hand2",
                   command=self.destroy).pack(side="right", padx=(0, px(8)))
        self.campos["nome"].focus_set()

    def _salvar(self):
        nome = self.campos["nome"].get().strip()
        taxa = _ler_pct(self.campos["taxa"].get())
        if not nome:
            return messagebox.showwarning("Financeira", "Dê um nome à financeira.", parent=self)
        if taxa <= 0:
            return messagebox.showwarning("Financeira", "Informe a taxa de juros ao mês.", parent=self)
        prazos = sorted({int(p) for p in "".join(
            c if c.isdigit() else " " for c in self.campos["prazos"].get()).split() if int(p) > 0})
        if not prazos:
            return messagebox.showwarning("Financeira", "Informe ao menos um prazo.", parent=self)
        idade_txt = "".join(c for c in self.campos["idade"].get() if c.isdigit())
        nova = fin.Financeira(
            nome=nome, taxa_am=taxa, prazos=prazos,
            ltv_max=_ler_pct(self.campos["ltv"].get(), 0.90) or 0.90,
            comprometimento_max=_ler_pct(self.campos["renda"].get(), 0.30) or 0.30,
            idade_max_veiculo=int(idade_txt) if idade_txt else 0,
        )
        self.ao_salvar(nova)
        self.destroy()
