import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io
import sqlite3
from datetime import datetime

# --- 1. BANCO DE DADOS (CRIAÇÃO AUTOMÁTICA) ---
def init_db():
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS registros 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data_processo TEXT, data_nota TEXT, empresa TEXT, 
                  valor REAL, categoria TEXT, status TEXT, justificativa TEXT)''')
    conn.commit()
    conn.close()

def salvar_no_historico(data_n, emp, val, cat, stat, just):
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''INSERT INTO registros 
                 (data_processo, data_nota, empresa, valor, categoria, status, justificativa) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (agora, data_n, emp, val, cat, stat, just))
    conn.commit()
    conn.close()

init_db()

# --- 2. LOGIN E SECRETS ---
st.set_page_config(page_title="Auditor Pro 2.5", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
    st.stop()

# Recuperação Robusta da Key
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("Chave GEMINI_API_KEY não encontrada nos Secrets!")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 3. INTERFACE ---
st.title("🛡️ Auditoria Fiscal Automática")

tab_processo, tab_historico = st.tabs(["🚀 Processar Agora", "📊 Banco de Dados"])

with tab_processo:
    limite = st.number_input("Limite (R$)", value=250.0)
    arquivos = st.file_uploader("Subir Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if st.button("Executar Auditoria") and arquivos:
        resultados_imediatos = []
        barra = st.progress(0)
        
        for idx, arq in enumerate(arquivos):
            try:
                img = Image.open(arq)
                # Prompt reforçado para evitar textos extras da IA
                prompt = f"""Analise a nota. Responda APENAS uma linha no formato: 
                DATA|EMPRESA|VALOR|CATEGORIA|STATUS|JUSTIFICATIVA. 
                Regra: Se valor > {limite} STATUS=REPROVADO. Use ponto para decimal."""
                
                response = model.generate_content([prompt, img])
                texto_ia = response.text.strip()
                
                # Tratamento para remover possíveis marcações de markdown (```) que a IA as vezes coloca
                texto_ia = texto_ia.replace("```", "").replace("pipe", "").strip()
                
                partes = texto_ia.split('|')
                
                if len(partes) >= 6:
                    v_raw = re.sub(r'[^\d.]', '', partes[2].replace(',', '.'))
                    valor = float(v_raw) if v_raw else 0.0
                    
                    # Salva no Banco
                    salvar_no_historico(partes[0], partes[1], valor, partes[3], partes[4].upper(), partes[5])
                    
                    # Guarda para mostrar na tela agora
                    resultados_imediatos.append({
                        "Data": partes[0], "Empresa": partes[1], "Valor": valor,
                        "Status": partes[4], "Justificativa": partes[5]
                    })
                else:
                    st.error(f"IA deu resposta incompleta em {arq.name}: {texto_ia}")
            except Exception as e:
                st.error(f"Erro no arquivo {arq.name}: {e}")
            
            barra.progress((idx + 1) / len(arquivos))
        
        # MOSTRA RESULTADO NA TELA IMEDIATAMENTE
        if resultados_imediatos:
            st.success("Processamento concluído!")
            st.table(pd.DataFrame(resultados_imediatos))

with tab_historico:
    st.subheader("📋 Registros Salvos no Banco")
    conn = sqlite3.connect('auditoria.db')
    df = pd.read_sql_query("SELECT * FROM registros ORDER BY id DESC", conn)
    conn.close()
    
    if not df.empty:
        # Filtro por Empresa (Desejo dos Diretores)
        lista_empresas = ["Todas"] + sorted(df['empresa'].unique().tolist())
        emp_sel = st.selectbox("Filtrar Histórico por Empresa", lista_empresas)
        
        df_view = df if emp_sel == "Todas" else df[df['empresa'] == emp_sel]
        
        st.dataframe(df_view, use_container_width=True)
        
        # Gráfico de histórico
        fig = px.bar(df_view, x='empresa', y='valor', color='status', title="Volume de Gastos por Empresa")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("O Banco de Dados está vazio.")
