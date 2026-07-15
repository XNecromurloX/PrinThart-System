import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import time
from datetime import date
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

# --- SISTEMA DE LOGIN ---
USUARIOS = {
    "Ainaht": "Thak9900",
    "XNecromurlocX": "15203"
}

def login():
    st.markdown("""
        <div style='text-align: center; padding: 40px 0 10px 0;'>
            <h1>🎨 PrinThart System</h1>
            <p style='color: gray;'>Inicia sesión para continuar</p>
        </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        usuario = st.text_input("👤 Usuario")
        contrasena = st.text_input("🔒 Contraseña", type="password")
        if st.button("Iniciar sesión", use_container_width=True):
            if usuario in USUARIOS and USUARIOS[usuario] == contrasena:
                st.session_state["autenticado"] = True
                st.session_state["usuario_actual"] = usuario
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    login()
    st.stop()

# --- SISTEMA DE FONDOS PERSONALIZADOS ---
if "fondo_activo" not in st.session_state:
    st.session_state.fondo_activo = "default"
if "fondo_url" not in st.session_state:
    st.session_state.fondo_url = ""

# Fondos predefinidos
FONDOS_PREDEFINIDOS = {
    "default": "",
    "gradient_blue": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "gradient_sunset": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    "gradient_ocean": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
    "gradient_forest": "linear-gradient(135deg, #0ba360 0%, #3cba92 100%)",
    "gradient_purple": "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",
    "blur_stats": "linear-gradient(135deg, rgba(30, 60, 114, 0.8) 0%, rgba(42, 82, 152, 0.8) 100%)",
}

# CSS para sidebar con fondo de mármol verde/azul
sidebar_css = """
<style>
    [data-testid="stSidebar"] {
        background: url('https://i.pinimg.com/736x/e5/50/ae/e550ae51d7dd5b40fa2f9c8dc2cc13e2.jpg');
        background-size: cover;
        background-position: center;
        backdrop-filter: blur(2px);
    }
    [data-testid="stSidebar"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(20, 40, 80, 0.3);
        pointer-events: none;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
        position: relative;
        z-index: 1;
    }
</style>
"""

# Aplicar CSS del sidebar siempre
st.markdown(sidebar_css, unsafe_allow_html=True)

# CSS para fondo de página completa (si está activado)
if st.session_state.fondo_activo != "default":
    if st.session_state.fondo_activo == "custom" and st.session_state.fondo_url:
        fondo_css = f"""
        <style>
            .stApp {{
                background: url('{st.session_state.fondo_url}');
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
        </style>
        """
        st.markdown(fondo_css, unsafe_allow_html=True)
    else:
        fondo_actual = FONDOS_PREDEFINIDOS.get(st.session_state.fondo_activo, "")
        if fondo_actual:
            fondo_css = f"""
            <style>
                .stApp {{
                    background: {fondo_actual};
                    background-attachment: fixed;
                }}
            </style>
            """
            st.markdown(fondo_css, unsafe_allow_html=True)

# --- CONEXIÓN BASE DE DATOS SUPABASE (PostgreSQL) ---
@st.cache_resource
def get_connection():
    """
    Devuelve una conexión psycopg2 RealDictCursor.
    - Lee st.secrets["DATABASE_URL"]
    - Reemplaza postgres:// por postgresql:// si es necesario
    - Añade sslmode=require si no existe (necesario para Supabase)
    """
    dsn = st.secrets.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL no encontrada en st.secrets")

    # Asegura el esquema aceptado por psycopg2 (postgresql://)
    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)

    # Añadir sslmode=require si no existe
    parsed = urlparse(dsn)
    query = parse_qs(parsed.query)
    if "sslmode" not in query:
        query["sslmode"] = ["require"]
        new_query = urlencode(query, doseq=True)
        parsed = parsed._replace(query=new_query)
        dsn = urlunparse(parsed)

    try:
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.OperationalError as e:
        st.error("Error al conectar con la base de datos. Revisa DATABASE_URL en st.secrets y la configuración de red/SSL.")
        st.exception(e)
        raise

# inicializa conexión cached
conn = get_connection()

def get_cursor():
    """
    Devuelve un cursor válido. Si la conexión murió intenta reconectar.
    Usa la variable global conn y re-asigna si hace falta.
    """
    global conn
    try:
        # Acceso ligero para comprobar si la conexión está viva
        _ = conn.isolation_level
    except Exception:
        conn = get_connection()
    return conn.cursor()

# --- CREAR TABLAS SI NO EXISTEN ---
def crear_tablas():
    cur = get_cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            fecha TEXT,
            cliente TEXT,
            detalle TEXT,
            cantidad INTEGER,
            precio_unidad REAL DEFAULT 0.0,
            total REAL,
            estado TEXT,
            materiales_usados TEXT,
            pagado BOOLEAN DEFAULT FALSE,
            inventario_descontado BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            material TEXT PRIMARY KEY,
            cantidad INTEGER,
            detalle TEXT,
            precio_compra REAL DEFAULT 0.0,
            precio_venta REAL DEFAULT 0.0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bajas_material (
            id SERIAL PRIMARY KEY,
            material TEXT,
            cantidad INTEGER,
            fecha TEXT,
            motivo TEXT,
            costo_unitario REAL,
            costo_total REAL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS suplidores (
            id SERIAL PRIMARY KEY,
            nombre TEXT,
            whatsapp TEXT,
            sitio TEXT,
            producto TEXT
        )
    ''')
    conn.commit()
    cur.close()

crear_tablas()

# Migración: agregar columna 'pagado' si no existe
try:
    cur = get_cursor()
    cur.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS pagado BOOLEAN DEFAULT FALSE")
    conn.commit()
    cur.close()
except:
    pass

# Migración: agregar columna 'inventario_descontado' si no existe
try:
    cur = get_cursor()
    cur.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS inventario_descontado BOOLEAN DEFAULT FALSE")
    conn.commit()
    cur.close()
except:
    pass

# --- FUNCIÓN LEER DATOS ---
def read_df(query, params=None):
    try:
        cur = get_cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        if rows:
            return pd.DataFrame([dict(r) for r in rows])
        else:
            # Devolver DataFrame vacío con columnas correctas
            cur2 = get_cursor()
            if params:
                cur2.execute(query, params)
            else:
                cur2.execute(query)
            cols = [desc[0] for desc in cur2.description]
            cur2.close()
            return pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Error leyendo datos: {e}")
        return pd.DataFrame()

# --- FUNCIONES AUXILIARES ---
def mostrar_feedback(tipo, mensaje, tiempo=2):
    if tipo == "exito":
        st.success(mensaje)
        st.balloons()
        time.sleep(tiempo)
        st.rerun()
    elif tipo == "advertencia":
        st.warning(mensaje)
        time.sleep(tiempo)
        st.rerun()
    elif tipo == "error":
        st.error(mensaje)
    elif tipo == "info":
        st.info(mensaje)

def safe_query(query, params=None, many=False):
    try:
        cur = get_cursor()
        if params:
            if many:
                cur.executemany(query, params)
            else:
                cur.execute(query, params)
        else:
            cur.execute(query)
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        conn.rollback()
        mostrar_feedback("error", f"Ocurrió un error en la base de datos: {e}")
        return False

# --- ESTADOS ---
lista_estados = ["Por confirmar", "Sin diseñar", "Diseños listos", "Listos para entregar"]
lista_estados_nuevo_pedido = ["Por confirmar", "Sin diseñar"]  # Solo para crear pedidos
lista_estados_todos = lista_estados + ["Entregado"]

# --- MENÚ LATERAL ---
st.sidebar.title("🎨 PrinThart System")
st.sidebar.caption(f"👤 {st.session_state.get('usuario_actual', '')}")
if st.sidebar.button("🚪 Cerrar sesión"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_actual"] = ""
    st.rerun()
st.sidebar.divider()
menu = st.sidebar.radio("Navegación", [
    "Entregas",
    "Nuevo pedido",
    "Inventario",
    "Suplidores",
    "Estados"
])

# --- RESUMEN FINANCIERO PEQUEÑO EN SIDEBAR ---
df_entregas = read_df("SELECT * FROM pedidos WHERE estado = 'Entregado'")
inventario_df = read_df("SELECT * FROM inventario")
bajas_df = read_df("SELECT * FROM bajas_material")

# Asegurar que la columna pagado existe
if not df_entregas.empty and 'pagado' not in df_entregas.columns:
    df_entregas['pagado'] = False

# FILTRAR SOLO PEDIDOS PAGADOS para calcular finanzas
df_entregas_pagados = df_entregas[df_entregas['pagado'] == True] if not df_entregas.empty else df_entregas

ingresos_totales = df_entregas_pagados['total'].sum() if not df_entregas_pagados.empty else 0
cantidad_pedidos = len(df_entregas)  # Total de entregas (pagadas y no pagadas)
cantidad_pagados = len(df_entregas_pagados)  # Solo pagadas

costos_totales = 0
if not df_entregas_pagados.empty and not inventario_df.empty:
    for _, row in df_entregas_pagados.iterrows():
        materiales = json.loads(row['materiales_usados']) if row['materiales_usados'] else []
        for material in materiales:
            mat_name = material['material']
            mat_cant = material['cantidad']
            mat_precio_compra = inventario_df[inventario_df['material'] == mat_name]['precio_compra'].values
            if len(mat_precio_compra) > 0:
                costos_totales += mat_precio_compra[0] * mat_cant

gastos_baja = bajas_df['costo_total'].sum() if not bajas_df.empty else 0
ganancia_neta = ingresos_totales - costos_totales
margen_ganancia = (ganancia_neta / ingresos_totales * 100) if ingresos_totales > 0 else 0

st.sidebar.markdown("#### 📊 Finanza (entregas)")
st.sidebar.caption(f"💰 Ingresos: ${ingresos_totales:,.0f}")
st.sidebar.caption(f"🧾 Costos: ${costos_totales:,.0f}")
st.sidebar.caption(f"🗑️ Baja: ${gastos_baja:,.0f}")
st.sidebar.caption(f"🔹 Ganancia: ${ganancia_neta:,.0f}")
st.sidebar.caption(f"📈 Margen: {margen_ganancia:.1f}%")
st.sidebar.caption(f"📦 Entregas: {cantidad_pedidos}")
st.sidebar.caption(f"✅ Pagadas: {cantidad_pagados}")

# --- BOTÓN DE AJUSTES EN ESQUINA SUPERIOR DERECHA ---
col_ajustes1, col_ajustes2 = st.columns([6, 1])
with col_ajustes2:
    with st.popover("⚙️", use_container_width=True):
        st.markdown("### ⚙️ Ajustes")
        st.caption("Personaliza tu aplicación")
        
        st.markdown("#### 🎨 Fondos Predefinidos")
        
        fondo_opciones = {
            "🔲 Por defecto": "default",
            "🔵 Azul": "gradient_blue",
            "🌅 Sunset": "gradient_sunset",
            "🌊 Océano": "gradient_ocean",
            "🌲 Bosque": "gradient_forest",
            "💜 Morado": "gradient_purple",
            "📊 Blur": "blur_stats",
        }
        
        seleccion = st.selectbox(
            "Elige un fondo:",
            list(fondo_opciones.keys()),
            key="fondo_select_popup"
        )
        
        if st.button("✅ Aplicar", key="btn_aplicar_fondo_popup", use_container_width=True):
            st.session_state.fondo_activo = fondo_opciones[seleccion]
            st.session_state.fondo_url = ""
            st.rerun()
        
        st.divider()
        st.markdown("#### 🔗 Fondo desde URL")
        
        url_fondo = st.text_input(
            "URL de imagen:",
            placeholder="https://...",
            key="input_url_popup",
            label_visibility="collapsed"
        )
        
        if st.button("🔗 Aplicar URL", key="btn_url_popup", use_container_width=True):
            if url_fondo.strip():
                st.session_state.fondo_activo = "custom"
                st.session_state.fondo_url = url_fondo.strip()
                st.rerun()
        
        st.divider()
        
        if st.button("🔄 Restablecer", key="btn_reset_popup", use_container_width=True):
            st.session_state.fondo_activo = "default"
            st.session_state.fondo_url = ""
            st.rerun()

# (el resto del archivo permanece igual — no modificado por el patch)
