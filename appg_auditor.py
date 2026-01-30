import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq Pro", layout="wide", page_icon="🛡️")

# --- LOGIN ---
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
            else:
                st.error("Credenciais inválidas")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Auditor Fiscal AI - Groq Edition")
st.caption("Engine: Llama 3.2 Vision (Ajustado para 2026)")

groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    st.header("⚙️ Configurações")
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.info("Solução: Fallback de Modelos Vision ativado.")

arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- TRATAMENTO DE IMAGEM ---
def preparar_imagem(upload):
    img = Image.open(upload)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- FUNÇÃO DE CHAMADA COM FALLBACK DINÂMICO ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Lista atualizada com os nomes de modelos válidos para Janeiro de 2026
    modelos_disponiveis = [
        "llama-3.2-11b-vision-preview", # Nome mais comum
        "llama-3.2-11b-vision-instant", # Versão acelerada (plano free)
        "llama-3.2-90b-vision-preview"  # Backup para contas Pro
    ]
    
    prompt = (
        f"Extraia os dados da nota fiscal. Responda APENAS no formato: "
        f"VALOR|ESTABELECIMENTO|CATEGORIA|STATUS. "
        f"Regra: Se valor total > {teto}, STATUS=REPROVADO, senão APROVADO."
    )
    
    log_erros = []
    
    for m in modelos_disponiveis:
        payload = {
            "model": m,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                ]
            }],
            "temperature": 0.1
        }
        
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                return r, m, None # Sucesso
            else:
                log_erros.append(f"{m}: {r.status_code}")
        except Exception as e:
            log_erros.append(f"{m}: {str(e)}")
            
    return None, None, f"Modelos testados falharam: {', '.join(log_erros)}"

# --- PROCESSAMENTO PRINCIPAL ---
if st.button("🚀 Iniciar Auditoria") and arquivos:
    if not groq_key:
        st.error("Chave API não encontrada nos Secrets do Streamlit.")
        st.stop()

    resultados = []
    barra = st.progress(0)
    msg = st.empty()

    for i, arq in enumerate(arquivos):
        msg.info(f"Analisando arquivo: {arq.name}")
        try:
            img_b64 = preparar_imagem(arq)
            res, m_ativo, erro_retornado = chamar_groq_vision(groq_key, img_b64, limite)
            
            if res:
                content = res.json()['choices'][0]['message']['content']
                partes = content.split('|')
                
                # Parsing Robusto
                v_raw = re.sub(r'[^\d.]', '', partes[0].replace(',', '.'))
                v_final = float(v_raw) if v_raw else 0.0
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": v_final,
                    "Local": partes[1].strip() if len(partes) > 1 else "N/D",
                    "Categoria": partes[2].strip() if len(partes) > 2 else "Geral",
                    "Status": partes[3].strip().upper() if len(partes) > 3 else "ERRO",
                    "Motor": m_ativo
                })
            else:
                st.error(f"Falha no arquivo {arq.name}: {erro_retornado}")
        except Exception as e:
            st.error(f"Erro inesperado em {arq.name}: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    msg.empty()

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        st.success(f"Processamento concluído com o modelo: {df['Motor'].iloc[0]}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                  color_discrete_map={'APROVADO':'#2ecc71', 'REPROVADO':'#e74c3c'}), 
                            use_container_width=True)
        with col2:
            st.plotly_chart(px.pie(df, names='Status', hole=0.4), use_container_width=True)
            
        st.subheader("📋 Relatório Detalhado")
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Baixar Planilha CSV", df.to_csv(index=False).encode('utf-8'), "auditoria_ia.csv", "text/csv")
