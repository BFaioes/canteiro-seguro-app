import os
import io
import json
from datetime import datetime
import numpy as np

# Streamlit para ler secrets no Cloud
import streamlit as st

# GCP
from google.oauth2 import service_account
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel

# PDF + RAG utils
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sklearn.metrics.pairwise import cosine_similarity
import pypdf

# Word
from docxtpl import DocxTemplate
from docx import Document  # para criar template fallback

# ---------------------------
# Config (pegamos de secrets)
# ---------------------------
PROJECT_ID = st.secrets["gcp"]["project_id"]
LOCATION   = st.secrets["gcp"]["location"]
BUCKET     = st.secrets["gcp"]["bucket_name"]

# Credenciais a partir de secrets (NÃO usa arquivo no disco)
CREDS = service_account.Credentials.from_service_account_info(
    dict(st.secrets["gcp_service_account"])
)

# Inicializa Vertex com credenciais
vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=CREDS)

MODELO_EMBED = "text-embedding-004"
MODELO_GEN   = "gemini-2.5-flash"
TOP_K_RAG    = 3

TEMPLATE_NAME = "template_apr_gerado.docx"  # suba este arquivo no repo; se faltar, criamos um simples


def _garante_template():
    """Cria um template simples se não existir no diretório."""
    if os.path.exists(TEMPLATE_NAME):
        return
    doc = Document()
    doc.add_heading('ANÁLISE PRELIMINAR DE RISCO (APR)', level=1)
    p = doc.add_paragraph(); p.add_run('Título: ').bold = True
    doc.add_paragraph('{{ titulo_apr }}')
    p = doc.add_paragraph(); p.add_run('Local: ').bold = True
    doc.add_paragraph('{{ local }}')
    p = doc.add_paragraph(); p.add_run('Data: ').bold = True
    doc.add_paragraph('{{ data_elaboracao }}')

    doc.add_heading('ETAPAS DA TAREFA, RISCOS E MEDIDAS DE CONTROLE', level=2)
    table = doc.add_table(rows=1, cols=5); table.style = 'Table Grid'
    hdr = table.rows[0].cells
    hdr[0].text = 'Etapa da Tarefa'
    hdr[1].text = 'Perigos Identificados'
    hdr[2].text = 'Riscos Associados'
    hdr[3].text = 'Medidas de Controle Recomendadas'
    hdr[4].text = 'Classificação do Risco Residual'

    row = table.add_row().cells
    row[0].text = '{% for r in etapas_e_riscos %}{{ r.etapa_tarefa }}{% if not loop.last %}\n---\n{% endif %}{% endfor %}'
    row[1].text = '{% for r in etapas_e_riscos %}{{ r.perigos_identificados|join("\\n- ") }}{% if not loop.last %}\n---\n{% endif %}{% endfor %}'
    row[2].text = '{% for r in etapas_e_riscos %}{{ r.riscos_associados|join("\\n- ") }}{% if not loop.last %}\n---\n{% endif %}{% endfor %}'
    row[3].text = '{% for r in etapas_e_riscos %}{{ r.medidas_de_controle_recomendadas|join("\\n- ") }}{% if not loop.last %}\n---\n{% endif %}{% endfor %}'
    row[4].text = '{% for r in etapas_e_riscos %}{{ r.classificacao_risco_residual }}{% if not loop.last %}\n---\n{% endif %}{% endfor %}'

    doc.add_heading('EQUIPAMENTOS DE PROTEÇÃO INDIVIDUAL (EPIs) OBRIGATÓRIOS', level=2)
    doc.add_paragraph('{% for e in epis_obrigatorios %}- {{ e }}{% endfor %}')

    doc.add_heading('PROCEDIMENTOS DE EMERGÊNCIA', level=2)
    doc.add_paragraph('{{ procedimentos_emergencia }}')

    doc.save(TEMPLATE_NAME)


def _ler_pdfs_bucket():
    """Lê PDFs do bucket e devolve lista de chunks {'source','content'} com limites para não estourar tokens."""
    client = storage.Client(project=PROJECT_ID, credentials=CREDS)
    bucket = client.bucket(BUCKET)

    # Estratégia: só pegar arquivos mais prováveis (NR-12, 18, 20, 33, 35) se existirem
    prefer = ("nr-12", "nr12", "nr-18", "nr18", "nr-20", "nr20", "nr-33", "nr33", "nr-35", "nr35")
    blobs = list(bucket.list_blobs())
    preferidos = [b for b in blobs if b.name.lower().endswith(".pdf") and any(p in b.name.lower() for p in prefer)]
    if not preferidos:
        preferidos = [b for b in blobs if b.name.lower().endswith(".pdf")]

    # Limites para segurança de tokens
    MAX_FILES = 8
    MAX_CHARS_PER_CHUNK = 1200
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=60)

    chunks = []
    for blob in preferidos[:MAX_FILES]:
        try:
            with blob.open("rb") as f:
                reader = pypdf.PdfReader(f)
                text = "".join((page.extract_text() or "") for page in reader.pages)
                if not text.strip():
                    continue
                for ch in splitter.split_text(text):
                    ch = ch[:MAX_CHARS_PER_CHUNK]
                    chunks.append({"source": blob.name, "content": ch})
        except Exception:
            continue

    # Hard cap
    return chunks[:1500]  # suficiente e seguro


def gerar_apr(atividade: str):
    """Retorna (filename, bytes) do DOCX gerado."""
    _garante_template()

    chunks = _ler_pdfs_bucket()
    if not chunks:
        raise RuntimeError("Nenhum texto lido dos PDFs do bucket.")

    # Embeddings (em lotes moderados)
    embed_model = TextEmbeddingModel.from_pretrained(MODELO_EMBED)
    texts = [c["content"] for c in chunks]

    vectors = []
    batch, acc = [], 0
    MAX_BATCH_CHARS = 16000  # margem
    for t in texts:
        if acc + len(t) > MAX_BATCH_CHARS and batch:
            res = embed_model.get_embeddings(batch)
            vectors.extend([e.values for e in res])
            batch, acc = [], 0
        batch.append(t); acc += len(t)
    if batch:
        res = embed_model.get_embeddings(batch)
        vectors.extend([e.values for e in res])

    if not vectors:
        raise RuntimeError("Falha ao gerar embeddings.")

    arr = np.array(vectors)

    # Similaridade
    q = embed_model.get_embeddings([atividade])[0].values
    sims = cosine_similarity([q], arr)[0]
    idxs = sims.argsort()[-TOP_K_RAG:][::-1]
    selecionados = [chunks[i]["content"] for i in idxs]

    # Pré-resumo para conter tokens
    gen = GenerativeModel(MODELO_GEN)
    resumos = []
    for ch in selecionados:
        prompt_resumo = (
            "Resuma em até 80 palavras focando em perigos, riscos, medidas e citações de NR quando houver:\n\n" + ch[:2000]
        )
        try:
            r = gen.generate_content(prompt_resumo)
            resumos.append((r.text or "")[:500])
        except Exception:
            resumos.append(ch[:300] + " ...")

    contexto = "\n---\n".join(resumos)
    if len(contexto) > 3000:
        contexto = contexto[:3000] + " ..."

    data_str = datetime.now().strftime("%d/%m/%Y")
    json_exemplo = """{
  "titulo_apr": "APR - ATIVIDADE",
  "local": "Local",
  "data_elaboracao": "DATA",
  "etapas_e_riscos": [
    {
      "etapa_tarefa": "Etapa",
      "perigos_identificados": ["Perigo1"],
      "riscos_associados": ["Risco1"],
      "medidas_de_controle_recomendadas": ["Medida1 (NR-XX, item Y.Y)"],
      "classificacao_risco_residual": "Baixo/Médio/Alto"
    }
  ],
  "epis_obrigatorios": ["Capacete", "Óculos"],
  "procedimentos_emergencia": "Descrever..."
}"""

    prompt_final = f"""Você é Engenheiro de Segurança do Trabalho no Brasil.
Gere uma APR em JSON para a atividade: {atividade}

Contexto técnico (NRs resumidas):
{contexto}

Regras:
- Responder SOMENTE com JSON válido.
- Cite NR e item quando aplicável (ex.: "NR-35, 35.4.1").
- Se faltar informação, use "Não especificado".

Modelo de saída:
{json_exemplo}
"""

    # Geração
    resp = gen.generate_content(prompt_final)
    txt = (resp.text or "").strip()
    a, b = txt.find("{"), txt.rfind("}") + 1
    if a == -1 or b <= a:
        raise ValueError("A IA não retornou JSON válido.")

    dados = json.loads(txt[a:b])

    # Normalizações
    etapas = dados.get("etapas_e_riscos", [])
    for r in etapas:
        for k in ("perigos_identificados", "riscos_associados", "medidas_de_controle_recomendadas"):
            if isinstance(r.get(k), str):
                r[k] = [r[k]]
            elif not isinstance(r.get(k), list):
                r[k] = ["Não especificado"]

    ctx = {
        "titulo_apr": dados.get("titulo_apr", f"APR - {atividade}"),
        "local": dados.get("local", "Não especificado"),
        "data_elaboracao": dados.get("data_elaboracao", data_str),
        "etapas_e_riscos": etapas,
        "epis_obrigatorios": dados.get("epis_obrigatorios", ["Não especificado"]),
        "procedimentos_emergencia": dados.get("procedimentos_emergencia", "Não especificado"),
    }

    # Render para bytes (sem gravar em disco)
    tpl = DocxTemplate(TEMPLATE_NAME)
    tpl.render(ctx)
    buf = io.BytesIO()
    tpl.save(buf)
    buf.seek(0)

    filename = f"APR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    return filename, buf.read()
