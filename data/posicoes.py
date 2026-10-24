# -*- coding: utf-8 -*-
"""Cadastro de posições reais do usuário (quantidade + preço médio por
ativo), persistido no Supabase (tabela posicoes_carteira, ver
sql/posicoes.sql) - uma linha por (sub, ticker).

Diferente da watchlist (lista de acompanhamento em user_prefs.preferencias,
sem quantidade/peso), uma posição aqui é o que viabiliza cálculo de risco
de verdade (concentração/exposição/correlação/volatilidade/drawdown/
cenários de estresse, ver data/radar.py:risco_carteira) - watchlist nunca
é usada como substituto de posição real (regra explícita do projeto)."""

from datetime import date, datetime, timezone

from data.supabase_client import obter_cliente

_TABELA = "posicoes_carteira"

TABELA_AUSENTE = "TABELA_AUSENTE"
TABELA_CREDENCIAL_OU_CONEXAO = "CREDENCIAL_OU_CONEXAO"
TABELA_ERRO_DESCONHECIDO = "ERRO_DESCONHECIDO"

_SINAIS_TABELA_AUSENTE = ("pgrst205", "could not find the table", "schema cache")
_SINAIS_CREDENCIAL_OU_CONEXAO = (
    "401", "403", "pgrst301", "pgrst302", "jwt", "api key", "apikey",
    "unauthorized", "authentication", "permission denied", "42501",
    "row-level security", "row level security", " rls ",
    "timeout", "timed out", "conexao", "conexão", "connection", "dns",
    "ssl", "unreachable", "econnrefused", "name or service not known",
)


def _texto_erro(erro: Exception) -> str:
    partes = [str(erro), repr(erro)]
    for atributo in ("code", "message", "details", "hint"):
        valor = getattr(erro, atributo, None)
        if valor:
            partes.append(str(valor))
    return " ".join(partes).lower()


def _classificar_erro_tabela(erro: Exception) -> str:
    texto = _texto_erro(erro)
    if any(s in texto for s in _SINAIS_TABELA_AUSENTE):
        return TABELA_AUSENTE
    if any(s in texto for s in _SINAIS_CREDENCIAL_OU_CONEXAO):
        return TABELA_CREDENCIAL_OU_CONEXAO
    return TABELA_ERRO_DESCONHECIDO


def tabela_disponivel() -> bool | str | None:
    """Diagnostico (nunca usado pelo fluxo normal de obter_posicoes/
    salvar_posicao/remover_posicao, que ja degradam com seguranca
    independente disso) - mesmo padrao de data/ia_cache.py:tabela_disponivel.
    Retorna True (tabela responde), TABELA_AUSENTE (rodar sql/posicoes.sql),
    TABELA_CREDENCIAL_OU_CONEXAO (chave/RLS/rede), TABELA_ERRO_DESCONHECIDO
    ou None (Supabase sem cliente configurado)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        cliente.table(_TABELA).select("sub").limit(1).execute()
        return True
    except Exception as e:
        causa = _classificar_erro_tabela(e)
        print(f"[posicoes] tabela_disponivel() falhou ({causa}): {e!r}")
        return causa


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def posicao_valida(quantidade, preco_medio) -> bool:
    """Validacao de fronteira (entrada do usuario na UI) - quantidade e
    preco medio precisam ser numeros finitos e positivos; uma posicao com
    quantidade/preco <= 0 nao representa nenhuma posse real."""
    try:
        return float(quantidade) > 0 and float(preco_medio) > 0
    except (TypeError, ValueError):
        return False


def obter_posicoes(sub: str) -> list[dict] | None:
    """Posições cadastradas por `sub`, ordenadas por ticker. None quando o
    Supabase está indisponível (NUNCA [] nesse caso) - quem chama precisa
    distinguir "ninguém cadastrou nada ainda" (lista vazia real) de "não
    foi possível saber" (banco fora do ar), mesmo principio de
    data/user_prefs.py:listar_assinantes_morning_call."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = cliente.table(_TABELA).select("*").eq("sub", sub).order("ticker").execute()
        return resp.data or []
    except Exception as e:
        print(f"[posicoes] obter_posicoes falhou: {e!r}")
        return None


def salvar_posicao(sub: str, ticker: str, quantidade: float, preco_medio: float,
                    data_referencia: date | None = None) -> bool:
    """Upsert por (sub, ticker): cadastro novo cria a linha, cadastrar de
    novo o mesmo ticker SUBSTITUI quantidade/preco_medio (edicao), nunca
    duplica. Validacao (quantidade/preco positivos) e' responsabilidade de
    quem chama (ver posicao_valida) - esta funcao confia no valor recebido,
    mesmo padrao de data/user_prefs.py:salvar_prefs (fronteira valida na UI,
    nao na camada de persistencia)."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table(_TABELA).upsert({
            "sub": sub,
            "ticker": ticker.strip().upper(),
            "quantidade": float(quantidade),
            "preco_medio": float(preco_medio),
            "data_referencia": (data_referencia or date.today()).isoformat(),
            "atualizado_em": _agora_iso(),
        }, on_conflict="sub,ticker").execute()
        return True
    except Exception as e:
        print(f"[posicoes] salvar_posicao({ticker!r}) falhou: {e!r}")
        return False


def remover_posicao(sub: str, ticker: str) -> bool:
    """Remove a posicao de `ticker` pro usuario `sub`. True mesmo se a
    linha nao existia (idempotente) - False so' em falha real do Supabase."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table(_TABELA).delete().eq("sub", sub).eq("ticker", ticker.strip().upper()).execute()
        return True
    except Exception as e:
        print(f"[posicoes] remover_posicao({ticker!r}) falhou: {e!r}")
        return False
