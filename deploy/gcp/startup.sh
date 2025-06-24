#!/bin/bash
# Script para encender todos los servicios de GCP
# ===============================================

set -e

echo "🚀 Iniciando proceso de encendido de servicios GCP..."

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

# Función para mostrar progreso
show_progress() {
    echo -e "${YELLOW}⏳ $1...${NC}"
}

# Verificar estado anterior
if [ -f "deploy/gcp/shutdown_state.txt" ]; then
    echo -e "${BLUE}📄 Leyendo estado anterior...${NC}"
    source deploy/gcp/shutdown_state.txt
else
    echo -e "${YELLOW}⚠️  No se encontró archivo de estado. Continuando con configuración completa...${NC}"
    REDIS_DELETED=true
    VPC_CONNECTOR_DELETED=true
    SUBNET_DELETED=true
    APP_ENGINE_ACTIVE=true
fi

# Paso 1: Crear subnet para VPC Access Connector
if [ "$SUBNET_DELETED" = "true" ]; then
    echo -e "\n${YELLOW}📋 Paso 1: Creando subnet para VPC Connector...${NC}"
    
    if gcloud compute networks subnets describe $SUBNET_NAME --region=$REGION &>/dev/null; then
        echo -e "${GREEN}✅ Subnet ya existe${NC}"
    else
        show_progress "Creando subnet $SUBNET_NAME"
        gcloud compute networks subnets create $SUBNET_NAME \
            --network=default \
            --range=10.8.0.0/28 \
            --region=$REGION
        echo -e "${GREEN}✅ Subnet creada${NC}"
    fi
else
    echo -e "\n${GREEN}✅ Paso 1: Subnet ya existía${NC}"
fi

# Paso 2: Crear instancia de Redis
if [ "$REDIS_DELETED" = "true" ]; then
    echo -e "\n${YELLOW}📋 Paso 2: Creando instancia de Redis...${NC}"
    
    if gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION &>/dev/null; then
        echo -e "${GREEN}✅ Instancia de Redis ya existe${NC}"
        REDIS_IP=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(host)")
    else
        show_progress "Creando instancia de Redis (esto puede tomar varios minutos)"
        gcloud redis instances create $REDIS_INSTANCE_NAME \
            --size=1 \
            --region=$REGION \
            --redis-version=redis_6_x \
            --network=default \
            --tier=basic
        
        echo -e "${GREEN}✅ Instancia de Redis creada${NC}"
        REDIS_IP=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(host)")
    fi
    
    echo -e "${GREEN}   IP de Redis: ${REDIS_IP}${NC}"
else
    echo -e "\n${GREEN}✅ Paso 2: Redis ya existía${NC}"
    REDIS_IP=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(host)" 2>/dev/null || echo "10.169.50.171")
fi

# Paso 3: Crear VPC Access Connector
if [ "$VPC_CONNECTOR_DELETED" = "true" ]; then
    echo -e "\n${YELLOW}📋 Paso 3: Creando VPC Access Connector...${NC}"
    
    if gcloud compute networks vpc-access connectors describe $VPC_CONNECTOR_NAME --region=$REGION &>/dev/null; then
        echo -e "${GREEN}✅ VPC Access Connector ya existe${NC}"
    else
        show_progress "Creando VPC Access Connector (esto puede tomar varios minutos)"
        gcloud compute networks vpc-access connectors create $VPC_CONNECTOR_NAME \
            --region=$REGION \
            --subnet=$SUBNET_NAME \
            --subnet-project=$PROJECT_ID \
            --min-instances=2 \
            --max-instances=3 \
            --machine-type=e2-micro
        
        echo -e "${GREEN}✅ VPC Access Connector creado${NC}"
    fi
else
    echo -e "\n${GREEN}✅ Paso 3: VPC Access Connector ya existía${NC}"
fi

# Paso 4: Actualizar configuración de app.yaml
echo -e "\n${YELLOW}📋 Paso 4: Actualizando configuración...${NC}"

# Actualizar IP de Redis en app.yaml
if [ -f "deploy/gcp/app.yaml" ]; then
    # Descomentar VPC connector si estaba comentado
    sed -i 's/^# vpc_access_connector:/vpc_access_connector:/g' deploy/gcp/app.yaml
    sed -i 's/^#   name: "projects/gcp-vm-357012/  name: "projects\/gcp-vm-357012/g' deploy/gcp/app.yaml
    
    # Actualizar IP de Redis
    sed -i "s/REDIS_HOST: \"[0-9.]*\"/REDIS_HOST: \"$REDIS_IP\"/g" deploy/gcp/app.yaml
    
    echo -e "${GREEN}✅ Configuración actualizada${NC}"
    echo -e "${GREEN}   IP de Redis configurada: $REDIS_IP${NC}"
else
    echo -e "${RED}❌ Archivo app.yaml no encontrado${NC}"
fi

# Paso 5: Esperar a que el VPC Connector esté listo
echo -e "\n${YELLOW}📋 Paso 5: Verificando estado del VPC Connector...${NC}"

show_progress "Esperando a que el VPC Connector esté listo"
TIMEOUT=300 # 5 minutos
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    STATUS=$(gcloud compute networks vpc-access connectors describe $VPC_CONNECTOR_NAME \
        --region=$REGION --format="value(state)" 2>/dev/null || echo "UNKNOWN")
    
    if [ "$STATUS" = "READY" ]; then
        echo -e "${GREEN}✅ VPC Connector está listo${NC}"
        break
    elif [ "$STATUS" = "CREATING" ]; then
        echo -e "${YELLOW}⏳ VPC Connector aún se está creando... (${ELAPSED}s/${TIMEOUT}s)${NC}"
        sleep 30
        ELAPSED=$((ELAPSED + 30))
    else
        echo -e "${RED}❌ Estado inesperado del VPC Connector: $STATUS${NC}"
        break
    fi
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo -e "${RED}❌ Timeout esperando VPC Connector${NC}"
    echo -e "${YELLOW}⚠️  Puedes intentar el deployment más tarde${NC}"
fi

# Paso 6: Deploy de la aplicación (si se requiere nueva versión)
if [ "$APP_ENGINE_ACTIVE" = "true" ]; then
    echo -e "\n${YELLOW}📋 Paso 6: Desplegando aplicación...${NC}"
    
    read -p "¿Deseas desplegar la aplicación ahora? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        show_progress "Desplegando aplicación en App Engine"
        
        # Copiar app.yaml al directorio raíz para deployment
        cp deploy/gcp/app.yaml app.yaml
        gcloud app deploy app.yaml --quiet
        
        
        # Limpiar archivo temporal
        rm -f app.yaml
        
        # Obtener URL de la aplicación
        APP_URL=$(gcloud app describe --format="value(defaultHostname)")
        echo -e "${GREEN}✅ Aplicación desplegada exitosamente${NC}"
        echo -e "${GREEN}   URL: https://${APP_URL}${NC}"
    else
        echo -e "${YELLOW}⚠️  Deployment omitido. Puedes desplegarlo manualmente más tarde.${NC}"
        echo -e "${YELLOW}   Comando: gcloud app deploy deploy/gcp/app.yaml${NC}"
    fi
else
    echo -e "\n${GREEN}✅ Paso 6: App Engine ya estaba activo${NC}"
fi

# Paso 7: Verificar servicios
echo -e "\n${YELLOW}📋 Paso 7: Verificando estado de servicios...${NC}"

# Verificar Redis
if gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION &>/dev/null; then
    REDIS_STATUS=$(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --format="value(state)")
    echo -e "${GREEN}✅ Redis: $REDIS_STATUS${NC}"
else
    echo -e "${RED}❌ Redis: No encontrado${NC}"
fi

# Verificar VPC Connector
if gcloud compute networks vpc-access connectors describe $VPC_CONNECTOR_NAME --region=$REGION &>/dev/null; then
    VPC_STATUS=$(gcloud compute networks vpc-access connectors describe $VPC_CONNECTOR_NAME --region=$REGION --format="value(state)")
    echo -e "${GREEN}✅ VPC Connector: $VPC_STATUS${NC}"
else
    echo -e "${RED}❌ VPC Connector: No encontrado${NC}"
fi

# Verificar App Engine
APP_VERSIONS=$(gcloud app versions list --filter="traffic_split>0" --format="value(version.id)" 2>/dev/null)
if [ -n "$APP_VERSIONS" ]; then
    echo -e "${GREEN}✅ App Engine: Activo (versiones: $APP_VERSIONS)${NC}"
else
    echo -e "${YELLOW}⚠️  App Engine: Sin versiones activas${NC}"
fi

# Paso 8: Resumen de costos
echo -e "\n${GREEN}💰 Resumen de costos activados:${NC}"
echo -e "${YELLOW}   💰 Redis Memorystore: ~$30-50/mes (instancia básica)${NC}"
echo -e "${YELLOW}   💰 VPC Access Connector: ~$36/mes${NC}"
echo -e "${YELLOW}   💰 App Engine: $0 + costos por uso${NC}"
echo -e "${YELLOW}   💰 Estimado total: ~$66-86/mes cuando está activo${NC}"

echo -e "\n${BLUE}📋 Estado del proyecto después del encendido:${NC}"
echo -e "${BLUE}   • Redis: Activo y funcionando${NC}"
echo -e "${BLUE}   • VPC Connector: Activo${NC}"
echo -e "${BLUE}   • App Engine: Listo para recibir tráfico${NC}"

echo -e "\n${GREEN}🎉 Proceso de encendido completado!${NC}"
echo -e "${GREEN}💡 Para apagar los servicios y ahorrar costos: ./shutdown.sh${NC}"

# Actualizar archivo de estado
cat > deploy/gcp/shutdown_state.txt << EOF
# Estado del proyecto después del encendido
# Fecha: $(date)
# Proyecto: $PROJECT_ID

REDIS_DELETED=false
VPC_CONNECTOR_DELETED=false
SUBNET_DELETED=false
APP_ENGINE_ACTIVE=true

# Para apagar y ahorrar costos, ejecutar: ./shutdown.sh
EOF

echo -e "\n${BLUE}📄 Estado actualizado en: deploy/gcp/shutdown_state.txt${NC}"