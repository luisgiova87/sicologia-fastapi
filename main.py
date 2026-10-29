import hashlib
import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import libsql_client
from pydantic import BaseModel

app = FastAPI(title="API Sistema Clínico de Psicología")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN DE CONEXIÓN A TURSO DB ---
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").replace("https://", "libsql://")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

# Configuración SMTP (Gmail)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")


def obtener_conexion():
  if not TURSO_URL or not TURSO_TOKEN:
    raise HTTPException(
        status_code=500,
        detail=(
            "[ERR_TURSO_00] Variables de entorno TURSO_DATABASE_URL o"
            " TURSO_AUTH_TOKEN vacías en Vercel."
        ),
    )
  try:
    return libsql_client.create_client_sync(
        url=TURSO_URL, auth_token=TURSO_TOKEN
    )
  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"[ERR_TURSO_CONN] Fallo conexion Turso: {e}"
    )


def encriptar_password(password: str) -> str:
  sal_sistema = "SISTEMA_CLINICO_PSICOLOGIA_EC_2026_SECURE"
  return hashlib.sha256(f"{password}{sal_sistema}".encode("utf-8")).hexdigest()


def enviar_correo_codigo(correo_destino: str, codigo: str):
  if not SMTP_USER or not SMTP_PASS:
    print(
        f"⚠️ [SMTP_INFO] Código generado para {correo_destino}: {codigo} (SMTP"
        " no configurado)"
    )
    return

  asunto = "Código de Recuperación de Contraseña - Sistema Clínico"
  cuerpo = f"Hola,\n\nTu código de seguridad es: {codigo}\n\nVence en 15 minutos."
  msg = MIMEText(cuerpo, "plain", "utf-8")
  msg["Subject"] = asunto
  msg["From"] = f"Sistema Clínico <{SMTP_USER}>"
  msg["To"] = correo_destino

  try:
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=8) as server:
      server.login(SMTP_USER, SMTP_PASS)
      server.sendmail(SMTP_USER, [correo_destino], msg.as_string())
  except Exception as e:
    print(f"⚠️ [SMTP_ERROR] Error enviando correo: {e}")


# --- MODELOS ---
class LoginRequest(BaseModel):
  usuario: str
  password: str


class PsicologoCreate(BaseModel):
  usuario: str
  password: str
  primer_apellido: str
  segundo_apellido: Optional[str] = ""
  primer_nombre: str
  segundo_nombre: Optional[str] = ""
  cedula: str
  rol: Optional[str] = "psicologo"
  institucion: Optional[str] = "MSP"
  unicodigo: Optional[str] = "0000"
  establecimiento: Optional[str] = "CENTRO SALUD"
  email: Optional[str] = ""
  estado_licencia: Optional[str] = "activo"
  fecha_expiracion: Optional[str] = "2026-12-31"
  limite_pacientes: Optional[int] = 100


class PsicologoUpdate(BaseModel):
  primer_apellido: Optional[str] = None
  segundo_apellido: Optional[str] = None
  primer_nombre: Optional[str] = None
  segundo_nombre: Optional[str] = None
  cedula: Optional[str] = None
  institucion: Optional[str] = None
  unicodigo: Optional[str] = None
  establecimiento: Optional[str] = None
  email: Optional[str] = None
  estado_licencia: Optional[str] = None
  fecha_expiracion: Optional[str] = None
  limite_pacientes: Optional[int] = None


class PasswordChange(BaseModel):
  password_actual: str
  password_nueva: str


class SolicitarRecuperacionRequest(BaseModel):
  usuario_o_email: str


class RestablecerPasswordRequest(BaseModel):
  usuario: str
  codigo: str
  nueva_password: str


class PacienteCreate(BaseModel):
  psicologo_id: int
  primer_apellido: str
  segundo_apellido: Optional[str] = ""
  primer_nombre: str
  segundo_nombre: Optional[str] = ""
  sexo: str
  edad: int
  historia_clinica: str
  numero_archivo: str


class SesionCreate(BaseModel):
  paciente_id: int
  psicologo_id: int
  fecha: str
  hora: str
  tipo_consulta: str
  motivo_consulta: str
  antecedentes_personales: Optional[str] = ""
  antecedentes_familiares: Optional[str] = ""
  problema_actual: str
  diagnosticos: Optional[str] = "[]"
  pruebas: Optional[str] = "[]"
  plan_tratamiento: Optional[str] = ""
  notas_evolucion: Optional[str] = ""
  proxima_cita: Optional[str] = ""


# --- RUTAS DE INICIALIZACIÓN ---
@app.get("/")
def home():
  return {"status": "ok", "mensaje": "API del Sistema Clínico Activa"}


@app.get("/api/init-db")
def inicializar_tablas():
  try:
    client = obtener_conexion()

    client.execute("""
        CREATE TABLE IF NOT EXISTS psicologos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            primer_apellido TEXT NOT NULL,
            segundo_apellido TEXT,
            primer_nombre TEXT NOT NULL,
            segundo_nombre TEXT,
            cedula TEXT UNIQUE NOT NULL,
            rol TEXT DEFAULT 'psicologo',
            institucion TEXT DEFAULT 'MSP',
            unicodigo TEXT DEFAULT '0000',
            establecimiento TEXT DEFAULT 'CENTRO SALUD',
            email TEXT DEFAULT '',
            estado_licencia TEXT DEFAULT 'activo',
            fecha_expiracion TEXT DEFAULT '2026-12-31',
            limite_pacientes INTEGER DEFAULT 100
        );
        """)

    client.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            psicologo_id INTEGER NOT NULL,
            primer_apellido TEXT NOT NULL,
            segundo_apellido TEXT,
            primer_nombre TEXT NOT NULL,
            segundo_nombre TEXT,
            sexo TEXT NOT NULL,
            edad INTEGER NOT NULL,
            historia_clinica TEXT NOT NULL,
            numero_archivo TEXT NOT NULL,
            FOREIGN KEY (psicologo_id) REFERENCES psicologos(id)
        );
        """)

    client.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER NOT NULL,
            psicologo_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            tipo_consulta TEXT NOT NULL,
            motivo_consulta TEXT NOT NULL,
            antecedentes_personales TEXT,
            antecedentes_familiares TEXT,
            problema_actual TEXT NOT NULL,
            diagnosticos TEXT,
            pruebas TEXT,
            plan_tratamiento TEXT,
            notas_evolucion TEXT,
            proxima_cita TEXT,
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
            FOREIGN KEY (psicologo_id) REFERENCES psicologos(id)
        );
        """)

    client.execute("""
        CREATE TABLE IF NOT EXISTS codigos_recuperacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            codigo TEXT NOT NULL,
            expiracion TEXT NOT NULL
        );
        """)

    res = client.execute("SELECT COUNT(*) FROM psicologos WHERE usuario = 'admin';")
    if res.rows[0][0] == 0:
      pass_hash = encriptar_password("admin123")
      client.execute(
          """
            INSERT INTO psicologos 
            (usuario, password, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento, email, estado_licencia, fecha_expiracion, limite_pacientes)
            VALUES ('admin', ?, 'ADMINISTRADOR', 'SISTEMA', 'ADMIN', '', '0000000000', 'admin', 'MSP', '0000', 'CENTRO SALUD', 'admin@sistema.ec', 'activo', '2099-12-31', 9999);
            """,
          [pass_hash],
      )

    return {
        "status": "ok",
        "mensaje": "Base de datos y usuario admin inicializados correctamente",
    }
  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"[ERR_INIT_DB] Error al inicializar: {str(e)}"
    )


# --- LOGIN CON IDENTIFICADOR DE ERRORES ---
@app.post("/login")
def login(req: LoginRequest):
  usuario_limpio = req.usuario.strip()
  pass_enviada = req.password.strip()
  pass_hash = encriptar_password(pass_enviada)
  pass_admin_esperada = encriptar_password("admin123")

  # 1. BYPASS DIRECTO DE EMERGENCIA PARA USUARIO ADMIN
  if usuario_limpio == "admin":
    if pass_enviada in ["admin123", pass_admin_esperada]:
      try:
        client = obtener_conexion()
        res_adm = client.execute(
            "SELECT id, usuario, primer_apellido, segundo_apellido,"
            " primer_nombre, rol, estado_licencia, fecha_expiracion,"
            " limite_pacientes, email FROM psicologos WHERE usuario = 'admin';"
        )
        if res_adm.rows:
          r = res_adm.rows[0]
          return {
              "id": r[0],
              "usuario": r[1],
              "primer_apellido": r[2],
              "segundo_apellido": r[3],
              "primer_nombre": r[4],
              "rol": r[5],
              "estado_licencia": r[6],
              "fecha_expiracion": r[7],
              "limite_pacientes": r[8],
              "email": r[9],
          }
      except Exception:
        pass  # Si falla la consulta a Turso, de todos modos responde con datos admin por defecto

      return {
          "id": 1,
          "usuario": "admin",
          "primer_apellido": "ADMINISTRADOR",
          "segundo_apellido": "SISTEMA",
          "primer_nombre": "ADMIN",
          "rol": "admin",
          "estado_licencia": "activo",
          "fecha_expiracion": "2099-12-31",
          "limite_pacientes": 9999,
          "email": "admin@sistema.ec",
      }

  # 2. BÚSQUEDA REGULAR CON IDENTIFICADOR DE ERRORES
  try:
    client = obtener_conexion()
    res = client.execute(
        "SELECT id, usuario, primer_apellido, segundo_apellido, primer_nombre,"
        " rol, estado_licencia, fecha_expiracion, limite_pacientes, email,"
        " password FROM psicologos WHERE usuario = ?;",
        [usuario_limpio],
    )
  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"[ERR_LOGIN_QUERY] Error consultando Turso: {e}"
    )

  if not res.rows:
    raise HTTPException(
        status_code=401,
        detail=f"[ERR_LOGIN_01] El usuario '{usuario_limpio}' no existe.",
    )

  r = res.rows[0]
  db_password = r[10]

  # Verificar hash o texto plano
  if db_password == pass_hash or db_password == pass_enviada:
    return {
        "id": r[0],
        "usuario": r[1],
        "primer_apellido": r[2],
        "segundo_apellido": r[3],
        "primer_nombre": r[4],
        "rol": r[5],
        "estado_licencia": r[6],
        "fecha_expiracion": r[7],
        "limite_pacientes": r[8],
        "email": r[9],
    }
  else:
    raise HTTPException(
        status_code=401,
        detail=(
            f"[ERR_LOGIN_02] Contraseña incorrecta para '{usuario_limpio}'."
            f" HashRecibido={pass_hash[:8]}... vs HashDB={db_password[:8]}..."
        ),
    )


# --- OTROS ENDPOINTS ---
@app.post("/solicitar-recuperacion")
def solicitar_recuperacion(req: SolicitarRecuperacionRequest):
  client = obtener_conexion()
  res = client.execute(
      "SELECT usuario, email FROM psicologos WHERE usuario = ? OR email = ?;",
      [req.usuario_o_email, req.usuario_o_email],
  )
  if not res.rows:
    raise HTTPException(
        status_code=404,
        detail="[ERR_RECUP_01] Usuario o correo electrónico no encontrado",
    )

  usuario, email = res.rows[0][0], res.rows[0][1]
  if not email:
    raise HTTPException(
        status_code=400,
        detail="[ERR_RECUP_02] El usuario no tiene correo registrado",
    )

  codigo = str(random.randint(100000, 999999))
  expiracion = (datetime.now() + timedelta(minutes=15)).strftime(
      "%Y-%m-%d %H:%M:%S"
  )

  client.execute(
      "INSERT INTO codigos_recuperacion (usuario, codigo, expiracion) VALUES"
      " (?, ?, ?);",
      [usuario, codigo, expiracion],
  )

  enviar_correo_codigo(email, codigo)
  return {"status": "ok", "mensaje": "Código enviado al correo registrado"}


@app.post("/restablecer-password")
def restablecer_password(req: RestablecerPasswordRequest):
  client = obtener_conexion()
  ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  res = client.execute(
      "SELECT id FROM codigos_recuperacion WHERE usuario = ? AND codigo = ? AND"
      " expiracion >= ? ORDER BY id DESC LIMIT 1;",
      [req.usuario, req.codigo, ahora],
  )
  if not res.rows:
    raise HTTPException(
        status_code=400, detail="[ERR_RESET_01] Código inválido o expirado"
    )

  nueva_pass_hash = encriptar_password(req.nueva_password)
  client.execute(
      "UPDATE psicologos SET password = ? WHERE usuario = ?;",
      [nueva_pass_hash, req.usuario],
  )
  client.execute(
      "DELETE FROM codigos_recuperacion WHERE usuario = ?;", [req.usuario]
  )

  return {"status": "ok", "mensaje": "Contraseña restablecida con éxito"}


@app.get("/api/rescue-admin")
def rescue_admin(clave_secreta: str):
  if clave_secreta != "MI_CLAVE_DE_RESCATE_2026":
    raise HTTPException(
        status_code=403, detail="[ERR_RESCUE] Clave de rescate incorrecta"
    )

  client = obtener_conexion()
  nueva_pass_hash = encriptar_password("admin123")
  client.execute(
      "UPDATE psicologos SET password = ? WHERE usuario = 'admin';",
      [nueva_pass_hash],
  )
  return {
      "status": "ok",
      "mensaje": "Contraseña de admin restablecida a 'admin123' exitosamente",
  }


@app.get("/psicologos")
def listar_psicologos():
  client = obtener_conexion()
  res = client.execute(
      "SELECT id, usuario, primer_apellido, segundo_apellido, primer_nombre,"
      " segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento,"
      " email, estado_licencia, fecha_expiracion, limite_pacientes FROM"
      " psicologos;"
  )
  columnas = [
      "id",
      "usuario",
      "primer_apellido",
      "segundo_apellido",
      "primer_nombre",
      "segundo_nombre",
      "cedula",
      "rol",
      "institucion",
      "unicodigo",
      "establecimiento",
      "email",
      "estado_licencia",
      "fecha_expiracion",
      "limite_pacientes",
  ]
  return {"psicologos": [dict(zip(columnas, row)) for row in res.rows]}


@app.get("/psicologos/{psi_id}")
def obtener_psicologo(psi_id: int):
  client = obtener_conexion()
  res = client.execute(
      "SELECT id, usuario, primer_apellido, segundo_apellido, primer_nombre,"
      " segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento,"
      " email, estado_licencia, fecha_expiracion, limite_pacientes FROM"
      " psicologos WHERE id = ?;",
      [psi_id],
  )
  if not res.rows:
    raise HTTPException(status_code=404, detail="Psicólogo no encontrado")
  columnas = [
      "id",
      "usuario",
      "primer_apellido",
      "segundo_apellido",
      "primer_nombre",
      "segundo_nombre",
      "cedula",
      "rol",
      "institucion",
      "unicodigo",
      "establecimiento",
      "email",
      "estado_licencia",
      "fecha_expiracion",
      "limite_pacientes",
  ]
  return dict(zip(columnas, res.rows[0]))


@app.post("/psicologos")
def crear_psicologo(data: PsicologoCreate):
  client = obtener_conexion()
  pass_hash = encriptar_password(data.password)
  try:
    client.execute(
        """
        INSERT INTO psicologos 
        (usuario, password, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento, email, estado_licencia, fecha_expiracion, limite_pacientes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        [
            data.usuario,
            pass_hash,
            data.primer_apellido,
            data.segundo_apellido,
            data.primer_nombre,
            data.segundo_nombre,
            data.cedula,
            data.rol,
            data.institucion,
            data.unicodigo,
            data.establecimiento,
            data.email,
            data.estado_licencia,
            data.fecha_expiracion,
            data.limite_pacientes,
        ],
    )
    return {"status": "ok", "mensaje": "Terapeuta creado exitosamente"}
  except Exception as e:
    raise HTTPException(
        status_code=400, detail=f"Error al crear terapeuta: {str(e)}"
    )


@app.put("/psicologos/{psi_id}")
def actualizar_psicologo(psi_id: int, data: PsicologoUpdate):
  client = obtener_conexion()
  campos = []
  valores = []
  for key, val in data.dict(exclude_unset=True).items():
    if val is not None:
      campos.append(f"{key} = ?")
      valores.append(val)
  if not campos:
    return {"mensaje": "Sin cambios"}
  valores.append(psi_id)
  query = f"UPDATE psicologos SET {', '.join(campos)} WHERE id = ?;"
  client.execute(query, valores)
  return {"status": "ok", "mensaje": "Terapeuta actualizado correctamente"}


@app.put("/psicologos/{psi_id}/password")
def cambiar_password(psi_id: int, data: PasswordChange):
  client = obtener_conexion()
  pass_act_hash = encriptar_password(data.password_actual)
  res = client.execute(
      "SELECT id FROM psicologos WHERE id = ? AND password = ?;",
      [psi_id, pass_act_hash],
  )
  if not res.rows:
    raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

  client.execute(
      "UPDATE psicologos SET password = ? WHERE id = ?;",
      [data.password_nueva, psi_id],
  )
  return {"status": "ok", "mensaje": "Contraseña actualizada exitosamente"}


@app.get("/pacientes/todos")
def listar_todos_pacientes():
  client = obtener_conexion()
  res = client.execute(
      "SELECT id, psicologo_id, primer_apellido, segundo_apellido,"
      " primer_nombre, segundo_nombre, sexo, edad, historia_clinica,"
      " numero_archivo FROM pacientes;"
  )
  columnas = [
      "id",
      "psicologo_id",
      "primer_apellido",
      "segundo_apellido",
      "primer_nombre",
      "segundo_nombre",
      "sexo",
      "edad",
      "historia_clinica",
      "numero_archivo",
  ]
  return {"pacientes": [dict(zip(columnas, row)) for row in res.rows]}


@app.get("/pacientes")
def listar_pacientes_terapeuta(psicologo_id: int, filtro: Optional[str] = None):
  client = obtener_conexion()
  if filtro and filtro.strip():
    f = f"%{filtro.strip()}%"
    res = client.execute(
        "SELECT id, psicologo_id, primer_apellido, segundo_apellido,"
        " primer_nombre, segundo_nombre, sexo, edad, historia_clinica,"
        " numero_archivo FROM pacientes WHERE psicologo_id = ? AND"
        " (primer_apellido LIKE ? OR primer_nombre LIKE ? OR historia_clinica"
        " LIKE ? OR numero_archivo LIKE ?) ORDER BY id DESC;",
        [psicologo_id, f, f, f, f],
    )
  else:
    res = client.execute(
        "SELECT id, psicologo_id, primer_apellido, segundo_apellido,"
        " primer_nombre, segundo_nombre, sexo, edad, historia_clinica,"
        " numero_archivo FROM pacientes WHERE psicologo_id = ? ORDER BY id"
        " DESC;",
        [psicologo_id],
    )
  columnas = [
      "id",
      "psicologo_id",
      "primer_apellido",
      "segundo_apellido",
      "primer_nombre",
      "segundo_nombre",
      "sexo",
      "edad",
      "historia_clinica",
      "numero_archivo",
  ]
  return {"pacientes": [dict(zip(columnas, row)) for row in res.rows]}


@app.post("/pacientes")
def crear_paciente(data: PacienteCreate):
  client = obtener_conexion()
  res_psi = client.execute(
      "SELECT limite_pacientes FROM psicologos WHERE id = ?;",
      [data.psicologo_id],
  )
  if res_psi.rows:
    limite = res_psi.rows[0][0] or 100
    res_p = client.execute(
        "SELECT COUNT(*) FROM pacientes WHERE psicologo_id = ?;",
        [data.psicologo_id],
    )
    if res_p.rows[0][0] >= limite:
      raise HTTPException(
          status_code=403,
          detail=f"Ha alcanzado el límite permitido de {limite} pacientes.",
      )

  client.execute(
      """
    INSERT INTO pacientes (psicologo_id, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, sexo, edad, historia_clinica, numero_archivo)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """,
      [
          data.psicologo_id,
          data.primer_apellido,
          data.segundo_apellido,
          data.primer_nombre,
          data.segundo_nombre,
          data.sexo,
          data.edad,
          data.historia_clinica,
          data.numero_archivo,
      ],
  )
  return {"status": "ok", "mensaje": "Paciente registrado exitosamente"}


@app.put("/pacientes/{pac_id}")
def actualizar_paciente(pac_id: int, data: PacienteCreate):
  client = obtener_conexion()
  client.execute(
      """
    UPDATE pacientes SET primer_apellido = ?, segundo_apellido = ?, primer_nombre = ?, segundo_nombre = ?, sexo = ?, edad = ?, historia_clinica = ?, numero_archivo = ?
    WHERE id = ?;
    """,
      [
          data.primer_apellido,
          data.segundo_apellido,
          data.primer_nombre,
          data.segundo_nombre,
          data.sexo,
          data.edad,
          data.historia_clinica,
          data.numero_archivo,
          pac_id,
      ],
  )
  return {"status": "ok", "mensaje": "Paciente actualizado correctamente"}


@app.delete("/pacientes/{pac_id}")
def eliminar_paciente(pac_id: int):
  client = obtener_conexion()
  client.execute("DELETE FROM sesiones WHERE paciente_id = ?;", [pac_id])
  client.execute("DELETE FROM pacientes WHERE id = ?;", [pac_id])
  return {"status": "ok", "mensaje": "Paciente y sus sesiones eliminados"}


@app.get("/sesiones")
def listar_sesiones(paciente_id: int):
  client = obtener_conexion()
  res = client.execute(
      "SELECT id, paciente_id, psicologo_id, fecha, hora, tipo_consulta,"
      " motivo_consulta, antecedentes_personales, antecedentes_familiares,"
      " problema_actual, diagnosticos, pruebas, plan_tratamiento,"
      " notas_evolucion, proxima_cita FROM sesiones WHERE paciente_id = ?"
      " ORDER BY id DESC;",
      [paciente_id],
  )
  columnas = [
      "id",
      "paciente_id",
      "psicologo_id",
      "fecha",
      "hora",
      "tipo_consulta",
      "motivo_consulta",
      "antecedentes_personales",
      "antecedentes_familiares",
      "problema_actual",
      "diagnosticos",
      "pruebas",
      "plan_tratamiento",
      "notas_evolucion",
      "proxima_cita",
  ]
  return {"sesiones": [dict(zip(columnas, row)) for row in res.rows]}


@app.post("/sesiones")
def crear_sesion(data: SesionCreate):
  client = obtener_conexion()
  client.execute(
      """
    INSERT INTO sesiones 
    (paciente_id, psicologo_id, fecha, hora, tipo_consulta, motivo_consulta, antecedentes_personales, antecedentes_familiares, problema_actual, diagnosticos, pruebas, plan_tratamiento, notas_evolucion, proxima_cita)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """,
      [
          data.paciente_id,
          data.psicologo_id,
          data.fecha,
          data.hora,
          data.tipo_consulta,
          data.motivo_consulta,
          data.antecedentes_personales,
          data.antecedentes_familiares,
          data.problema_actual,
          data.diagnosticos,
          data.pruebas,
          data.plan_tratamiento,
          data.notas_evolucion,
          data.proxima_cita,
      ],
  )
  return {"status": "ok", "mensaje": "Sesión registrada correctamente"}


@app.put("/sesiones/{ses_id}")
def actualizar_sesion(ses_id: int, data: SesionCreate):
  client = obtener_conexion()
  client.execute(
      """
    UPDATE sesiones SET fecha = ?, hora = ?, tipo_consulta = ?, motivo_consulta = ?, antecedentes_personales = ?, antecedentes_familiares = ?, problema_actual = ?, diagnosticos = ?, pruebas = ?, plan_tratamiento = ?, notas_evolucion = ?, proxima_cita = ?
    WHERE id = ?;
    """,
      [
          data.fecha,
          data.hora,
          data.tipo_consulta,
          data.motivo_consulta,
          data.antecedentes_personales,
          data.antecedentes_familiares,
          data.problema_actual,
          data.diagnosticos,
          data.pruebas,
          data.plan_tratamiento,
          data.notas_evolucion,
          data.proxima_cita,
          ses_id,
      ],
  )
  return {"status": "ok", "mensaje": "Sesión actualizada correctamente"}


@app.delete("/sesiones/{ses_id}")
def eliminar_sesion(ses_id: int):
  client = obtener_conexion()
  client.execute("DELETE FROM sesiones WHERE id = ?;", [ses_id])
  return {"status": "ok", "mensaje": "Sesión eliminada"}