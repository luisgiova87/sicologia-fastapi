import subprocess
import sys

def instalar_dependencias():
    librerias = ["streamlit", "pandas", "reportlab", "openpyxl", "requests", "urllib3"]
    for lib in librerias:
        try:
            __import__(lib)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

instalar_dependencias()

from datetime import datetime, date
import hashlib
import io
import json
import os
import re
import time
import pandas as pd
import streamlit as st
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

API_URL = os.getenv("API_URL", "https://sicologia-fastapi.vercel.app").rstrip("/")

if os.path.exists("url_api.txt"):
    try:
        with open("url_api.txt", "r", encoding="utf-8") as f:
            url_leida = f.read().strip()
            if url_leida:
                API_URL = url_leida.rstrip("/")
    except Exception:
        pass

def ejecutar_sistema():
    st.set_page_config(
        page_title="Sistema Clínico de Psicología",
        page_icon="🧠",
        layout="wide",
    )

    def encriptar_password(password):
        sal_sistema = "SISTEMA_CLINICO_PSICOLOGIA_EC_2026_SECURE"
        return hashlib.sha256(f"{password}{sal_sistema}".encode('utf-8')).hexdigest()

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
    if "psicologo_logueado" not in st.session_state:
        st.session_state["psicologo_logueado"] = None
    if "psicologo_id" not in st.session_state:
        st.session_state["psicologo_id"] = None
    if "nombre_psicologo" not in st.session_state:
        st.session_state["nombre_psicologo"] = None
    if "rol" not in st.session_state:
        st.session_state["rol"] = None
    if "licencia_info" not in st.session_state:
        st.session_state["licencia_info"] = {}
    if "menu_activo" not in st.session_state:
        st.session_state["menu_activo"] = ""

    # --- PANTALLA DE LOGIN Y RECUPERACIÓN ---
    if not st.session_state["autenticado"]:
        if os.path.exists("LOGO.jpeg"):
            try:
                st.image("LOGO.jpeg", width=220)
            except Exception:
                pass
        st.title("🔐 Sistema Clínico de Psicología")

        if "modo_recuperar" not in st.session_state:
            st.session_state["modo_recuperar"] = False

        if not st.session_state["modo_recuperar"]:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuario")
                password_input = st.text_input("Contraseña", type="password")
                
                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn1:
                    btn_login = st.form_submit_button("Ingresar al Sistema")

                if btn_login:
                    if not usuario_input.strip() or not password_input.strip():
                        st.error("Ingrese usuario y contraseña.")
                    else:
                        try:
                            resp = requests.post(
                                f"{API_URL}/login", 
                                json={"usuario": usuario_input.strip(), "password": password_input.strip()}, 
                                timeout=15,
                                verify=False
                            )
                            if resp.status_code == 200:
                                user_data = resp.json()
                                st.session_state["autenticado"] = True
                                st.session_state["psicologo_logueado"] = user_data["usuario"]
                                st.session_state["psicologo_id"] = user_data["id"]
                                st.session_state["nombre_psicologo"] = f"{user_data['primer_apellido']} {user_data.get('segundo_apellido', '')} {user_data['primer_nombre']}".strip()
                                st.session_state["rol"] = user_data["rol"]
                                st.session_state["licencia_info"] = {
                                    "estado": user_data.get("estado_licencia", "activo"),
                                    "expiracion": user_data.get("fecha_expiracion", "2099-12-31"),
                                    "limite": user_data.get("limite_pacientes", 9999)
                                }
                                
                                if user_data["rol"] == "admin":
                                    st.session_state["menu_activo"] = "Gestionar Licencias y Terapeutas"
                                else:
                                    st.session_state["menu_activo"] = "Gestión de Mis Pacientes"
                                    
                                st.rerun()
                            elif resp.status_code == 403:
                                st.error(f"🚫 Acceso Denegado: {resp.json().get('detail')}")
                            else:
                                st.error("Usuario o contraseña incorrectos.")
                        except Exception as e:
                            st.error(f"Error de conexión: {e}")

            c_link1, _ = st.columns([1, 1])
            with c_link1:
                if st.button("❓ ¿Olvidaste tu contraseña?", key="btn_ir_recuperar"):
                    st.session_state["modo_recuperar"] = True
                    st.rerun()

        else:
            st.subheader("📬 Recuperación de Contraseña por Correo")
            st.markdown("Paso 1: Solicite el código de seguridad a su correo registrado.")
            with st.form("form_solicitar_codigo"):
                user_email_req = st.text_input("Ingrese su Usuario o Correo Electrónico")
                btn_solicitar = st.form_submit_button("📩 Enviar Código de Seguridad")

                if btn_solicitar:
                    if not user_email_req.strip():
                        st.error("Por favor ingrese su usuario o correo.")
                    else:
                        try:
                            r_sol = requests.post(f"{API_URL}/solicitar-recuperacion", json={"usuario_o_email": user_email_req.strip()}, timeout=15, verify=False)
                            if r_sol.status_code == 200:
                                st.success(r_sol.json().get("mensaje", "Código enviado a su correo."))
                            else:
                                st.error(r_sol.json().get("detail", "Error al procesar la solicitud."))
                        except Exception as e:
                            st.error(f"Error de conexión: {e}")

            st.markdown("---")
            st.markdown("Paso 2: Ingrese el código recibido para establecer su nueva contraseña.")
            with st.form("form_restablecer_pass"):
                user_reset = st.text_input("Usuario")
                codigo_reset = st.text_input("Código de 6 dígitos recibido por correo")
                pass_nueva_reset = st.text_input("Nueva Contraseña", type="password")
                btn_restablecer = st.form_submit_button("💾 Guardar Nueva Contraseña")

                if btn_restablecer:
                    if not user_reset.strip() or not codigo_reset.strip() or not pass_nueva_reset.strip():
                        st.error("Todos los campos son obligatorios.")
                    else:
                        try:
                            r_res = requests.post(
                                f"{API_URL}/restablecer-password",
                                json={"usuario": user_reset.strip(), "codigo": codigo_reset.strip(), "nueva_password": pass_nueva_reset.strip()},
                                timeout=15,
                                verify=False
                            )
                            if r_res.status_code == 200:
                                st.success("¡Contraseña restablecida con éxito! Ya puede iniciar sesión.")
                            else:
                                st.error(r_res.json().get("detail", "Código inválido o expirado."))
                        except Exception as e:
                            st.error(f"Error de conexión: {e}")

            if st.button("⬅️ Volver al Inicio de Sesión"):
                st.session_state["modo_recuperar"] = False
                st.rerun()

        st.stop()

    # --- PANTALLA PRINCIPAL ---
    rol_actual = st.session_state["rol"]
    current_psi_id = st.session_state["psicologo_id"]
    lic = st.session_state.get("licencia_info", {})

    def validar_solo_letras(texto, nombre_campo):
        if not texto or not texto.strip():
            return f"El campo '{nombre_campo}' es obligatorio."
        if not re.match(r"^[A-Za-záéíóúÁÉÍÓÚñÑ\s]+$", texto.strip()):
            return f"El campo '{nombre_campo}' solo debe contener letras y espacios."
        return None

    def validar_identificacion(identificacion):
        if not identificacion or not identificacion.strip():
            return "La cédula o pasaporte es obligatoria."
        if not re.match(r"^[A-Za-z0-9\-]+$", identificacion.strip()):
            return "La identificación solo debe contener letras, números y guiones."
        return None

    def generar_pdf_sesion_msp(paciente, sesion, psicologo_info, institucion_datos):
        from xml.sax.saxutils import escape
        buffer = io.BytesIO()
        margen = 24
        ancho_util = letter[0] - 2 * margen
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=margen, leftMargin=margen, topMargin=22, bottomMargin=22, title="Historia Clínica - MSP")
        story = []
        styles = getSampleStyleSheet()

        def safe(value):
            if value is None:
                return ""
            return "<br/>".join(escape(line) if line else " " for line in str(value).replace("\r\n", "\n").split("\n"))

        cell = ParagraphStyle("MSPCell", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9, textColor=colors.HexColor("#17212B"), wordWrap="CJK")
        cell_bold = ParagraphStyle("MSPCellBold", parent=cell, fontName="Helvetica-Bold")
        heading = ParagraphStyle("MSPHeading", parent=cell_bold, fontSize=8, leading=10, textColor=colors.HexColor("#123B5D"))
        section_style = ParagraphStyle("MSPSection", parent=cell_bold, fontSize=8, leading=10, textColor=colors.HexColor("#123B5D"))
        small_center = ParagraphStyle("MSPCenter", parent=cell, alignment=1)

        azul = colors.HexColor("#123B5D")
        borde = colors.HexColor("#8EA7BC")
        fondo_titulo = colors.HexColor("#DCE6EF")

        def P(value, style=cell):
            return Paragraph(safe(value), style)

        def tabla(data, widths, header_rows=0, padding=4, repeat=0):
            t = Table(data, colWidths=widths, repeatRows=repeat, splitByRow=1, hAlign="LEFT")
            cmds = [
                ("BOX", (0, 0), (-1, -1), 0.7, azul),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, borde),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                ("TOPPADDING", (0, 0), (-1, -1), padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ]
            if header_rows:
                cmds.extend([("BACKGROUND", (0, 0), (-1, header_rows - 1), fondo_titulo), ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), azul)])
            t.setStyle(TableStyle(cmds))
            return t

        logo_path = next((p for p in ("LOGO.jpeg", "LOGO.jpg", "LOGO.png") if os.path.exists(p)), None)
        if logo_path:
            try:
                logo = RLImage(logo_path, width=115, height=37, kind="proportional")
                logo.hAlign = "LEFT"
                story.extend([logo, Spacer(1, 5)])
            except Exception:
                pass

        story.append(Paragraph("HISTORIA CLÍNICA PSICOLÓGICA", heading))
        story.append(Spacer(1, 4))

        n_archivo = paciente.get("numero_archivo", "") or ""
        story.append(tabla([[P("A. DATOS DEL ESTABLECIMIENTO Y USUARIO/PACIENTE", section_style)]], [ancho_util], header_rows=1, padding=4))
        story.append(tabla([
            [P("INSTITUCIÓN DEL SISTEMA"), P("UNICÓDIGO"), P("ESTABLECIMIENTO DE SALUD"), P("N.º HISTORIA CLÍNICA ÚNICA"), P("N.º ARCHIVO"), P("N.º HOJA")],
            [P(institucion_datos[0]), P(institucion_datos[1]), P(institucion_datos[2]), P(paciente.get("historia_clinica", "")), P(n_archivo), P("01")],
        ], [ancho_util * x for x in (0.19, 0.12, 0.20, 0.21, 0.16, 0.12)], header_rows=1, padding=3))
        story.append(tabla([
            [P("PRIMER APELLIDO"), P("SEGUNDO APELLIDO"), P("PRIMER NOMBRE"), P("SEGUNDO NOMBRE"), P("SEXO"), P("EDAD (AÑOS)")],
            [P(paciente.get("primer_apellido", "")), P(paciente.get("segundo_apellido", "")), P(paciente.get("primer_nombre", "")), P(paciente.get("segundo_nombre", "")), P(paciente.get("sexo", "")), P(paciente.get("edad", ""))],
        ], [ancho_util * x for x in (0.19, 0.19, 0.19, 0.19, 0.10, 0.14)], header_rows=1, padding=3))
        story.append(Spacer(1, 5))

        tipo = str(sesion.get("tipo_consulta", ""))
        story.append(tabla([
            [P("B. MOTIVO DE CONSULTA", section_style), P(f"PRIMERA: [{'X' if tipo.lower() == 'primera' else ' '}]", cell), P(f"SUBSECUENTE: [{'X' if tipo.lower() == 'subsecuente' else ' '}]", cell)],
            [P(sesion.get("motivo_consulta", "")), "", ""],
        ], [ancho_util * 0.60, ancho_util * 0.20, ancho_util * 0.20], header_rows=1, padding=4))
        story.append(Spacer(1, 5))

        for titulo, clave in [
            ("C. ANTECEDENTES PERSONALES", "antecedentes_personales"),
            ("D. ANTECEDENTES FAMILIARES", "antecedentes_familiares"),
            ("E. PROBLEMA ACTUAL", "problema_actual"),
        ]:
            story.append(tabla([[P(titulo, section_style)], [P(sesion.get(clave, ""))]], [ancho_util], header_rows=1, padding=4))
            story.append(Spacer(1, 5))

        diag_rows = [[P("DESCRIPCIÓN", cell_bold), P("CIE 10", cell_bold), P("CIE 11", cell_bold), P("PRE", cell_bold), P("DEF", cell_bold)]]
        try:
            diag_data = sesion.get("diagnosticos", "[]")
            if isinstance(diag_data, str):
                diag_data = json.loads(diag_data)
            for d in diag_data:
                diag_rows.append([P(d.get("desc", "")), P(d.get("cie10", "")), P(d.get("cie11", "")), P("X" if d.get("pre") else "", small_center), P("X" if d.get("def") else "", small_center)])
        except Exception:
            pass
        story.append(tabla([[P("I. DIAGNÓSTICO", section_style)]], [ancho_util], header_rows=1, padding=4))
        story.append(tabla(diag_rows, [ancho_util * x for x in (0.48, 0.18, 0.18, 0.08, 0.08)], header_rows=1, repeat=1, padding=4))
        story.append(Spacer(1, 5))

        pruebas_rows = [[P("PRUEBAS", section_style), P("DETALLE / PUNTAJE", cell_bold)]]
        try:
            pruebas_data = sesion.get("pruebas", "[]")
            if isinstance(pruebas_data, str):
                pruebas_data = json.loads(pruebas_data)
            for prueba in pruebas_data:
                pruebas_rows.append([P(prueba.get("test", "")), P(prueba.get("puntaje", ""))])
        except Exception:
            pass
        story.append(tabla(pruebas_rows, [ancho_util * 0.45, ancho_util * 0.55], header_rows=1, repeat=1, padding=4))
        story.append(Spacer(1, 5))

        story.append(tabla([
            [P("J. PLAN DE TRATAMIENTO", section_style)],
            [P(sesion.get("plan_tratamiento", ""))],
            [P(f"EVOLUCIÓN — FECHA: {sesion.get('fecha', '')} | HORA: {sesion.get('hora', '')}", section_style)],
            [P(sesion.get("notas_evolucion", ""))],
            [P(f"PRÓXIMA CITA PROGRAMADA: {sesion.get('proxima_cita', '')}", cell_bold)],
        ], [ancho_util], header_rows=0, padding=4))
        story.append(Spacer(1, 14))

        psi = list(psicologo_info or ["", "", "", "", ""]) + [""] * 5
        story.append(tabla([
            [P("K. DATOS DEL PROFESIONAL RESPONSABLE", section_style), P(""), P(""), P("")],
            [P("PRIMER NOMBRE"), P("PRIMER APELLIDO"), P("SEGUNDO APELLIDO"), P("DOCUMENTO DE IDENTIFICACIÓN")],
            [P(psi[2]), P(psi[0]), P(psi[1]), P(psi[4])],
            [P("FECHA"), P("HORA"), P("FIRMA"), P("SELLO")],
            [P(sesion.get("fecha", "")), P(sesion.get("hora", "")), P("________________________"), P("")],
        ], [ancho_util * x for x in (0.24, 0.24, 0.24, 0.28)], header_rows=1, padding=5))
        doc.build(story)
        buffer.seek(0)
        return buffer

    # --- MENÚ LATERAL ---
    st.sidebar.markdown("---")
    if rol_actual == "admin":
        st.sidebar.title("⚙️ Administrador General")
        if st.sidebar.button("👥 Licencias y Terapeutas", use_container_width=True):
            st.session_state["menu_activo"] = "Gestionar Licencias y Terapeutas"
            st.rerun()
        if st.sidebar.button("📋 Ver Todos los Pacientes", use_container_width=True):
            st.session_state["menu_activo"] = "Ver Todos los Pacientes"
            st.rerun()
        
        # BOTÓN DE DESCARGA DE BACKUP PARA ADMINISTRADOR
        try:
            r_bkp = requests.get(f"{API_URL}/admin/backup?admin_id={current_psi_id}", timeout=10, verify=False)
            if r_bkp.status_code == 200:
                json_bkp = r_bkp.text
                st.sidebar.download_button(
                    label="💾 Descargar Backup DB",
                    data=json_bkp,
                    file_name=f"Backup_Sistema_Clinico_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True
                )
        except Exception:
            pass

        if st.sidebar.button("🔑 Cambiar Contraseña", use_container_width=True):
            st.session_state["menu_activo"] = "Cambiar Contraseña"
            st.rerun()
    else:
        st.sidebar.title(f"👨‍⚕️ Terapeuta:\n{st.session_state['nombre_psicologo']}")
        st.sidebar.caption(f"📜 Expiración: **{lic.get('expiracion', 'N/A')}**")
        st.sidebar.caption(f"📊 Límite: **{lic.get('limite', 'Ilimitado')}**")
        
        if st.sidebar.button("👥 Gestión de Mis Pacientes", use_container_width=True):
            st.session_state["menu_activo"] = "Gestión de Mis Pacientes"
            st.rerun()
        if st.sidebar.button("📝 Registrar Sesión / Evolución", use_container_width=True):
            st.session_state["menu_activo"] = "Registrar Sesión / Evolución"
            st.rerun()
        if st.sidebar.button("🔍 Buscar Paciente e Historial", use_container_width=True):
            st.session_state["menu_activo"] = "Buscar Paciente e Historial"
            st.rerun()
        if st.sidebar.button("⚙️ Configurar Mis Datos", use_container_width=True):
            st.session_state["menu_activo"] = "Configurar Mis Datos"
            st.rerun()
        if st.sidebar.button("🔑 Cambiar Contraseña", use_container_width=True):
            st.session_state["menu_activo"] = "Cambiar Contraseña"
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    menu = st.session_state.get("menu_activo") or ("Gestionar Licencias y Terapeutas" if rol_actual == "admin" else "Gestión de Mis Pacientes")

    # --- NAVEGACIÓN ADMIN ---
    if rol_actual == "admin":
        if menu == "Gestionar Licencias y Terapeutas":
            st.header("🔑 Control de Licencias y Terapeutas")
            try:
                resp_psis = requests.get(f"{API_URL}/psicologos", timeout=10, verify=False)
                lista_psis = resp_psis.json().get("psicologos", []) if resp_psis.status_code == 200 else []
            except Exception:
                lista_psis = []

            df_psis = pd.DataFrame([p for p in lista_psis if p.get("rol") != "admin"])

            # REGISTRAR NUEVO TERAPEUTA
            with st.form("form_nuevo_psi_licencia"):
                st.subheader("➕ Registrar Nuevo Cliente / Terapeuta")
                nuevo_user = st.text_input("Usuario (Login)")
                nuevo_pass = st.text_input("Contraseña", type="password")
                nuevo_email = st.text_input("Correo Electrónico (Para recuperación)")
                c_1, c_2 = st.columns(2)
                with c_1:
                    p_ape = st.text_input("Primer Apellido")
                    p_nom = st.text_input("Primer Nombre")
                with c_2:
                    cedula_psi = st.text_input("Cédula / Identificación")
                    inst_sistema = st.text_input("Institución", value="MSP")
                
                col_l1, col_l2, col_l3 = st.columns(3)
                with col_l1: est_lic = st.selectbox("Estado", ["activo", "suspendido"])
                with col_l2: f_exp = st.date_input("Expiración", value=date(2026, 12, 31)).strftime("%Y-%m-%d")
                with col_l3: lim_pac = st.number_input("Límite Pacientes", min_value=1, max_value=9999, value=100)

                if st.form_submit_button("Crear Cliente con Licencia"):
                    if not nuevo_user or not nuevo_pass or not p_ape or not p_nom or not cedula_psi:
                        st.error("Campos obligatorios incompletos.")
                    else:
                        payload = {
                            "usuario": nuevo_user.strip(),
                            "password": encriptar_password(nuevo_pass.strip()),
                            "email": nuevo_email.strip(),
                            "primer_apellido": p_ape.strip(),
                            "primer_nombre": p_nom.strip(),
                            "cedula": cedula_psi.strip(),
                            "rol": "psicologo",
                            "institucion": inst_sistema.strip(),
                            "estado_licencia": est_lic,
                            "fecha_expiracion": f_exp,
                            "limite_pacientes": int(lim_pac)
                        }
                        r = requests.post(f"{API_URL}/psicologos", json=payload, timeout=10, verify=False)
                        if r.status_code == 200:
                            st.success("¡Cliente y licencia creados con éxito!")
                            time.sleep(1)
                            st.rerun()

            st.markdown("---")
            st.subheader("📋 Modificar / Eliminar Terapeutas")
            if not df_psis.empty:
                dict_psi_edit = {f"{r['primer_apellido']} {r['primer_nombre']} ({r['usuario']}) — Expira: {r.get('fecha_expiracion')}": r["id"] for _, r in df_psis.iterrows()}
                sel_psi = st.selectbox("Seleccione terapeuta:", list(dict_psi_edit.keys()))
                id_psi_sel = dict_psi_edit[sel_psi]
                psi_sel_data = next((p for p in lista_psis if p["id"] == id_psi_sel), None)

                if psi_sel_data:
                    c_act1, c_act2 = st.columns(2)
                    with c_act1:
                        btn_editar_psi = st.button("✏️ Modificar Terapeuta Seleccionado", key=f"btn_toggle_edit_{id_psi_sel}")
                    with c_act2:
                        btn_eliminar_psi = st.button("🗑️ Eliminar Terapeuta Seleccionado", key=f"btn_del_{id_psi_sel}")

                    if btn_editar_psi:
                        st.session_state[f"edit_psi_{id_psi_sel}"] = True
                        st.session_state[f"del_psi_{id_psi_sel}"] = False

                    if btn_eliminar_psi:
                        st.session_state[f"del_psi_{id_psi_sel}"] = True
                        st.session_state[f"edit_psi_{id_psi_sel}"] = False

                    # FORMULARIO DE CONFIRMACIÓN CON CONTRASEÑA
                    if st.session_state.get(f"del_psi_{id_psi_sel}", False):
                        with st.form(f"form_confirm_del_psi_{id_psi_sel}"):
                            st.warning(f"⚠️ ¿Está seguro que desea eliminar al terapeuta **{psi_sel_data['usuario']}**? Se borrarán sus pacientes y sesiones.")
                            pass_confirm_admin = st.text_input("Ingrese su contraseña de Administrador para confirmar", type="password")
                            
                            c_del_b1, c_del_b2 = st.columns(2)
                            with c_del_b1:
                                confirm_del = st.form_submit_button("🔥 Confirmar Eliminación")
                            with c_del_b2:
                                cancel_del = st.form_submit_button("❌ Cancelar")

                            if confirm_del:
                                if not pass_confirm_admin.strip():
                                    st.error("Debe ingresar su contraseña para confirmar.")
                                else:
                                    payload_del = {
                                        "admin_id": current_psi_id,
                                        "password": pass_confirm_admin.strip()
                                    }
                                    r_del = requests.request("DELETE", f"{API_URL}/psicologos/{id_psi_sel}", json=payload_del, timeout=10, verify=False)
                                    if r_del.status_code == 200:
                                        st.session_state[f"del_psi_{id_psi_sel}"] = False
                                        st.success("🗑️ Terapeuta y sus accesos eliminados correctamente.")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"Error: {r_del.json().get('detail', 'Contraseña incorrecta')}")

                            if cancel_del:
                                st.session_state[f"del_psi_{id_psi_sel}"] = False
                                st.rerun()

                    # FORMULARIO COLAPSADO (DESPLIEGUE TRAS EL CLIC)
                    if st.session_state.get(f"edit_psi_{id_psi_sel}", False):
                        with st.form(f"form_modificar_psi_{id_psi_sel}"):
                            st.markdown(f"#### ⚙️ Modificar Datos de `{psi_sel_data['usuario']}`")
                            m_u = st.text_input("Usuario", value=psi_sel_data.get("usuario", ""))
                            m_p = st.text_input("Nueva Contraseña (Dejar en blanco para conservar la actual)", type="password")
                            col_m_n1, col_m_n2 = st.columns(2)
                            with col_m_n1:
                                m_pa = st.text_input("Primer Apellido", value=psi_sel_data.get("primer_apellido", ""))
                                m_pn = st.text_input("Primer Nombre", value=psi_sel_data.get("primer_nombre", ""))
                            with col_m_n2:
                                m_ced = st.text_input("Cédula", value=psi_sel_data.get("cedula", ""))
                                m_email = st.text_input("Correo Electrónico", value=psi_sel_data.get("email", ""))
                            
                            col_m1, col_m2, col_m3 = st.columns(3)
                            with col_m1: 
                                m_est = st.selectbox("Estado", ["activo", "suspendido"], index=0 if psi_sel_data.get("estado_licencia") == "activo" else 1)
                            with col_m2:
                                curr_date = datetime.strptime(psi_sel_data.get("fecha_expiracion", "2026-12-31"), "%Y-%m-%d").date() if psi_sel_data.get("fecha_expiracion") else date.today()
                                m_fexp = st.date_input("Fecha Expiración", value=curr_date).strftime("%Y-%m-%d")
                            with col_m3: 
                                m_lim = st.number_input("Nuevo Límite", value=int(psi_sel_data.get("limite_pacientes") or 100))

                            col_f_btn1, col_f_btn2 = st.columns(2)
                            with col_f_btn1:
                                guardar_cambios = st.form_submit_button("💾 Guardar Cambios")
                            with col_f_btn2:
                                cancelar_edicion = st.form_submit_button("❌ Cancelar")

                            if guardar_cambios:
                                payload_up = {
                                    "usuario": m_u.strip(),
                                    "primer_apellido": m_pa.strip(),
                                    "primer_nombre": m_pn.strip(),
                                    "cedula": m_ced.strip(),
                                    "email": m_email.strip(),
                                    "estado_licencia": m_est,
                                    "fecha_expiracion": m_fexp,
                                    "limite_pacientes": int(m_lim)
                                }
                                if m_p.strip():
                                    payload_up["password"] = encriptar_password(m_p.strip())

                                r_up = requests.put(f"{API_URL}/psicologos/{id_psi_sel}", json=payload_up, timeout=10, verify=False)
                                if r_up.status_code == 200:
                                    st.session_state[f"edit_psi_{id_psi_sel}"] = False
                                    st.success("Datos del terapeuta actualizados correctamente.")
                                    time.sleep(1)
                                    st.rerun()

                            if cancelar_edicion:
                                st.session_state[f"edit_psi_{id_psi_sel}"] = False
                                st.rerun()

                st.dataframe(df_psis[["usuario", "email", "primer_apellido", "primer_nombre", "estado_licencia", "fecha_expiracion", "limite_pacientes"]], use_container_width=True)

        elif menu == "Ver Todos los Pacientes":
            st.header("📋 Listado General de Pacientes")
            try:
                resp = requests.get(f"{API_URL}/pacientes/todos", timeout=10, verify=False)
                st.dataframe(pd.DataFrame(resp.json().get("pacientes", [])), use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")

        elif menu == "Cambiar Contraseña":
            st.header("🔑 Cambiar Contraseña de Administrador")
            with st.form("form_pass_adm"):
                p_act = st.text_input("Contraseña Actual", type="password")
                p_nue = st.text_input("Nueva Contraseña", type="password")
                if st.form_submit_button("Actualizar Contraseña"):
                    if not p_act or not p_nue:
                        st.error("Campos vacíos.")
                    else:
                        payload = {"password_actual": p_act, "password_nueva": encriptar_password(p_nue)}
                        r = requests.put(f"{API_URL}/psicologos/{current_psi_id}/password", json=payload, timeout=10, verify=False)
                        if r.status_code == 200:
                            st.success("¡Contraseña del Administrador cambiada con éxito!")
                        else:
                            st.error(f"Error: {r.json().get('detail', 'Contraseña actual incorrecta')}")

    # --- NAVEGACIÓN TERAPEUTA ---
    else:
        try:
            resp_psi = requests.get(f"{API_URL}/psicologos/{current_psi_id}", timeout=10, verify=False)
            psi_info_data = resp_psi.json() if resp_psi.status_code == 200 else {}
        except Exception:
            psi_info_data = {}

        f_inst = psi_info_data.get("institucion", "MSP")
        f_uni = psi_info_data.get("unicodigo", "0000")
        f_est = psi_info_data.get("establecimiento", "CENTRO SALUD")

        if menu == "Gestión de Mis Pacientes":
            st.header("👥 Gestión de Mis Pacientes")
            try:
                resp_mis_p = requests.get(f"{API_URL}/pacientes?psicologo_id={current_psi_id}", timeout=10, verify=False)
                mis_pacs = resp_mis_p.json().get("pacientes", []) if resp_mis_p.status_code == 200 else []
            except Exception:
                mis_pacs = []

            last_arch = mis_pacs[0]["numero_archivo"] if mis_pacs and "numero_archivo" in mis_pacs[0] else None
            next_archivo = str(int(last_arch) + 1).zfill(4) if last_arch and str(last_arch).isdigit() else "0001"

            with st.form("form_paciente"):
                st.subheader("A. DATOS DEL ESTABLECIMIENTO Y USUARIO/PACIENTE")
                st.info(f"📌 N° de Archivo sugerido: **{next_archivo}**")
                col1, col2 = st.columns(2)
                with col1:
                    p_apellido = st.text_input("Primer Apellido")
                    s_apellido = st.text_input("Segundo Apellido (Opcional)")
                    p_nombre = st.text_input("Primer Nombre")
                    s_nombre = st.text_input("Segundo Nombre (Opcional)")
                with col2:
                    sexo = st.selectbox("Sexo", ["F", "M", "Otro"])
                    edad = st.number_input("Edad (Años)", 0, 120, 25)
                    identificacion_hc = st.text_input("N.º Historia Clínica Única (Cédula/Pasaporte)")
                    custom_archivo = st.text_input("Número de Archivo", value=next_archivo)

                if st.form_submit_button("Guardar Paciente"):
                    err = validar_solo_letras(p_apellido, "Primer Apellido") or validar_solo_letras(p_nombre, "Primer Nombre") or validar_identificacion(identificacion_hc)
                    if err:
                        st.error(err)
                    else:
                        payload = {
                            "psicologo_id": current_psi_id,
                            "primer_apellido": p_apellido.strip(),
                            "segundo_apellido": s_apellido.strip() if s_apellido else "",
                            "primer_nombre": p_nombre.strip(),
                            "segundo_nombre": s_nombre.strip() if s_nombre else "",
                            "sexo": sexo,
                            "edad": edad,
                            "historia_clinica": identificacion_hc.strip(),
                            "numero_archivo": custom_archivo.strip()
                        }
                        r = requests.post(f"{API_URL}/pacientes", json=payload, timeout=10, verify=False)
                        if r.status_code == 200:
                            st.success("¡Paciente guardado exitosamente!")
                            time.sleep(1)
                            st.rerun()
                        elif r.status_code == 403:
                            st.error(f"🚫 Límite alcanzado: {r.json().get('detail')}")

            st.markdown("---")
            st.subheader("📋 Mis Pacientes Registrados")
            df_mis_p_admin = pd.DataFrame(mis_pacs)
            
            if not df_mis_p_admin.empty:
                dict_p_edit = {f"{r['primer_apellido']} {r.get('segundo_apellido') or ''} {r['primer_nombre']} {r.get('segundo_nombre') or ''} — HC: {r['historia_clinica']}": r["id"] for _, r in df_mis_p_admin.iterrows()}
                sel_pac_editar = st.selectbox("Seleccione paciente para editar/eliminar:", list(dict_p_edit.keys()), key="sel_pac_admin_edit")
                id_pac_sel = dict_p_edit[sel_pac_editar]

                c_bp1, c_bp2 = st.columns(2)
                with c_bp1: abrir_form_mod_pac = st.button("✏️ Modificar Paciente Seleccionado", key="btn_toggle_mod_pac")
                with c_bp2: abrir_form_del_pac = st.button("🗑️ Eliminar Paciente Seleccionado", key="btn_toggle_del_pac")

                if abrir_form_mod_pac:
                    st.session_state[f"edit_pac_{id_pac_sel}"] = True
                    st.session_state[f"del_pac_{id_pac_sel}"] = False

                if abrir_form_del_pac:
                    st.session_state[f"del_pac_{id_pac_sel}"] = True
                    st.session_state[f"edit_pac_{id_pac_sel}"] = False

                # FORMULARIO DE CONFIRMACIÓN CON CONTRASEÑA PARA ELIMINAR PACIENTE
                if st.session_state.get(f"del_pac_{id_pac_sel}", False):
                    p_del_data = next((p for p in mis_pacs if p["id"] == id_pac_sel), None)
                    with st.form(f"form_confirm_del_pac_{id_pac_sel}"):
                        st.warning(f"⚠️ ¿Está seguro que desea eliminar al paciente **{p_del_data['primer_apellido']} {p_del_data['primer_nombre']}** (HC: {p_del_data['historia_clinica']})?")
                        pass_confirm_pac = st.text_input("Ingrese su contraseña para confirmar la eliminación", type="password")
                        
                        c_pdel_1, c_pdel_2 = st.columns(2)
                        with c_pdel_1:
                            confirm_del_pac = st.form_submit_button("🔥 Confirmar Eliminación")
                        with c_pdel_2:
                            cancel_del_pac = st.form_submit_button("❌ Cancelar")

                        if confirm_del_pac:
                            if not pass_confirm_pac.strip():
                                st.error("Debe ingresar su contraseña para confirmar.")
                            else:
                                payload_del_p = {
                                    "psicologo_id": current_psi_id,
                                    "password": pass_confirm_pac.strip()
                                }
                                r_del_p = requests.request("DELETE", f"{API_URL}/pacientes/{id_pac_sel}", json=payload_del_p, timeout=10, verify=False)
                                if r_del_p.status_code == 200:
                                    st.session_state[f"del_pac_{id_pac_sel}"] = False
                                    st.success("🗑️ Paciente y su historial eliminados correctamente.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Error: {r_del_p.json().get('detail', 'Contraseña incorrecta')}")

                        if cancel_del_pac:
                            st.session_state[f"del_pac_{id_pac_sel}"] = False
                            st.rerun()

                if st.session_state.get(f"edit_pac_{id_pac_sel}", False):
                    p_actual_data = next((p for p in mis_pacs if p["id"] == id_pac_sel), None)
                    if p_actual_data:
                        with st.form(f"form_editar_paciente_{id_pac_sel}"):
                            st.markdown("#### ✏️ Modificar Paciente")
                            e_pa = st.text_input("Primer Apellido", value=p_actual_data["primer_apellido"])
                            e_sa = st.text_input("Segundo Apellido (Opcional)", value=str(p_actual_data.get("segundo_apellido", "") or ""))
                            e_pn = st.text_input("Primer Nombre", value=p_actual_data["primer_nombre"])
                            e_sn = st.text_input("Segundo Nombre (Opcional)", value=str(p_actual_data.get("segundo_nombre", "") or ""))
                            e_sexo = st.selectbox("Sexo", ["F", "M", "Otro"], index=["F", "M", "Otro"].index(p_actual_data["sexo"]) if p_actual_data["sexo"] in ["F", "M", "Otro"] else 0)
                            e_edad = st.number_input("Edad", 0, 120, int(p_actual_data["edad"]))
                            e_hc = st.text_input("Historia Clínica", value=p_actual_data["historia_clinica"])
                            e_arch = st.text_input("N° Archivo", value=p_actual_data["numero_archivo"])

                            if st.form_submit_button("💾 Guardar Cambios"):
                                payload = {
                                    "primer_apellido": e_pa.strip(),
                                    "segundo_apellido": e_sa.strip() if e_sa else "",
                                    "primer_nombre": e_pn.strip(),
                                    "segundo_nombre": e_sn.strip() if e_sn else "",
                                    "sexo": e_sexo,
                                    "edad": e_edad,
                                    "historia_clinica": e_hc.strip(),
                                    "numero_archivo": e_arch.strip()
                                }
                                r = requests.put(f"{API_URL}/pacientes/{id_pac_sel}", json=payload, timeout=10, verify=False)
                                if r.status_code == 200:
                                    st.session_state[f"edit_pac_{id_pac_sel}"] = False
                                    st.success("¡Paciente actualizado!")
                                    time.sleep(1)
                                    st.rerun()

                st.markdown("---")
                st.dataframe(df_mis_p_admin[["numero_archivo", "primer_apellido", "segundo_apellido", "primer_nombre", "segundo_nombre", "historia_clinica", "edad", "sexo"]], use_container_width=True)

        elif menu == "Registrar Sesión / Evolución":
            st.header("📝 Registro de Sesión y Evolución - Plantilla MSP")
            try:
                resp_mis_p = requests.get(f"{API_URL}/pacientes?psicologo_id={current_psi_id}", timeout=10, verify=False)
                df_mis_pacientes = pd.DataFrame(resp_mis_p.json().get("pacientes", []))
            except Exception:
                df_mis_pacientes = pd.DataFrame()

            if df_mis_pacientes.empty:
                st.warning("Debe registrar al menos un paciente primero.")
            else:
                paciente_dict = {f"{r['primer_apellido']} {r.get('segundo_apellido') or ''} {r['primer_nombre']} {r.get('segundo_nombre') or ''} - HC: {r['historia_clinica']}": r["id"] for _, r in df_mis_pacientes.iterrows()}
                selected_label = st.selectbox("A. DATOS DEL USUARIO/PACIENTE (Selección)", list(paciente_dict.keys()), key="sel_pac_ses")
                paciente_id = paciente_dict[selected_label]

                try:
                    resp_ses = requests.get(f"{API_URL}/sesiones?paciente_id={paciente_id}", timeout=10, verify=False)
                    sesiones_pac = resp_ses.json().get("sesiones", []) if resp_ses.status_code == 200 else []
                except Exception:
                    sesiones_pac = []

                tipo_consulta_auto = "Primera" if len(sesiones_pac) == 0 else "Subsecuente"
                ant_personales_default = sesiones_pac[0]["antecedentes_personales"] if sesiones_pac else ""
                ant_familiares_default = sesiones_pac[0]["antecedentes_familiares"] if sesiones_pac else ""

                if "temp_diagnosticos" not in st.session_state: st.session_state.temp_diagnosticos = []
                if "temp_pruebas" not in st.session_state: st.session_state.temp_pruebas = []

                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    fecha_sesion_obj = st.date_input("FECHA DE LA SESIÓN (DÍA/MES/AÑO)", value=date.today())
                    fecha_sesion = fecha_sesion_obj.strftime("%d/%m/%Y")
                with col_f2:
                    horas_dinamicas = [f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 15, 30, 45)]
                    hora_actual_str = datetime.now().strftime("%H:%M")
                    idx_hora_def = next((i for i, h in enumerate(horas_dinamicas) if h >= hora_actual_str), 0)
                    hora_sesion = st.selectbox("HORA DE LA SESIÓN", horas_dinamicas, index=idx_hora_def)

                st.info(f"📅 Cita programada: **{fecha_sesion}** a las **{hora_sesion}** | Consulta: **{tipo_consulta_auto}**")

                st.markdown("#### B. MOTIVO DE CONSULTA")
                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    motivo = st.text_area("Detalle del Motivo de Consulta")
                with col_b2:
                    tipo_consulta_sel = st.radio("Tipo de Consulta", ["Primera", "Subsecuente"], index=0 if tipo_consulta_auto == "Primera" else 1)

                st.markdown("#### C. ANTECEDENTES PERSONALES")
                ant_personales = st.text_area("C. Antecedentes Personales", value=ant_personales_default)

                st.markdown("#### D. ANTECEDENTES FAMILIARES")
                ant_familiares = st.text_area("D. Antecedentes Familiares", value=ant_familiares_default)

                st.markdown("#### E. PROBLEMA ACTUAL")
                st.caption("Cronología, Características, Intensidad, Frecuencia, Factores agravantes")
                problema_actual = st.text_area("Detalle del Problema Actual")

                st.markdown("#### I. DIAGNÓSTICO (CIE-10 / CIE-11)")
                with st.form("form_add_diag", clear_on_submit=True):
                    d_desc = st.text_input("Descripción Diagnóstico")
                    c10 = st.text_input("CIE-10")
                    c11 = st.text_input("CIE-11 (Opcional)")
                    col_p, col_d = st.columns(2)
                    with col_p: is_pre = st.checkbox("PRE (Presuntivo)")
                    with col_d: is_def = st.checkbox("DEF (Definitivo)")
                    if st.form_submit_button("➕ Añadir Diagnóstico"):
                        if d_desc.strip():
                            st.session_state.temp_diagnosticos.append({"desc": d_desc.strip(), "cie10": c10.strip(), "cie11": c11.strip(), "pre": is_pre, "def": is_def})
                            st.rerun()

                if st.session_state.temp_diagnosticos:
                    for idx, d in enumerate(st.session_state.temp_diagnosticos):
                        st.markdown(f"- **{idx+1}. {d['desc']}** | CIE-10: `{d['cie10']}` | PRE: {d['pre']} | DEF: {d['def']}")
                    if st.button("🗑️ Limpiar diagnósticos"):
                        st.session_state.temp_diagnosticos = []
                        st.rerun()

                st.markdown("#### PRUEBAS PSICOLÓGICAS")
                with st.form("form_add_test", clear_on_submit=True):
                    test_sel = st.selectbox("Prueba", ["HADM", "Hamilton Depresión", "Hamilton Ansiedad", "MMS", "Reloj", "SPENCE", "OTRA"])
                    test_punt = st.text_input("Puntaje / Resultado")
                    if st.form_submit_button("➕ Añadir Prueba"):
                        if test_punt.strip():
                            st.session_state.temp_pruebas.append({"test": test_sel, "puntaje": test_punt.strip()})
                            st.rerun()

                if st.session_state.temp_pruebas:
                    for idx, p in enumerate(st.session_state.temp_pruebas):
                        st.markdown(f"- **{idx+1}. {p['test']}**: `{p['puntaje']}`")
                    if st.button("🗑️ Limpiar pruebas"):
                        st.session_state.temp_pruebas = []
                        st.rerun()

                with st.form("form_registro_sesion_final"):
                    st.markdown("#### J. PLAN DE TRATAMIENTO")
                    plan_tratamiento = st.text_area("J. Plan de Tratamiento")

                    st.markdown("#### EVOLUCIÓN Y PRÓXIMA CITA")
                    notas_evol = st.text_area("Notas de Evolución")
                    proxima_cita_fecha = st.date_input("Próxima Cita Programada", value=date.today()).strftime("%d/%m/%Y")

                    st.markdown("#### K. DATOS DEL PROFESIONAL RESPONSABLE")
                    st.info(f"👨‍⚕️ **{st.session_state['nombre_psicologo']}** | Documento: `{psi_info_data.get('cedula', '')}`")

                    if st.form_submit_button("💾 Guardar Sesión Completa"):
                        if not motivo.strip() or not problema_actual.strip():
                            st.error("El Motivo de Consulta y Problema Actual son obligatorios.")
                        else:
                            payload = {
                                "paciente_id": paciente_id,
                                "psicologo_id": current_psi_id,
                                "fecha": fecha_sesion,
                                "hora": hora_sesion,
                                "tipo_consulta": tipo_consulta_sel,
                                "motivo_consulta": motivo,
                                "antecedentes_personales": ant_personales,
                                "antecedentes_familiares": ant_familiares,
                                "problema_actual": problema_actual,
                                "diagnosticos": json.dumps(st.session_state.temp_diagnosticos),
                                "pruebas": json.dumps(st.session_state.temp_pruebas),
                                "plan_tratamiento": plan_tratamiento,
                                "notas_evolucion": notas_evol,
                                "proxima_cita": proxima_cita_fecha
                            }
                            r = requests.post(f"{API_URL}/sesiones", json=payload, timeout=10, verify=False)
                            if r.status_code == 200:
                                st.session_state.temp_diagnosticos = []
                                st.session_state.temp_pruebas = []
                                st.success("¡Sesión registrada correctamente en la base de datos!")
                                time.sleep(1)
                                st.rerun()

        elif menu == "Buscar Paciente e Historial":
            st.header("🔍 Buscar Paciente e Historial Completo")
            with st.form("form_busqueda_paciente"):
                col_b1, col_b2 = st.columns([3, 1])
                with col_b1: busqueda = st.text_input("Ingrese nombre, apellido, cédula o N° de archivo:", value="")
                with col_b2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_buscar = st.form_submit_button("🔎 Buscar")

            try:
                resp_pacs = requests.get(f"{API_URL}/pacientes?psicologo_id={current_psi_id}&filtro={busqueda}", timeout=10, verify=False)
                pacs_encontrados = resp_pacs.json().get("pacientes", []) if resp_pacs.status_code == 200 else []
            except Exception:
                pacs_encontrados = []

            if pacs_encontrados:
                st.success(f"Se encontraron {len(pacs_encontrados)} paciente(s).")
                p_dict = {f"{r['primer_apellido']} {r.get('segundo_apellido') or ''} {r['primer_nombre']} {r.get('segundo_nombre') or ''} — HC: {r['historia_clinica']} (Archivo: {r['numero_archivo']})": r["id"] for r in pacs_encontrados}
                sel_p = st.selectbox("Seleccione paciente:", list(p_dict.keys()), key="select_paciente_encontrado")
                p_id = p_dict[sel_p]
                p_info_dict = next((p for p in pacs_encontrados if p["id"] == p_id), {})

                st.markdown("### A. DATOS DEL ESTABLECIMIENTO Y USUARIO/PACIENTE")
                st.dataframe(pd.DataFrame([p_info_dict]), use_container_width=True)

                try:
                    resp_ses = requests.get(f"{API_URL}/sesiones?paciente_id={p_id}", timeout=10, verify=False)
                    ses_list = resp_ses.json().get("sesiones", []) if resp_ses.status_code == 200 else []
                except Exception:
                    ses_list = []

                if ses_list:
                    st.markdown("### 📋 Historial Clínico (Plantilla MSP Ordenada)")
                    for s in ses_list:
                        hora_str = s.get('hora', '00:00')
                        fecha_str = s.get('fecha', '')
                        with st.expander(f"Sesión del {fecha_str} (Hora: {hora_str}) — Tipo: {s['tipo_consulta']}"):
                            st.markdown(f"**FECHA Y HORA:** {fecha_str} - {hora_str}")
                            st.markdown(f"**B. MOTIVO DE CONSULTA ({s['tipo_consulta']}):**\n> {s['motivo_consulta']}")
                            st.markdown(f"**C. ANTECEDENTES PERSONALES:**\n> {s.get('antecedentes_personales') or 'N/A'}")
                            st.markdown(f"**D. ANTECEDENTES FAMILIARES:**\n> {s.get('antecedentes_familiares') or 'N/A'}")
                            st.markdown(f"**E. PROBLEMA ACTUAL:**\n> {s['problema_actual']}")
                            
                            st.markdown("**I. DIAGNÓSTICO (CIE-10 / CIE-11):**")
                            try:
                                diags_list = json.loads(s.get('diagnosticos') or "[]")
                                for d in diags_list:
                                    t_p = "Sí" if d.get('pre') else "No"
                                    t_d = "Sí" if d.get('def') else "No"
                                    st.markdown(f"- *{d.get('desc')}* | CIE-10: `{d.get('cie10')}` | PRE: {t_p} | DEF: {t_d}")
                            except Exception:
                                pass

                            st.markdown("**PRUEBAS PSICOLÓGICAS:**")
                            try:
                                pruebas_list = json.loads(s.get('pruebas') or "[]")
                                for p in pruebas_list:
                                    st.markdown(f"- **{p.get('test')}**: `{p.get('puntaje')}`")
                            except Exception:
                                pass

                            st.markdown(f"**J. PLAN DE TRATAMIENTO:**\n> {s.get('plan_tratamiento') or 'N/A'}")
                            st.markdown(f"**EVOLUCIÓN:**\n> {s.get('notas_evolucion') or 'N/A'}")
                            st.markdown(f"**PRÓXIMA CITA:** `{s.get('proxima_cita') or 'No programada'}`")
                            st.markdown(f"**K. PROFESIONAL RESPONSABLE:** {st.session_state['nombre_psicologo']}")

                            st.markdown("---")
                            c_s1, c_s2, c_s3 = st.columns(3)
                            with c_s1:
                                pdf = generar_pdf_sesion_msp(p_info_dict, s, [psi_info_data.get("primer_apellido"), psi_info_data.get("segundo_apellido"), psi_info_data.get("primer_nombre"), psi_info_data.get("segundo_nombre"), psi_info_data.get("cedula")], (f_inst, f_uni, f_est))
                                st.download_button(label="📥 Descargar PDF MSP", data=pdf, file_name=f"HC_{p_info_dict['historia_clinica']}_{fecha_str.replace('/', '-')}.pdf", mime="application/pdf", key=f"dl_pdf_{s['id']}")
                            with c_s2:
                                if st.button("✏️ Modificar Sesión", key=f"btn_mod_ses_{s['id']}"):
                                    st.session_state[f"edit_ses_{s['id']}"] = True
                                    try:
                                        st.session_state[f"ed_diags_{s['id']}"] = json.loads(s.get('diagnosticos') or "[]")
                                    except Exception:
                                        st.session_state[f"ed_diags_{s['id']}"] = []
                                    try:
                                        st.session_state[f"ed_pruebas_{s['id']}"] = json.loads(s.get('pruebas') or "[]")
                                    except Exception:
                                        st.session_state[f"ed_pruebas_{s['id']}"] = []

                            with c_s3:
                                if st.button("🗑️ Eliminar Sesión", key=f"del_ses_{s['id']}"):
                                    requests.delete(f"{API_URL}/sesiones/{s['id']}", timeout=10, verify=False)
                                    st.success("Sesión eliminada.")
                                    time.sleep(1)
                                    st.rerun()

                            if st.session_state.get(f"edit_ses_{s['id']}", False):
                                st.markdown("---")
                                st.markdown(f"#### ✏️ Modificar Sesión ID: {s['id']}")
                                
                                key_d = f"ed_diags_{s['id']}"
                                key_p = f"ed_pruebas_{s['id']}"
                                if key_d not in st.session_state: st.session_state[key_d] = []
                                if key_p not in st.session_state: st.session_state[key_p] = []

                                col_ed1, col_ed2 = st.columns(2)
                                with col_ed1: efecha = st.text_input("Fecha (DD/MM/AAAA)", value=s['fecha'])
                                with col_ed2: ehora = st.text_input("Hora (HH:MM)", value=s['hora'])

                                em = st.text_area("B. Motivo de Consulta", value=s['motivo_consulta'])
                                etipo = st.selectbox("Tipo Consulta", ["Primera", "Subsecuente"], index=0 if str(s['tipo_consulta']).lower() == 'primera' else 1)
                                eap = st.text_area("C. Antecedentes Personales", value=s.get('antecedentes_personales') or "")
                                eaf = st.text_area("D. Antecedentes Familiares", value=s.get('antecedentes_familiares') or "")
                                epa = st.text_area("E. Problema Actual", value=s['problema_actual'])

                                st.markdown("##### I. DIAGNÓSTICO (CIE-10 / CIE-11)")
                                with st.form(f"form_add_diag_ed_{s['id']}", clear_on_submit=True):
                                    ed_desc = st.text_input("Descripción Diagnóstico")
                                    ed_c10 = st.text_input("CIE-10")
                                    ed_c11 = st.text_input("CIE-11 (Opcional)")
                                    c_p, c_d = st.columns(2)
                                    with c_p: ed_pre = st.checkbox("PRE")
                                    with c_d: ed_def = st.checkbox("DEF")
                                    if st.form_submit_button("➕ Añadir Diagnóstico"):
                                        if ed_desc.strip():
                                            st.session_state[key_d].append({"desc": ed_desc.strip(), "cie10": ed_c10.strip(), "cie11": ed_c11.strip(), "pre": ed_pre, "def": ed_def})
                                            st.rerun()

                                if st.session_state[key_d]:
                                    for idx_d, item_d in enumerate(st.session_state[key_d]):
                                        col_d1, col_d2 = st.columns([4, 1])
                                        with col_d1:
                                            st.markdown(f"- **{item_d.get('desc')}** | CIE-10: `{item_d.get('cie10')}` | PRE: {item_d.get('pre')} | DEF: {item_d.get('def')}")
                                        with col_d2:
                                            if st.button("❌ Quitar", key=f"q_d_{s['id']}_{idx_d}"):
                                                st.session_state[key_d].pop(idx_d)
                                                st.rerun()

                                st.markdown("##### PRUEBAS PSICOLÓGICAS")
                                with st.form(f"form_add_test_ed_{s['id']}", clear_on_submit=True):
                                    et_sel = st.selectbox("Prueba", ["HADM", "Hamilton Depresión", "Hamilton Ansiedad", "MMS", "Reloj", "SPENCE", "OTRA"])
                                    et_punt = st.text_input("Puntaje / Resultado")
                                    if st.form_submit_button("➕ Añadir Prueba"):
                                        if et_punt.strip():
                                            st.session_state[key_p].append({"test": et_sel, "puntaje": et_punt.strip()})
                                            st.rerun()

                                if st.session_state[key_p]:
                                    for idx_p, item_p in enumerate(st.session_state[key_p]):
                                        col_p1, col_p2 = st.columns([4, 1])
                                        with col_p1:
                                            st.markdown(f"- **{item_p.get('test')}**: `{item_p.get('puntaje')}`")
                                        with col_p2:
                                            if st.button("❌ Quitar", key=f"q_p_{s['id']}_{idx_p}"):
                                                st.session_state[key_p].pop(idx_p)
                                                st.rerun()

                                with st.form(f"form_ed_sesion_fields_{s['id']}"):
                                    eplan = st.text_area("J. Plan de Tratamiento", value=s.get('plan_tratamiento') or "")
                                    enotas = st.text_area("Notas de Evolución", value=s.get('notas_evolucion') or "")
                                    eprox = st.text_input("Próxima Cita (DD/MM/AAAA)", value=s.get('proxima_cita') or "")

                                    if st.form_submit_button("💾 Guardar Todos los Cambios de la Sesión"):
                                        payload_ses = {
                                            "fecha": efecha.strip(),
                                            "hora": ehora.strip(),
                                            "tipo_consulta": etipo,
                                            "motivo_consulta": em,
                                            "antecedentes_personales": eap,
                                            "antecedentes_familiares": eaf,
                                            "problema_actual": epa,
                                            "diagnosticos": json.dumps(st.session_state[key_d]),
                                            "pruebas": json.dumps(st.session_state[key_p]),
                                            "plan_tratamiento": eplan,
                                            "notas_evolucion": enotas,
                                            "proxima_cita": eprox.strip()
                                        }
                                        r_up = requests.put(f"{API_URL}/sesiones/{s['id']}", json=payload_ses, timeout=10, verify=False)
                                        if r_up.status_code == 200:
                                            st.session_state[f"edit_ses_{s['id']}"] = False
                                            st.success("¡Sesión actualizada correctamente!")
                                            time.sleep(1)
                                            st.rerun()
                else:
                    st.info("Sin sesiones registradas.")
            else:
                st.warning("No se encontraron pacientes.")

        elif menu == "Configurar Mis Datos":
            st.header("⚙️ Mis Datos Personales e Institucionales")
            with st.form("form_cfg_psi"):
                e_pa = st.text_input("Primer Apellido", value=psi_info_data.get("primer_apellido", ""))
                e_sa = st.text_input("Segundo Apellido", value=str(psi_info_data.get("segundo_apellido", "") or ""))
                e_pn = st.text_input("Primer Nombre", value=psi_info_data.get("primer_nombre", ""))
                e_sn = st.text_input("Segundo Nombre", value=str(psi_info_data.get("segundo_nombre", "") or ""))
                e_ced = st.text_input("Cédula", value=psi_info_data.get("cedula", ""))
                e_email = st.text_input("Correo Electrónico (Para recuperación de contraseña)", value=psi_info_data.get("email", ""))
                e_inst = st.text_input("Institución", value=f_inst)
                e_uni = st.text_input("Unicódigo", value=f_uni)
                e_est = st.text_input("Establecimiento", value=f_est)

                if st.form_submit_button("Guardar Cambios"):
                    err = validar_solo_letras(e_pa, "Primer Apellido") or validar_solo_letras(e_pn, "Primer Nombre") or validar_identificacion(e_ced)
                    if err:
                        st.error(err)
                    else:
                        payload = {
                            "primer_apellido": e_pa.strip(),
                            "segundo_apellido": e_sa.strip() if e_sa else "",
                            "primer_nombre": e_pn.strip(),
                            "segundo_nombre": e_sn.strip() if e_sn else "",
                            "cedula": e_ced.strip(),
                            "email": e_email.strip(),
                            "institucion": e_inst,
                            "unicodigo": e_uni,
                            "establecimiento": e_est
                        }
                        r = requests.put(f"{API_URL}/psicologos/{current_psi_id}", json=payload, timeout=10, verify=False)
                        if r.status_code == 200:
                            st.success("¡Datos actualizados!")
                            time.sleep(1)
                            st.rerun()

        elif menu == "Cambiar Contraseña":
            st.header("🔑 Cambiar Contraseña")
            with st.form("form_pass_psi"):
                p_act = st.text_input("Contraseña Actual", type="password")
                p_nue = st.text_input("Nueva Contraseña", type="password")
                if st.form_submit_button("Actualizar"):
                    if not p_act or not p_nue:
                        st.error("Campos vacíos.")
                    else:
                        payload = {"password_actual": p_act, "password_nueva": encriptar_password(p_nue)}
                        r = requests.put(f"{API_URL}/psicologos/{current_psi_id}/password", json=payload, timeout=10, verify=False)
                        if r.status_code == 200:
                            st.success("¡Contraseña actualizada correctamente!")
                        else:
                            st.error(f"Error: {r.json().get('detail', 'Contraseña actual incorrecta')}")

if __name__ == "__main__":
    ejecutar_sistema()