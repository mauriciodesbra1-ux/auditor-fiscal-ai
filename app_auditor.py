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
                st.error("Usuário ou senha incorretos.")
        return False
    return True

if check_password():
    st.title("🛡️ AI Auditor Pro: Inteligência Fiscal")
    st.markdown("---")

    # --- ACESSO AUTOMÁTICO À KEY (SECRETS) ---
    # Busca no TOML do Streamlit Cloud. Se não achar, libera campo manual.
    api_key = st.secrets.get("GEMINI_KEY", "")
    if not api_key:
        api_key = st.sidebar.text_input("Gemini API Key", type="password")

    valor_max = st.sidebar.number_input("Limite de Reembolso (R$)", value=250.0)
    arquivos = st.file_uploader("📂 Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    def codificar_imagem(arquivo):
        return base64.b64encode(arquivo.read()).decode('utf-8')

    if st.button("🚀 Iniciar Auditoria") and arquivos:
        if not api_key:
            st.error("⚠️ Chave de API não encontrada nos Secrets ou campo vazio.")
        else:
            resultados = []
            progresso = st.progress(0)
            status_msg = st.empty()
            
            # Usando modelo estável para evitar erros de 'Preview'
            MODELO = "gemini-1.5-flash" 
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={api_key}"

            for i, arq in enumerate(arquivos):
                status_msg.info(f"Analisando: {arq.name} ({i+1}/{len(arquivos)})")
                img_b64 = codificar_imagem(arq)
                
                payload = {
                    "contents": [{"parts": [
                        {"text": f"Extraia em uma única linha separada por '|': VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. Categorias: Alimentação, Transporte, Hospedagem, Outros. Status APROVADO se valor <= {valor_max}, caso contrário REPROVADO."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]}],
                    "generationConfig": {"temperature": 0.1}
                }

                sucesso_nota = False
                for tentativa in range(3):
                    try:
                        response = requests.post(url, json=payload, timeout=40)
                        if response.status_code == 200:
                            res_json = response.json()
                            texto = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                            cols = texto.replace('`', '').replace('markdown', '').strip().split("|")
                            
                            # Preenchimento preventivo de colunas
                            if len(cols) >= 6:
                                v_raw = re.sub(r'[^\d,.]', '', cols[0]).replace(',', '.')
                                resultados.append({
                                    "Arquivo": arq.name,
                                    "Valor (R$)": float(v_raw) if v_raw else 0.0,
                                    "Local": cols[1].strip(),
                                    "CNPJ": cols[2].strip(),
                                    "Data": cols[3].strip(),
                                    "Categoria": cols[4].strip(),
                                    "Status": cols[5].strip().upper(),
                                    "Justificativa": cols[6].strip() if len(cols) > 6 else "OK"
                                })
                                sucesso_nota = True
                                break
                        elif response.status_code == 429: # Erro de Cota (Too Many Requests)
                            time.sleep(5) # Espera 5 segundos e tenta de novo
                        else:
                            time.sleep(2)
                    except:
                        time.sleep(2)
                
                if not sucesso_nota:
                    resultados.append({
                        "Arquivo": arq.name, "Valor (R$)": 0.0, "Local": "Erro API", 
                        "CNPJ": "-", "Data": "-", "Categoria": "Outros", 
                        "Status": "FALHA", "Justificativa": "A API não respondeu corretamente."
                    })
                
                progresso.progress((i + 1) / len(arquivos))
                time.sleep(1) # Delay de cortesia para a API

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                
                # Garante que as colunas existam para o gráfico
                for c in ["Categoria", "Status", "Valor (R$)"]:
                    if c not in df.columns: df[c] = "Indefinido" if c != "Valor (R$)" else 0.0

                st.markdown("### 📊 Dashboard de Auditoria")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Total de Notas", len(df))
                c2.metric("Total Aprovado", f"R$ {df[df['Status']=='APROVADO']['Valor (R$)'].sum():.2f}")
                c3.metric("Total Reprovado", f"R$ {df[df['Status']=='REPROVADO']['Valor (R$)'].sum():.2f}")

                col1, col2 = st.columns(2)
                with col1:
                    fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                   color_discrete_map={'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c', 'FALHA': '#95a5a6'})
                    st.plotly_chart(fig_bar, width='stretch')
                
                with col2:
                    fig_pie = px.pie(df, names='Status', values='Valor (R$)', hole=0.4)
                    st.plotly_chart(fig_pie, width='stretch')

                st.markdown("---")
                st.dataframe(df, width='stretch')
                
                csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 Baixar Relatório", csv, "auditoria.csv", "text/csv")
