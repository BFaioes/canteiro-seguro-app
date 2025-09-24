import streamlit as st
import json
import logging
import os
import tempfile
from typing import Dict, Any, Optional

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_gcp_credentials() -> Optional[Dict[str, Any]]:
    """
    Função ULTRA ROBUSTA para obter credenciais GCP
    Funciona com múltiplos formatos de configuração
    """
    try:
        # Verificar se existe a seção gcp
        if "gcp" not in st.secrets:
            st.error("❌ Seção 'gcp' não encontrada nos secrets do Streamlit")
            return None

        gcp_config = st.secrets["gcp"]
        
        # ESTRATÉGIA 1: Campos individuais na raiz de [gcp] - MAIS CONFIÁVEL
        if "type" in gcp_config:
            logger.info("✅ Usando estratégia 1: campos individuais")
            
            # Montar credenciais campo por campo
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
            
            logger.info(f"✅ Credenciais montadas com sucesso. Project: {credentials['project_id']}")
            return credentials
        
        # ESTRATÉGIA 2: credentials_safe (formato alternativo)
        elif "credentials_safe" in gcp_config:
            logger.info("✅ Usando estratégia 2: credentials_safe")
            safe_credentials = dict(gcp_config["credentials_safe"])
            
            # Verificar se tem os campos essenciais
            if "type" in safe_credentials:
                return safe_credentials
            else:
                st.error("❌ Campo 'type' não encontrado em credentials_safe")
                return None
        
        # ESTRATÉGIA 3: credentials como string JSON (formato original problemático)
        elif "credentials" in gcp_config:
            logger.info("⚠️ Usando estratégia 3: parsing JSON string")
            
            credentials_raw = gcp_config["credentials"]
            
            # Se já é um dict
            if isinstance(credentials_raw, dict):
                if "type" in credentials_raw:
                    return credentials_raw
                else:
                    st.error("❌ Campo 'type' não encontrado no dict de credenciais")
                    return None
            
            # Se é string, fazer parse cuidadoso
            if isinstance(credentials_raw, str):
                try:
                    # Limpeza cuidadosa da string
                    clean_json = credentials_raw.strip()
                    
                    # Remover aspas externas se existirem
                    if clean_json.startswith('"') and clean_json.endswith('"'):
                        clean_json = clean_json[1:-1]
                    
                    # Substituir escapes de aspas
                    clean_json = clean_json.replace('\\"', '"')
                    
                    # Parse do JSON
                    credentials = json.loads(clean_json)
                    
                    if "type" in credentials:
                        logger.info("✅ Parse JSON realizado com sucesso")
                        return credentials
                    else:
                        st.error("❌ Campo 'type' não encontrado no JSON parseado")
                        return None
                        
                except json.JSONDecodeError as e:
                    st.error(f"❌ Erro no parse do JSON: {e}")
                    logger.error(f"JSON parse error: {e}")
                    return None
                except Exception as e:
                    st.error(f"❌ Erro inesperado no parse: {e}")
                    return None
        
        # Se chegou aqui, nenhuma estratégia funcionou
        st.error("❌ Nenhum formato válido de credenciais encontrado")
        st.info("Formatos suportados: campos individuais, credentials_safe, ou credentials JSON")
        
        # Debug: mostrar o que foi encontrado
        available_keys = list(gcp_config.keys())
        st.write(f"Chaves disponíveis em [gcp]: {available_keys}")
        
        return None
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao carregar credenciais: {e}")
        logger.error(f"Critical error in get_gcp_credentials: {e}")
        return None


def setup_gcp_credentials() -> bool:
    """
    Configura as credenciais GCP para uso na aplicação
    Cria arquivo temporário e define variável de ambiente
    """
    try:
        st.info("🔧 Configurando credenciais do Google Cloud Platform...")
        
        # Obter credenciais
        credentials = get_gcp_credentials()
        if credentials is None:
            st.error("❌ Não foi possível obter as credenciais")
            return False
        
        # Validação final
        required_fields = ["type", "project_id", "private_key", "client_email"]
        for field in required_fields:
            if field not in credentials or not credentials[field]:
                st.error(f"❌ Campo obrigatório '{field}' ausente ou vazio")
                return False
        
        # Criar arquivo temporário com as credenciais
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(credentials, temp_file, indent=2)
            temp_credentials_path = temp_file.name
        
        # Definir variável de ambiente para o Google Cloud SDK
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
        
        # Log informações não sensíveis
        logger.info(f"✅ Credenciais configuradas com sucesso!")
        logger.info(f"Project ID: {credentials['project_id']}")
        logger.info(f"Service Account: {credentials['client_email']}")
        logger.info(f"Credentials file: {temp_credentials_path}")
        
        st.success("✅ Credenciais GCP configuradas com sucesso!")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao configurar credenciais: {e}")
        logger.error(f"Error in setup_gcp_credentials: {e}")
        return False


def get_gcp_config() -> Dict[str, str]:
    """
    Retorna configurações básicas do GCP dos secrets
    """
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
    """
    Testa a conexão com o Google Cloud Storage
    """
    try:
        from google.cloud import storage
        
        config = get_gcp_config()
        if not config:
            return False
        
        # Criar cliente
        client = storage.Client(project=config["project_id"])
        
        # Testar acesso ao bucket
        bucket = client.bucket(config["bucket_name"])
        
        # Verificar se o bucket existe e é acessível
        if bucket.exists():
            st.success(f"✅ Conexão estabelecida com o bucket: {config['bucket_name']}")
            logger.info(f"Successfully connected to bucket: {config['bucket_name']}")
            return True
        else:
            st.error(f"❌ Bucket não encontrado: {config['bucket_name']}")
            return False
            
    except Exception as e:
        st.error(f"❌ Erro na conexão GCP: {e}")
        logger.error(f"GCP connection test failed: {e}")
        return False


# Função principal que será chamada pelo app.py
def gerar_apr(*args, **kwargs):
    """
    SUA FUNÇÃO ORIGINAL gerar_apr
    
    Substitua esta função pela sua implementação original
    As credenciais GCP já estarão configuradas quando esta função for chamada
    """
    try:
        # Verificar se as credenciais estão configuradas
        if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
            st.error("❌ Credenciais GCP não configuradas")
            return None, None
        
        st.info("🚀 Iniciando geração de APR...")
        
        # AQUI VAI SUA IMPLEMENTAÇÃO ORIGINAL
        # As credenciais já estão configuradas via variável de ambiente
        
        # Exemplo de como usar as configurações:
        config = get_gcp_config()
        project_id = config["project_id"]
        bucket_name = config["bucket_name"]
        
        # Sua lógica original aqui...
        
        # Placeholder - substitua pelo seu código real
        filename = "exemplo_apr.pdf"
        file_bytes = b"Conteudo do arquivo APR aqui"
        
        st.success("✅ APR gerado com sucesso!")
        return filename, file_bytes
        
    except Exception as e:
        st.error(f"❌ Erro na geração do APR: {e}")
        logger.error(f"Error in gerar_apr: {e}")
        return None, None


# =========================================================
# INICIALIZAÇÃO DO MÓDULO
# =========================================================

# Esta parte roda quando o módulo é importado
try:
    logger.info("🚀 Inicializando pipeline...")
    
    # Configurar credenciais automaticamente na importação
    if not setup_gcp_credentials():
        st.error("❌ ERRO CRÍTICO: Falha ao configurar credenciais GCP")
        logger.error("Critical failure: GCP credentials setup failed")
        st.stop()  # Para a execução do Streamlit
    
    logger.info("✅ Pipeline inicializado com sucesso")
    
except Exception as e:
    st.error(f"❌ ERRO CRÍTICO na inicialização: {e}")
    logger.error(f"Critical initialization error: {e}")
    st.stop()


# =========================================================
# CÓDIGO DE TESTE (opcional)
# =========================================================

if __name__ == "__main__":
    st.title("🧪 Teste do Pipeline GCP")
    
    st.subheader("1. Status das Credenciais")
    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        st.success("✅ Variável de ambiente configurada")
        st.write(f"Arquivo: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
    else:
        st.error("❌ Variável de ambiente não configurada")
    
    st.subheader("2. Configurações GCP")
    config = get_gcp_config()
    if config:
        st.json(config)
    
    st.subheader("3. Teste de Conexão")
    if st.button("Testar Conexão com GCP"):
        with st.spinner("Testando..."):
            if test_gcp_connection():
                st.balloons()
            else:
                st.error("Falha no teste de conexão")
    
    st.subheader("4. Teste da Função APR")
    if st.button("Testar gerar_apr()"):
        filename, file_bytes = gerar_apr()
        if filename and file_bytes:
            st.download_button(
                label="📥 Download APR",
                data=file_bytes,
                file_name=filename,
                mime="application/pdf"
            )
