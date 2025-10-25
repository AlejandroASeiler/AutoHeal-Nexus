# Technical Documentation: AutoHeal-Nexus

## 1. Project Structure

The **AutoHeal-Nexus** project is structured to separate configuration, core logic, and supporting scripts.

```
AutoHeal-Nexus/
├── config/                  # Configuration files (crontab, alert rules)
│   └── crontab.txt
├── docs/                    # Documentation and guides
│   └── AUTO_REPAIR_GUIDE.md
├── scripts/                 # Core Python and Shell scripts for Watchdog and Remediation
│   ├── auto_patcher.py
│   ├── auto_repair_watchdog.py # The main Watchdog service
│   ├── auto_scaler.py          # Placeholder for scaling logic
│   ├── notify_build_progress.sh
│   ├── predictive_repair_agent.py # Placeholder for future ML-based prediction
│   ├── remediate.py            # Remediation functions (restart, stop/start, cleanup)
│   └── telegram_notifier.py    # Telegram notification utility
├── src/                     # Core application logic (currently empty, scripts are main logic)
├── .env.example             # Example environment variables
├── Dockerfile               # Docker image definition for the Watchdog service
├── docker-compose.yml       # Orchestration file for the full stack (Watchdog, Prometheus, Grafana)
├── requirements.txt         # Python dependencies
└── ... (Documentation and other files)
```

## 2. Core Components

### 2.1. `auto_repair_watchdog.py`

This is the main entry point and the core loop of the self-healing system.

*   **Functionality:**
    *   Connects to the local Docker daemon using the `docker` SDK.
    *   Periodically iterates through all running services in the current Docker Compose project.
    *   Checks the container status (`running`, `exited`, `restarting`) and health status (if a health check is configured).
    *   For resource-based alerts, it would ideally receive webhooks from Alertmanager (part of the Prometheus stack).
    *   Calls functions from `remediate.py` based on the detected failure and applies cooldown logic.
    *   Logs all actions to a file (`logs/auto_repair.log`) and sends critical notifications via `telegram_notifier.py`.

### 2.2. `remediate.py`

A module containing the specific, idempotent actions required for repair.

*   **Key Functions:**
    *   `restart_service(service_name)`: Restarts a service gracefully.
    *   `stop_start_service(service_name)`: Forces a stop and then a clean start, used for containers stuck in a bad state.
    *   `perform_cleanup()`: Executes disk space cleanup commands (`docker system prune -f`, log rotation/deletion).

### 2.3. `telegram_notifier.py`

A utility for sending notifications about critical events.

*   **Dependencies:** Requires `requests` library.
*   **Configuration:** Relies on `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from the environment.
*   **Usage:** Called by the Watchdog when a service exceeds `MAX_RESTART_ATTEMPTS` or for critical system alerts (e.g., disk space low).

## 3. Containerization and Orchestration

### 3.1. `Dockerfile`

The `Dockerfile` defines the environment for the `watchdog` service. It is based on a lightweight Python image, installs the necessary dependencies (`requirements.txt`), and sets up the entry point for `auto_repair_watchdog.py`.

### 3.2. `docker-compose.yml`

This file defines the complete stack:

| Service | Image/Build | Purpose | Key Configuration |
| :--- | :--- | :--- | :--- |
| `watchdog` | `build: .` | Core self-healing service. | Mounts `/var/run/docker.sock` for Docker API access. |
| `prometheus` | `prom/prometheus` | Metrics collection and alerting engine. | Configured with a `prometheus.yml` (in `config/`) to scrape services and define alert rules. |
| `grafana` | `grafana/grafana` | Visualization and dashboarding. | Pre-configured to connect to Prometheus and display the Auto-Repair dashboard. |

**Crucial Note:** The `watchdog` service requires access to the Docker daemon to manage other containers. This is achieved by mounting the Docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

## 4. Configuration and Environment

### 4.1. `.env.example`

Provides a template for environment variables to configure the Watchdog's behavior:

*   `WATCHDOG_INTERVAL`: Controls the frequency of health checks.
*   `MAX_RESTART_ATTEMPTS`: Controls the system's persistence before escalating an issue.
*   `RESTART_COOLDOWN`: A critical setting to prevent resource exhaustion from rapid restarts.

### 4.2. `crontab.txt`

This file is intended for system-level scheduled tasks that might run outside the Docker Compose stack, such as periodic log rotation or system maintenance, or as a fallback for the Watchdog. The included scripts like `auto_patcher.py` can be scheduled here.

