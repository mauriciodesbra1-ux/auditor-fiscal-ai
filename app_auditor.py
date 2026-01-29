import streamlit as st
import requests
import base64
import pandas as pd
import re
import time
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor AI Pro", layout="wide", page_icon="🛡️")

# --- SISTEMA DE LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔒 Acesso Restrito")
        user = st.text_input("Usuário")
        pw = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if user == "admin" and pw == "auditor2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Dados incorretos.")
        return False
    return True

if check_password():
    st.title("🛡️ AI Auditor Pro: Inteligência Fiscal")
    st.markdown("---")

    api_key = st.secrets.get("GEMINI_KEY", st.sidebar.text_input("Gemini API Key", type="password"))
    valor_max = st.sidebar.number_input("Limite de Reembolso (R$)", value=250.0)
    arquivos = st.file_uploader("📂 Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    def codificar_imagem(arquivo):
        return base64.b64encode(arquivo.read()).decode('utf-8')

    if st.button("🚀 Iniciar Auditoria") and arquivos:
        if not api_key:
            st.error("⚠️ Chave de API não configurada.")
        else:
            resultados = []
            progresso = st.progress(0)
            status_msg = st.empty()
            
            MODELO = "gemini-3-flash-preview"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={api_key}"

            for i, arq in enumerate(arquivos):
                status_msg.info(f"Analisando: {arq.name}...")
                img_b64 = codificar_imagem(arq)
                
                payload = {
                    "contents": [{"parts": [
                        {"text": f"Extraia EXATAMENTE assim: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. Use Categorias: Alimentação, Transporte, Hospedagem, Outros. Limite R$ {valor_max}."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]}],
                    "generationConfig": {"temperature": 0.1}
                }

                sucesso_nota = False
                try:
                    response = requests.post(url, json=payload, timeout=40)
                    res_json = response.json()
                    
                    if 'candidates' in res_json:
                        texto = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                        cols = texto.replace('`', '').replace('markdown', '').strip().split("|")
                        
                        # Garante que temos exatamente 7 colunas, preenchendo vazios se necessário
                        # Isso impede o erro de 'Categoria' não encontrada
                        res_dict = {
                            "Arquivo": arq.name,
                            "Valor (R$)": 0.0,
                            "Local": "Desconhecido",
                            "CNPJ": "N/A",
                            "Data": "N/A",
                            "Categoria": "Outros",
                            "Status": "FALHA",
                            "Justificativa": "Erro na resposta da IA"
                        }

                        if len(cols) >= 1:
                            v_str = re.sub(r'[^\d,.]', '', cols[0]).replace(',', '.')
                            res_dict["Valor (R$)"] = float(v_str) if v_str else 0.0
                        if len(cols) >= 2: res_dict["Local"] = cols[1].strip()
                        if len(cols) >= 3: res_dict["CNPJ"] = cols[2].strip()
                        if len(cols) >= 4: res_dict["Data"] = cols[3].strip()
                        if len(cols) >= 5: res_dict["Categoria"] = cols[4].strip()
                        if len(cols) >= 6: res_dict["Status"] = cols[5].strip().upper()
                        if len(cols) >= 7: res_dict["Justificativa"] = cols[6].strip()

                        resultados.append(res_dict)
                        sucesso_nota = True
                except Exception:
                    pass
                
                if not sucesso_nota:
                    resultados.append({
                        "Arquivo": arq.name, "Valor (R$)": 0.0, "Local": "Erro de Conexão",
                        "CNPJ": "N/A", "Data": "N/A", "Categoria": "Outros",
                        "Status": "FALHA", "Justificativa": "API não respondeu"
                    })
                
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                
                # --- HIGIENIZAÇÃO FINAL ANTES DO GRÁFICO ---
                # Isso aqui é o que impede o seu erro 'Value of x is not the name of a column'
                necessarias = ['Arquivo', 'Local', 'CNPJ', 'Data', 'Categoria', 'Status', 'Valor (R$)', 'Justificativa']
                for col in necessarias:
                    if col not in df.columns:
                        df[col] = 0.0 if col == 'Valor (R$)' else "N/A"

                st.markdown("### 📊 Resultado da Auditoria")
                
                # DASHBOARD DE MÉTRICAS
                m1, m2, m3 = st.columns(3)
                aprovados = df[df['Status'].str.contains('APROVADO', na=False)]['Valor (R$)'].sum()
                m1.metric("Total Analisado", f"R$ {df['Valor (R$)'].sum():,.2f}")
                m2.metric("Total Aprovado", f"R$ {aprovados:,.2f}", delta_color="normal")
                m3.metric("Notas", len(df))

                # GRÁFICOS PROTEGIDOS
                col1, col2 = st.columns(2)
                with col1:
                    try:
                        fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', title="Gastos por Categoria")
                        st.plotly_chart(fig_bar, width='stretch')
                    except Exception:
                        st.error("Não foi possível gerar o gráfico de barras devido à formatação dos dados.")

                with col2:
                    try:
                        fig_pie = px.pie(df, names='Status', values='Valor (R$)', title="Status das Notas", hole=0.3)
                        st.plotly_chart(fig_pie, width='stretch')
                    except Exception:
                        st.error("Não foi possível gerar o gráfico de pizza.")

                st.markdown("---")
                st.dataframe(df, width='stretch')
                
                # Download
                csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 Baixar Relatório CSV", csv, "auditoria.csv", "text/csv")
