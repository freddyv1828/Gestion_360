"""
Siembra clientes de ejemplo (fiscales y naturales) en la empresa indicada.

Uso:
    python scripts/seed_clients.py gestion360_j401234567
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.client_service import ClientService

SAMPLE_CLIENTS = [
    {"name": "Supermercado El Trigal, C.A.", "rif_cedula": "J-29887766-1", "client_type": "fiscal",
     "email": "compras@eltrigal.com", "phone": "0241-8451122", "address": "Av. Bolívar, Valencia",
     "credit_limit": "5000"},
    {"name": "Panadería La Espiga Dorada", "rif_cedula": "J-31122334-5", "client_type": "fiscal",
     "email": "laespiga@mail.com", "phone": "0212-7781234", "address": "Chacao, Caracas",
     "credit_limit": "2000"},
    {"name": "María José Pérez", "rif_cedula": "V-18456789", "client_type": "natural",
     "email": "mjperez@mail.com", "phone": "0414-5551234", "address": "Urb. Las Delicias, Maracay",
     "credit_limit": "300"},
    {"name": "Distribuidora Hermanos Rangel", "rif_cedula": "J-40011223-9", "client_type": "fiscal",
     "email": "ventas@hrangel.com", "phone": "0251-4123456", "address": "Zona Industrial II, Barquisimeto",
     "credit_limit": "8000"},
    {"name": "Carlos Giménez", "rif_cedula": "V-22334455", "client_type": "natural",
     "email": "cgimenez@mail.com", "phone": "0424-9871234", "address": "San Cristóbal, Táchira",
     "credit_limit": "500"},
]


def run(company_db_name):
    for c in SAMPLE_CLIENTS:
        ok, msg = ClientService.create_or_update_client(company_db_name, c, "seed@gestion360.com")
        print(("  OK  " if ok else "  SKIP") + f" {msg}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/seed_clients.py <company_db_name>")
        sys.exit(1)
    run(sys.argv[1])
