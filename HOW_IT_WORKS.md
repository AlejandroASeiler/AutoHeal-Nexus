# How the AutoHeal-Nexus System Works

The **AutoHeal-Nexus** is a closed-loop, self-healing system designed to maintain the operational integrity of Docker Compose services. It operates on a continuous monitoring and intelligent remediation cycle.

## 🔄 The Self-Healing Cycle

The core of the system is the **Watchdog** service, which orchestrates the entire process:

1.  **Monitoring:** The Watchdog periodically queries the Docker daemon to check the status, health, and resource usage of all services defined in the `docker-compose.yml`.
2.  **Alerting (Prometheus):** For more complex failures (like high CPU/Memory, or high error rates), the system relies on Prometheus. Prometheus continuously scrapes metrics from the monitored services and the Watchdog itself. When a metric breaches a defined threshold (e.g., `HighMemoryUsage > 90%`), it triggers an alert.
3.  **Remediation Trigger:** The Watchdog either detects a simple failure directly (e.g., `exited` status) or receives a notification from Prometheus about a complex alert.
4.  **Intelligent Strategy Selection:** Based on the type of failure, the Watchdog selects a pre-defined **Repair Strategy** (e.g., `Restart`, `Stop then Start`, `Cleanup`).
5.  **Execution and Cooldown:** The selected action is executed via the Docker API. A **cooldown period** is then applied to the service to prevent thrashing (rapid, repeated restarts) and allow the service time to stabilize.
6.  **Tracking and Notification:** Every action, success, and failure is logged. If the maximum number of restart attempts is reached, a critical notification is sent via the Telegram Notifier.
7.  **Loop Continuation:** The Watchdog immediately resumes monitoring, waiting for the next failure or alert.

## 🛠️ Key Repair Strategies

The system employs several intelligent strategies to address common failure scenarios:

| Failure Type | Trigger Condition | Primary Action | Cooldown | Max Attempts |
| :--- | :--- | :--- | :--- | :--- |
| **Unhealthy Service** | Docker Health Check fails. | `docker-compose restart <service>` | 5 minutes | 3 |
| **Exited Service** | Container status is `exited`. | `docker-compose start <service>` | 5 minutes | 3 |
| **Stuck Restarting** | Container stuck in `restarting` state. | `docker-compose stop` then `start` | 5 minutes | 3 |
| **High Memory Usage** | Memory usage > 90% (via Prometheus alert). | `docker-compose restart <service>` | 10 minutes | 2 |
| **Disk Space Low** | Disk usage > 90% (via Prometheus alert). | `docker system prune -f` and log cleanup. | 1 hour | 1 |

## 🔗 Prometheus Integration

Prometheus is central to the system's ability to handle resource-based and complex application-level failures.

*   **Alert Rules:** The system includes a set of pre-configured alert rules (e.g., `ContainerUnhealthy`, `HighCPUUsage`) that define the conditions for auto-remediation.
*   **Alertmanager:** Although not explicitly shown, a full implementation would use Alertmanager to route these alerts to the Watchdog's API endpoint, triggering the appropriate repair action.

## 🛑 Disabling Auto-Repair

For maintenance or debugging, auto-repair can be temporarily disabled for any service by adding a specific label to its definition in the `docker-compose.yml`:

```yaml
services:
  my-service:
    labels:
      - "auto_repair=false"
```
The Watchdog will respect this label and skip monitoring and remediation for that service.

