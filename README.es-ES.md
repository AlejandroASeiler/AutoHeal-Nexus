

# AutoHeal-Nexus: Autocuración estilo Kubernetes para Docker Compose

## 🛡️ Descripción General

**AutoHeal-Nexus** es un sistema integral de reparación automática y autocuración diseñado para brindar fiabilidad y resiliencia al estilo Kubernetes a implementaciones estándar de Docker Compose. Monitorea continuamente todos los servicios definidos, detecta diversos modos de fallo (bloqueos, pérdida de estado saludable, agotamiento de recursos) y ejecuta automáticamente estrategias de reparación inteligentes y configurables.

Este proyecto es esencial para mantener la alta disponibilidad y la estabilidad operativa en entornos de microservicios que ejecutan Docker Compose, reduciendo drásticamente la necesidad de intervención manual.

## ✨ Características

*   **Vigilante de Reparación Automática (Watchdog):** Monitorea continuamente el estado de los servicios, reinicia los contenedores bloqueados y resuelve estados atascados o en reinicio constante.
*   **Remediación Inteligente:** Implementa estrategias de reparación sofisticadas con períodos de espera (cooldown), intentos máximos y retroceso exponencial (exponential backoff).
*   **Integración con Prometheus:** Se integra con Prometheus para la remediación basada en alertas, el monitoreo de tasas de fallo y el seguimiento de acciones de reparación.
*   **Escalado Automático (Planificado):** Escalado dinámico de servicios basado en CPU, memoria o profundidad de cola (requiere un mecanismo de escalado externo o integración con una capa similar a Docker Swarm/Kubernetes).
*   **Registro y Monitoreo Integral:** Exporta métricas de Prometheus y proporciona un panel de Grafana dedicado para una visibilidad completa del historial de reparaciones y la salud del sistema.
*   **Gestión de Recursos:** Acciones automatizadas para manejar el alto uso de recursos (CPU/Memoria) y el bajo espacio en disco.

## 🚀 Inicio Rápido

Para ejecutar todo el sistema, incluyendo el Watchdog, Prometheus y Grafana:

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/AlejandroASeiler/AutoHeal-Nexus.git
    cd AutoHeal-Nexus
    ```

2.  **Configurar el Entorno:**
    Copie el archivo de entorno de ejemplo y edite las variables según sea necesario (por ejemplo, claves API de Telegram para notificaciones).
    ```bash
    cp .env.example .env
    ```

3.  **Iniciar la Pila (Stack):**
    El archivo `docker-compose.yml` incluye los servicios `watchdog`, `prometheus` y `grafana`.
    ```bash
    docker-compose up -d
    ```

4.  **Verificar el Estado del Watchdog:**
    ```bash
    docker-compose ps watchdog
    docker-compose logs -f watchdog
    ```

## ⚙️ Configuración

La configuración principal se gestiona a través de variables de entorno en el archivo `.env`:

| Variable | Predeterminado | Descripción |
| :--- | :--- | :--- |
| `WATCHDOG_INTERVAL` | `30` | Intervalo en segundos para la verificación de estado (health check) del Watchdog. |
| `MAX_RESTART_ATTEMPTS` | `3` | Intentos máximos antes de generar una alerta y detener la reparación automática para un servicio. |
| `RESTART_COOLDOWN` | `300` | Período de espera (en segundos) entre reinicios automáticos del mismo servicio. |
| `TELEGRAM_BOT_TOKEN` | `""` | Token del Bot de Telegram para el servicio de notificaciones. |
| `TELEGRAM_CHAT_ID` | `""` | ID del Chat de Telegram al que enviar las notificaciones. |

## 📊 Monitoreo y Panel de Control

Acceda a la pila de monitoreo una vez que los servicios estén en ejecución:

*   **Panel de Grafana:** `http://localhost:3000` (Credenciales predeterminadas: `admin`/`admin`)
    *   Hay un panel preconfigurado "Sistema de Reparación Automática" disponible para visualizar la salud de los servicios, los intentos de reparación y las tasas de éxito.
*   **Prometheus:** `http://localhost:9090`
    *   Revise las reglas de alertas activas y las métricas de servicio exportadas por el Watchdog.

## 🤝 Contribuir

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para obtener detalles sobre cómo contribuir al proyecto.

## 📄 Licencia

Este proyecto está licenciado bajo el archivo [LICENSE](LICENSE).
