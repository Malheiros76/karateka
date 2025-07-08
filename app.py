import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import io
from dateutil.relativedelta import relativedelta
import urllib.parse
from datetime import datetime, timedelta
import bcrypt
import pandas as pd
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder
import streamlit as st
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from PIL import Image
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
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
    'Preta': {'next': 'Preta1', 'months': 12, 'value': 110.00}
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

def exportar_pdf_presencas():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # -----------------------------------
    # Buscar dados do dojo
    # -----------------------------------
    dojo = col_dojo.find_one({
        "_id": ObjectId("686bbeld488b17fb0be63470")
    })

    if dojo and dojo.get("logo_data"):
        image_data = dojo["logo_data"]

        # Abrir imagem do logo
        image = Image.open(io.BytesIO(image_data))

        # Converter para ImageReader
        img_reader = ImageReader(image)

        # Desenhar imagem
        c.drawImage(img_reader, 2*cm, 26*cm, width=4*cm, height=4*cm)

        # Nome do dojo ao lado do brasão
        c.setFont("Helvetica-Bold", 16)
        c.drawString(7*cm, 28*cm, dojo.get("nome", "Dojo"))
    else:
        # Caso não encontre logo
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2*cm, 28*cm, "Relatório de Presenças")

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

from datetime import datetime, timedelta
import streamlit as st
from bson import ObjectId

def pagina_alunos():
    st.header("🥋 空手道 (Karatedō) - Alunos Cadastrados")
    alunos = list(col_alunos.find())

    if alunos:
        for a in alunos:
            col1, col2, col3 = st.columns([4, 4, 4])
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
import numpy as np

# ------------------------------------
# CONFIGURAÇÃO DO BANCO
# ------------------------------------
# client = MongoClient("mongodb://localhost:27017/")
# db = client["karate"]
# col_alunos = db["alunos"]
# col_presencas = db["presencas"]

def pagina_presencas():
    st.header("🥋 空手道 (Karatedō) - Presenças")

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

    registros = list(col_presencas.find({"ano": ano, "mes": mes}))
    df_presencas = pd.DataFrame(registros)

    if df_presencas.empty:
        # cria grade vazia
        data = {"Aluno": nomes_alunos}
        for dia in dias_no_mes:
            data[dia] = ""
        df_grid = pd.DataFrame(data)
    else:
        registro = df_presencas.iloc[0]
        if "tabela" in registro and registro["tabela"] is not None:
            df_grid = pd.DataFrame(registro["tabela"])
        else:
            st.warning("Documento encontrado, mas sem dados salvos. Exibindo grade vazia.")
            data = {"Aluno": nomes_alunos}
            for dia in dias_no_mes:
                data[dia] = ""
            df_grid = pd.DataFrame(data)

    # ---------------------------------------------------------
    # VALIDAÇÃO E PREPARAÇÃO DO DATAFRAME PARA AgGrid
    # ---------------------------------------------------------

    df_grid.reset_index(drop=True, inplace=True)

    # Renomeia coluna mal formatada se necessário
    if 0 in df_grid.columns:
        st.warning("Corrigindo coluna inválida chamada '0'")
        df_grid = df_grid.rename(columns={0: "Aluno"})

    # Força que "Aluno" exista
    if "Aluno" not in df_grid.columns:
        col_candidatas = [col for col in df_grid.columns if isinstance(col, str) and "nome" in col.lower()]
        if col_candidatas:
            df_grid = df_grid.rename(columns={col_candidatas[0]: "Aluno"})

    colunas_esperadas = ["Aluno"] + dias_no_mes
    for col in colunas_esperadas:
        if col not in df_grid.columns:
            df_grid[col] = ""

    df_grid = df_grid.dropna(how="all").fillna("")

    for col in df_grid.columns:
        if df_grid[col].apply(lambda x: isinstance(x, (list, dict, np.ndarray))).any():
            df_grid[col] = df_grid[col].apply(str)

    for col in df_grid.columns:
        if df_grid[col].apply(lambda x: callable(x)).any():
            st.error(f"🛑 ERRO: A coluna '{col}' contém função. Isso quebra o AgGrid.")
            st.stop()

    st.subheader(f"Registro de Presenças - {hoje.strftime('%B/%Y')}")

    if df_grid.empty:
        st.info("Nenhum dado para exibir.")
        return

    # ---------------------------
    # CONFIGURAÇÃO DO GRID
    # ---------------------------
    gb = GridOptionsBuilder.from_dataframe(df_grid)
    gb.configure_default_column(editable=True, minWidth=80, resizable=True)
    gb.configure_column("Aluno", editable=False, pinned="left", width=250)

    for col in df_grid.columns:
        if col != "Aluno":
            gb.configure_column(col, editable=True, width=80)

    grid_options = gb.build()

    try:
        grid_response = AgGrid(
            df_grid,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.VALUE_CHANGED,
            fit_columns_on_grid_load=False,
            height=1000,
            key="presencas_grid"
        )
    except Exception as e:
        st.error(f"Erro ao renderizar AgGrid: {e}")
        st.stop()

    new_df = grid_response["data"]

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

# -------------------------------------------------------
# PÁGINA DE MENSALIDADES
# -------------------------------------------------------

def pagina_mensalidades():
    st.header("🥋 空手道 (Karatedō) - Mensalidades Registradas")
    mensalidades = list(col_mensalidades.find().sort("vencimento", -1))
    if mensalidades:
        for m in mensalidades:
            pago = "✅" if m.get("pago") else "❌"
            st.markdown(f"📌 {m['aluno']} | Vencimento: {m['vencimento']} | Pago: {pago}")
    else:
        st.info("Nenhuma mensalidade registrada.")

    st.header("🥋 空手道 (Karatedō) - Registrar Mensalidade")
    with st.form("form_mensalidade"):
        alunos = list(col_alunos.find())
        aluno_nomes = [a["nome"] for a in alunos]
        aluno = st.selectbox("Aluno", aluno_nomes)
       # calcula o próximo dia 5
        hoje = datetime.today().date()
        if hoje.day <= 5:
            prox_venc = hoje.replace(day=5)
        else:
        # pula para o mês seguinte
            ano = hoje.year + (1 if hoje.month == 12 else 0)
            mes = 1 if hoje.month == 12 else hoje.month + 1
            prox_venc = hoje.replace(year=ano, month=mes, day=5)
        vencimento = st.date_input("Data de Vencimento", value=prox_venc)
        pago = st.checkbox("Pago?")
        if st.form_submit_button("Registrar"):
            col_mensalidades.insert_one({
                "aluno": aluno,
                "vencimento": str(vencimento),
                "pago": pago
            })
            st.success("Mensalidade registrada!")
            st.rerun()

    if st.button("Exportar PDF de Mensalidades"):
        pdf_bytes = exportar_pdf_mensalidades()
        st.download_button("Baixar PDF", pdf_bytes, "mensalidades.pdf", "application/pdf")
      
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    import io
    from datetime import datetime

    def gerar_pdf_grade(df, mes, ano):
        buffer = io.BytesIO()
        
        # Cria PDF em paisagem
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        
        # Título
        c.setFont("Helvetica-Bold", 16)
        titulo = f"Grade de Presença - {datetime(ano, mes, 1).strftime('%B/%Y')}"
        c.drawString(2 * cm, 19 * cm, titulo)
        
        # Prepara dados para tabela
        data = [list(df.columns)] + df.astype(str).values.tolist()
        
        # Cria tabela do reportlab
        table = Table(data, repeatRows=1, colWidths=[3*cm] + [1.2*cm]*(len(df.columns)-1))
        
        # Estilo da tabela
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
        ])
        table.setStyle(style)
        
        # Posiciona tabela
        table.wrapOn(c, 20*cm, 15*cm)
        table.drawOn(c, 2 * cm, 2 * cm)
        
        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

        # --- PDF Download ---
        pdf_bytes = gerar_pdf_grade(grid_data, mes, ano)

        st.download_button(
            label="📄 Baixar Relatório em PDF",
            data=pdf_bytes,
            file_name=f"grade_presenca_{mes}_{ano}.pdf",
            mime="application/pdf",
    )   
# -------------------------------------------------------
# PÁGINA DE EXAMES
# -------------------------------------------------------

def pagina_exames():
    st.header("🥋 空手道 (Karatedō) - Histórico de Exames")

    alunos = list(col_alunos.find())

    for aluno_doc in alunos:
        exames = list(col_exames.find({"aluno": aluno_doc["nome"]}).sort("data", -1))
        if exames:
            ultimo = exames[0]

            next_belt, data_proximo, meses_faltando, dias_faltando, valor = calcular_proximo_exame(
                ultimo["faixa"], ultimo["data"]
            )

            if next_belt:
                if meses_faltando > 0 or dias_faltando > 0:
                    st.info(f"""
                        **Aluno:** {aluno_doc["nome"]}  
                        Último exame: {ultimo["data"]} ({ultimo["faixa"]}, {ultimo["status"]})  
                        Próxima faixa: {next_belt}  
                        Valor do próximo exame: R$ {valor:.2f}  
                        Poderá fazer exame em {data_proximo.strftime("%d/%m/%Y")}  
                        (faltam {meses_faltando} mês(es) e {dias_faltando} dia(s)).
                    """)
                else:
                    st.success(f"""
                        **Aluno:** {aluno_doc["nome"]}  
                        Último exame: {ultimo["data"]} ({ultimo["faixa"]}, {ultimo["status"]})  
                        Próxima faixa: {next_belt}  
                        Valor do próximo exame: R$ {valor:.2f}  
                        ✅ Já pode realizar o próximo exame!
                    """)
            else:
                st.warning(f"""
                    **Aluno:** {aluno_doc["nome"]}  
                    Último exame: {ultimo["data"]} ({ultimo["faixa"]}, {ultimo["status"]})  
                    Não há faixa seguinte cadastrada.
                """)
        else:
            st.info(f"Aluno **{aluno_doc['nome']}** ainda não possui exames registrados.")

    st.divider()

    st.header("🥋 空手道 (Karatedō) - Registrar Novo Exame")
    with st.form("form_exame"):
        aluno_nomes = [a["nome"] for a in alunos]
        aluno = st.selectbox("Aluno", aluno_nomes)
        data = st.date_input("Data do Exame")
        faixa = st.selectbox("Faixa", list(belt_progression.keys()))
        status = st.selectbox("Status", ["Aprovado", "Reprovado"])
        if st.form_submit_button("Registrar"):
            col_exames.insert_one({
                "aluno": aluno,
                "data": str(data),
                "faixa": faixa,
                "status": status
            })
            st.success("Exame registrado!")
            st.rerun()

    if st.button("Exportar PDF de Exames"):
        pdf_bytes = exportar_pdf_exames()
        st.download_button("Baixar PDF", pdf_bytes, "exames.pdf", "application/pdf")

# -------------------------------------------------------
# PÁGINA DE EQUIPAMENTOS
# -------------------------------------------------------

def pagina_equipamentos():
    st.header("🥋 空手道 (Karatedō) - 🎽 Equipamentos")

    equipamentos = list(col_equipamentos.find())
    if equipamentos:
        for eq in equipamentos:
            nome = eq.get('nome', 'Sem nome')
            quantidade = eq.get('quantidade', 0)
            st.markdown(f"**{nome}** - Quantidade: {quantidade}")
    else:
        st.info("Nenhum equipamento cadastrado.")

    st.header("🥋 空手道 (Karatedō) - Adicionar Equipamento")
    with st.form("form_equipamento"):
        nome = st.text_input("Nome do Equipamento")
        quantidade = st.number_input("Quantidade", min_value=0, step=1)
        if st.form_submit_button("Adicionar"):
            if nome:
                col_equipamentos.insert_one({"nome": nome, "quantidade": quantidade})
                st.success("Equipamento adicionado!")
                st.rerun()
            else:
                st.error("Nome do equipamento é obrigatório.")

# -------------------------------------------------------
# PÁGINA DE EMPRESTIMOS
# -------------------------------------------------------

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
            # Mostrar o campo Cor da Faixa só se o tipo for Faixa
            cor_faixa = None
            if tipo.lower() == "faixa":
                cor_faixa = st.selectbox("Cor da Faixa", 
                    ["Branca", "Cinza", "Azul", "Amarela", "Vermelha", "Laranja", "Verde", "Roxa", "Marrom", "Preta"])

        if st.button("Cadastrar Equipamento"):
            # Validar campos
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

                # Verifica se código já existe
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

        # Filtrar equipamentos disponíveis (não emprestados ou devolvidos)
        emprestados_ids = [e['equipamento_id'] for e in col_emprestimos.find({"devolvido": False})]
        equipamentos_disponiveis = [eq for eq in equipamentos if eq["_id"] not in emprestados_ids]

        nomes_alunos = [a["nome"] for a in alunos]
        nomes_equip = [f"{eq['tipo']} ({eq['codigo']})" for eq in equipamentos_disponiveis]

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
                # Encontrar ids dos documentos
                aluno_doc = next((a for a in alunos if a["nome"] == aluno_sel), None)
                equipamento_doc = next((eq for eq in equipamentos_disponiveis if f"{eq['tipo']} ({eq['codigo']})" == equipamento_sel), None)

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
            col1, col2 = st.columns([7,1])
            with col1:
                st.markdown(
                    f"**Aluno:** {emp['aluno']}  \n"
                    f"**Equipamento:** {emp['equipamento']}  \n"
                    f"**Data Empréstimo:** {emp['data_emprestimo']}  \n"
                    f"**Previsão Devolução:** {emp['data_devolucao']}  \n"
                    f"**Observações:** {emp.get('observacoes','')}"
                )
            with col2:
                if st.button(f"Registrar Devolução - {emp['aluno']} - {emp['equipamento']}", key=f"dev_{emp['_id']}"):
                    col_emprestimos.update_one({"_id": emp["_id"]}, {"$set": {"devolvido": True}})
                    st.success(f"Devolução registrada para {emp['aluno']}.")
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
                f"**Aluno:** {emp['aluno']}  \n"
                f"**Equipamento:** {emp['equipamento']}  \n"
                f"**Data Empréstimo:** {emp['data_emprestimo']}  \n"
                f"**Data Devolução Prevista:** {emp['data_devolucao']}  \n"
                f"**Observações:** {emp.get('observacoes','')}  \n"
                f"**Status:** {status}"
            )
            st.markdown("---")

    st.markdown("---")

    # --- Inventário de Equipamentos ---
    st.subheader("🥋 空手道 (Karatedō) - Inventário de Equipamentos")
    equipamentos_todos = list(col_equipamentos.find())

    if not equipamentos_todos:
        st.info("Nenhum equipamento cadastrado.")
    else:
        for eq in equipamentos_todos:
            cor_faixa = eq.get("cor_faixa", "")
            faixa_info = f" | Cor Faixa: {cor_faixa}" if cor_faixa else ""
            st.markdown(
                f"**Tipo:** {eq['tipo']}  \n"
                f"**Tamanho:** {eq['tamanho']}  \n"
                f"**Código:** {eq['codigo']}  \n"
                f"**Estado:** {eq['estado']}{faixa_info}"
            )
            st.markdown("---")

# -------------------------------------------------------
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
        enviar_alerta_mensalidade()
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
