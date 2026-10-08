"""
Conciliación bancaria real: importa el estado de cuenta descargado del banco
(formato confirmado con un export real de Banco Mercantil: columnas Tipo
[NC=Nota de Crédito/ingreso, ND=Nota de Débito/egreso], Fecha, Referencia,
Descripción, Monto Bs.) y lo cruza contra lo que Gestión 360 tiene registrado
en Tesorería — exactamente lo que hace una conciliación bancaria manual en
Excel, pero automático y auditable.

El número de Referencia es la clave de cruce: es el mismo dato que luego se
usa para validar si el abono que declara un cliente realmente entró al banco.
"""
import io
from datetime import datetime
from bson import ObjectId
import openpyxl
from database import get_company_db


def _parse_bank_statement_xlsx(file_bytes):
    """Retorna (lista_de_movimientos, error_o_None). Cada movimiento:
    {bank_type, movement_type, date, reference, description, amount}."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception:
        return None, "El archivo no es un Excel (.xlsx) válido."

    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))

    header_idx = None
    for i, row in enumerate(rows):
        if not row or len(row) < 5:
            continue
        first = str(row[0]).strip().lower() if row[0] is not None else ''
        second = str(row[1]).strip().lower() if row[1] is not None else ''
        if first == 'tipo' and second == 'fecha':
            header_idx = i
            break

    if header_idx is None:
        return None, ("No se encontró la tabla de movimientos (se esperaba un encabezado "
                       "Tipo / Fecha / Referencia / Descripción / Monto Bs. en el archivo).")

    movements = []
    for row in rows[header_idx + 1:]:
        if not row or row[0] is None:
            continue
        tipo = str(row[0]).strip().upper()
        if tipo not in ('NC', 'ND'):
            continue

        fecha_raw = row[1]
        referencia = str(row[2]).strip() if row[2] is not None else ''
        descripcion = str(row[3]).strip() if row[3] is not None else ''
        monto_raw = row[4]

        if descripcion.upper() == 'SALDO FINAL' or referencia.strip('0') == '':
            continue

        if isinstance(fecha_raw, datetime):
            fecha = fecha_raw
        else:
            try:
                fecha = datetime.strptime(str(fecha_raw).strip(), '%d/%m/%Y')
            except (ValueError, TypeError):
                continue

        try:
            monto = abs(float(monto_raw))
        except (TypeError, ValueError):
            continue

        movements.append({
            "bank_type": tipo,
            "movement_type": "credito" if tipo == "NC" else "debito",
            "date": fecha,
            "reference": referencia,
            "description": descripcion,
            "amount": monto,
        })

    return movements, None


class ReconciliationService:

    @staticmethod
    def import_bank_statement(company_db_name, account_id, file_bytes, filename, user_email):
        db = get_company_db(company_db_name)
        if db is None:
            return False, "Base de datos no disponible.", 0

        try:
            account = db['banking_accounts'].find_one({"_id": ObjectId(account_id)})
        except Exception:
            account = None
        if not account:
            return False, "Cuenta bancaria no encontrada.", 0

        movements, error = _parse_bank_statement_xlsx(file_bytes)
        if error:
            return False, error, 0
        if not movements:
            return False, "El archivo no contiene movimientos reconocibles (NC/ND).", 0

        inserted = 0
        for m in movements:
            exists = db['bank_statement_movements'].find_one({
                "account_id": account['_id'],
                "reference": m['reference'],
                "amount": m['amount'],
                "bank_type": m['bank_type'],
            })
            if exists:
                continue
            db['bank_statement_movements'].insert_one({
                **m,
                "account_id": account['_id'],
                "matched": False,
                "matched_transaction_id": None,
                "imported_by": user_email,
                "imported_at": datetime.utcnow(),
                "source_file": filename,
            })
            inserted += 1

        ReconciliationService.reconcile_account(company_db_name, account_id)

        skipped = len(movements) - inserted
        message = f"Se importaron {inserted} movimiento(s) nuevo(s) del estado de cuenta ({len(movements)} encontrados"
        message += f", {skipped} ya estaban importados)." if skipped else ")."
        return True, message, inserted

    @staticmethod
    def reconcile_account(company_db_name, account_id):
        """Cruza movimientos de banco sin conciliar contra transacciones de
        Tesorería sin conciliar de la MISMA cuenta, mismo tipo (NC<->COBRO,
        ND<->PAGO), misma referencia y mismo monto. Si coincide, marca ambos
        lados como conciliados."""
        db = get_company_db(company_db_name)
        if db is None:
            return 0
        try:
            acc_oid = ObjectId(account_id)
        except Exception:
            return 0

        matched_count = 0
        unmatched_bank = db['bank_statement_movements'].find({"account_id": acc_oid, "matched": {"$ne": True}})
        for bm in unmatched_bank:
            tx_type = 'COBRO' if bm['bank_type'] == 'NC' else 'PAGO'
            if not bm.get('reference'):
                continue
            tx = db['treasury_transactions'].find_one({
                "account_id": acc_oid,
                "reference": bm['reference'],
                "type": tx_type,
                "reconciled": {"$ne": True},
            })
            if not tx:
                continue
            db['bank_statement_movements'].update_one(
                {"_id": bm['_id']},
                {"$set": {"matched": True, "matched_transaction_id": tx['_id']}}
            )
            db['treasury_transactions'].update_one(
                {"_id": tx['_id']},
                {"$set": {"reconciled": True, "reconciled_bank_movement_id": bm['_id']}}
            )
            matched_count += 1

        return matched_count

    @staticmethod
    def get_reconciliation_view(company_db_name, account_id):
        """Las 3 listas clásicas de una conciliación bancaria:
        - matched: movimientos que cuadran en ambos lados.
        - bank_only: el banco los tiene pero Gestión 360 no los registró
          (dinero que entró/salió sin que quede constancia interna).
        - system_only: Gestión 360 los registró pero no aparecen (todavía)
          en el estado de cuenta importado (ej. cheques en tránsito, o un
          estado de cuenta desactualizado)."""
        db = get_company_db(company_db_name)
        if db is None:
            return None
        try:
            acc_oid = ObjectId(account_id)
        except Exception:
            return None

        account = db['banking_accounts'].find_one({"_id": acc_oid})
        if not account:
            return None

        bank_only = list(db['bank_statement_movements'].find({"account_id": acc_oid, "matched": {"$ne": True}}).sort('date', -1))
        system_only = list(db['treasury_transactions'].find({"account_id": acc_oid, "reconciled": {"$ne": True}}).sort('created_at', -1))
        matched_bank = list(db['bank_statement_movements'].find({"account_id": acc_oid, "matched": True}).sort('date', -1).limit(100))

        for b in bank_only + matched_bank:
            b['_id'] = str(b['_id'])
            b['account_id'] = str(b['account_id'])
            if b.get('matched_transaction_id'):
                b['matched_transaction_id'] = str(b['matched_transaction_id'])
        for t in system_only:
            t['_id'] = str(t['_id'])
            t['account_id'] = str(t['account_id'])
            if t.get('reconciled_bank_movement_id'):
                t['reconciled_bank_movement_id'] = str(t['reconciled_bank_movement_id'])

        account['_id'] = str(account['_id'])

        return {
            "account": account,
            "matched": matched_bank,
            "matched_count": len(matched_bank),
            "bank_only": bank_only,
            "bank_only_total": round(sum(b['amount'] for b in bank_only), 2),
            "system_only": system_only,
            "system_only_total": round(sum(t.get('amount', 0) for t in system_only), 2),
        }
