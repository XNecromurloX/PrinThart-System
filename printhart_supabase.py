import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import time
from datetime import date

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
    return psycopg2.connect(st.secrets["DATABASE_URL"], cursor_factory=RealDictCursor)

conn = get_connection()

def get_cursor():
    global conn
    try:
        conn.isolation_level  # chequea si sigue viva
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

ingresos_totales = df_entregas['total'].sum() if not df_entregas.empty else 0
cantidad_pedidos = len(df_entregas)

costos_totales = 0
if not df_entregas.empty and not inventario_df.empty:
    for _, row in df_entregas.iterrows():
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

# ---------------------------------------------------------
# ENTREGAS
# ---------------------------------------------------------
if menu == "Entregas":
    st.title("📋 Entregas Completadas")
    df = read_df("SELECT * FROM pedidos WHERE estado = 'Entregado'")
    inventario_df = read_df("SELECT * FROM inventario")
    bajas_df = read_df("SELECT * FROM bajas_material")
    if not df.empty:
        df['materiales_mostrados'] = df['materiales_usados'].apply(
            lambda x: ', '.join([f"{i['material']}({i['cantidad']})" for i in json.loads(x)]) if x else "")
        # Asegurar que la columna pagado existe
        if 'pagado' not in df.columns:
            df['pagado'] = False
        df['pagado_texto'] = df['pagado'].apply(lambda x: '✅ Pagado' if x else '❌ Sin pagar')
        df_orden = df[['id', 'estado', 'cantidad', 'precio_unidad', 'total', 'cliente', 'detalle', 'fecha', 'pagado_texto', 'materiales_mostrados']]
        df_orden = df_orden.rename(columns={
            'id': 'ID', 'estado': 'Estado', 'cantidad': 'Cantidad',
            'precio_unidad': 'Precio x unidad', 'total': 'Precio total',
            'pagado_texto': 'Pago',
            'materiales_mostrados': 'Artículos usados'
        })
        df_orden['Precio x unidad'] = df_orden['Precio x unidad'].astype(int)
        df_orden['Precio total'] = df_orden['Precio total'].astype(int)
        st.dataframe(df_orden, use_container_width=True, hide_index=True)
        st.download_button(label="⬇️ Descargar CSV entregas",
                           data=df_orden.to_csv(index=False).encode('utf-8'),
                           file_name='entregas.csv', mime='text/csv')
        
        st.divider()
        st.subheader("💳 Marcar pago de pedido")
        id_pago = st.selectbox("Selecciona ID de pedido:", df['id'].tolist(), key="id_pago")
        pedido_selec = df[df['id'] == id_pago].iloc[0]
        estado_actual = '✅ Pagado' if pedido_selec.get('pagado', False) else '❌ Sin pagar'
        st.caption(f"Estado actual: {estado_actual}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Marcar como PAGADO"):
                safe_query("UPDATE pedidos SET pagado = TRUE WHERE id = %s", (id_pago,))
                mostrar_feedback("exito", f"Pedido {id_pago} marcado como PAGADO")
        with col2:
            if st.button("❌ Marcar como SIN PAGAR"):
                safe_query("UPDATE pedidos SET pagado = FALSE WHERE id = %s", (id_pago,))
                mostrar_feedback("advertencia", f"Pedido {id_pago} marcado como SIN PAGAR")
    else:
        st.info("No hay entregas completadas aún.")

    st.divider()
    st.subheader("💰 Resumen Financiero de Entregas")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: st.metric("Ingresos", f"${ingresos_totales:,.0f}")
    with col2: st.metric("Costos", f"${costos_totales:,.0f}")
    with col3: st.metric("Ganancia neta", f"${ganancia_neta:,.0f}")
    with col4: st.metric("Baja", f"${gastos_baja:,.0f}")
    with col5: st.metric("Entregas", f"{cantidad_pedidos}")

    if not bajas_df.empty:
        st.expander("🗑️ Ver bajas de inventario").dataframe(
            bajas_df[['material', 'cantidad', 'fecha', 'motivo', 'costo_total']])
    if not df.empty:
        st.divider()
        id_eliminar = st.selectbox("Selecciona pedido entregado a eliminar:", df['id'], key="del_ped_ent")
        if st.button("🗑️ Eliminar pedido seleccionado", key="btn_del_ped_ent"):
            # Obtener el pedido antes de eliminarlo
            pedido_a_eliminar = df[df['id'] == id_eliminar].iloc[0]
            inventario_descontado = pedido_a_eliminar.get('inventario_descontado', False)
            
            # Si el inventario fue descontado, devolverlo
            if inventario_descontado:
                materiales = json.loads(pedido_a_eliminar['materiales_usados']) if pedido_a_eliminar['materiales_usados'] else []
                for m in materiales:
                    safe_query("UPDATE inventario SET cantidad = cantidad + %s WHERE material = %s",
                               (int(m['cantidad']), m['material']))
            
            # Eliminar el pedido
            safe_query("DELETE FROM pedidos WHERE id = %s", (int(id_eliminar),))
            
            if inventario_descontado:
                mostrar_feedback("advertencia", f"Pedido {id_eliminar} eliminado e inventario repuesto.")
            else:
                mostrar_feedback("advertencia", f"Pedido {id_eliminar} eliminado.")

# ---------------------------------------------------------
# NUEVO PEDIDO (SIN FORMULARIO - TIEMPO REAL)
# ---------------------------------------------------------
elif menu == "Nuevo pedido":
    st.title("📝 Registrar nuevo pedido")
    inventario_df = read_df("SELECT * FROM inventario")
    # Filtrar solo materiales con stock disponible
    inventario_con_stock = inventario_df[inventario_df['cantidad'] > 0] if not inventario_df.empty else inventario_df
    inventario_list = inventario_con_stock['material'].tolist() if not inventario_con_stock.empty else []
    
    # Inicializar session_state
    if "material_rows_v2" not in st.session_state:
        st.session_state.material_rows_v2 = [0]
    if "pedido_cliente" not in st.session_state:
        st.session_state.pedido_cliente = ""
    if "pedido_detalle" not in st.session_state:
        st.session_state.pedido_detalle = ""
    if "pedido_estado" not in st.session_state:
        st.session_state.pedido_estado = lista_estados_nuevo_pedido[0]
    if "pedido_fecha" not in st.session_state:
        st.session_state.pedido_fecha = date.today()
    
    # Campos principales
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.pedido_fecha = st.date_input("Fecha", st.session_state.pedido_fecha, key="fecha_ped_v2")
        st.session_state.pedido_cliente = st.text_input("Cliente *", st.session_state.pedido_cliente, key="cli_ped_v2")
    with col2:
        st.session_state.pedido_detalle = st.text_area("Detalle del trabajo", st.session_state.pedido_detalle, height=80, key="det_ped_v2")
        # Usar lista_estados_nuevo_pedido (solo "Por confirmar" y "Sin diseñar")
        if st.session_state.pedido_estado not in lista_estados_nuevo_pedido:
            st.session_state.pedido_estado = lista_estados_nuevo_pedido[0]
        st.session_state.pedido_estado = st.selectbox("Estado", lista_estados_nuevo_pedido, index=lista_estados_nuevo_pedido.index(st.session_state.pedido_estado), key="estado_ped_v2")
    
    st.divider()
    st.markdown("### 📦 Materiales utilizados")
    
    # Botones para agregar/quitar
    cols_acc = st.columns([1, 1, 2])
    if cols_acc[0].button("+ Agregar artículo", key="btn_add_mat_v2"):
        new_key = max(st.session_state.material_rows_v2) + 1 if st.session_state.material_rows_v2 else 0
        st.session_state.material_rows_v2.append(new_key)
        st.rerun()
    
    if len(st.session_state.material_rows_v2) > 1:
        if cols_acc[1].button("- Quitar artículo", key="btn_rem_mat_v2"):
            st.session_state.material_rows_v2.pop()
            st.rerun()
    
    # Recolectar materiales y calcular total EN TIEMPO REAL
    materiales_usados = []
    usados_ya = set()
    precio_total_calculado = 0
    cantidad_total_materiales = 0
    
    for ix in st.session_state.material_rows_v2:
        # Filtrar materiales disponibles
        opciones_disp = [m for m in inventario_list if m not in usados_ya]
        
        if not opciones_disp:
            st.info("No hay más materiales con stock disponible")
            break
        
        cols_mat = st.columns([2, 1, 1])
        
        # Inicializar valores en session_state si no existen
        mat_key = f"mat_sel_{ix}_v2"
        cant_key = f"cant_sel_{ix}_v2"
        precio_key = f"precio_sel_{ix}_v2"
        
        if mat_key not in st.session_state:
            st.session_state[mat_key] = opciones_disp[0]
        if cant_key not in st.session_state:
            st.session_state[cant_key] = 1
        if precio_key not in st.session_state:
            # Obtener precio por defecto del material
            mat_row = inventario_con_stock[inventario_con_stock['material'] == opciones_disp[0]]
            st.session_state[precio_key] = int(mat_row['precio_venta'].iloc[0]) if not mat_row.empty else 0
        
        # Asegurar que el material actual está en opciones disponibles
        if st.session_state[mat_key] not in opciones_disp:
            st.session_state[mat_key] = opciones_disp[0]
        
        with cols_mat[0]:
            mat = st.selectbox(
                f"Material {ix+1}:", 
                opciones_disp, 
                index=opciones_disp.index(st.session_state[mat_key]) if st.session_state[mat_key] in opciones_disp else 0,
                key=f"select_{mat_key}"
            )
            st.session_state[mat_key] = mat
        
        # Obtener info del material seleccionado
        mat_row = inventario_con_stock[inventario_con_stock['material'] == mat]
        if not mat_row.empty:
            max_disp = int(mat_row['cantidad'].iloc[0])
            precio_venta_default = int(mat_row['precio_venta'].iloc[0])
        else:
            max_disp = 0
            precio_venta_default = 0
        
        # Ajustar cantidad si supera el máximo disponible
        if st.session_state[cant_key] > max_disp:
            st.session_state[cant_key] = max_disp if max_disp > 0 else 1
        
        with cols_mat[1]:
            if max_disp > 0:
                cant = st.number_input(
                    "Cantidad", 
                    min_value=1, 
                    max_value=max_disp, 
                    value=st.session_state[cant_key],
                    step=1, 
                    format="%d", 
                    key=f"input_{cant_key}"
                )
                st.session_state[cant_key] = cant
            else:
                cant = 0
        
        with cols_mat[2]:
            # Actualizar precio default si cambió el material
            if precio_key not in st.session_state or st.session_state[precio_key] == 0:
                st.session_state[precio_key] = precio_venta_default
            
            precio = st.number_input(
                "Precio c/u", 
                min_value=0, 
                value=st.session_state[precio_key],
                step=1, 
                format="%d", 
                key=f"input_{precio_key}"
            )
            st.session_state[precio_key] = precio
        
        if cant > 0:
            materiales_usados.append({
                'material': mat,
                'cantidad': int(cant),
                'precio': int(precio)
            })
            usados_ya.add(mat)
            precio_total_calculado += int(cant) * int(precio)
            cantidad_total_materiales += int(cant)
    
    # Mostrar total actualizado EN TIEMPO REAL
    st.markdown(f"### 💵 Total del pedido: ${precio_total_calculado:,.0f} ({cantidad_total_materiales} artículos)")
    
    st.divider()
    
    # Botón para guardar (sin formulario)
    _faltan_ped = []
    if not st.session_state.pedido_cliente.strip():
        _faltan_ped.append("cliente")
    if not materiales_usados:
        _faltan_ped.append("al menos un artículo")
    if precio_total_calculado <= 0:
        _faltan_ped.append("precio mayor a 0")
    if _faltan_ped:
        st.caption(f"⚠️ Falta: {', '.join(_faltan_ped)}")
    if st.button("✅ Guardar pedido", type="primary", key="btn_guardar_pedido_v2"):
        if _faltan_ped:
            mostrar_feedback("error", f"Completa los campos obligatorios: {', '.join(_faltan_ped)}")
        else:
            # Verificar stock
            errores_stock = []
            for m in materiales_usados:
                mat_stock = inventario_df[inventario_df['material'] == m['material']]
                if not mat_stock.empty:
                    stock_actual = int(mat_stock['cantidad'].iloc[0])
                    if m['cantidad'] > stock_actual:
                        errores_stock.append(f"- Stock insuficiente de {m['material']} (disponible: {stock_actual})")
            if errores_stock:
                mostrar_feedback("error", "Corrige los siguientes errores:\n" + "\n".join(errores_stock), tiempo=3)
            else:
                mat_json = json.dumps(materiales_usados, ensure_ascii=False)
                precio_promedio = precio_total_calculado // cantidad_total_materiales if cantidad_total_materiales > 0 else 0
                
                # Guardar pedido SIN descontar inventario (se descontará al cambiar a "Listos para entregar")
                query_ok = safe_query(
                    "INSERT INTO pedidos (fecha, cliente, detalle, cantidad, precio_unidad, total, estado, materiales_usados, pagado, inventario_descontado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (str(st.session_state.pedido_fecha), st.session_state.pedido_cliente.strip(), 
                     st.session_state.pedido_detalle.strip(), cantidad_total_materiales,
                     precio_promedio, precio_total_calculado, st.session_state.pedido_estado, mat_json, False, False)
                )
                
                if query_ok:
                    # NO descontamos inventario aquí - se hará al cambiar estado a "Listos para entregar"
                    
                    # Limpiar session_state después de guardar
                    st.session_state.material_rows_v2 = [0]
                    st.session_state.pedido_cliente = ""
                    st.session_state.pedido_detalle = ""
                    st.session_state.pedido_estado = lista_estados_nuevo_pedido[0]
                    st.session_state.pedido_fecha = date.today()
                    
                    # Limpiar materiales
                    keys_to_delete = [k for k in st.session_state.keys() if k.startswith(('mat_sel_', 'cant_sel_', 'precio_sel_'))]
                    for k in keys_to_delete:
                        del st.session_state[k]
                    
                    mostrar_feedback("exito", f"¡Pedido guardado con éxito! Total: ${precio_total_calculado:,.0f}")
                    st.rerun()

# ---------------------------------------------------------
# INVENTARIO
# ---------------------------------------------------------
elif menu == "Inventario":
    st.title("📦 Inventario de materiales")
    inventario_df = read_df("SELECT * FROM inventario")
    with st.expander("➕ Agregar material", expanded=False):
        with st.form("frm_inventario", clear_on_submit=True):
            material = st.text_input("Nombre del material *")
            cantidad = st.number_input("Cantidad *", min_value=0, step=1, format="%d")
            detalle = st.text_area("Detalle/Descripción (opcional)", height=50)
            precio_compra = st.number_input("Precio de compra (costo unitario) *", min_value=0, step=1, format="%d")
            precio_venta = st.number_input("Precio de venta (unitario) *", min_value=0, step=1, format="%d")
            if st.form_submit_button("Guardar material"):
                errores = []
                if not material.strip(): errores.append("- Nombre obligatorio")
                if cantidad < 0: errores.append("- La cantidad debe ser al menos 0")
                if precio_compra < 0: errores.append("- Precio de compra no puede ser negativo")
                if precio_venta < 0: errores.append("- Precio de venta no puede ser negativo")
                if errores:
                    mostrar_feedback("error", "\n".join(errores))
                else:
                    existe_df = read_df("SELECT * FROM inventario WHERE UPPER(material)=%s", (material.strip().upper(),))
                    if not existe_df.empty:
                        mostrar_feedback("advertencia", f"El material '{material}' ya existe.")
                    else:
                        query_ok = safe_query(
                            "INSERT INTO inventario (material, cantidad, detalle, precio_compra, precio_venta) VALUES (%s,%s,%s,%s,%s)",
                            (material.strip(), int(cantidad), detalle.strip(), int(precio_compra), int(precio_venta))
                        )
                        if query_ok:
                            mostrar_feedback("exito", f"Material '{material}' guardado correctamente")

    # --- REGISTRAR BAJA ---
    st.subheader("🗑️ Registrar baja de material")
    # Filtrar solo materiales con stock disponible
    inventario_con_stock_baja = inventario_df[inventario_df['cantidad'] > 0]
    if not inventario_con_stock_baja.empty:
        mat_baja = st.selectbox("Material:", inventario_con_stock_baja['material'].tolist(), key='select_baja')
        stock_disponible = int(inventario_con_stock_baja[inventario_con_stock_baja['material'] == mat_baja]['cantidad'].iloc[0])
        cant_baja = st.number_input("Cantidad a dar de baja:", min_value=1,
                                    max_value=stock_disponible,
                                    value=1, step=1, key='cant_baja')
        motivo = st.text_input("Motivo (Ej: Daño, vencimiento, uso interno)", value="Daño", key='motivo_baja')
        costo_unit = float(inventario_con_stock_baja[inventario_con_stock_baja['material'] == mat_baja]['precio_compra'].iloc[0])
        fecha_baja = date.today().isoformat()
        if not motivo.strip():
            st.caption("⚠️ El motivo es obligatorio para registrar una baja.")
        if st.button("Registrar baja de material"):
            if not motivo.strip():
                mostrar_feedback("error", "El motivo es obligatorio.")
            else:
                safe_query("UPDATE inventario SET cantidad = cantidad - %s WHERE material = %s", (cant_baja, mat_baja))
                costo_total = costo_unit * cant_baja
                safe_query(
                    "INSERT INTO bajas_material (material, cantidad, fecha, motivo, costo_unitario, costo_total) VALUES (%s, %s, %s, %s, %s, %s)",
                    (mat_baja, cant_baja, fecha_baja, motivo, costo_unit, costo_total)
                )
                mostrar_feedback("exito", f"Baja registrada: {cant_baja} de {mat_baja} por '{motivo}'")
    else:
        st.info("No hay materiales con stock disponible para dar de baja")
    
    # --- EDITAR/ELIMINAR BAJAS ---
    st.divider()
    bajas_df_edit = read_df("SELECT * FROM bajas_material")
    if not bajas_df_edit.empty:
        with st.expander("✏️ Editar o eliminar bajas registradas"):
            st.dataframe(bajas_df_edit[['id', 'material', 'cantidad', 'fecha', 'motivo', 'costo_total']], 
                        use_container_width=True, hide_index=True)
            
            baja_id_editar = st.selectbox("Selecciona ID de baja para editar/eliminar:", 
                                         bajas_df_edit['id'].tolist(), key="baja_edit_select")
            baja_actual = bajas_df_edit[bajas_df_edit['id'] == baja_id_editar].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("✏️ Editar baja")
                st.info(f"📊 **Valores actuales:**\n\n"
                       f"• Material: {baja_actual['material']}\n\n"
                       f"• Cantidad: {int(baja_actual['cantidad'])}\n\n"
                       f"• Motivo: {baja_actual['motivo']}\n\n"
                       f"• Costo total: ${baja_actual['costo_total']:.2f}")
                
                st.caption("⚠️ Solo completa los campos que quieras cambiar")
                nuevo_motivo = st.text_input("Nuevo motivo (dejar vacío para no cambiar):", value="", placeholder=baja_actual['motivo'], key="edit_motivo_baja")
                nueva_cantidad = st.number_input("Nueva cantidad (dejar en 0 para no cambiar):", min_value=0, 
                                                value=0, step=1, key="edit_cant_baja")
                
                if nueva_cantidad > 0:
                    nuevo_costo_total = nueva_cantidad * float(baja_actual['costo_unitario'])
                    st.caption(f"Costo total recalculado: ${nuevo_costo_total:,.2f}")
                
                _nada_baja = not nuevo_motivo.strip() and nueva_cantidad == 0
                if _nada_baja:
                    st.caption("⚠️ Cambia al menos un campo para poder actualizar.")
                if st.button("💾 Actualizar baja", key="btn_update_baja"):
                    if _nada_baja:
                        mostrar_feedback("error", "No hay cambios que guardar.")
                    else:
                        # Solo actualizar campos que no estén vacíos o en 0
                        motivo_final = nuevo_motivo.strip() if nuevo_motivo.strip() else baja_actual['motivo']
                        cantidad_final = nueva_cantidad if nueva_cantidad > 0 else int(baja_actual['cantidad'])
                        costo_final = cantidad_final * float(baja_actual['costo_unitario'])
                        
                        safe_query(
                            "UPDATE bajas_material SET cantidad = %s, motivo = %s, costo_total = %s WHERE id = %s",
                            (cantidad_final, motivo_final, costo_final, baja_id_editar)
                        )
                        mostrar_feedback("exito", f"Baja {baja_id_editar} actualizada correctamente")
            
            with col2:
                st.subheader("🗑️ Eliminar baja")
                st.warning(f"⚠️ Vas a eliminar la baja de {baja_actual['material']}")
                st.caption(f"Cantidad: {baja_actual['cantidad']} | Costo: ${baja_actual['costo_total']:.2f}")
                if st.button("🗑️ Eliminar esta baja", key="btn_del_baja"):
                    safe_query("DELETE FROM bajas_material WHERE id = %s", (baja_id_editar,))
                    mostrar_feedback("advertencia", f"Baja {baja_id_editar} eliminada")

    # --- VISUALIZACIÓN INVENTARIO ---
    inventario_df = read_df("SELECT * FROM inventario")
    bajas_df = read_df("SELECT * FROM bajas_material")
    
    # Checkbox para filtrar materiales con stock
    mostrar_solo_con_stock = st.checkbox("📦 Mostrar solo materiales con stock disponible", value=False, key="filtro_stock")
    
    if not inventario_df.empty:
        inventario_df['cantidad'] = inventario_df['cantidad'].astype(int)
        inventario_df['precio_compra'] = inventario_df['precio_compra'].astype(int)
        inventario_df['precio_venta'] = inventario_df['precio_venta'].astype(int)
        inventario_df['ganancia_unitaria'] = inventario_df['precio_venta'] - inventario_df['precio_compra']
        inventario_df['inversion_total'] = inventario_df['cantidad'] * inventario_df['precio_compra']
        inventario_df['ganancia_total'] = inventario_df['cantidad'] * inventario_df['ganancia_unitaria']
        
        # Calcular bajas por material
        if not bajas_df.empty:
            bajas_agrupadas = bajas_df.groupby('material').agg({
                'cantidad': 'sum',
                'costo_total': 'sum'
            }).reset_index()
            bajas_agrupadas.columns = ['material', 'cantidad_baja', 'costo_baja']
            inventario_df = inventario_df.merge(bajas_agrupadas, on='material', how='left')
        else:
            inventario_df['cantidad_baja'] = 0
            inventario_df['costo_baja'] = 0
        
        inventario_df['cantidad_baja'] = inventario_df['cantidad_baja'].fillna(0).astype(int)
        inventario_df['costo_baja'] = inventario_df['costo_baja'].fillna(0).astype(int)
        
        # Aplicar filtro si está activado
        if mostrar_solo_con_stock:
            inventario_df = inventario_df[inventario_df['cantidad'] > 0]
        
        df_vista = inventario_df[['material', 'cantidad', 'detalle', 'precio_compra', 'precio_venta',
                                   'ganancia_unitaria', 'cantidad_baja', 'costo_baja', 
                                   'inversion_total', 'ganancia_total']].copy()
        df_vista.columns = ['Material', 'Stock', 'Detalle', 'P. Compra', 'P. Venta',
                             'Ganancia/Unidad', 'Cantidad Baja', 'Costo Baja',
                             'Inversión Total', 'Ganancia Total']
        st.dataframe(df_vista, use_container_width=True, hide_index=True)
        
        # --- RESUMEN FINANCIERO DEL INVENTARIO ---
        st.divider()
        st.subheader("💰 Resumen Financiero del Inventario")
        inversion_total_inv = inventario_df['inversion_total'].sum()
        ganancia_potencial = inventario_df['ganancia_total'].sum()
        perdidas_bajas = inventario_df['costo_baja'].sum()
        
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("💵 Inversión Total", f"${inversion_total_inv:,.0f}")
        with col2: st.metric("📈 Ganancia Potencial", f"${ganancia_potencial:,.0f}")
        with col3: st.metric("🗑️ Pérdidas por Bajas", f"${perdidas_bajas:,.0f}")
        st.divider()
        st.subheader("✏️ Editar material")
        mat_editar = st.selectbox("Selecciona material a editar:", inventario_df['material'].unique(), key="edit_mat")
        mat_data = inventario_df[inventario_df['material'] == mat_editar].iloc[0]
        
        # Mostrar valores actuales
        st.info(f"📊 **Valores actuales de '{mat_editar}':**\n\n"
                f"• Cantidad: {int(mat_data['cantidad'])}\n\n"
                f"• Detalle: {mat_data['detalle'] if mat_data['detalle'] else 'Sin detalle'}\n\n"
                f"• Precio compra: ${int(mat_data['precio_compra'])}\n\n"
                f"• Precio venta: ${int(mat_data['precio_venta'])}")
        
        with st.form("frm_editar_material"):
            st.caption("⚠️ Solo completa los campos que quieras cambiar")
            nueva_cantidad = st.number_input("Nueva cantidad (dejar en 0 para no cambiar)", min_value=0, value=0, step=1, format="%d", key='upd_cant')
            nuevo_detalle = st.text_area("Nuevo detalle (dejar vacío para no cambiar)", value="", placeholder=mat_data['detalle'] if mat_data['detalle'] else "Ingresa nuevo detalle", height=50, key='upd_detalle')
            nuevo_precio_compra = st.number_input("Nuevo precio de compra (dejar en 0 para no cambiar)", min_value=0, value=0, step=1, format="%d", key='upd_pc')
            nuevo_precio_venta = st.number_input("Nuevo precio de venta (dejar en 0 para no cambiar)", min_value=0, value=0, step=1, format="%d", key='upd_pv')
            
            if st.form_submit_button("💾 Actualizar material"):
                _nada_mat = (nueva_cantidad == 0 and not nuevo_detalle.strip() and nuevo_precio_compra == 0 and nuevo_precio_venta == 0)
                if _nada_mat:
                    mostrar_feedback("error", "No hay cambios que guardar. Deja los campos en 0 o vacío si no quieres cambiarlos.")
                else:
                    # Solo actualizar campos que no estén en 0 o vacíos
                    cantidad_final = nueva_cantidad if nueva_cantidad > 0 else int(mat_data['cantidad'])
                    detalle_final = nuevo_detalle.strip() if nuevo_detalle.strip() else mat_data['detalle']
                    precio_c_final = nuevo_precio_compra if nuevo_precio_compra > 0 else int(mat_data['precio_compra'])
                    precio_v_final = nuevo_precio_venta if nuevo_precio_venta > 0 else int(mat_data['precio_venta'])
                    
                    safe_query(
                        "UPDATE inventario SET cantidad = %s, detalle = %s, precio_compra = %s, precio_venta = %s WHERE material = %s",
                        (cantidad_final, detalle_final, precio_c_final, precio_v_final, mat_editar)
                    )
                    mostrar_feedback("exito", f"Material '{mat_editar}' actualizado correctamente.")
        st.divider()
        mat_eliminar = st.selectbox("Selecciona material a eliminar:", inventario_df['material'].unique(), key="del_mat")
        if st.button("🗑️ Eliminar material"):
            query_ok = safe_query("DELETE FROM inventario WHERE material = %s", (mat_eliminar,))
            if query_ok:
                mostrar_feedback("advertencia", f"Material '{mat_eliminar}' eliminado.")
    else:
        st.info("No hay materiales registrados.")

# ---------------------------------------------------------
# SUPLIDORES
# ---------------------------------------------------------
elif menu == "Suplidores":
    st.title("🤝 Lista de suplidores")
    with st.expander("➕ Registrar nuevo suplidor", expanded=True):
        with st.form("frm_suplidor", clear_on_submit=True):
            nombre = st.text_input("Nombre de empresa/persona *")
            whatsapp = st.text_input("WhatsApp (opcional)")
            web = st.text_input("Tienda/página web (opcional)")
            producto = st.text_area("¿Qué se compra en este sitio?", height=70)
            if st.form_submit_button("💾 Guardar suplidor"):
                errores = []
                if not nombre.strip(): errores.append("- Nombre obligatorio")
                if whatsapp.strip() and not whatsapp.strip().isdigit():
                    errores.append("- WhatsApp solo debe tener números")
                if errores:
                    mostrar_feedback("error", "\n".join(errores))
                else:
                    existe_df = read_df("SELECT * FROM suplidores WHERE UPPER(nombre)=%s", (nombre.strip().upper(),))
                    if not existe_df.empty:
                        mostrar_feedback("advertencia", f"El suplidor '{nombre}' ya existe.")
                    else:
                        query_ok = safe_query(
                            "INSERT INTO suplidores (nombre, whatsapp, sitio, producto) VALUES (%s, %s, %s, %s)",
                            (nombre.strip(), whatsapp.strip(), web.strip(), producto.strip())
                        )
                        if query_ok:
                            mostrar_feedback("exito", "Suplidor guardado correctamente.")
    suplidores_df = read_df("SELECT * FROM suplidores")
    if not suplidores_df.empty:
        st.dataframe(suplidores_df.rename(
            columns={'nombre': 'Nombre', 'whatsapp': 'WhatsApp', 'sitio': 'Web', 'producto': 'Compra'}),
            use_container_width=True, hide_index=True)
        st.divider()
        supl_del = st.selectbox("Selecciona suplidor a eliminar:", suplidores_df['nombre'].unique(), key="del_sup")
        if st.button("🗑️ Eliminar suplidor", key="btn_del_sup"):
            query_ok = safe_query("DELETE FROM suplidores WHERE nombre = %s", (supl_del,))
            if query_ok:
                mostrar_feedback("advertencia", f"Suplidor '{supl_del}' eliminado.")
    else:
        st.info("No hay suplidores registrados.")

# ---------------------------------------------------------
# ESTADOS
# ---------------------------------------------------------
elif menu == "Estados":
    st.title("📋 Consultar estados de pedidos")
    df = read_df("SELECT * FROM pedidos")
    if df.empty:
        st.info("No hay pedidos registrados aún.")
    else:
        estado_sel = st.selectbox("Selecciona estado:", lista_estados_todos)
        df_est = df[df['estado'] == estado_sel].copy()
        df_est['materiales_mostrados'] = df_est['materiales_usados'].apply(
            lambda x: ', '.join([f"{i['material']}({i['cantidad']})" for i in json.loads(x)]) if x else "")
        df_estado_view = df_est[["id", "estado", "cantidad", "precio_unidad", "total", "cliente", "detalle", "fecha", "materiales_mostrados"]]\
            .rename(columns={
                "id": "ID", "estado": "Estado", "cantidad": "Cantidad",
                "precio_unidad": "Precio x unidad", "total": "Precio total",
                "materiales_mostrados": "Artículos usados"
            })
        st.dataframe(df_estado_view, use_container_width=True, hide_index=True)
        if not df_est.empty:
            st.divider()
            st.subheader("💳 Marcar pago de pedido")
            # Asegurar que columna pagado existe
            if 'pagado' not in df_est.columns:
                df_est['pagado'] = False
            id_pago_estados = st.selectbox("Selecciona ID de pedido:", df_est['id'].tolist(), key="id_pago_estados")
            pedido_pago = df_est[df_est['id'] == id_pago_estados].iloc[0]
            estado_pago_actual = '✅ Pagado' if pedido_pago.get('pagado', False) else '❌ Sin pagar'
            st.caption(f"Estado actual: {estado_pago_actual}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Marcar como PAGADO", key="btn_pago_estados"):
                    safe_query("UPDATE pedidos SET pagado = TRUE WHERE id = %s", (id_pago_estados,))
                    mostrar_feedback("exito", f"Pedido {id_pago_estados} marcado como PAGADO")
            with col2:
                if st.button("❌ Marcar como SIN PAGAR", key="btn_no_pago_estados"):
                    safe_query("UPDATE pedidos SET pagado = FALSE WHERE id = %s", (id_pago_estados,))
                    mostrar_feedback("advertencia", f"Pedido {id_pago_estados} marcado como SIN PAGAR")
            
            st.divider()
            st.subheader("Cambiar estado de un pedido")
            id_cambiar = st.selectbox("Selecciona ID de pedido para cambiar estado:", df_est["id"], key="estado_change")
            nuevo_estado = st.selectbox(
                "Nuevo estado:", [e for e in lista_estados_todos if e != estado_sel], key="estado_nuevo"
            )
            if st.button("Cambiar estado de este pedido", key="btn_estado_cambio"):
                # Obtener el pedido actual
                pedido_actual = df_est[df_est["id"] == id_cambiar].iloc[0]
                inventario_ya_descontado = pedido_actual.get('inventario_descontado', False)
                
                # Estados que requieren inventario descontado
                estados_con_descuento = ["Listos para entregar", "Entregado"]
                
                # CASO 1: Mover A un estado que requiere descuento (y aún no está descontado)
                if nuevo_estado in estados_con_descuento and not inventario_ya_descontado:
                    # Descontar inventario
                    materiales = json.loads(pedido_actual['materiales_usados']) if pedido_actual['materiales_usados'] else []
                    for m in materiales:
                        safe_query("UPDATE inventario SET cantidad = cantidad - %s WHERE material = %s",
                                   (int(m['cantidad']), m['material']))
                    # Marcar como descontado
                    safe_query("UPDATE pedidos SET estado = %s, inventario_descontado = TRUE WHERE id = %s", 
                               (nuevo_estado, int(id_cambiar)))
                    mostrar_feedback("exito", f"Pedido {id_cambiar} cambiado a '{nuevo_estado}' e inventario descontado.")
                
                # CASO 2: Mover DESDE un estado con descuento HACIA uno sin descuento (devolver inventario)
                elif nuevo_estado not in estados_con_descuento and inventario_ya_descontado:
                    # Devolver inventario
                    materiales = json.loads(pedido_actual['materiales_usados']) if pedido_actual['materiales_usados'] else []
                    for m in materiales:
                        safe_query("UPDATE inventario SET cantidad = cantidad + %s WHERE material = %s",
                                   (int(m['cantidad']), m['material']))
                    # Marcar como NO descontado
                    safe_query("UPDATE pedidos SET estado = %s, inventario_descontado = FALSE WHERE id = %s", 
                               (nuevo_estado, int(id_cambiar)))
                    mostrar_feedback("exito", f"Pedido {id_cambiar} cambiado a '{nuevo_estado}' e inventario repuesto.")
                
                # CASO 3: Cambio de estado sin afectar inventario
                else:
                    # Solo cambiar el estado
                    safe_query("UPDATE pedidos SET estado = %s WHERE id = %s", (nuevo_estado, int(id_cambiar)))
                    mostrar_feedback("exito", f"Pedido {id_cambiar} cambiado a '{nuevo_estado}'.")
            
            st.divider()
            st.subheader("✏️ Editar pedido")
            id_editar = st.selectbox("Selecciona ID de pedido para editar:", df_est["id"], key="estado_edit")
            pedido_editar = df_est[df_est["id"] == id_editar].iloc[0]
            
            # Mostrar valores actuales
            st.info(f"📊 **Valores actuales del pedido #{id_editar}:**\n\n"
                   f"• Cliente: {pedido_editar['cliente']}\n\n"
                   f"• Detalle: {pedido_editar['detalle']}\n\n"
                   f"• Total: ${int(pedido_editar['total']):,.0f}\n\n"
                   f"• Cantidad artículos: {int(pedido_editar['cantidad'])}")
            
            with st.form("frm_editar_pedido"):
                st.caption("⚠️ Solo completa los campos que quieras cambiar")
                nuevo_cliente = st.text_input("Nuevo cliente (dejar vacío para no cambiar)", value="", placeholder=pedido_editar['cliente'])
                nuevo_detalle = st.text_area("Nuevo detalle (dejar vacío para no cambiar)", value="", placeholder=pedido_editar['detalle'], height=80)
                nuevo_precio_total = st.number_input("Nuevo precio total (dejar en 0 para no cambiar)", min_value=0, value=0, step=1, format="%d")
                
                if nuevo_precio_total > 0:
                    nuevo_precio_promedio = nuevo_precio_total // int(pedido_editar['cantidad']) if int(pedido_editar['cantidad']) > 0 else 0
                    st.caption(f"💵 Precio promedio por unidad: ${nuevo_precio_promedio:,.0f}")
                
                if st.form_submit_button("💾 Guardar cambios"):
                    _nada_ped = (not nuevo_cliente.strip() and not nuevo_detalle.strip() and nuevo_precio_total == 0)
                    if _nada_ped:
                        mostrar_feedback("error", "No hay cambios que guardar. Deja los campos vacíos o en 0 si no quieres cambiarlos.")
                    else:
                        # Solo actualizar campos que no estén vacíos o en 0
                        cliente_final = nuevo_cliente.strip() if nuevo_cliente.strip() else pedido_editar['cliente']
                        detalle_final = nuevo_detalle.strip() if nuevo_detalle.strip() else pedido_editar['detalle']
                        total_final = nuevo_precio_total if nuevo_precio_total > 0 else int(pedido_editar['total'])
                        precio_promedio_final = total_final // int(pedido_editar['cantidad']) if int(pedido_editar['cantidad']) > 0 else 0
                        
                        safe_query(
                            "UPDATE pedidos SET cliente = %s, detalle = %s, precio_unidad = %s, total = %s WHERE id = %s",
                            (cliente_final, detalle_final, precio_promedio_final, total_final, int(id_editar))
                        )
                        mostrar_feedback("exito", f"Pedido {id_editar} actualizado correctamente.")
            
            st.divider()
            id_eliminar_estado = st.selectbox("Selecciona pedido a eliminar en este estado:", df_est["id"], key="del_estado")
            if st.button("🗑️ Eliminar pedido de este estado"):
                # Obtener el pedido antes de eliminarlo
                pedido_a_eliminar = df_est[df_est['id'] == id_eliminar_estado].iloc[0]
                inventario_descontado = pedido_a_eliminar.get('inventario_descontado', False)
                
                # Si el inventario fue descontado, devolverlo
                if inventario_descontado:
                    materiales = json.loads(pedido_a_eliminar['materiales_usados']) if pedido_a_eliminar['materiales_usados'] else []
                    for m in materiales:
                        safe_query("UPDATE inventario SET cantidad = cantidad + %s WHERE material = %s",
                                   (int(m['cantidad']), m['material']))
                
                # Eliminar el pedido
                safe_query("DELETE FROM pedidos WHERE id = %s", (int(id_eliminar_estado),))
                
                if inventario_descontado:
                    mostrar_feedback("advertencia", f"Pedido {id_eliminar_estado} eliminado e inventario repuesto.")
                else:
                    mostrar_feedback("advertencia", f"Pedido {id_eliminar_estado} eliminado.")
