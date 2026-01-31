import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import sqlite3
from datetime import datetime, timedelta

# =========================================================
# 1. BANCO DE DADOS
# =========================================================
def init_db():
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_processo TEXT,
            data_nota TEXT,
            empresa TEXT,
            cnpj TEXT,
            num_doc TEXT,
            cpf_colaborador TEXT,
            valor REAL,
            categoria TEXT,
            status TEXT,
            justificativa TEXT
        )
    ''')
    conn.commit()
    conn.close()

def verificar_duplicidade(num_doc, cnpj, val):
    if not num_doc or num_doc == "N/D":
        return False
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    c.execute(
        "SELECT id FROM registros WHERE num_doc=? AND cnpj=? AND valor=?",
        (num_doc, cnpj, val)
    )
    res = c.fetchone()
    conn.close()
    return res is not None

def salvar_no_historico(data_n, emp, cnpj, doc, cpf, val, cat, stat, just):
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''
        INSERT INTO registros
        (data_processo, data_nota, empresa, cnpj, num_doc, cpf_colaborador,
         valor, categoria, status, justificativa)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (agora, data_n, emp, cnpj, doc, cpf, val, cat, stat, just))
    conn.commit()
    conn.close()

init_db()

# =========================================================
# 2. CONFIG STREAMLIT / LOGIN
# =========================================================
st.set_page_config(page_title="Auditoria de Reembolsos por Política", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login Administrativo")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar") and u == "admin" and p == "auditor2026":
            st.session_state["autenticado"] = True
            st.rerun()
    st.stop()

# =========================================================
# 3. CONFIG GEMINI
# =========================================================
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    api_key = st.sidebar.text_input("API Key Gemini", type="password")

if not api_key:
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

# =========================================================
# 4. POLÍTICA CONFIGURÁVEL (DEMO REALISTA)
# =========================================================
st.sidebar.header("⚙️ Política de Reembolso")

LIMITES_POLITICA = {
    "Alimentação": st.sidebar.number_input("Alimentação (R$)", 50.0, 300.0, 120.0),
    "Transporte": st.sidebar.number_input("Transporte (R$)", 50.0, 500.0, 200.0),
    "Hospedagem": st.sidebar.number_input("Hospedagem (R$)", 200.0, 800.0, 450.0),
    "Material": st.sidebar.number_input("Material (R$)", 50.0, 300.0, 150.0),
    "Outros": st.sidebar.number_input("Outros (R$)", 20.0, 200.0, 50.0)
}

PRAZO_MAX_DIAS = st.sidebar.number_input(
    "Prazo máximo para envio da nota (dias)",
    1, 60, 7
)

# =========================================================
# 5. INTERFACE PRINCIPAL
# =========================================================
st.title("🛡️ Auditoria de Reembolsos por Política")

modo = st.radio(
    "Modo de Operação",
    ["Financeiro / Administrativo (Lote)", "Colaborador (Envio Unitário - Demo)"],
    horizontal=True
)

tab_auditoria, tab_bi = st.tabs(["🚀 Auditoria", "📊 Relatórios & BI"])

# =========================================================
# 6. AUDITORIA
# =========================================================
with tab_auditoria:

    if modo.startswith("Financeiro"):
        st.info("Simulação do **Financeiro validando um lote de notas do período**.")
        arquivos = st.file_uploader(
            "Upload de comprovantes (lote)",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True
        )
    else:
        st.info("Simulação do **Colaborador enviando uma nota individual**.")
        arquivos = st.file_uploader(
            "Envio de comprovante",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=False
        )
        arquivos = [arquivos] if arquivos else []

    if st.button("Processar") and arquivos:
        barra = st.progress(0)

        for idx, arq in enumerate(arquivos):
            try:
                img = Image.open(arq)

                prompt = """
                Analise rigorosamente e responda apenas uma linha no formato:
                DATA|EMPRESA|CNPJ|NUM_DOC|CPF_COLABORADOR|VALOR|CATEGORIA
                Categorias: Alimentação, Transporte, Hospedagem, Material, Outros.
                Use N/D quando não encontrar.
                """

                response = model.generate_content([prompt, img])
                p = response.text.strip().replace("```", "").split("|")

                if len(p) < 7:
                    st.error(f"Erro de leitura: {arq.name}")
                    continue

                data_nota = p[0].strip()
                empresa = p[1].strip()
                cnpj = p[2].strip()
                num_doc = p[3].strip()
                cpf = p[4].strip()
                valor = float(re.sub(r"[^\d.]", "", p[5].replace(",", ".")))
                categoria = p[6].strip()

                status = "APROVADO"
                justificativa = "Dentro da política."

                # --- REGRA 1: LIMITE DE VALOR
                teto = LIMITES_POLITICA.get(categoria, LIMITES_POLITICA["Outros"])
                if valor > teto:
                    status = "EXCEÇÃO"
                    justificativa = f"Valor acima do teto de R$ {teto:.2f}."

                # --- REGRA 2: PRAZO DE ENVIO
                try:
                    dt_nota = datetime.strptime(data_nota, "%d/%m/%Y")
                    if datetime.now() - dt_nota > timedelta(days=PRAZO_MAX_DIAS):
                        status = "EXCEÇÃO"
                        justificativa = f"Nota enviada fora do prazo ({PRAZO_MAX_DIAS} dias)."
                except:
                    status = "EXCEÇÃO"
                    justificativa = "Data da nota inválida."

                # --- REGRA 3: DUPLICIDADE
                if verificar_duplicidade(num_doc, cnpj, valor):
                    status = "EXCEÇÃO"
                    justificativa = "Possível duplicidade detectada."

                salvar_no_historico(
                    data_nota, empresa, cnpj, num_doc, cpf,
                    valor, categoria, status, justificativa
                )

                st.success(f"{empresa} — {status}")

            except Exception as e:
                st.error(f"Falha técnica: {e}")

            barra.progress((idx + 1) / len(arquivos))

# =========================================================
# 7. BI / RELATÓRIOS
# =========================================================
with tab_bi:
    conn = sqlite3.connect('auditoria.db')
    df = pd.read_sql_query("SELECT * FROM registros", conn)
    conn.close()

    if df.empty:
        st.info("Nenhum dado disponível.")
        st.stop()

    df["data_nota_dt"] = pd.to_datetime(df["data_nota"], dayfirst=True, errors="coerce")

    # --- FILTRO DE PERÍODO
    st.subheader("📅 Filtro por Período")
    col1, col2 = st.columns(2)
    with col1:
        dt_ini = st.date_input("Data inicial", df["data_nota_dt"].min())
    with col2:
        dt_fim = st.date_input("Data final", df["data_nota_dt"].max())

    df_f = df[
        (df["data_nota_dt"] >= pd.to_datetime(dt_ini)) &
        (df["data_nota_dt"] <= pd.to_datetime(dt_fim))
    ]

    # --- MÉTRICAS
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Processado", f"R$ {df_f['valor'].sum():.2f}")
    c2.metric("Qtd Notas", len(df_f))
    c3.metric("Total em Exceção", f"R$ {df_f[df_f['status']=='EXCEÇÃO']['valor'].sum():.2f}")
    c4.metric("Aprovação Automática",
              f"{(df_f[df_f['status']=='APROVADO'].shape[0] / max(len(df_f),1))*100:.1f}%")

    # --- GRÁFICO
    st.subheader("📊 Status por Categoria")
    fig = px.bar(
        df_f, x="categoria", y="valor",
        color="status", barmode="group"
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- TABELA
    st.subheader("📋 Relatório Detalhado")
    st.dataframe(df_f[
        ["data_nota", "empresa", "cnpj", "num_doc", "cpf_colaborador",
         "valor", "categoria", "status", "justificativa"]
    ], use_container_width=True)

    st.download_button(
        "📥 Exportar CSV",
        df_f.to_csv(index=False).encode("utf-8"),
        "reembolsos_auditados.csv",
        "text/csv"
    )

# =========================================================
# 8. MANUTENÇÃO
# =========================================================
if st.sidebar.button("⚠️ Resetar Base"):
    conn = sqlite3.connect('auditoria.db')
    conn.execute("DROP TABLE registros")
    conn.commit()
    conn.close()
    st.rerun()
