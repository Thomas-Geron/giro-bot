"""Giro Bot — janela do usuário final.

Visual da família do MarketplaceBot (ui_tema, ui_componentes, ui_execucao,
ui_imagens e ui_animacao são cópias de lá, com as cores do Giro): lateral
escura com a marca, os atalhos e o estado da conexão; conteúdo claro em
cartões; aviso de riscos fixo no topo; barra de ações fixa no rodapé.

Thread nenhuma toca no Tk: as mensagens do motor e o resultado das tarefas em
segundo plano chegam por filas, esvaziadas pela thread da janela (`after`
chamado de outra thread falha calado no Tk — lição do MarketplaceBot).
"""
import logging
import math
import os
import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox, ttk

import config
import termo
import ui_animacao
import ui_imagens
import ui_tema
import updater
from giro_client import GiroClient
from runner import Runner
from ui_componentes import Banner, Cartao, Interruptor, Marcador, dica_flutuante, estilo_moldura, placeholder
from ui_execucao import LogExecucao
from version import __version__

C = ui_tema.CORES
logger = logging.getLogger("girobot")

# (chave, nome, ícone, explicação)
CANAIS_UI = [
    ("whatsapp", "WhatsApp do celular", "mensagem",
     "Leva ao Giro as conversas individuais não lidas e envia as respostas. Grupos ficam de fora."),
    ("simulado", "Teste (simulado)", "lampada",
     "Confere a conexão sem abrir o WhatsApp: as mensagens saem do arquivo simulado_entrada.txt."),
]
TITULO_RISCOS = "Riscos de usar o bot (não é oficial):"


# ------------------------------------------------------------- lateral
class ItemLateral(tk.Canvas):
    """Atalho da lateral (hover em pílula), no desenho do MarketplaceBot."""

    def __init__(self, pai, nome_icone, texto, comando):
        self.px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        super().__init__(pai, width=self.px(196), height=self.px(40), bg=C["lateral"],
                         highlightthickness=0, borderwidth=0, cursor="hand2", takefocus=1)
        self.nome_icone, self.texto = nome_icone, texto
        self._imgs = {}
        self._t_hover = ui_animacao.Transicao(self, "hover", lambda _v: self.redesenhar())
        for evento in ("<Button-1>", "<space>", "<Return>"):
            self.bind(evento, lambda _e: comando())
        self.bind("<Enter>", lambda _e: self._t_hover.ir(1.0))
        self.bind("<Leave>", lambda _e: self._t_hover.ir(0.0))
        self.bind("<FocusIn>", lambda _e: self.redesenhar())
        self.bind("<FocusOut>", lambda _e: self.redesenhar())
        self.redesenhar()

    def _pilula(self, cor):
        if cor not in self._imgs:
            self._imgs[cor] = ui_tema.guardar(self, ui_imagens.retangulo(
                self, int(self["width"]), int(self["height"]), self.px(8), cor))
        return self._imgs[cor]

    def redesenhar(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        meio = int(self["height"]) // 2
        foco = 1.0 if self.focus_get() is self else 0.0
        hover = ui_animacao.degrau(max(self._t_hover.valor, foco))
        pilula = ui_animacao.cor(C["lateral"], C["lateral_hover"], hover)
        if pilula != C["lateral"]:
            self.create_image(0, 0, anchor="nw", image=self._pilula(pilula))
        cor = ui_animacao.cor(C["lateral_texto"], "#ffffff", hover)
        self.create_text(self.px(16), meio, anchor="w", fill=cor,
                         text=ui_tema.ICONES[self.nome_icone], font=(ui_tema.FONTE_ICONES, 12))
        self.create_text(self.px(46), meio, anchor="w", fill=cor, text=self.texto,
                         font=(ui_tema.FONTE, 10))


class Lateral(tk.Frame):
    """Marca, atalhos e, no rodapé, o estado da conexão com o Giro."""

    def __init__(self, pai, app):
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        super().__init__(pai, bg=C["lateral"], width=px(220))
        self.pack_propagate(False)

        topo = tk.Frame(self, bg=C["lateral"])
        topo.pack(fill="x", padx=px(16), pady=(px(22), px(26)))
        logo = tk.Canvas(topo, width=px(38), height=px(38), bg=C["lateral"], highlightthickness=0)
        logo.pack(side="left")
        self._logo = ui_tema.guardar(self, ui_imagens.retangulo(
            self, px(38), px(38), px(10), C["primaria"], gradiente=("#c0475f", "#8e2b3d")))
        logo.create_image(0, 0, anchor="nw", image=self._logo)
        logo.create_text(px(19), px(19), text="G", fill="#ffffff", font=(ui_tema.FONTE_FORTE, 15))
        nomes = tk.Frame(topo, bg=C["lateral"])
        nomes.pack(side="left", padx=(px(10), 0))
        tk.Label(nomes, text="Giro Bot", bg=C["lateral"], fg="#ffffff",
                 font=(ui_tema.FONTE_FORTE, 12)).pack(anchor="w")
        tk.Label(nomes, text=f"v{__version__}", bg=C["lateral"], fg=C["lateral_suave"],
                 font=(ui_tema.FONTE, 8)).pack(anchor="w")

        for nome_icone, texto, comando in (
                ("globo", "Abrir o Giro", app.abrir_giro),
                ("escudo", "Ler o termo", lambda: app.abrir_giro("/admin/bot/termo")),
                ("pasta", "Abrir registro", app.abrir_registro),
                ("atualizar", "Buscar atualizações", lambda: app.checar_atualizacao(silencioso=False))):
            ItemLateral(self, nome_icone, texto, comando).pack(padx=px(12), pady=(0, px(4)))

        rodape = tk.Frame(self, bg=C["lateral"])
        rodape.pack(side="bottom", fill="x", padx=px(16), pady=px(18))
        tk.Frame(self, bg="#3d3236", height=1).pack(side="bottom", fill="x")
        linha = tk.Frame(rodape, bg=C["lateral"])
        linha.pack(fill="x")
        self.ponto = tk.Label(linha, text="●", bg=C["lateral"], font=(ui_tema.FONTE, 9))
        self.ponto.pack(side="left")
        self.lbl_estado = tk.Label(linha, bg=C["lateral"], fg=C["lateral_texto"],
                                   font=(ui_tema.FONTE_FORTE, 9))
        self.lbl_estado.pack(side="left", padx=(px(6), 0))
        self.lbl_loja = tk.Label(rodape, bg=C["lateral"], fg=C["lateral_suave"],
                                 font=(ui_tema.FONTE, 9), anchor="w", justify="left",
                                 wraplength=px(184))
        self.lbl_loja.pack(fill="x", pady=(px(2), 0))
        self.conexao(None)

    def conexao(self, loja=None, erro=None):
        if loja:
            self.ponto.configure(fg=C["sucesso"])
            self.lbl_estado.configure(text="Conectado ao Giro")
            self.lbl_loja.configure(text=loja)
        elif erro:
            self.ponto.configure(fg=C["erro"])
            self.lbl_estado.configure(text="Sem conexão")
            self.lbl_loja.configure(text=erro[:120])
        else:
            self.ponto.configure(fg=C["lateral_suave"])
            self.lbl_estado.configure(text="Conexão não testada")
            self.lbl_loja.configure(text="Cole o token e clique em Testar conexão.")


# -------------------------------------------------------- barra de ações
class BarraAcoes(tk.Frame):
    """Rodapé fixo: estado (bolinha que pulsa enquanto roda) + Parar / Iniciar."""

    TEXTOS = {"parado": ("Parado", C["borda_forte"]),
              "rodando": ("Rodando", C["sucesso"]),
              "parando": ("Parando…", C["aviso"])}

    def __init__(self, pai, iniciar, parar):
        super().__init__(pai, bg=C["cartao"])
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        tk.Frame(self, bg=C["borda"], height=1).pack(fill="x", side="top")
        interno = tk.Frame(self, bg=C["cartao"], padx=px(24), pady=px(12))
        interno.pack(fill="x")
        interno.columnconfigure(0, weight=1)

        estado = tk.Frame(interno, bg=C["cartao"])
        estado.grid(row=0, column=0, sticky="we")
        self.ponto = tk.Label(estado, text="●", font=(ui_tema.FONTE, 10), bg=C["cartao"], borderwidth=0)
        self.ponto.pack(side="left", padx=(0, px(8)))
        self.lbl_estado = tk.Label(estado, font=(ui_tema.FONTE_FORTE, 10), bg=C["cartao"],
                                   fg=C["texto"], borderwidth=0)
        self.lbl_estado.pack(side="left")
        self.lbl_status = tk.Label(estado, font=(ui_tema.FONTE, 9), bg=C["cartao"],
                                   fg=C["texto_suave"], anchor="w", borderwidth=0,
                                   text="Deixe esta janela aberta enquanto quiser receber e responder mensagens.")
        self.lbl_status.pack(side="left", padx=(px(12), 0), fill="x", expand=True)

        botoes = tk.Frame(interno, bg=C["cartao"])
        botoes.grid(row=0, column=1, sticky="e")
        self.bt_parar = ttk.Button(botoes, text="■  Parar", style="Perigo.TButton",
                                   cursor="hand2", command=parar)
        self.bt_parar.pack(side="left", padx=(0, px(8)))
        self.bt_iniciar = ttk.Button(botoes, text="▶  Iniciar", style="Primario.TButton",
                                     cursor="hand2", command=iniciar)
        self.bt_iniciar.pack(side="left")
        self.estado = None
        self.definir_estado("parado")

    def _pulsar(self, cor):
        ui_animacao.cancelar(self.ponto, "pulso")
        if cor is None:
            return

        def passo(p):
            intensidade = (1 - math.cos(2 * math.pi * p)) / 2
            self.ponto.configure(fg=ui_animacao.cor(cor, C["cartao"], 0.65 * intensidade))

        def de_novo():
            if self.estado != "parado":
                ui_animacao.animar(self.ponto, "pulso", passo, 1400, fim=de_novo, curva=lambda t: t)
        de_novo()

    def definir_estado(self, estado):
        if estado == self.estado:
            return
        self.estado = estado
        texto, cor = self.TEXTOS[estado]
        self.lbl_estado.configure(text=texto)
        self.ponto.configure(fg=cor)
        self._pulsar(cor if estado != "parado" else None)
        parado = estado == "parado"
        self.bt_iniciar.state(["!disabled"] if parado else ["disabled"])
        self.bt_parar.state(["!disabled"] if estado == "rodando" else ["disabled"])
        self.bt_parar.configure(style="PerigoCheio.TButton" if estado == "rodando" else "Perigo.TButton")


# ------------------------------------------------------------------ app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Giro Bot")
        ui_tema.aplicar_tema(self)
        ui_tema.geometria(self, 1040, 780, minimo=(900, 660), centralizar=True)

        config.configurar_log()
        self.cfg = config.carregar()
        self.fila = queue.Queue()      # mensagens do motor
        self.tarefas = queue.Queue()   # resultados das threads, rodados aqui
        self.runner = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.lateral = Lateral(self, self)
        self.lateral.grid(row=0, column=0, rowspan=2, sticky="ns")
        self._montar_conteudo()
        self.barra = BarraAcoes(self, self._iniciar, self._parar)
        self.barra.grid(row=1, column=1, sticky="we")

        self._log("Pronto. Cole o token, escolha os canais e clique em Iniciar.")
        self.after(200, self._drenar_filas)
        self.after(1500, lambda: self.checar_atualizacao(silencioso=True))
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    # ── layout ────────────────────────────────────────────────────────────
    def _montar_conteudo(self):
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        area = tk.Frame(self, bg=C["fundo"])
        area.grid(row=0, column=1, sticky="nsew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(3, weight=1)
        m = px(24)

        # Riscos: fixos no topo, sem fechar (só o link para ler o termo)
        self.aviso = Banner(area, tipo="risco", fechavel=False, titulo=TITULO_RISCOS,
                            texto=self._texto_riscos(termo.RISCOS_PADRAO))
        self.aviso.grid(row=0, column=0, sticky="we", padx=m, pady=(px(16), 0))
        self.lbl_riscos = self.aviso.rotulo
        link = tk.Label(self.aviso, text="Ver o termo", bg=Banner.TIPOS["risco"][0], fg="#7f1d1d",
                        cursor="hand2", font=(ui_tema.FONTE, 9, "underline"))
        link.grid(row=0, column=2, sticky="n", padx=(px(10), 0))
        link.bind("<Button-1>", lambda _e: self.abrir_giro("/admin/bot/termo"))
        self.aviso.bind("<Configure>", lambda e: self.aviso.rotulo.configure(
            wraplength=max(200, e.width - px(170))), add="+")

        cabecalho = ttk.Frame(area, style="Pagina.TFrame")
        cabecalho.grid(row=1, column=0, sticky="we", padx=m, pady=(px(18), px(14)))
        ttk.Label(cabecalho, text="Painel do bot", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(cabecalho, style="Subtitulo.TLabel",
                  text="Traz as conversas do WhatsApp do celular para a Central de Mensagens do Giro "
                       "e envia daqui as suas respostas.").pack(anchor="w")

        cartoes = ttk.Frame(area, style="Pagina.TFrame")
        cartoes.grid(row=2, column=0, sticky="we", padx=m - px(4))
        cartoes.columnconfigure(0, weight=3, uniform="c")
        cartoes.columnconfigure(1, weight=2, uniform="c")
        self._cartao_conexao(cartoes).grid(row=0, column=0, sticky="nsew", padx=px(4))
        self._cartao_canais(cartoes).grid(row=0, column=1, sticky="nsew", padx=px(4))

        self.log = LogExecucao(area, titulo="Registro", altura=8)
        self.log.grid(row=3, column=0, sticky="nsew", padx=m - px(4), pady=(px(10), px(16)))

    def _cartao_conexao(self, pai):
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        cartao = Cartao(pai, "Conexão com o Giro", numero=1)
        corpo = cartao.corpo
        corpo.columnconfigure(0, weight=1)

        ttk.Label(corpo, text="Endereço do Giro", style="Rotulo.TLabel").grid(row=0, column=0, sticky="w")
        self.var_url = tk.StringVar(value=self.cfg.get("giro_url", ""))
        ttk.Entry(corpo, textvariable=self.var_url).grid(row=1, column=0, columnspan=2, sticky="we",
                                                        pady=(px(4), px(12)))

        ttk.Label(corpo, text="Token do bot", style="Rotulo.TLabel").grid(row=2, column=0, sticky="w")
        self.var_token = tk.StringVar(value=self.cfg.get("token", ""))
        self.ent_token = ttk.Entry(corpo, textvariable=self.var_token, show="•")
        self.ent_token.grid(row=3, column=0, sticky="we", pady=(px(4), 0))
        placeholder(self.ent_token, "Cole aqui o token gerado no Giro")
        self.bt_ver = ttk.Button(corpo, text="Mostrar", style="FantasmaCartao.TButton",
                                 cursor="hand2", command=self._alternar_token)
        self.bt_ver.grid(row=3, column=1, sticky="w", padx=(px(8), 0), pady=(px(4), 0))
        ajuda = ui_tema.texto_suave(corpo, "Gere o token no Giro, na página Bot, depois de aceitar o termo. "
                                           "Ele aparece uma vez só.", cursor="hand2")
        ajuda.grid(row=4, column=0, columnspan=2, sticky="we", pady=(px(6), px(12)))
        ajuda.bind("<Button-1>", lambda _e: self.abrir_giro())

        linha = ttk.Frame(corpo, style="Superficie.TFrame")
        linha.grid(row=5, column=0, columnspan=2, sticky="w")
        self.bt_testar = ttk.Button(linha, text="Testar conexão", style="Secundario.TButton",
                                    cursor="hand2", command=self._testar)
        self.bt_testar.pack(side="left")
        self.selo_teste = None
        self._linha_teste = linha
        return cartao

    def _cartao_canais(self, pai):
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        cartao = Cartao(pai, "Canais", numero=2)
        corpo = cartao.corpo
        corpo.columnconfigure(1, weight=1)
        ativos = set(self.cfg.get("canais", []))
        self.vars_canais = {}
        for i, (chave, nome, _icone, explicacao) in enumerate(CANAIS_UI):
            var = tk.IntVar(value=1 if chave in ativos else 0)
            self.vars_canais[chave] = var
            Interruptor(corpo, var).grid(row=2 * i, column=0, sticky="nw", padx=(0, px(10)),
                                          pady=(px(2) if i == 0 else px(14), 0))
            rotulo = ttk.Label(corpo, text=nome, style="Rotulo.TLabel", cursor="hand2")
            rotulo.grid(row=2 * i, column=1, sticky="w", pady=(px(4) if i == 0 else px(16), 0))
            rotulo.bind("<Button-1>", lambda _e, v=var: v.set(0 if v.get() else 1))
            ui_tema.texto_suave(corpo, explicacao).grid(row=2 * i + 1, column=1, sticky="we")
        ui_tema.dica(corpo, "OLX e WhatsApp oficial não precisam do bot: funcionam direto no Giro, "
                            "em Minha loja.").grid(row=4, column=0, columnspan=2, sticky="we",
                                                    pady=(px(14), 0))
        return cartao

    def _texto_riscos(self, titulos):
        return "  •  ".join(titulos) + "."

    def _mostrar_riscos(self, titulos):
        self.aviso.texto(f"{TITULO_RISCOS}  " + self._texto_riscos(titulos))

    # ── ações ─────────────────────────────────────────────────────────────
    def _alternar_token(self):
        escondido = self.ent_token.cget("show") == "•"
        self.ent_token.configure(show="" if escondido else "•")
        self.bt_ver.configure(text="Esconder" if escondido else "Mostrar")

    def abrir_giro(self, caminho: str = "/admin/bot"):
        url = (self.var_url.get() or "").rstrip("/")
        if url:
            webbrowser.open(f"{url}{caminho}")

    def abrir_registro(self):
        if config.LOG_FILE.exists():
            os.startfile(config.LOG_FILE)  # abre no Bloco de Notas
        else:
            messagebox.showinfo("Registro", "Ainda não há registro. Ele é criado quando o bot roda.")

    def _coletar(self) -> dict:
        return {
            "giro_url": self.var_url.get().strip().rstrip("/"),
            "token": self.var_token.get().strip(),
            "canais": [c for c, v in self.vars_canais.items() if v.get()],
            "poll_segundos": int(self.cfg.get("poll_segundos") or 15),
            "headless": False,
        }

    def _em_segundo_plano(self, funcao, depois):
        """Roda `funcao` numa thread e `depois(resultado)` aqui, na thread da janela."""
        threading.Thread(target=lambda: self.tarefas.put(lambda r=funcao(): depois(r)),
                         daemon=True).start()

    def _resultado_selo(self, texto, tipo):
        if self.selo_teste is not None:
            self.selo_teste.destroy()
        self.selo_teste = ui_tema.selo(self._linha_teste, texto, tipo, ponto=True)
        self.selo_teste.pack(side="left", padx=(ui_tema.px(self, 12), 0))

    def _testar(self):
        cfg = self._coletar()
        erros = config.validar(cfg)
        if erros:
            messagebox.showwarning("Faltam dados", "\n".join(erros))
            return
        config.salvar(cfg)
        self.cfg = config.carregar()
        self.bt_testar.state(["disabled"])
        self._resultado_selo("Testando…", "neutro")

        def pronto(res):
            self.bt_testar.state(["!disabled"])
            if "erro" in res:
                self._log(f"Falha na conexão: {res['erro']}")
                self._resultado_selo("Não conectou", "erro")
                self.lateral.conexao(erro=res["erro"])
            else:
                loja = res.get("loja") or "loja"
                self._log(f"Conexão OK — loja: {loja}")
                self._resultado_selo(f"Conectado: {loja}", "sucesso")
                self.lateral.conexao(loja=loja)
        self._em_segundo_plano(lambda: Runner(cfg).testar_conexao(), pronto)

    def _iniciar(self):
        if self.runner and self.runner.rodando:
            return
        cfg = self._coletar()
        erros = config.validar(cfg)
        if erros:
            messagebox.showwarning("Faltam dados", "\n".join(erros))
            return
        config.salvar(cfg)
        self.cfg = config.carregar()
        if not self._termo_aceito(cfg):
            return
        self.runner = Runner(cfg, log=lambda m: self.fila.put(m))
        self.runner.iniciar()
        self.barra.definir_estado("rodando")
        self.log.ao_vivo(True)

    def _parar(self):
        if self.runner and self.runner.rodando:
            self._log("Parando…")
            self.runner.parar()
            self.barra.definir_estado("parando")

    # ── termo de riscos ───────────────────────────────────────────────────
    def _termo_aceito(self, cfg: dict) -> bool:
        """Busca a versão atual no Giro; se ainda não foi aceita nesta janela, pede o aceite."""
        cli = GiroClient(cfg["giro_url"], cfg["token"])
        try:
            atual = cli.termo()
            if "erro" in atual:
                messagebox.showerror("Termo de riscos", f"Não consegui ler o termo no Giro:\n{atual['erro']}")
                return False
            self._mostrar_riscos([r["titulo"] for r in atual.get("riscos", [])] or termo.RISCOS_PADRAO)
            if self.cfg.get("termo_versao") == atual.get("versao"):
                return True
            nome = self._dialogo_termo(atual)
            if not nome:
                self._log("Termo não aceito: o bot não foi iniciado.")
                return False
            config.salvar({"termo_versao": atual["versao"], "termo_nome": nome,
                           "termo_aceito_em": datetime.now().isoformat(timespec="seconds")})
            self.cfg = config.carregar()
            res = cli.aceitar_termo(atual["versao"], nome)
            self._log("Termo aceito." if "erro" not in res else f"Termo aceito aqui; o Giro respondeu: {res['erro']}")
            return True
        finally:
            cli.fechar()

    def _dialogo_termo(self, atual: dict) -> str:
        """Janela de aceite. Devolve o nome digitado, ou "" se a pessoa não aceitou."""
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        janela = tk.Toplevel(self, bg=C["cartao"])
        janela.title("Giro Bot — Termo de riscos")
        ui_tema.icone(janela)
        ui_tema.geometria(janela, 760, 780, minimo=(620, 600), centralizar=True)
        janela.transient(self)
        janela.grab_set()
        resultado = {"nome": ""}
        pad = px(24)

        tk.Label(janela, text="Antes de usar: leia o termo de riscos", bg=C["cartao"], fg=C["texto"],
                 font=(ui_tema.FONTE_FORTE, 14), anchor="w").pack(fill="x", padx=pad, pady=(pad, px(2)))
        tk.Label(janela, bg=C["cartao"], fg=C["texto_suave"], font=(ui_tema.FONTE, 9), anchor="w",
                 justify="left", wraplength=px(700),
                 text="O Giro Bot não é oficial. Para usar, marque cada declaração e digite seu nome "
                      "completo, que vale como assinatura.").pack(fill="x", padx=pad)

        moldura = ttk.Frame(janela, style=estilo_moldura(janela, C["fundo"], C["borda"], C["cartao"], raio=8),
                            padding=(px(4), px(4)))
        moldura.pack(fill="both", expand=True, padx=pad, pady=(px(12), px(10)))
        moldura.columnconfigure(0, weight=1)
        moldura.rowconfigure(0, weight=1)
        caixa = tk.Text(moldura, height=12, wrap="word", bg=C["fundo"], fg=C["texto"], relief="flat",
                        borderwidth=0, highlightthickness=0, font=(ui_tema.FONTE, 10),
                        padx=px(14), pady=px(10), spacing1=px(2), spacing3=px(2),
                        selectbackground=C["primaria_borda"], selectforeground=C["texto"])
        caixa.insert("1.0", termo.texto(atual))
        caixa.configure(state="disabled")
        barra = ttk.Scrollbar(moldura, orient="vertical", command=caixa.yview)
        caixa.configure(yscrollcommand=barra.set)
        caixa.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")

        marcas = []
        for texto_decl in atual.get("declaracoes", []):
            linha = tk.Frame(janela, bg=C["cartao"])
            linha.pack(fill="x", padx=pad, pady=px(3))
            var = tk.IntVar(value=0)
            marcas.append(var)
            marcador = Marcador(linha, var, comando=lambda: atualizar(), fundo=C["cartao"])
            marcador.pack(side="left", anchor="n")
            rotulo = tk.Label(linha, text=texto_decl, bg=C["cartao"], fg=C["texto"], anchor="w",
                              justify="left", wraplength=px(660), font=(ui_tema.FONTE, 10), cursor="hand2")
            rotulo.pack(side="left", fill="x", padx=(px(8), 0))
            rotulo.bind("<Button-1>", lambda _e, m=marcador: m.alternar())

        tk.Label(janela, text="Seu nome completo", bg=C["cartao"], fg=C["texto"],
                 font=(ui_tema.FONTE_FORTE, 10), anchor="w").pack(fill="x", padx=pad, pady=(px(12), px(4)))
        var_nome = tk.StringVar()
        entrada = ttk.Entry(janela, textvariable=var_nome, width=46)
        entrada.pack(anchor="w", padx=pad)
        placeholder(entrada, "Nome e sobrenome")
        var_nome.trace_add("write", lambda *_: atualizar())

        botoes = tk.Frame(janela, bg=C["cartao"])
        botoes.pack(fill="x", padx=pad, pady=pad)
        btn_aceito = ttk.Button(botoes, text="Li, entendi os riscos e aceito", style="Primario.TButton",
                                cursor="hand2", state="disabled")
        btn_aceito.pack(side="right")
        ttk.Button(botoes, text="Não aceito", style="Secundario.TButton", cursor="hand2",
                   command=janela.destroy).pack(side="right", padx=(0, px(8)))

        def atualizar():
            pronto = bool(marcas) and all(v.get() for v in marcas) and termo.nome_valido(var_nome.get())
            btn_aceito.configure(state="normal" if pronto else "disabled")

        def aceitar():
            resultado["nome"] = var_nome.get().strip()
            janela.destroy()

        btn_aceito.configure(command=aceitar)
        self.wait_window(janela)
        return resultado["nome"]

    # ── atualização ───────────────────────────────────────────────────────
    def checar_atualizacao(self, silencioso: bool = True):
        self._em_segundo_plano(updater.checar, lambda res: self._resultado_atualizacao(res, silencioso))

    def _resultado_atualizacao(self, res: dict, silencioso: bool):
        if "erro" in res:
            if not silencioso:
                messagebox.showinfo("Atualizações", f"Não foi possível verificar agora:\n{res['erro']}")
            return
        if not res.get("ha_atualizacao"):
            self._log(f"Você está na versão mais recente (v{__version__}).")
            if not silencioso:
                messagebox.showinfo("Atualizações", f"Tudo em dia! Você já usa a versão {__version__}.")
            return

        nova = res.get("versao")
        self._log(f"Nova versão disponível: v{nova}")
        msg = f"Nova versão {nova} disponível (você tem {__version__}).\n\nDeseja atualizar agora?"
        notas = (res.get("notas") or "").strip()
        if notas:
            msg += f"\n\nNovidades:\n{notas[:400]}"
        if not messagebox.askyesno("Atualização disponível", msg):
            self._log("Atualização adiada pelo usuário.")
            return

        url = res.get("url_instalador")
        if not url:
            webbrowser.open(res.get("pagina") or updater.PAGINA_RELEASES)
            return
        self._baixar_e_atualizar(url)

    def _baixar_e_atualizar(self, url: str):
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        janela = tk.Toplevel(self, bg=C["cartao"])
        janela.title("Baixando atualização")
        ui_tema.icone(janela)
        ui_tema.geometria(janela, 400, 130, centralizar=True)
        janela.transient(self)
        janela.resizable(False, False)
        texto = tk.StringVar(value="Baixando o instalador…")
        tk.Label(janela, textvariable=texto, bg=C["cartao"], fg=C["texto"],
                 font=(ui_tema.FONTE, 10), anchor="w").pack(fill="x", padx=px(20), pady=(px(20), px(8)))
        barra = ttk.Progressbar(janela, maximum=100)
        barra.pack(fill="x", padx=px(20))

        def progresso(p):  # chamada pela thread do download: só enfileira
            self.tarefas.put(lambda: (barra.configure(value=p),
                                      texto.set(f"Baixando o instalador… {int(p)}%")))

        def baixar():
            try:
                return updater.baixar_instalador(url, progresso=progresso)
            except Exception as exc:
                return exc

        def pronto(res):
            if isinstance(res, Exception):
                janela.destroy()
                messagebox.showerror("Falha no download", str(res))
            else:
                self._instalar(janela, res)
        self._em_segundo_plano(baixar, pronto)

    def _instalar(self, janela, caminho):
        janela.destroy()
        if self.runner and self.runner.rodando:
            self._log("Parando o bot para atualizar…")
            self.runner.parar()
            self.runner.aguardar(15)
        messagebox.showinfo("Pronto para atualizar",
                            "O instalador vai abrir agora e o Giro Bot será fechado.\n"
                            "Ao terminar, abra o Giro Bot novamente.")
        try:
            updater.executar_instalador(caminho)
        except Exception as exc:
            messagebox.showerror("Falha ao instalar", str(exc))
            return
        self.destroy()

    # ── registro ──────────────────────────────────────────────────────────
    def _log(self, msg: str):
        """Mensagem da própria janela: vai para a tela e para o arquivo."""
        logger.info(msg)
        self.log.adicionar(msg)

    def _drenar_filas(self):
        try:
            while True:
                tarefa = self.tarefas.get_nowait()
                tarefa()
        except queue.Empty:
            pass
        try:
            while True:
                msg = self.fila.get_nowait()   # o motor já gravou no arquivo
                self.log.adicionar(msg)
                if msg.startswith("Conectado ao Giro como:"):
                    self.lateral.conexao(loja=msg.split(":", 1)[1].strip())
                elif msg.startswith("Não consegui falar com o Giro:"):
                    self.lateral.conexao(erro=msg.split(":", 1)[1].strip())
        except queue.Empty:
            pass
        if self.runner and not self.runner.rodando and self.barra.estado != "parado":
            self.barra.definir_estado("parado")
            self.log.ao_vivo(False)
        self.after(300, self._drenar_filas)

    def _fechar(self):
        if self.runner and self.runner.rodando:
            if not messagebox.askokcancel("Sair", "O bot está rodando. Deseja parar e sair?"):
                return
            self.runner.parar()
            self.runner.aguardar(10)
        self.destroy()


if __name__ == "__main__":
    ui_tema.preparar_dpi()
    App().mainloop()
