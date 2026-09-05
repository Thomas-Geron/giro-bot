"""Giro Bot — janela do usuário final.

Sem terminal: o lojista cola o token, escolhe os canais e clica em Iniciar.
As mensagens do motor chegam por uma fila e são desenhadas pela thread da
interface (tkinter não é thread-safe).
"""
import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

import config
import updater
from runner import Runner
from version import __version__

CANAIS_UI = [("whatsapp", "WhatsApp"), ("olx", "OLX"), ("simulado", "Simulado (teste)")]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Giro Bot {__version__}")
        self.geometry("620x560")
        self.minsize(560, 480)

        self.cfg = config.carregar()
        self.fila = queue.Queue()
        self.runner = None

        self._montar()
        self.after(200, self._drenar_fila)
        self.after(1500, lambda: self._checar_atualizacao(silencioso=True))
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    # ── layout ────────────────────────────────────────────────────────────
    def _montar(self):
        pad = {"padx": 12, "pady": 6}

        topo = ttk.Frame(self)
        topo.pack(fill="x", **pad)
        ttk.Label(topo, text="Giro Bot", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(topo, text=f"v{__version__}", foreground="#888").pack(side="left", padx=(6, 0))
        self.lbl_status = ttk.Label(topo, text="● parado", foreground="#888")
        self.lbl_status.pack(side="right")

        form = ttk.LabelFrame(self, text="Conexão")
        form.pack(fill="x", **pad)

        ttk.Label(form, text="Endereço do Giro:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.var_url = tk.StringVar(value=self.cfg.get("giro_url", ""))
        ttk.Entry(form, textvariable=self.var_url, width=52).grid(row=0, column=1, sticky="we", padx=8, pady=4)

        ttk.Label(form, text="Token do bot:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.var_token = tk.StringVar(value=self.cfg.get("token", ""))
        self.ent_token = ttk.Entry(form, textvariable=self.var_token, width=52, show="•")
        self.ent_token.grid(row=1, column=1, sticky="we", padx=8, pady=4)

        self.var_ver = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="mostrar", variable=self.var_ver,
                        command=self._alternar_token).grid(row=1, column=2, padx=4)
        form.columnconfigure(1, weight=1)

        ajuda = ttk.Label(
            form, text="O token é gerado no Giro, na página Bot → Gerar token.",
            foreground="#666", cursor="hand2",
        )
        ajuda.grid(row=2, column=1, sticky="w", padx=8)
        ajuda.bind("<Button-1>", lambda _e: self._abrir_giro())

        canais = ttk.LabelFrame(self, text="Canais")
        canais.pack(fill="x", **pad)
        self.vars_canais = {}
        ativos = set(self.cfg.get("canais", []))
        for i, (chave, rotulo) in enumerate(CANAIS_UI):
            v = tk.BooleanVar(value=chave in ativos)
            self.vars_canais[chave] = v
            ttk.Checkbutton(canais, text=rotulo, variable=v).grid(row=0, column=i, padx=10, pady=6, sticky="w")

        botoes = ttk.Frame(self)
        botoes.pack(fill="x", **pad)
        self.btn_iniciar = ttk.Button(botoes, text="Iniciar", command=self._alternar)
        self.btn_iniciar.pack(side="left")
        ttk.Button(botoes, text="Testar conexão", command=self._testar).pack(side="left", padx=8)
        ttk.Button(botoes, text="Abrir o Giro", command=self._abrir_giro).pack(side="left")
        ttk.Button(botoes, text="Buscar atualizações",
                   command=lambda: self._checar_atualizacao(silencioso=False)).pack(side="right")

        reg = ttk.LabelFrame(self, text="Registro")
        reg.pack(fill="both", expand=True, **pad)
        self.txt = scrolledtext.ScrolledText(reg, height=12, state="disabled", wrap="word")
        self.txt.pack(fill="both", expand=True, padx=6, pady=6)

        ttk.Label(
            self, foreground="#666",
            text="Deixe esta janela aberta enquanto quiser receber e responder mensagens.",
        ).pack(pady=(0, 8))

        self._log("Pronto. Cole o token, escolha os canais e clique em Iniciar.")

    # ── ações ─────────────────────────────────────────────────────────────
    def _alternar_token(self):
        self.ent_token.configure(show="" if self.var_ver.get() else "•")

    def _abrir_giro(self):
        url = (self.var_url.get() or "").rstrip("/")
        if url:
            webbrowser.open(f"{url}/admin/bot")

    def _coletar(self) -> dict:
        return {
            "giro_url": self.var_url.get().strip().rstrip("/"),
            "token": self.var_token.get().strip(),
            "canais": [c for c, v in self.vars_canais.items() if v.get()],
            "poll_segundos": int(self.cfg.get("poll_segundos") or 15),
            "headless": False,
        }

    def _testar(self):
        cfg = self._coletar()
        erros = config.validar(cfg)
        if erros:
            messagebox.showwarning("Faltam dados", "\n".join(erros))
            return
        config.salvar(cfg)
        self.cfg = config.carregar()
        res = Runner(cfg, log=self._log).testar_conexao()
        if "erro" in res:
            self._log(f"Falha na conexão: {res['erro']}")
            messagebox.showerror("Não conectou", f"{res['erro']}\n\nConfira o endereço e o token.")
        else:
            loja = res.get("loja") or "loja"
            self._log(f"Conexão OK — loja: {loja}")
            messagebox.showinfo("Conectado", f"Tudo certo!\nLoja: {loja}")

    def _alternar(self):
        if self.runner and self.runner.rodando:
            self._log("Parando…")
            self.runner.parar()
            self.btn_iniciar.configure(text="Iniciar")
            self.lbl_status.configure(text="● parado", foreground="#888")
            return

        cfg = self._coletar()
        erros = config.validar(cfg)
        if erros:
            messagebox.showwarning("Faltam dados", "\n".join(erros))
            return
        config.salvar(cfg)
        self.cfg = config.carregar()
        self.runner = Runner(cfg, log=lambda m: self.fila.put(m))
        self.runner.iniciar()
        self.btn_iniciar.configure(text="Parar")
        self.lbl_status.configure(text="● rodando", foreground="#1a7f37")

    # ── atualização ───────────────────────────────────────────────────────
    def _checar_atualizacao(self, silencioso: bool = True):
        def tarefa():
            res = updater.checar()
            self.after(0, lambda: self._resultado_atualizacao(res, silencioso))
        threading.Thread(target=tarefa, daemon=True).start()

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
        janela = tk.Toplevel(self)
        janela.title("Baixando atualização")
        janela.geometry("360x110")
        janela.transient(self)
        janela.resizable(False, False)
        ttk.Label(janela, text="Baixando o instalador…").pack(pady=(14, 6))
        barra = ttk.Progressbar(janela, length=310, maximum=100)
        barra.pack(pady=4)

        def tarefa():
            try:
                caminho = updater.baixar_instalador(
                    url, progresso=lambda p: self.after(0, lambda: barra.configure(value=p)),
                )
            except Exception as exc:
                self.after(0, lambda: (janela.destroy(),
                                       messagebox.showerror("Falha no download", str(exc))))
                return
            self.after(0, lambda: self._instalar(janela, caminho))

        threading.Thread(target=tarefa, daemon=True).start()

    def _instalar(self, janela, caminho):
        janela.destroy()
        if self.runner and self.runner.rodando:
            self._log("Parando o bot para atualizar…")
            self.runner.parar()
            self.runner.aguardar(15)
        messagebox.showinfo(
            "Pronto para atualizar",
            "O instalador vai abrir agora e o Giro Bot será fechado.\n"
            "Ao terminar, abra o Giro Bot novamente.",
        )
        try:
            updater.executar_instalador(caminho)
        except Exception as exc:
            messagebox.showerror("Falha ao instalar", str(exc))
            return
        self.destroy()

    # ── log ───────────────────────────────────────────────────────────────
    def _log(self, msg: str):
        self.txt.configure(state="normal")
        self.txt.insert("end", f"{datetime.now():%H:%M:%S}  {msg}\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _drenar_fila(self):
        try:
            while True:
                self._log(self.fila.get_nowait())
        except queue.Empty:
            pass
        if self.runner and not self.runner.rodando and self.btn_iniciar["text"] == "Parar":
            self.btn_iniciar.configure(text="Iniciar")
            self.lbl_status.configure(text="● parado", foreground="#888")
        self.after(300, self._drenar_fila)

    def _fechar(self):
        if self.runner and self.runner.rodando:
            if not messagebox.askokcancel("Sair", "O bot está rodando. Deseja parar e sair?"):
                return
            self.runner.parar()
            self.runner.aguardar(10)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
