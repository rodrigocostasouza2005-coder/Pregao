import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { Painel } from "@/components/Painel";
import { Tabela } from "@/components/Tabela";
import { idade } from "@/lib/formatos";
import { usuarioAtual } from "@/lib/server/auth";
import { ESTADOS_OK, painelSaude } from "@/lib/server/dominio/saude";
import { loginConfigurado, supabaseConfigurado } from "@/lib/server/env";

export const metadata = { title: "Configurações · Pregão" };

const COR: Record<string, string> = {
  SUCESSO_COM_NOVIDADE: "text-alta", SUCESSO_SEM_NOVIDADE: "text-alta", PARCIAL: "text-ambar", DADOS_DESATUALIZADOS: "text-ambar",
  FONTE_INDISPONIVEL: "text-baixa", FALHA_EXECUCAO: "text-baixa", FALHA_PERSISTENCIA: "text-baixa", NAO_COMPROVADO: "text-apagado", NUNCA_EXECUTADO: "text-apagado",
};

export default async function Configuracoes() {
  const [usuario, saude] = await Promise.all([usuarioAtual(), painelSaude()]);
  const ok = saude.linhas.filter((l) => ESTADOS_OK.has(l.estado.codigo)).length;
  return (
    <>
      <CabecalhoPagina titulo="Configurações" descricao="Conta, integrações deste ambiente e saúde dos coletores" />
      <div className="grid gap-3 lg:grid-cols-2">
        <Painel titulo="Conta">
          <dl className="grid grid-cols-[8rem_1fr] gap-y-1 text-[12.5px]">
            <dt className="text-apagado">Usuário</dt><dd>{usuario ? usuario.email : "—"}</dd>
            <dt className="text-apagado">Perfil</dt><dd>{usuario?.admin ? "Administrador" : "Usuário"}</dd>
          </dl>
        </Painel>
        <Painel titulo="Integrações deste ambiente" rodape="Só o estado de configuração - nenhum valor de credencial é exibido">
          <dl className="grid grid-cols-[10rem_1fr] gap-y-1 text-[12.5px]">
            <dt className="text-apagado">Banco (Supabase)</dt><dd className={supabaseConfigurado() ? "text-alta" : "text-ambar"}>{supabaseConfigurado() ? "Configurado" : "Não configurado"}</dd>
            <dt className="text-apagado">Login Google</dt><dd className={loginConfigurado() ? "text-alta" : "text-ambar"}>{loginConfigurado() ? "Configurado" : "Não configurado"}</dd>
          </dl>
        </Painel>
      </div>
      <Painel
        titulo="Saúde dos coletores"
        className="mt-3"
        acao={<span className="font-mono text-[11px] text-suave">{ok}/{saude.linhas.length} OK</span>}
        rodape="coletores_status · mesma classificação de data/saude_dados.py"
      >
        <EstadoDados r={saude.r} />
        <Tabela
          linhas={saude.linhas}
          chave={(l) => l.nome}
          colunas={[
            { titulo: "Coletor", celula: (l) => <span className="text-texto">{l.nome}</span> },
            { titulo: "Categoria", celula: (l) => <span className="text-apagado">{l.categoria}</span>, larga: true },
            { titulo: "Estado", celula: (l) => <span className={COR[l.estado.codigo]}>{l.estado.rotulo}</span> },
            { titulo: "Último sucesso", celula: (l) => idade(l.status?.ultimo_sucesso_em), alinhar: "dir" },
            { titulo: "Frequência", celula: (l) => <span className="text-apagado">{l.frequencia_esperada}</span>, larga: true },
            ...(usuario?.admin
              ? [{ titulo: "Último erro", celula: (l: (typeof saude.linhas)[number]) => <span className="text-[11px] text-apagado">{(l.status?.ultimo_erro || "").slice(0, 120) || "—"}</span>, larga: true }]
              : []),
          ]}
        />
      </Painel>
    </>
  );
}
