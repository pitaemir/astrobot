"""
Estrutura de dados de um lead.

Se você adicionar perguntas novas no prompt (prompts/qualificacao.py),
adicione os campos correspondentes aqui.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


# Status possíveis de um lead no funil
NOVO = "novo"                    # importado, ainda não abordado
EM_CONVERSA = "em_conversa"      # bot conversando
QUALIFICADO = "qualificado"      # respondeu tudo, score calculado
TRANSFERIDO = "transferido"      # atendente humano já foi avisado
SEM_INTERESSE = "sem_interesse"  # disse que não quer mais
SEM_RESPOSTA = "sem_resposta"    # não respondeu a abordagem


@dataclass
class Lead:
    telefone: str                       # formato internacional sem "+" (ex: 5511999999999)

    # ---- Respostas coletadas na conversa ----
    nome: Optional[str] = None
    interesse_ativo: Optional[bool] = None
    regiao: Optional[str] = None
    eh_capital: Optional[bool] = None
    habitantes: Optional[int] = None
    capital_disponivel: Optional[str] = None
    prazo: Optional[str] = None

    # ---- Resultado da qualificação ----
    score: Optional[int] = None
    classificacao: Optional[str] = None   # "QUENTE" | "MORNO" | "FRIO"
    detalhe_score: Dict[str, int] = field(default_factory=dict)

    # ---- Controle ----
    status: str = NOVO
    pedir_humano: bool = False
    historico: List[Dict[str, str]] = field(default_factory=list)
    criado_em: str = field(default_factory=lambda: datetime.now().isoformat())
    atualizado_em: str = field(default_factory=lambda: datetime.now().isoformat())

    # ---- Integrações ----
    chatwoot_conversation_id: Optional[int] = None
    planilha_linha: Optional[int] = None

    # ------------------------------------------------------------------
    def registrar(self, autor: str, texto: str):
        """Guarda uma mensagem no histórico. autor = 'lead' ou 'bot'."""
        self.historico.append({
            "autor": autor,
            "texto": texto,
            "em": datetime.now().isoformat(),
        })
        self.atualizado_em = datetime.now().isoformat()

    def aplicar_dados(self, dados: Dict[str, Any]):
        """Aplica os campos extraídos pela IA, sem apagar o que já existe."""
        for chave, valor in (dados or {}).items():
            if valor is None:
                continue
            if hasattr(self, chave):
                setattr(self, chave, valor)
        self.atualizado_em = datetime.now().isoformat()

    def campos_faltando(self, obrigatorios):
        return [c for c in obrigatorios if getattr(self, c, None) is None]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, dados):
        return cls(**dados)

    def resumo_para_atendente(self):
        """Texto curto enviado ao atendente humano no WhatsApp."""
        def ou(valor, padrao="não informado"):
            return padrao if valor in (None, "") else valor

        local = ou(self.regiao)
        if self.eh_capital is not None:
            local += " (capital)" if self.eh_capital else " (interior)"

        habitantes = (
            f"{self.habitantes:,}".replace(",", ".")
            if isinstance(self.habitantes, int) else ou(self.habitantes)
        )

        linhas = [
            "🚀 *NOVO LEAD QUALIFICADO - ASTROBOX*",
            "",
            f"*Nome:* {ou(self.nome)}",
            f"*WhatsApp:* +{self.telefone}",
            "",
            f"*Região:* {local}",
            f"*Habitantes:* {habitantes}",
            f"*Capital disponível:* {ou(self.capital_disponivel)}",
            f"*Prazo:* {ou(self.prazo)}",
        ]

        if self.score is not None:
            linhas += ["", f"*Score:* {self.score} — *{self.classificacao}*"]

        if self.pedir_humano:
            linhas += ["", "⚠️ _O lead pediu para falar com um atendente._"]

        linhas += ["", f"👉 Iniciar conversa: https://wa.me/{self.telefone}"]
        return "\n".join(linhas)
