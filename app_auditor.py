import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io
import sqlite3
from datetime import datetime

# --- 1. BANCO DE DADOS COM MIGRAÇÃO AUTOMÁTICA ---
def init_db():
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    # Cria a tabela se não existir
    c.execute('''CREATE TABLE IF NOT EXISTS registros 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data_processo TEXT, data_nota TEXT, empresa TEXT, 
                  valor REAL, categoria TEXT, status TEXT, justificativa TEXT)''')
    
    # MÁGICA: Verifica se a coluna cnpj existe, se não, adiciona
    c.execute("PRAGMA table_info(registros)")
    colunas = [col[1] for col in c.fetchall()]
    if 'cnpj' not in colunas:
        c.execute("ALTER TABLE registros ADD COLUMN cnpj TEXT DEFAULT 'N/D'")
    
    conn.commit()
    conn.close()

def salvar_no_historico(data_n, emp, cnpj, val, cat, stat, just):
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''INSERT INTO registros 
                 (data_processo, data_nota, empresa, cnpj, valor, categoria, status, justificativa) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
              (agora, data_n, emp, cnpj, val, cat, stat, just))
    conn.commit()
    conn.close()

init_db()

# --- 2. LOGIN E CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditor Pro 2026", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login de Auditoria")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
    st.stop()

# Gerenciamento da Chave
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("Chave GEMINI_API_KEY não encontrada nos Secrets!")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 3. INTERFACE ---
st.title("🛡️ Auditoria Fiscal Inteligente")

tab_proc, tab_hist = st.tabs(["🚀 Processar Notas", "📊 Análise Estratégica"])

with tab_proc:
    limite = st.number_input("Limite Global de Reembolso (R$)", value=250.0)
    arquivos = st.file_uploader("Subir Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if st.button("Executar Auditoria") and arquivos:
        barra = st.progress(0)
        for idx, arq in enumerate(arquivos):
            try:
                img = Image.open(arq)
                prompt = f"""Analise a nota. Responda APENAS uma linha no formato: 
                DATA|EMPRESA|CNPJ|VALOR|CATEGORIA|STATUS|JUSTIFICATIVA. 
                Regra: Se valor > {limite} STATUS=REPROVADO. Categorias: Alimentação, Transporte, Hospedagem, Material, Outros."""
                
                response = model.generate_content([prompt, img])
                t = response.text.strip().replace("```", "").replace("pipe", "").strip()
                p = t.split('|')
                
                if len(p) >= 7:
                    v_raw = re.sub(r'[^\d.]', '', p[3].replace(',', '.'))
                    valor = float(v_raw) if v_raw else 0.0
                    salvar_no_historico(p[0], p[1], p[2], valor, p[4], p[5].upper(), p[6])
                    st.success(f"Auditado: {p[1]}")
            except Exception as e:
                st.error(f"Erro no arquivo {arq.name}: {e}")
            barra.progress((idx + 1) / len(arquivos))

with tab_hist:
    conn = sqlite3.connect('auditoria.db')
    df = pd.read_sql_query("SELECT * FROM registros ORDER BY id DESC", conn)
    conn.close()
    
    if not df.empty:
        # Filtros de Diretor
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            cats = st.multiselect("Categorias", df['categoria'].unique(), default=df['categoria'].unique())
        with col_f2:
            emps = st.selectbox("Empresa", ["Todas"] + sorted(df['empresa'].unique().tolist()))
        
        # Aplicar Filtros
        df_f = df[df['categoria'].isin(cats)]
        if emps != "Todas":
            df_f = df_f[df_f['empresa'] == emps]

        # Métricas de Resumo
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Gasto", f"R$ {df_f['valor'].sum():.2f}")
        m2.metric("Qtd Notas", len(df_f))
        m3.metric("Ticket Médio", f"R$ {df_f['valor'].mean():.2f}" if len(df_f)>0 else "0")

        # Gráfico Agrupado por Categoria
        st.subheader("📊 Gastos por Categoria")
        fig = px.bar(df_f, x='categoria', y='valor', color='status', barmode='group',
                     color_discrete_map={'APROVADO':'#00cc96', 'REPROVADO':'#ef553b'})
        st.plotly_chart(fig, use_container_width=True)

        # Tabela com as colunas corretas
        st.subheader("📋 Detalhamento")
        # Garantimos que as colunas existem antes de exibir
        colunas_exibir = ['data_nota', 'empresa', 'cnpj', 'valor', 'categoria', 'status', 'justificativa']
        st.dataframe(df_f[colunas_exibir], use_container_width=True)
        
        # Botão para limpar banco caso queira resetar
        if st.sidebar.button("⚠️ Resetar Banco de Dados"):
            conn = sqlite3.connect('auditoria.db')
            conn.cursor().execute("DROP TABLE registros")
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.info("O banco de dados está vazio.")
