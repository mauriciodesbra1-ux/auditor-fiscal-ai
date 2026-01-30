import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Scanner de Modelos Gemini", layout="wide")

st.title("🔍 Scanner de Permissões Gemini")

# Recupera a chave
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    api_key = st.sidebar.text_input("Google API Key", type="password")

if api_key:
    try:
        genai.configure(api_key=api_key)
        
        st.subheader("Modelos disponíveis para sua conta:")
        modelos_validos = []
        
        # O pulo do gato: Listar o que a sua chave realmente alcança
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos_validos.append(m.name)
                st.write(f"✅ **{m.name}** - Suporta Visão/Conteúdo")
        
        if modelos_validos:
            st.success(f"Tente usar este nome no seu código: `{modelos_validos[0]}`")
        else:
            st.error("Sua chave não tem modelos de geração habilitados. Verifique o faturamento.")
            
    except Exception as e:
        st.error(f"Erro ao listar modelos: {e}")
        if "API_KEY_INVALID" in str(e):
            st.info("Sua API Key parece estar incorreta.")
else:
    st.info("Insira a API Key na barra lateral para escanear.")
