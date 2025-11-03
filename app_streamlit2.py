import streamlit as st
import pandas as pd
from datetime import date
import os
import time

# Importa la lógica y constantes del módulo vecino
from routing_logic2 import COORDENADAS_LOTES, solve_route_optimization, VEHICLES, COORDENADAS_ORIGEN 

# =============================================================================
# CONFIGURACIÓN INICIAL Y ESTILO
# =============================================================================

# Título de la pestaña del navegador y layout
st.set_page_config(page_title="Optimizador Bimodal de Rutas", layout="wide")

# Ocultar menú de Streamlit y footer
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------------------
# ✅ FUNCIONES: PERSISTENCIA EN CSV (GitHub)
# -------------------------------------------------------------------------

# Define el nombre del archivo de historial
HISTORIAL_FILE = 'historial_rutas.csv'

def load_historial_from_csv():
    """Carga el historial desde el archivo CSV o inicializa un DataFrame vacío."""
    if os.path.exists(HISTORIAL_FILE):
        try:
            # Lee el CSV. Usamos 'ast' para convertir las listas guardadas como strings de vuelta a listas
            df = pd.read_csv(HISTORIAL_FILE, converters={'lotes_a': eval, 'lotes_b': eval})
            return df.to_dict('records')
        except Exception as e:
            st.warning(f"Advertencia: No se pudo leer el historial. Se inicia vacío. Error: {e}")
            pass
    
    # Define la estructura de las columnas si el archivo no existe o falla la lectura
    return []

def save_new_route_to_csv(new_route_data):
    """Guarda un nuevo registro de ruta en el archivo CSV."""
    
    # Carga el historial actual
    df_actual = pd.DataFrame(st.session_state.historial_rutas)
    
    # Agrega la nueva ruta (new_route_data es un diccionario)
    df_new_row = pd.DataFrame([new_route_data])
    df_combined = pd.concat([df_actual, df_new_row], ignore_index=True)
    
    # Guarda en el archivo CSV
    # Nota: Los campos que son listas (lotes_a, lotes_b) se guardarán como strings,
    # que es lo que manejamos al cargarlo con 'converters'
    df_combined.to_csv(HISTORIAL_FILE, index=False)

# -------------------------------------------------------------------------
# INICIALIZACIÓN
# -------------------------------------------------------------------------

# Inicializar el estado de la sesión para guardar el historial PERMANENTE
if 'historial_cargado' not in st.session_state:
    st.session_state.historial_rutas = load_historial_from_csv()
    st.session_state.historial_cargado = True 

# Inicializar la clave 'results'
if 'results' not in st.session_state:
    st.session_state.results = None 

# =============================================================================
# ESTRUCTURA DEL MENÚ LATERAL
# =============================================================================

st.sidebar.title("Menú Principal")
page = st.sidebar.radio(
    "Seleccione una opción:",
    ["Calcular Nueva Ruta", "Historial", "Estadísticas"]
)
st.sidebar.divider()
st.sidebar.info(f"Rutas Guardadas: {len(st.session_state.historial_rutas)}")

# =============================================================================
# 1. PÁGINA: CALCULAR NUEVA RUTA
# =============================================================================

if page == "Calcular Nueva Ruta":
    st.title("🚚 Optimizator")
    st.caption("Planificación y división óptima de lotes para vehículos de entrega.")

    # --- ENTRADA Y VALIDACIÓN ---
    st.header("Selección de Destinos")
    
    lotes_input = st.text_input(
        "Ingrese los lotes a visitar (separados por coma, ej: A05, B10, C95):",
        placeholder="A05, A10, B05, B10, C95, D01, K01"
    )
    
    col_map, col_details = st.columns([2, 1])

    all_stops_to_visit = [l.strip().upper() for l in lotes_input.split(',') if l.strip()]
    num_lotes = len(all_stops_to_visit)

    # Lógica de pre-visualización y mapa...
    map_data_list = []
    map_data_list.append({'name': 'INGENIO (Origen)', 'lat': COORDENADAS_ORIGEN[1], 'lon': COORDENADAS_ORIGEN[0]})
    
    valid_stops_count = 0
    invalid_stops = [l for l in all_stops_to_visit if l not in COORDENADAS_LOTES]

    for lote in all_stops_to_visit:
        if lote in COORDENADAS_LOTES:
            lon, lat = COORDENADAS_LOTES[lote]
            map_data_list.append({'name': lote, 'lat': lat, 'lon': lon})
            valid_stops_count += 1
    
    map_data = pd.DataFrame(map_data_list)
    
    with col_map:
        if valid_stops_count > 0:
            st.subheader(f"Mapa de {valid_stops_count} Destinos")
            st.map(map_data, latitude='lat', longitude='lon', color='#0044FF', size=10, zoom=10)
        else:
            st.info("Ingrese lotes válidos para ver la previsualización del mapa.")

    with col_details:
        st.subheader("Estado de la Selección")
        st.metric("Total Lotes Ingresados", num_lotes)
        
        if invalid_stops:
            st.error(f"❌ {len(invalid_stops)} Lotes Inválidos: {', '.join(invalid_stops)}.")
        
        MIN_LOTES = 3
        MAX_LOTES = 7
        
        if valid_stops_count < MIN_LOTES or valid_stops_count > MAX_LOTES:
            st.warning(f"⚠️ Debe ingresar entre {MIN_LOTES} y {MAX_LOTES} lotes válidos. Ingresó {valid_stops_count}.")
            calculate_disabled = True
        elif valid_stops_count > 0:
            calculate_disabled = False
        else:
            calculate_disabled = True

    # -------------------------------------------------------------------------
    # 🛑 BOTÓN DE CÁLCULO Y LÓGICA (Guarda en CSV)
    # -------------------------------------------------------------------------
    st.divider()
    
    if st.button("🚀 Calcular Rutas Óptimas", key="calc_btn_main", type="primary", disabled=calculate_disabled):
        
        if 'results' not in st.session_state:
            st.session_state.results = None

        with st.spinner('Realizando cálculo óptimo y agrupando rutas (¡75s de espera incluidos!)...'):
            try:
                results = solve_route_optimization(all_stops_to_visit) 
                
                if "error" in results:
                    st.session_state.results = None
                    st.error(f"❌ Error en la API de Ruteo: {results['error']}")
                else:
                    # ✅ CREA LA ESTRUCTURA DEL REGISTRO
                    new_route = {
                        "fecha": date.today().strftime("%Y-%m-%d"),
                        "lotes_ingresados": ", ".join(all_stops_to_visit),
                        "lotes_a": results['ruta_a']['lotes_asignados'],
                        "lotes_b": results['ruta_b']['lotes_asignados'],
                        "km_a": results['ruta_a']['distancia_km'],
                        "km_b": results['ruta_b']['distancia_km'],
                        "tiempo_a": results['ruta_a']['tiempo_estimado'],
                        "tiempo_b": results['ruta_b']['tiempo_estimado'],
                    }
                    
                    # 🚀 GUARDA PERMANENTEMENTE EN CSV
                    save_new_route_to_csv(new_route)
                    
                    # ACTUALIZA EL ESTADO DE LA SESIÓN
                    st.session_state.historial_rutas.append(new_route)
                    
                    st.session_state.results = results
                    st.success("✅ Cálculo finalizado y rutas optimizadas.")
                    
            except Exception as e:
                st.session_state.results = None
                st.error(f"❌ Ocurrió un error inesperado durante el ruteo: {e}")
                
    # -------------------------------------------------------------------------
    # 2. REPORTE DE RESULTADOS UNIFICADO
    # -------------------------------------------------------------------------
    
    if st.session_state.results:
        results = st.session_state.results
        
        st.divider()
        st.header("Análisis de Rutas Generadas")
        st.metric("Distancia Interna de Agrupación (Minimización)", f"{results['agrupacion_distancia_km']} km")
        st.divider()

        res_a = results.get('ruta_a', {})
        res_b = results.get('ruta_b', {})

        col_a, col_b = st.columns(2)
        
        with col_a:
            st.subheader(f"🚛 Camión 1: {res_a.get('patente', 'N/A')}")
            with st.container(border=True):
                st.markdown(f"**Total Lotes:** {len(res_a.get('lotes_asignados', []))}")
                st.markdown(f"**Distancia Total (TSP):** **{res_a.get('distancia_km', 'N/A')} km**")
                st.markdown(f"**Tiempo Estimado:** **{res_a.get('tiempo_estimado', 'N/A')}**")
                st.markdown(f"**Lotes Asignados:** `{' → '.join(res_a.get('lotes_asignados', []))}`")
                st.info(f"**Orden Óptimo:** Ingenio → {' → '.join(res_a.get('orden_optimo', []))} → Ingenio")
                st.link_button("🌐 Ver Ruta A en GeoJSON.io", res_a.get('geojson_link', '#'))
            
        with col_b:
            st.subheader(f"🚚 Camión 2: {res_b.get('patente', 'N/A')}")
            with st.container(border=True):
                st.markdown(f"**Total Lotes:** {len(res_b.get('lotes_asignados', []))}")
                st.markdown(f"**Distancia Total (TSP):** **{res_b.get('distancia_km', 'N/A')} km**")
                st.markdown(f"**Tiempo Estimado:** **{res_b.get('tiempo_estimado', 'N/A')}**")
                st.markdown(f"**Lotes Asignados:** `{' → '.join(res_b.get('lotes_asignados', []))}`")
                st.info(f"**Orden Óptimo:** Ingenio → {' → '.join(res_b.get('orden_optimo', []))} → Ingenio")
                st.link_button("🌐 Ver Ruta B en GeoJSON.io", res_b.get('geojson_link', '#'))

    else:
        st.info("El reporte aparecerá aquí después de un cálculo exitoso.")


# =============================================================================
# 2. PÁGINA: HISTORIAL
# =============================================================================

elif page == "Historial":
    st.header("📋 Historial de Rutas Calculadas")
    
    if st.session_state.historial_rutas:
        df_historial = pd.DataFrame(st.session_state.historial_rutas)
        st.subheader(f"Total de {len(df_historial)} Rutas Guardadas")
        
        # Eliminar las columnas de listas/strings para una visualización más limpia
        df_display = df_historial.drop(columns=['lotes_ingresados'], errors='ignore')

        st.dataframe(df_display, 
                     use_container_width=True,
                     column_order=("fecha", "km_a", "tiempo_a", "km_b", "tiempo_b", "lotes_a", "lotes_b"),
                     column_config={
                         "km_a": st.column_config.NumberColumn("KM A", format="%.2f km"),
                         "km_b": st.column_config.NumberColumn("KM B", format="%.2f km"),
                         "tiempo_a": "Tiempo A",
                         "tiempo_b": "Tiempo B",
                         "lotes_a": "Lotes Camión A",
                         "lotes_b": "Lotes Camión B",
                         "fecha": "Fecha"
                     })
        
        st.divider()
        st.warning("El botón a continuación borrará el historial de la sesión y el archivo CSV permanente.")
        if st.button("🗑️ Borrar Historial PERMANENTE"):
            # Vacia el estado de la sesión
            st.session_state.historial_rutas = []
            # Elimina el archivo CSV
            if os.path.exists(HISTORIAL_FILE):
                os.remove(HISTORIAL_FILE)
            st.rerun()
            

    else:
        st.info("Aún no hay rutas guardadas en el historial. Realice un cálculo en la página principal.")

# =============================================================================
# 3. PÁGINA: ESTADÍSTICAS
# =============================================================================

elif page == "Estadísticas":
    st.header("📈 Estadísticas de Kilometraje y Tiempo")
    
    if st.session_state.historial_rutas:
        df = pd.DataFrame(st.session_state.historial_rutas)
        df['fecha'] = pd.to_datetime(df['fecha'])

        # CÁLCULOS
        df_diario = df.groupby(df['fecha'].dt.date)[['km_a', 'km_b']].sum().reset_index()
        df_diario.columns = ['Fecha', 'KM Camión A', 'KM Camión B']
        
        df['mes_año'] = df['fecha'].dt.to_period('M')
        df_mensual = df.groupby('mes_año')[['km_a', 'km_b']].sum().reset_index()
        df_mensual['Mes'] = df_mensual['mes_año'].astype(str)
        
        df_mensual_final = df_mensual[['Mes', 'km_a', 'km_b']].rename(columns={'km_a': 'KM Camión A', 'km_b': 'KM Camión B'})


        st.subheader("Kilómetros Recorridos por Día")
        st.dataframe(df_diario, use_container_width=True)
        st.bar_chart(df_diario.set_index('Fecha'))

        st.subheader("Kilómetros Mensuales Acumulados")
        st.dataframe(df_mensual_final, use_container_width=True)
        st.bar_chart(df_mensual_final.set_index('Mes'))

    else:
        st.info("No hay datos en el historial para generar estadísticas.")








