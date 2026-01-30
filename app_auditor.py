import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io
import sqlite3
from datetime import datetime

# --- 1. BANCO DE DADOS ATUALIZADO (INCLUINDO CNPJ) ---
def init_db():
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    # Adicionado coluna cnpj
    c.execute('''CREATE TABLE IF NOT EXISTS registros 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data_processo TEXT, data_nota TEXT, empresa TEXT, 
                  cnpj TEXT, valor REAL, categoria TEXT, status TEXT, justificativa TEXT)''')
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

# --- 2. CONFIGURAÇÃO E LOGIN ---
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

# Secrets Management
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("Configure a GEMINI_API_KEY no painel do Streamlit!")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 3. INTERFACE PRINCIPAL ---
st.title("🛡️ Auditoria Fiscal Estratégica")

tab_processo, tab_historico = st.tabs(["🚀 Processar Notas", "📊 Visão por Categoria/Empresa"])

with tab_processo:
    col_config1, col_config2 = st.columns(2)
    with col_config1:
        limite = st.number_input("Limite Global de Reembolso (R$)", value=250.0)
    
    arquivos = st.file_uploader("Upload de Notas Fiscais", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if st.button("Executar Auditoria e Salvar") and arquivos:
        barra = st.progress(0)
        
        for idx, arq in enumerate(arquivos):
            try:
                img = Image.open(arq)
                # Prompt atualizado para capturar CNPJ
                prompt = f"""Analise a nota fiscal. Responda APENAS uma linha no formato: 
                DATA|EMPRESA|CNPJ|VALOR|CATEGORIA|STATUS|JUSTIFICATIVA. 
                Regras: 
                - Se valor > {limite}, STATUS=REPROVADO.
                - Categorias aceitas: Alimentação, Transporte, Hospedagem, Material, Outros.
                - CNPJ: Apenas números ou formato 00.000.000/0000-00."""
                
                response = model.generate_content([prompt, img])
                texto_ia = response.text.strip().replace("```", "").replace("pipe", "").strip()
                
                partes = texto_ia.split('|')
                
                if len(partes) >= 7:
                    v_raw = re.sub(r'[^\d.]', '', partes[3].replace(',', '.'))
                    valor = float(v_raw) if v_raw else 0.0
                    
                    salvar_no_historico(
                        partes[0].strip(), # Data Nota
                        partes[1].strip(), # Empresa
                        partes[2].strip(), # CNPJ
                        valor,             # Valor
                        partes[4].strip(), # Categoria
                        partes[5].strip().upper(), # Status
                        partes[6].strip()  # Justificativa
                    )
                    st.success(f"Processado: {partes[1]} (CNPJ: {partes[2]})")
                else:
                    st.error(f"Erro no formato da IA para {arq.name}")
            except Exception as e:
                st.error(f"Erro técnico: {e}")
            
            barra.progress((idx + 1) / len(arquivos))

with tab_historico:
    conn = sqlite3.connect('auditoria.db')
    # Carregamos os dados brutos
    df = pd.read_sql_query("SELECT * FROM registros ORDER BY id DESC", conn)
    conn.close()
    
    if not df.empty:
        # Filtros Superiores
        c1, c2 = st.columns(2)
        with c1:
            filtro_cat = st.multiselect("Filtrar por Categoria", df['categoria'].unique(), default=df['categoria'].unique())
        with c2:
            filtro_emp = st.selectbox("Filtrar por Empresa", ["Todas"] + sorted(df['empresa'].unique().tolist()))
        
        # Aplicando Filtros
        df_filtrado = df[df['categoria'].isin(filtro_cat)]
        if filtro_emp != "Todas":
            df_filtrado = df_filtrado[df_filtrado['empresa'] == filtro_emp]

        # --- DASHBOARD PARA DIRETORIA ---
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Acumulado", f"R$ {df_filtrado['valor'].sum():.2f}")
        m2.metric("Nº de Notas", len(df_filtrado))
        m3.metric("Média por Nota", f"R$ {df_filtrado['valor'].mean():.2f}")

        # Gráfico Agrupado por Categoria
        st.subheader("📊 Gastos Agrupados por Categoria")
        fig_cat = px.bar(df_filtrado, x='categoria', y='valor', color='status', 
                         title="Volume Financeiro por Categoria", barmode='group')
        st.plotly_chart(fig_cat, use_container_width=True)

        # Planilha Detalhada (com CNPJ)
        st.subheader("📋 Detalhamento da Planilha")
        st.dataframe(df_filtrado[['data_nota', 'empresa', 'cnpj', 'valor', 'categoria', 'status', 'justificativa']], 
                     use_container_width=True)
        
        # Botão de Exportação
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha Auditada (CSV)", csv, "auditoria_cnpj.csv", "text/csv")
    else:
        st.info("Ainda não existem dados no histórico. Processe algumas notas primeiro.")
