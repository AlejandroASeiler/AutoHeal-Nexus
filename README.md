# AutoHeal-Nexus: Kubernetes-Style Self-Healing for Docker Compose

## 🛡️ Overview

**AutoHeal-Nexus** is a comprehensive auto-repair and self-healing system designed to bring Kubernetes-style reliability and resilience to standard Docker Compose deployments. It continuously monitors all defined services, detects various failure modes (crashes, unhealthiness, resource exhaustion), and automatically executes intelligent, configurable repair strategies.

This project is essential for maintaining high availability and operational stability in microservices environments running on Docker Compose, drastically reducing the need for manual intervention.

## ✨ Features

*   **Auto-Repair Watchdog:** Continuously monitors service health, restarts crashed containers, and resolves stuck/restarting states.
*   **Intelligent Remediation:** Implements sophisticated repair strategies with cooldown periods, max attempts, and exponential backoff.
*   **Prometheus Integration:** Integrates with Prometheus for alert-driven remediation, failure rate monitoring, and repair action tracking.
*   **Auto-Scaling (Planned):** Dynamic scaling of services based on CPU, memory, or queue depth (requires external scaling mechanism or integration with a Docker Swarm/Kubernetes-like layer).
*   **Comprehensive Logging & Monitoring:** Exports Prometheus metrics and provides a dedicated Grafana dashboard for full visibility into repair history and system health.
*   **Resource Management:** Automated actions to handle high resource usage (CPU/Memory) and low disk space.

## 🚀 Quick Start

To run the entire system, including the Watchdog, Prometheus, and Grafana:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AlejandroASeiler/AutoHeal-Nexus.git
    cd AutoHeal-Nexus
    ```

2.  **Configure Environment:**
    Copy the example environment file and edit the variables as needed (e.g., Telegram API keys for notifications).
    ```bash
    cp .env.example .env
    ```

3.  **Start the Stack:**
    The `docker-compose.yml` file includes the `watchdog`, `prometheus`, and `grafana` services.
    ```bash
    docker-compose up -d
    ```

4.  **Verify Watchdog Status:**
    ```bash
    docker-compose ps watchdog
    docker-compose logs -f watchdog
    ```

## ⚙️ Configuration

The core configuration is managed via environment variables in the `.env` file:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `WATCHDOG_INTERVAL` | `30` | Health check interval in seconds for the Watchdog. |
| `MAX_RESTART_ATTEMPTS` | `3` | Max attempts before alerting and stopping auto-repair for a service. |
| `RESTART_COOLDOWN` | `300` | Cooldown period (seconds) between automatic restarts of the same service. |
| `TELEGRAM_BOT_TOKEN` | `""` | Telegram Bot Token for notification service. |
| `TELEGRAM_CHAT_ID` | `""` | Telegram Chat ID to send notifications to. |

## 📊 Monitoring and Dashboard

Access the monitoring stack once the services are up:

*   **Grafana Dashboard:** `http://localhost:3000` (Default credentials: `admin`/`admin`)
    *   A pre-configured "Auto-Repair System" dashboard is available to visualize service health, repair attempts, and success rates.
*   **Prometheus:** `http://localhost:9090`
    *   Review the active alert rules and service metrics exported by the Watchdog.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to the project.

## 📄 License

This project is licensed under the [LICENSE](LICENSE) file.

