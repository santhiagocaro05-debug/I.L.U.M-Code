# ILUM IA - Advanced Virtual Assistant

An advanced desktop virtual assistant featuring deep Windows integration, cognitive automation, environment control, an interactive holographic UI, voice cloning capabilities, and profound reasoning mechanics.

## Core Features

* **Holographic Interface:** A reactive orb UI with dynamic processing animations and a cohesive visual identity.
* **Smart Voice Commands and Shortcuts:** Low-latency fluid interaction driven by Gemini 2.0 Flash, featuring an intelligent sleep mode and customizable keyword wake-up mechanisms.
* **Voice Cloning:** Native integration with Fish Audio (cloud) and XTTS-v2 (local) for high-fidelity speech synthesis.
* **Contextual Environment Control:** Autonomous management of system settings, notifications, and active processes.
* **Self-Editing Capabilities:** Unique capability to read, modify, and rewrite its own source code, create backups, and dynamically update its logical parameters.

## Capabilities and Modules

ILUM is equipped with a comprehensive suite of interconnected modules:

### System and Environment Control
- **Computer Settings:** Absolute control over volume, brightness, power state, and window management.
- **Windows Settings:** Advanced OS configuration management.
- **Desktop Control:** Automation of desktop tasks and application management.
- **System Monitor:** Real-time resource tracking (CPU, RAM, Network).
- **RGB Control:** Lighting synchronization and management.
- **Terminal Agent:** Proactive and dynamic execution of PowerShell/CMD commands for complex task resolution.
- **Macro Recorder:** Hardware-level macro recording and playback for workflow automation, including raw mouse input support for 3D applications.

### Navigation and Search
- **Web Search:** Autonomous internet browsing for updated data retrieval.
- **Browser Control:** Direct manipulation of web browsers.
- **Media Management:** Background playback and high-quality media downloading via yt-dlp.
- **Mapping and Routing:** Navigation and route calculation.
- **Flight Finder:** Travel and flight availability searches.

### File and Information Management
- **File Controller:** Intelligent creation, movement, reading, and deletion of local files.
- **Document Processor:** File analysis and automated document generation.
- **Cloud Integration:** Synchronization and management of cloud storage files.
- **Knowledge Base:** Long-term memory storage and goal-tracking systems.

### Productivity and Communications
- **Unified Messaging:** Centralized multi-platform message dispatching.
- **Social Integration:** Specific modules for major communication platforms.
- **Email Control:** Email composition and reading.
- **Calendar Management:** Event scheduling and availability tracking.
- **Scheduler:** Background programming of timers, alarms, and recurring tasks.
- **Morning Briefing:** Automated daily summaries covering weather, agenda, and news.

### Academic Mode
- **Focus Environment:** Distraction-free mode activation.
- **Text Processing:** Intelligent text paraphrasing and summarization.
- **Formatting:** Automatic APA 7 reference correction and formatting.
- **Document Conversion:** PDF to editable Word document conversion.
- **Quality Assurance:** Analytical reporting on writing quality.

### Computer Vision and Accessibility
- **Screen Processing:** Real-time semantic capture and analysis of the screen using vision models.
- **Vision Guardian:** Continuous and discreet screen monitoring.
- **Visual Click:** Automated UI element location and interaction via computer vision.
- **Accessibility:** Activation of accessibility modules including eye-tracking and head-movement control.
- **Screen Reader:** Visual assistance and overlay integration.

### Development and Deep Reasoning
- **Development Agent:** Programming assistance and debugging capabilities.
- **Codebase Analysis:** Software architecture parsing and repository management.
- **Delegated Processing:** Routing of complex logical, mathematical, or analytical tasks to advanced LLMs via OpenRouter.
- **Image Generation:** Synthetic image creation.

## Technology Stack

* Python 3.12, PyQt6, Gemini Live API (Bidirectional WebSockets).
* Operating System Integrations: `pycaw`, `pygetwindow`, `psutil`, `WMI`, `winreg`, and direct Win32 Kernel calls (`ctypes`).

## Installation and Usage

1. Install Python 3.12 (ensure "Add Python to PATH" is checked during installation).
2. Clone this repository to your local machine.
3. Execute `Instalar_ILUM.bat` and wait for the dependency installation to complete.
4. Execute `Iniciar ILUM Beta.vbs` to launch the application.
5. On the first launch, input your designated API keys and your ILUM license when prompted.

If the application fails to launch, review the `ilum_startup_error.log` file located in the program's root directory for detailed dependency or configuration errors.

## Security Considerations
Local configurations and keys are stored in `config/api_keys.json`. This file must remain secure and should never be committed to version control.
