# app.py - Aplicación Principal del ERP
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import pyodbc
from datetime import datetime, date
import hashlib
import requests
import json
from functools import wraps
from flask_moment import Moment


# Rutas actualizadas para Facebook Marketing - Agregar al app.py existente

# Importar las funciones de Facebook al inicio del archivo
from facebook_config import (
    FacebookMarketingAPI, 
    init_facebook_marketing, 
    crear_campania_facebook_completa,
    sincronizar_estadisticas_facebook,
    procesar_webhook_facebook
)


app = Flask(__name__)
app.secret_key = 'OSX?$X]&r_7zH"F^~Tyx6aCel_9#/qbss}?~V@;6F<po!vxnC%Tc$Jz_9Z2kIS'
moment = Moment(app)

# Configuración de la base de datos
DB_CONFIG = {
    'server': 'DRAK3',
    'database': 'ERP_Database',
    'username': 'Prueba',
    'password': 'j12345m6789d'
}

def get_db_connection():
    """Obtiene conexión a la base de datos SQL Server"""
    try:
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_CONFIG['server']};DATABASE={DB_CONFIG['database']};UID={DB_CONFIG['username']};PWD={DB_CONFIG['password']}"
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return None

def login_required(f):
    """Decorador para rutas que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Primera opción: Si las contraseñas están en texto plano (para pruebas)
            cursor.execute("SELECT id, nombre, email, rol FROM usuarios WHERE email = ? AND password = ?", 
                         (email, password))
            user = cursor.fetchone()
            
            # Segunda opción: Si usas SHA-256 (descomenta esta sección si es necesario)
            # import hashlib
            # hashed_password = hashlib.sha256(password.encode()).hexdigest()
            # cursor.execute("SELECT id, nombre, email, rol FROM usuarios WHERE email = ? AND password = ?", 
            #              (email, hashed_password))
            # user = cursor.fetchone()
            
            if user:
                session['user_id'] = user[0]  # ID como string
                session['user_name'] = user[1]
                session['user_email'] = user[2]
                session['user_role'] = user[3]  # Agregamos el rol
                flash('Inicio de sesión exitoso', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Credenciales inválidas', 'error')
            
            conn.close()
    
    return render_template('login.html')

# También necesitas modificar el decorador para usar string IDs
def login_required(f):
    """Decorador para rutas que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Función adicional para verificar roles (opcional)
def role_required(required_role):
    """Decorador para rutas que requieren un rol específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('user_role') != required_role and session.get('user_role') != 'administrador':
                flash('No tienes permisos para acceder a esta página', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    stats = {}
    
    if conn:
        cursor = conn.cursor()
        
        # Estadísticas generales
        cursor.execute("SELECT COUNT(*) FROM clientes")
        stats['total_clientes'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM facturas WHERE MONTH(fecha) = MONTH(GETDATE())")
        stats['facturas_mes'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(total) FROM facturas WHERE MONTH(fecha) = MONTH(GETDATE())")
        result = cursor.fetchone()[0]
        stats['ventas_mes'] = result if result else 0
        
        cursor.execute("SELECT COUNT(*) FROM empleados WHERE activo = 1")
        stats['empleados_activos'] = cursor.fetchone()[0]
        
        # Facturas recientes
        cursor.execute("""
            SELECT TOP 5 f.numero, c.nombre, f.fecha, f.total 
            FROM facturas f 
            JOIN clientes c ON f.cliente_id = c.id 
            ORDER BY f.fecha DESC
        """)
        stats['facturas_recientes'] = cursor.fetchall()
        
        conn.close()
    
    return render_template('dashboard.html', stats=stats)

# ==================== GESTIÓN DE CLIENTES ====================

@app.route('/clientes')
@login_required
def clientes():
    conn = get_db_connection()
    clientes_list = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, email, telefono, direccion, fecha_registro 
            FROM clientes ORDER BY nombre
        """)
        clientes_list = cursor.fetchall()
        conn.close()
    
    return render_template('clientes.html', clientes=clientes_list)

@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        id = request.form['id']
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        direccion = request.form['direccion']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clientes (id, nombre, email, telefono, direccion, fecha_registro)
                VALUES (?, ?, ?, ?, ?, GETDATE())
            """, (nombre, email, telefono, direccion))
            conn.commit()
            conn.close()
            
            flash('Cliente creado exitosamente', 'success')
            return redirect(url_for('clientes'))
    
    return render_template('cliente_form.html')

@app.route('/clientes/<cliente_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_id):
    conn = get_db_connection()
    cliente = None
    
    if conn:
        cursor = conn.cursor()
        
        if request.method == 'POST':
            nombre = request.form['nombre']
            email = request.form['email']
            telefono = request.form['telefono']
            direccion = request.form['direccion']
            
            cursor.execute("""
                UPDATE clientes 
                SET nombre = ?, email = ?, telefono = ?, direccion = ?
                WHERE id = ?
            """, (nombre, email, telefono, direccion, cliente_id))
            conn.commit()
            conn.close()
            
            flash('Cliente actualizado exitosamente', 'success')
            return redirect(url_for('clientes'))
        
        cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
        cliente = cursor.fetchone()
        conn.close()
    
    return render_template('cliente_form.html', cliente=cliente)

# ==================== GESTIÓN DE FACTURAS ====================

@app.route('/facturas')
@login_required
def facturas():
    conn = get_db_connection()
    facturas_list = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.numero, c.nombre, f.fecha, f.total, f.estado
            FROM facturas f
            JOIN clientes c ON f.cliente_id = c.id
            ORDER BY f.fecha DESC
        """)
        facturas_list = cursor.fetchall()
        conn.close()
    
    return render_template('facturas.html', facturas=facturas_list)

@app.route('/facturas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_factura():
    conn = get_db_connection()
    clientes_list = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM clientes ORDER BY nombre")
        clientes_list = cursor.fetchall()
        
        if request.method == 'POST':
            cliente_id = request.form['cliente_id']
            items = request.form.getlist('item[]')
            cantidades = request.form.getlist('cantidad[]')
            precios = request.form.getlist('precio[]')
            
            # Generar número de factura
            cursor.execute("SELECT MAX(numero) FROM facturas")
            last_number = cursor.fetchone()[0]
            nuevo_numero = (last_number + 1) if last_number else 1
            
            # Calcular total
            total = sum(float(cantidad) * float(precio) for cantidad, precio in zip(cantidades, precios))
            
            # Insertar factura
            cursor.execute("""
                INSERT INTO facturas (numero, cliente_id, fecha, total, estado, usuario_id)
                VALUES (?, ?, GETDATE(), ?, 'pendiente', ?)
            """, (nuevo_numero, cliente_id, total, session['user_id']))
            
            factura_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
            
            # Insertar detalles de factura
            for item, cantidad, precio in zip(items, cantidades, precios):
                if item and cantidad and precio:
                    cursor.execute("""
                        INSERT INTO factura_detalles (factura_id, descripcion, cantidad, precio_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (factura_id, item, cantidad, precio, float(cantidad) * float(precio)))
            
            conn.commit()
            conn.close()
            
            flash('Factura creada exitosamente', 'success')
            return redirect(url_for('facturas'))
        
        conn.close()
    
    return render_template('factura_form.html', clientes=clientes_list, date=date)

# ==================== GESTIÓN DE REMISIONES ====================

@app.route('/remisiones')
@login_required
def remisiones():
    conn = get_db_connection()
    remisiones_list = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.numero, c.nombre, r.fecha, r.estado
            FROM remisiones r
            JOIN clientes c ON r.cliente_id = c.id
            ORDER BY r.fecha DESC
        """)
        remisiones_list = cursor.fetchall()
        conn.close()
    
    return render_template('remisiones.html', remisiones=remisiones_list)

@app.route('/remisiones/nueva', methods=['GET', 'POST'])
@login_required
def nueva_remision():
    conn = get_db_connection()
    clientes_list = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM clientes ORDER BY nombre")
        clientes_list = cursor.fetchall()
        
        if request.method == 'POST':
            cliente_id = request.form['cliente_id']
            items = request.form.getlist('item[]')
            cantidades = request.form.getlist('cantidad[]')
            
            # Generar número de remisión
            cursor.execute("SELECT MAX(numero) FROM remisiones")
            last_number = cursor.fetchone()[0]
            nuevo_numero = (last_number + 1) if last_number else 1
            
            # Insertar remisión
            cursor.execute("""
                INSERT INTO remisiones (numero, cliente_id, fecha, estado, usuario_id)
                VALUES (?, ?, GETDATE(), 'pendiente', ?)
            """, (nuevo_numero, cliente_id, session['user_id']))
            
            remision_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
            
            # Insertar detalles de remisión
            for item, cantidad in zip(items, cantidades):
                if item and cantidad:
                    cursor.execute("""
                        INSERT INTO remision_detalles (remision_id, descripcion, cantidad)
                        VALUES (?, ?, ?)
                    """, (remision_id, item, cantidad))
            
            conn.commit()
            conn.close()
            
            flash('Remisión creada exitosamente', 'success')
            return redirect(url_for('remisiones'))
        
        conn.close()
    
    return render_template('remision_form.html', clientes=clientes_list, datetime=datetime)

# ==================== GESTIÓN DE EMPLEADOS ====================

@app.route('/empleados')
@login_required
def empleados():
    conn = get_db_connection()
    empleados_list = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, email, telefono, cargo, salario, fecha_ingreso, activo
            FROM empleados ORDER BY nombre
        """)
        empleados_list = cursor.fetchall()
        conn.close()
    
    return render_template('empleados.html', empleados=empleados_list)

@app.route('/empleados/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_empleado():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        cargo = request.form['cargo']
        salario = request.form['salario']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO empleados (nombre, email, telefono, cargo, salario, fecha_ingreso, activo)
                VALUES (?, ?, ?, ?, ?, GETDATE(), 1)
            """, (nombre, email, telefono, cargo, salario))
            conn.commit()
            conn.close()
            
            flash('Empleado creado exitosamente', 'success')
            return redirect(url_for('empleados'))
    
    return render_template('empleado_form.html')

# ==================== NÓMINA ====================

@app.route('/nomina')
@login_required
def nomina():
    conn = get_db_connection()
    nomina_list = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.id, e.nombre, n.periodo, n.salario_base, n.deducciones, n.bonificaciones, n.total
            FROM nomina n
            JOIN empleados e ON n.empleado_id = e.id
            ORDER BY n.periodo DESC
        """)
        nomina_list = cursor.fetchall()
        conn.close()
    
    return render_template('nomina.html', nomina=nomina_list)

@app.route('/nomina/generar', methods=['GET', 'POST'])
@login_required
def generar_nomina():
    if request.method == 'POST':
        periodo = request.form['periodo']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Obtener empleados activos
            cursor.execute("SELECT id, salario FROM empleados WHERE activo = 1")
            empleados = cursor.fetchall()
            
            for empleado_id, salario in empleados:
                # Calcular deducciones (ejemplo: 10% de seguridad social)
                deducciones = salario * 0.10
                bonificaciones = 0  # Puedes agregar lógica para bonificaciones
                total = salario - deducciones + bonificaciones
                
                cursor.execute("""
                    INSERT INTO nomina (empleado_id, periodo, salario_base, deducciones, bonificaciones, total, fecha_generacion)
                    VALUES (?, ?, ?, ?, ?, ?, GETDATE())
                """, (empleado_id, periodo, salario, deducciones, bonificaciones, total))
            
            conn.commit()
            conn.close()
            
            flash('Nómina generada exitosamente', 'success')
            return redirect(url_for('nomina'))
    
    return render_template('generar_nomina.html')

# ==================== MARKETING Y CRM ====================

@app.route('/marketing')
@login_required
def marketing():
    conn = get_db_connection()
    campanias = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, descripcion, fecha_inicio, fecha_fin, estado, presupuesto
            FROM campanias_marketing ORDER BY fecha_inicio DESC
        """)
        campanias = cursor.fetchall()
        conn.close()
    
    return render_template('marketing.html', campanias=campanias)


# ==================== MARKETING FACEBOOK COMPLETO ====================

@app.route('/marketing/facebook', methods=['GET', 'POST'])
@login_required
def facebook_marketing():
    if request.method == 'POST':
        # Datos del formulario
        datos_campania = {
            'nombre': request.form['titulo'],
            'descripcion': request.form['descripcion'],
            'objetivo': request.form['objetivo'],
            'presupuesto_diario': float(request.form['presupuesto']),
            'audiencia': request.form['audiencia'],
            'paises': request.form.getlist('paises[]'),
            'edad_min': int(request.form.get('edad_min', 18)),
            'edad_max': int(request.form.get('edad_max', 65)),
            'intereses': request.form.getlist('intereses[]')
        }
        
        conn = get_db_connection()
        if conn:
            try:
                # Crear campaña en Facebook
                exito, resultado = crear_campania_facebook_completa(datos_campania, conn)
                
                if exito:
                    flash(f'Campaña de Facebook creada exitosamente. ID: {resultado["campaign_id"]}', 'success')
                else:
                    flash(f'Error al crear campaña: {resultado}', 'error')
                
                conn.close()
                
            except Exception as e:
                flash(f'Error inesperado: {str(e)}', 'error')
                conn.close()
            
            return redirect(url_for('marketing'))
    
    # GET request - mostrar formulario
    conn = get_db_connection()
    cuentas_publicitarias = []
    
    if conn:
        try:
            # Verificar conexión con Facebook
            config = init_facebook_marketing()
            fb_api = FacebookMarketingAPI(
                config['access_token'],
                config['app_id'],
                config['app_secret']
            )
            
            valido, info = fb_api.verificar_token()
            if valido:
                exito, cuentas = fb_api.obtener_cuentas_publicitarias()
                if exito:
                    cuentas_publicitarias = cuentas
            
            conn.close()
        except Exception as e:
            flash(f'Error conectando con Facebook: {str(e)}', 'warning')
    
    return render_template('facebook_marketing.html', cuentas=cuentas_publicitarias)

@app.route('/marketing/facebook/configuracion', methods=['GET', 'POST'])
@login_required
@role_required('administrador')
def configuracion_facebook():
    """Configuración de credenciales de Facebook"""
    if request.method == 'POST':
        app_id = request.form['app_id']
        app_secret = request.form['app_secret']
        access_token = request.form['access_token']
        
        # En producción, deberías cifrar estos datos
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Guardar configuración
            cursor.execute("""
                MERGE configuracion_facebook AS target
                USING (SELECT 1 as dummy) AS source
                ON 1=1
                WHEN MATCHED THEN
                    UPDATE SET 
                        app_id = ?,
                        app_secret = ?,
                        access_token = ?,
                        fecha_actualizacion = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (app_id, app_secret, access_token, fecha_creacion)
                    VALUES (?, ?, ?, GETDATE());
            """, (app_id, app_secret, access_token, app_id, app_secret, access_token))
            
            conn.commit()
            conn.close()
            
            flash('Configuración de Facebook actualizada', 'success')
            return redirect(url_for('marketing'))
    
    # Obtener configuración actual
    conn = get_db_connection()
    config_actual = None
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT app_id, access_token, fecha_actualizacion 
            FROM configuracion_facebook
        """)
        config_actual = cursor.fetchone()
        conn.close()
    
    return render_template('configuracion_facebook.html', config=config_actual)

@app.route('/marketing/facebook/campanias')
@login_required
def campanias_facebook():
    """Lista todas las campañas de Facebook"""
    conn = get_db_connection()
    campanias = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                cm.id,
                cm.nombre,
                cm.descripcion,
                cm.presupuesto,
                cm.estado,
                cm.fecha_inicio,
                cm.facebook_campaign_id,
                ce.impresiones,
                ce.clics,
                ce.gasto,
                ce.ctr,
                ce.alcance,
                ce.fecha_actualizacion
            FROM campanias_marketing cm
            LEFT JOIN campanias_estadisticas ce ON cm.id = ce.campania_id
            WHERE cm.plataforma = 'Facebook'
            ORDER BY cm.fecha_inicio DESC
        """)
        campanias = cursor.fetchall()
        conn.close()
    
    return render_template('campanias_facebook.html', campanias=campanias)

@app.route('/marketing/facebook/estadisticas/<campania_id>')
@login_required
def estadisticas_campania_facebook(campania_id):
    """Muestra estadísticas detalladas de una campaña"""
    conn = get_db_connection()
    campania = None
    estadisticas = None
    
    if conn:
        cursor = conn.cursor()
        
        # Obtener datos de la campaña
        cursor.execute("""
            SELECT cm.*, ce.*
            FROM campanias_marketing cm
            LEFT JOIN campanias_estadisticas ce ON cm.id = ce.campania_id
            WHERE cm.id = ? AND cm.plataforma = 'Facebook'
        """, (campania_id,))
        
        resultado = cursor.fetchone()
        if resultado:
            campania = {
                'id': resultado[0],
                'nombre': resultado[1],
                'descripcion': resultado[2],
                'presupuesto': resultado[4],
                'estado': resultado[5],
                'fecha_inicio': resultado[6],
                'campaign_id': resultado[7]
            }
            
            if len(resultado) > 10:  # Si hay estadísticas
                estadisticas = {
                    'impresiones': resultado[10],
                    'clics': resultado[11],
                    'gasto': resultado[12],
                    'ctr': resultado[13],
                    'alcance': resultado[15],
                    'fecha_actualizacion': resultado[16]
                }
        
        conn.close()
    
    return render_template('estadisticas_facebook.html', 
                         campania=campania, estadisticas=estadisticas)

@app.route('/api/facebook/sincronizar', methods=['POST'])
@login_required
def sincronizar_facebook():
    """API para sincronizar estadísticas de Facebook"""
    conn = get_db_connection()
    
    if conn:
        exito, mensaje = sincronizar_estadisticas_facebook(conn)
        conn.close()
        
        if exito:
            return jsonify({'success': True, 'message': mensaje})
        else:
            return jsonify({'success': False, 'message': mensaje}), 500
    
    return jsonify({'success': False, 'message': 'Error de conexión'}), 500

@app.route('/api/facebook/campania/<campania_id>/estado', methods=['POST'])
@login_required
def cambiar_estado_campania_facebook(campania_id):
    """Cambia el estado de una campaña en Facebook"""
    data = request.get_json()
    nuevo_estado = data.get('estado', 'PAUSED')
    
    conn = get_db_connection()
    
    if conn:
        cursor = conn.cursor()
        
        # Obtener Facebook Campaign ID
        cursor.execute("""
            SELECT facebook_campaign_id 
            FROM campanias_marketing 
            WHERE id = ? AND plataforma = 'Facebook'
        """, (campania_id,))
        
        resultado = cursor.fetchone()
        
        if resultado and resultado[0]:
            fb_campaign_id = resultado[0]
            
            try:
                # Actualizar estado en Facebook
                config = init_facebook_marketing()
                fb_api = FacebookMarketingAPI(
                    config['access_token'],
                    config['app_id'],
                    config['app_secret']
                )
                
                url = f"{fb_api.base_url}/{fb_campaign_id}"
                data_update = {
                    'access_token': fb_api.access_token,
                    'status': nuevo_estado
                }
                
                response = requests.post(url, data=data_update)
                
                if response.status_code == 200:
                    # Actualizar en base de datos
                    estado_local = 'activa' if nuevo_estado == 'ACTIVE' else 'pausada'
                    cursor.execute("""
                        UPDATE campanias_marketing 
                        SET estado = ? 
                        WHERE id = ?
                    """, (estado_local, campania_id))
                    conn.commit()
                    
                    conn.close()
                    return jsonify({
                        'success': True, 
                        'message': f'Estado cambiado a {nuevo_estado}'
                    })
                else:
                    conn.close()
                    return jsonify({
                        'success': False, 
                        'message': f'Error en Facebook: {response.text}'
                    }), 500
                    
            except Exception as e:
                conn.close()
                return jsonify({
                    'success': False, 
                    'message': f'Error: {str(e)}'
                }), 500
        else:
            conn.close()
            return jsonify({
                'success': False, 
                'message': 'Campaña no encontrada'
            }), 404
    
    return jsonify({'success': False, 'message': 'Error de conexión'}), 500

# ==================== WEBHOOK DE FACEBOOK ====================

@app.route('/webhook/facebook', methods=['GET', 'POST'])
def webhook_facebook():
    """Webhook para recibir eventos de Facebook"""
    if request.method == 'GET':
        # Verificación del webhook
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        config = init_facebook_marketing()
        if verify_token == config.get('webhook_verify_token'):
            return challenge
        else:
            return 'Error de verificación', 403
    
    elif request.method == 'POST':
        # Procesar eventos
        data = request.get_json()
        
        if procesar_webhook_facebook(data):
            return 'OK', 200
        else:
            return 'Error procesando webhook', 500

# ==================== LEADS DE FACEBOOK ====================

@app.route('/marketing/facebook/leads')
@login_required
def leads_facebook():
    """Muestra leads provenientes de Facebook"""
    conn = get_db_connection()
    leads = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, email, telefono, estado, fecha_creacion, facebook_lead_id
            FROM leads 
            WHERE origen = 'Facebook'
            ORDER BY fecha_creacion DESC
        """)
        leads = cursor.fetchall()
        conn.close()
    
    return render_template('leads_facebook.html', leads=leads)

@app.route('/api/facebook/leads/importar', methods=['POST'])
@login_required
def importar_leads_facebook():
    """Importa leads manualmente desde Facebook"""
    try:
        config = init_facebook_marketing()
        fb_api = FacebookMarketingAPI(
            config['access_token'],
            config['app_id'],
            config['app_secret']
        )
        
        # Obtener formularios de leads
        url = f"{fb_api.base_url}/me/leadgen_forms"
        params = {
            'access_token': fb_api.access_token,
            'fields': 'id,name,leads{id,created_time,field_data}'
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            leads_importados = 0
            
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                
                for form in data.get('data', []):
                    for lead in form.get('leads', {}).get('data', []):
                        # Verificar si el lead ya existe
                        cursor.execute("""
                            SELECT id FROM leads WHERE facebook_lead_id = ?
                        """, (lead['id'],))
                        
                        if not cursor.fetchone():
                            # Procesar datos del lead
                            field_data = lead.get('field_data', [])
                            lead_info = {'nombre': '', 'email': '', 'telefono': ''}
                            
                            for field in field_data:
                                name = field.get('name', '').lower()
                                values = field.get('values', [])
                                if values:
                                    if name in ['full_name', 'first_name', 'last_name']:
                                        lead_info['nombre'] = values[0]
                                    elif name == 'email':
                                        lead_info['email'] = values[0]
                                    elif name in ['phone_number', 'telefono']:
                                        lead_info['telefono'] = values[0]
                            
                            # Insertar lead
                            cursor.execute("""
                                INSERT INTO leads (nombre, email, telefono, origen, estado, 
                                                 fecha_creacion, facebook_lead_id, usuario_id)
                                VALUES (?, ?, ?, 'Facebook', 'nuevo', ?, ?, ?)
                            """, (
                                lead_info['nombre'],
                                lead_info['email'],
                                lead_info['telefono'],
                                lead['created_time'],
                                lead['id'],
                                session['user_id']
                            ))
                            
                            leads_importados += 1
                
                conn.commit()
                conn.close()
                
                return jsonify({
                    'success': True, 
                    'message': f'{leads_importados} leads importados exitosamente'
                })
        
        return jsonify({
            'success': False, 
            'message': 'Error obteniendo formularios de Facebook'
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error importando leads: {str(e)}'
        }), 500

# ==================== ANÁLISIS Y REPORTES ====================

@app.route('/marketing/facebook/reportes')
@login_required
def reportes_facebook():
    """Genera reportes de rendimiento de Facebook"""
    conn = get_db_connection()
    reportes = {}
    
    if conn:
        cursor = conn.cursor()
        
        # Resumen general
        cursor.execute("""
            SELECT 
                COUNT(*) as total_campanias,
                SUM(ce.gasto) as gasto_total,
                SUM(ce.impresiones) as impresiones_total,
                SUM(ce.clics) as clics_total,
                AVG(ce.ctr) as ctr_promedio
            FROM campanias_marketing cm
            LEFT JOIN campanias_estadisticas ce ON cm.id = ce.campania_id
            WHERE cm.plataforma = 'Facebook'
        """)
        
        resumen = cursor.fetchone()
        if resumen:
            reportes['resumen'] = {
                'total_campanias': resumen[0] or 0,
                'gasto_total': float(resumen[1] or 0),
                'impresiones_total': resumen[2] or 0,
                'clics_total': resumen[3] or 0,
                'ctr_promedio': float(resumen[4] or 0)
            }
        
        # Top 5 campañas por rendimiento
        cursor.execute("""
            SELECT TOP 5
                cm.nombre,
                ce.impresiones,
                ce.clics,
                ce.gasto,
                ce.ctr
            FROM campanias_marketing cm
            INNER JOIN campanias_estadisticas ce ON cm.id = ce.campania_id
            WHERE cm.plataforma = 'Facebook'
            ORDER BY ce.clics DESC
        """)
        
        reportes['top_campanias'] = cursor.fetchall()
        
        # Leads por mes
        cursor.execute("""
            SELECT 
                FORMAT(fecha_creacion, 'yyyy-MM') as mes,
                COUNT(*) as total_leads
            FROM leads 
            WHERE origen = 'Facebook'
            GROUP BY FORMAT(fecha_creacion, 'yyyy-MM')
            ORDER BY mes DESC
        """)
        
        reportes['leads_por_mes'] = cursor.fetchall()
        
        conn.close()
    
    return render_template('reportes_facebook.html', reportes=reportes)

@app.route('/api/facebook/exportar-datos', methods=['POST'])
@login_required
def exportar_datos_facebook():
    """Exporta datos de Facebook a CSV"""
    try:
        tipo_export = request.json.get('tipo', 'campanias')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Error de conexión'}), 500
        
        cursor = conn.cursor()
        
        if tipo_export == 'campanias':
            cursor.execute("""
                SELECT 
                    cm.nombre,
                    cm.descripcion,
                    cm.presupuesto,
                    cm.estado,
                    cm.fecha_inicio,
                    ce.impresiones,
                    ce.clics,
                    ce.gasto,
                    ce.ctr,
                    ce.alcance
                FROM campanias_marketing cm
                LEFT JOIN campanias_estadisticas ce ON cm.id = ce.campania_id
                WHERE cm.plataforma = 'Facebook'
                ORDER BY cm.fecha_inicio DESC
            """)
            
        elif tipo_export == 'leads':
            cursor.execute("""
                SELECT nombre, email, telefono, estado, fecha_creacion
                FROM leads 
                WHERE origen = 'Facebook'
                ORDER BY fecha_creacion DESC
            """)
        
        datos = cursor.fetchall()
        conn.close()
        
        if datos:
            # Crear CSV en memoria
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Headers según el tipo
            if tipo_export == 'campanias':
                writer.writerow(['Nombre', 'Descripción', 'Presupuesto', 'Estado', 
                               'Fecha Inicio', 'Impresiones', 'Clics', 'Gasto', 'CTR', 'Alcance'])
            else:
                writer.writerow(['Nombre', 'Email', 'Teléfono', 'Estado', 'Fecha Creación'])
            
            # Datos
            for row in datos:
                writer.writerow(row)
            
            output.seek(0)
            csv_data = output.getvalue()
            
            return jsonify({
                'success': True,
                'data': csv_data,
                'filename': f'facebook_{tipo_export}.csv'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No hay datos para exportar'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error exportando datos: {str(e)}'
        }), 500

# ==================== UTILIDADES ADICIONALES ====================

@app.route('/api/facebook/test-conexion', methods=['POST'])
@login_required
def test_conexion_facebook():
    """Prueba la conexión con Facebook API"""
    try:
        config = init_facebook_marketing()
        fb_api = FacebookMarketingAPI(
            config['access_token'],
            config['app_id'],
            config['app_secret']
        )
        
        valido, info = fb_api.verificar_token()
        
        if valido:
            # Obtener información adicional
            exito, cuentas = fb_api.obtener_cuentas_publicitarias()
            
            return jsonify({
                'success': True,
                'message': 'Conexión exitosa con Facebook',
                'info': {
                    'usuario': info.get('name', 'N/A'),
                    'id': info.get('id', 'N/A'),
                    'cuentas_disponibles': len(cuentas) if exito else 0
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Error de conexión: {info}'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error probando conexión: {str(e)}'
        }), 500

@app.route('/api/facebook/audiencias-sugeridas', methods=['POST'])
@login_required
def audiencias_sugeridas():
    """Obtiene audiencias sugeridas basadas en intereses"""
    try:
        data = request.get_json()
        interes = data.get('interes', '')
        
        if not interes:
            return jsonify({'success': False, 'message': 'Interés requerido'}), 400
        
        config = init_facebook_marketing()
        fb_api = FacebookMarketingAPI(
            config['access_token'],
            config['app_id'],
            config['app_secret']
        )
        
        # Buscar intereses relacionados
        url = f"{fb_api.base_url}/search"
        params = {
            'access_token': fb_api.access_token,
            'type': 'adinterest',
            'q': interes,
            'limit': 10
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            intereses = data.get('data', [])
            
            return jsonify({
                'success': True,
                'intereses': [{'id': i['id'], 'name': i['name']} for i in intereses]
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error obteniendo sugerencias'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

# ==================== GESTIÓN DE CRM COMPLETA ====================

@app.route('/crm', methods=['GET', 'POST'])
@login_required
def crm():
    conn = get_db_connection()
    leads = []
    oportunidades = []
    clientes_list = []
    
    if conn:
        cursor = conn.cursor()
        
        # Manejar POST para crear nuevo lead u oportunidad
        if request.method == 'POST':
            tipo = request.form.get('tipo', 'lead')
            
            if tipo == 'lead' or not tipo:
                # Crear nuevo lead
                id = request.form['id']
                nombre = request.form['nombre']
                email = request.form['email']
                telefono = request.form.get('telefono', '')
                origen = request.form['origen']
                notas = request.form.get('notas', '')
                
                try:
                    cursor.execute("""
                        INSERT INTO leads (id, nombre, email, telefono, origen, estado, notas, fecha_creacion, usuario_id)
                        VALUES (? ,?, ?, ?, ?, 'nuevo', ?, GETDATE(), ?)
                    """, (nombre, email, telefono, origen, notas, session['user_id']))
                    conn.commit()
                    flash('Lead creado exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al crear el lead: {str(e)}', 'error')
            
            elif tipo == 'oportunidad':
                # Crear nueva oportunidad
                cliente_id = request.form['cliente_id']
                descripcion = request.form['descripcion']
                valor = request.form['valor']
                probabilidad = request.form['probabilidad']
                fecha_cierre_estimada = request.form.get('fecha_cierre_estimada')
                
                try:
                    cursor.execute("""
                        INSERT INTO oportunidades (cliente_id, descripcion, valor, probabilidad, 
                                                 fecha_cierre_estimada, estado, fecha_creacion, usuario_id)
                        VALUES (?, ?, ?, ?, ?, 'prospecto', GETDATE(), ?)
                    """, (cliente_id, descripcion, valor, probabilidad, fecha_cierre_estimada, session['user_id']))
                    conn.commit()
                    flash('Oportunidad creada exitosamente', 'success')
                except Exception as e:
                    flash(f'Error al crear la oportunidad: {str(e)}', 'error')
            
            return redirect(url_for('crm'))
        
        # Obtener leads recientes
        cursor.execute("""
            SELECT id, nombre, email, telefono, origen, estado, fecha_creacion
            FROM leads 
            ORDER BY fecha_creacion DESC
        """)
        leads = cursor.fetchall()
        
        # Obtener oportunidades abiertas
        cursor.execute("""
            SELECT o.id, c.nombre, o.descripcion, o.valor, o.probabilidad, o.estado
            FROM oportunidades o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.estado != 'cerrada'
            ORDER BY o.fecha_creacion DESC
        """)
        oportunidades = cursor.fetchall()
        
        # Obtener clientes para el modal de oportunidades
        cursor.execute("SELECT id, nombre FROM clientes ORDER BY nombre")
        clientes_list = cursor.fetchall()
        
        conn.close()
    
    return render_template('crm.html', leads=leads, oportunidades=oportunidades, clientes=clientes_list)

# ==================== APIs PARA ACCIONES AJAX ====================

@app.route('/api/leads/<lead_id>/contactar', methods=['POST'])
@login_required
def contactar_lead(lead_id):
    """API para marcar un lead como contactado"""
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE leads 
                SET estado = 'contactado', fecha_contacto = GETDATE(), contactado_por = ?
                WHERE id = ?
            """, (session['user_id'], lead_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Lead marcado como contactado'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': 'Error de conexión'}), 500

@app.route('/api/leads/<lead_id>/convertir', methods=['POST'])
@login_required
def convertir_lead(lead_id):
    """API para convertir un lead en cliente"""
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            
            # Obtener datos del lead
            cursor.execute("SELECT nombre, email, telefono FROM leads WHERE id = ?", (lead_id,))
            lead_data = cursor.fetchone()
            
            if lead_data:
                # Crear cliente
                cursor.execute("""
                    INSERT INTO clientes (nombre, email, telefono, direccion, fecha_registro)
                    VALUES (?, ?, ?, 'Por actualizar', GETDATE())
                """, (lead_data[0], lead_data[1], lead_data[2]))
                
                # Marcar lead como convertido
                cursor.execute("""
                    UPDATE leads 
                    SET estado = 'convertido', fecha_conversion = GETDATE()
                    WHERE id = ?
                """, (lead_id,))
                
                conn.commit()
                conn.close()
                
                return jsonify({'success': True, 'message': 'Lead convertido en cliente exitosamente'})
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Lead no encontrado'}), 404
                
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': 'Error de conexión'}), 500

@app.route('/api/leads/<lead_id>/calificar', methods=['POST'])
@login_required
def calificar_lead(lead_id):
    """API para calificar un lead"""
    data = request.get_json()
    calificacion = data.get('calificacion', 'calificado')
    notas = data.get('notas', '')
    
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE leads 
                SET estado = ?, notas = ?, fecha_calificacion = GETDATE()
                WHERE id = ?
            """, (calificacion, notas, lead_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Lead calificado exitosamente'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': 'Error de conexión'}), 500

@app.route('/api/oportunidades/<oportunidad_id>/cerrar', methods=['POST'])
@login_required
def cerrar_oportunidad(oportunidad_id):
    """API para cerrar una oportunidad"""
    data = request.get_json()
    estado = data.get('estado', 'ganada')  # ganada o perdida
    notas = data.get('notas', '')
    
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            
            # Si la oportunidad se gana, también se puede crear una factura automáticamente
            if estado == 'ganada':
                cursor.execute("""
                    UPDATE oportunidades 
                    SET estado = 'cerrada', resultado = 'ganada', fecha_cierre = GETDATE(), notas_cierre = ?
                    WHERE id = ?
                """, (notas, oportunidad_id))
            else:
                cursor.execute("""
                    UPDATE oportunidades 
                    SET estado = 'cerrada', resultado = 'perdida', fecha_cierre = GETDATE(), notas_cierre = ?
                    WHERE id = ?
                """, (notas, oportunidad_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': f'Oportunidad cerrada como {estado}'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': 'Error de conexión'}), 500

@app.route('/api/oportunidades/<oportunidad_id>/actualizar', methods=['POST'])
@login_required
def actualizar_oportunidad(oportunidad_id):
    """API para actualizar el estado y probabilidad de una oportunidad"""
    data = request.get_json()
    estado = data.get('estado')
    probabilidad = data.get('probabilidad')
    notas = data.get('notas', '')
    
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE oportunidades 
                SET estado = ?, probabilidad = ?, notas = ?, fecha_actualizacion = GETDATE()
                WHERE id = ?
            """, (estado, probabilidad, notas, oportunidad_id))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Oportunidad actualizada exitosamente'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': 'Error de conexión'}), 500

# ==================== RUTAS ADICIONALES PARA CRM ====================

@app.route('/leads')
@login_required
def lista_leads():
    """Vista completa de todos los leads"""
    conn = get_db_connection()
    leads = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, email, telefono, origen, estado, fecha_creacion, notas
            FROM leads 
            ORDER BY fecha_creacion DESC
        """)
        leads = cursor.fetchall()
        conn.close()
    
    return render_template('leads.html', leads=leads)

@app.route('/oportunidades')
@login_required
def lista_oportunidades():
    """Vista completa de todas las oportunidades"""
    conn = get_db_connection()
    oportunidades = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.id, c.nombre, o.descripcion, o.valor, o.probabilidad, 
                   o.estado, o.fecha_creacion, o.fecha_cierre_estimada
            FROM oportunidades o
            JOIN clientes c ON o.cliente_id = c.id
            ORDER BY o.fecha_creacion DESC
        """)
        oportunidades = cursor.fetchall()
        conn.close()
    
    return render_template('oportunidades.html', oportunidades=oportunidades)

@app.route('/oportunidades/<oportunidad_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_oportunidad(oportunidad_id):
    """Editar una oportunidad específica"""
    conn = get_db_connection()
    oportunidad = None
    clientes_list = []
    
    if conn:
        cursor = conn.cursor()
        
        if request.method == 'POST':
            cliente_id = request.form['cliente_id']
            descripcion = request.form['descripcion']
            valor = request.form['valor']
            probabilidad = request.form['probabilidad']
            estado = request.form['estado']
            fecha_cierre_estimada = request.form.get('fecha_cierre_estimada')
            
            try:
                cursor.execute("""
                    UPDATE oportunidades 
                    SET cliente_id = ?, descripcion = ?, valor = ?, probabilidad = ?, 
                        estado = ?, fecha_cierre_estimada = ?, fecha_actualizacion = GETDATE()
                    WHERE id = ?
                """, (cliente_id, descripcion, valor, probabilidad, estado, 
                      fecha_cierre_estimada, oportunidad_id))
                conn.commit()
                flash('Oportunidad actualizada exitosamente', 'success')
                return redirect(url_for('lista_oportunidades'))
            except Exception as e:
                flash(f'Error al actualizar: {str(e)}', 'error')
        
        # Obtener datos de la oportunidad
        cursor.execute("""
            SELECT o.*, c.nombre as cliente_nombre
            FROM oportunidades o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.id = ?
        """, (oportunidad_id,))
        oportunidad = cursor.fetchone()
        
        # Obtener lista de clientes
        cursor.execute("SELECT id, nombre FROM clientes ORDER BY nombre")
        clientes_list = cursor.fetchall()
        
        conn.close()
    
    return render_template('oportunidad_form.html', oportunidad=oportunidad, clientes=clientes_list)

@app.route('/api/crm/estadisticas')
@login_required
def estadisticas_crm():
    """API para obtener estadísticas del CRM"""
    conn = get_db_connection()
    stats = {}
    
    if conn:
        cursor = conn.cursor()
        
        # Total de leads por estado
        cursor.execute("""
            SELECT estado, COUNT(*) as total
            FROM leads
            GROUP BY estado
        """)
        stats['leads_por_estado'] = dict(cursor.fetchall())
        
        # Valor total de oportunidades por estado
        cursor.execute("""
            SELECT estado, SUM(valor) as total_valor, COUNT(*) as cantidad
            FROM oportunidades
            GROUP BY estado
        """)
        stats['oportunidades_por_estado'] = {}
        for row in cursor.fetchall():
            stats['oportunidades_por_estado'][row[0]] = {
                'valor': float(row[1]) if row[1] else 0,
                'cantidad': row[2]
            }
        
        # Leads por origen
        cursor.execute("""
            SELECT origen, COUNT(*) as total
            FROM leads
            GROUP BY origen
        """)
        stats['leads_por_origen'] = dict(cursor.fetchall())
        
        # Conversión de leads a clientes
        cursor.execute("SELECT COUNT(*) FROM leads WHERE estado = 'convertido'")
        leads_convertidos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads")
        total_leads = cursor.fetchone()[0]
        
        stats['tasa_conversion'] = (leads_convertidos / total_leads * 100) if total_leads > 0 else 0
        
        conn.close()
    
    return jsonify(stats)

@app.route('/api/facebook_leads', methods=['POST'])
def recibir_lead_facebook():
    """Webhook para recibir leads de Facebook"""
    data = request.get_json()
    
    if data:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO leads (nombre, email, telefono, origen, estado, fecha_creacion)
                VALUES (?, ?, ?, 'Facebook', 'nuevo', GETDATE())
            """, (data.get('nombre'), data.get('email'), data.get('telefono')))
            conn.commit()
            conn.close()
    
    return jsonify({'status': 'success'})

# ==================== REPORTES ====================

@app.route('/reportes')
@login_required
def reportes():
    return render_template('reportes.html')

@app.route('/reportes/ventas')
@login_required
def reporte_ventas():
    conn = get_db_connection()
    datos = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MONTH(fecha) as mes, SUM(total) as total_ventas
            FROM facturas 
            WHERE YEAR(fecha) = YEAR(GETDATE())
            GROUP BY MONTH(fecha)
            ORDER BY mes
        """)
        datos = cursor.fetchall()
        conn.close()
    
    return render_template('reporte_ventas.html', datos=datos)

# ==================== RUTAS DE REPORTES AVANZADOS COMPLETOS ====================
# Agregar estas rutas al archivo app.py después de la ruta /reportes existente

@app.route('/reportes/ventas/mensual')
@login_required
def reporte_ventas_mensual():
    conn = get_db_connection()
    datos = {
        'ventas_por_mes': [],
        'comparativo_anual': [],
        'top_clientes': [],
        'tendencias': {}
    }
    
    if conn:
        cursor = conn.cursor()
        
        # Ventas por mes del año actual
        cursor.execute("""
            SELECT 
                MONTH(fecha) as mes,
                DATENAME(MONTH, fecha) as nombre_mes,
                COUNT(*) as cantidad_facturas,
                SUM(total) as total_ventas,
                AVG(total) as promedio_venta
            FROM facturas 
            WHERE YEAR(fecha) = YEAR(GETDATE()) AND estado != 'cancelada'
            GROUP BY MONTH(fecha), DATENAME(MONTH, fecha)
            ORDER BY mes
        """)
        datos['ventas_por_mes'] = cursor.fetchall()
        
        # Comparativo con año anterior
        cursor.execute("""
            SELECT 
                YEAR(fecha) as anio,
                SUM(total) as total_anual,
                COUNT(*) as cantidad_facturas
            FROM facturas 
            WHERE YEAR(fecha) >= YEAR(GETDATE()) - 1 AND estado != 'cancelada'
            GROUP BY YEAR(fecha)
            ORDER BY anio
        """)
        datos['comparativo_anual'] = cursor.fetchall()
        
        # Top 10 clientes del mes
        cursor.execute("""
            SELECT TOP 10
                c.nombre,
                COUNT(f.id) as cantidad_compras,
                SUM(f.total) as total_comprado
            FROM facturas f
            JOIN clientes c ON f.cliente_id = c.id
            WHERE MONTH(f.fecha) = MONTH(GETDATE()) 
                AND YEAR(f.fecha) = YEAR(GETDATE())
                AND f.estado != 'cancelada'
            GROUP BY c.nombre
            ORDER BY total_comprado DESC
        """)
        datos['top_clientes'] = cursor.fetchall()
        
        # Calcular tendencias
        if datos['ventas_por_mes']:
            ventas = [float(row[3]) for row in datos['ventas_por_mes']]
            if len(ventas) > 1:
                datos['tendencias']['crecimiento_promedio'] = (
                    (ventas[-1] - ventas[0]) / ventas[0] * 100 if ventas[0] > 0 else 0
                )
                datos['tendencias']['mejor_mes'] = max(datos['ventas_por_mes'], key=lambda x: x[3])
                datos['tendencias']['total_anual'] = sum(ventas)
        
        conn.close()
    
    return render_template('reportes/ventas_mensual.html', datos=datos)

@app.route('/reportes/ventas/clientes')
@login_required
def reporte_ventas_clientes():
    conn = get_db_connection()
    datos = {
        'ranking_clientes': [],
        'clientes_nuevos': [],
        'clientes_frecuentes': [],
        'estadisticas': {}
    }
    
    if conn:
        cursor = conn.cursor()
        
        # Ranking de clientes por ventas
        cursor.execute("""
            SELECT 
                c.id,
                c.nombre,
                c.email,
                COUNT(f.id) as total_facturas,
                SUM(f.total) as total_comprado,
                AVG(f.total) as promedio_compra,
                MAX(f.fecha) as ultima_compra,
                DATEDIFF(DAY, MAX(f.fecha), GETDATE()) as dias_ultima_compra
            FROM clientes c
            LEFT JOIN facturas f ON c.id = f.cliente_id AND f.estado != 'cancelada'
            GROUP BY c.id, c.nombre, c.email
            ORDER BY total_comprado DESC
        """)
        datos['ranking_clientes'] = cursor.fetchall()
        
        # Clientes nuevos (últimos 30 días)
        cursor.execute("""
            SELECT 
                c.nombre,
                c.email,
                c.fecha_registro,
                COALESCE(SUM(f.total), 0) as total_comprado
            FROM clientes c
            LEFT JOIN facturas f ON c.id = f.cliente_id AND f.estado != 'cancelada'
            WHERE c.fecha_registro >= DATEADD(DAY, -30, GETDATE())
            GROUP BY c.nombre, c.email, c.fecha_registro
            ORDER BY c.fecha_registro DESC
        """)
        datos['clientes_nuevos'] = cursor.fetchall()
        
        # Clientes más frecuentes
        cursor.execute("""
            SELECT TOP 10
                c.nombre,
                COUNT(f.id) as frecuencia_compra,
                SUM(f.total) as total_comprado,
                AVG(DATEDIFF(DAY, LAG(f.fecha) OVER (PARTITION BY c.id ORDER BY f.fecha), f.fecha)) as promedio_dias_entre_compras
            FROM clientes c
            JOIN facturas f ON c.id = f.cliente_id AND f.estado != 'cancelada'
            GROUP BY c.id, c.nombre
            HAVING COUNT(f.id) > 1
            ORDER BY frecuencia_compra DESC
        """)
        datos['clientes_frecuentes'] = cursor.fetchall()
        
        # Estadísticas generales
        cursor.execute("SELECT COUNT(*) FROM clientes")
        datos['estadisticas']['total_clientes'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(DISTINCT cliente_id) 
            FROM facturas 
            WHERE MONTH(fecha) = MONTH(GETDATE()) AND YEAR(fecha) = YEAR(GETDATE())
        """)
        datos['estadisticas']['clientes_activos_mes'] = cursor.fetchone()[0]
        
        conn.close()
    
    return render_template('reportes/ventas_clientes.html', datos=datos)

@app.route('/reportes/crm/leads')
@login_required
def reporte_crm_leads():
    conn = get_db_connection()
    datos = {
        'resumen_leads': [],
        'conversion_por_origen': [],
        'tendencias': [],
        'estadisticas': {}
    }
    
    if conn:
        cursor = conn.cursor()
        
        # Resumen de leads por estado
        cursor.execute("""
            SELECT 
                estado,
                COUNT(*) as cantidad,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM leads), 2) as porcentaje
            FROM leads
            GROUP BY estado
            ORDER BY cantidad DESC
        """)
        datos['resumen_leads'] = cursor.fetchall()
        
        # Conversión por origen
        cursor.execute("""
            SELECT 
                origen,
                COUNT(*) as total_leads,
                SUM(CASE WHEN estado = 'convertido' THEN 1 ELSE 0 END) as convertidos,
                ROUND(SUM(CASE WHEN estado = 'convertido' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as tasa_conversion
            FROM leads
            WHERE origen IS NOT NULL
            GROUP BY origen
            ORDER BY tasa_conversion DESC
        """)
        datos['conversion_por_origen'] = cursor.fetchall()
        
        # Tendencias por mes
        cursor.execute("""
            SELECT 
                YEAR(fecha_creacion) as anio,
                MONTH(fecha_creacion) as mes,
                DATENAME(MONTH, fecha_creacion) as nombre_mes,
                COUNT(*) as leads_creados,
                SUM(CASE WHEN estado = 'convertido' THEN 1 ELSE 0 END) as leads_convertidos
            FROM leads
            WHERE fecha_creacion >= DATEADD(MONTH, -12, GETDATE())
            GROUP BY YEAR(fecha_creacion), MONTH(fecha_creacion), DATENAME(MONTH, fecha_creacion)
            ORDER BY anio, mes
        """)
        datos['tendencias'] = cursor.fetchall()
        
        # Estadísticas generales
        cursor.execute("SELECT COUNT(*) FROM leads")
        datos['estadisticas']['total_leads'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE estado = 'convertido'")
        leads_convertidos = cursor.fetchone()[0]
        
        datos['estadisticas']['tasa_conversion_general'] = (
            round(leads_convertidos / datos['estadisticas']['total_leads'] * 100, 2) 
            if datos['estadisticas']['total_leads'] > 0 else 0
        )
        
        cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE fecha_creacion >= DATEADD(DAY, -30, GETDATE())
        """)
        datos['estadisticas']['leads_mes_actual'] = cursor.fetchone()[0]
        
        conn.close()
    
    return render_template('reportes/crm_leads.html', datos=datos)


@app.route('/reportes/empleados')
@login_required
def reporte_empleados():
    conn = get_db_connection()
    datos = {
        'lista_empleados': [],
        'por_cargo': [],
        'estadisticas': {}
    }
    
    if conn:
        cursor = conn.cursor()
        
        # Lista completa de empleados
        cursor.execute("""
            SELECT 
                id,
                nombre,
                email,
                telefono,
                cargo,
                salario,
                fecha_ingreso,
                DATEDIFF(DAY, fecha_ingreso, GETDATE()) as dias_empresa,
                activo
            FROM empleados
            ORDER BY fecha_ingreso DESC
        """)
        datos['lista_empleados'] = cursor.fetchall()
        
        # Empleados por cargo
        cursor.execute("""
            SELECT 
                cargo,
                COUNT(*) as cantidad,
                AVG(salario) as salario_promedio,
                MIN(salario) as salario_minimo,
                MAX(salario) as salario_maximo
            FROM empleados
            WHERE activo = 1
            GROUP BY cargo
            ORDER BY cantidad DESC
        """)
        datos['por_cargo'] = cursor.fetchall()
        
        # Estadísticas generales
        cursor.execute("SELECT COUNT(*) FROM empleados WHERE activo = 1")
        datos['estadisticas']['empleados_activos'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM empleados WHERE activo = 0")
        datos['estadisticas']['empleados_inactivos'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(salario) FROM empleados WHERE activo = 1")
        datos['estadisticas']['salario_promedio'] = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT COUNT(*) FROM empleados 
            WHERE fecha_ingreso >= DATEADD(MONTH, -6, GETDATE()) AND activo = 1
        """)
        datos['estadisticas']['contrataciones_recientes'] = cursor.fetchone()[0]
        
        conn.close()
    
    return render_template('reportes/empleados.html', datos=datos)

@app.route('/reportes/nomina')
@login_required
def reporte_nomina():
    conn = get_db_connection()
    datos = {
        'nomina_actual': [],
        'historico': [],
        'costos_totales': {},
        'por_empleado': []
    }
    
    if conn:
        cursor = conn.cursor()
        
        # Nómina del período actual
        cursor.execute("""
            SELECT 
                e.nombre,
                e.cargo,
                n.periodo,
                n.salario_base,
                n.deducciones,
                n.bonificaciones,
                n.total,
                n.fecha_generacion
            FROM nomina n
            JOIN empleados e ON n.empleado_id = e.id
            WHERE n.periodo = (SELECT MAX(periodo) FROM nomina)
            ORDER BY n.total DESC
        """)
        datos['nomina_actual'] = cursor.fetchall()
        
        # Histórico de costos por período
        cursor.execute("""
            SELECT 
                periodo,
                COUNT(*) as empleados,
                SUM(salario_base) as total_salarios,
                SUM(deducciones) as total_deducciones,
                SUM(bonificaciones) as total_bonificaciones,
                SUM(total) as costo_total
            FROM nomina
            GROUP BY periodo
            ORDER BY periodo DESC
        """)
        datos['historico'] = cursor.fetchall()
        
        # Costos totales actuales
        if datos['nomina_actual']:
            datos['costos_totales'] = {
                'total_salarios': sum(row[3] for row in datos['nomina_actual']),
                'total_deducciones': sum(row[4] for row in datos['nomina_actual']),
                'total_bonificaciones': sum(row[5] for row in datos['nomina_actual']),
                'costo_total': sum(row[6] for row in datos['nomina_actual'])
            }
        
        # Análisis por empleado (últimos 6 meses)
        cursor.execute("""
            SELECT 
                e.nombre,
                COUNT(n.id) as periodos_pagados,
                AVG(n.total) as promedio_pago,
                SUM(n.total) as total_pagado
            FROM empleados e
            JOIN nomina n ON e.id = n.empleado_id
            WHERE n.fecha_generacion >= DATEADD(MONTH, -6, GETDATE())
            GROUP BY e.id, e.nombre
            ORDER BY total_pagado DESC
        """)
        datos['por_empleado'] = cursor.fetchall()
        
        conn.close()
    
    return render_template('reportes/nomina.html', datos=datos)

@app.route('/reportes/financiero')
@login_required
def reporte_financiero():
    conn = get_db_connection()
    datos = {
        'ingresos_mensuales': [],
        'estado_facturas': [],
        'rentabilidad': {},
        'proyecciones': [],
        'flujo_caja': []
    }
    
    if conn:
        cursor = conn.cursor()
        
        # Ingresos por mes (últimos 12 meses)
        cursor.execute("""
            SELECT 
                YEAR(fecha) as anio,
                MONTH(fecha) as mes,
                DATENAME(MONTH, fecha) as nombre_mes,
                SUM(total) as ingresos,
                COUNT(*) as cantidad_facturas,
                SUM(CASE WHEN estado = 'pagada' THEN total ELSE 0 END) as ingresos_cobrados,
                SUM(CASE WHEN estado = 'pendiente' THEN total ELSE 0 END) as ingresos_pendientes
            FROM facturas
            WHERE fecha >= DATEADD(MONTH, -12, GETDATE()) AND estado != 'cancelada'
            GROUP BY YEAR(fecha), MONTH(fecha), DATENAME(MONTH, fecha)
            ORDER BY anio, mes
        """)
        datos['ingresos_mensuales'] = cursor.fetchall()
        
        # Estado de facturas
        cursor.execute("""
            SELECT 
                estado,
                COUNT(*) as cantidad,
                SUM(total) as monto_total,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM facturas WHERE estado != 'cancelada'), 2) as porcentaje
            FROM facturas
            WHERE estado != 'cancelada'
            GROUP BY estado
            ORDER BY monto_total DESC
        """)
        datos['estado_facturas'] = cursor.fetchall()
        
        # Análisis de rentabilidad
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN estado = 'pagada' THEN total ELSE 0 END) as ingresos_reales,
                SUM(total) as ingresos_facturados,
                COUNT(*) as total_facturas
            FROM facturas 
            WHERE YEAR(fecha) = YEAR(GETDATE()) AND estado != 'cancelada'
        """)
        rentabilidad_data = cursor.fetchone()
        if rentabilidad_data:
            datos['rentabilidad'] = {
                'ingresos_reales': rentabilidad_data[0] or 0,
                'ingresos_facturados': rentabilidad_data[1] or 0,
                'tasa_cobranza': round((rentabilidad_data[0] or 0) / (rentabilidad_data[1] or 1) * 100, 2),
                'total_facturas': rentabilidad_data[2]
            }
        
        # Proyecciones basadas en tendencias (próximos 3 meses)
        cursor.execute("""
            SELECT 
                AVG(monthly_income) as promedio_mensual
            FROM (
                SELECT SUM(total) as monthly_income
                FROM facturas
                WHERE fecha >= DATEADD(MONTH, -6, GETDATE()) AND estado != 'cancelada'
                GROUP BY YEAR(fecha), MONTH(fecha)
            ) as monthly_data
        """)
        promedio_result = cursor.fetchone()
        if promedio_result and promedio_result[0]:
            promedio_mensual = promedio_result[0]
            datos['proyecciones'] = [
                {'mes': 1, 'proyeccion': promedio_mensual * 1.02},  # Crecimiento 2%
                {'mes': 2, 'proyeccion': promedio_mensual * 1.04},  # Crecimiento 4%
                {'mes': 3, 'proyeccion': promedio_mensual * 1.06}   # Crecimiento 6%
            ]
        
        # Flujo de caja semanal (últimas 8 semanas)
        cursor.execute("""
            SELECT 
                DATEPART(WEEK, fecha) as semana,
                YEAR(fecha) as anio,
                SUM(CASE WHEN estado = 'pagada' THEN total ELSE 0 END) as ingresos,
                COUNT(*) as facturas
            FROM facturas
            WHERE fecha >= DATEADD(WEEK, -8, GETDATE()) AND estado != 'cancelada'
            GROUP BY DATEPART(WEEK, fecha), YEAR(fecha)
            ORDER BY anio, semana
        """)
        datos['flujo_caja'] = cursor.fetchall()
        
        conn.close()
    
    return render_template('reportes/financiero.html', datos=datos)

@app.route('/reportes/inventario')
@login_required
def reporte_inventario():
    conn = get_db_connection()
    datos = {
        'productos_stock': [],
        'movimientos_recientes': [],
        'productos_agotados': [],
        'rotacion_inventario': [],
        'valoracion_inventario': {}
    }
    
    if conn:
        cursor = conn.cursor()
        
        # Productos con stock actual (si tienes tabla de productos/inventario)
        try:
            cursor.execute("""
                SELECT 
                    codigo,
                    nombre,
                    stock_actual,
                    stock_minimo,
                    precio_compra,
                    precio_venta,
                    CASE 
                        WHEN stock_actual <= stock_minimo THEN 'Crítico'
                        WHEN stock_actual <= stock_minimo * 2 THEN 'Bajo'
                        ELSE 'Normal'
                    END as estado_stock
                FROM productos
                ORDER BY stock_actual ASC
            """)
            datos['productos_stock'] = cursor.fetchall()
        except:
            # Si no existe la tabla productos, usar datos de factura_detalles
            cursor.execute("""
                SELECT 
                    fd.descripcion as producto,
                    SUM(fd.cantidad) as cantidad_vendida,
                    COUNT(DISTINCT f.id) as facturas_con_producto,
                    AVG(fd.precio_unitario) as precio_promedio
                FROM factura_detalles fd
                JOIN facturas f ON fd.factura_id = f.id
                WHERE f.fecha >= DATEADD(MONTH, -3, GETDATE()) AND f.estado != 'cancelada'
                GROUP BY fd.descripcion
                ORDER BY cantidad_vendida DESC
            """)
            datos['productos_stock'] = cursor.fetchall()
        
        # Movimientos recientes de inventario
        cursor.execute("""
            SELECT TOP 20
                fd.descripcion,
                fd.cantidad,
                fd.precio_unitario,
                f.fecha,
                c.nombre as cliente,
                'Venta' as tipo_movimiento
            FROM factura_detalles fd
            JOIN facturas f ON fd.factura_id = f.id
            JOIN clientes c ON f.cliente_id = c.id
            WHERE f.estado != 'cancelada'
            ORDER BY f.fecha DESC
        """)
        datos['movimientos_recientes'] = cursor.fetchall()
        
        # Productos más vendidos (rotación de inventario)
        cursor.execute("""
            SELECT TOP 10
                fd.descripcion,
                SUM(fd.cantidad) as total_vendido,
                COUNT(DISTINCT f.id) as numero_ventas,
                SUM(fd.subtotal) as ingresos_generados,
                AVG(fd.precio_unitario) as precio_promedio
            FROM factura_detalles fd
            JOIN facturas f ON fd.factura_id = f.id
            WHERE f.fecha >= DATEADD(MONTH, -6, GETDATE()) AND f.estado != 'cancelada'
            GROUP BY fd.descripcion
            ORDER BY total_vendido DESC
        """)
        datos['rotacion_inventario'] = cursor.fetchall()
        
        # Valoración del inventario
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT fd.descripcion) as productos_diferentes,
                SUM(fd.cantidad) as unidades_totales_vendidas,
                SUM(fd.subtotal) as valor_total_ventas,
                AVG(fd.precio_unitario) as precio_promedio_general
            FROM factura_detalles fd
            JOIN facturas f ON fd.factura_id = f.id
            WHERE f.fecha >= DATEADD(MONTH, -12, GETDATE()) AND f.estado != 'cancelada'
        """)
        valoracion_result = cursor.fetchone()
        if valoracion_result:
            datos['valoracion_inventario'] = {
                'productos_diferentes': valoracion_result[0] or 0,
                'unidades_vendidas': valoracion_result[1] or 0,
                'valor_ventas': valoracion_result[2] or 0,
                'precio_promedio': valoracion_result[3] or 0
            }
        
        conn.close()
    
    return render_template('reportes/inventario.html', datos=datos)

@app.route('/reportes/dashboard_ejecutivo')
@login_required
def dashboard_ejecutivo():
    """Dashboard ejecutivo con métricas clave"""
    conn = get_db_connection()
    datos = {
        'kpis': {},
        'tendencias_ventas': [],
        'top_clientes': [],
        'performance_empleados': [],
        'alertas': []
    }
    
    if conn:
        cursor = conn.cursor()
        
        # KPIs principales
        # Ventas del mes actual vs mes anterior
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN MONTH(fecha) = MONTH(GETDATE()) AND YEAR(fecha) = YEAR(GETDATE()) THEN total ELSE 0 END) as ventas_mes_actual,
                SUM(CASE WHEN MONTH(fecha) = MONTH(DATEADD(MONTH, -1, GETDATE())) AND YEAR(fecha) = YEAR(DATEADD(MONTH, -1, GETDATE())) THEN total ELSE 0 END) as ventas_mes_anterior,
                COUNT(CASE WHEN MONTH(fecha) = MONTH(GETDATE()) AND YEAR(fecha) = YEAR(GETDATE()) THEN 1 END) as facturas_mes_actual,
                COUNT(CASE WHEN MONTH(fecha) = MONTH(DATEADD(MONTH, -1, GETDATE())) AND YEAR(fecha) = YEAR(DATEADD(MONTH, -1, GETDATE())) THEN 1 END) as facturas_mes_anterior
            FROM facturas
            WHERE estado != 'cancelada'
        """)
        kpi_result = cursor.fetchone()
        if kpi_result:
            ventas_actual = kpi_result[0] or 0
            ventas_anterior = kpi_result[1] or 1
            datos['kpis'] = {
                'ventas_mes_actual': ventas_actual,
                'ventas_mes_anterior': ventas_anterior,
                'crecimiento_ventas': round((ventas_actual - ventas_anterior) / ventas_anterior * 100, 2),
                'facturas_mes_actual': kpi_result[2] or 0,
                'facturas_mes_anterior': kpi_result[3] or 0
            }
        
        # Clientes nuevos vs leads convertidos
        cursor.execute("""
            SELECT 
                COUNT(*) as clientes_nuevos_mes
            FROM clientes
            WHERE MONTH(fecha_registro) = MONTH(GETDATE()) AND YEAR(fecha_registro) = YEAR(GETDATE())
        """)
        datos['kpis']['clientes_nuevos_mes'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM leads WHERE estado = 'convertido' 
            AND MONTH(fecha_conversion) = MONTH(GETDATE()) AND YEAR(fecha_conversion) = YEAR(GETDATE())
        """)
        datos['kpis']['leads_convertidos_mes'] = cursor.fetchone()[0]
        
        # Tendencias de ventas (últimos 6 meses)
        cursor.execute("""
            SELECT 
                DATENAME(MONTH, fecha) as mes,
                SUM(total) as ventas,
                COUNT(*) as cantidad_ventas
            FROM facturas
            WHERE fecha >= DATEADD(MONTH, -6, GETDATE()) AND estado != 'cancelada'
            GROUP BY YEAR(fecha), MONTH(fecha), DATENAME(MONTH, fecha)
            ORDER BY YEAR(fecha), MONTH(fecha)
        """)
        datos['tendencias_ventas'] = cursor.fetchall()
        
        # Top 5 clientes por ventas
        cursor.execute("""
            SELECT TOP 5
                c.nombre,
                SUM(f.total) as total_compras,
                COUNT(f.id) as numero_compras,
                MAX(f.fecha) as ultima_compra
            FROM clientes c
            JOIN facturas f ON c.id = f.cliente_id
            WHERE f.estado != 'cancelada' AND f.fecha >= DATEADD(MONTH, -12, GETDATE())
            GROUP BY c.nombre
            ORDER BY total_compras DESC
        """)
        datos['top_clientes'] = cursor.fetchall()
        
        # Performance de empleados (si tienes relación empleado-ventas)
        cursor.execute("""
            SELECT 
                u.nombre,
                COUNT(f.id) as facturas_generadas,
                SUM(f.total) as ventas_generadas
            FROM usuarios u
            LEFT JOIN facturas f ON u.id = f.usuario_id AND f.fecha >= DATEADD(MONTH, -3, GETDATE()) AND f.estado != 'cancelada'
            GROUP BY u.nombre
            ORDER BY ventas_generadas DESC
        """)
        datos['performance_empleados'] = cursor.fetchall()
        
        # Alertas automáticas
        alertas = []
        
        # Alerta: Facturas vencidas
        cursor.execute("""
            SELECT COUNT(*) FROM facturas 
            WHERE estado = 'pendiente' AND fecha < DATEADD(DAY, -30, GETDATE())
        """)
        facturas_vencidas = cursor.fetchone()[0]
        if facturas_vencidas > 0:
            alertas.append({
                'tipo': 'warning',
                'mensaje': f'{facturas_vencidas} facturas pendientes de pago con más de 30 días'
            })
        
        # Alerta: Leads sin contactar
        cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE estado = 'nuevo' AND fecha_creacion < DATEADD(DAY, -3, GETDATE())
        """)
        leads_sin_contactar = cursor.fetchone()[0]
        if leads_sin_contactar > 0:
            alertas.append({
                'tipo': 'info',
                'mensaje': f'{leads_sin_contactar} leads nuevos sin contactar por más de 3 días'
            })
        
        # Alerta: Crecimiento negativo
        if datos['kpis'].get('crecimiento_ventas', 0) < -10:
            alertas.append({
                'tipo': 'danger',
                'mensaje': f'Ventas han decrecido {abs(datos["kpis"]["crecimiento_ventas"])}% respecto al mes anterior'
            })
        
        datos['alertas'] = alertas
        
        conn.close()
    
    return render_template('reportes/dashboard_ejecutivo.html', datos=datos)




if __name__ == '__main__':
    app.run(debug=True)