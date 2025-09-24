import streamlit as st
import json
import logging
import os
import tempfile
from typing import Dict, Any, Optional

# Configurar logging
logger = logging.getLogger(__name__)

def get_gcp_credentials() -> Optional[Dict[str, Any]]:
    """
    Função para obter credenciais GCP de forma segura e robusta
    
    Returns:
        Dict com credenciais ou None se houver erro
    """
    try:
        # Verificar se as chaves existem
        if "gcp" not in st.secrets:
            logger.error("Chave 'gcp' não encontrada em st.secrets")
            st.error("Configuração GCP não encontrada nos secrets")
            return None
        
        # OPÇÃO 1: Credenciais como string JSON
        if "credentials" in st.secrets["gcp"]:
            credentials_raw = st.secrets["gcp"]["credentials"]
            
            # Se já é um dict, retornar diretamente
            if isinstance(credentials_raw, dict):
                logger.info("Credenciais já estão em formato dict")
                return credentials_raw
            
            # Se é string, fazer parse
            if isinstance(credentials_raw, str):
                credentials_clean = credentials_raw.strip()
                
                # Remover aspas externas se existirem
                if credentials_clean.startswith('"') and credentials_clean.endswith('"'):
                    credentials_clean = credentials_clean[1:-1]
                
                # Corrigir escapes comuns
                credentials_clean = (credentials_clean
                                   .replace('\\n', '\n')
                                   .replace('\\"', '"')
                                   .replace('\\\\', '\\'))
                
                return json.loads(credentials_clean)
        
        # OPÇÃO 2: Credenciais como objetos TOML separados
        elif "credentials" in st.secrets["gcp"] and isinstance(st.secrets["gcp"]["credentials"], dict):
            logger.info("Usando credenciais em formato TOML")
            return dict(st.secrets["gcp"]["credentials"])
        
        # OPÇÃO 3: Credenciais como campos individuais
        else:
            logger.info("Montando credenciais a partir de campos individuais")
            required_fields = ["type", "project_id", "private_key", "client_email"]
            credentials = {}
            
            gcp_config = st.secrets["gcp"]
            for field in required_fields:
                if field not in gcp_config:
                    raise ValueError(f"Campo obrigatório '{field}' não encontrado nas configurações GCP")
                credentials[field] = gcp_config[field]
            
            # Adicionar campos opcionais se existirem
            optional_fields = ["private_key_id", "client_id", "auth_uri", "token_uri", 
                             "auth_provider_x509_cert_url", "client_x509_cert_url"]
            for field in optional_fields:
                if field in gcp_config:
                    credentials[field] = gcp_config[field]
            
            return credentials
        
        logger.error("Nenhum formato válido de credenciais encontrado")
        return None
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro de JSON: {e}")
        st.error(f"Erro ao fazer parse das credenciais JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro ao carregar credenciais GCP: {e}")
        st.error(f"Erro ao carregar credenciais GCP: {e}")
        return None

def setup_gcp_credentials() -> bool:
    """
    Configura as credenciais GCP para uso na aplicação
    
    Returns:
        True se configurado com sucesso, False caso contrário
    """
    try:
        credentials = get_gcp_credentials()
        if credentials is None:
            return False
        
        # Criar arquivo temporário com as credenciais
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(credentials, f, indent=2)
            temp_credentials_path = f.name
        
        # Definir a variável de ambiente
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
        
        logger.info("Credenciais GCP configuradas com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao configurar credenciais GCP: {e}")
        st.error(f"Erro ao configurar credenciais GCP: {e}")
        return False

# Configurar credenciais na importação do módulo
if not setup_gcp_credentials():
    st.error("Falha ao configurar credenciais do Google Cloud Platform")
    st.stop()

# Resto do seu código original do pipeline.py continua aqui...
# Substitua a linha 31 problemática por:
# credentials = get_gcp_credentials()

def gerar_apr(*args, **kwargs):
    """
    Sua função gerar_apr original
    Adicione aqui a lógica original da função
    """
    # Implementação da sua função
    pass

# Se este for o arquivo principal, executar testes
if __name__ == "__main__":
    print("Testando configuração das credenciais GCP...")
    if setup_gcp_credentials():
        print("✅ Credenciais configuradas com sucesso!")
    else:
        print("❌ Falha ao configurar credenciais")
