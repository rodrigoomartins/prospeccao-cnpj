import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Prospecção de Empresas de Moda", layout="wide")

@st.cache_data
def carregar_municipios():
    df = pd.read_csv("F.K03200$Z.D50307MUNIC.csv", sep=";", header=None, dtype=str)
    df.columns = ["CODIGO", "DESCRICAO"]
    df["DESCRICAO"] = df["DESCRICAO"].str.title()
    cod_para_nome = dict(zip(df["CODIGO"], df["DESCRICAO"]))
    nome_para_cod = {v: k for k, v in cod_para_nome.items()}
    return cod_para_nome, nome_para_cod

@st.cache_data
def carregar_cnaes_filtrados():
    cnaes_interesse = [
        '1340501', '1340502', '1340599', '1411801', '1411802',
        '1412601', '1412602', '1412603', '1413401', '1413402', '1413403',
        '1414200', '1422300', '2599301', '2864000', '3292201',
        '3314720', '4616800', '4642701', '4642702', '4781400', '7723300'
    ]
    df = pd.read_csv("cnaes_202504212018.csv", sep=",", header=0, dtype=str, quotechar='"')
    df.columns = ["codigo", "descricao"]
    df = df[df["codigo"].isin(cnaes_interesse)]
    df["legenda"] = df["codigo"] + " - " + df["descricao"].str.title()
    return df

@st.cache_data
def carregar_dados(codigos_municipios, cnaes, porte, termo, cnpj, socio_nome_cpf):
    df_est = pd.read_csv("tabela_estabelecimentos_ce_202504221631.csv", dtype=str)
    df_est = df_est.rename(columns=lambda x: x.strip().lower())
    df_emp = pd.read_csv("tabela_empresas_ce_202504221631.csv", dtype=str)
    df_socios = pd.read_csv("tabela_socios_ce_deduplicada_202504221745.csv", dtype=str)

    df = df_est.merge(df_emp, on="cnpj_basico", how="left")

    # Aplicação de filtros
    if codigos_municipios:
        df = df[df["municipio"].isin(codigos_municipios)]
    if cnaes:
        df = df[df["cnae_fiscal_principal"].isin(cnaes)]
    if porte:
        df = df[df["porte_empresa"].isin(porte)]
    if termo:
        termo = termo.upper()
        df = df[df["nome_fantasia"].str.upper().str.contains(termo, na=False) | df["razao_social"].str.upper().str.contains(termo, na=False)]
    if cnpj:
        df = df[df["cnpj_basico"].str.contains(cnpj)]
    if socio_nome_cpf:
        df_socios_filtrado = df_socios[df_socios["nome_socio"].str.contains(socio_nome_cpf, case=False, na=False) |
                                       df_socios["cpf_cnpj_socio"].str.contains(socio_nome_cpf, na=False)]
        cnpjs_socios = df_socios_filtrado["cnpj_basico"].unique()
        df = df[df["cnpj_basico"].isin(cnpjs_socios)]

    # Construção do CNPJ completo formatado
    if {"cnpj_basico", "cnpj_ordem", "cnpj_dv"}.issubset(df.columns):
        df["cnpj_completo"] = (
        df["cnpj_basico"].astype(str).str.zfill(8) +
        df["cnpj_ordem"].astype(str).str.zfill(4) +
        df["cnpj_dv"].astype(str).str.zfill(2)
        )
    else:
        df["cnpj_completo"] = df["cnpj_basico"].str.zfill(14)


    df["municipio_nome"] = df["municipio"].map(cod_para_nome)
    df = df.rename(columns={"municipio_nome": "Município"})

    # Remover duplicidades pelo CNPJ completo
    df = df.drop_duplicates(subset=["cnpj_completo"])

    # Trazer os sócios associados
    df_socios = df_socios[df_socios["cnpj_basico"].isin(df["cnpj_basico"])]

    return df, df_socios

# Dados auxiliares
cod_para_nome, nome_para_cod = carregar_municipios()
df_cnaes = carregar_cnaes_filtrados()

# CNAEs disponíveis
df_est_base = pd.read_csv("tabela_estabelecimentos_ce_202504221631.csv", dtype=str)
cnaes_usados = sorted(df_est_base["cnae_fiscal_principal"].dropna().unique())
df_cnaes_disponiveis = df_cnaes[df_cnaes["codigo"].isin(cnaes_usados)].copy()
df_cnaes_disponiveis["rotulo"] = df_cnaes_disponiveis["codigo"] + " - " + df_cnaes_disponiveis["descricao"]
mapa_codigo_rotulo = dict(zip(df_cnaes_disponiveis["rotulo"], df_cnaes_disponiveis["codigo"]))

# Interface
st.title("🧵 Prospecção de Empresas de Moda - Ceará")

with st.expander("🎛️ Filtros", expanded=True):
    col1, col2, col3, col4 = st.columns(4)

    # Municípios com "Todos"
    municipios_nomes = ["Todos"] + sorted(nome_para_cod.keys())
    with col1:
        municipios_nomes_selecionados = st.multiselect("Municípios", municipios_nomes,default=["Todos"], key="municipios_nomes_selecionados")
        codigos_municipios = (
            [] if "Todos" in municipios_nomes_selecionados
            else [nome_para_cod[n] for n in municipios_nomes_selecionados if n in nome_para_cod]
        )

    # CNAEs com "Todos"
    cnaes_rotulo = ["Todos"] + list(mapa_codigo_rotulo.keys())
    with col2:
        cnaes_selecionados = st.multiselect("CNAEs Principais", cnaes_rotulo, default=["Todos"], key="cnaes_selecionados")
        cnaes = (
            [] if "Todos" in cnaes_selecionados
            else [mapa_codigo_rotulo[r] for r in cnaes_selecionados if r in mapa_codigo_rotulo]
        )

    # Porte da Empresa com múltiplos
    opcoes_porte = {
        "05": "05 - Demais",
        "03": "03 - Média",
        "01": "01 - Pequena",
        "00": "00 - Não Informado"
    }
    with col3:
        porte_selecionado = st.multiselect("Porte da Empresa", ["Todos"] + list(opcoes_porte.values()), default=["Todos"],key="porte_selecionado")
        porte = [] if "Todos" in porte_selecionado else [k for k, v in opcoes_porte.items() if v in porte_selecionado]

    # Termos
    with col4:
        termo = st.text_input("🔎 Nome Fantasia ou Razão Social",key="termo")

    col5, col6 = st.columns(2)
    with col5:
        cnpj = st.text_input("🔎 CNPJ (completo ou parcial)",key="cnpj")
    with col6:
        socio_nome_cpf = st.text_input("🧍 Nome ou CPF/CNPJ do Sócio",key="socio_nome_cpf")
    
    if "municipios_nomes_selecionados" not in st.session_state:
        st.session_state["municipios_nomes_selecionados"] = ["Todos"]
    if "cnaes_selecionados" not in st.session_state:
        st.session_state["cnaes_selecionados"] = ["Todos"]
    if "porte_selecionado" not in st.session_state:
        st.session_state["porte_selecionado"] = ["Todos"]
    if "termo" not in st.session_state:
        st.session_state["termo"] = ""
    if "cnpj" not in st.session_state:
        st.session_state["cnpj"] = ""
    if "socio_nome_cpf" not in st.session_state:
        st.session_state["socio_nome_cpf"] = ""
        
    col_reset, _ = st.columns([3, 9])
    with col_reset:
        if st.button("🔄 Limpar Filtros"):
            st.session_state["municipios_nomes_selecionados"] = ["Todos"]
            st.session_state["cnaes_selecionados"] = ["Todos"]
            st.session_state["porte_selecionado"] = ["Todos"]
            st.session_state["termo"] = ""
            st.session_state["cnpj"] = ""
            st.session_state["socio_nome_cpf"] = ""
            st.rerun()

# Dados
df, df_socios = carregar_dados(codigos_municipios, cnaes, porte, termo, cnpj, socio_nome_cpf)
st.success(f"🔍 {len(df)} empresas encontradas com os filtros aplicados.")

# Exibição
df_exibicao = df.copy()
df_exibicao.insert(0, "Selecionar", False)
editado = st.data_editor(
    df_exibicao[["Selecionar", "cnpj_completo", "nome_fantasia", "razao_social", "Município"]],
    use_container_width=True,
    hide_index=True,
    key="editor_tabela"
)
selecionados = editado[editado["Selecionar"] == True]["cnpj_completo"].tolist()

# Detalhes
if not selecionados:
    st.info("Selecione uma ou mais empresas na tabela para ver os detalhes abaixo.")
else:
    for cnpj in selecionados:
        empresa = df[df["cnpj_completo"] == cnpj].iloc[0]
        socios_empresa = df_socios[df_socios["cnpj_basico"] == empresa["cnpj_basico"]]

        with st.expander(f"🔍 Detalhes: {empresa['razao_social']}", expanded=False):
            import re

            def formatar_cnpj(cnpj):
                return re.sub(r"^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$", r"\1.\2.\3/\4-\5", cnpj)

            # Estilo customizado para a área de detalhes
            st.markdown("""
            <style>
            .detalhes-card {
                background-color: #1e1e1e;
                padding: 25px;
                border-radius: 10px;
                margin-bottom: 15px;
            }
            .detalhes-coluna {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .campo-label {
                font-weight: bold;
                color: #aaa;
                font-size: 0.9em;
            }
            .campo-valor {
                font-size: 1.05em;
                margin-bottom: 5px;
            }
            .linha-flex {
                display: flex;
                gap: 40px;
                flex-wrap: wrap;
            }
            </style>
            """, unsafe_allow_html=True)

            # Layout visual da ficha da empresa
            # Ajuste da data para o formato DD/MM/AAAA
            data_inicio = empresa.get("data_inicio_atividade", "")
            data_inicio_formatada = f"{data_inicio[6:8]}/{data_inicio[4:6]}/{data_inicio[0:4]}" if pd.notna(data_inicio) and len(str(data_inicio)) == 8 else data_inicio

            st.markdown(f"""
            <div class="detalhes-card">
                <div class="linha-flex">
                    <div class="detalhes-coluna">
                        <div class="campo-label">CNPJ</div>
                        <div class="campo-valor">{formatar_cnpj(empresa['cnpj_completo'])}</div>
                        <div class="campo-label">Nome Fantasia</div>
                        <div class="campo-valor">{empresa.get('nome_fantasia') or 'Não informado'}</div>
                        <div class="campo-label">Razão Social</div>
                        <div class="campo-valor">{empresa.get('razao_social')}</div>
                        <div class="campo-label">Endereço</div>
                        <div class="campo-valor">{empresa.get('logradouro', '')}, {empresa.get('numero', '')} {empresa.get('complemento', '') or ''}, {empresa.get('bairro', '')}</div>
                        <div class="campo-label">Município</div>
                        <div class="campo-valor">{empresa.get('Município', '')} / {empresa.get('uf', '')}</div>
                        <div class="campo-label">CEP</div>
                        <div class="campo-valor">{empresa.get('cep', '')}</div>
                        <div class="campo-label">E-mail</div>
                        <div class="campo-valor">{empresa.get('email', '') or 'Não informado'}</div>
                    </div>
                    <div class="detalhes-coluna">
                        <div class="campo-label">Porte</div>
                        <div class="campo-valor">{empresa.get('porte_empresa')}</div>
                        <div class="campo-label">Matriz ou Filial</div>
                        <div class="campo-valor">{'Matriz' if empresa.get('matriz_filial') == '1' else 'Filial'}</div>
                        <div class="campo-label">Início Atividade</div>
                        <div class="campo-valor">{data_inicio_formatada}</div>
                        <div class="campo-label">Situação Cadastral</div>
                        <div class="campo-valor">{empresa.get('situacao_cadastral')}</div>
                        <div class="campo-label">CNAE Principal</div>
                        <div class="campo-valor">{empresa.get('cnae_fiscal_principal')}</div>
                        <div class="campo-label">CNAEs Secundários</div>
                        <div class="campo-valor">{empresa.get('cnae_fiscal_secundaria') or 'Não informado'}</div>
                        <div class="campo-label">Responsável Legal</div>
                        <div class="campo-valor">{empresa.get('qualificacao_responsavel')}</div>
                        <div class="campo-label">Capital Social</div>
                        <div class="campo-valor">
            """, unsafe_allow_html=True)

            # Capital com tratamento de erro
            capital_str = empresa.get('capital_social', '0').replace(',', '.')
            try:
                capital = float(capital_str)
                capital_formatado = f"R$ {capital:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except:
                capital_formatado = "Não informado"

            st.markdown(f"""
                        {capital_formatado}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Sócios permanece igual
            st.markdown("---")
            st.markdown("### 👥 Sócios")
            if not socios_empresa.empty:
                socios_empresa = socios_empresa.copy()
                socios_empresa["data_entrada_sociedade"] = socios_empresa["data_entrada_sociedade"].apply(lambda x: f"{x[6:8]}/{x[4:6]}/{x[0:4]}" if pd.notna(x) and len(str(x)) == 8 else x)
                socios_empresa = socios_empresa.rename(columns={
                    "nome_socio": "Nome",
                    "cpf_cnpj_socio": "CPF/CNPJ",
                    "qualificacao_socio": "Qualificação",
                    "data_entrada_sociedade": "Entrada",
                    "faixa_etaria": "Faixa Etária"
                })
                st.dataframe(socios_empresa[["Nome", "CPF/CNPJ", "Qualificação", "Entrada", "Faixa Etária"]], use_container_width=True, hide_index=True)
            else:
                st.markdown("🔕 Nenhum sócio cadastrado.")



# Exportação
st.download_button("⬇️ Baixar resultados em CSV", df.to_csv(index=False).encode("utf-8"), "empresas_filtradas.csv", "text/csv")

# Gráfico
if not df.empty:
    fig = px.histogram(df, x="Município", title="Distribuição por Município", color_discrete_sequence=["indigo"])
    st.plotly_chart(fig, use_container_width=True)
