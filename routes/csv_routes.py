from flask import Blueprint, request, jsonify, render_template
import os
import csv
import tempfile
import logging
from datetime import datetime
from database.db_sqlite import get_db

logger = logging.getLogger(__name__)
csv_bp = Blueprint('csv', __name__)

def allowed_file(filename):
    """Verificar si el archivo es CSV"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

@csv_bp.route('/upload', methods=['GET'])
def upload_form():
    """Mostrar formulario de upload"""
    return render_template('upload.html')

@csv_bp.route('/upload', methods=['POST'])
def upload_csv():
    """Endpoint para subir CSV"""
    try:
        # Verificar que hay archivo
        if 'file' not in request.files:
            return jsonify({'error': 'No se proporcionó archivo'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Solo se permiten archivos CSV'}), 400
        
        # Guardar archivo temporalmente
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        file.save(temp_path)
        
        # Registrar upload en base de datos
        db = get_db()
        upload_id = db.execute("""
            INSERT INTO upload_logs (filename, file_size, status)
            VALUES (?, ?, 'processing')
        """, (file.filename, os.path.getsize(temp_path)))
        
        try:
            # Procesar CSV
            processed_rows = process_csv_file(temp_path, upload_id)
            
            # Actualizar log
            db.execute("""
                UPDATE upload_logs 
                SET status = 'completed', 
                    processed_rows = ?,
                    total_rows = ?
                WHERE id = ?
            """, (processed_rows, processed_rows, upload_id))
            
            return jsonify({
                'success': True,
                'message': f'CSV procesado exitosamente. {processed_rows} registros actualizados.',
                'upload_id': upload_id,
                'processed_rows': processed_rows
            }), 200
            
        except Exception as e:
            # Marcar como fallido
            db.execute("""
                UPDATE upload_logs 
                SET status = 'failed', 
                    error_message = ?
                WHERE id = ?
            """, (str(e), upload_id))
            
            logger.error(f"Error procesando CSV: {e}")
            return jsonify({'error': f'Error procesando CSV: {str(e)}'}), 400
            
        finally:
            # Limpiar archivo temporal
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error en upload: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

def process_csv_file(filepath, upload_id):
    """Procesar archivo CSV y actualizar base de datos"""
    db = get_db()
    processed_rows = 0
    
    with open(filepath, 'r', encoding='utf-8') as csvfile:
        # Detectar delimitador
        sample = csvfile.read(1024)
        csvfile.seek(0)
        
        delimiter = ','
        if ';' in sample and ',' not in sample:
            delimiter = ';'
        elif '\t' in sample and ',' not in sample and ';' not in sample:
            delimiter = '\t'
        
        # Leer CSV
        reader = csv.DictReader(csvfile, delimiter=delimiter)
        
        for row in reader:
            try:
                # Normalizar datos
                customer_id = row.get('customer_id', '').strip()
                if not customer_id:
                    continue
                
                # Insertar o actualizar cliente
                db.execute("""
                    INSERT OR REPLACE INTO customers 
                    (customer_id, name, email, phone, address, city, country, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    customer_id,
                    row.get('name', '').strip(),
                    row.get('email', '').strip().lower(),
                    row.get('phone', '').strip(),
                    row.get('address', '').strip(),
                    row.get('city', '').strip(),
                    row.get('country', '').strip(),
                    f"upload_{upload_id}"
                ))
                
                processed_rows += 1
                
            except Exception as e:
                logger.error(f"Error procesando fila: {e}")
                continue
    
    return processed_rows

@csv_bp.route('/uploads', methods=['GET'])
def list_uploads():
    """Listar todos los uploads"""
    db = get_db()
    
    uploads = db.execute("""
        SELECT id, filename, upload_date, processed_rows, total_rows, status
        FROM upload_logs
        ORDER BY upload_date DESC
        LIMIT 50
    """, fetchall=True)
    
    result = []
    for upload in uploads:
        result.append({
            'id': upload[0],
            'filename': upload[1],
            'upload_date': upload[2],
            'processed_rows': upload[3],
            'total_rows': upload[4],
            'status': upload[5]
        })
    
    return jsonify({'uploads': result})

@csv_bp.route('/customers', methods=['GET'])
def list_customers():
    """Listar clientes"""
    db = get_db()
    
    # Parámetros de paginación
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page
    
    # Contar total
    total = db.execute("SELECT COUNT(*) FROM customers", fetchone=True)[0]
    
    # Obtener clientes
    customers = db.execute("""
        SELECT id, customer_id, name, email, city, country, created_at
        FROM customers
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset), fetchall=True)
    
    result = []
    for customer in customers:
        result.append({
            'id': customer[0],
            'customer_id': customer[1],
            'name': customer[2],
            'email': customer[3],
            'city': customer[4],
            'country': customer[5],
            'created_at': customer[6]
        })
    
    return jsonify({
        'customers': result,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page
        }
    })

@csv_bp.route('/stats', methods=['GET'])
def get_stats():
    """Obtener estadísticas"""
    db = get_db()
    
    # Estadísticas básicas
    total_customers = db.execute(
        "SELECT COUNT(*) FROM customers", 
        fetchone=True
    )[0]
    
    total_uploads = db.execute(
        "SELECT COUNT(*) FROM upload_logs", 
        fetchone=True
    )[0]
    
    successful_uploads = db.execute(
        "SELECT COUNT(*) FROM upload_logs WHERE status = 'completed'", 
        fetchone=True
    )[0]
    
    # Clientes por ciudad
    customers_by_city = db.execute("""
        SELECT city, COUNT(*) as count 
        FROM customers 
        WHERE city IS NOT NULL AND city != ''
        GROUP BY city 
        ORDER BY count DESC 
        LIMIT 10
    """, fetchall=True)
    
    return jsonify({
        'customers': {
            'total': total_customers,
            'by_city': [{'city': city, 'count': count} for city, count in customers_by_city]
        },
        'uploads': {
            'total': total_uploads,
            'successful': successful_uploads,
            'failed': total_uploads - successful_uploads
        }
    })

@csv_bp.route('/load_categories', methods=['GET', 'POST'])
def load_categories():
    """Endpoint para cargar categorías (simulado)"""
    # Aquí iría la lógica para cargar categorías
    logger.info("🔄 Cargando categorías...")
    # Simulación de carga
    import time
    time.sleep(2)
    logger.info("✅ Categorías cargadas")
    return "Categorías cargadas - Funcionalidad en desarrollo", 200


@csv_bp.route('/load_products', methods=['GET', 'POST'])
def load_products():
    #form = UploadForm()
    #if form.validate_on_submit():
    #    file = form.file.data
    #    filename = file.filename
        #file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        #file.save(file_path)
    #    flash(f'File {filename} uploaded successfully!', 'success')
    #    return redirect(url_for('main.upload_file'))
    #return render_template('upload.html', form=form)
    return "Cargar productos - Funcionalidad en desarrollo", 200
