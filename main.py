import os
import hashlib
from fastapi import FastAPI
import libsql_experimental as libsql

app = FastAPI()

# Obtener variables de entorno configuradas en Vercel / Render
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

def obtener_conexion():
    """Crea la conexión remota con Turso DB usando el cliente de Python."""
    return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)

def encriptar_password(password: str) -> str:
    sal_sistema = "SISTEMA_CLINICO_PSICOLOGIA_EC_2026_SECURE"
    return hashlib.sha256(f"{password}{sal_sistema}".encode('utf-8')).hexdigest()

@app.on_event("startup")
def inicializar_base_datos():
    """Se ejecuta automáticamente al iniciar la API en Python."""
    if not TURSO_URL or not TURSO_TOKEN:
        print("⚠️ Advertencia: Variables de Turso no configuradas.")
        return

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        # 1. Crear Tabla Psicologos
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
                establecimiento TEXT
            );
        """)

        # 2. Crear Tabla Pacientes
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

        # 3. Crear Tabla Sesiones
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

        # 4. Crear Usuario Admin Inicial si no existen registros
        cursor.execute("SELECT COUNT(*) FROM psicologos;")
        total = cursor.fetchone()[0]

        if total == 0:
            pass_admin_hash = encriptar_password("admin123")
            cursor.execute("""
                INSERT INTO psicologos 
                (usuario, password, primer_apellido, segundo_apellido, primer_nombre, segundo_nombre, cedula, rol, institucion, unicodigo, establecimiento) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "admin",
                pass_admin_hash,
                "ADMINISTRADOR",
                "SISTEMA",
                "ADMIN",
                "",
                "0000000000",
                "admin",
                "MSP",
                "0000",
                "CENTRO SALUD"
            ))

        conn.commit()
        conn.close()
        print("✅ Base de datos inicializada correctamente en Turso DB.")
    except Exception as e:
        print(f"❌ Error al auto-inicializar Turso DB: {e}")

@app.get("/")
def root():
    return {"status": "ok", "mensaje": "API Python corriendo y conectada a Turso DB"}