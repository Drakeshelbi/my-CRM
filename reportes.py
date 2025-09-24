
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

