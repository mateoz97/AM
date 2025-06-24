#!/bin/bash
# Script para apagar todos los servicios de GCP y ahorrar costos
# ============================================================

set -e

echo "🛑 Iniciando proceso de apagado de servicios GCP..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
REDIS_INSTANCE_NAME="adb-redis-prod"
VPC_CONNECTOR_NAME="redis-connector"
SUBNET_NAME="vpc-connector-subnet"

echo -e "${BLUE}📋 Proyecto: ${PROJECT_ID}${NC}"
echo -e "${BLUE}📋 Región: ${REGION}${NC}"

# Función para confirmar acción
confirm_action() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    read -p "¿Continuar? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Operación cancelada${NC}"
        exit 1
    fi
}

# Paso 1: Gestionar App Engine
echo -e "\n${YELLOW}📋 Paso 1: Gestionando App Engine...${NC}"

# Listar versiones activas
ACTIVE_VERSIONS=$(gcloud app versions list --filter="traffic_split>0" --format="value(version.id,service)" 2>/dev/null)

if [ -n "$ACTIVE_VERSIONS" ]; then
    echo -e "${YELLOW}⚠️  Versiones activas encontradas:${NC}"
    echo "$ACTIVE_VERSIONS"
    
    echo -e "${BLUE}ℹ️  App Engine encontrado pero NO se puede apagar completamente:${NC}"
    echo -e "${BLUE}   • App Engine requiere al menos 1 versión activa${NC}"
    echo -e "${BLUE}   • Auto-scaling solo cobra por uso real${NC}"
    echo -e "${BLUE}   • Sin visitas = costos casi $0${NC}"
    
    echo -e "${GREEN}✅ App Engine se mantendrá activo (costo mínimo sin tráfico)${NC}"
    echo -e "${GREEN}   Para ahorrar costos: simplemente no visites la URL${NC}"
else
    echo -e "${GREEN}✅ No hay versiones activas de App Engine${NC}"
fi

# Paso 2: Eliminar VPC Access Connector
echo -e "\n${YELLOW}📋 Paso 2: Eliminando VPC Access Connector...${NC}"

if gcloud compute networks vpc-access connectors describe $VPC_CONNECTOR_NAME --region=$REGION &>/dev/null; then
    confirm_action "Eliminar VPC Access Connector ($VPC_CONNECTOR_NAME)"
    
    echo -e "${YELLOW}🗑️  Eliminando VPC Access Connector...${NC}"
    gcloud compute networks vpc-access connectors delete $VPC_CONNECTOR_NAME --region=$REGION --quiet
    echo -e "${GREEN}✅ VPC Access Connector eliminado${NC}"
else
    echo -e "${GREEN}✅ VPC Access Connector no existe${NC}"
fi

# Paso 3: Eliminar instancia de Redis
echo -e "\n${YELLOW}📋 Paso 3: Eliminando instancia de Redis...${NC}"

if gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION &>/dev/null; then
    confirm_action "Eliminar instancia de Redis ($REDIS_INSTANCE_NAME). ⚠️  SE PERDERÁN TODOS LOS DATOS DE CACHE."
    
    echo -e "${YELLOW}🗑️  Eliminando instancia de Redis...${NC}"
    gcloud redis instances delete $REDIS_INSTANCE_NAME --region=$REGION --quiet
    echo -e "${GREEN}✅ Instancia de Redis eliminada${NC}"
else
    echo -e "${GREEN}✅ Instancia de Redis no existe${NC}"
fi

# Paso 4: Eliminar subnet personalizada
echo -e "\n${YELLOW}📋 Paso 4: Eliminando subnet personalizada...${NC}"

if gcloud compute networks subnets describe $SUBNET_NAME --region=$REGION &>/dev/null; then
    confirm_action "Eliminar subnet personalizada ($SUBNET_NAME)"
    
    echo -e "${YELLOW}🗑️  Eliminando subnet...${NC}"
    gcloud compute networks subnets delete $SUBNET_NAME --region=$REGION --quiet
    echo -e "${GREEN}✅ Subnet eliminada${NC}"
else
    echo -e "${GREEN}✅ Subnet personalizada no existe${NC}"
fi

# Paso 5: Listar otros recursos que generan costos
echo -e "\n${YELLOW}📋 Paso 5: Verificando otros recursos...${NC}"

# Verificar instancias de Compute Engine
COMPUTE_INSTANCES=$(gcloud compute instances list --format="value(name,zone)" 2>/dev/null)
if [ -n "$COMPUTE_INSTANCES" ]; then
    echo -e "${YELLOW}⚠️  Instancias de Compute Engine encontradas:${NC}"
    echo "$COMPUTE_INSTANCES"
    echo -e "${YELLOW}⚠️  Estas instancias generan costos. Considera detenerlas manualmente.${NC}"
    echo "   Comando: gcloud compute instances stop INSTANCE_NAME --zone=ZONE"
fi

# Verificar instancias de Cloud SQL
SQL_INSTANCES=$(gcloud sql instances list --format="value(name)" 2>/dev/null)
if [ -n "$SQL_INSTANCES" ]; then
    echo -e "${YELLOW}⚠️  Instancias de Cloud SQL encontradas:${NC}"
    echo "$SQL_INSTANCES"
    echo -e "${YELLOW}⚠️  Estas instancias generan costos. Considera detenerlas manualmente.${NC}"
    echo "   Comando: gcloud sql instances patch INSTANCE_NAME --activation-policy=NEVER"
fi

# Verificar buckets de Cloud Storage
STORAGE_BUCKETS=$(gsutil ls 2>/dev/null | grep gs://)
if [ -n "$STORAGE_BUCKETS" ]; then
    echo -e "${YELLOW}⚠️  Buckets de Cloud Storage encontrados:${NC}"
    echo "$STORAGE_BUCKETS"
    echo -e "${YELLOW}⚠️  Los buckets con datos generan costos de almacenamiento.${NC}"
fi

# Paso 6: Resumen de costos ahorrados
echo -e "\n${GREEN}💰 Resumen de costos minimizados:${NC}"
echo -e "${GREEN}   ✅ App Engine: Activo pero sin tráfico = ~$0${NC}"
echo -e "${GREEN}   ✅ Redis Memorystore: $0 (eliminado)${NC}"
echo -e "${GREEN}   ✅ VPC Access Connector: $0 (eliminado)${NC}"
echo -e "${GREEN}   ✅ Subnet personalizada: $0 (eliminada)${NC}"

echo -e "\n${BLUE}📋 Estado del proyecto después del apagado:${NC}"
echo -e "${BLUE}   • App Engine: Activo (sin tráfico = costo mínimo)${NC}"
echo -e "${BLUE}   • Redis: Eliminado (necesita recrearse)${NC}"
echo -e "${BLUE}   • VPC Connector: Eliminado (necesita recrearse)${NC}"
echo -e "${BLUE}   • Código fuente: Intacto${NC}"

echo -e "\n${GREEN}🎉 Proceso de apagado completado!${NC}"
echo -e "${GREEN}💡 Para reactivar los servicios, ejecuta: ./startup.sh${NC}"

# Crear archivo de estado
cat > deploy/gcp/shutdown_state.txt << EOF
# Estado del proyecto después del apagado
# Fecha: $(date)
# Proyecto: $PROJECT_ID

REDIS_DELETED=true
VPC_CONNECTOR_DELETED=true
SUBNET_DELETED=true
APP_ENGINE_ACTIVE=true

# Para restaurar, ejecutar: ./startup.sh
EOF

echo -e "\n${BLUE}📄 Estado guardado en: deploy/gcp/shutdown_state.txt${NC}"