# app.py - Canteiro Seguro APR Generator
# ======================================================================================

import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel
from google.cloud import storage
from sklearn.metrics.pairwise import cosine_similarity
import docx
from docx.shared import Pt
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
import json
import numpy as np
from datetime import datetime
import pypdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tempfile
import os
from google.oauth2 import service_account

# --------------------------------------------------------------------------------------
# CONFIGURAÇÃO INICIAL DO STREAMLIT
# --------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Canteiro Seguro - APR Generator",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Canteiro Seguro - Gerador de APR")
st.markdown("---")

# --------------------------------------------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------------------------------------------

PROJECT_ID = "arctic-dynamo-467600-k9"
BUCKET_NAME = "documentos-apr-bruno-revisao01"
LOCATION = "us-central1"
MODELO_DE_EMBEDDING = "text-embedding-004"
MODELO_DE_GERACAO = "gemini-2.5-flash"
TOP_K_RAG = 3
NOME_DO_ARQUIVO_FINAL = "APR_FINALMENTE_PREENCHIDA.docx"

# --------------------------------------------------------------------------------------
# FUNÇÕES PRINCIPAIS
# --------------------------------------------------------------------------------------

@st.cache_resource
def init_vertexai():
    """Inicializa o Vertex AI com as credenciais do GCP"""
    try:
        if 'gcp_service_account' in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
        else:
            # Para desenvolvimento local
            credentials = None
        
        vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
        st.success("✅ Vertex AI inicializado com sucesso!")
        return True
    except Exception as e:
        st.error(f"❌ Erro na inicialização do Vertex AI: {e}")
        return False

def processar_pdfs():
    """Processa PDFs do bucket GCS e retorna chunks de texto"""
    try:
        if 'gcp_service_account' in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            storage_client = storage.Client(credentials=credentials, project=PROJECT_ID)
        else:
            storage_client = storage.Client(project=PROJECT_ID)
            
        bucket = storage_client.bucket(BUCKET_NAME)
        all_chunks = []
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        MAX_CHARS = 4000

        # Listar PDFs do bucket
        pdf_blobs = [blob for blob in bucket.list_blobs() if blob.name.lower().endswith('.pdf')]
        
        if not pdf_blobs:
            st.warning("⚠️ Nenhum PDF encontrado no bucket.")
            return []

        # Barra de progresso
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, blob in enumerate(pdf_blobs):
            try:
                status_text.text(f"📖 Lendo: {blob.name}")
                with blob.open("rb") as pdf_file:
                    pdf_reader = pypdf.PdfReader(pdf_file)
                    pdf_text = ""
                    
                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text:
                            pdf_text += text + "\n"

                    if not pdf_text.strip():
                        st.warning(f"📄 PDF sem texto legível: {blob.name}")
                        continue

                    # Dividir em chunks
                    chunks = text_splitter.split_text(pdf_text)
                    safe_chunks = [c[:MAX_CHARS] if len(c) > MAX_CHARS else c for c in chunks]
                    
                    for chunk in safe_chunks:
                        all_chunks.append({"source": blob.name, "content": chunk})

                progress_bar.progress((i + 1) / len(pdf_blobs))
                
            except Exception as e:
                st.warning(f"⚠️ Erro ao processar {blob.name}: {str(e)}")
                continue

        status_text.text(f"✅ Processamento concluído! {len(all_chunks)} chunks gerados.")
        return all_chunks

    except Exception as e:
        st.error(f"❌ Erro ao acessar o bucket: {e}")
        return []

def gerar_embeddings(all_chunks):
    """Gera embeddings para os chunks de texto"""
    try:
        embedding_model = TextEmbeddingModel.from_pretrained(MODELO_DE_EMBEDDING)
        vectors = []
        batch_texts = []
        current_size = 0
        MAX_BATCH_CHARS = 15000

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, chunk in enumerate(all_chunks):
            text = chunk["content"]
            
            if current_size + len(text) > MAX_BATCH_CHARS and batch_texts:
                # Processar batch atual
                res = embedding_model.get_embeddings(batch_texts)
                vectors.extend([e.values for e in res])
                batch_texts = []
                current_size = 0
            
            batch_texts.append(text)
            current_size += len(text)
            
            progress_bar.progress((i + 1) / len(all_chunks))
            status_text.text(f"🔢 Vetorizando: {i+1}/{len(all_chunks)}")

        # Processar último batch
        if batch_texts:
            res = embedding_model.get_embeddings(batch_texts)
            vectors.extend([e.values for e in res])

        status_text.text("✅ Vetorização concluída!")
        return np.array(vectors)

    except Exception as e:
        st.error(f"❌ Erro na geração de embeddings: {e}")
        return None

def executar_rag(tarefa_usuario, all_chunks, embeddings_array):
    """Executa o processo RAG para recuperar contexto relevante"""
    try:
        embedding_model = TextEmbeddingModel.from_pretrained(MODELO_DE_EMBEDDING)
        
        # Gerar embedding da query
        query_embedding = embedding_model.get_embeddings([tarefa_usuario])[0].values
        
        # Calcular similaridades
        similarities = cosine_similarity([query_embedding], embeddings_array)[0]
        top_indices = similarities.argsort()[-TOP_K_RAG:][::-1]
        selecionados = [all_chunks[i] for i in top_indices]

        # Resumir chunks selecionados
        gen = GenerativeModel(MODELO_DE_GERACAO)
        resumos = []
        
        for i, chunk_info in enumerate(selecionados):
            with st.spinner(f"📝 Resumindo contexto {i+1}/{len(selecionados)}..."):
                resumo_prompt = f"""
Resuma tecnicamente este trecho em até 80 palavras, preservando informações sobre:
- Riscos identificados
- Medidas de controle
- Citações de NRs
- Procedimentos de segurança

Texto:
{chunk_info['content'][:2000]}
"""
                resumo_resp = gen.generate_content(resumo_prompt)
                if resumo_resp and resumo_resp.text:
                    resumos.append(f"Fonte: {chunk_info['source']}\nResumo: {resumo_resp.text.strip()[:500]}")

        contexto_recuperado = "\n---\n".join(resumos)
        if len(contexto_recuperado) > 3000:
            contexto_recuperado = contexto_recuperado[:3000] + "... [texto truncado]"

        return contexto_recuperado

    except Exception as e:
        st.error(f"❌ Erro no processo RAG: {e}")
        return ""

def gerar_apr_com_ia(tarefa_usuario, contexto_recuperado):
    """Gera a APR usando IA com base na tarefa e contexto"""
    try:
        gen = GenerativeModel(MODELO_DE_GERACAO)
        data_str = datetime.now().strftime("%d/%m/%Y")
        
        json_exemplo = '''{
  "titulo_apr": "APR - [NOME DA ATIVIDADE]",
  "local": "Local da atividade",
  "data_elaboracao": "DATA",
  "etapas_e_riscos": [
    {
      "etapa_tarefa": "Descrição da etapa",
      "perigos_identificados": ["Perigo 1", "Perigo 2"],
      "riscos_associados": ["Risco 1", "Risco 2"],
      "medidas_de_controle_recomendadas": ["Medida 1 - NR XX", "Medida 2 - NR YY"],
      "classificacao_risco_residual": "Baixo/Médio/Alto"
    }
  ],
  "epis_obrigatorios": ["EPI 1", "EPI 2"],
  "procedimentos_emergencia": "Descrição dos procedimentos"
}'''

        prompt_final = f"""
# CONTEXTO TÉCNICO (Baseado em normas de segurança):
{contexto_recuperado}

# ATIVIDADE A SER ANALISADA:
{tarefa_usuario}

# INSTRUÇÕES:
Você é um especialista em segurança do trabalho. Gere uma Análise Preliminar de Risco (APR) em formato JSON seguindo EXATAMENTE a estrutura abaixo:

{json_exemplo}

# REGRAS OBRIGATÓRIAS:
1. Preencha TODOS os campos do JSON
2. "epis_obrigatorios" deve conter pelo menos 3 EPIs básicos se não houver especificações
3. Cite as NRs relevantes nas medidas de controle
4. Classifique o risco residual de forma realista (Baixo/Médio/Alto)
5. Inclua procedimentos de emergência mínimos se não especificados

Responda APENAS com o JSON válido, sem texto adicional.
"""

        with st.spinner("🤖 Gerando análise de riscos com IA..."):
            response = gen.generate_content(prompt_final)
            
            if not response.text:
                raise ValueError("Resposta vazia da IA")

            # Extrair JSON da resposta
            txt = response.text.strip()
            start, end = txt.find('{'), txt.rfind('}') + 1
            
            if start == -1 or end == 0:
                raise ValueError("JSON não encontrado na resposta")
                
            json_str = txt[start:end]
            dados_da_apr = json.loads(json_str)

            # Validação e pós-processamento
            if not isinstance(dados_da_apr, dict):
                raise ValueError("Estrutura de dados inválida")

            # Garantir campos obrigatórios
            if not dados_da_apr.get("epis_obrigatorios"):
                dados_da_apr["epis_obrigatorios"] = ["Capacete de segurança", "Botina de segurança", "Óculos de proteção"]

            if not dados_da_apr.get("procedimentos_emergencia"):
                dados_da_apr["procedimentos_emergencia"] = "Acionar brigada de emergência, isolar a área, prestar primeiros socorros e contactar bombeiros (193) se necessário."

            if not dados_da_apr.get("data_elaboracao"):
                dados_da_apr["data_elaboracao"] = data_str

            if not dados_da_apr.get("titulo_apr"):
                dados_da_apr["titulo_apr"] = f"APR - {tarefa_usuario[:50]}..."

            return dados_da_apr

    except json.JSONDecodeError as e:
        st.error(f"❌ Erro ao decodificar JSON: {e}")
        st.code(response.text if 'response' in locals() else "Resposta não disponível")
        return None
    except Exception as e:
        st.error(f"❌ Erro na geração da APR: {e}")
        return None

def criar_documento_word(dados_da_apr):
    """Cria o documento Word formatado com os dados da APR"""
    try:
        doc = docx.Document()

        # Título principal
        title = doc.add_heading('ANÁLISE PRELIMINAR DE RISCO (APR)', level=1)
        title.alignment = 1  # Centralizado

        # Informações básicas
        doc.add_paragraph()  # Espaço

        p = doc.add_paragraph()
        p.add_run('Título: ').bold = True
        p.add_run(dados_da_apr.get("titulo_apr", "Não especificado"))

        p = doc.add_paragraph()
        p.add_run('Local: ').bold = True
        p.add_run(dados_da_apr.get("local", "Não especificado"))

        p = doc.add_paragraph()
        p.add_run('Data de elaboração: ').bold = True
        p.add_run(dados_da_apr.get("data_elaboracao", "Não especificado"))

        doc.add_paragraph()  # Espaço

        # Tabela de etapas e riscos
        doc.add_heading('ETAPAS DA TAREFA, RISCOS E MEDIDAS DE CONTROLE', level=2)

        if dados_da_apr.get("etapas_e_riscos"):
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            
            # Cabeçalho
            headers = [
                "Etapa da Tarefa", 
                "Perigos Identificados", 
                "Riscos Associados",
                "Medidas de Controle", 
                "Risco Residual"
            ]
            
            hdr_cells = table.rows[0].cells
            for i, header in enumerate(headers):
                hdr_cells[i].text = header
                hdr_cells[i].paragraphs[0].runs[0].bold = True
                hdr_cells[i].paragraphs[0].alignment = 1  # Centralizado
                
                # Fundo cinza para cabeçalho
                shading_elm = parse_xml(r'<w:shd {} w:fill="D9D9D9"/>'.format(nsdecls('w')))
                hdr_cells[i]._tc.get_or_add_tcPr().append(shading_elm)

            # Dados
            for etapa in dados_da_apr["etapas_e_riscos"]:
                row_cells = table.add_row().cells
                
                row_cells[0].text = etapa.get("etapa_tarefa", "N/A")
                row_cells[1].text = "\n".join(etapa.get("perigos_identificados", ["N/A"]))
                row_cells[2].text = "\n".join(etapa.get("riscos_associados", ["N/A"]))
                row_cells[3].text = "\n".join(etapa.get("medidas_de_controle_recomendadas", ["N/A"]))
                row_cells[4].text = etapa.get("classificacao_risco_residual", "N/A")

                # Formatação das células
                for cell in row_cells:
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_after = Pt(6)
        else:
            doc.add_paragraph("Nenhuma etapa de risco identificada.")

        doc.add_paragraph()  # Espaço

        # EPIs
        doc.add_heading('EQUIPAMENTOS DE PROTEÇÃO INDIVIDUAL (EPIs) OBRIGATÓRIOS', level=2)
        epis = dados_da_apr.get("epis_obrigatorios", [])
        if epis:
            for epi in epis:
                doc.add_paragraph(f"• {epi}", style="List Bullet")
        else:
            doc.add_paragraph("Nenhum EPI específico identificado.")

        doc.add_paragraph()  # Espaço

        # Procedimentos de emergência
        doc.add_heading('PROCEDIMENTOS DE EMERGÊNCIA', level=2)
        doc.add_paragraph(dados_da_apr.get("procedimentos_emergencia", "Procedimentos padrão de emergência devem ser seguidos."))

        return doc

    except Exception as e:
        st.error(f"❌ Erro ao criar documento Word: {e}")
        return None

# --------------------------------------------------------------------------------------
# INTERFACE PRINCIPAL
# --------------------------------------------------------------------------------------

def main():
    # Sidebar
    with st.sidebar:
        st.title("ℹ️ Configurações")
        
        st.markdown("""
        **Como usar:**
        1. 📝 Descreva a atividade
        2. 🚀 Clique em Gerar APR
        3. ⏳ Aguarde o processamento
        4. 📥 Baixe o documento
        
        **Recursos:**
        - Análise automática de riscos
        - Base em normas técnicas
        - Formatação profissional
        - Download em Word
        """)
        
        st.markdown("---")
        st.markswith("**Configurações técnicas:**")
        st.code(f"""
        Projeto: {PROJECT_ID}
        Bucket: {BUCKET_NAME}
        Modelo: {MODELO_DE_GERACAO}
        """)

    # Área principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Descrição da Atividade")
        tarefa_usuario = st.text_area(
            "Descreva detalhadamente a atividade ou serviço para análise de riscos:",
            placeholder="Ex: Trabalho em altura para instalação de equipamentos em torre de comunicação de 20 metros, envolvendo solda elétrica e manuseio de ferramentas pesadas...",
            height=120,
            key="tarefa_input"
        )
        
        # Configurações avançadas
        with st.expander("⚙️ Configurações Avançadas"):
            st.number_input("Número de referências técnicas", min_value=1, max_value=5, value=3, key="top_k")
            st.checkbox("Incluir resumo executivo", value=True, key="incluir_resumo")
            st.checkbox("Validar com normas técnicas", value=True, key="validar_normas")

    with col2:
        st.subheader("🚀 Ações")
        if st.button("🛡️ Gerar APR", type="primary", use_container_width=True):
            if not tarefa_usuario.strip():
                st.error("❌ Por favor, descreva a atividade antes de gerar a APR.")
                return

            # Inicializar Vertex AI
            if not init_vertexai():
                st.error("❌ Falha na inicialização. Verifique as credenciais.")
                return

            # Processo principal com status
            with st.status("🎯 Iniciando processo de geração da APR...", expanded=True) as status:
                try:
                    # Etapa 1: Processar PDFs
                    status.update(label="📚 Processando documentos técnicos...", state="running")
                    all_chunks = processar_pdfs()
                    
                    if not all_chunks:
                        st.error("❌ Não foi possível carregar documentos de referência.")
                        return

                    # Etapa 2: Gerar embeddings
                    status.update(label="🔢 Analisando conteúdo técnico...", state="running")
                    embeddings_array = gerar_embeddings(all_chunks)
                    
                    if embeddings_array is None:
                        st.error("❌ Erro na análise de conteúdo.")
                        return

                    # Etapa 3: Buscar contexto relevante
                    status.update(label="🔍 Buscando informações específicas...", state="running")
                    contexto_recuperado = executar_rag(tarefa_usuario, all_chunks, embeddings_array)

                    # Etapa 4: Gerar APR com IA
                    status.update(label="🤖 Gerando análise de riscos...", state="running")
                    dados_apr = gerar_apr_com_ia(tarefa_usuario, contexto_recuperado)
                    
                    if dados_apr is None:
                        st.error("❌ Erro na geração da análise.")
                        return

                    # Etapa 5: Criar documento
                    status.update(label="📄 Formatando documento final...", state="running")
                    documento = criar_documento_word(dados_apr)
                    
                    if documento is None:
                        st.error("❌ Erro na formatação do documento.")
                        return

                    status.update(label="✅ APR gerada com sucesso!", state="complete")

                except Exception as e:
                    status.update(label="❌ Erro no processo", state="error")
                    st.error(f"Erro durante a geração: {e}")
                    return

            # Salvar e disponibilizar download
            if 'documento' in locals() and documento:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
                        documento.save(tmp_file.name)
                        
                        with open(tmp_file.name, "rb") as file:
                            st.success("🎉 APR gerada com sucesso!")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.download_button(
                                    label="📥 Download da APR",
                                    data=file,
                                    file_name=NOME_DO_ARQUIVO_FINAL,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    use_container_width=True
                                )
                            
                            with col2:
                                if st.button("🔄 Gerar nova APR", use_container_width=True):
                                    st.rerun()
                    
                    # Limpeza do arquivo temporário
                    os.unlink(tmp_file.name)

                except Exception as e:
                    st.error(f"❌ Erro ao salvar documento: {e}")

            # Visualização dos dados gerados
            with st.expander("📊 Visualizar dados gerados"):
                st.json(dados_apr)

        # Informações de uso
        st.markdown("---")
        st.info("""
        **💡 Dicas:**
        - Seja específico na descrição da atividade
        - Inclua altura, equipamentos, materiais
        - Mentione condições especiais de trabalho
        - O sistema usa IA baseada em normas técnicas
        """)

if __name__ == "__main__":
    main()
