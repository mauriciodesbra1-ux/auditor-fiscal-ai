import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io
import sqlite3
from datetime import datetime

# --- 1. BANCO DE DADOS E CONFIGURAÇÕES DE POLÍTICA ---
def init_db():
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS registros 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data_processo TEXT, data_nota TEXT, empresa TEXT, 
                  cnpj TEXT, num_doc TEXT, cpf_colaborador TEXT,
                  valor REAL, categoria TEXT, status TEXT, justificativa TEXT)''')
    
    # Migração de colunas para garantir compatibilidade
    c.execute("PRAGMA table_info(registros)")
    colunas = [col[1] for col in c.fetchall()]
    for col in ['num_doc', 'cpf_colaborador']:
        if col not in colunas:
            c.execute(f"ALTER TABLE registros ADD COLUMN {col} TEXT DEFAULT 'N/D'")
    conn.commit()
    conn.close()

# Definição dos Limites da Política (Cláusula 3)
LIMITES_POLITICA = {
    "Alimentação": 120.0,
    "Transporte": 200.0,
    "Hospedagem": 450.0,
    "Material": 150.0,
    "Outros": 50.0
}

def verificar_duplicidade(num_doc, cnpj, val):
    if not num_doc or num_doc == "N/D": return False
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    c.execute("SELECT id FROM registros WHERE num_doc = ? AND cnpj = ? AND valor = ?", (num_doc, cnpj, val))
    res = c.fetchone()
    conn.close()
    return res is not None

def salvar_no_historico(data_n, emp, cnpj, doc, cpf, val, cat, stat, just):
    conn = sqlite3.connect('auditoria.db')
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''INSERT INTO registros 
                 (data_processo, data_nota, empresa, cnpj, num_doc, cpf_colaborador, valor, categoria, status, justificativa) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (agora, data_n, emp, cnpj, doc, cpf, val, cat, stat, just))
    conn.commit()
    conn.close()

init_db()

# --- 2. CONFIGURAÇÃO STREAMLIT & GEMINI ---
st.set_page_config(page_title="Auditor Fiscal Pro - Compliance 2026", layout="wide")

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

# Recuperação da API Key
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.sidebar.warning("API Key não encontrada no Secrets.")
    api_key = st.sidebar.text_input("Insira a Key manualmente:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.stop()

# --- 3. INTERFACE PRINCIPAL ---
st.title("🛡️ Auditoria Fiscal Baseada em Política")

tab_auditoria, tab_bi = st.tabs(["🚀 Iniciar Auditoria", "📊 Business Intelligence"])

with tab_auditoria:
    st.info(f"**Política Ativa:** Alimentação (R$ {LIMITES_POLITICA['Alimentação']}), "
            f"Transporte (R$ {LIMITES_POLITICA['Transporte']}), Hospedagem (R$ {LIMITES_POLITICA['Hospedagem']})")
    
    arquivos = st.file_uploader("Upload de Comprovantes", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if st.button("Processar Lote") and arquivos:
        barra = st.progress(0)
        for idx, arq in enumerate(arquivos):
            try:
                img = Image.open(arq)
                # Prompt instruindo a IA sobre a categorização
                prompt = """Analise rigorosamente e responda apenas uma linha no formato:
                DATA|EMPRESA|CNPJ|NUM_DOC|CPF_CLIENTE|VALOR|CATEGORIA|DESCRICAO_ITENS
                Categorias: Alimentação, Transporte, Hospedagem, Material, Outros.
                Se não achar CPF, retorne 'N/D'. Se não achar Numero Doc, retorne 'N/D'."""
                
                response = model.generate_content([prompt, img])
                p = response.text.strip().replace("```", "").split('|')
                
                if len(p) >= 7:
                    v_raw = re.sub(r'[^\d.]', '', p[5].replace(',', '.'))
                    valor = float(v_raw) if v_raw else 0.0
                    categoria = p[6].strip()
                    
                    # LOGICA DE COMPLIANCE DINÂMICA
                    teto = LIMITES_POLITICA.get(categoria, 50.0) # 50 é o padrão para 'Outros'
                    
                    status = "APROVADO"
                    justificativa = "Gasto dentro dos limites da política."
                    
                    if valor > teto:
                        status = "REPROVADO"
                        justificativa = f"Excede o teto de R$ {teto:.2f} para {categoria}."
                    
                    # Verificação de Duplicidade
                    if verificar_duplicidade(p[3].strip(), p[2].strip(), valor):
                        st.warning(f"🚨 Bloqueado: Nota {p[3]} (Duplicada)")
                    else:
                        salvar_no_historico(p[0].strip(), p[1].strip(), p[2].strip(), p[3].strip(), 
                                           p[4].strip(), valor, categoria, status, justificativa)
                        st.success(f"Auditado: {p[1]} - {status}")
                else:
                    st.error(f"Erro de leitura na nota {arq.name}")
            except Exception as e:
                st.error(f"Falha técnica: {e}")
            barra.progress((idx + 1) / len(arquivos))

with tab_bi:
    conn = sqlite3.connect('auditoria.db')
    df = pd.read_sql_query("SELECT * FROM registros", conn)
    conn.close()
    
    if not df.empty:
        # Filtros Mensais e de Categoria
        df['dt_obj'] = pd.to_datetime(df['data_nota'], dayfirst=True, errors='coerce')
        df['Mes_Ano'] = df['dt_obj'].dt.strftime('%m/%Y')
        
        c1, c2 = st.columns(2)
        with c1:
            filtro_mes = st.multiselect("Filtrar Período", sorted(df['Mes_Ano'].dropna().unique()), 
                                        default=sorted(df['Mes_Ano'].dropna().unique()))
        with c2:
            filtro_emp = st.text_input("Buscar por Empresa, CNPJ ou CPF")

        df_f = df[df['Mes_Ano'].isin(filtro_mes)]
        if filtro_emp:
            df_f = df_f[df_f['empresa'].str.contains(filtro_emp, case=False) | 
                        df_f['cnpj'].str.contains(filtro_emp) |
                        df_f['cpf_colaborador'].str.contains(filtro_emp)]

        # Dashboard Visual
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Auditado", f"R$ {df_f['valor'].sum():.2f}")
        col2.metric("Nº de Notas", len(df_f))
        col3.metric("Total Reprovado", f"R$ {df_f[df_f['status']=='REPROVADO']['valor'].sum():.2f}")

        st.subheader("📊 Gastos por Categoria (Real vs Teto)")
        fig = px.bar(df_f, x='categoria', y='valor', color='status', barmode='group',
                     color_discrete_map={'APROVADO':'#00cc96', 'REPROVADO':'#ef553b'})
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Relatório Consolidado")
        st.dataframe(df_f[['data_nota', 'empresa', 'cnpj', 'num_doc', 'cpf_colaborador', 'valor', 'categoria', 'status', 'justificativa']], 
                     use_container_width=True)
        
        st.download_button("📥 Exportar Relatórios", df_f.to_csv(index=False).encode('utf-8'), "auditoria_final.csv", "text/csv")
    else:
        st.info("Nenhum dado processado ainda.")

# Sidebar de manutenção
if st.sidebar.button("⚠️ Resetar Base de Dados"):
    conn = sqlite3.connect('auditoria.db')
    conn.cursor().execute("DROP TABLE registros"); conn.commit(); conn.close()
    st.rerun()
