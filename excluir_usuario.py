import streamlit as st
from pymongo import MongoClient
import bcrypt

# --- CONFIGURAÇÃO DO MONGO ---
MONGO_URI = "mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["academia_karate"]
col_usuarios = db["usuarios"]

st.set_page_config(page_title="Admin - Excluir Usuários")

# --- INTERFACE STREAMLIT ---

st.title("🔐 Admin - Exclusão de Usuários")

# Buscar todos os usuários
usuarios = list(col_usuarios.find({}))

if not usuarios:
    st.info("Nenhum usuário encontrado no banco de dados.")
else:
    nomes = [u["usuario"] for u in usuarios]
    
    user_sel = st.selectbox("Selecione o usuário para excluir:", nomes)

    if user_sel:
        usuario_doc = col_usuarios.find_one({"usuario": user_sel})
        nivel = usuario_doc.get("nivel", "N/A")

        st.write(f"**Usuário:** {user_sel}")
        st.write(f"**Nível:** {nivel}")

        if st.button("Excluir Usuário", type="primary"):
            col_usuarios.delete_one({"_id": usuario_doc["_id"]})
            st.success(f"Usuário **{user_sel}** excluído com sucesso!")
            st.rerun()
