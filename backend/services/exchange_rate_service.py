import requests
from services.financial_service import FinancialService

BCV_API_BASE_URL = "https://ve.dolarapi.com/v1"
BCV_CURRENCY_ENDPOINTS = {
    "VES": "dolares/oficial",
    "EUR": "euros/oficial",
}


def fetch_bcv_rate(currency):
    """
    Consulta la tasa oficial BCV (dolarapi.com) para 'VES' (USD->Bs) o 'EUR' (EUR->Bs).
    Retorna (ok, valor_o_mensaje_error).
    """
    endpoint = BCV_CURRENCY_ENDPOINTS.get(currency)
    if not endpoint:
        return False, f"Moneda '{currency}' no soportada para tasa BCV automática."

    try:
        response = requests.get(f"{BCV_API_BASE_URL}/{endpoint}", timeout=10)
        response.raise_for_status()
        data = response.json()
        rate = data.get("promedio")
        if not rate:
            return False, "La API de tasa BCV no devolvió un valor válido."
        return True, float(rate)
    except requests.RequestException as e:
        return False, f"No se pudo contactar la API de tasa BCV: {e}"
    except (ValueError, TypeError):
        return False, "La API de tasa BCV devolvió un formato inesperado."


class ExchangeRateService:

    @staticmethod
    def sync_bcv_rates(company_db_name, user_email):
        """
        Obtiene USD->Bs (VES) y EUR->Bs desde la API oficial BCV y las guarda como
        nuevas tasas de cambio de la empresa (fuente 'bcv_auto').
        Retorna (ok, mensaje).
        """
        results = []
        any_success = False

        for currency in ("VES", "EUR"):
            ok, value = fetch_bcv_rate(currency)
            if not ok:
                results.append(f"{currency}: {value}")
                continue

            saved_ok, saved_msg = FinancialService.set_exchange_rate(
                company_db_name, currency, value, user_email, source="bcv_auto"
            )
            if saved_ok:
                any_success = True
                results.append(f"{currency}: {value:.4f} Bs (BCV)")
            else:
                results.append(f"{currency}: {saved_msg}")

        message = "Tasas BCV sincronizadas — " + " · ".join(results)
        return any_success, message
