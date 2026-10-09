"""Configuración común de pruebas: el límite de pedidos se desactiva salvo en test_security."""
import os
os.environ.setdefault('DOTS_DISABLE_RATE_LIMIT', '1')
