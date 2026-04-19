import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import os
import base64
import math
import google.generativeai as genai
import fitz  # PyMuPDF: Necesario para renderizar PDFs evadiendo el bloqueo del navegador

# ==========================================
# 0. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Simulador BioSTEAM - Separación de Etanol", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 0.1 INYECCIÓN DE CSS PARA EL DISEÑO DE LA IMAGEN
# ==========================================
# Aquí está todo el diseño solicitado sobre el fondo oscuro.
st.markdown("""
    <style>
    /* 1. ANIMACIÓN DE ENTRADA Y FUENTES GLOABLES */
    @keyframes fadeIn {
        0% { opacity: 0; transform: translateY(20px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    .main .block-container {
        animation: fadeIn 0.8s ease-out;
    }

    /* 2. ESTILO DEL TÍTULO PRINCIPAL Y SUBTÍTULO CON GRADIENTE AZUL-VERDE */
    .title-text {
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 0px;
        padding-bottom: 0px;
        color: white; /* Color de base blanco */
    }
    .title-text span {
        background: linear-gradient(90deg, #00b49c, #86e819); /* Gradiente cian a lima */
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .subtitle-text {
        color: #cbd5e1; /* Gris suave */
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }

    /* 3. ESTILO DE LAS TARJETAS DE MÉTRICAS (Efecto SaaS de Image 1) */
    div[data-testid="stMetric"] {
        background-color: #0a2a41; /* Slightly lighter navy para tarjetas */
        border: 1px solid #1f2937;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: all 0.3s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border-color: #00b49c; /* Borde cian al pasar el cursor */
        box-shadow: 0 10px 15px -3px rgba(0, 180, 156, 0.2); /* Brillo cian */
    }

    /* Etiquetas de las métricas */
    div[data-testid="stMetricLabel"] > div > div > p {
        color: #cbd5e1; /* Soft gray-blue para etiquetas */
        font-weight: 600;
        font-size: 1.1rem;
    }

    /* Valores principales de las métricas */
    div[data-testid="stMetricValue"] > div {
        color: #ffffff; /* Valor métrico blanco */
        font-weight: 700;
    }

    /* 4. ESTILO DEL BOTÓN PRINCIPAL CON GRADIENTE */
    /* Target específico del botón en la sidebar */
    [data-testid="stSidebar"] button[kind="primary"] {
        background: linear-gradient(90deg, #00b49c, #86e819);
        color: #ffffff;
        border: none;
        font-weight: 700;
        use_container_width: True;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        opacity: 0.9;
        transform: scale(1.02);
    }

    /* 5. ESTILO GENERAL DE SUBENCABEZADOS (H2, H3) CON GRADIENTE */
    /* Clases para subheaders en markdown */
    .section-header {
        background: linear-gradient(90deg, #00b49c, #86e819);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
    }

    /* 6. ESTILO DE LOS SLIDERS NATIVOS (Sincronizado con primaryColor) */
    /* Streamlit lo maneja con primaryColor en config.toml, pero para asegurar: */
    div[data-baseweb="slider"] > div > div > div:nth-child(1) {
        background: linear-gradient(90deg, #00b49c, #86e819) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Reemplazo de títulos y subheaders por markdown con clases CSS para el gradiente
st.markdown('<h1 class="title-text">⚙️ Simulación Interactiva: <span>Separación de Etanol</span></h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle-text">Plataforma web para el análisis termodinámico, balances y evaluación económica del proceso.</p>', unsafe_allow_html=True)

# ==========================================
# 1. SIDEBAR: PARÁMETROS OPERATIVOS Y COSTOS
# ==========================================
# Usamos Markdown para subheaders en sidebar también
st.sidebar.markdown('<h3 class="section-header">⚙️ Ejecución</h3>', unsafe_allow_html=True)
ejecutar_btn = st.sidebar.button("▶ Ejecutar Simulación", type="primary", use_container_width=True)
st.sidebar.divider()

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
    """Función auxiliar para rasterizar un PDF a imagen usando PyMuPDF y asegurar su visualización"""
    try:
        if os.path.exists(ruta_archivo):
            # Abrir el documento PDF
            doc = fitz.open(ruta_archivo)
            
            # Renderizar cada página del PDF como una imagen
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Matriz para aplicar zoom y mejorar la resolución
                mat = fitz.Matrix(2, 2) 
                pix = page.get_pixmap(matrix=mat)
                
                # Convertir los datos de la imagen a formato apto para Streamlit
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, caption=f"Página {page_num + 1} - Renderizado desde Plant 3D", use_container_width=True)
            
            # Mantener el botón de descarga nativo como contingencia
            with open(ruta_archivo, "rb") as f:
                pdf_data = f.read()
                
            st.download_button(
                label="⬇️ Descargar archivo original en PDF",
                data=pdf_data,
                file_name=ruta_archivo,
                mime="application/pdf",
                key=f"btn_{ruta_archivo}"
            )
        else:
            st.warning(f"⚠️ No se encontró el archivo: `{ruta_archivo}`. Asegúrate de subirlo a la raíz de tu repositorio.")
    except Exception as e:
        st.error(f"❌ Error interno al renderizar el documento: {e}")

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
    
    # Condensador (enfriamiento riguroso a 293 K por requerimiento de transferencia de masa)
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
if ejecutar_btn:
    with st.spinner("Resolviendo balances termodinámicos y financieros..."):
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
    st.markdown('<h3 class="section-header">📦 Propiedades del Producto Final</h3>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Presión", f"{kpis['prod'].get('P', 0):.2f} bar")
    c2.metric("Temperatura", f"{kpis['prod'].get('T', 0):.2f} °C")
    c3.metric("Flujo Másico", f"{kpis['prod'].get('Flujo', 0):.1f} kg/h")
    c4.metric("Composición Etanol", f"{kpis['prod'].get('Comp', 0):.1f} %")

    # --- SECCIÓN B: EVALUACIÓN ECONÓMICA MODIFICADA ---
    # He reordenado el arreglo de las columnas para que los números grandes quepan.
    # En lugar de una fila de 5, usaremos una fila de 3 y otra de 2.
    st.markdown('<h3 class="section-header">💰 Evaluación Financiera (Base Anual)</h3>', unsafe_allow_html=True)
    
    # Fila 1: 3 columnas para métricas de costos y NPV
    e1, e2, e3 = st.columns(3)
    e1.metric("Costo Real Prod.", f"$ {kpis['costo_prod']:.2f} /ton")
    e2.metric("Precio Venta Sug.", f"$ {kpis['precio_venta']:.2f} /ton")
    e3.metric("NPV (10 años)", f"$ {kpis['npv']:,.0f}")
    
    # Fila 2: 2 columnas para métricas de tiempo y retorno
    e4, e5 = st.columns(2)
    e4.metric("Payback", f"{kpis['payback']:.1f} años" if kpis['payback']>0 else "No viable")
    e5.metric("ROI", f"{kpis['roi']:.1f} %")

    st.divider()

    # --- SECCIÓN C: TABLAS DE BALANCE ---
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<h3 class="section-header">💧 Balance de Materia</h3>', unsafe_allow_html=True)
        st.dataframe(st.session_state['df_mat'], use_container_width=True, hide_index=True)
    with col2:
        st.markdown('<h3 class="section-header">⚡ Balance de Energía</h1>', unsafe_allow_html=True)
        st.dataframe(st.session_state['df_en'], use_container_width=True, hide_index=True)
        
    st.divider()

    # --- SECCIÓN D: VISUALIZACIÓN DE PLANOS ISO ---
    st.markdown('<h3 class="section-header">📐 Diagramas de Ingeniería (Estándar ISO)</h3>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["Diagrama de Bloques (BFD)", "Diagrama de Flujo de Proceso (PFD)"])
    
    with t1:
        st.info("Renderizando BFD desde AutoCAD Plant 3D")
        mostrar_pdf("diagrama_bfd.pdf")
        
    with t2:
        st.info("Renderizando PFD desde AutoCAD Plant 3D")
        mostrar_pdf("diagrama_pfd.pdf")

    st.divider()

    # --- SECCIÓN E: TUTOR IA (GEMINI 2.5 PRO) ---
    st.markdown('<h3 class="section-header">🧠 Tutor de Ingeniería Asistido por IA</h3>', unsafe_allow_html=True)
    modo_tutor = st.toggle("Habilitar Modo Tutor IA", value=False)
    
    if modo_tutor:
        st.markdown("Chatea con el asistente técnico sobre los resultados termodinámicos y financieros de tu simulación.")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt_usuario := st.chat_input("Ej: ¿Por qué el ROI es tan bajo si aumento la presión en V-100?"):
            st.session_state.messages.append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"):
                st.markdown(prompt_usuario)

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
else:
    # Mensaje de espera en estado inicial
    st.info("👈 Ajusta los parámetros operativos y de costos en el panel lateral, luego presiona **Ejecutar Simulación** para visualizar los balances y la evaluación económica.")
