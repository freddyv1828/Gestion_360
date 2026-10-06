"""
Siembra cupones de ejemplo para probar descuentos en facturación.

Uso:
    python scripts/seed_coupons.py gestion360_j401234567
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.coupon_service import CouponService

SAMPLE_COUPONS = [
    {"code": "BIENVENIDA10", "discount_type": "percentage", "discount_value": "10", "usage_limit": "0"},
    {"code": "FLETE5", "discount_type": "fixed", "discount_value": "5", "usage_limit": "0"},
]


def run(company_db_name):
    for c in SAMPLE_COUPONS:
        ok, msg = CouponService.create_coupon(company_db_name, c, "seed@gestion360.com")
        print(("  OK  " if ok else "  SKIP") + f" {msg}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/seed_coupons.py <company_db_name>")
        sys.exit(1)
    run(sys.argv[1])
