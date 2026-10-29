import os
import hashlib
from datetime import datetime, date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import libsql_experimental as libsql

app = FastAPI()

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

def obtener_conexion():
    return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)

def encriptar_password(password: str) -> str:
    sal_sistema = "SISTEMA_CLINICO_PSICOLOGIA_EC_2026_SECURE"
    return hashlib.sha256(f"{password}{sal_sistema}".encode('utf-8')).hexdigest()

def inicializar_tablas():
    if not TURSO_URL or not TURSO_TOKEN:
        return

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("""
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
                institucion TEXT,
                unicodigo TEXT,
                establecimiento TEXT,
                estado_licencia TEXT DEFAULT 'activo',
                fecha_expiracion TEXT DEFAULT '2099-12-31',
                limite_pacientes INTEGER DEFAULT 9999
            );
        """)

        cursor.execute("PRAGMA table_info(psicologos);")
        columnas = [row[1] for row in cursor.fetchall()]
        if "estado_licencia" not in columnas:
            cursor.execute("ALTER TABLE psicologos ADD COLUMN estado_licencia TEXT DEFAULT 'activo';")
        if "fecha_expiracion" not in columnas:
            cursor.execute("ALTER TABLE psicologos ADD COLUMN fecha_expiracion TEXT DEFAULT '2099-12-31';")
        if "limite_pacientes" not in columnas:
            cursor.execute("ALTER TABLE psicologos ADD COLUMN limite_pacientes INTEGER DEFAULT 9999;")

        cursor.execute("""
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

        cursor.execute("""
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

        pass_admin_correcta = encriptar_password("admin123")
        cursor.execute("SELECT id FROM psicologos WHERE usuario = 'admin';")
        row_admin = cursor.fetchone()

        if not row_admin:
            cursor.execute("""
                INSERT INTO psicologos 
                (usuario, password, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento, estado_licencia, fecha_expiracion, limite_pacientes) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'activo', '2099-12-31', 9999)
            """, (
                "admin", pass_admin_correcta, "ADMINISTRADOR", "SISTEMA", "ADMIN", "", "0000000000", "admin", "MSP", "0000", "CENTRO SALUD"
            ))

        conn.commit()
    except Exception as e:
        print(f"Error al inicializar DB: {e}")

@app.on_event("startup")
def startup():
    inicializar_tablas()

class LoginData(BaseModel):
    usuario: str
    password: str

@app.post("/login")
def login(data: LoginData):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, password, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, cedula, rol, estado_licencia, fecha_expiracion, limite_pacientes FROM psicologos WHERE usuario = ?;", (data.usuario.strip(),))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")

        db_password = row[2]
        raw_password = data.password.strip()
        hash_password = encriptar_password(raw_password)

        if db_password == hash_password or db_password == raw_password:
            rol = row[8]
            estado = row[9] or "activo"
            expiracion = row[10] or "2099-12-31"
            limite_p = row[11] if row[11] is not None else 9999

            if rol != "admin":
                if estado != "activo":
                    raise HTTPException(status_code=403, detail="Cuenta suspendida.")
                try:
                    fecha_exp_obj = datetime.strptime(expiracion, "%Y-%m-%d").date()
                    if date.today() > fecha_exp_obj:
                        raise HTTPException(status_code=403, detail=f"Licencia vencida el {expiracion}.")
                except ValueError:
                    pass

            return {
                "id": row[0], "usuario": row[1], "primer_apellido": row[3], "segundo_apellido": row[4],
                "primer_nombre": row[5], "segundo_nombre": row[6], "cedula": row[7], "rol": rol,
                "estado_licencia": estado, "fecha_expiracion": expiracion, "limite_pacientes": limite_p
            }
        else:
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/psicologos")
def listar_psicologos():
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento, estado_licencia, fecha_expiracion, limite_pacientes FROM psicologos;")
        rows = cursor.fetchall()
        lista = [{
            "id": r[0], "usuario": r[1], "primer_apellido": r[2], "segundo_apellido": r[3],
            "primer_nombre": r[4], "segundo_nombre": r[5], "cedula": r[6], "rol": r[7],
            "institucion": r[8], "unicodigo": r[9], "establecimiento": r[10],
            "estado_licencia": r[11] or "activo", "fecha_expiracion": r[12] or "2099-12-31",
            "limite_pacientes": r[13] if r[13] is not None else 9999
        } for r in rows]
        return {"psicologos": lista}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/psicologos/{psi_id}")
def obtener_psicologo_por_id(psi_id: int):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento FROM psicologos WHERE id = ?;", (psi_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="No encontrado")
        return {
            "id": r[0], "usuario": r[1], "primer_apellido": r[2], "segundo_apellido": r[3],
            "primer_nombre": r[4], "segundo_nombre": r[5], "cedula": r[6], "rol": r[7],
            "institucion": r[8], "unicodigo": r[9], "establecimiento": r[10]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/psicologos/{psi_id}")
def actualizar_psicologo(psi_id: int, p: dict):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        campos, valores = [], []
        for key in ["usuario", "primer_apellido", "segundo_apellido", "primer_nombre", "segundo_nombre", "cedula", "institucion", "unicodigo", "establecimiento", "estado_licencia", "fecha_expiracion", "limite_pacientes"]:
            if key in p:
                campos.append(f"{key} = ?")
                valores.append(p[key])
        if "password" in p and p["password"]:
            campos.append("password = ?")
            valores.append(p["password"])

        if campos:
            valores.append(psi_id)
            cursor.execute(f"UPDATE psicologos SET {', '.join(campos)} WHERE id = ?;", tuple(valores))
            conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/psicologos/{psi_id}/password")
def cambiar_password(psi_id: int, data: dict):
    try:
        p_act = data.get("password_actual")
        p_nue = data.get("password_nueva")
        
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM psicologos WHERE id = ?;", (psi_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
            
        db_pass = row[0]
        if db_pass == p_act or db_pass == encriptar_password(p_act):
            cursor.execute("UPDATE psicologos SET password = ? WHERE id = ?;", (p_nue, psi_id))
            conn.commit()
            return {"status": "ok", "mensaje": "Contraseña actualizada exitosamente"}
        else:
            raise HTTPException(status_code=400, detail="La contraseña actual no coincide")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pacientes")
def listar_pacientes(psicologo_id: int, filtro: str = ""):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        if filtro and filtro.strip():
            f = f"%{filtro.strip()}%"
            cursor.execute("""
                SELECT id, psicologo_id, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, sexo, edad, historia_clinica, numero_archivo 
                FROM pacientes 
                WHERE psicologo_id = ? AND (primer_apellido LIKE ? OR primer_nombre LIKE ? OR historia_clinica LIKE ? OR numero_archivo LIKE ?);
            """, (psicologo_id, f, f, f, f))
        else:
            cursor.execute("""
                SELECT id, psicologo_id, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, sexo, edad, historia_clinica, numero_archivo 
                FROM pacientes 
                WHERE psicologo_id = ? ORDER BY id DESC;
            """, (psicologo_id,))

        rows = cursor.fetchall()
        lista = [{
            "id": r[0], "psicologo_id": r[1], "primer_apellido": r[2], "segundo_apellido": r[3],
            "primer_nombre": r[4], "segundo_nombre": r[5], "sexo": r[6], "edad": r[7],
            "historia_clinica": r[8], "numero_archivo": r[9]
        } for r in rows]
        return {"pacientes": lista}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pacientes/todos")
def listar_todos_pacientes():
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.primer_apellido, p.segundo_apellido, p.primer_nombre, p.segundo_nombre, p.historia_clinica, p.numero_archivo, psi.usuario as terapeuta
            FROM pacientes p JOIN psicologos psi ON p.psicologo_id = psi.id;
        """)
        rows = cursor.fetchall()
        lista = [{
            "id": r[0], "primer_apellido": r[1], "segundo_apellido": r[2], "primer_nombre": r[3],
            "segundo_nombre": r[4], "historia_clinica": r[5], "numero_archivo": r[6], "terapeuta": r[7]
        } for r in rows]
        return {"pacientes": lista}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pacientes")
def crear_paciente(p: dict):
    try:
        psi_id = p.get("psicologo_id")
        conn = obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("SELECT limite_pacientes, rol FROM psicologos WHERE id = ?;", (psi_id,))
        row_psi = cursor.fetchone()
        if row_psi and row_psi[1] != "admin":
            limite = row_psi[0] if row_psi[0] is not None else 9999
            cursor.execute("SELECT COUNT(*) FROM pacientes WHERE psicologo_id = ?;", (psi_id,))
            conteo = cursor.fetchone()[0]
            if conteo >= limite:
                raise HTTPException(status_code=403, detail=f"Alcanzó el límite de {limite} pacientes de su plan.")

        cursor.execute("""
            INSERT INTO pacientes (psicologo_id, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, sexo, edad, historia_clinica, numero_archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            psi_id, p.get("primer_apellido"), p.get("segundo_apellido", ""), p.get("primer_nombre"),
            p.get("segundo_nombre", ""), p.get("sexo"), p.get("edad"), p.get("historia_clinica"), p.get("numero_archivo")
        ))
        conn.commit()
        return {"status": "ok"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/pacientes/{paciente_id}")
def actualizar_paciente(paciente_id: int, p: dict):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pacientes 
            SET primer_apellido = ?, segundo_apellido = ?, primer_nombre = ?, segundo_nombre = ?, sexo = ?, edad = ?, historia_clinica = ?, numero_archivo = ?
            WHERE id = ?;
        """, (
            p.get("primer_apellido"), p.get("segundo_apellido", ""), p.get("primer_nombre"),
            p.get("segundo_nombre", ""), p.get("sexo"), p.get("edad"), p.get("historia_clinica"),
            p.get("numero_archivo"), paciente_id
        ))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/pacientes/{paciente_id}")
def eliminar_paciente(paciente_id: int):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sesiones WHERE paciente_id = ?;", (paciente_id,))
        cursor.execute("DELETE FROM pacientes WHERE id = ?;", (paciente_id,))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# LISTAR SESIONES ORDENADAS DESDE LA ÚLTIMA A LA MÁS ANTIGUA (ORDER BY id DESC)
@app.get("/sesiones")
def listar_sesiones(paciente_id: int):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, paciente_id, psicologo_id, fecha, hora, tipo_consulta, motivo_consulta, antecedentes_personales, antecedentes_familiares, problema_actual, diagnosticos, pruebas, plan_tratamiento, notas_evolucion, proxima_cita 
            FROM sesiones 
            WHERE paciente_id = ? ORDER BY id DESC;
        """, (paciente_id,))
        rows = cursor.fetchall()
        lista = [{
            "id": r[0], "paciente_id": r[1], "psicologo_id": r[2], "fecha": r[3], "hora": r[4],
            "tipo_consulta": r[5], "motivo_consulta": r[6], "antecedentes_personales": r[7],
            "antecedentes_familiares": r[8], "problema_actual": r[9], "diagnosticos": r[10],
            "pruebas": r[11], "plan_tratamiento": r[12], "notas_evolucion": r[13], "proxima_cita": r[14]
        } for r in rows]
        return {"sesiones": lista}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sesiones")
def crear_sesion(s: dict):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sesiones (paciente_id, psicologo_id, fecha, hora, tipo_consulta, motivo_consulta, antecedentes_personales, antecedentes_familiares, problema_actual, diagnosticos, pruebas, plan_tratamiento, notas_evolucion, proxima_cita)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s.get("paciente_id"), s.get("psicologo_id"), s.get("fecha"), s.get("hora"),
            s.get("tipo_consulta"), s.get("motivo_consulta"), s.get("antecedentes_personales", ""),
            s.get("antecedentes_familiares", ""), s.get("problema_actual"), s.get("diagnosticos", "[]"),
            s.get("pruebas", "[]"), s.get("plan_tratamiento", ""), s.get("notas_evolucion", ""),
            s.get("proxima_cita", "")
        ))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/sesiones/{sesion_id}")
def actualizar_sesion(sesion_id: int, s: dict):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sesiones 
            SET fecha = ?, hora = ?, tipo_consulta = ?, motivo_consulta = ?, antecedentes_personales = ?, antecedentes_familiares = ?, problema_actual = ?, diagnosticos = ?, pruebas = ?, plan_tratamiento = ?, notas_evolucion = ?, proxima_cita = ?
            WHERE id = ?;
        """, (
            s.get("fecha"), s.get("hora"), s.get("tipo_consulta"), s.get("motivo_consulta"),
            s.get("antecedentes_personales", ""), s.get("antecedentes_familiares", ""),
            s.get("problema_actual"), s.get("diagnosticos", "[]"), s.get("pruebas", "[]"),
            s.get("plan_tratamiento", ""), s.get("notas_evolucion", ""), s.get("proxima_cita", ""),
            sesion_id
        ))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/sesiones/{sesion_id}")
def eliminar_sesion(sesion_id: int):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sesiones WHERE id = ?;", (sesion_id,))
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
def root():
    return {"status": "ok", "mensaje": "API de Psicología operando"}