import streamlit as st
import io
import urllib.parse
import bcrypt
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder
from bson import ObjectId
from PIL import Image
from reportlab.lib.utils import ImageReader

# --- Inicialização segura do session_state ---

if "logado" not in st.session_state:
    st.session_state["logado"] = False

if "nivel" not in st.session_state:
    st.session_state["nivel"] = None

if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

# Definição segura se é user
usuario_eh_user = st.session_state.get("nivel") == "user"

# --- Configuração MongoDB (substitua pela sua string) ---

MONGO_URI = "mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["academia_karate"]

# Coleções
col_usuarios = db["usuarios"]
col_academia = db["academia"]
col_alunos = db["alunos"]
col_presencas = db["presencas"]
col_mensalidades = db["mensalidades"]
col_exames = db["exames"]
col_equipamentos = db["equipamentos"]
col_emprestimos = db["emprestimos"]
col_dojo = db["dojo"]

# --- Estilo CSS: Fundo azul escuro e texto branco ---
st.markdown(
    """
    <style>
    body {
        background-color: #1e3a8a;
        color: white;
    }
    .css-1d391kg, .css-1offfwp {
        color: white;
    }
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div > select,
    .stDateInput > div > div > input {
        background-color: #1e40af;
        color: white;
        border-radius: 5px;
        border: 1px solid #3b82f6;
    }
    div.stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        font-weight: 600;
        border-radius: 8px;
        border: none;
    }
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-thumb {
        background: #3b82f6;
        border-radius: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- FUNÇÕES AUXILIARES ----------

belt_progression = {
    'Branca': {'next': 'Cinza', 'months': 3, 'value': 40.00},
    'Cinza': {'next': 'Azul', 'months': 3, 'value': 45.00},
    'Azul': {'next': 'Amarela', 'months': 3, 'value': 55.00},
    'Amarela': {'next': 'Vermelha', 'months': 3, 'value': 60.00},
    'Vermelha': {'next': 'Laranja', 'months': 6, 'value': 65.00},
    'Laranja': {'next': 'Verde', 'months': 9, 'value': 70.00},
    'Verde': {'next': 'Roxa', 'months': 9, 'value': 75.00},
    'Roxa': {'next': 'Marrom2', 'months': 12, 'value': 80.00},
    'Marrom2': {'next': 'Marrom1', 'months': 12, 'value': 90.00},
    'Marrom1': {'next': 'Preta', 'months': 12, 'value': 100.00},
    'Preta': {'next': 'Preta1', 'months': 24, 'value': 110.00}
}

def enviar_mensagem_whatsapp(telefone, mensagem):
    numero = telefone.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
    texto = urllib.parse.quote(mensagem)
    url = f"https://api.whatsapp.com/send?phone=55{numero}&text={texto}"
    st.markdown(f"[Clique aqui para enviar mensagem via WhatsApp]({url})", unsafe_allow_html=True)

def enviar_alerta_mensalidade():
    hoje = datetime.today().date()
    
    # Data fixa de vencimento: dia 5 do mês atual
    vencimento_fixo = hoje.replace(day=5)
    
    # Se hoje passou do dia 5, verifica vencimento do próximo mês
    if hoje.day > 5:
        mes = 1 if hoje.month == 12 else hoje.month + 1
        ano = hoje.year + (1 if hoje.month == 12 else 0)
        vencimento_fixo = vencimento_fixo.replace(year=ano, month=mes)
    
    # Define as datas para os alertas
    datas_alerta = {
        3: vencimento_fixo - timedelta(days=3),
        2: vencimento_fixo - timedelta(days=2),
        1: vencimento_fixo - timedelta(days=1),
    }
    
    # Busca mensalidades não pagas
    mensalidades = list(col_mensalidades.find({"pago": False}))
    
    for mensalidade in mensalidades:
        aluno_nome = mensalidade['aluno']
        
        aluno_doc = col_alunos.find_one({"nome": aluno_nome})
        if not aluno_doc:
            continue

        telefone = aluno_doc.get("telefone")
        if not telefone:
            continue

        try:
            vencimento = datetime.strptime(mensalidade['vencimento'], "%Y-%m-%d").date()
        except:
            continue

        # Verifica alertas por data
        dias_restantes = (vencimento - hoje).days

        if dias_restantes in datas_alerta:
            mensagem = (
                f"Olá {aluno_nome}, sua mensalidade vence em {dias_restantes} dia(s) "
                f"({vencimento.strftime('%d/%m/%Y')}). "
                f"Por favor, realize o pagamento para evitar suspensão das aulas."
            )
            enviar_mensagem_whatsapp(telefone, mensagem)

        elif dias_restantes < 0:
            mensagem = (
                f"⚠️ Olá {aluno_nome}, sua mensalidade venceu no dia "
                f"{vencimento.strftime('%d/%m/%Y')}. Regularize o pagamento o quanto antes para evitar restrições às aulas."
            )
            enviar_mensagem_whatsapp(telefone, mensagem)

def hash_password(password):
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(usuario, senha):
    user = col_usuarios.find_one({"usuario": usuario})
    if user and user["senha"] == hash_password(senha):
        return True
    return False

def cadastrar_usuario(usuario, senha):
    if col_usuarios.find_one({"usuario": usuario}):
        return False
    col_usuarios.insert_one({"usuario": usuario, "senha": hash_password(senha)})
    return True

def exportar_pdf_alunos():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, 27*cm, "Relatório de Alunos")
    c.setFont("Helvetica", 12)
    y = 25*cm
    for aluno in col_alunos.find():
        linha = f"Nome: {aluno['nome']}, RG: {aluno.get('rg','')}, Faixa: {aluno.get('faixa','')}"
        c.drawString(2*cm, y, linha)
        y -= 1*cm
        if y < 2*cm:
            c.showPage()
            y = 27*cm
    c.save()
    buffer.seek(0)
    return buffer

# -------------------------------------------------------
# FUNÇÃO PARA EXPORTAR PDF DE PRESENÇAS
# -------------------------------------------------------

def exportar_pdf_presencas(df):
    buffer = BytesIO()

    # Documento paisagem
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    elements = []

    # ----------------------------------
    # CABEÇALHO: insere imagem completa
    # ----------------------------------
    try:
        cabecalho = Image("cabecario.jpg", width=770, height=150)
        elements.append(cabecalho)
        elements.append(Spacer(1, 20))
    except Exception as e:
        print("Erro carregando cabeçalho:", e)

    # ------------------------------
    # TABELA DE PRESENÇAS
    # ------------------------------
    # Converte DataFrame em lista de listas
    data = [df.columns.tolist()] + df.values.tolist()

    table = Table(data, repeatRows=1)

    style = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.black),
        ("BOX", (0,0), (-1,-1), 0.5, colors.black),
        ("FONTSIZE", (0,0), (-1,-1), 4,5),
    ])
    table.setStyle(style)

    elements.append(table)

    # Gera PDF
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf
    
    # -----------------------------------
    # Buscar presenças do dia
    # -----------------------------------
    hoje = datetime.today().strftime("%Y-%m-%d")
    presenca = col_presencas.find_one({"data": hoje})

    y = 24*cm

    if presenca and presenca.get("presentes"):
        for nome in presenca["presentes"]:
            c.setFont("Helvetica", 12)
            c.drawString(2*cm, y, f"✅ {nome}")
            y -= 1*cm

            # Quebra de página se necessário
            if y < 2*cm:
                c.showPage()
                y = 28*cm
    else:
        c.setFont("Helvetica", 12)
        c.drawString(2*cm, 24*cm, "Nenhuma presença registrada hoje.")

    c.save()
    buffer.seek(0)
    return buffer

def exportar_pdf_mensalidades():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, 27*cm, "Relatório de Mensalidades")
    c.setFont("Helvetica", 12)
    y = 25*cm
    for m in col_mensalidades.find().sort("vencimento", -1):
        linha = f"Aluno: {m['aluno']}, Vencimento: {m['vencimento']}, Pago: {'Sim' if m.get('pago') else 'Não'}"
        c.drawString(2*cm, y, linha)
        y -= 1*cm
        if y < 2*cm:
            c.showPage()
            y = 27*cm
    c.save()
    buffer.seek(0)
    return buffer

def calcular_proximo_exame(ultima_faixa, ultima_data):
    if ultima_faixa not in belt_progression:
        return None, None, None, None, None

    next_belt = belt_progression[ultima_faixa]["next"]
    interval = belt_progression[ultima_faixa]["months"]
    valor = belt_progression[ultima_faixa]["value"]

    data_ultimo = datetime.strptime(ultima_data, "%Y-%m-%d")
    data_proximo = data_ultimo + relativedelta(months=interval)

    hoje = datetime.today()
    if data_proximo > hoje:
        diff = relativedelta(data_proximo, hoje)
        meses_faltando = diff.months
        dias_faltando = diff.days
    else:
        meses_faltando = 0
        dias_faltando = 0

    return next_belt, data_proximo, meses_faltando, dias_faltando, valor

def exportar_pdf_exames():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, 27*cm, "Relatório de Exames")
    c.setFont("Helvetica", 12)
    y = 25*cm
    for e in col_exames.find().sort("data", -1):
        linha = f"Aluno: {e['aluno']}, Data: {e['data']}, Faixa: {e['faixa']}, Status: {e['status']}"
        c.drawString(2*cm, y, linha)
        y -= 1*cm
        if y < 2*cm:
            c.showPage()
            y = 27*cm
    c.save()
    buffer.seek(0)
    return buffer

def exportar_pdf_equipamentos():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, 27*cm, "Relatório de Equipamentos e Empréstimos")
    c.setFont("Helvetica", 12)
    y = 25*cm
    equipamentos = list(col_equipamentos.find())
    for eq in equipamentos:
        desc = f"{eq['tipo'].capitalize()} - {eq['tamanho']} ({eq['codigo']})"
        if eq["tipo"] == "faixa":
            desc = f"{eq['tipo'].capitalize()} {eq['cor_faixa']} - {eq['tamanho']} ({eq['codigo']})"
        linha = f"Equipamento: {desc}, Condição: {eq['condicao']}, Status: {eq['status']}"
        c.drawString(2*cm, y, linha)
        y -= 0.8*cm
        if y < 2*cm:
            c.showPage()
            y = 27*cm
    c.drawString(2*cm, y-1*cm, "Histórico de Empréstimos:")
    y -= 2*cm
    emprestimos = list(col_emprestimos.find().sort("createdAt", -1))
    for emp in emprestimos:
        linha = f"Aluno: {emp['aluno_nome']}, Equip.: {emp['equipamento_desc']}, Emprestado: {emp['data_emprestimo']}, Devolução: {emp['data_devolucao']}, Status: {emp['status']}"
        c.drawString(2*cm, y, linha)
        y -= 0.8*cm
        if y < 2*cm:
            c.showPage()
            y = 27*cm
    c.save()
    buffer.seek(0)
    return buffer

# ---------- PÁGINAS ----------

# -------------------------------------------------------
# PÁGINA DE CRIAR ADMIN
# -------------------------------------------------------

def criar_admin():
    st.title("🥋 空手道 (Karatedō) - Primeiro Acesso - By Malheiros")
    st.info("Nenhum usuário encontrado. Crie o usuário administrador.")

    usuario = st.text_input("Usuário Admin")
    senha = st.text_input("Senha", type="password")
    confirmar = st.text_input("Confirme a Senha", type="password")

    if st.button("Criar Admin"):
        if senha != confirmar:
            st.error("As senhas não coincidem.")
            return

        if not usuario or not senha:
            st.error("Preencha todos os campos.")
            return

        hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())

        col_usuarios.insert_one({
            "usuario": usuario,
            "senha": hashed,
            "nivel": "admin"
        })

        st.success("Usuário admin criado com sucesso! Faça login.")
        st.rerun()

# -------------------------------------------------------
# PÁGINA DE LOGIN
# -------------------------------------------------------

def login():
    st.title("🥋 空手道 (Karatedō) - Sistema Karatê -By Malheiros")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        user = col_usuarios.find_one({"usuario": usuario})
        if user and bcrypt.checkpw(senha.encode(), user["senha"]):
            st.session_state["logado"] = True
            st.session_state["nivel"] = user["nivel"]
            st.session_state["usuario"] = usuario
        else:
            st.error("Credenciais inválidas")

# -------------------------------------------------------
# PÁGINA DE GERAL
# -------------------------------------------------------

def pagina_geral():
    st.header("🥋 空手道 (Karatedō) - Cadastros Gerais da Academia")

    dados = col_academia.find_one()
    if dados:
        st.success(f"**Academia cadastrada:** {dados.get('nome','')}")
        st.write(f"**CNPJ:** {dados.get('cnpj','')}")
        if dados.get("logo_data"):
            st.image(dados["logo_data"], width=200)

    with st.form("form_geral"):
        nome = st.text_input("Nome da Academia", value=dados.get("nome") if dados else "")
        cnpj = st.text_input("CNPJ", value=dados.get("cnpj") if dados else "")
        logo = st.file_uploader("Logo da Academia", type=["png","jpg","jpeg"])

        if st.form_submit_button("Salvar Dados Gerais"):
            logo_data = None
            if logo:
                logo_data = logo.getvalue()

            col_academia.delete_many({})
            col_academia.insert_one({
                "nome": nome,
                "cnpj": cnpj,
                "logo_data": logo_data
            })
            st.success("Dados salvos com sucesso!")
            st.rerun()

# -------------------------------------------------------
# PÁGINA DE ALUNOS
# -------------------------------------------------------

import re
import io
import base64
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from bson import ObjectId
import streamlit as st

MONGO_URI = "mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["academia_karate"]

col_usuarios = db["usuarios"]
col_academia = db["academia"]
col_alunos = db["alunos"]
col_presencas = db["presencas"]
col_mensalidades = db["mensalidades"]
col_exames = db["exames"]
col_equipamentos = db["equipamentos"]
col_emprestimos = db["emprestimos"]
col_dojo = db["dojo"]

# -----------------------------------------------
# Função para normalizar nomes
# -----------------------------------------------
def normalizar_nome(nome):
    return re.sub(r"\s+", " ", nome).strip().upper()

# -----------------------------------------------
# Função para filtrar documentos mesmo que tenham espaços extras ou maiúsculas/minúsculas diferentes
# -----------------------------------------------
def filtra_por_nome(collection, nome_normalizado):
    docs = list(collection.find())
    return [
        doc for doc in docs
        if normalizar_nome(doc.get("aluno", "")) == nome_normalizado
    ]

# -----------------------------------------------
# Função para gerar o PDF
# -----------------------------------------------
def gerar_pdf_relatorio_aluno(aluno_id):

    aluno = col_alunos.find_one({"_id": ObjectId(aluno_id)})

    if not aluno:
        st.error("Aluno não encontrado.")
        return

    nome_normalizado = normalizar_nome(aluno["nome"])

    # Busca dados em outras coleções
    mensalidades = filtra_por_nome(col_mensalidades, nome_normalizado)
    exames = filtra_por_nome(col_exames, nome_normalizado)
    emprestimos = filtra_por_nome(col_emprestimos, nome_normalizado)
    presencas = filtra_por_nome(col_presencas, nome_normalizado)
    equipamentos = filtra_por_nome(col_equipamentos, nome_normalizado)

    # Criação do PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Cabeçalho com imagem
    try:
        cabecalho_path = "cabecario.jpg"   # ajuste o caminho se necessário
        c.drawImage(cabecalho_path, 50, 750, width=500, height=80, preserveAspectRatio=True)
    except Exception as e:
        print(f"Erro ao carregar cabeçalho: {e}")

    y = 740
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Relatório Completo do Aluno - {aluno['nome']}")
    y -= 30

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Nome: {aluno['nome']}")
    y -= 15
    c.drawString(50, y, f"RG: {aluno.get('rg', '')}")
    y -= 15
    c.drawString(50, y, f"Telefone: {aluno.get('telefone', '')}")
    y -= 15
    c.drawString(50, y, f"Faixa: {aluno.get('faixa', '')}")
    y -= 15
    c.drawString(50, y, f"Data de Nascimento: {aluno.get('data_nascimento', '')}")
    y -= 25

    def escreve_titulo(titulo):
        nonlocal y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"{titulo}:")
        y -= 20
        c.setFont("Helvetica", 10)

    def escreve_linhas(linhas):
        nonlocal y
        for linha in linhas:
            c.drawString(60, y, linha)
            y -= 15
            if y < 50:
                c.showPage()
                y = 780

    # MENSALIDADES
    escreve_titulo("Mensalidades")
    if mensalidades:
        total_pago = sum(1 for m in mensalidades if m.get("pago", False))
        linhas = [
            f"Vencimento: {m.get('vencimento','')} - Pago: {m.get('pago', False)}"
            for m in mensalidades
        ]
        escreve_linhas(linhas)
        escreve_linhas([f"Total Mensalidades Pagas: {total_pago}"])
    else:
        escreve_linhas(["Nenhum registro."])

    y -= 10

    # PRESENÇAS
    escreve_titulo("Presenças")
    if presencas:
        linhas = [
            f"Data: {p.get('data')} - Aula: {p.get('aula')}"
            for p in presencas
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])

    y -= 10

    # EXAMES
    escreve_titulo("Exames")
    if exames:
        linhas = [
            f"Data: {e.get('data')} - Faixa: {e.get('faixa')} - Status: {e.get('status')}"
            for e in exames
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])

    y -= 10

    # EMPRÉSTIMOS
    escreve_titulo("Empréstimos")
    if emprestimos:
        linhas = [
            f"Item: {em.get('equipamento','')} - Empréstimo: {em.get('data_emprestimo','')} - Devolução: {em.get('data_devolucao','')} - Observações: {em.get('observacoes','')}"
            for em in emprestimos
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])

    y -= 10

    # EQUIPAMENTOS
    escreve_titulo("Equipamentos")
    if equipamentos:
        linhas = [
            f"Equipamento: {eq.get('equipamento','')} - Código: {eq.get('codigo','')}"
            for eq in equipamentos
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])

    c.showPage()
    c.save()

    buffer.seek(0)

    # Gerar link para download no Streamlit
    b64_pdf = base64.b64encode(buffer.read()).decode("utf-8")
    href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="relatorio_{aluno["nome"]}.pdf">📄 Download Relatório PDF</a>'
    st.markdown(href, unsafe_allow_html=True)

from datetime import datetime, timedelta
import streamlit as st
from bson import ObjectId

def pagina_alunos():
    st.header("🥋 空手道 (Karatedō) - Alunos Cadastrados")
    alunos = list(col_alunos.find())

    if alunos:
        for a in alunos:
            col1, col2, col3, col4 = st.columns([5, 3, 3, 3])

            with col1:
                st.markdown(
                    f"**{a['nome']}** | RG: {a.get('rg','')} | Faixa: {a.get('faixa','')} | Tel: {a.get('telefone','')}"
                )
            with col2:
                if st.button(f"✏️ Editar {a['nome']}", key=f"editar_{a['_id']}"):
                    st.session_state["editar_id"] = str(a["_id"])
                    st.experimental_rerun()
            with col3:
                if st.button(f"🗑️ Excluir {a['nome']}", key=f"excluir_{a['_id']}"):
                    col_alunos.delete_one({"_id": a["_id"]})
                    st.success(f"Aluno {a['nome']} excluído!")
                    st.rerun()
            with col4:
                if st.button(f"📄 Relatório PDF {a['nome']}", key=f"relatorio_{a['_id']}"):
                    gerar_pdf_relatorio_aluno(str(a["_id"]))


        else:
            st.info("Nenhum aluno cadastrado.")

    editar_id = st.session_state.get("editar_id", None)

    if editar_id:
        aluno_edit = col_alunos.find_one({"_id": ObjectId(editar_id)})

        st.subheader(f"Editar Aluno: {aluno_edit['nome']}")

        with st.form("form_editar_aluno"):
            nome = st.text_input("Nome", value=aluno_edit["nome"])
            rg = st.text_input("RG", value=aluno_edit.get("rg", ""))
            faixa = st.selectbox(
                "Faixa",
                ["Branca","cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"],
                index=[
                    "Branca","cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"
                ].index(aluno_edit.get("faixa", "Branca")),
            )
            data_nascimento = st.date_input(
                "Data de Nascimento",
                value=datetime.strptime(aluno_edit.get("data_nascimento", "1900-01-01"), "%Y-%m-%d")
            )
            telefone = st.text_input("Telefone/WhatsApp (com DDD)", value=aluno_edit.get("telefone", ""))

            if st.form_submit_button("Salvar Alterações"):
                col_alunos.update_one(
                    {"_id": ObjectId(editar_id)},
                    {"$set": {
                        "nome": nome,
                        "rg": rg,
                        "faixa": faixa,
                        "data_nascimento": str(data_nascimento),
                        "telefone": telefone
                    }}
                )
                st.success("Aluno atualizado com sucesso!")
                del st.session_state["editar_id"]
                st.rerun()

        if st.button("Cancelar edição"):
            del st.session_state["editar_id"]
            st.rerun()

    else:
        # Formulário para cadastrar novo aluno (só aparece se não estiver editando)
        st.header("🥋 空手道 (Karatedō) - Cadastrar Novo Aluno")
        with st.form("form_aluno"):
            nome = st.text_input("Nome")
            rg = st.text_input("RG")
            faixa = st.selectbox(
                "Faixa",
                ["Branca", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"]
            )
            data_nascimento = st.date_input("Data de Nascimento")
            telefone = st.text_input("Telefone/WhatsApp (com DDD)", max_chars=15)

            if st.form_submit_button("Cadastrar"):
                col_alunos.insert_one({
                    "nome": nome,
                    "rg": rg,
                    "telefone": telefone,
                    "faixa": faixa,
                    "data_nascimento": str(data_nascimento)
                })
                st.success("Aluno cadastrado!")
                st.rerun()

# -------------------------------------------------------
# PÁGINA DE PRESENÇAS
# -------------------------------------------------------

from datetime import datetime, timedelta
import streamlit as st
from pymongo import MongoClient
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

# ------------------------------------
# CONFIGURAÇÃO DO BANCO
# ------------------------------------
client = MongoClient(MONGO_URI)
col_alunos = db["alunos"]
col_presencas = db["presencas"]

#-------------------------------------
# FUNÇÃO PRINCIPAL
# ------------------------------------
def pagina_presencas():
    st.header("🥋 空手道 (Karatedō) - Presenças")

    # Carrega lista de alunos
    alunos = list(col_alunos.find())
    nomes_alunos = [a["nome"] for a in alunos]

    hoje = datetime.today()
    ano = hoje.year
    mes = hoje.month

    # cria lista de datas do mês
    dias_no_mes = []
    dia_atual = datetime(ano, mes, 1)
    while dia_atual.month == mes:
        dias_no_mes.append(dia_atual.strftime("%d/%m"))
        dia_atual += timedelta(days=1)

    # busca o documento único
    registro = col_presencas.find_one({"ano": ano, "mes": mes})

    if registro and registro.get("tabela"):
        df_grid = pd.DataFrame(registro["tabela"])
    
        # Garante que novos alunos sejam adicionados
        alunos_existentes = df_grid["Aluno"].tolist()
        alunos_novos = [a for a in nomes_alunos if a not in alunos_existentes]
    
        for nome in alunos_novos:
            nova_linha = {col: "" for col in df_grid.columns}
            nova_linha["Aluno"] = nome
            df_grid = pd.concat([df_grid, pd.DataFrame([nova_linha])], ignore_index=True)
    
        # Remove alunos que foram excluídos (opcional)
        # df_grid = df_grid[df_grid["Aluno"].isin(nomes_alunos)].reset_index(drop=True)
    
    else:
        # cria grid vazio
        data = {"Aluno": nomes_alunos}
        for dia in dias_no_mes:
            data[dia] = ""
        df_grid = pd.DataFrame(data)

    # LIMPEZA
    df_grid = df_grid.drop(columns=["_id"], errors="ignore")
    df_grid = df_grid.fillna("")
    df_grid = df_grid.astype(str)

    st.subheader(f"Registro de Presenças - {hoje.strftime('%B/%Y')}")

    # ✅ TABELA EDITÁVEL
    new_df = st.data_editor(
        df_grid,
        use_container_width=True,
        num_rows="dynamic",
        key="presencas_editor"
    )

    # Botão para salvar
    if st.button("Salvar Presenças"):
        col_presencas.update_one(
            {"ano": ano, "mes": mes},
            {"$set": {
                "ano": ano,
                "mes": mes,
                "tabela": new_df.to_dict("records")
            }},
            upsert=True
        )
        st.success("Presenças salvas com sucesso!")

    if st.button("Exportar PDF de Presenças"):
        pdf_bytes = exportar_pdf_presencas(new_df)
        st.download_button("Baixar PDF", pdf_bytes, "presencas.pdf", "application/pdf")
    from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import io
import base64
from bson import ObjectId

def gerar_pdf_relatorio_aluno(aluno_id):
    aluno = col_alunos.find_one({"_id": ObjectId(aluno_id)})

    if not aluno:
        st.error("Aluno não encontrado.")
        return

    # Recupera dados das outras coleções
    mensalidades = list(col_mensalidades.find({"aluno_id": aluno_id}))
    presencas = list(col_presencas.find({"aluno_id": aluno_id}))
    exames = list(col_exames.find({"aluno_id": aluno_id}))
    emprestimos = list(col_emprestimos.find({"aluno_id": aluno_id}))
    equipamentos = list(col_equipamentos.find({"aluno_id": aluno_id}))

    # Cria buffer de memória para PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Desenha o cabeçalho (imagem)
    cabecalho_path = "cabecario.jpg"  # caminho da imagem
    c.drawImage(cabecalho_path, 50, 750, width=500, height=80, preserveAspectRatio=True)

    # Começa a escrever abaixo do cabeçalho
    y = 740
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Relatório Completo do Aluno - {aluno['nome']}")
    y -= 30

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Nome: {aluno['nome']}")
    y -= 15
    c.drawString(50, y, f"RG: {aluno.get('rg', '')}")
    y -= 15
    c.drawString(50, y, f"Telefone: {aluno.get('telefone', '')}")
    y -= 15
    c.drawString(50, y, f"Faixa: {aluno.get('faixa', '')}")
    y -= 15
    c.drawString(50, y, f"Data de Nascimento: {aluno.get('data_nascimento', '')}")
    y -= 25

    def escreve_titulo(titulo):
        nonlocal y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"{titulo}:")
        y -= 20
        c.setFont("Helvetica", 10)

    def escreve_linhas(linhas):
        nonlocal y
        for linha in linhas:
            c.drawString(60, y, linha)
            y -= 7

    # Mensalidades
    escreve_titulo("Mensalidades")
    if mensalidades:
        linhas = [
            f"Mês/Ano: {m.get('mes')}/{m.get('ano')} - Valor: {m.get('valor')} - Pago: {m.get('pago', False)}"
            for m in mensalidades
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])
    y -= 10

    # Presenças
    escreve_titulo("Presenças")
    if presencas:
        linhas = [
            f"Data: {p.get('data')} - Aula: {p.get('aula', '')}"
            for p in presencas
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])
    y -= 10

    # Exames
    escreve_titulo("Exames")
    if exames:
        linhas = [
            f"Data: {e.get('data')} - Faixa: {e.get('faixa', '')}"
            for e in exames
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])
    y -= 10

    # Empréstimos
    escreve_titulo("Empréstimos")
    if emprestimos:
        linhas = [
            f"Item: {em.get('item', '')} - Data: {em.get('data', '')}"
            for em in emprestimos
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])
    y -= 10

    # Equipamentos
    escreve_titulo("Equipamentos")
    if equipamentos:
        linhas = [
            f"Equipamento: {eq.get('nome', '')} - Data compra: {eq.get('data_compra', '')}"
            for eq in equipamentos
        ]
        escreve_linhas(linhas)
    else:
        escreve_linhas(["Nenhum registro."])

    # Finaliza PDF
    c.showPage()
    c.save()

    buffer.seek(0)

    # Para permitir download no Streamlit
    b64_pdf = base64.b64encode(buffer.read()).decode("utf-8")
    href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="relatorio_{aluno["nome"]}.pdf">📄 Download Relatório PDF</a>'
    st.markdown(href, unsafe_allow_html=True)
   
    if st.button("Gerar PDF do Relatório"):
        gerar_pdf_relatorio_aluno(aluno_id)
    
from datetime import datetime, timedelta
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import urllib.parse

# -------------------------------
# Pagina Mensalidades
# -------------------------------
from datetime import datetime
import streamlit as st
from pymongo import MongoClient
import urllib

# -------------------------------
# BANCO
# -------------------------------
client = MongoClient(MONGO_URI)
db = client["academia_karate"]
col_alunos = db["alunos"]
col_mensalidades = db["mensalidades"]

# -------------------------------
# FUNÇÃO
# -------------------------------
def pagina_mensalidades():
    st.header("🥋 空手道 (Karatedō) - Mensalidades Registradas")

    # → define hoje ANTES do form
    hoje = datetime.today().date()

    # -------------------------------
    # Exibir mensalidades existentes
    # -------------------------------
    mensalidades = list(col_mensalidades.find().sort("vencimento", -1))

    if mensalidades:
        for m in mensalidades:
            pago = "✅" if m.get("pago") else "❌"

            # cria colunas para texto e botão lado a lado
            col1, col2 = st.columns([0.8, 0.2])

            with col1:
                st.markdown(f"📌 **{m['aluno']}** | Vencimento: {m['vencimento']} | Pago: {pago}")

            with col2:
                botao_excluir = st.button(
                    "🗑️ Excluir",
                    key=f"excluir_{str(m['_id'])}"
                )

            if botao_excluir:
                col_mensalidades.delete_one({"_id": m["_id"]})
                st.success(f"Mensalidade de {m['aluno']} excluída!")
                st.rerun()

    else:
        st.info("Nenhuma mensalidade registrada.")

    # -------------------------------
    # Exibir alunos que NÃO pagaram
    # -------------------------------
    st.subheader("🚫 Alunos em débito")

    mensalidades_nao_pagas = list(col_mensalidades.find({"pago": False}))

    inadimplentes = []

    for m in mensalidades_nao_pagas:
        vencimento_str = m.get("vencimento", "")
        try:
            vencimento_date = datetime.strptime(vencimento_str, "%Y-%m-%d").date()
        except:
            # se estiver salvo como string diferente (p.ex. dd/mm/yyyy)
            try:
                vencimento_date = datetime.strptime(vencimento_str, "%d/%m/%Y").date()
            except:
                vencimento_date = None

        if vencimento_date and vencimento_date < hoje:
            # está vencido
            inadimplentes.append({
                "aluno": m["aluno"],
                "vencimento": vencimento_str
            })

    if inadimplentes:
        for inad in inadimplentes:
            aluno_nome = inad["aluno"]
            venc = inad["vencimento"]

            st.markdown(f"🔴 **{aluno_nome}** - Vencimento: {venc}")

            # buscar telefone do aluno
            aluno_doc = col_alunos.find_one({"nome": aluno_nome})
            if aluno_doc and aluno_doc.get("telefone"):
                telefone = aluno_doc["telefone"]
            else:
                telefone = "5511999999999"   # coloque um número padrão ou deixe em branco

            # mensagem personalizada
            msg = f"Olá {aluno_nome}! Sua mensalidade venceu em {venc}. Poderia regularizar, por favor?"
            msg_url = urllib.parse.quote(msg)

            # gerar link WhatsApp
            link_whatsapp = f"https://wa.me/{telefone}?text={msg_url}"

            st.markdown(f"[📲 Enviar WhatsApp]({link_whatsapp})", unsafe_allow_html=True)
            st.write("---")

    else:
        st.success("Nenhum aluno inadimplente!")

    # -------------------------------
    # Formulário para registrar nova mensalidade
    # -------------------------------
    st.header("🥋 空手道 (Karatedō) - Registrar Mensalidade")

    with st.form("form_mensalidade"):
        alunos = list(col_alunos.find())
        aluno_nomes = [a["nome"] for a in alunos]

        aluno = st.selectbox("Aluno", aluno_nomes)

        # calcula o próximo dia 5
        if hoje.day <= 5:
            prox_venc = hoje.replace(day=5)
        else:
            # pula para o mês seguinte
            ano = hoje.year + (1 if hoje.month == 12 else 0)
            mes = 1 if hoje.month == 12 else hoje.month + 1
            prox_venc = hoje.replace(year=ano, month=mes, day=5)

        vencimento = st.date_input("Data de Vencimento", value=prox_venc)
        pago = st.checkbox("Pago?")

        submit = st.form_submit_button("Registrar")

        if submit:
            col_mensalidades.insert_one({
                "aluno": aluno,
                "vencimento": str(vencimento),
                "pago": pago
            })
            st.success("Mensalidade registrada!")
            st.rerun()
import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson import ObjectId
import io
import base64
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# ---------------------------------------------------------------
# CONFIGURAÇÃO MONGO DB
# ---------------------------------------------------------------

MONGO_URI = "mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/"
DB_NAME = "academia_karate"
COL_ALUNOS = "alunos"
COL_EXAMES = "exames"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col_alunos = db[COL_ALUNOS]
col_exames = db[COL_EXAMES]

# ---------------------------------------------------------------
# BUSCAR DADOS DE EXAMES
# ---------------------------------------------------------------

def buscar_dados_exames():
    exames = list(col_exames.find({}))
    alunos = []
    for doc in exames:
        alunos.append({
            "nome": doc.get("aluno", "Sem nome"),
            "faixa": doc.get("faixa", "Sem faixa"),
            "data_exame": doc.get("data", "Sem data"),
            "status": doc.get("status", "Sem status"),
        })
    return alunos

# ---------------------------------------------------------------
# EXPORTAR PDF COM CABEÇALHO E EXAMES
# ---------------------------------------------------------------

def exportar_pdf_exames(alunos):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    imagem_cabecalho = "cabecario.jpg"

    try:
        img = ImageReader(imagem_cabecalho)
        img_width_px = 1208
        img_height_px = 311

        scale_factor = width / img_width_px
        img_width_pts = width
        img_height_pts = img_height_px * scale_factor

        c.drawImage(
            img,
            x=0,
            y=height - img_height_pts,
            width=img_width_pts,
            height=img_height_pts,
            mask='auto'
        )

        y_pos = height - img_height_pts - 30

    except Exception as e:
        st.error(f"Erro ao carregar imagem do cabeçalho: {e}")
        y_pos = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y_pos, "Relatório de Exames")

    y_pos -= 30
    c.setFont("Helvetica", 12)

    if alunos:
        for aluno in alunos:
            texto = f"Nome: {aluno['nome']} | Faixa: {aluno['faixa']} | Data: {aluno['data_exame']} | Status: {aluno['status']}"
            c.drawString(50, y_pos, texto)
            y_pos -= 20
            if y_pos < 50:
                c.showPage()
                y_pos = height - 50
    else:
        c.drawString(50, y_pos, "Nenhum exame encontrado.")

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ---------------------------------------------------------------
# PÁGINA DE EXAMES
# ---------------------------------------------------------------

def pagina_exames():
    st.header("🥋 空手道 (Karatedō) - Gerenciar Exames")

    # -------------------------------------------------------
    # FORMULÁRIO PARA NOVO EXAME
    # -------------------------------------------------------

    alunos = list(col_alunos.find())
    st.subheader("📝 Registrar Novo Exame")

    with st.form("form_exame"):
        aluno_nomes = [a["nome"] for a in alunos]
        aluno = st.selectbox("Aluno", aluno_nomes)
        data = st.date_input("Data do Exame")
        belt_progression = {
            "Branca": "Cinza",
            "Cinza": "Amarela",
            "Amarela": "Vermelha",
            "Vermelho": "Laranja",
            "Laranja": "Verde",
            "Verde": "Azul",
            "Azul": "Roxa",
            "Roxa": "Marrom",
            "Marrom": "Preta",
            "Preta": None
        }
        faixa = st.selectbox("Faixa", list(belt_progression.keys()))
        status = st.selectbox("Status", ["Aprovado", "Reprovado"])

        if st.form_submit_button("Registrar"):
            col_exames.insert_one({
                "aluno": aluno,
                "data": str(data),
                "faixa": faixa,
                "status": status
            })
            st.success("Exame registrado com sucesso!")
            st.rerun()

    st.divider()

    # -------------------------------------------------------
    # FORMULÁRIO PARA EDITAR EXAME
    # -------------------------------------------------------

    if st.session_state.get("edit_mode"):
        exame_id = st.session_state["edit_exame_id"]
        exame = col_exames.find_one({"_id": ObjectId(exame_id)})

        st.subheader("✏️ Alterar Exame")
        with st.form("form_edit_exame"):
            aluno = st.text_input("Aluno", exame["aluno"], disabled=True)
            data = st.date_input("Data do Exame", pd.to_datetime(exame["data"]))
            faixa = st.selectbox("Faixa", list(belt_progression.keys()),
                                 index=list(belt_progression.keys()).index(exame["faixa"]))
            status = st.selectbox("Status", ["Aprovado", "Reprovado"],
                                  index=0 if exame["status"] == "Aprovado" else 1)

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Salvar Alterações"):
                    col_exames.update_one(
                        {"_id": ObjectId(exame_id)},
                        {"$set": {
                            "data": str(data),
                            "faixa": faixa,
                            "status": status
                        }}
                    )
                    st.success("Exame alterado com sucesso!")
                    st.session_state["edit_mode"] = False
                    st.rerun()
            with col2:
                if st.form_submit_button("Cancelar"):
                    st.session_state["edit_mode"] = False
                    st.rerun()

    st.divider()

    # -------------------------------------------------------
    # EXPORTAR PDF
    # -------------------------------------------------------

    st.subheader("📄 Exportar Exames")

    alunos_exames = buscar_dados_exames()

    if st.button("Exportar PDF de Exames"):
        pdf_bytes = exportar_pdf_exames(alunos_exames)
        st.download_button(
            "Baixar PDF",
            pdf_bytes,
            file_name="exames.pdf",
            mime="application/pdf"
        )

    st.divider()
    # -------------------------------------------------------
    # EXIBIR RELATÓRIO INDIVIDUAL NA TELA
    # -------------------------------------------------------

#    if st.session_state.get("show_relatorio", False):
#       nome_aluno = st.session_state["relatorio_aluno_nome"]
#      exames = st.session_state["relatorio_exames"]
#
#       st.header(f"📄 Relatório Individual - {nome_aluno}")
#
#       if exames:
#          df = pd.DataFrame(exames)
#            df = df[["data", "faixa", "status"]]
#            df.columns = ["Data", "Faixa", "Status"]
#            st.table(df)
#        else:
#            st.info("Este aluno não possui exames registrados.")
#
#        if st.button("⬅️ Voltar"):
#            st.session_state["show_relatorio"] = False
#            st.rerun()
    # -------------------------------------------------------
    # HISTÓRICO DE EXAMES POR ALUNO
    # -------------------------------------------------------

    st.subheader("📚 Histórico de Exames por Aluno")

    for aluno_doc in alunos:
        exames = list(col_exames.find({"aluno": aluno_doc["nome"]}).sort("data", -1))

        if exames:
            st.markdown(f"### 👤 {aluno_doc['nome']}")

            df = pd.DataFrame(exames)
            df = df[["data", "faixa", "status"]]
            df.columns = ["Data", "Faixa", "Status"]
            st.table(df)

            for exame in exames:
                exame_id = str(exame["_id"])

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"❌ Excluir exame {exame_id}", key=f"excluir_{exame_id}"):
                        col_exames.delete_one({"_id": ObjectId(exame_id)})
                        st.success("Exame excluído!")
                        st.rerun()
                with col2:
                    if st.button(f"✏️ Alterar exame {exame_id}", key=f"alterar_{exame_id}"):
                        st.session_state["edit_exame_id"] = exame_id
                        st.session_state["edit_mode"] = True
                        st.rerun()

            col3, col4 = st.columns(2)

            #with col3:
            #    if st.button(f"🔎 Ver relatório individual de {aluno_doc['nome']}", key=f"relatorio_{aluno_doc['_id']}"):
            #        st.session_state["relatorio_aluno_nome"] = aluno_doc["nome"]
            #        st.session_state["relatorio_exames"] = exames
            #        st.session_state["show_relatorio"] = True
            #        st.rerun()

            with col4:
                if st.button(f"📄 Gerar PDF de {aluno_doc['nome']}", key=f"pdf_{aluno_doc['_id']}"):
                    buffer = io.BytesIO()
                    c = canvas.Canvas(buffer, pagesize=A4)
                    
                    # Definir largura e altura da página
                    width, height = A4
                    
                    imagem_cabecalho = "cabecario.jpg"
                    
                    try:
                        # Carregar e desenhar a imagem
                        img = ImageReader(imagem_cabecalho)
                        img_width_px = 1208
                        img_height_px = 311
                    
                        scale_factor = width / img_width_px
                        img_width_pts = width
                        img_height_pts = img_height_px * scale_factor
                    
                        c.drawImage(
                            img,
                            x=0,
                            y=height - img_height_pts,
                            width=img_width_pts,
                            height=img_height_pts,
                            mask='auto'
                        )
                    
                        # Definir posição inicial do texto abaixo da imagem
                        y = height - img_height_pts - 30
                    
                    except Exception as e:
                        st.error(f"Erro ao carregar cabeçalho: {e}")
                        y = height - 50  # valor padrão se imagem falhar
                    
                    # A partir daqui: desenhar título e conteúdo normalmente
                    c.setFont("Helvetica-Bold", 16)
                    c.drawString(50, y, f"Relatório de Exames - {aluno_doc['nome']}")
                    y -= 30
                    
                    c.setFont("Helvetica", 12)
                    
                    for exame in exames:
                        data_str = exame["data"]
                        texto = f"Data: {data_str} | Faixa: {exame['faixa']} | Status: {exame['status']}"
                        c.drawString(50, y, texto)
                        y -= 20
                        if y < 50:
                            c.showPage()
                            y = height - 50
                    buffer = io.BytesIO()
                    c = canvas.Canvas(buffer, pagesize=A4)
                    
                    # Definir largura e altura da página
                    width, height = A4
                    
                    imagem_cabecalho = "cabecario.jpg"
                    
                    try:
                        # Carregar e desenhar a imagem
                        img = ImageReader(imagem_cabecalho)
                        img_width_px = 1208
                        img_height_px = 311
                    
                        scale_factor = width / img_width_px
                        img_width_pts = width
                        img_height_pts = img_height_px * scale_factor
                    
                        c.drawImage(
                            img,
                            x=0,
                            y=height - img_height_pts,
                            width=img_width_pts,
                            height=img_height_pts,
                            mask='auto'
                        )
                    
                        # Definir posição inicial do texto abaixo da imagem
                        y = height - img_height_pts - 30
                    
                    except Exception as e:
                        st.error(f"Erro ao carregar cabeçalho: {e}")
                        y = height - 50  # valor padrão se imagem falhar
                    
                    # A partir daqui: desenhar título e conteúdo normalmente
                    c.setFont("Helvetica-Bold", 16)
                    c.drawString(50, y, f"Relatório de Exames - {aluno_doc['nome']}")
                    y -= 30
                    
                    c.setFont("Helvetica", 12)
                    
                    for exame in exames:
                        data_str = exame["data"]
                        texto = f"Data: {data_str} | Faixa: {exame['faixa']} | Status: {exame['status']}"
                        c.drawString(50, y, texto)
                        y -= 20
                        if y < 50:
                            c.showPage()
                            y = height - 50


                    c.showPage()
                    c.save()
                    buffer.seek(0)

                    b64 = base64.b64encode(buffer.read()).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="relatorio_{aluno_doc["nome"]}.pdf">📥 Download do PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)


        else:
            st.info(f"Aluno **{aluno_doc['nome']}** ainda não possui exames registrados.")

    
#-----------------------------------------------------------------------
#PAGINA EMPRESTIMOS
#-----------------------------------------------------------------------
def pagina_emprestimos():
    st.title("🥋 空手道 (Karatedō) - 📦 Gerenciamento de Empréstimos")

    # --- Cadastro de Equipamentos ---
    with st.expander("Cadastrar Novo Equipamento", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            tipo = st.selectbox("Tipo de Equipamento", 
                ["Kimono", "Faixa", "Luvas", "Colete", "Protetor Bucal", "Bandeira", "Apostila"])

            tamanho = st.selectbox("Tamanho", ["PP", "P", "M", "G", "GG", "XG"])

            codigo = st.text_input("Código/Número (ex: K001, F001)")

            estado = st.selectbox("Estado", ["Novo", "Bom", "Regular", "Ruim"])

        with col2:
            cor_faixa = None
            if tipo.lower() == "faixa":
                cor_faixa = st.selectbox("Cor da Faixa", 
                    ["Branca", "Cinza", "Azul", "Amarela", "Vermelha", "Laranja", "Verde", "Roxa", "Marrom", "Preta"])

        if st.button("Cadastrar Equipamento"):
            if not codigo.strip():
                st.error("Informe o código do equipamento.")
            else:
                equip_doc = {
                    "tipo": tipo,
                    "tamanho": tamanho,
                    "codigo": codigo.strip(),
                    "estado": estado,
                }
                if cor_faixa:
                    equip_doc["cor_faixa"] = cor_faixa

                existe = col_equipamentos.find_one({"codigo": equip_doc["codigo"]})
                if existe:
                    st.error("Já existe um equipamento com esse código.")
                else:
                    col_equipamentos.insert_one(equip_doc)
                    st.success("Equipamento cadastrado com sucesso!")
                    st.rerun()

    st.markdown("---")

    # --- Registrar Novo Empréstimo ---
    with st.expander("Registrar Novo Empréstimo", expanded=True):
        alunos = list(col_alunos.find())
        equipamentos = list(col_equipamentos.find({"estado": {"$in": ["Novo", "Bom", "Regular"]}}))

        emprestados_ids = [e['equipamento_id'] for e in col_emprestimos.find({"devolvido": False})]
        equipamentos_disponiveis = [eq for eq in equipamentos if eq["_id"] not in emprestados_ids]

        nomes_alunos = [a.get("nome", "Sem nome") for a in alunos]
        nomes_equip = [f"{eq.get('tipo', 'Tipo?')} ({eq.get('codigo', 'Código?')})" for eq in equipamentos_disponiveis]

        aluno_sel = st.selectbox("Aluno", [""] + nomes_alunos)
        equipamento_sel = st.selectbox("Equipamento Disponível", [""] + nomes_equip)

        data_emprestimo = st.date_input("Data de Empréstimo", value=datetime.today())
        data_devolucao = st.date_input("Data de Devolução Prevista", value=datetime.today() + timedelta(days=7))
        observacoes = st.text_input("Observações")

        if st.button("Registrar Empréstimo"):
            if not aluno_sel:
                st.error("Selecione um aluno.")
            elif not equipamento_sel:
                st.error("Selecione um equipamento disponível.")
            elif data_devolucao < data_emprestimo:
                st.error("Data de devolução não pode ser anterior à data do empréstimo.")
            else:
                aluno_doc = next((a for a in alunos if a.get("nome") == aluno_sel), None)
                equipamento_doc = next((eq for eq in equipamentos_disponiveis if f"{eq.get('tipo', 'Tipo?')} ({eq.get('codigo', 'Código?')})" == equipamento_sel), None)

                if not aluno_doc or not equipamento_doc:
                    st.error("Erro ao localizar aluno ou equipamento.")
                else:
                    col_emprestimos.insert_one({
                        "aluno_id": aluno_doc["_id"],
                        "aluno": aluno_sel,
                        "equipamento_id": equipamento_doc["_id"],
                        "equipamento": equipamento_sel,
                        "data_emprestimo": data_emprestimo.strftime("%Y-%m-%d"),
                        "data_devolucao": data_devolucao.strftime("%Y-%m-%d"),
                        "observacoes": observacoes,
                        "devolvido": False,
                    })
                    st.success("Empréstimo registrado com sucesso!")
                    st.experimental_rerun()

    st.markdown("---")

    # --- Empréstimos Ativos ---
    st.subheader("🥋 空手道 (Karatedō) - Empréstimos Ativos")
    emprestimos_ativos = list(col_emprestimos.find({"devolvido": False}))

    if not emprestimos_ativos:
        st.info("Nenhum empréstimo ativo no momento.")
    else:
        for emp in emprestimos_ativos:
            col1, col2, col3 = st.columns([6,3,3])
            with col1:
                st.markdown(
                    f"**Aluno:** {emp.get('aluno', 'Sem nome')}  \n"
                    f"**Equipamento:** {emp.get('equipamento', 'Sem equipamento')}  \n"
                    f"**Data Empréstimo:** {emp.get('data_emprestimo', 'N/A')}  \n"
                    f"**Previsão Devolução:** {emp.get('data_devolucao', 'N/A')}  \n"
                    f"**Observações:** {emp.get('observacoes','')}"
                )
            with col2:
                if st.button(f"Registrar Devolução", key=f"dev_{emp['_id']}"):
                    col_emprestimos.update_one({"_id": emp["_id"]}, {"$set": {"devolvido": True}})
                    st.success(f"Devolução registrada para {emp.get('aluno', '')}.")
                    st.experimental_rerun()
            with col3:
                if st.button(f"Excluir", key=f"del_emp_{emp['_id']}"):
                    col_emprestimos.delete_one({"_id": emp["_id"]})
                    st.success("Empréstimo excluído.")
                    st.experimental_rerun()

    st.markdown("---")

    # --- Histórico de Empréstimos ---
    st.subheader("🥋 空手道 (Karatedō) - Histórico de Empréstimos")
    emprestimos_todos = list(col_emprestimos.find().sort("data_emprestimo", -1))

    if not emprestimos_todos:
        st.info("Nenhum histórico de empréstimos.")
    else:
        for emp in emprestimos_todos:
            status = "✅ Devolvido" if emp.get("devolvido", False) else "❌ Em aberto"
            st.markdown(
                f"**Aluno:** {emp.get('aluno', 'Sem nome')}  \n"
                f"**Equipamento:** {emp.get('equipamento', 'Sem equipamento')}  \n"
                f"**Data Empréstimo:** {emp.get('data_emprestimo', 'N/A')}  \n"
                f"**Data Devolução Prevista:** {emp.get('data_devolucao', 'N/A')}  \n"
                f"**Observações:** {emp.get('observacoes','')}  \n"
                f"**Status:** {status}"
            )
            st.markdown("---")

    st.markdown("---")

# -------------------------------------------------------
# PÁGINA DE EQUIPAMENTOS
# ------------------------------------------------------
   
def pagina_equipamentos():

    # --- Inventário de Equipamentos ---
    st.subheader("🥋 空手道 (Karatedō) - Inventário de Equipamentos")
    equipamentos_todos = list(col_equipamentos.find())

    if not equipamentos_todos:
        st.info("Nenhum equipamento cadastrado.")
    else:
        for eq in equipamentos_todos:
            cor_faixa = eq.get("cor_faixa", "")
            faixa_info = f" | Cor Faixa: {cor_faixa}" if cor_faixa else ""

            tipo = eq.get('tipo', 'Tipo não informado')
            tamanho = eq.get('tamanho', 'Tamanho não informado')
            codigo = eq.get('codigo', 'Código não informado')
            estado = eq.get('estado', 'Estado não informado')

            col1, col2 = st.columns([7,3])
            with col1:
                st.markdown(
                    f"**Tipo:** {tipo}  \n"
                    f"**Tamanho:** {tamanho}  \n"
                    f"**Código:** {codigo}  \n"
                    f"**Estado:** {estado}{faixa_info}"
                )
            with col2:
                if st.button(f"Excluir Equipamento - {codigo}", key=f"del_eq_{eq['_id']}"):
                    col_equipamentos.delete_one({"_id": eq["_id"]})
                    st.success(f"Equipamento {codigo} excluído.")
                    st.experimental_rerun()
            st.markdown("---")

#--------------------------------------------------------
# PÁGINA DE ADMIN DO SISTEMA
# -------------------------------------------------------

def pagina_admin_system():
    st.header("🔐 Administração de Usuários")

    st.subheader("Criar Novo Usuário")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    confirmar = st.text_input("Confirme a Senha", type="password")
    nivel = st.selectbox("Nível", ["admin", "user"])

    if st.button("Criar Usuário"):
        if not usuario or not senha:
            st.error("Preencha todos os campos.")
        elif senha != confirmar:
            st.error("Senhas não coincidem.")
        else:
            hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())
            col_usuarios.insert_one({
                "usuario": usuario,
                "senha": hashed,
                "nivel": nivel
            })
            st.success(f"Usuário {usuario} ({nivel}) criado!")


# ---------- CONTROLE DE SESSÃO ----------

# Verifica se já existe usuário cadastrado
if col_usuarios.count_documents({}) == 0:
    criar_admin()
elif not st.session_state.logado:
    login()
else:
    # BARRA SUPERIOR COM MENU E BOTÃO SAIR
    st.markdown("""
        <style>
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #ffffff;
            padding: 10px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 9999;
        }
        .menu-radio label {
            margin-right: 15px;
            font-weight: 600;
            cursor: pointer;
        }
        .menu-radio input[type="radio"] {
            margin-right: 5px;
        }
        .logout-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
        }
        </style>
    """, unsafe_allow_html=True)

    # Cria a barra superior
    col1, col2 = st.columns([8, 1])
    with col1:
        pagina = st.radio(
           "Menu",
           ["Alunos", "Presenças", "Mensalidades", "Exames", "Empréstimos", "Equipamentos", "Cadastros Gerais", "Sistema"],
           horizontal=True,
           label_visibility="collapsed"
        )

        def logout():
            st.session_state.logado = False
            st.rerun()

    with col2:
       if st.button("🚪 Sair", use_container_width=True):
        logout()
            
    # Exibe a página selecionada
    if pagina == "Alunos":
        pagina_alunos()
    elif pagina == "Presenças":
        pagina_presencas()
    elif pagina == "Mensalidades":
        pagina_mensalidades()
        #enviar_alerta_mensalidade()
    elif pagina == "Exames":
        pagina_exames()
    elif pagina == "Empréstimos":
        pagina_emprestimos()
    elif pagina == "Equipamentos":
        pagina_equipamentos()
    elif pagina == "Cadastros Gerais":
        pagina_geral()
    elif pagina == "Sistema":
        pagina_admin_system()

