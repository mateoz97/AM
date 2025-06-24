#!/usr/bin/env python3
"""
Script para probar las APIs y verificar que los errores de Redis se han solucionado
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8001"

def test_api_endpoints():
    """Prueba varios endpoints para verificar que funcionan sin errores de Redis"""
    
    # Headers básicos
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Lista de endpoints para probar
    endpoints_to_test = [
        {'method': 'GET', 'url': '/api/orders/', 'description': 'Listar órdenes'},
        {'method': 'GET', 'url': '/api/orders/stats/', 'description': 'Estadísticas de órdenes'},
        {'method': 'GET', 'url': '/api/inventory/products/', 'description': 'Listar productos'},
        {'method': 'GET', 'url': '/api/settings/user-settings/', 'description': 'Configuraciones de usuario'},
    ]
    
    print("🧪 Iniciando pruebas de API...")
    print("=" * 50)
    
    for test in endpoints_to_test:
        try:
            print(f"\n📡 Probando: {test['description']}")
            print(f"   {test['method']} {BASE_URL}{test['url']}")
            
            if test['method'] == 'GET':
                response = requests.get(BASE_URL + test['url'], headers=headers, timeout=5)
            elif test['method'] == 'POST':
                response = requests.post(BASE_URL + test['url'], headers=headers, json=test.get('data', {}), timeout=5)
            
            print(f"   ✅ Status: {response.status_code}")
            
            if response.status_code < 400:
                print(f"   ✅ Respuesta exitosa")
            else:
                print(f"   ⚠️  Error HTTP: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error text: {response.text[:200]}...")
                    
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error de conexión: {str(e)}")
        except Exception as e:
            print(f"   ❌ Error inesperado: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🎯 Pruebas completadas")
    print("\nSi ves mensajes '✅ Respuesta exitosa' en lugar de errores 500,")
    print("significa que los errores de Redis se han solucionado correctamente.")

if __name__ == "__main__":
    test_api_endpoints()