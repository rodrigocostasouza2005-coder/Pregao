# -*- coding: utf-8 -*-
"""Persistencia do RADAR X (tabelas x_sinais/x_sinais_historico/
x_radar_consumo, ver sql/x_radar.sql) - mesmo padrao de
data/research/store.py: None quando o Supabase esta fora do ar
(distinto de [] = banco respondeu e nao achou nada), nunca lanca pra
quem chama, upsert por post_id (dedup)."""

from datetime import datetime, timezone

from data.supabase_client import obter_cliente

_TABELA = "x_sinais"
_TABELA_HISTORICO = "x_sinais_historico"
_TABELA_CONSUMO = "x_radar_consumo"


def _linha_para_persistir(sinal, classificacao: dict, cruzamento: dict) -> dict:
    agora = datetime.now(timezone.utc).isoformat()
    return {
        "post_id": sinal.post_id,
        "link_original": sinal.link_original,
        "autor": sinal.autor,
        "conta_verificada": sinal.conta_verificada,
        "texto": sinal.contexto,
        "horario_publicacao": sinal.horario_publicacao.isoformat() if sinal.horario_publicacao else None,
        "horario_captura": sinal.horario_captura.isoformat(),
        "ticker": classificacao.get("ticker"),
        "empresa": classificacao.get("empresa"),
        "setor": classificacao.get("setor"),
        "tema": classificacao.get("tema"),
        "categoria": classificacao.get("categoria") or "sem_relevancia",
        "tipo_conteudo": classificacao.get("tipo_conteudo"),
        "sentimento": classificacao.get("sentimento"),
        "argumento_central": classificacao.get("argumento_central"),
        "catalisador": classificacao.get("catalisador"),
        "risco": classificacao.get("risco"),
        "necessita_investigacao": bool(classificacao.get("necessita_investigacao")),
        "relevancia": classificacao.get("relevancia"),
        "relevancia_motivo": classificacao.get("relevancia_motivo"),
        "credibilidade": classificacao.get("credibilidade"),
        "credibilidade_motivo": classificacao.get("credibilidade_motivo"),
        "nivel_evidencia": cruzamento.get("nivel_evidencia"),
        "estado": cruzamento.get("estado"),
        "chave_acontecimento": cruzamento.get("chave_acontecimento"),
        "mesma_origem": cruzamento.get("mesma_origem", False),
        "evidencias_confirmacao": cruzamento.get("evidencias_confirmacao") or [],
        "fontes_cruzadas": cruzamento.get("fontes_cruzadas") or [],
        "versao_classificador": classificacao.get("versao_classificador") or "desconhecida",
        "classificado_em": classificacao.get("classificado_em") or agora,
        "atualizado_em": agora,
    }


def existe_chave_acontecimento(chave: str, *, excluir_post_id: str | None = None) -> bool:
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        query = cliente.table(_TABELA).select("post_id").eq("chave_acontecimento", chave)
        resp = query.execute()
        linhas = [r for r in resp.data if r.get("post_id") != excluir_post_id]
        return len(linhas) > 0
    except Exception:
        return False


def _historizar_se_reprocessado(cliente, post_id: str, nova_versao: str) -> None:
    try:
        resp = cliente.table(_TABELA).select(
            "post_id,categoria,relevancia,relevancia_motivo,credibilidade,credibilidade_motivo,"
            "nivel_evidencia,estado,versao_classificador,classificado_em"
        ).eq("post_id", post_id).limit(1).execute()
    except Exception:
        return
    if not resp.data:
        return
    atual = resp.data[0]
    if atual.get("versao_classificador") == nova_versao:
        return  # mesma versao - nao e' reprocessamento, e' a mesma classificacao
    try:
        cliente.table(_TABELA_HISTORICO).insert({**atual, "substituido_em": datetime.now(timezone.utc).isoformat()}).execute()
    except Exception as exc:
        print(f"[x_radar.store] falha ao historizar {post_id!r}: {exc!r}")


def persistir_lote(enriquecidos: list[dict]) -> int:
    """enriquecidos: lista de {'sinal':Sinal,'classificacao':dict,
    'cruzamento':dict}. Upsert por post_id (dedup); historiza a
    classificacao ANTERIOR quando a versao do classificador mudou (ver
    _historizar_se_reprocessado). Retorna quantos posts eram NOVOS
    (nao existiam antes) - usado pelo Coordenador como 'registros_novos'."""
    cliente = obter_cliente()
    if cliente is None:
        return 0

    post_ids = [item["sinal"].post_id for item in enriquecidos]
    try:
        existentes = {
            r["post_id"]
            for r in cliente.table(_TABELA).select("post_id").in_("post_id", post_ids).execute().data
        } if post_ids else set()
    except Exception:
        existentes = set()

    novos = 0
    for item in enriquecidos:
        sinal, classificacao, cruzamento = item["sinal"], item["classificacao"], item["cruzamento"]
        if not classificacao.get("ok"):
            # falha TECNICA de classificacao (sem credencial Groq/cota/
            # erro) - NUNCA persiste como 'sem_relevancia' (seria fingir
            # que classificou e nao achou nada relevante, quando na
            # verdade nao conseguiu classificar). Fica de fora desta
            # rodada - a proxima coleta tenta de novo (post nao
            # persistido = nao marcado como dedup, buscar_sinais pode
            # trazer o mesmo post outra vez dentro da janela).
            print(f"[x_radar.store] post {sinal.post_id!r} nao persistido - classificacao falhou ({classificacao.get('motivo_falha')})")
            continue
        _historizar_se_reprocessado(cliente, sinal.post_id, classificacao.get("versao_classificador") or "")
        linha = _linha_para_persistir(sinal, classificacao, cruzamento)
        try:
            cliente.table(_TABELA).upsert(linha, on_conflict="post_id").execute()
            if sinal.post_id not in existentes:
                novos += 1
        except Exception as exc:
            print(f"[x_radar.store] falha ao persistir {sinal.post_id!r}: {exc!r}")
    return novos


def registrar_consumo(info_consumo: dict) -> None:
    cliente = obter_cliente()
    if cliente is None:
        return
    janela = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    try:
        atual = cliente.table(_TABELA_CONSUMO).select("leituras").eq("janela", janela).limit(1).execute()
        leituras_antes = atual.data[0]["leituras"] if atual.data else 0
        cliente.table(_TABELA_CONSUMO).upsert({
            "janela": janela,
            "leituras": leituras_antes + info_consumo.get("leituras", 0),
            "limite": info_consumo.get("limite_restante"),
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="janela").execute()
    except Exception as exc:
        print(f"[x_radar.store] falha ao registrar consumo: {exc!r}")


def listar_sinais(*, ticker: str = None, setor: str = None, autor: str = None,
                   categoria: str = None, estado: str = None, dias: int = 7,
                   limite: int = 200) -> list | None:
    """Sinais persistidos, mais recentes primeiro. None se o banco
    estiver fora do ar (distinto de [] = sem nenhum sinal no filtro)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        desde = (datetime.now(timezone.utc).timestamp() - dias * 86400)
        desde_iso = datetime.fromtimestamp(desde, tz=timezone.utc).isoformat()
        query = cliente.table(_TABELA).select("*").gte("horario_captura", desde_iso).order("horario_captura", desc=True).limit(limite)
        if ticker:
            query = query.eq("ticker", ticker.upper())
        if setor:
            query = query.eq("setor", setor)
        if autor:
            query = query.eq("autor", autor)
        if categoria:
            query = query.eq("categoria", categoria)
        if estado:
            query = query.eq("estado", estado)
        return query.execute().data
    except Exception as exc:
        print(f"[x_radar.store] listar_sinais falhou: {exc!r}")
        return None


def historico_autor(autor: str, *, excluir_post_id: str | None = None) -> list | None:
    """Sinais ANTERIORES do mesmo autor com estado final - alimenta
    relevancia.calcular_credibilidade(). None se banco fora do ar."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        query = cliente.table(_TABELA).select("post_id,estado").eq("autor", autor).in_("estado", ["confirmado", "refutado"])
        linhas = query.execute().data
        if excluir_post_id:
            linhas = [r for r in linhas if r["post_id"] != excluir_post_id]
        return linhas
    except Exception:
        return None


def saude_conector() -> dict:
    """Pra UI (painel 'saude do conector') - combina status real da
    credencial (data/x_signals.py) com o que ja esta persistido."""
    from data import x_signals
    status = x_signals.status_credencial()
    cliente = obter_cliente()
    total_sinais = None
    ultima_captura = None
    if cliente is not None:
        try:
            resp = cliente.table(_TABELA).select("horario_captura").order("horario_captura", desc=True).limit(1).execute()
            if resp.data:
                ultima_captura = resp.data[0]["horario_captura"]
            total_sinais = cliente.table(_TABELA).select("post_id", count="exact").execute().count
        except Exception:
            pass
    return {"status_credencial": status, "total_sinais": total_sinais, "ultima_captura": ultima_captura}
