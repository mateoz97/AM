# Configuración GCP para Proyecto ADB
## Proyecto: gcp-vm-357012

### 1. Requisitos previos completados ✅
- [x] Proyecto GCP creado: `gcp-vm-357012`
- [x] APIs habilitadas requeridas
- [x] Configuración inicial de gcloud

### 2. Próximos pasos para deployment

#### Habilitar APIs necesarias:
```bash
gcloud services enable appengine.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable vpcaccess.googleapis.com
gcloud services enable cloudsql.googleapis.com
gcloud services enable storage.googleapis.com
```

#### Ejecutar deployment automatizado:
```bash
cd /home/teo/Documents/ADB
chmod +x deploy/gcp/deploy.sh
./deploy/gcp/deploy.sh
```

### 3. Configuración manual alternativa

#### Crear instancia Redis Memorystore:
```bash
gcloud redis instances create adb-redis-prod \
    --size=1 \
    --region=us-central1 \
    --redis-version=redis_6_x \
    --network=default \
    --tier=basic
```

#### Crear VPC Access Connector:
```bash
gcloud compute networks vpc-access connectors create redis-connector \
    --region=us-central1 \
    --subnet=default \
    --subnet-project=gcp-vm-357012 \
    --min-instances=2 \
    --max-instances=3 \
    --machine-type=e2-micro
```

#### Deploy aplicación:
```bash
gcloud app deploy deploy/gcp/app.yaml
```

### 4. Variables de entorno a configurar

Actualizar las siguientes variables en `app.yaml` antes del deployment:
- `SECRET_KEY`: Clave secreta Django
- `REDIS_PASSWORD`: Password de Redis (si se configura)
- `DATABASE_URL`: Conexión a Cloud SQL (si se usa)

### 5. Monitoreo

El archivo `monitoring.yaml` incluye configuración para:
- Alertas de Redis
- Métricas de rendimiento
- Monitoreo de conexiones

### 6. Archivos configurados para el proyecto

- `app.yaml`: Configuración App Engine
- `.env.gcp.example`: Variables de entorno para GCP
- `deploy.sh`: Script automatizado de deployment
- `requirements-gcp.txt`: Dependencias para GCP
- `monitoring.yaml`: Configuración de monitoreo