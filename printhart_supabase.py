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

# --- CONEXIÓN BASE DE DATOS SUPABASE (PostgreSQL) ---
@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"], cursor_factory=RealDictCursor)

conn = get_connection()

def get_cursor():
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
            materiales_usados TEXT
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
        df_orden = df[['id', 'estado', 'cantidad', 'precio_unidad', 'total', 'cliente', 'detalle', 'fecha', 'materiales_mostrados']]
        df_orden = df_orden.rename(columns={
            'id': 'ID', 'estado': 'Estado', 'cantidad': 'Cantidad',
            'precio_unidad': 'Precio x unidad', 'total': 'Precio total',
            'materiales_mostrados': 'Artículos usados'
        })
        df_orden['Precio x unidad'] = df_orden['Precio x unidad'].astype(int)
        df_orden['Precio total'] = df_orden['Precio total'].astype(int)
        st.dataframe(df_orden, use_container_width=True, hide_index=True)
        st.download_button(label="⬇️ Descargar CSV entregas",
                           data=df_orden.to_csv(index=False).encode('utf-8'),
                           file_name='entregas.csv', mime='text/csv')
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
            safe_query("DELETE FROM pedidos WHERE id = %s", (int(id_eliminar),))
            mostrar_feedback("advertencia", f"Pedido {id_eliminar} eliminado.")

# ---------------------------------------------------------
# NUEVO PEDIDO
# ---------------------------------------------------------
elif menu == "Nuevo pedido":
    st.title("📝 Registrar nuevo pedido")
    inventario_df = read_df("SELECT * FROM inventario")
    inventario_list = inventario_df['material'].tolist() if not inventario_df.empty else []
    with st.form("frm_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", date.today(), key="fecha_ped_outf")
            cliente = st.text_input("Cliente *", key="cli_ped_outf")
            detalle = st.text_area("Detalle del trabajo", height=80, key="det_ped_outf")
        with col2:
            precio_unidad = st.number_input("Precio por unidad *", min_value=0, step=1, format="%d", key="ppu_ped_outf")
            precio_total = precio_unidad
            st.text_input("Precio total", value=f"{precio_total}", disabled=True, key="ptotal_ped_outf")
            estado = st.selectbox("Estado", lista_estados, key="estado_ped_outf")
        st.divider()
        st.markdown("### Materiales utilizados")
        if "material_rows" not in st.session_state:
            st.session_state.material_rows = [0]
        cols_acc = st.columns([1, 1])
        agregar_art = cols_acc[0].form_submit_button("+ Agregar artículo")
        quitar_art = False
        if len(st.session_state.material_rows) > 1:
            quitar_art = cols_acc[1].form_submit_button("- Quitar artículo")
        if agregar_art:
            new_key = max(st.session_state.material_rows) + 1 if st.session_state.material_rows else 0
            st.session_state.material_rows.append(new_key)
        if quitar_art:
            st.session_state.material_rows.pop()
        materiales_usados = []
        usados_ya = set()
        for ix in st.session_state.material_rows:
            cols_mat = st.columns([2, 1])
            opciones_disp = [m for m in inventario_list if m not in usados_ya]
            if not opciones_disp: opciones_disp = inventario_list
            with cols_mat[0]:
                mat = st.selectbox("Selecciona artículo:", opciones_disp, key=f"mat_{ix}_OUTF")
            if mat in usados_ya:
                st.warning(f"Ya seleccionaste {mat} en este pedido. Elige otro.")
                continue
            else:
                max_disp = int(inventario_df.loc[inventario_df['material'] == mat, 'cantidad'].iloc[0]) if mat in inventario_list else 1
                with cols_mat[1]:
                    cant = st.number_input("Cantidad", min_value=1, max_value=max_disp, step=1, format="%d", key=f"cant_{ix}_OUTF")
                materiales_usados.append({'material': mat, 'cantidad': int(cant)})
                usados_ya.add(mat)
        enviar = st.form_submit_button("✅ Guardar pedido")
        if enviar:
            errores = []
            if not cliente.strip():
                errores.append("- Cliente obligatorio")
            if int(precio_unidad) <= 0:
                errores.append("- El precio por unidad debe ser mayor a 0")
            for m in materiales_usados:
                existen = inventario_df.loc[inventario_df['material'] == m['material'], 'cantidad'].iloc[0]
                if m['cantidad'] <= 0:
                    errores.append(f"- Debes usar al menos 1 unidad de {m['material']}")
                if m['cantidad'] > existen:
                    errores.append(f"- Stock insuficiente de {m['material']}")
            if errores:
                mostrar_feedback("error", "Corrige los siguientes errores:\n" + "\n".join(errores), tiempo=3)
            else:
                mat_json = json.dumps(materiales_usados, ensure_ascii=False)
                query_ok = safe_query(
                    "INSERT INTO pedidos (fecha, cliente, detalle, cantidad, precio_unidad, total, estado, materiales_usados) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (str(fecha), cliente.strip(), detalle.strip(), 1,
                     int(precio_unidad), int(precio_total), estado, mat_json)
                )
                for m in materiales_usados:
                    safe_query("UPDATE inventario SET cantidad = cantidad - %s WHERE material = %s",
                               (int(m['cantidad']), m['material']))
                if query_ok:
                    st.session_state.material_rows = [0]
                    mostrar_feedback("exito", f"¡Pedido guardado con éxito y stock descontado!")

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
    if not inventario_df.empty:
        mat_baja = st.selectbox("Material:", inventario_df['material'].tolist(), key='select_baja')
        cant_baja = st.number_input("Cantidad a dar de baja:", min_value=1,
                                    max_value=int(inventario_df[inventario_df['material'] == mat_baja]['cantidad']),
                                    value=1, step=1, key='cant_baja')
        motivo = st.text_input("Motivo (Ej: Daño, vencimiento, uso interno)", value="Daño", key='motivo_baja')
        costo_unit = float(inventario_df[inventario_df['material'] == mat_baja]['precio_compra'].iloc[0])
        fecha_baja = date.today().isoformat()
        if st.button("Registrar baja de material"):
            safe_query("UPDATE inventario SET cantidad = cantidad - %s WHERE material = %s", (cant_baja, mat_baja))
            costo_total = costo_unit * cant_baja
            safe_query(
                "INSERT INTO bajas_material (material, cantidad, fecha, motivo, costo_unitario, costo_total) VALUES (%s, %s, %s, %s, %s, %s)",
                (mat_baja, cant_baja, fecha_baja, motivo, costo_unit, costo_total)
            )
            mostrar_feedback("exito", f"Baja registrada: {cant_baja} de {mat_baja} por '{motivo}'")

    # --- VISUALIZACIÓN INVENTARIO ---
    inventario_df = read_df("SELECT * FROM inventario")
    bajas_df = read_df("SELECT * FROM bajas_material")
    
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
        with st.form("frm_editar_material"):
            nueva_cantidad = st.number_input("Nueva cantidad", min_value=0, value=int(mat_data['cantidad']), step=1, format="%d", key='upd_cant')
            nuevo_detalle = st.text_area("Nuevo detalle", value=mat_data['detalle'] if mat_data['detalle'] else "", height=50, key='upd_detalle')
            nuevo_precio_compra = st.number_input("Nuevo precio de compra", min_value=0, value=int(mat_data['precio_compra']), step=1, format="%d", key='upd_pc')
            nuevo_precio_venta = st.number_input("Nuevo precio de venta", min_value=0, value=int(mat_data['precio_venta']), step=1, format="%d", key='upd_pv')
            if st.form_submit_button("💾 Actualizar material"):
                safe_query(
                    "UPDATE inventario SET cantidad = %s, detalle = %s, precio_compra = %s, precio_venta = %s WHERE material = %s",
                    (int(nueva_cantidad), nuevo_detalle.strip(), int(nuevo_precio_compra), int(nuevo_precio_venta), mat_editar)
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
            st.subheader("Cambiar estado de un pedido")
            id_cambiar = st.selectbox("Selecciona ID de pedido para cambiar estado:", df_est["id"], key="estado_change")
            nuevo_estado = st.selectbox(
                "Nuevo estado:", [e for e in lista_estados_todos if e != estado_sel], key="estado_nuevo"
            )
            if st.button("Cambiar estado de este pedido", key="btn_estado_cambio"):
                safe_query("UPDATE pedidos SET estado = %s WHERE id = %s", (nuevo_estado, int(id_cambiar)))
                mostrar_feedback("exito", f"Pedido {id_cambiar} cambiado a '{nuevo_estado}'.")
            
            st.divider()
            st.subheader("✏️ Editar pedido")
            id_editar = st.selectbox("Selecciona ID de pedido para editar:", df_est["id"], key="estado_edit")
            pedido_editar = df_est[df_est["id"] == id_editar].iloc[0]
            
            with st.form("frm_editar_pedido"):
                nuevo_cliente = st.text_input("Cliente", value=pedido_editar['cliente'])
                nuevo_detalle = st.text_area("Detalle del trabajo", value=pedido_editar['detalle'], height=80)
                nuevo_precio = st.number_input("Precio por unidad", min_value=0, value=int(pedido_editar['precio_unidad']), step=1, format="%d")
                nuevo_total = int(pedido_editar['cantidad']) * nuevo_precio
                st.caption(f"💵 Total del pedido: ${nuevo_total:,.0f}")
                
                if st.form_submit_button("💾 Guardar cambios"):
                    safe_query(
                        "UPDATE pedidos SET cliente = %s, detalle = %s, precio_unidad = %s, total = %s WHERE id = %s",
                        (nuevo_cliente.strip(), nuevo_detalle.strip(), nuevo_precio, nuevo_total, int(id_editar))
                    )
                    mostrar_feedback("exito", f"Pedido {id_editar} actualizado correctamente.")
            
            st.divider()
            id_eliminar_estado = st.selectbox("Selecciona pedido a eliminar en este estado:", df_est["id"], key="del_estado")
            if st.button("🗑️ Eliminar pedido de este estado"):
                safe_query("DELETE FROM pedidos WHERE id = %s", (int(id_eliminar_estado),))
                mostrar_feedback("advertencia", f"Pedido {id_eliminar_estado} eliminado.")
