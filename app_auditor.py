import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io
import sqlite3
from datetime import datetime

# --- 1. BANCO DE DADOS EVOLUÍDO ---
def init_db():
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    # Tabela com novas colunas: num_doc e cpf_colaborador
    c.execute('''CREATE TABLE IF NOT EXISTS registros 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data_processo TEXT, data_nota TEXT, empresa TEXT, 
                  cnpj TEXT, num_doc TEXT, cpf_colaborador TEXT,
                  valor REAL, categoria TEXT, status TEXT, justificativa TEXT)''')
    
    # Migração automática de colunas caso o banco já exista
    c.execute("PRAGMA table_info(registros)")
    colunas = [col[1] for col in c.fetchall()]
    for nova_col in ['num_doc', 'cpf_colaborador']:
        if nova_col not in colunas:
            c.execute(f"ALTER TABLE registros ADD COLUMN {nova_col} TEXT DEFAULT 'N/D'")
    
    conn.commit()
    conn.close()

def verificar_duplicidade(num_doc, cnpj, val):
    """Verifica duplicidade baseada no Número do Documento, CNPJ e Valor."""
    if not num_doc or num_doc == "N/D": return False # Evita falso positivo em notas sem número
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    c.execute("SELECT id FROM registros WHERE num_doc = ? AND cnpj = ? AND valor = ?", (num_doc, cnpj, val))
    resultado = c.fetchone()
    conn.close()
    return resultado is not None

def salvar_no_historico(data_n, emp, cnpj, num_doc, cpf, val, cat, stat, just):
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''INSERT INTO registros 
                 (data_processo, data_nota, empresa, cnpj, num_doc, cpf_colaborador, valor, categoria, status, justificativa) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (agora, data_n, emp, cnpj, num_doc, cpf, val, cat, stat, just))
    conn.commit()
    conn.close()

init_db()

# --- 2. LOGIN E CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditor Fiscal Pro", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login de Auditoria")
    with st.form("login"):
        u, p = st.text_input("Usuário"), st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar") and u == "admin" and p == "auditor2026":
            st.session_state["autenticado"] = True
            st.rerun()
    st.stop()

api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key: st.stop()
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 3. INTERFACE ---
st.title("🛡️ Auditoria Fiscal & Compliance")

tab_proc, tab_hist = st.tabs(["🚀 Auditoria em Lote", "📊 Business Intelligence"])

with tab_proc:
    limite = st.number_input("Teto de Reembolso (R$)", value=250.0)
    arquivos = st.file_uploader("Subir Notas/Cupons", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if st.button("Iniciar Processamento") and arquivos:
        barra = st.progress(0)
        for idx, arq in enumerate(arquivos):
            try:
                img = Image.open(arq)
                # Prompt atualizado para capturar Numero do Documento e CPF
                prompt = f"""Extraia da nota: DATA|EMPRESA|CNPJ|NUM_DOC|CPF_CLIENTE|VALOR|CATEGORIA|STATUS|JUSTIFICATIVA. 
                Regras:
                - NUM_DOC: Localize o número da nota, COO ou extrato SAT.
                - CPF_CLIENTE: Se houver CPF no cupom, extraia, senão 'N/D'.
                - Se valor > {limite} = REPROVADO.
                Responda apenas em uma linha com pipes."""
                
                response = model.generate_content([prompt, img])
                p = response.text.strip().replace("```", "").split('|')
                
                if len(p) >= 9:
                    v_raw = re.sub(r'[^\d.]', '', p[5].replace(',', '.'))
                    valor = float(v_raw) if v_raw else 0.0
                    
                    # Verificação de Duplicidade Aprimorada
                    if verificar_duplicidade(p[3].strip(), p[2].strip(), valor):
                        st.warning(f"🚨 Duplicata detectada: Nota {p[3]} de {p[1]} já existe no banco.")
                    else:
                        salvar_no_historico(p[0].strip(), p[1].strip(), p[2].strip(), p[3].strip(), 
                                           p[4].strip(), valor, p[6].strip(), p[7].upper(), p[8].strip())
                        st.success(f"✅ Arquivo {arq.name} processado com sucesso.")
            except Exception as e:
                st.error(f"Erro no processamento de {arq.name}: {e}")
            barra.progress((idx + 1) / len(arquivos))

with tab_hist:
    conn = sqlite3.connect('auditoria.db')
    df = pd.read_sql_query("SELECT * FROM registros", conn)
    conn.close()
    
    if not df.empty:
        # Tratamento de Data para Filtro
        df['dt_obj'] = pd.to_datetime(df['data_nota'], dayfirst=True, errors='coerce')
        df['Mes_Ano'] = df['dt_obj'].dt.strftime('%m/%Y')
        
        # Filtros
        c1, c2, c3 = st.columns(3)
        with c1:
            meses = sorted(df['Mes_Ano'].dropna().unique().tolist())
            filtro_mes = st.multiselect("Mês/Ano", meses, default=meses)
        with c2:
            filtro_cat = st.multiselect("Categoria", df['categoria'].unique(), default=df['categoria'].unique())
        with c3:
            empresa_busca = st.text_input("Buscar Empresa ou CPF")

        # Aplicar Filtros
        df_f = df[df['Mes_Ano'].isin(filtro_mes) & df['categoria'].isin(filtro_cat)]
        if empresa_busca:
            df_f = df_f[df_f['empresa'].str.contains(empresa_busca, case=False) | 
                        df_f['cpf_colaborador'].str.contains(empresa_busca)]

        # Métricas
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", f"R$ {df_f['valor'].sum():.2f}")
        m2.metric("Qtd Notas", len(df_f))
        m3.metric("Ticket Médio", f"R$ {df_f['valor'].mean():.2f}" if len(df_f)>0 else "0")
        m4.metric("Aprovados", f"{len(df_f[df_f['status']=='APROVADO'])}")

        st.subheader("📊 Gráfico de Gastos por Categoria")
        st.plotly_chart(px.bar(df_f, x='categoria', y='valor', color='status', barmode='group'), use_container_width=True)

        st.subheader("📋 Planilha Completa para Auditoria")
        colunas_final = ['data_nota', 'empresa', 'cnpj', 'num_doc', 'cpf_colaborador', 'valor', 'categoria', 'status', 'justificativa']
        st.dataframe(df_f[colunas_final], use_container_width=True)
        
        st.download_button("📥 Exportar para Excel/CSV", df_f.to_csv(index=False).encode('utf-8'), "relatorio_auditoria.csv", "text/csv")
    else:
        st.info("Nenhum dado encontrado no histórico.")

# Manutenção
if st.sidebar.button("⚠️ Resetar Base de Dados"):
    conn = sqlite3.connect('auditoria.db')
    conn.cursor().execute("DROP TABLE registros")
    conn.commit(); conn.close()
    st.rerun()
