import streamlit as st
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor

def mask(s, keep=3):
    if not s:
        return ""
    try:
        return s[:keep] + "..." + s[-keep:]
    except Exception:
        return "*****"

dsn = st.secrets.get("DATABASE_URL")
if not dsn:
    st.error("DATABASE_URL no encontrada en st.secrets")
else:
    p = urlparse(dsn)
    st.write("host:", p.hostname)
    st.write("port:", p.port)
    st.write("user:", mask(p.username))
    st.write("dbname:", p.path.lstrip('/'))
    try:
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        st.success("Conexión OK")
        cur.close()
        conn.close()
    except Exception as e:
        st.error("Error al conectar (ver excepción completa en logs):")
        st.exception(e)
        raise
