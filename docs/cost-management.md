# Gestión de Costos GCP - Proyecto Personal
## Proyecto: gcp-vm-357012

### 🎯 Objetivo
Minimizar costos de GCP para proyectos personales mediante scripts de encendido/apagado automatizado.

### 💰 Análisis de Costos

#### Costos cuando está ACTIVO:
- **Redis Memorystore (básico)**: ~$30-50/mes
- **VPC Access Connector**: ~$36/mes
- **App Engine**: $0 base + uso (muy bajo para proyectos personales)
- **Cloud Storage**: ~$0.02/GB/mes
- **Total estimado**: **$66-86/mes**

#### Costos cuando está APAGADO:
- **Redis Memorystore**: $0 (eliminado)
- **VPC Access Connector**: $0 (eliminado)
- **App Engine**: $0 (sin tráfico)
- **Cloud Storage**: ~$0.02/GB/mes (solo datos almacenados)
- **Total estimado**: **~$0-5/mes**

### 🛠️ Scripts de Gestión

#### 1. Apagar servicios (Ahorrar costos)
```bash
chmod +x deploy/gcp/shutdown.sh
./deploy/gcp/shutdown.sh
```

**¿Qué hace?**
- Detiene todas las versiones de App Engine
- Elimina la instancia de Redis Memorystore
- Elimina el VPC Access Connector
- Elimina la subnet personalizada
- Guarda el estado para restauración posterior

**⚠️ Advertencias:**
- Se perderán todos los datos de cache de Redis
- La aplicación web no estará disponible
- Los usuarios no podrán acceder al sitio

#### 2. Encender servicios (Restaurar funcionalidad)
```bash
chmod +x deploy/gcp/startup.sh
./deploy/gcp/startup.sh
```

**¿Qué hace?**
- Recrea la subnet para VPC
- Recrea la instancia de Redis (toma 5-10 minutos)
- Recrea el VPC Access Connector
- Actualiza la configuración con las nuevas IPs
- Opcionalmente despliega la aplicación

**⏱️ Tiempo estimado:** 10-15 minutos

#### 3. Solo deploy (sin recrear infraestructura)
```bash
./deploy/gcp/deploy.sh
```

### 📋 Flujo de Trabajo Recomendado

#### Para desarrollo diario:
1. **Mañana** (antes de trabajar):
   ```bash
   ./deploy/gcp/startup.sh
   ```

2. **Noche** (después de trabajar):
   ```bash
   ./deploy/gcp/shutdown.sh
   ```

#### Para demos o presentaciones:
1. **Antes del evento:**
   ```bash
   ./deploy/gcp/startup.sh
   # Esperar 10-15 minutos
   # Verificar que todo funciona
   ```

2. **Después del evento:**
   ```bash
   ./deploy/gcp/shutdown.sh
   ```

### 🔧 Comandos Útiles

#### Verificar estado actual:
```bash
# Ver apps activas
gcloud app versions list --filter="traffic_split>0"

# Ver instancias de Redis
gcloud redis instances list

# Ver VPC connectors
gcloud compute networks vpc-access connectors list

# Ver costos del mes actual
gcloud billing accounts list
```

#### Monitoreo de costos:
```bash
# Ver uso de recursos
gcloud logging read "timestamp>=\\\"$(date -d '1 day ago' --iso-8601)\\\"" --limit=100

# Verificar alertas de billing (si están configuradas)
gcloud alpha billing budgets list --billing-account=YOUR_BILLING_ACCOUNT
```

### 📊 Estimación de Ahorros

#### Escenario 1: Uso diario (8 horas/día, 22 días/mes)
- **Tiempo activo**: ~176 horas/mes
- **Ahorro**: ~70% de costos
- **Costo estimado**: $20-25/mes

#### Escenario 2: Uso semanal (fines de semana)
- **Tiempo activo**: ~64 horas/mes  
- **Ahorro**: ~90% de costos
- **Costo estimado**: $7-10/mes

#### Escenario 3: Solo demos/presentaciones
- **Tiempo activo**: ~20 horas/mes
- **Ahorro**: ~95% de costos
- **Costo estimado**: $2-5/mes

### 🚨 Consideraciones Importantes

#### ⚠️ Limitaciones:
- **Datos de Redis se pierden**: Cache, sesiones, etc.
- **Tiempo de arranque**: 10-15 minutos para tener todo listo
- **IPs pueden cambiar**: El script actualiza automáticamente
- **Interrupciones**: Los usuarios no pueden acceder durante apagado

#### ✅ Ventajas:
- **Ahorro significativo**: 70-95% en costos
- **Automatización completa**: Scripts manejan todo
- **Fácil restauración**: Un comando restaura todo
- **Código preservado**: El código fuente nunca se pierde

### 🎯 Mejores Prácticas

1. **Siempre usar los scripts**: No eliminar recursos manualmente
2. **Verificar estado**: Revisar que todo funciona antes de demos
3. **Backup de datos importantes**: No depender del cache de Redis
4. **Configurar alertas**: Para no olvidar apagar los servicios
5. **Monitorear facturación**: Revisar costos semanalmente

### 🔄 Automatización Avanzada (Opcional)

#### Usando cron para automatizar:
```bash
# Apagar automáticamente a las 6 PM
0 18 * * * cd /home/teo/Documents/ADB && ./deploy/gcp/shutdown.sh

# Encender automáticamente a las 8 AM (lunes a viernes)
0 8 * * 1-5 cd /home/teo/Documents/ADB && ./deploy/gcp/startup.sh
```

#### Usando GitHub Actions para deployment automático:
- Configurar workflow que se ejecute solo cuando pushees cambios
- Incluir step para encender servicios antes del deploy
- Incluir step para apagar servicios después del deploy (opcional)

### 📞 Soporte

Si algo sale mal:
1. Revisar logs: `gcloud logging read --limit=100`
2. Verificar estado: Ver comandos en sección "Comandos Útiles"
3. Recrear desde cero: Ejecutar `startup.sh` después de `shutdown.sh`
4. Contactar support de GCP si hay problemas con la facturación

### 📈 Roadmap de Mejoras

1. **Backup automático de Redis** antes del apagado
2. **Notificaciones por email** cuando se enciende/apaga
3. **Dashboard de costos** integrado
4. **Scheduling inteligente** basado en uso real
5. **Health checks** automáticos después del encendido