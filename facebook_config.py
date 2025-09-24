# facebook_config.py - Configuración para Facebook Marketing API
import requests
import json
from datetime import datetime
from flask import session, flash

class FacebookMarketingAPI:
    def __init__(self, access_token, app_id, app_secret):
        self.access_token = access_token
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://graph.facebook.com/v18.0"
        
    def verificar_token(self):
        """Verifica si el token de acceso es válido"""
        url = f"{self.base_url}/me"
        params = {
            'access_token': self.access_token,
            'fields': 'id,name'
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.json()
        except Exception as e:
            return False, str(e)
    
    def obtener_cuentas_publicitarias(self):
        """Obtiene las cuentas publicitarias disponibles"""
        url = f"{self.base_url}/me/adaccounts"
        params = {
            'access_token': self.access_token,
            'fields': 'id,name,account_status,currency,timezone_name'
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return True, response.json()['data']
            else:
                return False, response.json()
        except Exception as e:
            return False, str(e)
    
    def crear_campania(self, ad_account_id, nombre, objetivo, presupuesto_diario, estado='PAUSED'):
        """Crea una nueva campaña publicitaria"""
        url = f"{self.base_url}/act_{ad_account_id}/campaigns"
        
        data = {
            'access_token': self.access_token,
            'name': nombre,
            'objective': objetivo,  # REACH, TRAFFIC, CONVERSIONS, etc.
            'status': estado,
            'daily_budget': int(presupuesto_diario * 100),  # Facebook usa centavos
            'buying_type': 'AUCTION'
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.json()
        except Exception as e:
            return False, str(e)
    
    def crear_conjunto_anuncios(self, ad_account_id, campaign_id, nombre, targeting, presupuesto_diario):
        """Crea un conjunto de anuncios"""
        url = f"{self.base_url}/act_{ad_account_id}/adsets"
        
        data = {
            'access_token': self.access_token,
            'name': nombre,
            'campaign_id': campaign_id,
            'daily_budget': int(presupuesto_diario * 100),
            'billing_event': 'IMPRESSIONS',
            'optimization_goal': 'REACH',
            'targeting': json.dumps(targeting),
            'status': 'PAUSED'
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.json()
        except Exception as e:
            return False, str(e)
    
    def crear_anuncio(self, ad_account_id, adset_id, nombre, creative_id):
        """Crea un anuncio"""
        url = f"{self.base_url}/act_{ad_account_id}/ads"
        
        data = {
            'access_token': self.access_token,
            'name': nombre,
            'adset_id': adset_id,
            'creative': json.dumps({'creative_id': creative_id}),
            'status': 'PAUSED'
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.json()
        except Exception as e:
            return False, str(e)
    
    def obtener_estadisticas_campania(self, campaign_id, fechas=None):
        """Obtiene estadísticas de una campaña"""
        url = f"{self.base_url}/{campaign_id}/insights"
        
        params = {
            'access_token': self.access_token,
            'fields': 'impressions,clicks,spend,ctr,cpm,reach,frequency'
        }
        
        if fechas:
            params['time_range'] = json.dumps(fechas)
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return True, response.json()['data']
            else:
                return False, response.json()
        except Exception as e:
            return False, str(e)

# Configuraciones adicionales para el archivo app.py
def init_facebook_marketing():
    """Inicializa la configuración de Facebook Marketing"""
    # Estas credenciales deberían estar en variables de entorno
    FACEBOOK_CONFIG = {
        'app_id': 'TU_APP_ID_DE_FACEBOOK',
        'app_secret': 'TU_APP_SECRET_DE_FACEBOOK',
        'access_token': 'TU_ACCESS_TOKEN_DE_FACEBOOK',
        'webhook_verify_token': 'TU_WEBHOOK_VERIFY_TOKEN'
    }
    return FACEBOOK_CONFIG

# Funciones para integrar en app.py

def crear_campania_facebook_completa(datos_campania, conn):
    """
    Crea una campaña completa en Facebook y la guarda en la base de datos
    """
    try:
        # Inicializar API de Facebook
        config = init_facebook_marketing()
        fb_api = FacebookMarketingAPI(
            config['access_token'],
            config['app_id'],
            config['app_secret']
        )
        
        # Verificar token
        valido, info = fb_api.verificar_token()
        if not valido:
            return False, f"Token inválido: {info}"
        
        # Obtener cuentas publicitarias
        exito, cuentas = fb_api.obtener_cuentas_publicitarias()
        if not exito:
            return False, f"Error obteniendo cuentas: {cuentas}"
        
        if not cuentas:
            return False, "No se encontraron cuentas publicitarias"
        
        # Usar la primera cuenta disponible
        ad_account_id = cuentas[0]['id'].replace('act_', '')
        
        # Crear campaña
        exito, campania = fb_api.crear_campania(
            ad_account_id,
            datos_campania['nombre'],
            datos_campania['objetivo'],
            float(datos_campania['presupuesto_diario'])
        )
        
        if not exito:
            return False, f"Error creando campaña: {campania}"
        
        campaign_id = campania['id']
        
        # Configurar targeting
        targeting = {
            "geo_locations": {
                "countries": datos_campania.get('paises', ['MX'])
            },
            "age_min": datos_campania.get('edad_min', 18),
            "age_max": datos_campania.get('edad_max', 65)
        }
        
        if 'intereses' in datos_campania:
            targeting['interests'] = datos_campania['intereses']
        
        # Crear conjunto de anuncios
        exito, adset = fb_api.crear_conjunto_anuncios(
            ad_account_id,
            campaign_id,
            f"{datos_campania['nombre']} - AdSet",
            targeting,
            float(datos_campania['presupuesto_diario'])
        )
        
        if not exito:
            return False, f"Error creando conjunto de anuncios: {adset}"
        
        # Guardar en la base de datos
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO campanias_marketing (
                nombre, descripcion, plataforma, presupuesto, estado, 
                fecha_inicio, facebook_campaign_id, facebook_adset_id,
                objetivo, targeting_config, usuario_id
            ) VALUES (?, ?, 'Facebook', ?, 'activa', GETDATE(), ?, ?, ?, ?, ?)
        """, (
            datos_campania['nombre'],
            datos_campania['descripcion'],
            datos_campania['presupuesto_diario'],
            campaign_id,
            adset['id'],
            datos_campania['objetivo'],
            json.dumps(targeting),
            session['user_id']
        ))
        
        conn.commit()
        
        return True, {
            'campaign_id': campaign_id,
            'adset_id': adset['id'],
            'message': 'Campaña creada exitosamente en Facebook'
        }
        
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"

def sincronizar_estadisticas_facebook(conn):
    """
    Sincroniza las estadísticas de Facebook con la base de datos
    """
    try:
        config = init_facebook_marketing()
        fb_api = FacebookMarketingAPI(
            config['access_token'],
            config['app_id'],
            config['app_secret']
        )
        
        cursor = conn.cursor()
        
        # Obtener campañas de Facebook desde la base de datos
        cursor.execute("""
            SELECT id, facebook_campaign_id 
            FROM campanias_marketing 
            WHERE plataforma = 'Facebook' AND facebook_campaign_id IS NOT NULL
        """)
        
        campanias = cursor.fetchall()
        
        for campania_id, fb_campaign_id in campanias:
            # Obtener estadísticas de Facebook
            exito, stats = fb_api.obtener_estadisticas_campania(fb_campaign_id)
            
            if exito and stats:
                stat = stats[0]  # Tomar la primera estadística
                
                # Actualizar o insertar estadísticas
                cursor.execute("""
                    MERGE campanias_estadisticas AS target
                    USING (SELECT ? as campania_id) AS source
                    ON target.campania_id = source.campania_id
                    WHEN MATCHED THEN
                        UPDATE SET 
                            impresiones = ?,
                            clics = ?,
                            gasto = ?,
                            ctr = ?,
                            cpm = ?,
                            alcance = ?,
                            fecha_actualizacion = GETDATE()
                    WHEN NOT MATCHED THEN
                        INSERT (campania_id, impresiones, clics, gasto, ctr, cpm, alcance, fecha_actualizacion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE());
                """, (
                    campania_id,
                    stat.get('impressions', 0),
                    stat.get('clicks', 0),
                    float(stat.get('spend', 0)),
                    float(stat.get('ctr', 0)),
                    float(stat.get('cpm', 0)),
                    stat.get('reach', 0),
                    campania_id,
                    stat.get('impressions', 0),
                    stat.get('clicks', 0),
                    float(stat.get('spend', 0)),
                    float(stat.get('ctr', 0)),
                    float(stat.get('cpm', 0)),
                    stat.get('reach', 0)
                ))
        
        conn.commit()
        return True, "Estadísticas sincronizadas correctamente"
        
    except Exception as e:
        return False, f"Error sincronizando estadísticas: {str(e)}"

# Webhook para recibir eventos de Facebook
def procesar_webhook_facebook(data):
    """
    Procesa los webhooks de Facebook para eventos como nuevos leads
    """
    try:
        if 'entry' in data:
            for entry in data['entry']:
                if 'changes' in entry:
                    for change in entry['changes']:
                        if change['field'] == 'leadgen':
                            # Procesar nuevo lead
                            leadgen_id = change['value']['leadgen_id']
                            form_id = change['value']['form_id']
                            
                            # Aquí deberías obtener los datos del lead usando la API
                            # y guardarlo en tu base de datos
                            procesar_nuevo_lead_facebook(leadgen_id, form_id)
        
        return True
    except Exception as e:
        print(f"Error procesando webhook: {e}")
        return False

def procesar_nuevo_lead_facebook(leadgen_id, form_id):
    """
    Procesa un nuevo lead de Facebook y lo guarda en la base de datos
    """
    try:
        config = init_facebook_marketing()
        fb_api = FacebookMarketingAPI(
            config['access_token'],
            config['app_id'],
            config['app_secret']
        )
        
        # Obtener datos del lead
        url = f"{fb_api.base_url}/{leadgen_id}"
        params = {
            'access_token': fb_api.access_token,
            'fields': 'id,created_time,field_data'
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            lead_data = response.json()
            
            # Extraer información del lead
            field_data = lead_data.get('field_data', [])
            lead_info = {}
            
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
            
            # Guardar en la base de datos
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO leads (nombre, email, telefono, origen, estado, fecha_creacion, facebook_lead_id)
                    VALUES (?, ?, ?, 'Facebook', 'nuevo', GETDATE(), ?)
                """, (
                    lead_info.get('nombre', ''),
                    lead_info.get('email', ''),
                    lead_info.get('telefono', ''),
                    leadgen_id
                ))
                conn.commit()
                conn.close()
                
                return True
        
        return False
        
    except Exception as e:
        print(f"Error procesando lead de Facebook: {e}")
        return False