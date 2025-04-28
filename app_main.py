import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit_authenticator as stauth
import os
from dotenv import load_dotenv
import yaml
import copy
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Prospecção de Empresas de Moda", layout="wide")

# # Carregando usuários do st.secrets
# credentials = {
#     "usernames": {
#         st.secrets["USERNAME1"]: {
#             "email": st.secrets["EMAIL1"],
#             "name": st.secrets["USERNAME1"],  # ou um nome separado, se quiser criar
#             "password": st.secrets["PASSWORD1"],
#         },
#         st.secrets["USERNAME2"]: {
#             "email": st.secrets["EMAIL2"],
#             "name": st.secrets["USERNAME2"],
#             "password": st.secrets["PASSWORD2"],
#         },
#         st.secrets["USERNAME3"]: {
#             "email": st.secrets["EMAIL3"],
#             "name": st.secrets["USERNAME3"],
#             "password": st.secrets["PASSWORD3"],
#         },
#     }
# }

# # Inicializa o Authenticator
# authenticator = stauth.Authenticate(
#     credentials,
#     cookie_name="prospeccao_app",
#     key="abcdef",
#     cookie_expiry_days=1,
# )

# # Exibe login
# authenticator.login(location="main")

# # Avalia status da sessão
# if st.session_state.get("authentication_status") is True:
#     authenticator.logout("Sair", location="sidebar")
#     st.sidebar.success(f"Bem-vindo(a), {st.session_state.get('name')}")
# elif st.session_state.get("authentication_status") is False:
#     st.error("Usuário ou senha incorretos.")
#     st.stop()
# elif st.session_state.get("authentication_status") is None:
#     st.warning("Por favor, preencha seu login.")
#     st.stop()

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
def carregar_marcadores():
    df_tags = pd.read_csv("marcadores_extraidos.csv")
    df_tags.columns = [col.strip() for col in df_tags.columns]
    mapa_tags = dict(zip(df_tags["name"], df_tags["id"]))  # Agora usando o nome e id corretos
    return mapa_tags

mapa_marcadores = carregar_marcadores()


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

import pandas as pd
import os

def carregar_envios_odoo():
    if os.path.exists('envios_odoo.csv'):
        return pd.read_csv('envios_odoo.csv', dtype=str)
    else:
        return pd.DataFrame(columns=['cnpj_completo', 'data_hora_envio', 'vendedor_nome', 'marcadores'])

from datetime import datetime

def registrar_envio_odoo(cnpj, vendedor_nome, marcadores):
    df_envios = carregar_envios_odoo()
    novo_envio = {
        'cnpj_completo': cnpj,
        'data_hora_envio': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'vendedor_nome': vendedor_nome,
        'marcadores': ";".join(marcadores)
    }
    df_envios = pd.concat([df_envios, pd.DataFrame([novo_envio])], ignore_index=True)
    df_envios.to_csv('envios_odoo.csv', index=False)



# Função para exibir o histograma dos preços
def exibir_distribuicao_precos(precos):
    st.subheader("📈 Distribuição dos Preços Coletados")

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.hist(precos, bins=30, color="skyblue", edgecolor="black", alpha=0.7)
    ax.axvline(np.mean(precos), color="red", linestyle="dashed", linewidth=2, label=f"Média: R$ {np.mean(precos):.2f}")
    ax.axvline(np.min(precos), color="green", linestyle="dotted", linewidth=2, label=f"Mínimo: R$ {np.min(precos):.2f}")
    ax.axvline(np.max(precos), color="purple", linestyle="dotted", linewidth=2, label=f"Máximo: R$ {np.max(precos):.2f}")

    ax.set_xlabel("Faixa de Preço (R$)")
    ax.set_ylabel("Quantidade de Produtos")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)

    st.pyplot(fig)

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
        
    # col_reset, _ = st.columns([3, 9])
    # with col_reset:
    #     if st.button("🔄 Limpar Filtros"):
    #         st.query_params.clear()
    #         st.markdown("""<meta http-equiv="refresh" content="0">""", unsafe_allow_html=True)

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
    for i, cnpj in enumerate(selecionados):

        empresa = df[df["cnpj_completo"] == cnpj].iloc[0]
        socios_empresa = df_socios[df_socios["cnpj_basico"] == empresa["cnpj_basico"]]

        with st.expander(f"🔍 Detalhes: {empresa['razao_social']}", expanded=False):
            # Formatação do CNPJ
            import re
            def formatar_cnpj(cnpj):
                return re.sub(r"^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$", r"\1.\2.\3/\4-\5", cnpj)

            # Formatação de capital
            capital_str = empresa.get('capital_social', '0').replace(',', '.')
            try:
                capital = float(capital_str)
                capital_formatado = f"R$ {capital:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except:
                capital_formatado = "Não informado"

            # Formatação da data
            data_inicio = empresa.get("data_inicio_atividade", "")
            data_inicio_formatada = f"{data_inicio[6:8]}/{data_inicio[4:6]}/{data_inicio[0:4]}" if pd.notna(data_inicio) and len(str(data_inicio)) == 8 else data_inicio
            
            # # Estilo visual
            # st.markdown("""
            # <style>
            # .detalhes-card {
            #     background-color: #f9f9f9;
            #     padding: 15px;
            #     border-radius: 10px;
            #     margin-bottom: 10px;
            #     width: 100%;
            # }
            # .linha-flex {
            #     display: flex;
            #     flex-wrap: wrap;
            #     gap: 20px;
            #     justify-content: flex-start;
            # }
            # .detalhes-coluna {
            #     flex: 1 1 250px;
            #     max-width: 400px;
            #     background-color: #ffffff;
            #     border: 1px solid #ccc;
            #     border-radius: 8px;
            #     padding: 8px 10px;
            #     box-shadow: 1px 1px 4px rgba(0,0,0,0.05);
            #     word-break: break-word;
            # }
            # .campo-label {
            #     font-weight: 600;
            #     color: #333;
            #     font-size: 0.8em;
            #     margin-bottom: 2px;
            # }
            # .campo-valor {
            #     font-size: 0.95em;
            #     color: #000;
            # }
            # .cnae-principal, .cnae-secundarios {
            #     background-color: #f2f2f2;
            #     padding: 12px;
            #     border-radius: 8px;
            #     margin-top: 10px;
            # }
            # .cnae-principal h5, .cnae-secundarios h5 {
            #     margin: 0 0 8px 0;
            #     font-size: 1em;
            #     color: #333;
            # }
            # .cnae-item {
            #     font-size: 0.9em;
            #     margin-bottom: 5px;
            # }
            # </style>
            # """, unsafe_allow_html=True)

            # # HTML renderizado corretamente (unificado)
            # st.markdown(f"""
            # <div class="detalhes-card">
            #     <div class="linha-flex">
            #         <div class="detalhes-coluna">
            #             <div class="campo-label">CNPJ</div>
            #             <div class="campo-valor">{formatar_cnpj(empresa['cnpj_completo'])}</div>
            #             <div class="campo-label">Nome Fantasia</div>
            #             <div class="campo-valor">{empresa.get('nome_fantasia') or 'Não informado'}</div>
            #             <div class="campo-label">Razão Social</div>
            #             <div class="campo-valor">{empresa.get('razao_social')}</div>
            #             <div class="campo-label">Endereço</div>
            #             <div class="campo-valor">{empresa.get('logradouro', '')}, {empresa.get('numero', '')} {empresa.get('complemento', '') or ''}, {empresa.get('bairro', '')}</div>
            #             <div class="campo-label">Município</div>
            #             <div class="campo-valor">{empresa.get('Município', '')} / {empresa.get('uf', '')}</div>
            #             <div class="campo-label">CEP</div>
            #             <div class="campo-valor">{empresa.get('cep', '')}</div>
            #             <div class="campo-label">E-mail</div>
            #             <div class="campo-valor">{empresa.get('email', '') or 'Não informado'}</div>
            #             <div class="campo-label">Telefone(s)</div>
            #             <div class="campo-valor">
            #                 ({str(empresa.get('ddd1', '')).split('.')[0]}) {str(empresa.get('telefone1', '')).split('.')[0]}
            #                 {(' | (' + str(empresa.get('ddd2', '')).split('.')[0] + ') ' + str(empresa.get('telefone2', '')).split('.')[0]) if empresa.get('telefone2') else ''}
            #             </div>
            #         </div>
            #         <div class="detalhes-coluna">
            #             <div class="campo-label">Capital Social</div>
            #             <div class="campo-valor">{capital_formatado}</div>
            #             <div class="campo-label">Porte</div>
            #             <div class="campo-valor">{empresa.get('porte_empresa')}</div>
            #             <div class="campo-label">Matriz ou Filial</div>
            #             <div class="campo-valor">{'Matriz' if empresa.get('matriz_filial') == '1' else 'Filial'}</div>
            #             <div class="campo-label">Início Atividade</div>
            #             <div class="campo-valor">{data_inicio_formatada}</div>
            #             <div class="campo-label">Situação Cadastral</div>
            #             <div class="campo-valor">{empresa.get('situacao_cadastral')}</div>
            #             <div class="campo-label">CNAE Principal</div>
            #             <div class="campo-valor">{empresa.get('cnae_fiscal_principal')}</div>
            #             <div class="campo-label">CNAEs Secundários</div>
            #             <div class="campo-valor">{empresa.get('cnae_fiscal_secundaria') or 'Não informado'}</div>
            #             <div class="campo-label">Responsável Legal</div>
            #             <div class="campo-valor">{empresa.get('qualificacao_responsavel')}</div>
            #         </div>
            #         <dib class="detalhes-coluna">
            #             <div class="campo-label">Natureza Jurídica</div>
            #             <div class="campo-valor">{empresa.get('natureza_juridica', '')}</div>
            #             <div class="campo-label">Data da Situação Cadastral</div>
            #             <div class="campo-valor">{empresa.get('data_situacao_cadastral', '')}</div>
            #             <div class="campo-label">Motivo Situação Cadastral</div>
            #             <div class="campo-valor">{empresa.get('motivo_situacao_cadastral', '') or 'Não informado'}</div>
            #             <div class="campo-label">Ente Federativo Responsável</div>
            #             <div class="campo-valor">{empresa.get('ente_federativo_responsavel', '') or 'Não informado'}</div>
            #             <div class="campo-label">Situação Especial</div>
            #             <div class="campo-valor">{empresa.get('situacao_especial', '') or 'Não informado'}</div>
            #             <div class="campo-label">Data Situação Especial</div>
            #             <div class="campo-valor">{empresa.get('data_situacao_especial', '') or 'Não informado'}</div>
            #         </dib>
            #     </div>
            # </div>
            # """, unsafe_allow_html=True)
            
            # Modelo de exibição estilo Receita Federal
            def exibir_comprovante_formatado(empresa):
                # Dados
                cnpj = empresa.get('cnpj_completo', '')
                razao_social = empresa.get('razao_social', '')
                nome_fantasia = empresa.get('nome_fantasia', 'Não informado')
                capital_social = empresa.get('capital_social', 'Não informado')
                porte = empresa.get('porte_empresa', 'Não informado')
                natureza_juridica = empresa.get('natureza_juridica', 'Não informado')
                situacao_cadastral = empresa.get('situacao_cadastral', 'Não informado')
                data_abertura = empresa.get('data_inicio_atividade', '')
                logradouro = empresa.get('logradouro', '')
                numero = empresa.get('numero', '')
                complemento = empresa.get('complemento', '')
                bairro = empresa.get('bairro', '')
                municipio = empresa.get('Município', '')
                uf = empresa.get('uf', '')
                cep = empresa.get('cep', '')
                email = empresa.get('email', '')
                telefone = empresa.get('telefone1', '')
                ddd = empresa.get('ddd1', '')
                # CNAE Principal
                # Função para buscar a descrição do CNAE
                # Função para buscar a descrição correta do CNAE
                df_cnaes2 = pd.read_csv('cnaes_202504212018.csv', sep=",", quotechar='"', header=None, names=["codigo", "descricao"])
                # Criar uma nova coluna sem pontuação
                df_cnaes2["codigo_normalizado"] = df_cnaes2["codigo"].str.replace(".", "", regex=False).str.replace("-", "", regex=False)
                
                def buscar_descricao_cnae(codigo):
                    codigo = str(codigo).zfill(7)  # Garante que o código tenha 7 dígitos
                    descricao = df_cnaes2[df_cnaes2["codigo_normalizado"] == codigo]["descricao"]
                    if not descricao.empty:
                        return descricao.values[0]
                    return "Descrição não encontrada"

                cnae_principal_codigo = str(empresa.get('cnae_fiscal_principal', '')).split('.')[0]
                descricao_principal = buscar_descricao_cnae(cnae_principal_codigo)

                # CNAEs Secundários
                cnaes_secundarios_raw = empresa.get('cnae_fiscal_secundaria', '')
                cnaes_secundarios_codigos = []
                if isinstance(cnaes_secundarios_raw, str) and cnaes_secundarios_raw:
                    cnaes_secundarios_codigos = [c.strip() for c in cnaes_secundarios_raw.split(",") if c.strip()]

                cnaes_secundarios_descritos = []
                for codigo in cnaes_secundarios_codigos:
                    descricao = buscar_descricao_cnae(codigo)
                    cnaes_secundarios_descritos.append(f"{codigo} - {descricao}")
                
                # Estilos CSS
                st.markdown("""
                <style>
                .comprovante-container {
                    background-color: #ffffff;
                    border: 1px solid #ccc;
                    padding: 15px;
                    border-radius: 8px;
                    font-family: Arial, sans-serif;
                    font-size: 13px;
                }
                .linha-formulario {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 12px;
                    margin-bottom: 10px;
                }
                .campo-formulario {
                    flex: 1 1 240px;
                    background-color: #f9f9f9;
                    padding: 8px 10px;
                    border: 1px solid #bbb;
                    border-radius: 5px;
                    min-width: 220px;
                }
                .titulo-campo {
                    font-weight: bold;
                    color: #333;
                    font-size: 12px;
                    margin-bottom: 2px;
                }
                .valor-campo {
                    font-size: 13px;
                    color: #000;
                }
                .cnae-card {
                    margin-top: 10px;
                    padding: 10px;
                    border: 1px solid #bbb;
                    border-radius: 5px;
                }
                .cnae-title {
                    font-weight: bold;
                    font-size: 13px;
                    margin-bottom: 6px;
                    color: #333;
                }
                .cnae-item {
                    font-size: 12px;
                    margin-bottom: 4px;
                    color: #444;
                }
                hr {
                    border: none;
                    border-top: 1px solid #bbb;
                    margin: 15px 0;
                }
                </style>
                """, unsafe_allow_html=True)

                # HTML renderizado - tudo num único bloco (compacto e organizado)
                st.markdown(f"""
                <div class="comprovante-container">
                    <div class="linha-formulario">
                        <div class="campo-formulario">
                            <div class="titulo-campo">CNPJ</div>
                            <div class="valor-campo">{cnpj}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">Data de Abertura</div>
                            <div class="valor-campo">{data_abertura}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">Situação Cadastral</div>
                            <div class="valor-campo">{situacao_cadastral}</div>
                        </div>
                    </div>
                    <div class="linha-formulario">
                        <div class="campo-formulario">
                            <div class="titulo-campo">Nome Empresarial</div>
                            <div class="valor-campo">{razao_social}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">Nome Fantasia</div>
                            <div class="valor-campo">{nome_fantasia}</div>
                        </div>
                    </div>
                    <div class="linha-formulario">
                        <div class="campo-formulario">
                            <div class="titulo-campo">Capital Social</div>
                            <div class="valor-campo">R$ {capital_social}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">Porte</div>
                            <div class="valor-campo">{porte}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">Natureza Jurídica</div>
                            <div class="valor-campo">{natureza_juridica}</div>
                        </div>
                    </div>
                    <div class="cnae-card">
                        <div class="cnae-title">Código e Descrição da Atividade Econômica Principal</div>
                        <div class="cnae-item">{cnae_principal_codigo} - {descricao_principal}</div>
                    </div>
                    <div class="cnae-card">
                        <div class="cnae-title">Código e Descrição das Atividades Econômicas Secundárias</div>
                        {''.join(f'<div class="cnae-item">{item}</div>' for item in cnaes_secundarios_descritos) if cnaes_secundarios_descritos else '<div class="cnae-item">Nenhum CNAE secundário informado.</div>'}
                    </div>
                    <hr>
                    <div class="linha-formulario">
                        <div class="campo-formulario">
                            <div class="titulo-campo">Endereço</div>
                            <div class="valor-campo">{logradouro}, {numero} {complemento} - {bairro}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">Município/UF</div>
                            <div class="valor-campo">{municipio} / {uf}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">CEP</div>
                            <div class="valor-campo">{cep}</div>
                        </div>
                    </div>
                    <div class="linha-formulario">
                        <div class="campo-formulario">
                            <div class="titulo-campo">E-mail</div>
                            <div class="valor-campo">{email}</div>
                        </div>
                        <div class="campo-formulario">
                            <div class="titulo-campo">Telefone</div>
                            <div class="valor-campo">({ddd}) {telefone}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)


            col1_form, col2_form = st.columns([3,2])
            with col1_form:
                exibir_comprovante_formatado(empresa)
                import math

                # Função para limpar valores nulos ou 'nan'
                def limpar_valor(valor):
                    if not valor or (isinstance(valor, float) and math.isnan(valor)) or str(valor).lower() == "nan":
                        return ""
                    return str(valor)

                # Coletar e limpar os dados
                nome_fantasia = limpar_valor(empresa.get("nome_fantasia", ""))
                razao_social = limpar_valor(empresa.get("razao_social", ""))
                cidade = limpar_valor(empresa.get("Município", ""))
                logradouro = limpar_valor(empresa.get("logradouro", ""))
                numero = limpar_valor(empresa.get("numero", ""))
                bairro = limpar_valor(empresa.get("bairro", ""))
                uf = limpar_valor(empresa.get("uf", ""))

                # Construir endereço para Google Maps
                endereco_google = f"{logradouro}, {numero} {bairro}, {cidade} - {uf}".strip().replace(" ", "+")
                url_maps = f"https://www.google.com/maps/search/?api=1&query={endereco_google}"

                # Construir pesquisa para Google
                query_google = f"{razao_social} {nome_fantasia} {cidade}".strip().replace(" ", "+")
                url_google = f"https://www.google.com/search?q={query_google}"

                # Evitar termo vazio
                termo_busca = None

                if nome_fantasia and nome_fantasia.strip():
                    termo_busca = nome_fantasia.strip()
                elif razao_social and razao_social.strip():
                    termo_busca = razao_social.strip()
                elif cidade and cidade.strip():
                    termo_busca = cidade.strip()

                if termo_busca:
                    query_insta = termo_busca.replace(" ", "+")
                    url_insta = f"https://www.google.com/search?q=site:instagram.com+{query_insta}"
                else:
                    url_insta = "https://www.instagram.com"  # Se não tiver NADA, manda pro Instagram principal

                st.markdown(f"""
                    <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px;">
                        <a href="{url_maps}" target="_blank"
                        style='text-decoration: none; background-color: #34A853; color: white; padding: 10px 20px; border-radius: 6px;
                            font-weight: 600; font-size: 14px; display: inline-block;'>
                            📍 Ver no Google Maps
                        </a>
                        <a href="{url_google}" target="_blank"
                        style='text-decoration: none; background-color: #4285F4; color: white; padding: 10px 20px; border-radius: 6px;
                            font-weight: 600; font-size: 14px; display: inline-block;'>
                            🔎 Pesquisar no Google
                        </a>
                        <a href="{url_insta}" target="_blank"
                        style='text-decoration: none; background-color: #833AB4; color: white; padding: 10px 20px; border-radius: 6px;
                            font-weight: 600; font-size: 14px; display: inline-block;'>
                            📸 Buscar no Instagram
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
            st.divider()
            # st.divider()
            # # Preparar dados para a tabela
            # dados_empresa = {
            #     "Campo": [
            #         "CNPJ",
            #         "Nome Fantasia",
            #         "Razão Social",
            #         "Endereço",
            #         "Município/UF",
            #         "CEP",
            #         "E-mail",
            #         "Telefone(s)",
            #         "Capital Social",
            #         "Porte",
            #         "Matriz ou Filial",
            #         "Início Atividade",
            #         "Situação Cadastral",
            #         "CNAE Principal",
            #         "CNAEs Secundários",
            #         "Responsável Legal",
            #         "Natureza Jurídica",
            #         "Data da Situação Cadastral",
            #         "Motivo Situação Cadastral",
            #         "Ente Federativo Responsável",
            #         "Situação Especial",
            #         "Data Situação Especial",
            #     ],
            #     "Valor": [
            #         formatar_cnpj(empresa.get('cnpj_completo', '')),
            #         empresa.get('nome_fantasia') or 'Não informado',
            #         empresa.get('razao_social') or 'Não informado',
            #         f"{empresa.get('logradouro', '')}, {empresa.get('numero', '')} {empresa.get('complemento', '') or ''}, {empresa.get('bairro', '')}",
            #         f"{empresa.get('Município', '')} / {empresa.get('uf', '')}",
            #         empresa.get('cep', '') or 'Não informado',
            #         empresa.get('email', '') or 'Não informado',
            #         f"({str(empresa.get('ddd1', '')).split('.')[0]}) {str(empresa.get('telefone1', '')).split('.')[0]}" +
            #         (f" | ({str(empresa.get('ddd2', '')).split('.')[0]}) {str(empresa.get('telefone2', '')).split('.')[0]}" if empresa.get('telefone2') else ''),
            #         capital_formatado,
            #         empresa.get('porte_empresa', ''),
            #         'Matriz' if empresa.get('matriz_filial') == '1' else 'Filial',
            #         data_inicio_formatada,
            #         empresa.get('situacao_cadastral', ''),
            #         empresa.get('cnae_fiscal_principal', ''),
            #         empresa.get('cnae_fiscal_secundaria', '') or 'Não informado',
            #         empresa.get('qualificacao_responsavel', ''),
            #         empresa.get('natureza_juridica', ''),
            #         empresa.get('data_situacao_cadastral', ''),
            #         empresa.get('motivo_situacao_cadastral', '') or 'Não informado',
            #         empresa.get('ente_federativo_responsavel', '') or 'Não informado',
            #         empresa.get('situacao_especial', '') or 'Não informado',
            #         empresa.get('data_situacao_especial', '') or 'Não informado',
            #     ]
            # }

            # Criar dataframe
            # df_detalhes_empresa = pd.DataFrame(dados_empresa)

            # Exibir no Streamlit
            # st.dataframe(df_detalhes_empresa, use_container_width=True)
            col1_conteudo, col2_acoes = st.columns(2)
            with col2_form:
                from odoo import enviar_para_odoo
                usuarios_odoo = {
                    'marcia@voturfid.com.br': 6,
                    'rodrigo@voturfid.com.br': 7,
                    'Edmilson Moreira': 2,
                    "Sem Vendedor Atribuído": False
                }
                # --- Novo expander para envio ao CRM ---
                st.markdown("### 📤 Enviar para o Odoo CRM")
            
                # Selecionar o vendedor
                usuario_selecionado = st.selectbox(
                    "👤 Atribuir a oportunidade para:",
                    list(usuarios_odoo.keys()),
                    index=0,
                    key=f"usuario_atribuicao_{empresa['cnpj_completo']}_{i}"
                )

                # Selecionar marcadores
                tags_selecionados = st.multiselect(
                    "🏷️ Selecione os Marcadores para essa oportunidade:",
                    options=list(mapa_marcadores.keys()),
                    key=f"marcadores_oportunidade_{empresa['cnpj_completo']}_{i}"
                )

                df_envios = carregar_envios_odoo()
                cnpj_ja_enviado = cnpj in df_envios['cnpj_completo'].values

                if cnpj_ja_enviado:
                    envio = df_envios[df_envios['cnpj_completo'] == cnpj].iloc[0]
                    st.warning(f"🚀 Este CNPJ já foi enviado ao Odoo em {envio['data_hora_envio']} para {envio['vendedor_nome']}.")
                    st.info(f"🏷️ Marcadores usados: {envio['marcadores']}")
                else:
                    if st.button(f"✅ Confirmar envio ao Odoo CRM", key=f"botao_envio_{empresa['cnpj_completo']}_{i}"):
                        sucesso = enviar_para_odoo(
                            empresa,
                            usuarios_odoo[usuario_selecionado],
                            tags_selecionados,
                            mapa_marcadores
                        )
                        if sucesso:
                            registrar_envio_odoo(
                                empresa['cnpj_completo'],
                                usuario_selecionado,
                                tags_selecionados
                            )
                            st.success("Oportunidade enviada e registrada com sucesso!")
                st.divider()
                from analisar_perfil_empresa import *
                st.subheader("🔖 Análise Comercial da Empresa")
                cnpj_atual = empresa.get("cnpj_completo", "")
                razao_social_atual = empresa.get("razao_social", "")
                url_site_empresa = empresa.get("site", "")

                df_analises = carregar_analises()
                analise_anterior = df_analises[df_analises["cnpj"] == cnpj_atual]

                if not analise_anterior.empty:
                    st.success("Análise anterior encontrada:")
                    st.write(f"**Site:** [{analise_anterior.iloc[0]['url_site']}]({analise_anterior.iloc[0]['url_site']})")
                    st.write(f"**Perfil:** {analise_anterior.iloc[0]['perfil']}")
                    st.write(f"**Termos detectados:** {analise_anterior.iloc[0]['termos_detectados']}")
                    st.write(f"**Quantidade de Preços:** {analise_anterior.iloc[0]['quantidade_precos']}")
                    st.write(f"**Preço Mínimo:** R$ {analise_anterior.iloc[0]['preco_minimo']}".replace(".",","))
                    st.write(f"**Preço Máximo:** R$ {analise_anterior.iloc[0]['preco_maximo']}".replace(".",","))
                    st.write(f"**Preço Médio:** R$ {analise_anterior.iloc[0]['preco_medio']}".replace(".",","))
                    try:
                        precos_str = analise_anterior.iloc[0]["precos"]
                        if precos_str:
                            precos = json.loads(precos_str)
                            if isinstance(precos, list) and precos:
                                exibir_distribuicao_precos(precos)
                    except Exception as e:
                        st.warning(f"Erro ao carregar preços para gráfico: {e}")

                url_nova_analise = st.text_input("Informe a URL do site para nova análise:", value=url_site_empresa)

                if st.button("🔄 Reanalisar Perfil e Preços"):
                    with st.spinner("Analisando site, por favor aguarde..."):
                        try:
                            resultado_perfil = analisar_perfil_empresa(url_nova_analise)
                            resultado_precos = analisar_precos(url_nova_analise)

                            salvar_analise_comercial(
                                cnpj=cnpj_atual,
                                razao_social=razao_social_atual,
                                url_site=url_nova_analise,
                                perfil=resultado_perfil["perfil"],
                                termos_detectados=resultado_perfil["termos_detectados"],
                                resultado_precos=resultado_precos
                            )

                            st.success("Análise atualizada!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro durante a análise: {e}")
            # Exibe dados de sócios, se existirem
            # Exibe dados de sócios, se existirem
            if not socios_empresa.empty:
                st.markdown("### 👥 Sócios da Empresa")
                try:
                    # Trata possíveis colunas
                    colunas_validas = [col for col in ["nome_socio", "qualificacao_socio", "pais_origem", "tipo_socio"] if col in socios_empresa.columns]
                    df_exibir_socios = socios_empresa[colunas_validas].copy()

                    # Renomeia para exibição
                    renomear_colunas = {
                        "nome_socio": "Nome do Sócio",
                        "qualificacao_socio": "Qualificação",
                        "pais_origem": "País de Origem",
                        "tipo_socio": "Tipo"
                    }
                    df_exibir_socios = df_exibir_socios.rename(columns=renomear_colunas)

                    # Exibe no Streamlit
                    st.dataframe(df_exibir_socios, use_container_width=True)

                except Exception as e:
                    st.warning(f"⚠️ Erro ao carregar dados de sócios: {e}")

# Exportação
st.download_button("⬇️ Baixar resultados em CSV", df.to_csv(index=False).encode("utf-8"), "empresas_filtradas.csv", "text/csv")
st.divider()
col1_grafico, col2_heatmap = st.columns(2)
with col1_grafico:
    # Gráfico
    st.markdown("### Distribuição por Município")
    if not df.empty:
        fig = px.histogram(df, x="Município", color_discrete_sequence=["indigo"])
        st.plotly_chart(fig, use_container_width=True)

from streamlit_folium import st_folium
import folium
from folium.plugins import HeatMap

@st.cache_data
def carregar_municipios_latlon():
    df_latlon = pd.read_csv('municipios_ce_latlon.csv', sep=';', dtype=str)
    df_latlon['latitude'] = df_latlon['latitude'].astype(float)
    df_latlon['longitude'] = df_latlon['longitude'].astype(float)
    return df_latlon

@st.cache_data
def preparar_dados_heatmap(df, df_latlon):
    if df.empty:
        return []

    # Contar empresas por município
    empresas_por_municipio = df['Município'].value_counts().reset_index()
    empresas_por_municipio.columns = ['Município', 'Quantidade']

    # Juntar latitude/longitude
    mapa_empresas = empresas_por_municipio.merge(df_latlon, on='Município', how='left')

    # Gerar lista de pontos
    heat_data = [
        [row['latitude'], row['longitude'], row['Quantidade']] 
        for idx, row in mapa_empresas.iterrows()
        if not pd.isna(row['latitude']) and not pd.isna(row['longitude'])
    ]

    return heat_data

def criar_mapa_heatmap(heat_data):
    # Posição inicial focada no Ceará
    mapa = folium.Map(location=[-5.2, -39.0], zoom_start=7, control_scale=True)

    if heat_data:
        HeatMap(
            heat_data, 
            radius=15, 
            blur=12, 
            max_zoom=10,
            min_opacity=0.4
        ).add_to(mapa)

    return mapa

# --- Exibir Heatmap ---
with col2_heatmap:
    st.markdown("### Mapa de Calor de Empresas")

    df_latlon = carregar_municipios_latlon()
    heat_data = preparar_dados_heatmap(df, df_latlon)

    if heat_data:
        mapa = criar_mapa_heatmap(heat_data)
        st_folium(mapa, use_container_width=True, height=600)
    else:
        st.warning("Nenhuma empresa encontrada para gerar o mapa.")