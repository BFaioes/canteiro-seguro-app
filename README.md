## 👷 Gerador de APR com IA (Streamlit)

Aplicação Streamlit que usa Google Vertex AI (Gemini + Embeddings) e RAG sobre PDFs em um bucket do Google Cloud Storage para gerar APR em `.docx`.

### ✅ Pré-requisitos
- Conta no Google Cloud com Vertex AI e Cloud Storage habilitados.
- Um bucket no GCS com os PDFs (normas/conteúdos) que serão a base de conhecimento.
- Uma Conta de Serviço com permissão de acesso ao Vertex AI e ao bucket (pelo menos `roles/aiplatform.user` e `roles/storage.objectViewer`).

### 🔐 Secrets necessários (Streamlit Cloud)
Este app lê as credenciais do `st.secrets["gcp"]`. No Streamlit Cloud, adicione em Settings → Secrets, usando este formato:

```toml
[gcp]
type = "service_account"
project_id = "SEU_PROJECT_ID"
private_key_id = "SEU_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\nSUA_CHAVE_AQUI\n-----END PRIVATE KEY-----\n"
client_email = "sua-conta-de-servico@SEU_PROJECT_ID.iam.gserviceaccount.com"
client_id = "SEU_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/sua-conta-de-servico%40SEU_PROJECT_ID.iam.gserviceaccount.com"
bucket_name = "NOME_DO_SEU_BUCKET"
```

Você encontra um exemplo pronto em `.streamlit/secrets.toml.example`.

### 🚀 Deploy no Streamlit Community Cloud
1. Publique este repositório no GitHub (público ou privado).
2. Acesse `https://share.streamlit.io` e clique em "New app".
3. Selecione o repositório e branch, e defina o caminho do arquivo principal como `app.py`.
4. Em "Advanced settings" → "Secrets", cole o conteúdo acima do `secrets.toml`.
5. Clique em "Deploy".

### ▶️ Execução local (opcional)
1. Python 3.11+
2. Crie um virtualenv e instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Crie um arquivo `.streamlit/secrets.toml` com o conteúdo do exemplo e suas credenciais reais.
4. Rode o app:
   ```bash
   streamlit run app.py
   ```

### 📦 Dependências
Ver `requirements.txt`. Caso encontre incompatibilidades do `google-cloud-aiplatform`, atualize para uma versão recente (ex.: `>=1.52.0`).

### 🧩 Como funciona (alto nível)
- Faz cache da autenticação no Vertex AI e cliente do GCS.
- Lê PDFs do bucket, extrai texto e cria chunks.
- Gera embeddings (Vertex `text-embedding-004`) e executa RAG por similaridade.
- Gera o conteúdo da APR (Gemini `gemini-1.5-flash-001`).
- Exporta um `.docx` para download.


