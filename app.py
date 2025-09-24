import io
import os
import streamlit as st
from pipeline import gerar_apr  # retorna (filename, bytes)

st.set_page_config(page_title="Gerador de APR - Canteiro Seguro", page_icon="📋", layout="centered")

st.title("📋 Gerador de APR - Canteiro Seguro")

atividade = st.text_area("📝 Atividade/Serviço:", placeholder="Ex.: Montagem de andaime metálico a 12 m do solo", height=100)

col1, col2 = st.columns([1,2])
with col1:
    gerar = st.button("🚀 Gerar APR", use_container_width=True)

status = st.empty()

if gerar:
    if not atividade.strip():
        st.warning("Digite a atividade/serviço.")
        st.stop()

    with st.spinner("Gerando APR com base nas NRs do bucket..."):
        try:
            filename, file_bytes = gerar_apr(atividade)
            st.success("APR gerada com sucesso!")
            st.download_button(
                "📥 Baixar APR (Word)",
                data=file_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"❌ Erro ao gerar APR: {e}")
            st.info("Verifique as credenciais (Secrets), permissões no bucket e limites de tokens.")
