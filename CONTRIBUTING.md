# Contributing to AutoHeal-Nexus

We welcome contributions to the **AutoHeal-Nexus** project! By participating in this project, you agree to abide by our code of conduct.

## 💡 How to Contribute

There are many ways to contribute to the project:

1.  **Reporting Bugs:** If you find a bug, please check the existing issues to see if it has already been reported. If not, open a new issue using the `bug_report.md` template.
2.  **Suggesting Enhancements:** We are always looking for ways to improve the self-healing capabilities. Use the issue tracker to suggest new features or improvements.
3.  **Code Contributions:** Fork the repository, make your changes, and submit a Pull Request (PR).

## 💻 Setting up Your Development Environment

1.  **Fork and Clone:** Fork the repository on GitHub and clone your fork locally.
    ```bash
    git clone https://github.com/AlejandroASeiler/AutoHeal-Nexus.git
    cd AutoHeal-Nexus
    ```

2.  **Install Dependencies:** The core Watchdog is a Python application. Install the required dependencies.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Docker Setup:** The project is designed to run within a Docker Compose environment. Ensure Docker and Docker Compose are installed and running.

4.  **Run Tests:** Before submitting a PR, ensure all tests pass.
    ```bash
    # Assuming a testing framework is set up (e.g., pytest)
    pytest
    ```

## 🛠️ Submitting a Pull Request (PR)

1.  **Create a New Branch:**
    ```bash
    git checkout -b feature/my-new-feature
    ```

2.  **Commit Your Changes:** Write clear and concise commit messages.
    ```bash
    git commit -m "feat: Add new repair strategy for network issues"
    ```

3.  **Push to Your Fork:**
    ```bash
    git push origin feature/my-new-feature
    ```

4.  **Open a Pull Request:** Open a PR from your fork to the main repository's `main` branch. Fill out the PR template completely, describing the changes and the motivation behind them.

## 📝 Code Style and Guidelines

*   **Python:** Follow **PEP 8** style guidelines.
*   **Documentation:** All new features and changes to existing functionality should be reflected in the relevant documentation files (`HOW_IT_WORKS.md`, `TECHNICAL_DOCUMENTATION.md`).
*   **Scripts:** Ensure shell scripts are executable (`chmod +x`).

Thank you for contributing!

