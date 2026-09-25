# ui_execucao.py — registro em linha do tempo, do MarketplaceBot (LogExecucao
# igual ao de lá; `nivel_da_linha` com as mensagens do Giro Bot).
"""
- `nivel_da_linha()`: lê uma mensagem do bot e diz se é info, sucesso, aviso
  ou erro;
- `LogExecucao`: hora, ícone colorido pelo nível e o texto sem pintar a linha
  inteira, com Copiar e Limpar e rolagem automática só quando o usuário já
  está no fim.
"""
import re
import time
import tkinter as tk
from tkinter import ttk

import ui_tema
from ui_componentes import Cartao, estilo_moldura

C = ui_tema.CORES

_ERRO = re.compile(r"\b(traceback|exception|error)\b", re.IGNORECASE)


def nivel_da_linha(texto):
    """'info', 'sucesso', 'aviso', 'erro' ou None (linha vazia)."""
    t = (texto or "").strip()
    if not t:
        return None
    baixo = t.lower()
    if (_ERRO.search(t) or "falha" in baixo or "erro" in baixo or "não consegui" in baixo
            or "recusou" in baixo):
        return "erro"
    if ("não aceito" in baixo or baixo.startswith(("confira", "aviso", "nova versão"))
            or "ignorad" in baixo):
        return "aviso"
    if (baixo.startswith(("conectado", "conexão ok", "termo aceito", "bot rodando"))
            or baixo.endswith("pronto") or "enviada" in baixo):
        return "sucesso"
    return "info"


_NIVEIS = {
    "info": ("info", C["secundaria"]),
    "sucesso": ("ok", C["sucesso"]),
    "aviso": ("aviso", C["aviso"]),
    "erro": ("fechar", C["erro"]),
}


class LogExecucao(Cartao):
    """Cartão do registro. `adicionar(texto)` aceita uma ou várias linhas."""

    VAZIO = "Nada por aqui ainda. Clique em Iniciar para o bot começar."

    def __init__(self, pai, titulo="Registro", altura=10):
        super().__init__(pai, titulo)
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        self.selo_vivo = ui_tema.selo(self.acoes, "Ao vivo", "sucesso", ponto=True)
        ttk.Button(self.acoes, text="Copiar", style="FantasmaCartao.TButton",
                   cursor="hand2", command=self.copiar).pack(side="right")
        ttk.Button(self.acoes, text="Limpar", style="FantasmaCartao.TButton",
                   cursor="hand2", command=self.limpar).pack(side="right")

        console = ttk.Frame(self.corpo, style=estilo_moldura(
            pai, C["fundo"], C["borda"], C["cartao"], raio=8),
            padding=(px(4), px(4)))
        console.pack(fill="both", expand=True)
        console.columnconfigure(0, weight=1)
        console.rowconfigure(0, weight=1)
        self.texto = tk.Text(
            console, height=altura, wrap="word", bg=C["fundo"], fg=C["texto"],
            relief="flat", borderwidth=0, highlightthickness=0,
            font=(ui_tema.FONTE, 10), padx=px(12), pady=px(8),
            spacing1=px(3), spacing3=px(3), cursor="arrow",
            selectbackground=C["primaria_borda"], selectforeground=C["texto"],
            insertwidth=0)
        barra = ttk.Scrollbar(console, orient="vertical", command=self.texto.yview)
        self.texto.configure(yscrollcommand=barra.set)
        self.texto.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")

        self.texto.tag_configure("hora", foreground=C["placeholder"],
                                 font=(ui_tema.FONTE_MONO, 9))
        self.texto.tag_configure("linha", lmargin2=px(96))
        self.texto.tag_configure("vazio", foreground=C["placeholder"],
                                 justify="center", spacing1=px(30))
        for nivel, (_, cor) in _NIVEIS.items():
            self.texto.tag_configure(f"ic_{nivel}", foreground=cor,
                                     font=(ui_tema.FONTE_ICONES, 9))
        self.texto.tag_configure("msg_erro", foreground=C["erro_texto"])
        # só leitura, mas com seleção e Ctrl+C
        self.texto.bind("<Key>", lambda e: None if (e.state & 4) else "break")
        self._vazio = False
        self.limpar()

    def ao_vivo(self, ligado):
        if ligado:
            self.selo_vivo.pack(side="right", padx=(0, ui_tema.px(self, 8)))
        else:
            self.selo_vivo.pack_forget()

    def limpar(self):
        self.texto.delete("1.0", "end")
        self.texto.insert("end", self.VAZIO, "vazio")
        self._vazio = True

    def copiar(self):
        if self._vazio:
            return
        self.clipboard_clear()
        self.clipboard_append(self.texto.get("1.0", "end").strip())

    def adicionar(self, texto, hora=None):
        if self._vazio:
            self.texto.delete("1.0", "end")
            self._vazio = False
        no_fim = self.texto.yview()[1] >= 0.999
        for linha in str(texto).splitlines():
            nivel = nivel_da_linha(linha)
            if nivel is None:
                continue
            if self.texto.index("end-1c") != "1.0":
                self.texto.insert("end", "\n")
            glifo, _ = _NIVEIS[nivel]
            self.texto.insert("end", (hora or time.strftime("%H:%M:%S")) + "   ", ("hora", "linha"))
            self.texto.insert("end", ui_tema.ICONES[glifo], (f"ic_{nivel}", "linha"))
            self.texto.insert("end", "   " + linha.strip(),
                              ("linha", "msg_erro") if nivel == "erro" else ("linha",))
        if no_fim:
            self.texto.see("end")


if __name__ == "__main__":
    assert nivel_da_linha("Conectado ao Giro como: Loja") == "sucesso"
    assert nivel_da_linha("[whatsapp] 2 mensagem(ns) enviada(s) ao Giro") == "sucesso"
    assert nivel_da_linha("[whatsapp] pronto") == "sucesso"
    assert nivel_da_linha("Não consegui falar com o Giro: HTTP 403") == "erro"
    assert nivel_da_linha("[whatsapp] falha ao enviar resposta: x") == "erro"
    assert nivel_da_linha("Termo não aceito: o bot não foi iniciado.") == "aviso"
    assert nivel_da_linha("Bot parado.") == "info"
    assert nivel_da_linha("   ") is None
    print("níveis ok")
