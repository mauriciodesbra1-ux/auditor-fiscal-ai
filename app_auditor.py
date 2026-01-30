import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io
import sqlite3
from datetime import datetime

# --- 1. FUNÇÕES DO BANCO DE DADOS ---

def init_db():
    """Cria o arquivo do banco e a tabela se não existirem."""
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS registros 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data_processo TEXT, 
                  data_nota TEXT, 
                  empresa TEXT, 
                  valor REAL, 
                  categoria TEXT, 
                  status TEXT, 
                  justificativa TEXT)''')
    conn.commit()
    conn.close()

def salvar_no_historico(data_n, emp, val, cat, stat, just):
    """Insere uma nova nota auditada no banco de dados."""
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''INSERT INTO registros 
                 (data_processo, data_nota, empresa, valor, categoria, status, justificativa) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (agora, data_n, emp, val, cat, stat, just))
    conn.commit()
    conn.close()

# Inicializa o banco assim que o app rodar
init_db()

# --- 2. CONFIGURAÇÃO E LOGIN ---

st.set_page_config(page_title="Auditor Fiscal 2.5 Pro", layout="wide")

# (Aqui vai o seu bloco de login que já funciona)
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if not st.session_state["autenticado"]:
    # ... (seu código de login)
    st.stop()

# --- 3. CONFIGURAÇÃO DA API GEMINI ---

# Forçando a busca da Key de forma segura
api_key = st.secrets.get("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("Chave API não encontrada no Secrets. Verifique as configurações do Streamlit.")
    st.stop()

# --- 4. INTERFACE ---

st.title("🛡️ Auditoria Fiscal com Banco de Dados")

# Criando abas para separar Processamento de Relatórios
tab_processo, tab_historico = st.tabs(["🚀 Processar Notas", "📊 Histórico de Diretor"])

with tab_processo:
    limite = st.number_input("Teto de Gastos (R$)", value=250.0)
    arquivos = st.file_uploader("Subir Notas", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if st.button("Auditar e Gravar no Banco") and arquivos:
        for arq in arquivos:
            try:
                img = Image.open(arq)
                prompt = f"Extraia: DATA|EMPRESA|VALOR|CATEGORIA|STATUS|JUSTIFICATIVA. Regra: Valor > {limite} = REPROVADO. Responda apenas o pipe."
                
                response = model.generate_content([prompt, img])
                dados = response.text.strip().split('|')
                
                if len(dados) >= 6:
                    # Limpeza para garantir que o valor seja numérico
                    v_limpo = float(re.sub(r'[^\d.]', '', dados[2].replace(',', '.')))
                    
                    # SALVANDO NO BANCO DE DADOS
                    salvar_no_historico(dados[0], dados[1], v_limpo, dados[3], dados[4].upper(), dados[5])
                    st.success(f"Nota da empresa {dados[1]} salva!")
            except Exception as e:
                st.error(f"Erro no arquivo {arq.name}: {e}")

with tab_historico:
    st.subheader("📈 Visão Estratégica")
    
    # Lendo dados do banco para o Pandas
    conn = sqlite3.connect('auditoria.db')
    df = pd.read_sql_query("SELECT * FROM registros", conn)
    conn.close()
    
    if not df.empty:
        # Filtro por Empresa para os Diretores
        lista_empresas = ["Todas"] + sorted(df['empresa'].unique().tolist())
        filtro_empresa = st.selectbox("Selecione a Empresa para análise", lista_empresas)
        
        if filtro_empresa != "Todas":
            df = df[df['empresa'] == filtro_empresa]
        
        # Métricas
        c1, c2 = st.columns(2)
        c1.metric("Soma de Gastos", f"R$ {df['valor'].sum():.2f}")
        c2.metric("Qtd de Notas", len(df))
        
        # Gráfico
        st.plotly_chart(px.bar(df, x='data_nota', y='valor', color='status', hover_data=['justificativa']))
        
        # Tabela completa
        st.dataframe(df, use_container_width=True)
    else:
        st.info("O banco de dados está vazio. Processe notas na primeira aba.")
