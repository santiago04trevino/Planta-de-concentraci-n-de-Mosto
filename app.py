import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import os
import google.generativeai as genai

# ==========================================
# 0. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Simulador BioSTEAM - Separación de Etanol", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚙️ Simulación Interactiva: Separación de Etanol")
st.markdown("Plataforma web para el análisis termodinámico y balances de materia y energía mediante BioSTEAM.")

# ==========================================
# 1. SIDEBAR: PARÁMETROS DE ENTRADA
# ==========================================
st.sidebar.header("Parámetros de Operación")
st.sidebar.markdown("Ajusta las condiciones de alimentación al sistema:")

flujo_agua = st.sidebar.slider("Flujo de Agua (kmol/h)", 10.0, 100.0, 43.2, step=0.1)
flujo_etanol = st.sidebar.slider("Flujo de Etanol (kmol/h)", 1.0, 20.0, 4.9, step=0.1)
# Temperatura base corregida para cálculos de transferencia de masa (293 K)
temp_mosto = st.sidebar.slider("Temperatura del Mosto (K)", 280.0, 320.0, 293.0, step=1.0)

# ==========================================
# 2. MOTOR DE SIMULACIÓN
# ==========================================
def ejecutar_simulacion(f_agua, f_etanol, t_mosto):
    # Limpiar el flowsheet para evitar colisiones de IDs en ejecuciones continuas
    bst.main_flowsheet.clear()
    
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # Corrientes
    mosto = bst.Stream("1-MOSTO", Water=f_agua, Ethanol=f_etanol, units="kmol/h", T=t_mosto, P=101325)
    vinazas_retorno = bst.Stream("Vinazas-Retorno", Water=43.335, Ethanol=0, units="kmol/h", T=90+273.15, P=300000)

    # Equipos de proceso
    P100 = bst.Pump("P-100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W-210", ins=(P100-0, vinazas_retorno), outs=("3-MOSTO-PRE","DRENAJE"), phase0="l", phase1="l")
    W210.outs[0].T = 85+273.15
    W220 = bst.HXutility("W-220", ins=W210-0, outs="Mezcla", T=95+273.15)
    V100 = bst.IsenthalpicValve("V-100", ins=W220-0, outs="Mezcla-Bifásica", P=101325)
    
    # Separador flash (adiabático)
    V1 = bst.Flash("V-1", ins=V100-0, outs=("Vapor Caliente","Vinazas"), P=101325, Q=0)
    # Condensador (enfriamiento a 293 K)
    W310 = bst.HXutility("W-310", ins=V1-0, outs="Producto Final", T=293.0)
    P200 = bst.Pump("P-200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    # Ejecución del sistema
    eth_sys = bst.System("planta_etanol", path=(P100,W210,W220,V100,V1,W310,P200))
    eth_sys.simulate()

    # Procesamiento de Datos de Materia
    datos_mat = []
    pureza_etanol_producto = 0.0
    for s in eth_sys.streams:
        if s.F_mass > 0:
            porcentaje_etanol = (s.imass['Ethanol']/s.F_mass)*100
            if s.ID == "Producto Final":
                pureza_etanol_producto = porcentaje_etanol
                
            datos_mat.append({
                "ID Corriente": s.ID,
                "Temp (°C)": f"{s.T-273.15:.2f}",
                "Presión (bar)": f"{s.P/1e5:.2f}",
                "Flujo (kg/h)": f"{s.F_mass:.2f}",
                "% Etanol": f"{porcentaje_etanol:.1f}%",
                "% Agua": f"{(s.imass['Water']/s.F_mass)*100:.1f}%"
            })
    
    # Procesamiento de Datos de Energía
    datos_en = []
    consumo_calentamiento_total = 0.0
    consumo_enfriamiento_total = 0.0
    
    for u in eth_sys.units:
        calor_kw = 0.0
        tipo_servicio = "-"
        
        if isinstance(u, bst.HXprocess):
            calor_kw = (u.outs[0].H - u.ins[0].H) / 3600
            tipo_servicio = "Recuperación Interna"
        elif isinstance(u, bst.Flash):
            calor_kw = 0.0
            tipo_servicio = "Adiabático"
        elif hasattr(u, "duty") and u.duty is not None:
            calor_kw = u.duty / 3600
            if calor_kw > 0.01: 
                tipo_servicio = "Calentamiento (Vapor)"
                consumo_calentamiento_total += calor_kw
            if calor_kw < -0.01: 
                tipo_servicio = "Enfriamiento (Agua)"
                consumo_enfriamiento_total += calor_kw

        potencia = u.power_utility.rate if (hasattr(u, "power_utility") and u.power_utility) else 0.0

        if abs(calor_kw) > 0.01:
            datos_en.append({"ID Equipo": u.ID, "Función": tipo_servicio, "Energía Térmica (kW)": f"{calor_kw:.2f}"})
        if potencia > 0.01:
            datos_en.append({"ID Equipo": u.ID, "Función": "Motor bomba", "Energía Eléctrica (kW)": f"{potencia:.2f}"})

    df_mat = pd.DataFrame(datos_mat)
    df_en = pd.DataFrame(datos_en)

    # Generación de Diagrama de Flujo (PFD)
    diagram_path = "diagrama_etanol"
    try:
        eth_sys.diagram(file=diagram_path, format="png")
        diagrama_generado = diagram_path + ".png"
    except Exception:
        diagrama_generado = None

    # Agrupamos métricas clave para retornar
    metricas = {
        "pureza_producto": pureza_etanol_producto,
        "calentamiento_kw": consumo_calentamiento_total,
        "enfriamiento_kw": abs(consumo_enfriamiento_total)
    }

    return df_mat, df_en, diagrama_generado, metricas

# ==========================================
# 3. INTERFAZ DE USUARIO (UI)
# ==========================================
if st.sidebar.button("▶ Ejecutar Simulación", type="primary", use_container_width=True):
    with st.spinner("Resolviendo balances de materia y energía..."):
        df_materia, df_energia, ruta_diagrama, kpis = ejecutar_simulacion(flujo_agua, flujo_etanol, temp_mosto)
        
        st.divider()
        
        # --- SECCIÓN DE MÉTRICAS CLAVE ---
        st.subheader("📊 Indicadores Clave de Rendimiento (KPIs)")
        m1, m2, m3 = st.columns(3)
        m1.metric("Pureza del Etanol (Producto Final)", f"{kpis['pureza_producto']:.1f} %")
        m2.metric("Consumo de Calentamiento Total", f"{kpis['calentamiento_kw']:.2f} kW")
        m3.metric("Requerimiento de Enfriamiento", f"{kpis['enfriamiento_kw']:.2f} kW")
        
        st.write("") # Espaciador
        
        # --- SECCIÓN DE TABLAS EN COLUMNAS ---
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            st.markdown("### 💧 Balance de Materia")
            st.dataframe(df_materia, use_container_width=True, hide_index=True)
            
        with col2:
            st.markdown("### ⚡ Balance de Energía")
            st.dataframe(df_energia, use_container_width=True, hide_index=True)
            
        st.divider()
        
        # --- DIAGRAMA DEL PROCESO ---
        if ruta_diagrama and os.path.exists(ruta_diagrama):
            st.subheader("🗺️ Diagrama de Flujo del Proceso (PFD)")
            st.image(ruta_diagrama, use_column_width=True)
        
        st.divider()
        
        # --- INTEGRACIÓN CON IA (GEMINI TUTOR) ---
        st.subheader("🧠 Análisis Asistido por IA")
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            modelo = genai.GenerativeModel("gemini-2.5-pro")
            
            prompt = f"""
            Actúa como un ingeniero químico senior evaluando el reporte técnico de una simulación de separación de etanol.
            
            Tabla de Materia:
            {df_materia.to_markdown(index=False)}
            
            Tabla de Energía:
            {df_energia.to_markdown(index=False)}
            
            Proporciona un reporte de 3 párrafos concisos:
            1. Evalúa la viabilidad técnica del proceso.
            2. Señala el equipo con mayor consumo energético y su impacto.
            3. Proporciona una sugerencia técnica directa para optimización termodinámica.
            """
            respuesta = modelo.generate_content(prompt)
            st.success(respuesta.text)
            # ... (código anterior del try) ...
        except Exception as e:
            st.error("Fallo en la ejecución de la API de Gemini. Detalles del servidor:")
            st.code(str(e)) # Esto imprimirá el error técnico exacto
            st.info("Revisa el mensaje de arriba para diagnosticar el problema.")
        except Exception as e:
            st.warning("⚠️ La conexión con la API de Gemini no está configurada correctamente en los Secrets.")
