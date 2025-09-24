# app.py - Canteiro Seguro APR Generator (VERSÃO SIMPLIFICADA E FUNCIONAL)
# ======================================================================================

import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel
from google.cloud import storage
import json
import numpy as np
from datetime import datetime
import tempfile
import os

# --------------------------------------------------------------------------------------
# CONFIGURAÇÃO INICIAL
# --------------------------------------------------------------------------------------

st.set_page_config(page_title="Canteiro Seguro - APR", page_icon="🛡️", layout="wide")
st.title("🛡️ Canteiro Seguro - Gerador de APR")
st.markdown("---")

# --------------------------------------------------------------------------------------
# CONFIGURAÇÕES (USE AS SUAS CREDENCIAIS REAIS AQUI)
# --------------------------------------------------------------------------------------

PROJECT_ID = "arctic-dynamo-467600-k9"
BUCKET_NAME = "documentos-apr-bruno-revisao01" 
LOCATION = "us-central1"

# --------------------------------------------------------------------------------------
# AUTENTICAÇÃO SIMPLIFICADA
# --------------------------------------------------------------------------------------

@st.cache_resource
def init_vertexai():
    """Inicialização mais simples e robusta"""
    try:
        # Método 1: Tentar com credentials do secrets
        if 'gcp_service_account' in st.secrets:
            import json
            from google.oauth2 import service_account
            
            # Cria arquivo temporário com as credenciais
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
            
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
            st.success("✅ Autenticado via Secrets!")
            return True
            
        # Método 2: Tentar autenticação padrão (para desenvolvimento)
        else:
            vertexai.init(project=PROJECT_ID, location=LOCATION)
            st.success("✅ Autenticado via ambiente padrão!")
            return True
            
    except Exception as e:
        st.error(f"❌ Erro de autenticação: {str(e)}")
        st.info("💡 Dica: Verifique se as credenciais no Streamlit Secrets estão corretas.")
        return False

# --------------------------------------------------------------------------------------
# FUNÇÕES PRINCIPAIS (VERSÃO SIMPLIFICADA)
# --------------------------------------------------------------------------------------

def gerar_apr_simples(tarefa):
    """Gera APR usando IA sem RAG complexo (versão simplificada)"""
    try:
        model = GenerativeModel("gemini-1.5-flash-001")
        
        prompt = f"""
Você é um especialista em segurança do trabalho. Crie uma APR (Análise Preliminar de Risco) para:

ATIVIDADE: {tarefa}

Retorne APENAS um JSON válido com esta estrutura:

{{
  "titulo_apr": "Título da APR",
  "local": "Local da atividade", 
  "data_elaboracao": "Data",
  "etapas_e_riscos": [
    {{
      "etapa_tarefa": "Descrição da etapa",
      "perigos_identificados": ["Perigo 1", "Perigo 2"],
      "riscos_associados": ["Risco 1", "Risco 2"],
      "medidas_de_controle_recomendadas": ["Medida 1 - NR XX", "Medida 2 - NR YY"],
      "classificacao_risco_residual": "Médio"
    }}
  ],
  "epis_obrigatorios": ["Capacete", "Botinas", "Óculos"],
  "procedimentos_emergencia": "Procedimentos de emergência padrão"
}}

Regras:
- Se envolve altura: inclua cinto de segurança
- Se envolve eletricidade: inclua luvas isolantes  
- Mantenha o JSON válido!
"""

        response = model.generate_content(prompt)
        
        if response.text:
            # Extrair JSON
            text = response.text.strip()
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > 0:
                json_str = text[start:end]
                dados = json.loads(json_str)
                return dados
                
        return None
        
    except Exception as e:
        st.error(f"Erro na geração: {e}")
        return None

def criar_documento_word(dados):
    """Cria documento Word simples"""
    from docx import Document
    from docx.shared import Pt
    
    try:
        doc = Document()
        
        # Cabeçalho
        doc.add_heading('ANÁLISE PRELIMINAR DE RISCO (APR)', 0)
        
        # Informações básicas
        doc.add_paragraph().add_run('Título: ').bold = True
        doc.add_paragraph(dados.get('titulo_apr', 'Não especificado'))
        
        doc.add_paragraph().add_run('Local: ').bold = True  
        doc.add_paragraph(dados.get('local', 'Não especificado'))
        
        doc.add_paragraph().add_run('Data: ').bold = True
        doc.add_paragraph(dados.get('data_elaboracao', datetime.now().strftime('%d/%m/%Y')))
        
        # Tabela de riscos
        doc.add_heading('Etapas e Riscos', level=2)
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        
        # Cabeçalho
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Etapa'
        hdr_cells[1].text = 'Riscos'
        hdr_cells[2].text = 'Medidas'
        
        # Dados
        for etapa in dados.get('etapas_e_riscos', []):
            row_cells = table.add_row().cells
            row_cells[0].text = etapa.get('etapa_tarefa', '')
            row_cells[1].text = '\n'.join(etapa.get('riscos_associados', []))
            row_cells[2].text = '\n'.join(etapa.get('medidas_de_controle_recomendadas', []))
        
        # EPIs
        doc.add_heading('EPIs Obrigatórios', level=2)
        for epi in dados.get('epis_obrigatorios', []):
            doc.add_paragraph(f'• {epi}', style='List Bullet')
            
        # Emergência
        doc.add_heading('Procedimentos de Emergência', level=2)
        doc.add_paragraph(dados.get('procedimentos_emergencia', ''))
        
        return doc
        
    except Exception as e:
        st.error(f"Erro ao criar documento: {e}")
        return None

# --------------------------------------------------------------------------------------
# INTERFACE PRINCIPAL
# --------------------------------------------------------------------------------------

def main():
    st.sidebar.title("⚙️ Configuração")
    
    # Verificação de credenciais
    if 'gcp_service_account' in st.secrets:
        st.sidebar.success("✅ Credenciais encontradas")
        st.sidebar.code(f"Projeto: {PROJECT_ID}")
    else:
        st.sidebar.error("❌ Credenciais não encontradas")
        st.sidebar.info("Configure as secrets no Streamlit Cloud")
    
    st.sidebar.markdown("---")
    st.sidebar.info("""
    **📝 Como usar:**
    1. Descreva a atividade
    2. Clique em Gerar APR  
    3. Aguarde o processamento
    4. Baixe o documento
    """)
    
    # Área principal
    st.subheader("📋 Descreva a atividade")
    
    tarefa = st.text_area(
        "Descreva a atividade para análise de riscos:",
        height=100,
        placeholder="Ex: Trabalho em altura para instalação de balancim em prédio de 20 andares..."
    )
    
    if st.button("🛡️ Gerar APR", type="primary", use_container_width=True):
        if not tarefa.strip():
            st.error("❌ Por favor, descreva a atividade.")
            return
            
        # Inicializar Vertex AI
        if not init_vertexai():
            st.error("❌ Falha na autenticação. Verifique as credenciais.")
            return
            
        # Gerar APR
        with st.status("🎯 Gerando APR...", expanded=True) as status:
            try:
                status.update(label="🤖 Consultando IA...", state="running")
                dados_apr = gerar_apr_simples(tarefa)
                
                if not dados_apr:
                    st.error("❌ Erro ao gerar a APR.")
                    return
                    
                status.update(label="📄 Criando documento...", state="running") 
                documento = criar_documento_word(dados_apr)
                
                if not documento:
                    st.error("❌ Erro ao criar documento.")
                    return
                    
                status.update(label="✅ Concluído!", state="complete")
                
            except Exception as e:
                status.update(label="❌ Erro", state="error")
                st.error(f"Erro no processo: {e}")
                return
                
        # Download
        if documento:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
                    documento.save(tmp_file.name)
                    
                    with open(tmp_file.name, "rb") as file:
                        st.success("🎉 APR gerada com sucesso!")
                        
                        st.download_button(
                            label="📥 Baixar APR",
                            data=file,
                            file_name="APR_GERADA.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
                
                os.unlink(tmp_file.name)
                
            except Exception as e:
                st.error(f"❌ Erro ao salvar: {e}")
                
        # Preview
        with st.expander("👀 Visualizar dados"):
            st.json(dados_apr)

if __name__ == "__main__":
    main()
