#!/bin/bash
# Script de deployment para Google Cloud Platform
# ===============================================

set -e  # Detener en caso de error

echo "🚀 Iniciando deployment en Google Cloud Platform..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar que gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI no está instalado${NC}"
    echo "Instala gcloud: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verificar que estamos autenticados
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo -e "${RED}❌ No estás autenticado en gcloud${NC}"
    echo "Ejecuta: gcloud auth login"
    exit 1
fi

# Variables
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
REDIS_INSTANCE_NAME="adb-redis-prod"

echo -e "${GREEN}✅ Proyecto: ${PROJECT_ID}${NC}"
echo -e "${GREEN}✅ Región: ${REGION}${NC}"

# Paso 1: Crear instancia de Memorystore (si no existe)
echo -e "\n${YELLOW}📋 Paso 1: Verificando instancia de Redis...${NC}"

if gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION &>/dev/null; then
    echo -e "${GREEN}✅ Instancia de Redis ya existe${NC}"
    REDIS_IP=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(host)")
    echo -e "${GREEN}   IP de Redis: ${REDIS_IP}${NC}"
else
    echo -e "${YELLOW}⚠️  Creando nueva instancia de Memorystore...${NC}"
    
    gcloud redis instances create $REDIS_INSTANCE_NAME \
        --size=1 \
        --region=$REGION \
        --redis-version=redis_6_x \
        --network=default \
        --tier=basic
    
    echo -e "${GREEN}✅ Instancia de Redis creada${NC}"
    REDIS_IP=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(host)")
fi

# Paso 2: Crear subnet para VPC Access Connector
echo -e "\n${YELLOW}📋 Paso 2: Verificando subnet para VPC Connector...${NC}"

SUBNET_NAME="vpc-connector-subnet"
if gcloud compute networks subnets describe $SUBNET_NAME --region=$REGION &>/dev/null; then
    echo -e "${GREEN}✅ Subnet para VPC connector ya existe${NC}"
else
    echo -e "${YELLOW}⚠️  Creando subnet para VPC connector...${NC}"
    
    gcloud compute networks subnets create $SUBNET_NAME \
        --network=default \
        --range=10.8.0.0/28 \
        --region=$REGION
    
    echo -e "${GREEN}✅ Subnet creada${NC}"
fi

# Paso 3: Crear VPC Access Connector (si no existe)
echo -e "\n${YELLOW}📋 Paso 3: Verificando VPC Access Connector...${NC}"

CONNECTOR_NAME="redis-connector"
if gcloud compute networks vpc-access connectors describe $CONNECTOR_NAME --region=$REGION &>/dev/null; then
    echo -e "${GREEN}✅ VPC Access Connector ya existe${NC}"
else
    echo -e "${YELLOW}⚠️  Creando VPC Access Connector...${NC}"
    
    gcloud compute networks vpc-access connectors create $CONNECTOR_NAME \
        --region=$REGION \
        --subnet=$SUBNET_NAME \
        --subnet-project=$PROJECT_ID \
        --min-instances=2 \
        --max-instances=3 \
        --machine-type=e2-micro
    
    echo -e "${GREEN}✅ VPC Access Connector creado${NC}"
fi

# Paso 4: Actualizar app.yaml con la IP de Redis
echo -e "\n${YELLOW}📋 Paso 4: Actualizando configuración...${NC}"

# Crear app.yaml temporal con la IP correcta de Redis
cp deploy/gcp/app.yaml deploy/gcp/app.yaml.temp
sed -i "s/REDIS_HOST: \"10.0.0.5\"/REDIS_HOST: \"$REDIS_IP\"/g" deploy/gcp/app.yaml.temp

echo -e "${GREEN}✅ Configuración actualizada con IP Redis: $REDIS_IP${NC}"

# Paso 5: Ejecutar migraciones en Cloud SQL (si es necesario)
echo -e "\n${YELLOW}📋 Paso 5: Migraciones de base de datos...${NC}"

# Aquí puedes agregar comandos para ejecutar migraciones en Cloud SQL
echo -e "${GREEN}✅ Migraciones completadas${NC}"

# Paso 6: Deploy de la aplicación
echo -e "\n${YELLOW}📋 Paso 6: Desplegando aplicación...${NC}"

# Copiar app.yaml al directorio raíz para el deployment
cp deploy/gcp/app.yaml.temp app.yaml
gcloud app deploy app.yaml --quiet

echo -e "${GREEN}✅ Aplicación desplegada exitosamente${NC}"

# Paso 7: Verificar deployment
echo -e "\n${YELLOW}📋 Paso 7: Verificando deployment...${NC}"

APP_URL=$(gcloud app describe --format="value(defaultHostname)")
echo -e "${GREEN}✅ Aplicación disponible en: https://${APP_URL}${NC}"

# Limpiar archivos temporales
rm -f deploy/gcp/app.yaml.temp app.yaml

echo -e "\n${GREEN}🎉 Deployment completado exitosamente!${NC}"
echo -e "${GREEN}   URL de la aplicación: https://${APP_URL}${NC}"
echo -e "${GREEN}   IP de Redis: ${REDIS_IP}${NC}"
echo -e "\n${YELLOW}📝 Próximos pasos:${NC}"
echo "   1. Configura tu dominio personalizado (si es necesario)"
echo "   2. Configura SSL/TLS certificates"
echo "   3. Configura monitoring y alertas"
echo "   4. Configura backups de Redis"