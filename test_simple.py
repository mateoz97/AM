#!/usr/bin/env python3
"""
Script simple para probar WebSockets sin navegador
"""

import asyncio
import websockets
import json
import requests
import sys

# Configuración
SERVER_URL = "127.0.0.1:8000"
USERNAME = "test_user"
PASSWORD = "password123"
BUSINESS_ID = 1


async def test_websocket():
    print("🧪 PRUEBA WEBSOCKET - SISTEMA DE ÓRDENES")
    print("=" * 50)
    
    # Paso 1: Obtener token JWT
    print("1️⃣ Obteniendo token JWT...")
    try:
        login_response = requests.post(
            f"http://{SERVER_URL}/api/auth/login/",
            json={"username": USERNAME, "password": PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            access_token = token_data.get('access')
            print(f"✅ Token obtenido: {access_token[:20]}...")
        else:
            print(f"❌ Error obteniendo token: {login_response.status_code}")
            print(f"   Respuesta: {login_response.text}")
            return
            
    except Exception as e:
        print(f"❌ Error conectando al servidor HTTP: {e}")
        print("   ¿Está ejecutándose 'python manage.py runserver'?")
        return
    
    # Paso 2: Conectar WebSocket
    print("\n2️⃣ Conectando WebSocket...")
    ws_url = f"ws://{SERVER_URL}/ws/orders/{BUSINESS_ID}/?token={access_token}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ Conexión WebSocket establecida")
            
            # Paso 3: Enviar mensaje de prueba
            print("\n3️⃣ Enviando mensajes de prueba...")
            
            # Ping
            ping_message = {"type": "ping", "timestamp": "2024-01-01T12:00:00Z"}
            await websocket.send(json.dumps(ping_message))
            print(f"📤 Enviado: {ping_message}")
            
            # Esperar respuesta
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                print(f"📥 Recibido: {response_data}")
                
                if response_data.get('type') == 'initial_data':
                    print("✅ Datos iniciales recibidos correctamente")
                
            except asyncio.TimeoutError:
                print("⏰ Timeout esperando respuesta")
            except json.JSONDecodeError:
                print(f"📥 Respuesta raw: {response}")
            
            # Solicitar órdenes
            orders_message = {"type": "get_orders"}
            await websocket.send(json.dumps(orders_message))
            print(f"📤 Enviado: {orders_message}")
            
            # Escuchar respuestas adicionales
            print("\n4️⃣ Escuchando respuestas (5 segundos)...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    print(f"📥 Recibido: {response_data}")
                    
            except asyncio.TimeoutError:
                print("⏰ Timeout - finalizando prueba")
            except json.JSONDecodeError:
                print(f"📥 Respuesta raw final: {response}")
            
            print("\n✅ Prueba de WebSocket completada exitosamente")
            
    except websockets.exceptions.ConnectionRefused:
        print("❌ Conexión WebSocket rechazada")
        print("   ¿Está ejecutándose 'python manage.py runserver'?")
        print("   ¿El token JWT es válido?")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Estado HTTP inválido: {e.status_code}")
        if e.status_code == 403:
            print("   Problema de autenticación o permisos")
        elif e.status_code == 404:
            print("   Ruta WebSocket no encontrada")
    except Exception as e:
        print(f"❌ Error WebSocket: {e}")
        print(f"   Tipo: {type(e).__name__}")


if __name__ == "__main__":
    print("Instalando dependencias si es necesario...")
    try:
        import websockets
        import requests
    except ImportError:
        print("Instalando websockets...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "requests"])
        import websockets
        import requests
    
    asyncio.run(test_websocket())