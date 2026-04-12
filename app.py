import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import os
import base64
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
st.markdown("Plataforma web para el análisis termodinámico, balances y evaluación económica del proceso.")

# ==========================================
# 1. SIDEBAR: PARÁMETROS OPERATIVOS Y COSTOS
# ==========================================
st.sidebar.header("1. Parámetros de Operación")
flujo_agua = st.sidebar.slider("Flujo de Agua en Mosto (kmol/h)", 10.0, 100.0, 43.2, step=0.1)
flujo_etanol = st.sidebar.slider("Flujo de Etanol en Mosto (kmol/h)", 1.0, 20.0, 4.9, step=0.1)

# Temperaturas en °C
temp_mosto_c = st.sidebar.slider("Temp. Alimentación Mosto (°C)", 5.0, 50.0, 20.0, step=1.0)
temp_w220_c = st.sidebar.slider("Temp. Salida W-220 (°C)", 70.0, 110.0, 95.0, step=1.0)

# Presión en bar
presion_v100_bar = st.sidebar.slider("Presión Separador V-100 (bar)", 0.5, 5.0, 1.0, step=0.1)

st.sidebar.divider()
st.sidebar.header("2. Precios y Utilidades (USD)")
precio_mosto = st.sidebar.slider("Precio Mosto ($/ton)", 10.0, 100.0, 30.0)
precio_etanol = st.sidebar.slider("Precio Etanol ($/ton)", 500.0, 2000.0, 900.0)
precio_luz = st.sidebar.slider("Precio Luz ($/kWh)", 0.05, 0.50, 0.12)
precio_vapor = st.sidebar.slider("Precio Vapor ($/ton)", 10.0, 50.0, 20.0)
precio_agua = st.sidebar.slider("Precio Agua Enfriamiento ($/ton)", 0.1, 5.0, 0.5)

# ==========================================
# 2. FUNCIONES AUXILIARES (PDF VIEWER)
# ==========================================
def mostrar_pdf(ruta_archivo):
    """Función auxiliar para leer y renderizar un PDF en Streamlit mediante base64 y etiqueta embed"""
    try:
        with open(ruta_archivo, "rb") as f:
            pdf_data = f.read()
            base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
        
        # 1. Intentar renderizar con <embed> en lugar de <iframe> para evitar el bloqueo de Chrome
        pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf">'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        # 2. Respaldo de seguridad: Botón de descarga nativo
        st.download_button(
            label="⬇️ Descargar PDF si no se visualiza correctamente",
            data=pdf_data,
            file_name=ruta_archivo,
            mime="application/pdf"
        )
        
    except FileNotFoundError:
        st.warning(f"⚠️ No se encontró el archivo: `{ruta_archivo}`. Verifica que esté en el repositorio.")

# ==========================================
# 3. MOTOR DE SIMULACIÓN Y ECONOMÍA
# ==========================================
def ejecutar_simulacion(f_agua, f_etanol, t_mosto_c, t_w220_c, p_v100_bar):
    bst.main_flowsheet.clear()
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # Corrientes (Conversión de °C a K, y bar a Pa)
    mosto = bst.Stream("1-MOSTO", Water=f_agua, Ethanol=f_etanol, units="kmol/h", T=t_mosto_c+273.15, P=101325)
    vinazas_retorno = bst.Stream("Vinazas-Retorno", Water=43.335, Ethanol=0, units="kmol/h", T=90+273.15, P=300000)

    # Equipos
    P100 = bst.Pump("P-100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W-210", ins=(P100-0, vinazas_retorno), outs=("3-MOSTO-PRE","DRENAJE"), phase0="l", phase1="l")
    W210.outs[0].T = 85+273.15
    W220 = bst.HXutility("W-220", ins=W210-0, outs="Mezcla", T=t_w220_c+273.15)
    V100 = bst.IsenthalpicValve("V-100", ins=W220-0, outs="Mezcla-Bifásica", P=p_v100_bar*100000)
    
    V1 = bst.Flash("V-1", ins=V100-0, outs=("Vapor Caliente","Vinazas"), P=p_v100_bar*100000, Q=0)
    W310 = bst.HXutility("W-310", ins=V1-0, outs="Producto Final", T=293.0)
    P200 = bst.Pump("P-200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    eth_sys = bst.System("planta_etanol", path=(P100,W210,W220,V100,V1,W310,P200))
    eth_sys.simulate()

    # Procesamiento Materia
    datos_mat = []
    prod_data = {}
    for s in eth_sys.streams:
        if s.F_mass > 0:
            pct_etanol = (s.imass['Ethanol']/s.F_mass)*100
            if s.ID == "Producto Final":
                prod_data = {
                    "P": s.P / 100000, # bar
                    "T": s.T - 273.15, # °C
                    "Flujo": s.F_mass, # kg/h
                    "Comp": pct_etanol # %
                }
            datos_mat.append({
                "ID Corriente": s.ID, "Temp (°C)": f"{s.T-273.15:.2f}",
                "Presión (bar)": f"{s.P/100000:.2f}", "Flujo (kg/h)": f"{s.F_mass:.2f}",
                "% Etanol": f"{pct_etanol:.1f}%", "% Agua": f"{(s.imass['Water']/s.F_mass)*100:.1f}%"
            })
    
    # Procesamiento Energía y Utilidades
    datos_en = []
    calor_kw = enfriamiento_kw = potencia_kw = 0.0
    
    for u in eth_sys.units:
        q_kw = (u.duty / 3600) if (hasattr(u, "duty") and u.duty) else 0.0
        p_kw = u.power_utility.rate if (hasattr(u, "power_utility") and u.power_utility) else 0.0
        
        tipo_srv = "-"
        if isinstance(u, bst.HXprocess): tipo_srv = "Recuperación"
        elif isinstance(u, bst.Flash): tipo_srv = "Adiabático"
        elif q_kw > 0.01: 
            tipo_srv = "Vapor"
            calor_kw += q_kw
        elif q_kw < -0.01: 
            tipo_srv = "Agua Enfriamiento"
            enfriamiento_kw += abs(q_kw)
            
        potencia_kw += p_kw

        if abs(q_kw) > 0.01: datos_en.append({"ID Equipo": u.ID, "Función": tipo_srv, "Energía Térmica (kW)": f"{q_kw:.2f}"})
        if p_kw > 0.01: datos_en.append({"ID Equipo": u.ID, "Función": "Motor Eléctrico", "Energía Eléctrica (kW)": f"{p_kw:.2f}"})

    # --- EVALUACIÓN ECONÓMICA BÁSICA (Clase V) ---
    horas_año = 8000
    ton_to_kg = 1000
    
    # OPEX Anual (Materia prima + Servicios)
    costo_mosto_anual = (mosto.F_mass / ton_to_kg) * precio_mosto * horas_año
    costo_vapor_anual = (calor_kw * 3600 / 2257 / ton_to_kg) * precio_vapor * horas_año # Asumiendo dHvap = 2257 kJ/kg
    costo_agua_anual = (enfriamiento_kw * 3600 / 41.8 / ton_to_kg) * precio_agua * horas_año # Asumiendo dT = 10C
    costo_luz_anual = potencia_kw * precio_luz * horas_año
    opex_total = costo_mosto_anual + costo_vapor_anual + costo_agua_anual + costo_luz_anual
    
    costo_real_produccion = opex_total / (prod_data["Flujo"] * horas_año / ton_to_kg) if prod_data["Flujo"] > 0 else 0
    
    # Ingresos y Métricas Financieras
    ingresos = (prod_data["Flujo"] / ton_to_kg) * precio_etanol * horas_año
    flujo_caja = ingresos - opex_total
    
    # Asumimos un CAPEX estimado fijo de $1,500,000 USD para el cálculo de viabilidad
    capex_estimado = 1500000 
    roi = (flujo_caja / capex_estimado) * 100 if capex_estimado > 0 else 0
    payback = capex_estimado / flujo_caja if flujo_caja > 0 else 0
    
    # NPV a 10 años con tasa de descuento del 10%
    tasa = 0.10
    npv = -capex_estimado + sum([flujo_caja / ((1 + tasa)**t) for t in range(1, 11)])

    kpis = {
        "prod": prod_data,
        "costo_prod": costo_real_produccion,
        "precio_venta": precio_etanol,
        "npv": npv,
        "payback": payback,
        "roi": roi
    }

    return pd.DataFrame(datos_mat), pd.DataFrame(datos_en), kpis

# ==========================================
# 4. INTERFAZ Y RENDERIZADO
# ==========================================
if st.sidebar.button("▶ Ejecutar Simulación", type="primary", use_container_width=True):
    st.session_state['simulacion_ejecutada'] = True
    df_materia, df_energia, kpis = ejecutar_simulacion(
        flujo_agua, flujo_etanol, temp_mosto_c, temp_w220_c, presion_v100_bar
    )
    st.session_state['df_mat'] = df_materia
    st.session_state['df_en'] = df_energia
    st.session_state['kpis'] = kpis

if st.session_state.get('simulacion_ejecutada'):
    kpis = st.session_state['kpis']
    
    # --- SECCIÓN A: MÉTRICAS DEL PRODUCTO FINAL ---
    st.subheader("📦 Propiedades del Producto Final")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Presión", f"{kpis['prod'].get('P', 0):.2f} bar")
    c2.metric("Temperatura", f"{kpis['prod'].get('T', 0):.2f} °C")
    c3.metric("Flujo Másico", f"{kpis['prod'].get('Flujo', 0):.1f} kg/h")
    c4.metric("Composición Etanol", f"{kpis['prod'].get('Comp', 0):.1f} %")

    # --- SECCIÓN B: EVALUACIÓN ECONÓMICA ---
    st.subheader("💰 Evaluación Financiera (Base Anual)")
    e1, e2, e3, e4, e5 = st.columns(5)
    e1.metric("Costo Real Prod.", f"$ {kpis['costo_prod']:.2f} /ton")
    e2.metric("Precio Venta Sug.", f"$ {kpis['precio_venta']:.2f} /ton")
    e3.metric("NPV (10 años)", f"$ {kpis['npv']:,.0f}")
    e4.metric("Payback", f"{kpis['payback']:.1f} años" if kpis['payback']>0 else "No viable")
    e5.metric("ROI", f"{kpis['roi']:.1f} %")

    st.divider()

    # --- SECCIÓN C: TABLAS DE BALANCE ---
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("### 💧 Balance de Materia")
        st.dataframe(st.session_state['df_mat'], use_container_width=True, hide_index=True)
    with col2:
        st.markdown("### ⚡ Balance de Energía")
        st.dataframe(st.session_state['df_en'], use_container_width=True, hide_index=True)
        
    st.divider()

    # --- SECCIÓN D: VISUALIZACIÓN DE PLANOS ISO ---
    st.subheader("📐 Diagramas de Ingeniería (Estándar ISO)")
    t1, t2 = st.tabs(["Diagrama de Bloques (BFD)", "Diagrama de Flujo de Proceso (PFD)"])
    
    with t1:
        st.info("Renderizando BFD desde AutoCAD Plant 3D")
        mostrar_pdf("diagrama_bfd.pdf")
        
    with t2:
        st.info("Renderizando PFD desde AutoCAD Plant 3D")
        mostrar_pdf("diagrama_pfd.pdf")

    st.divider()

    # --- SECCIÓN E: TUTOR IA (GEMINI 2.5 PRO) ---
    st.subheader("🧠 Tutor de Ingeniería Asistido por IA")
    modo_tutor = st.toggle("Habilitar Modo Tutor IA", value=False)
    
    if modo_tutor:
        st.markdown("Chatea con el asistente técnico sobre los resultados termodinámicos y financieros de tu simulación.")
        
        # Inicializar historial de chat
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Mostrar historial
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Input natural del usuario
        if prompt_usuario := st.chat_input("Ej: ¿Por qué el ROI es tan bajo si aumento la presión en V-100?"):
            st.session_state.messages.append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"):
                st.markdown(prompt_usuario)

            # Contexto del sistema inyectado en la API
            contexto_simulacion = f"""
            Actúa como un tutor de ingeniería química senior. El alumno está simulando una planta de separación de etanol.
            Datos actuales de la simulación:
            - Temperatura W-220: {temp_w220_c} °C
            - Presión V-100: {presion_v100_bar} bar
            - Pureza del producto: {kpis['prod'].get('Comp', 0):.1f} %
            - NPV: ${kpis['npv']:,.2f} USD
            - ROI: {kpis['roi']:.1f} %
            Pregunta del alumno: {prompt_usuario}
            Responde de manera directa, técnica y basándote en la termodinámica o ingeniería de costos.
            """

            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                modelo = genai.GenerativeModel("gemini-2.5-pro")
                
                with st.chat_message("assistant"):
                    with st.spinner("Analizando balances..."):
                        respuesta = modelo.generate_content(contexto_simulacion)
                        st.markdown(respuesta.text)
                
                st.session_state.messages.append({"role": "assistant", "content": respuesta.text})
                
            except Exception as e:
                st.error("Fallo de conexión con Gemini.")
                st.code(str(e))
