import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
from datetime import datetime
import altair as alt


## ================================
# CONFIG
# ================================
st.set_page_config(page_title="Gestão Financeira Master", layout="wide")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1VyFBo9qeKQOjdTtvtuQjsVBQGQ54Yh0iYVkaH-iG4wM/edit"

conn = st.connection("gsheets", type=GSheetsConnection)


# ================================
# SESSION STATE (SALDOS)
# ================================
if "caixa" not in st.session_state:
    st.session_state.caixa = 0.0

if "bradesco" not in st.session_state:
    st.session_state.bradesco = 0.0

if "brasil" not in st.session_state:
    st.session_state.brasil = 0.0

# ================================
# CARREGAR ÚLTIMO SALDO
# ================================
if "carregado" not in st.session_state:
    try:
        df_saldos = conn.read(spreadsheet=URL_PLANILHA, worksheet="Saldos")

        if not df_saldos.empty:
            ultimo = df_saldos.iloc[-1]

            st.session_state.caixa = float(ultimo["Caixa"])
            st.session_state.bradesco = float(ultimo["Bradesco"])
            st.session_state.brasil = float(ultimo["Banco do Brasil"])

    except:
        pass

    st.session_state.carregado = True

# ================================
# SIDEBAR
# ================================
st.sidebar.header("🏦 Saldos Bancários e Filtros")

with st.sidebar.expander("Saldos em Conta", expanded=True):

    caixa = st.number_input("Saldo Caixa R$:", step=100.0, format="%.2f", key="caixa")

    bradesco = st.number_input(
        "Saldo Bradesco R$:", step=100.0, format="%.2f", key="bradesco"
    )

    brasil = st.number_input(
        "Saldo Banco do Brasil R$:", step=100.0, format="%.2f", key="brasil"
    )

    saldo_inicial = caixa + bradesco + brasil

    # BOTÃO SALVAR
    if st.button("💾 Salvar Saldos"):

        df_saldo = pd.DataFrame([{
           "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
           "Caixa": caixa,
           "Bradesco": bradesco,
           "Banco do Brasil": brasil,
        }])

        try:
            df_existente = conn.read(spreadsheet=URL_PLANILHA, worksheet="Saldos")
        except:
               df_existente = pd.DataFrame(columns=["Data", "Caixa", "Bradesco", "Banco do Brasil"])

        df_novo = pd.concat([df_existente, df_saldo], ignore_index=True)

        conn.update(
            spreadsheet=URL_PLANILHA,
            worksheet="Saldos",
            data=df_novo
        )

        st.success("✅ Saldos salvos com sucesso!")

st.sidebar.markdown("---")


# Seleção de Mês e Ano

mes_atual = datetime.now().month

ano_atual = datetime.now().year

mes_sel = st.sidebar.selectbox(
    "Mês da Projeção:", list(range(1, 13)), index=mes_atual - 1
)

ano_sel = st.sidebar.number_input("Ano:", value=ano_atual)


# SELEÇÃO DE CENÁRIO

cenario = st.sidebar.radio(
    "Escolha o Cenário de Receita:",
    ("Cenário 1 (Normal)", "Cenário 2 (GEAP -50%)", "Cenário 3 (GEAP ZERADA)"),
)


# --- CARREGAMENTO E LIMPEZA ---

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1VyFBo9qeKQOjdTtvtuQjsVBQGQ54Yh0iYVkaH-iG4wM/edit"

ABA_DADOS = "Planejamento Financeiro Mensal"
ABA_SALDOS = "Saldos"

try:

    conn = st.connection("gsheets", type=GSheetsConnection)

    # 🔥 LÊ SOMENTE A ABA CORRETA (EVITA PEGAR SALDOS)
    df = conn.read(
        spreadsheet=URL_PLANILHA,
        worksheet=ABA_DADOS,
        header=0,
        ttl=0
    )


    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace("\n", "", regex=False)
        .str.replace("\r", "", regex=False)
    )

    def limpar_valor(v):

        if isinstance(v, str):

            v = v.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")

            return v

        return v

    df["valor_final"] = pd.to_numeric(
        df["Valor"].apply(limpar_valor), errors="coerce"
    ).fillna(0)

    # ================================
    # LIMPEZA E PADRÃO BRASILEIRO
    # ================================

    # Remove linhas totalmente vazias
    df = df.dropna(how="all")

    # Converte datas no padrão brasileiro (DD/MM/AAAA)
    df["Data Lançamento"] = pd.to_datetime(
        df["Data Lançamento"],
        dayfirst=True,   # 🔥 ESSENCIAL
        errors="coerce"
    )

    df["Data de Pagamento"] = pd.to_datetime(
        df["Data de Pagamento"],
        dayfirst=True,   # 🔥 ESSENCIAL
        errors="coerce"
    )

    # Garante que colunas de texto não quebrem
    df["Classificação"] = df["Classificação"].fillna("")
    df["Itens"] = df["Itens"].fillna("")
    df["Plano de Contas"] = df["Plano de Contas"].fillna("")

    # Filtragem Base

    df_mes = df[
        (df["Data Lançamento"].dt.month == mes_sel)
        & (df["Data Lançamento"].dt.year == ano_sel)
    ].copy()

    # --- LÓGICA DE CENÁRIOS ---

    # --- LÓGICA DE CENÁRIOS ---
    mask_geap = (df_mes["Classificação"].str.lower().str.contains("receita")) & (
        df_mes["Itens"].str.upper().str.contains("GEAP")
    )

    # Identifica a despesa do Anestesista
    mask_anestesista = (df_mes["Itens"].str.upper().str.contains("ANESTESISTA")) | (
        df_mes["Plano de Contas"].str.upper().str.contains("ANESTESISTA")
    )

    valor_geap_cortado = 0

    if cenario == "Cenário 2 (GEAP -50%)":
        valor_geap_cortado = df_mes.loc[mask_geap, "valor_final"].sum() * 0.5
        df_mes.loc[mask_geap, "valor_final"] *= 0.5
        # Reduz Anestesista para 70%
        df_mes.loc[mask_anestesista, "valor_final"] *= 0.70

    elif cenario == "Cenário 3 (GEAP ZERADA)":
        valor_geap_cortado = df_mes.loc[mask_geap, "valor_final"].sum()
        df_mes.loc[mask_geap, "valor_final"] = 0.0
        # Reduz Anestesista para 50%
        df_mes.loc[mask_anestesista, "valor_final"] *= 0.50
    # Classificação Financeira

    df_mes["Despesa paga"] = df_mes.apply(
        lambda x: (
            x["valor_final"]
            if pd.notna(x["Data de Pagamento"])
            and "receita" not in str(x["Classificação"]).lower()
            else 0
        ),
        axis=1,
    )

    df_mes["Despesa a pagar"] = df_mes.apply(
        lambda x: (
            x["valor_final"]
            if pd.isna(x["Data de Pagamento"])
            and "receita" not in str(x["Classificação"]).lower()
            else 0
        ),
        axis=1,
    )

    df_mes["Receita realizada"] = df_mes.apply(
        lambda x: (
            x["valor_final"]
            if pd.notna(x["Data de Pagamento"])
            and "receita" in str(x["Classificação"]).lower()
            else 0
        ),
        axis=1,
    )

    df_mes["Receita prevista"] = df_mes.apply(
        lambda x: (
            x["valor_final"]
            if pd.isna(x["Data de Pagamento"])
            and "receita" in str(x["Classificação"]).lower()
            else 0
        ),
        axis=1,
    )

    def categorizar_semana(data):

        if pd.isna(data):
            return "Sem Data"

        dia = data.day

        return f"Semana {1 if dia <= 7 else 2 if dia <= 14 else 3 if dia <= 21 else 4}"

    df_mes["Semana"] = df_mes["Data Lançamento"].apply(categorizar_semana)

    # --- EXIBIÇÃO ---

    st.title(f"🏦 Planejamento financeiro mensal - {mes_sel}/{ano_sel}")

    st.markdown(
        f"*Bradesco:* R\$ {bradesco:,.2f} | *Caixa:* R\$ {caixa:,.2f} | *Banco do Brasil:* R\$ {brasil:,.2f}"
    )

    if valor_geap_cortado > 0:

        st.warning(
            f"🚨 *Aviso de Cenário:* Receita GEAP reduzida em R$ {valor_geap_cortado:,.2f}"
        )

    # --- QUADRO 1: RESUMO DE FLUXO COM TOTAL GERAL ---
    st.subheader("📊 Resumo de Fluxo Semanal")
    res_sem = (
        df_mes.groupby("Semana")
        .agg(
            {
                "Despesa paga": "sum",
                "Despesa a pagar": "sum",
                "Receita realizada": "sum",
                "Receita prevista": "sum",
            }
        )
        .reset_index()
        .sort_values("Semana")
    )

    # Removido: Cálculo de Despesa Total e Receita Total que você não quer mais

    # Cálculo do Saldo Acumulado (usando as variáveis internas sem precisar das colunas extras)
    saldos, atual = [], saldo_inicial
    for _, row in res_sem.iterrows():
        # O saldo é: Saldo anterior + (Realizada + Prevista) - (Paga + A pagar)
        receita_total_linha = row["Receita realizada"] + row["Receita prevista"]
        despesa_total_linha = row["Despesa paga"] + row["Despesa a pagar"]
        atual = atual + receita_total_linha - despesa_total_linha
        saldos.append(atual)

    res_sem["Saldo Final"] = saldos

    # Criando a linha de TOTAL GERAL (removendo as colunas indesejadas aqui também)
    total_geral = pd.DataFrame(
        {
            "Semana": ["TOTAL GERAL"],
            "Despesa paga": [res_sem["Despesa paga"].sum()],
            "Despesa a pagar": [res_sem["Despesa a pagar"].sum()],
            "Receita realizada": [res_sem["Receita realizada"].sum()],
            "Receita prevista": [res_sem["Receita prevista"].sum()],
            "Saldo Final": [res_sem["Saldo Final"].iloc[-1]],
        }
    )

    df_res_completo = pd.concat([res_sem, total_geral], ignore_index=True)

    # Exibição da tabela formatada
    st.dataframe(
        df_res_completo.style.format(
            {c: "R$ {:,.2f}" for c in df_res_completo.columns if c != "Semana"}
        ).set_table_styles(
            [
                {
                    "selector": "tr:last-child",
                    "props": [("font-weight", "bold"), ("background-color", "#f0f2f6")],
                }
            ]
        ),
        use_container_width=True,
    )

    # --- QUADRO 2: ANALÍTICOS MENSAIS ---

    col_rec, col_desp = st.columns(2)

    with col_rec:

        st.success("### 🟢 Expectativa de receita")

        det_rec = (
            df_mes[df_mes["Receita realizada"] + df_mes["Receita prevista"] > 0]
            .groupby(["Classificação", "Itens"])["valor_final"]
            .sum()
            .reset_index()
        )

        st.dataframe(
            det_rec.style.format({"valor_final": "R$ {:,.2f}"}).bar(color="#d1e7dd"),
            use_container_width=True,
        )

    with col_desp:

        st.error("### 🔴 Expectativa de despesa")

        det_des = (
            df_mes[df_mes["Despesa paga"] + df_mes["Despesa a pagar"] > 0]
            .groupby(["Classificação", "Plano de Contas"])["valor_final"]
            .sum()
            .reset_index()
        )

        st.dataframe(
            det_des.style.format({"valor_final": "R$ {:,.2f}"}).bar(color="#f8d7da"),
            use_container_width=True,
        )

    # --- QUADRO 3: CONFRONTO SEMANAL DETALHADO ---

    st.markdown("---")

    st.header("⚖️ Confronto Semanal Detalhado")

    s_rea_acum, s_pre_acum = saldo_inicial, saldo_inicial

    for sem in ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]:
        df_s = df_mes[df_mes["Semana"] == sem]
        if df_s.empty:
            continue

        with st.expander(f"📍 Detalhamento {sem}", expanded=(sem == "Semana 1")):
            rp, rr, dp, dr = (
                df_s["Receita prevista"].sum(),
                df_s["Receita realizada"].sum(),
                df_s["Despesa a pagar"].sum(),
                df_s["Despesa paga"].sum(),
            )

            # --- STATUS E MAIOR DESPESA ---
            despesa_total_semana = dp + dr
            receita_total_semana = rp + rr
            perc_falta_pagar = (
                (dp / despesa_total_semana * 100) if despesa_total_semana > 0 else 0
            )

            df_s_desp = df_s[~df_s["Classificação"].str.lower().str.contains("receita")]

            if not df_s_desp.empty:
                idx_maior = df_s_desp["valor_final"].idxmax()
                maior_despesa_nome = df_s_desp.loc[idx_maior, "Plano de Contas"]
                maior_despesa_valor = df_s_desp.loc[idx_maior, "valor_final"]

                st.markdown(
                    f"*📉 Despesa Total Prevista:* R$ {despesa_total_semana:,.2f} | *⏳ Status:* Falta pagar *{perc_falta_pagar:.1f}%*"
                )
                st.markdown(
                    f"*🚨 Maior Despesa:* {maior_despesa_nome} (R$ {maior_despesa_valor:,.2f}) | *📉 Receita Total Prevista* {receita_total_semana:,.2f}"
                )
            else:
                st.markdown(
                    f"*📉 Despesa Total Prevista:* R$ 0,00 | *⏳ Status:* Falta pagar *0.0%*"
                )
                st.markdown("*🚨 Maior Despesa:* Nenhuma despesa registrada.")
            st.markdown("---")

            # --- TABELA DE DESPESAS DA SEMANA COM STATUS ---
            st.write(f"*🔍 Despesas da {sem}:*")
            if not df_s_desp.empty:
                # 1. Criamos uma cópia para formatar o visual
                tabela_visual = df_s_desp.copy()

                # 2. Criamos a coluna de Status baseada na data de pagamento
                tabela_visual["Status"] = tabela_visual["Data de Pagamento"].apply(
                    lambda x: "✅ PAGO" if pd.notna(x) else "⏳ PENDENTE"
                )

                # 3. Organizamos as colunas que queremos mostrar
                colunas_exibicao = [
                    "Status",
                    "Plano de Contas",
                    "Classificação",
                    "valor_final",
                ]
                exibir = tabela_visual[colunas_exibicao]

                # 4. Aplicamos a cor: Verde para pago, Vermelho claro para pendente
                def estilizar_status(row):
                    cor = (
                        "background-color: #d1e7dd"
                        if row["Status"] == "✅ PAGO"
                        else "background-color: #f8d7da"
                    )
                    return [cor] * len(row)

                st.dataframe(
                    exibir.style.apply(estilizar_status, axis=1).format(
                        {"valor_final": "R$ {:,.2f}"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            # --- CONFRONTO E SALDOS LIMPOS ---
            # --- CONFRONTO E SALDOS LIMPOS ---
            # --- CONFRONTO E SALDOS LIMPOS ---
            st.markdown("#### ⚖️ Resumo da Semana")

            # O Previsto mostra a "fotografia original": tudo o que foi planejado (Pago + A Pagar)
            receita_total_projetada = rp + rr
            despesa_total_projetada = dp + dr

            # Cálculos dos saldos finais
            saldo_final_prev = (
                s_pre_acum + receita_total_projetada - despesa_total_projetada
            )
            saldo_final_real = s_rea_acum + rr - dr

            df_c = pd.DataFrame(
                {
                    "Saldo Inicial": [s_pre_acum, s_rea_acum],
                    "Receita na Semana": [receita_total_projetada, rr],
                    "Despesa na Semana": [despesa_total_projetada, dr],
                    "Saldo Final": [saldo_final_prev, saldo_final_real],
                },
                index=["Previsto / Projeção", "Realizado"],
            )

            st.dataframe(df_c.style.format("R$ {:,.2f}"), use_container_width=True)

            # Atualização dos saldos para a próxima semana
            s_rea_acum = saldo_final_real
            s_pre_acum = saldo_final_real  # <-- CORREÇÃO: A projeção agora "zera" e parte da realidade bancária!
            # --- INÍCIO DA ALTERAÇÃO: GRÁFICO DA SEMANA MINIMIZADO ---
            # Cria uma aba minimizada por padrão (expanded=False)
            # --- GRÁFICO DA SEMANA (BARRAS AGRUPADAS) ---
        with st.expander(
            f"📊 Gráfico de Desempenho (Comparativo) - {sem}", expanded=False
        ):
            # 1. Prepara os dados: O formato atual está "largo", precisamos deixar "longo" para o Altair agrupar
            df_grafico = pd.DataFrame(
                {
                    "Projetado": [receita_total_projetada, despesa_total_projetada],
                    "Realizado": [rr, dr],
                },
                index=["Receitas", "Despesas"],
            )

            # "Derrete" a tabela para o formato longo (tidy data)
            df_long = (
                df_grafico.reset_index()
                .melt("index", var_name="Cenário", value_name="Valor")
                .rename(columns={"index": "Tipo"})
            )

            # 2. Cria o gráfico Altair
            chart = (
                alt.Chart(df_long)
                .mark_bar()
                .encode(
                    # Eixo X: Coloca o cenário, mas esconde os rótulos para não poluir
                    x=alt.X("Cenário", axis=None),
                    # Eixo Y: O valor financeiro
                    y=alt.Y("Valor", axis=alt.Axis(format="$,.0f", title="Valor (R$)")),
                    # Cor: Define cores diferentes para Projetado (Cinza) e Realizado (Azul) para contraste
                    color=alt.Color(
                        "Cenário",
                        scale={
                            "domain": ["Projetado", "Realizado"],
                            "range": ["#A9A9A9", "#1f77b4"],
                        },
                    ),
                    # Agrupamento: Divide o gráfico em duas colunas: Receitas e Despesas
                    column=alt.Column(
                        "Tipo",
                        header=alt.Header(
                            titleOrient="bottom", labelOrient="bottom", titleFontSize=14
                        ),
                    ),
                    # Tooltip: O que aparece quando passa o mouse em cima
                    tooltip=[
                        alt.Tooltip("Tipo"),
                        alt.Tooltip("Cenário"),
                        alt.Tooltip("Valor", format="$,.2f"),
                    ],
                )
                .properties(
                    width=220,  # Largura de cada grupo de barras
                    height=300,  # Altura do gráfico
                )
                .configure_view(
                    stroke="transparent"  # Remove bordas padrão para ficar mais limpo
                )
                .interactive()
            )  # Permite zoom e pan se quiser

            # Exibe o gráfico
            st.altair_chart(chart, use_container_width=False)

    # --- NOVA PARTE: CÁLCULO E EXIBIÇÃO DOS RESULTADOS FINAIS ---

    # --- CÁLCULO E EXIBIÇÃO DOS RESULTADOS FINAIS ---

    # 1. Resultado Líquido (O que você tem no banco de fato AGORA)
    # Saldo Inicial + Tudo que foi Recebido - Tudo que foi Pago
    saldo_atual_real = (
        saldo_inicial + df_mes["Receita realizada"].sum() - df_mes["Despesa paga"].sum()
    )

    # 2. Resultado Previsto (Como o banco estará no DIA 30 se tudo ocorrer como planejado)
    # Saldo Inicial + Total de Receitas (Real + Prev) - Total de Despesas (Paga + A Pagar)
    total_receita_mes = (
        df_mes["Receita realizada"].sum() + df_mes["Receita prevista"].sum()
    )
    total_despesa_mes = df_mes["Despesa paga"].sum() + df_mes["Despesa a pagar"].sum()
    saldo_final_projetado = saldo_inicial + total_receita_mes - total_despesa_mes
    saldo_final_projetadopr = total_receita_mes - total_despesa_mes
    st.markdown("---")
    col_prev, col_real = st.columns(2)

    with col_prev:
        # Se o saldo projetado for menor que o inicial, a cor fica vermelha (prejuízo no mês)
        cor_pre = "red" if saldo_final_projetadopr < 0 else "#1E90FF"
        st.markdown(
            f"### 📋 Saldo Final Previsto: <span style='color:{cor_pre}; font-weight:bold;'>R$ {saldo_final_projetadopr:,.2f}</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Estimativa de saldo bancário ao final do mês (Saldo Inicial + Projeções)."
        )

    with col_real:
        # Se o saldo atual for menor que o inicial, cor vermelha
        cor_real = "red" if saldo_atual_real < 0 else "green"
        st.markdown(
            f"### 📝 Saldo Atual Líquido: <span style='color:{cor_real}; font-weight:bold;'>R$ {saldo_atual_real:,.2f}</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Saldo bancário disponível neste exato momento (Considerando pagamentos efetuados)."
        )
except Exception as e:
    st.error(f"Erro no processamento: {e}")
