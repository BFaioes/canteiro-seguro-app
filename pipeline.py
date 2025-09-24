import streamlit as st
import json
import logging
import os
import tempfile
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import io

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_gcp_credentials() -> Optional[Dict[str, Any]]:
    """
    Função ULTRA ROBUSTA para obter credenciais GCP
    """
    try:
        if "gcp" not in st.secrets:
            st.error("❌ Seção 'gcp' não encontrada nos secrets do Streamlit")
            return None

        gcp_config = st.secrets["gcp"]
        
        # ESTRATÉGIA 1: Campos individuais na raiz de [gcp]
        if "type" in gcp_config:
            logger.info("✅ Usando estratégia 1: campos individuais")
            
            credentials = {
                "type": gcp_config["type"],
                "project_id": gcp_config["project_id"],
                "private_key_id": gcp_config["private_key_id"],
                "private_key": gcp_config["private_key"],
                "client_email": gcp_config["client_email"],
                "client_id": gcp_config["client_id"],
                "auth_uri": gcp_config["auth_uri"],
                "token_uri": gcp_config["token_uri"],
                "auth_provider_x509_cert_url": gcp_config["auth_provider_x509_cert_url"],
                "client_x509_cert_url": gcp_config["client_x509_cert_url"],
                "universe_domain": gcp_config["universe_domain"]
            }
            
            # Validar campos essenciais
            required_fields = ["type", "project_id", "private_key", "client_email"]
            for field in required_fields:
                if not credentials.get(field):
                    st.error(f"❌ Campo obrigatório '{field}' está vazio")
                    return None
            
            return credentials
        
        # ESTRATÉGIA 2: credentials_safe
        elif "credentials_safe" in gcp_config:
            return dict(gcp_config["credentials_safe"])
        
        # ESTRATÉGIA 3: credentials como JSON string
        elif "credentials" in gcp_config:
            credentials_raw = gcp_config["credentials"]
            
            if isinstance(credentials_raw, dict):
                return credentials_raw
            
            if isinstance(credentials_raw, str):
                try:
                    clean_json = credentials_raw.strip()
                    if clean_json.startswith('"') and clean_json.endswith('"'):
                        clean_json = clean_json[1:-1]
                    clean_json = clean_json.replace('\\"', '"')
                    return json.loads(clean_json)
                except json.JSONDecodeError as e:
                    st.error(f"❌ Erro no parse do JSON: {e}")
                    return None
        
        st.error("❌ Nenhum formato válido de credenciais encontrado")
        return None
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao carregar credenciais: {e}")
        return None


def setup_gcp_credentials() -> bool:
    """
    Configura as credenciais GCP para uso na aplicação
    """
    try:
        credentials = get_gcp_credentials()
        if credentials is None:
            return False
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(credentials, temp_file, indent=2)
            temp_credentials_path = temp_file.name
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
        logger.info("✅ Credenciais GCP configuradas com sucesso!")
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao configurar credenciais: {e}")
        return False


def get_gcp_config() -> Dict[str, str]:
    """Retorna configurações básicas do GCP"""
    try:
        return {
            "project_id": st.secrets["gcp"]["project_id"],
            "location": st.secrets["gcp"]["location"],
            "bucket_name": st.secrets["gcp"]["bucket_name"]
        }
    except KeyError as e:
        st.error(f"❌ Configuração GCP ausente: {e}")
        return {}


def test_gcp_connection() -> bool:
    """Testa a conexão com o Google Cloud Storage"""
    try:
        from google.cloud import storage
        
        config = get_gcp_config()
        if not config:
            return False
        
        client = storage.Client(project=config["project_id"])
        bucket = client.bucket(config["bucket_name"])
        
        if bucket.exists():
            st.success(f"✅ Conexão estabelecida com o bucket: {config['bucket_name']}")
            return True
        else:
            st.error(f"❌ Bucket não encontrado: {config['bucket_name']}")
            return False
            
    except Exception as e:
        st.error(f"❌ Erro na conexão GCP: {e}")
        return False


def criar_pdf_apr(dados_apr: Dict[str, Any]) -> bytes:
    """
    Cria um PDF da APR usando reportlab
    """
    try:
        from reportlab.lib.pagesizes import A4, letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        
    except ImportError:
        st.error("❌ Biblioteca reportlab não instalada. Instalando...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
        
        # Tentar importar novamente
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    
    # Buffer para o PDF
    buffer = io.BytesIO()
    
    # Criar documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.darkblue
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=TA_JUSTIFY
    )
    
    # Conteúdo do documento
    story = []
    
    # Título
    story.append(Paragraph("ANÁLISE PRELIMINAR DE RISCOS (APR)", title_style))
    story.append(Spacer(1, 20))
    
    # Informações básicas
    info_data = [
        ["PROJETO:", dados_apr.get("projeto_nome", "")],
        ["LOCAL:", dados_apr.get("local_obra", "")],
        ["RESPONSÁVEL:", dados_apr.get("responsavel", "")],
        ["DATA INÍCIO:", dados_apr.get("data_inicio", "")],
        ["DATA TÉRMINO:", dados_apr.get("data_fim", "")],
        ["TIPO DE ATIVIDADE:", dados_apr.get("tipo_atividade", "")],
        ["DATA DE ELABORAÇÃO:", datetime.now().strftime("%d/%m/%Y %H:%M")]
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Descrição da Atividade
    story.append(Paragraph("1. DESCRIÇÃO DA ATIVIDADE", heading_style))
    descricao_text = dados_apr.get("descricao_atividade", "Não informado")
    story.append(Paragraph(descricao_text, normal_style))
    story.append(Spacer(1, 15))
    
    # Riscos Identificados
    story.append(Paragraph("2. RISCOS IDENTIFICADOS", heading_style))
    riscos_text = dados_apr.get("riscos", "Não informado")
    # Processar lista de riscos
    riscos_list = riscos_text.split('\n')
    for risco in riscos_list:
        if risco.strip():
            story.append(Paragraph(f"• {risco.strip()}", normal_style))
    story.append(Spacer(1, 15))
    
    # Medidas de Controle
    story.append(Paragraph("3. MEDIDAS DE CONTROLE E PREVENÇÃO", heading_style))
    medidas_text = dados_apr.get("medidas_controle", "Não informado")
    # Processar lista de medidas
    medidas_list = medidas_text.split('\n')
    for medida in medidas_list:
        if medida.strip():
            story.append(Paragraph(f"• {medida.strip()}", normal_style))
    story.append(Spacer(1, 20))
    
    # Matriz de Riscos (exemplo)
    story.append(Paragraph("4. MATRIZ DE RISCOS", heading_style))
    
    matriz_data = [
        ["RISCO", "PROBABILIDADE", "SEVERIDADE", "CLASSIFICAÇÃO", "MEDIDAS"],
        ["Queda em altura", "MÉDIA", "ALTA", "CRÍTICO", "EPI, Guarda-corpo"],
        ["Choque elétrico", "BAIXA", "ALTA", "MODERADO", "Desenergização"],
        ["Cortes", "MÉDIA", "MÉDIA", "MODERADO", "EPI, Treinamento"]
    ]
    
    matriz_table = Table(matriz_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
    matriz_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    story.append(matriz_table)
    story.append(Spacer(1, 30))
    
    # Assinaturas
    story.append(Paragraph("5. RESPONSABILIDADES E APROVAÇÕES", heading_style))
    story.append(Spacer(1, 20))
    
    assinatura_data = [
        ["ELABORADO POR:", "APROVADO POR:", "DATA:"],
        ["", "", ""],
        ["_________________________", "_________________________", "_________________"],
        [dados_apr.get("responsavel", ""), "Supervisor de Segurança", datetime.now().strftime("%d/%m/%Y")]
    ]
    
    assinatura_table = Table(assinatura_data, colWidths=[2*inch, 2*inch, 1.5*inch])
    assinatura_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(assinatura_table)
    
    # Footer
    story.append(Spacer(1, 40))
    story.append(Paragraph("Este documento deve ser revisado antes do início das atividades e sempre que houver mudanças nas condições de trabalho.", normal_style))
    
    # Construir PDF
    doc.build(story)
    
    # Retornar bytes
    buffer.seek(0)
    return buffer.getvalue()


def salvar_no_gcs(filename: str, file_bytes: bytes) -> bool:
    """
    Salva o arquivo no Google Cloud Storage
    """
    try:
        from google.cloud import storage
        
        config = get_gcp_config()
        if not config:
            return False
        
        # Criar cliente
        client = storage.Client(project=config["project_id"])
        bucket = client.bucket(config["bucket_name"])
        
        # Upload do arquivo
        blob = bucket.blob(filename)
        blob.upload_from_string(file_bytes, content_type='application/pdf')
        
        logger.info(f"✅ Arquivo salvo no GCS: {filename}")
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao salvar no GCS: {e}")
        return False


def gerar_apr(dados_apr: Dict[str, Any]) -> Tuple[Optional[str], Optional[bytes]]:
    """
    Função principal para gerar APR
    Retorna (filename, bytes) ou (None, None) em caso de erro
    """
    try:
        st.info("🔄 Iniciando geração da APR...")
        
        # Validar entrada
        if not dados_apr or not isinstance(dados_apr, dict):
            st.error("❌ Dados da APR inválidos")
            return None, None
        
        # Gerar nome do arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        projeto_nome = dados_apr.get("projeto_nome", "projeto").replace(" ", "_")
        filename = f"APR_{projeto_nome}_{timestamp}.pdf"
        
        st.info("📄 Criando documento PDF...")
        
        # Criar PDF
        pdf_bytes = criar_pdf_apr(dados_apr)
        
        if not pdf_bytes:
            st.error("❌ Falha na criação do PDF")
            return None, None
        
        st.info(f"📊 PDF criado com sucesso ({len(pdf_bytes):,} bytes)")
        
        # Tentar salvar no GCS (opcional)
        st.info("☁️ Salvando no Google Cloud Storage...")
        if salvar_no_gcs(filename, pdf_bytes):
            st.success("✅ Arquivo salvo no cloud")
        else:
            st.warning("⚠️ Erro ao salvar no cloud, mas PDF foi gerado")
        
        logger.info(f"✅ APR gerada com sucesso: {filename}")
        return filename, pdf_bytes
        
    except Exception as e:
        st.error(f"❌ Erro na geração da APR: {e}")
        logger.error(f"Error in gerar_apr: {e}")
        return None, None


# =========================================================
# INICIALIZAÇÃO DO MÓDULO
# =========================================================

try:
    logger.info("🚀 Inicializando pipeline...")
    
    if not setup_gcp_credentials():
        st.error("❌ ERRO CRÍTICO: Falha ao configurar credenciais GCP")
        st.stop()
    
    logger.info("✅ Pipeline inicializado com sucesso")
    
except Exception as e:
    st.error(f"❌ ERRO CRÍTICO na inicialização: {e}")
    st.stop()


# =========================================================
# CÓDIGO DE TESTE
# =========================================================

if __name__ == "__main__":
    st.title("🧪 Teste do Pipeline APR")
    
    # Dados de teste
    dados_teste = {
        "projeto_nome": "Teste de Geração APR",
        "local_obra": "Local de Teste",
        "responsavel": "João Silva",
        "data_inicio": "01/01/2024",
        "data_fim": "31/12/2024",
        "tipo_atividade": "Construção Civil",
        "descricao_atividade": "Teste de geração automática de APR com dados fictícios para validação do sistema.",
        "riscos": "- Risco de teste 1\n- Risco de teste 2\n- Risco de teste 3",
        "medidas_controle": "- Medida 1\n- Medida 2\n- Medida 3"
    }
    
    if st.button("🚀 Testar Geração de APR"):
        with st.spinner("Gerando APR de teste..."):
            filename, file_bytes = gerar_apr(dados_teste)
            
            if filename and file_bytes:
                st.success("✅ APR de teste gerado com sucesso!")
                
                st.download_button(
                    label="📥 Download APR Teste",
                    data=file_bytes,
                    file_name=filename,
                    mime="application/pdf"
                )
            else:
                st.error("❌ Falha na geração da APR de teste")
