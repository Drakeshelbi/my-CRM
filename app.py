# app.py - Aplicación Principal del ERP
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import pyodbc
from datetime import datetime, date
import hashlib
import requests
import json
from functools import wraps
from flask_moment import Moment

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

@app.route('/marketing/facebook', methods=['GET', 'POST'])
@login_required
def facebook_marketing():
    if request.method == 'POST':
        # Aquí implementarías la integración con Facebook Marketing API
        # Por ahora, simulamos el proceso
        
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        presupuesto = request.form['presupuesto']
        audiencia = request.form['audiencia']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO campanias_marketing (nombre, descripcion, plataforma, presupuesto, fecha_inicio, estado)
                VALUES (?, ?, 'Facebook', ?, GETDATE(), 'activa')
            """, (titulo, descripcion, presupuesto))
            conn.commit()
            conn.close()
            
            # Aquí llamarías a la API de Facebook
            # resultado = crear_campania_facebook(titulo, descripcion, presupuesto, audiencia)
            
            flash('Campaña de Facebook creada exitosamente', 'success')
            return redirect(url_for('marketing'))
    
    return render_template('facebook_marketing.html')

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


if __name__ == '__main__':
    app.run(debug=True)