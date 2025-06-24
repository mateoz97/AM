# Utility Scripts

## 📁 Scripts Disponibles

### 🧪 Testing & Development
- **`test_api.py`** - Script para probar endpoints de la API
- **`test_orders.py`** - Script para probar funcionalidad de órdenes

### 🔧 Deployment
- **`../deploy/gcp/deploy.sh`** - Deployment completo a GCP
- **`../deploy/gcp/startup.sh`** - Encender servicios GCP
- **`../deploy/gcp/shutdown.sh`** - Apagar servicios GCP (ahorrar costos)

## 🚀 Uso

### Testing local:
```bash
# Desde el directorio raíz del proyecto
cd /home/teo/Documents/ADB
python scripts/test_api.py
python scripts/test_orders.py
```

### GCP Management:
```bash
# Encender servicios (desarrollo)
./deploy/gcp/startup.sh

# Deployment completo
./deploy/gcp/deploy.sh

# Apagar servicios (ahorrar costos)
./deploy/gcp/shutdown.sh
```