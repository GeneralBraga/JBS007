import streamlit as st
import pandas as pd
import re
import itertools
from io import BytesIO
from fpdf import FPDF
from datetime import datetime
import os

# --- CONFIGURAÇÃO INICIAL ---
favicon_path = "logo_pdf.png" if os.path.exists("logo_pdf.png") else "🏛️"

st.set_page_config(
    page_title="JBS SNIPER",
    page_icon=favicon_path,
    layout="wide"
)

# --- CORES DA MARCA ---
COLOR_GOLD = "#84754e"
COLOR_BEIGE = "#ecece4"
COLOR_BG = "#0e1117"

# --- CSS PERSONALIZADO ---
st.markdown(f"""
<style>
    .stApp {{background-color: {COLOR_BG}; color: {COLOR_BEIGE};}}
    .stButton>button {{
        width: 100%; 
        background-color: {COLOR_GOLD}; 
        color: white; 
        border: none; 
        border-radius: 6px; 
        font-weight: bold; 
        text-transform: uppercase;
        padding: 12px;
        letter-spacing: 1px;
    }}
    .stButton>button:hover {{
        background-color: #6b5e3d; 
        color: {COLOR_BEIGE};
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }}
    h1, h2, h3 {{color: {COLOR_GOLD} !important; font-family: 'Helvetica', sans-serif;}}
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div {{
        background-color: #1c1f26; 
        color: white; 
        border: 1px solid {COLOR_GOLD};
    }}
    div[data-testid="stDataFrame"], .streamlit-expanderHeader {{
        border: 1px solid {COLOR_GOLD};
        background-color: #1c1f26;
    }}
</style>
""", unsafe_allow_html=True)

# --- CABEÇALHO ---
c1, c2 = st.columns([1, 5])
with c1:
    if os.path.exists("logo_app.png"):
        st.image("logo_app.png", width=220)
    else:
        st.markdown(f"<h1 style='color:{COLOR_GOLD}'>JBS</h1>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<h1 style='margin-top: 15px; margin-bottom: 0px;'>SISTEMA SNIPER</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin-top: 0px; color: {COLOR_BEIGE} !important;'>Ferramenta Exclusiva da JBS Contempladas</h3>", unsafe_allow_html=True)

st.markdown(f"<hr style='border: 1px solid {COLOR_GOLD}; margin-top: 0;'>", unsafe_allow_html=True)

# --- FUNÇÕES ---
def limpar_moeda(texto):
    if not texto: return 0.0
    texto = str(texto).lower().strip().replace('\xa0', '').replace('&nbsp;', '')
    texto = re.sub(r'[^\d\.,]', '', texto)
    if not texto: return 0.0
    try:
        if ',' in texto and '.' in texto: return float(texto.replace('.', '').replace(',', '.'))
        elif ',' in texto: return float(texto.replace(',', '.'))
        elif '.' in texto:
             if len(texto.split('.')[1]) == 2: return float(texto)
             return float(texto.replace('.', ''))
        return float(texto)
    except: return 0.0

def extrair_dados_universal(texto_copiado):
    lista_cotas = []
    texto_limpo = "\n".join([line.strip() for line in texto_copiado.split('\n') if line.strip()])
    
    # ATUALIZAÇÃO: Adicionado 'directions' e 'selecionar' para pegar o padrão iContemplados
    blocos = re.split(r'(?i)(?=imóvel|imovel|automóvel|automovel|veículo|caminhão|moto|directions|selecionar)', texto_limpo)
    
    if len(blocos) < 2: blocos = texto_limpo.split('\n\n')

    id_cota = 1
    for bloco in blocos:
        if len(bloco) < 20: continue
        bloco_lower = bloco.lower()
        
        # Identificação de Administradora
        admins = ['BRADESCO', 'SANTANDER', 'ITAÚ', 'ITAU', 'PORTO', 'CAIXA', 'BANCO DO BRASIL', 'BB', 'RODOBENS', 'EMBRACON', 'ANCORA', 'ÂNCORA', 'MYCON', 'SICREDI', 'SICOOB', 'MAPFRE', 'HS', 'YAMAHA', 'ZEMA', 'BANCORBRÁS', 'BANCORBRAS', 'SERVOPA']
        admin_encontrada = "OUTROS"
        for adm in admins:
            if adm.lower() in bloco_lower:
                admin_encontrada = adm.upper()
                break
        
        # Ignora blocos sem admin ou sem valores (exceto se for admin reconhecida)
        if admin_encontrada == "OUTROS" and "r$" not in bloco_lower: continue

        # Tipo de Cota
        tipo_cota = "Geral"
        if "imóvel" in bloco_lower or "imovel" in bloco_lower: tipo_cota = "Imóvel"
        elif "automóvel" in bloco_lower or "automovel" in bloco_lower or "veículo" in bloco_lower or "carro" in bloco_lower: tipo_cota = "Automóvel"
        elif "caminhão" in bloco_lower or "pesado" in bloco_lower: tipo_cota = "Pesados"
        elif "moto" in bloco_lower: tipo_cota = "Automóvel" # Motos tratadas como auto/geral
        elif "directions_car" in bloco_lower: tipo_cota = "Automóvel" # Específico iContemplados

        # Extração de Crédito
        credito = 0.0
        # Padrão 1: Rótulo na mesma linha
        match_cred = re.search(r'(?:crédito|credito|bem|valor)[^\d\n]*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_cred: 
            credito = limpar_moeda(match_cred.group(1))
        else:
            # Fallback (Pega o maior valor do bloco, comum no iContemplados onde o crédito vem solto)
            valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
            vals = sorted([limpar_moeda(v) for v in valores], reverse=True)
            if vals: credito = vals[0]

        # Extração de Entrada
        entrada = 0.0
        # Padrão 1: Rótulo na mesma linha
        match_ent = re.search(r'(?:entrada|ágio|agio|quero|pago)[^\d\n]*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_ent: 
            entrada = limpar_moeda(match_ent.group(1))
        else:
            # Padrão 2 (iContemplados): Rótulo, quebra de linha, valor
            match_ent_break = re.search(r'(?:entrada|ágio|agio).*?R\$\s?([\d\.,]+)', bloco_lower, re.DOTALL)
            if match_ent_break:
                 # Verificação simples para não pegar valor longe demais
                 if len(match_ent_break.group(0)) < 50: 
                    entrada = limpar_moeda(match_ent_break.group(1))
            
            if entrada == 0:
                # Fallback: Segundo maior valor do bloco
                valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
                vals = sorted([limpar_moeda(v) for v in valores], reverse=True)
                if len(vals) > 1: entrada = vals[1]

        # Extração de Parcelas
        regex_parc = r'(\d+)\s*[xX]\s*R?\$\s?([\d\.,]+)'
        todas_parcelas = re.findall(regex_parc, bloco)
        
        saldo_devedor = 0.0
        parcela_teto = 0.0
        prazo_final = 0
        
        for pz_str, vlr_str in todas_parcelas:
            pz = int(pz_str)
            vlr = limpar_moeda(vlr_str)
            saldo_devedor += (pz * vlr)
            if pz > 1 and vlr > parcela_teto: 
                parcela_teto = vlr
                prazo_final = pz
            elif len(todas_parcelas) == 1: 
                parcela_teto = vlr
                prazo_final = pz

        if credito > 0 and entrada > 0:
            if saldo_devedor == 0: saldo_devedor = (credito * 1.3) - entrada
            custo_total = entrada + saldo_devedor
            if credito > 5000: 
                lista_cotas.append({
                    'ID': id_cota, 'Admin': admin_encontrada, 'Tipo': tipo_cota,
                    'Crédito': credito, 'Entrada': entrada,
                    'Parcela': parcela_teto, 'Prazo': prazo_final, 'Saldo': saldo_devedor, 
                    'CustoTotal': custo_total,
                    'EntradaPct': (entrada/credito) if credito else 0
                })
                id_cota += 1
    return lista_cotas

def processar_combinacoes(cotas, min_cred, max_cred, max_ent, max_parc, max_custo, tipo_filtro):
    combinacoes_validas = []
    cotas_por_admin = {}
    
    for cota in cotas:
        if tipo_filtro != "Todos" and cota['Tipo'] != tipo_filtro: continue
        adm = cota['Admin']
        if adm not in cotas_por_admin: cotas_por_admin[adm] = []
        cotas_por_admin[adm].append(cota)
    
    progress_bar = st.progress(0)
    total_admins = len(cotas_por_admin)
    current = 0

    if total_admins == 0: return pd.DataFrame()

    for admin, grupo in cotas_por_admin.items():
        if admin == "OUTROS": continue
        current += 1
        progress_bar.progress(int((current / total_admins) * 100))
        grupo.sort(key=lambda x: x['EntradaPct'])
        
        count = 0
        max_ops = 3000000 
        
        for r in range(1, 7):
            iterator = itertools.combinations(grupo, r)
            while True:
                try:
                    combo = next(iterator)
                    count += 1
                    if count > max_ops: break
                    
                    soma_ent = sum(c['Entrada'] for c in combo)
                    if soma_ent > (max_ent * 1.05): continue
                    soma_cred = sum(c['Crédito'] for c in combo)
                    if soma_cred < min_cred or soma_cred > max_cred: continue
                    soma_parc = sum(c['Parcela'] for c in combo)
                    if soma_parc > (max_parc * 1.05): continue
                    
                    soma_saldo = sum(c['Saldo'] for c in combo)
                    custo_total_abs = soma_ent + soma_saldo
                    custo_real = (custo_total_abs / soma_cred) - 1
                    if custo_real > max_custo: continue
                    
                    pct_entrada = (soma_ent / soma_cred) if soma_cred > 0 else 0
                    prazos_str = " + ".join([str(c['Prazo']) for c in combo])
                    ids = " + ".join([str(c['ID']) for c in combo])
                    detalhes = " || ".join([f"[ID {c['ID']}] {c['Tipo']} Cr: {c['Crédito']:,.0f}" for c in combo])
                    tipo_final = combo[0]['Tipo']
                    
                    status = "⚠️ PADRÃO"
                    if custo_real <= 0.20: status = "💎 OURO"
                    elif custo_real <= 0.35: status = "🔥 IMPERDÍVEL"
                    elif custo_real <= 0.45: status = "✨ EXCELENTE"
                    elif custo_real <= 0.50: status = "✅ OPORTUNIDADE"
                    
                    combinacoes_validas.append({
                        'Admin': admin, 'Status': status, 'Tipo': tipo_final, 'IDs': ids,
                        'Crédito Total': soma_cred, 
                        'Entrada Total': soma_ent,
