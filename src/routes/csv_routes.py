from flask import Blueprint, request, jsonify, render_template
import os
import csv
import tempfile
from datetime import datetime
from database.db_manager import get_db
from shared.decorators import api_token_required
from shared.services import import_service
from utils.logger_factory import get_api_logger

logger = get_api_logger(__name__)
csv_bp = Blueprint('csv', __name__)

_XLSX_EXTENSION = 'xlsx'

def allowed_file(filename):
    """Verificar si el archivo es CSV"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'


def allowed_xlsx_file(filename):
    """Verificar si el archivo es Excel (.xlsx)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == _XLSX_EXTENSION

@csv_bp.route('/upload', methods=['GET'])
def upload_form():
    """Mostrar formulario de upload.

    El formulario HTML se sirve publicamente; la autenticacion se realiza
    via JavaScript usando el token guardado en localStorage. Los endpoints
    POST que realizan la importacion siempre requieren JWT.
    """
    return render_template('upload.html')

@csv_bp.route('/upload', methods=['POST'])
@api_token_required
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
@api_token_required
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

@csv_bp.route('/stats', methods=['GET'])
@api_token_required
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

def _handle_xlsx_upload(import_fn, upload_type: str):
    """Common helper to receive, save and process an uploaded .xlsx file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No se proporcionó archivo'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No se seleccionó archivo'}), 400

    if not allowed_xlsx_file(file.filename):
        return jsonify({'error': 'Solo se permiten archivos Excel (.xlsx)'}), 400

    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(
        temp_dir,
        f"upload_{upload_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
    )
    file.save(temp_path)

    db = get_db()
    upload_id = db.execute(
        """
        INSERT INTO upload_logs (filename, original_filename, file_size, status)
        VALUES (?, ?, ?, 'processing')
        """,
        (file.filename, file.filename, os.path.getsize(temp_path)),
    )

    try:
        summary = import_fn(temp_path, upload_id)
        status = 'completed' if summary['errors'] == 0 else 'partial'

        db.execute(
            """
            UPDATE upload_logs
            SET status = ?,
                processed_rows = ?,
                total_rows = ?,
                completed_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                summary['processed_rows'],
                summary['processed_rows'],
                upload_id,
            ),
        )

        return jsonify({
            'success': True,
            'message': (
                f"Importación de {upload_type} finalizada. "
                f"Creados: {summary['created']}, "
                f"Actualizados: {summary['updated']}, "
                f"Errores: {summary['errors']}."
            ),
            'upload_id': upload_id,
            **summary,
        }), 200

    except ValueError as exc:
        db.execute(
            """
            UPDATE upload_logs
            SET status = 'failed', error_message = ?
            WHERE id = ?
            """,
            (str(exc), upload_id),
        )
        logger.error("Error validando archivo %s: %s", upload_type, exc)
        return jsonify({'error': f'Error procesando archivo: {str(exc)}'}), 400

    except Exception as exc:
        db.execute(
            """
            UPDATE upload_logs
            SET status = 'failed', error_message = ?
            WHERE id = ?
            """,
            (str(exc), upload_id),
        )
        logger.exception("Error procesando archivo %s", upload_type)
        return jsonify({'error': 'Error interno del servidor'}), 500

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@csv_bp.route('/load_categories', methods=['GET', 'POST'])
@api_token_required
def load_categories():
    """Upload and import categories from an Excel (.xlsx) file.

    POST expects a multipart/form-data with a 'file' field.
    The workbook must contain a sheet named 'categories' with columns:
    codigo, nombre, descripcion, parent_name (optional).
    """
    if request.method == 'GET':
        return jsonify({
            'description': 'Endpoint para cargar categorías desde Excel (.xlsx)',
            'method': 'POST',
            'content_type': 'multipart/form-data',
            'sheet_name': 'categories',
            'columns': {
                'required': ['codigo', 'nombre', 'descripcion'],
                'optional': ['parent_name'],
            },
        }), 200

    return _handle_xlsx_upload(
        import_service.import_categories_from_xlsx,
        'categorías',
    )


@csv_bp.route('/load_products', methods=['GET', 'POST'])
@api_token_required
def load_products():
    """Upload and import products from an Excel (.xlsx) file.

    POST expects a multipart/form-data with a 'file' field.
    The workbook must contain a sheet named 'products' with columns:
    nombre, descripcion, precio, category_name, stock_inicial (optional).
    """
    if request.method == 'GET':
        return jsonify({
            'description': 'Endpoint para cargar productos desde Excel (.xlsx)',
            'method': 'POST',
            'content_type': 'multipart/form-data',
            'sheet_name': 'products',
            'columns': {
                'required': ['nombre', 'descripcion', 'precio', 'category_name'],
                'optional': ['stock_inicial'],
            },
        }), 200

    return _handle_xlsx_upload(
        import_service.import_products_from_xlsx,
        'productos',
    )
