# app.py - Canteiro Seguro APR Generator (VERSÃO DEFINITIVA)
# ======================================================================================

import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
import json
from datetime import datetime
import tempfile
import os
from google.oauth2 import service_account

# --------------------------------------------------------------------------------------
# CONFIGURAÇÃO INICIAL
# --------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Canteiro Seguro - APR Generator", 
    page_icon="🛡️", 
    layout="wide"
)

st.title("🛡️ Canteiro Seguro - Gerador de APR")
st.markdown("---")

# --------------------------------------------------------------------------------------
# CONFIGURAÇÕES (APENAS IDs PÚBLICOS)
# --------------------------------------------------------------------------------------

PROJECT_ID = "arctic-dynamo-467600-k9"
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash"

# --------------------------------------------------------------------------------------
# AUTENTICAÇÃO SEGURA (SEM CREDENCIAIS NO CÓDIGO)
# --------------------------------------------------------------------------------------

@st.cache_resource
def init_vertexai():
    """Inicialização segura usando apenas secrets do Streamlit"""
    try:
        if 'gcp_service_account' in st.secrets:
            # ✅ MÉTODO SEGURO: Credenciais apenas via Secrets
            credentials = service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"])
            )
            vertexai.init(
                project=PROJECT_ID, 
                location=LOCATION, 
                credentials=credentials
            )
            return True
        else:
            st.error("""
            ❌ Credenciais não encontradas!
            
            **Solução:**
            1. Acesse o Streamlit Cloud
            2. Vá em: Settings → Secrets  
            3. Cole suas credenciais do GCP
            """)
            return False
            
    except Exception as e:
        st.error(f"🔐 Erro de autenticação: {str(e)}")
        return False

# --------------------------------------------------------------------------------------
# FUNÇÃO PRINCIPAL - GERAR APR
# --------------------------------------------------------------------------------------

def gerar_apr_com_ia(descricao_atividade):
    """Gera análise de riscos usando Gemini"""
    try:
        model = GenerativeModel(MODEL_NAME)
        
        prompt = f"""
Você é um especialista em segurança do trabalho brasileiro, com profund conhecimento das NRs.
Gere uma APR (Análise Preliminar de Risco) completa e técnica para:

**ATIVIDADE:** {descricao_atividade}

**INSTRUÇÕES:**
- Retorne APENAS JSON válido
- Use a estrutura exata abaixo
- Inclua 3-4 etapas realistas de trabalho
- Cite NRs específicas (NR-35, NR-18, NR-10, etc.)
- Classifique riscos realisticamente (Baixo/Médio/Alto)

**ESTRUTURA JSON OBRIGATÓRIA:**
{{
  "titulo_apr": "APR - [Nome da Atividade]",
  "local": "Canteiro de Obras",
  "data_elaboracao": "DD/MM/AAAA",
  "etapas_e_riscos": [
    {{
      "etapa_tarefa": "Descrição detalhada da etapa 1",
      "perigos_identificados": ["Perigo 1", "Perigo 2"],
      "riscos_associados": ["Risco 1", "Risco 2"],
      "medidas_de_controle_recomendadas": ["Medida 1 - NR XX", "Medida 2 - NR YY"],
      "classificacao_risco_residual": "Médio"
    }}
  ],
  "epis_obrigatorios": ["EPI 1", "EPI 2", "EPI 3"],
  "procedimentos_emergencia": "Procedimentos completos para emergências"
}}

**EXEMPLOS DE NRs:**
- Trabalho em altura: NR-35
- Edificações: NR-18  
- Eletricidade: NR-10
- Máquinas: NR-12
- PCMAT: NR-18

Responda APENAS com o JSON válido.
"""

        with st.spinner("🔍 Analisando riscos com IA..."):
            response = model.generate_content(prompt)
            
            if response.text:
                # Extrair JSON de forma robusta
                texto = response.text.strip()
                inicio = texto.find('{')
                fim = texto.rfind('}') + 1
                
                if inicio >= 0 and fim > inicio:
                    json_str = texto[inicio:fim]
                    dados_apr = json.loads(json_str)
                    
                    # Validação básica
                    if not isinstance(dados_apr, dict):
                        raise ValueError("Estrutura de dados inválida")
                    
                    # Garantir campos essenciais
                    if not dados_apr.get("data_elaboracao"):
                        dados_apr["data_elaboracao"] = datetime.now().strftime("%d/%m/%Y")
                    
                    return dados_apr
                else:
                    st.error("📄 Estrutura JSON não encontrada na resposta")
                    return None
            else:
                st.error("🤖 Nenhuma resposta da IA")
                return None
                
    except json.JSONDecodeError as e:
        st.error(f"📋 Erro no JSON: {str(e)}")
        return None
    except Exception as e:
        st.error(f"⚡ Erro na geração: {str(e)}")
        return None

# --------------------------------------------------------------------------------------
# CRIAÇÃO DO DOCUMENTO WORD
# --------------------------------------------------------------------------------------

def criar_documento_word(dados_apr):
    """Cria documento Word profissional"""
    try:
        from docx import Document
        from docx.shared import Pt
        from docx.oxml.shared import OxmlElement
        from docx.oxml.ns import qn
        
        doc = Document()
        
        # Título principal
        titulo = doc.add_heading('ANÁLISE PRELIMINAR DE RISCO (APR)', 0)
        
        # Informações básicas
        info_style = doc.styles['Normal']
        info_style.paragraph_format.space_after = Pt(6)
        
        p = doc.add_paragraph()
        p.add_run('Título: ').bold = True
        p.add_run(dados_apr.get('titulo_apr', 'Análise de Risco'))
        
        p = doc.add_paragraph()
        p.add_run('Local: ').bold = True
        p.add_run(dados_apr.get('local', 'Canteiro de Obras'))
        
        p = doc.add_paragraph()
        p.add_run('Data de Elaboração: ').bold = True
        p.add_run(dados_apr.get('data_elaboracao', datetime.now().strftime('%d/%m/%Y')))
        
        doc.add_paragraph()  # Espaço
        
        # Tabela de etapas e riscos
        doc.add_heading('ETAPAS DA TAREFA, RISCOS E MEDIDAS DE CONTROLE', level=1)
        
        if dados_apr.get('etapas_e_riscos'):
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            
            # Cabeçalho com formatação
            headers = ['Etapa da Tarefa', 'Perigos Identificados', 'Riscos Associados', 
                      'Medidas de Controle', 'Risco Residual']
            
            hdr_cells = table.rows[0].cells
            for i, header in enumerate(headers):
                hdr_cells[i].text = header
                hdr_cells[i].paragraphs[0].runs[0].bold = True
                # Fundo cinza para cabeçalho
                tcPr = hdr_cells[i]._tc.get_or_add_tcPr()
                shading = OxmlElement('w:shd')
                shading.set(qn('w:fill'), 'D9D9D9')
                tcPr.append(shading)
            
            # Dados das etapas
            for etapa in dados_apr['etapas_e_riscos']:
                row_cells = table.add_row().cells
                row_cells[0].text = etapa.get('etapa_tarefa', 'N/A')
                row_cells[1].text = '\n'.join(etapa.get('perigos_identificados', ['N/A']))
                row_cells[2].text = '\n'.join(etapa.get('riscos_associados', ['N/A']))
                row_cells[3].text = '\n'.join(etapa.get('medidas_de_controle_recomendadas', ['N/A']))
                row_cells[4].text = etapa.get('classificacao_risco_residual', 'N/A')
        
        # EPIs Obrigatórios
        doc.add_heading('EQUIPAMENTOS DE PROTEÇÃO INDIVIDUAL (EPIs) OBRIGATÓRIOS', level=1)
        epis = dados_apr.get('epis_obrigatorios', [])
        if epis:
            for epi in epis:
                doc.add_paragraph(f'• {epi}', style='List Bullet')
        else:
            # EPIs padrão de segurança
            doc.add_paragraph('• Capacete de segurança', style='List Bullet')
            doc.add_paragraph('• Botina de segurança com biqueira de aço', style='List Bullet')
            doc.add_paragraph('• Óculos de proteção', style='List Bullet')
            doc.add_paragraph('• Luvas de proteção', style='List Bullet')
        
        # Procedimentos de Emergência
        doc.add_heading('PROCEDIMENTOS DE EMERGÊNCIA', level=1)
        procedimentos = dados_apr.get('procedimentos_emergencia', 
            "1. Acionar a brigada de emergência\n"
            "2. Isolar a área do incidente\n"
            "3. Prestar primeiros socorros\n"
            "4. Acionar bombeiros (193) se necessário\n"
            "5. Evacuar a área se houver risco iminente"
        )
        doc.add_paragraph(procedimentos)
        
        return doc
        
    except Exception as e:
        st.error(f"📄 Erro ao criar documento: {str(e)}")
        return None

# --------------------------------------------------------------------------------------
# INTERFACE PRINCIPAL
# --------------------------------------------------------------------------------------

def main():
    # Sidebar com informações
    with st.sidebar:
        st.title("⚙️ Configuração")
        
        # Status da autenticação
        if 'gcp_service_account' in st.secrets:
            st.success("✅ Credenciais configuradas")
            st.code(f"Projeto: {PROJECT_ID}")
        else:
            st.error("❌ Credenciais não encontradas")
            st.info("Configure as Secrets no Streamlit Cloud")
        
        st.markdown("---")
        st.markdown("""
        **📋 Como usar:**
        1. Descreva a atividade em detalhes
        2. Clique em **Gerar APR**
        3. Aguarde o processamento (10-30s)
        4. Baixe o documento Word
        
        **🛡️ Recursos:**
        - Análise automática de riscos
        - Baseada nas NRs brasileiras
        - Formatação profissional
        - Download em Word
        """)
        
        st.markdown("---")
        st.markdown("*Sistema desenvolvido para segurança do trabalho*")

    # Área principal
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📝 Descrição da Atividade")
        
        # Exemplo pré-preenchido para facilitar
        exemplo = "Trabalho em altura para instalação de balancim em prédio de 20 pavimentos, utilizando máquina projetora de argamassa e envolvendo equipe de 3 pessoas."
        
        descricao_atividade = st.text_area(
            "Descreva detalhadamente a atividade, equipamentos, materiais e condições:",
            value=exemplo,
            height=150,
            placeholder="Ex: Trabalho em altura, espaço confinado, solda elétrica, escavação..."
        )
    
    with col2:
        st.subheader("🚀 Ação")
        gerar_apr = st.button(
            "🛡️ Gerar APR", 
            type="primary", 
            use_container_width=True,
            help="Clique para gerar a análise de riscos"
        )
    
    # Processamento quando o botão é clicado
    if gerar_apr:
        if not descricao_atividade.strip():
            st.error("❌ Por favor, descreva a atividade para análise.")
            return
        
        # Inicialização segura
        with st.spinner("🔐 Conectando ao Google Cloud..."):
            if not init_vertexai():
                return
        
        # Processo principal com feedback visual
        with st.status("🎯 **Gerando sua APR...**", expanded=True) as status:
            try:
                # Etapa 1: Geração com IA
                status.update(label="🤖 Consultando especialista virtual...", state="running")
                dados_apr = gerar_apr_com_ia(descricao_atividade)
                
                if not dados_apr:
                    status.update(label="❌ Falha na geração", state="error")
                    return
                
                # Etapa 2: Criação do documento
                status.update(label="📄 Formatando documento profissional...", state="running")
                documento = criar_documento_word(dados_apr)
                
                if not documento:
                    status.update(label="❌ Erro no documento", state="error")
                    return
                
                status.update(label="✅ APR gerada com sucesso!", state="complete")
                
            except Exception as e:
                status.update(label="❌ Erro inesperado", state="error")
                st.error(f"Erro durante o processamento: {str(e)}")
                return
        
        # Download do documento
        if documento:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
                    documento.save(tmp_file.name)
                    
                    with open(tmp_file.name, "rb") as file:
                        st.success("🎉 **Análise de Risco concluída!**")
                        
                        # Botões de ação
                        col_download, col_novo = st.columns(2)
                        
                        with col_download:
                            st.download_button(
                                label="📥 Baixar Documento Word",
                                data=file,
                                file_name=f"APR_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                help="Clique para baixar a APR em formato Word"
                            )
                        
                        with col_novo:
                            if st.button("🔄 Nova Análise", use_container_width=True):
                                st.rerun()
                
                # Limpeza do arquivo temporário
                os.unlink(tmp_file.name)
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar download: {str(e)}")
        
        # Visualização dos dados (opcional)
        with st.expander("📊 Visualizar dados técnicos (JSON)"):
            st.json(dados_apr)

# --------------------------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
