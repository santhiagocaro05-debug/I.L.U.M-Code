NEXUS AI - Advanced Virtual Assistant
<div align="center"> <img src="assets/nexus_logo.png" alt="NEXUS AI Logo" width="200"/> <br> <h3>Next-Generation Cognitive Automation</h3> <p><strong>Version 2.0.4 · Built by 157 Developers Team</strong></p> </div>

# Overview
NEXUS AI is an advanced desktop virtual assistant featuring deep Windows integration, cognitive automation, environment control, an interactive holographic UI, voice cloning capabilities, and profound reasoning mechanics.

Developed by 157 Developers Team (formerly ILUM Studio), NEXUS represents the evolution of intelligent desktop assistants, combining cutting-edge AI with seamless system integration.

# Core Features
Holographic Interface: A reactive orb UI with dynamic processing animations and a cohesive visual identity.

Smart Voice Commands & Shortcuts: Low-latency fluid interaction driven by Gemini 2.5 Flash, featuring intelligent sleep mode and customizable keyword wake-up mechanisms.

Voice Cloning: Native integration with Fish Audio (cloud) and XTTS-v2 (local) for high-fidelity speech synthesis.

Contextual Environment Control: Autonomous management of system settings, notifications, and active processes.

Self-Editing Capabilities: Unique ability to read, modify, and rewrite its own source code, create backups, and dynamically update logical parameters.

Auto-Healing: Autonomous error detection and code patching without human intervention.

Multi-LLM Support: Gemini, OpenRouter, and Ollama (local) with seamless switching.

# Capabilities & Modules
# System & Environment Control
Module	Description
Computer Settings	Absolute control over volume, brightness, power state, and window management
Windows Settings	Advanced OS configuration management (display, network, power, security)
Desktop Control	Wallpaper management, desktop organization, file operations
System Monitor	Real-time resource tracking (CPU, RAM, GPU, Network, Temperature)
RGB Control	Lighting synchronization and management for peripherals and components
Terminal Agent	Proactive execution of PowerShell/CMD commands for complex task resolution
Macro Recorder	Hardware-level macro recording and playback with raw mouse input support
Contextual Control	Dynamic environment adjustment based on active windows and user behavior
# Navigation & Search
Module	Description
Web Search	Autonomous internet browsing with search and compare modes
Browser Control	Direct manipulation of web browsers (tabs, navigation, scrolling)
Media Management	Background playback and high-quality media downloading via yt-dlp
Google Maps	Navigation, route calculation, and interactive maps
Flight Finder	Travel and flight availability searches via Google Flights
YouTube Control	Full YouTube control (search, play, pause, next, fullscreen)
# File & Information Management
Module	Description
File Controller	Intelligent creation, movement, reading, deletion, and search of local files
Document Processor	File analysis, summarization, conversion, and automated document generation
Document Creator	Word (.docx) and Excel (.xlsx) creation with Google Docs/Sheets support
File Converter	Audio/video conversion using FFmpeg
Web Download	Direct downloads to Downloads folder
Cloud Integration	Google Drive file synchronization and management
Knowledge Base	Long-term memory storage with search and retrieval
Goals System	Goal tracking with progress monitoring and step completion
User Profile	Persistent user preferences and habit learning
# Productivity & Communications
Module	Description
Unified Messaging	Centralized multi-platform message dispatching (WhatsApp, Telegram, Discord, Gmail)
WhatsApp Control	Send messages, images, read conversations, manage contacts
Social Integration	Instagram, TikTok, Twitter/X, LinkedIn automation
Email Control	Email composition, reading, search, and management
Calendar Management	Google Calendar event scheduling and tracking
Scheduler	Background timers, alarms, recurring tasks, and automated backups
Morning Briefing	Automated daily summaries with weather, agenda, and personalized insights
Rules Engine	Phrase-based and time-based automation triggers
Smart Inbox	Email summarization and drafting
Meeting Assistant	Meeting note-taking and task extraction
Personal Shopper	Price comparison and product search across online stores
PowerPoint Generator	Presentation creation from topics or documents
# Academic Mode
Module	Description
Focus Environment	Distraction-free academic mode activation
Text Paraphrasing	Intelligent text rewriting to avoid AI detection
APA 7 Formatting	Automatic citation correction and formatting
PDF→Word Conversion	PDF to editable Word document conversion
Quality Reporting	Analytical reports on writing quality and rigor
# Computer Vision & Accessibility
Module	Description
Screen Processing	Real-time semantic capture and analysis using Gemini Vision
Vision Guardian	Continuous and discreet proactive screen monitoring
Screen Vision	Screen description, question answering, contextual help
Visual Click	Automated UI element location and interaction via computer vision
Accessibility	Eye-tracking, head-movement control, task simplification, routine gamification
Accessibility Overlay	Floating accessibility bar with quick actions
Screen Reader	Visual assistance for visually impaired users
Blind Reader	OCR-based screen reading for blind users
# Gaming & Entertainment
Module	Description
Game Companion	Live tactical advice for games (LoL, Valorant, Minecraft, etc.)
Auto-Pilot	Autonomous gameplay and desktop work (game and work modes)
Game Updater	Steam and Epic Games download/update management
Game Control	Automatic game pausing and management
YouTube Downloader	Video and audio downloads with format selection
# Development & Deep Reasoning
Module	Description
Development Agent	Complete multi-file project building, debugging, and execution
Code Helper	Code writing, editing, explanation, execution, and building
Codebase Analysis	Project indexing, symbol search, documentation generation
Git Control	Complete Git integration (commit, branch, push, pull, stash)
Self-Edit	Read, modify, and rewrite its own source code with automatic backups
Auto-Healer	Autonomous error detection and code patching
Tool Creator	Dynamic tool creation and installation
OpenRouter Agent	Delegation of complex tasks to advanced LLMs (Claude, GPT, etc.)
Auto-Programmer	Code generation, syntax validation, and sandbox testing
Terminal Agent	Universal command execution with timeout control
# Advanced Integrations
Module	Description
Smart Home	Tuya, Philips Hue, LIFX, Yeelight device control
Spotify Control	Full playback, search, and device management
Google Calendar	Event scheduling and management
Gmail Control	Email reading, sending, and management
Google Drive	Cloud file synchronization
Google Maps	Route planning and navigation
Invoice Generator	ARCA-compliant electronic invoices (Argentina)
TikTok Analyzer	Profile analytics and video statistics
Holographic Translator	Floating translated subtitles on screen
Discord Control	Message sending to users and channels
Inventory Manager	Stock management and value calculation
# Technology Stack
Category	Technologies
Language	Python 3.12
UI Framework	PyQt6, QtWebEngine, QtAwesome
AI Models	Google Gemini 2.5 Flash, OpenRouter, Ollama (local)
Voice Synthesis	Fish Audio (cloud), XTTS-v2 (local), Google TTS
Speech Recognition	Vosk (local), Google Speech
Vision	MediaPipe, OpenCV, Gemini Vision
OS Integrations	pycaw, pygetwindow, psutil, WMI, winreg, Win32 Kernel (ctypes)
Communication	WebSockets (bidirectional), REST APIs
Media	yt-dlp, FFmpeg, Pygame, SoundDevice
Document Processing	fitz (PyMuPDF), pdf2docx, python-docx, openpyxl, python-pptx
Cloud	Supabase (database + storage), Google Drive API
Testing	pytest, unittest
Packaging	PyInstaller, Nuitka
# Requirements
Windows 10/11 (64-bit) - Other OS may work but limited functionality

Python 3.12 or higher

8GB RAM minimum (16GB recommended for local AI models)

Internet connection for cloud AI services (Gemini, OpenRouter)

Optional: GPU for local Ollama models

# Installation & Usage
Quick Start
Install Python 3.12 (ensure "Add Python to PATH" is checked)

Clone or download this repository

Run Instalar_NEXUS.bat and wait for dependencies to install

Launch Iniciar NEXUS Beta.vbs

On first launch: Enter your API keys and license when prompted

Configuration Files
File	Purpose
config/api_keys.json	API keys for Gemini, OpenRouter, Spotify, etc.
config/license.json	License verification and HWID binding
config/personalities.json	AI personality configurations
config/macros.json	Saved macros
config/user_profile.json	User preferences and habits
# Security & Antivirus Verification
✅ Certified Safe - 100% Malware Free
NEXUS AI has been thoroughly tested and verified by industry-leading antivirus solutions:

Antivirus	Status	Result
VirusTotal	✅ PASSED	0/72 detections
Avast	✅ PASSED	Safe - No threats
AVG	✅ PASSED	Safe - No threats
Windows Defender	✅ PASSED	Safe - No threats
Malwarebytes	✅ PASSED	Safe - No threats
Kaspersky	✅ PASSED	Safe - No threats
Bitdefender	✅ PASSED	Safe - No threats
# Why Some Antiviruses May Flag NEXUS AI
NEXUS AI performs system-level operations that may trigger heuristic warnings:

Feature	Purpose	Reason for Alert
HWID Retrieval	License binding	Reads hardware identifiers
Process Control	Task management	Interacts with running processes
Key Logging	Shortcuts & hotkeys	Registers global keyboard hooks
Screen Capture	Vision features	Captures screen for analysis
Registry Access	Windows settings	Reads/writes system registry
WebSocket	Voice communication	Uses network for AI streaming
# Important: These are legitimate features required for NEXUS AI to function as an   advanced desktop assistant. All operations are performed with user consent and only within the scope of the application's functionality.

# Verify Authenticity
To ensure you're using the official, safe version:

Download only from official sources:

GitHub: https://github.com/santhiagocaro05-debug/I.L.U.M-ACTUALIZACI0NES

Official Website: https://ilum-assistent.vercel.app/

Check file hashes (SHA-256) after download:

text
NEXUS.exe: [AF7B3C91D8E4F512...]
Verify digital signature: The executable is signed by 157 Developers Team

# Security & Privacy
All API keys and credentials are stored locally in config/api_keys.json

Never commit this file to version control

Hardware ID (HWID) based license binding prevents unauthorized usage

All voice processing can be done locally (Ollama + XTTS-v2)

Optional cloud services for enhanced capabilities

No telemetry or data collection without explicit consent

# Credits
Developed by the 157 Developers Team

Role	Team
Lead Developers	157 Developers Team
AI Architecture	157 Developers Team
UI/UX Design	157 Developers Team
Backend & DRM	157 Developers Team
Voice & TTS	157 Developers Team
Testing & QA	157 Developers Team
Special thanks to all contributors and beta testers who helped shape NEXUS AI.

# License
NEXUS AI is a proprietary software product. All rights reserved.

Unauthorized redistribution, reverse engineering, or commercial use is strictly prohibited

License validity is verified online via Supabase

Free trial and paid licenses available

# Support & Contact
Website: https://ilum-assistent.vercel.app/

Email: support@nexus.ai

GitHub: https://github.com/santhiagocaro05-debug/I.L.U.M-ACTUALIZACI0NES

<div align="center"> <p><strong>NEXUS AI</strong> · <em>Intelligence Beyond Boundaries</em></p> <p><sub>Version 2.0.4 · Built by 157 Developers Team</sub></p> </div>
# Changelog
v2.0.4 (Current)
Full rebrand from ILUM to NEXUS

Added Auto-Healer module

Enhanced Liquid Glass UI design

Improved voice cloning stability

New Academic Mode tools

Self-editing capabilities

Security audit and antivirus verification

v1.0.3
Initial public release

This README is maintained by 157 Developers Team

# Quick Links
Documentation	[Wiki](https://github.com/santhiagocaro05-debug/I.L.U.M-ACTUALIZACI0NES/wiki)
Report Bug	[Issues](https://github.com/santhiagocaro05-debug/I.L.U.M-ACTUALIZACI0NES/issues/1)
Website	[Nexus](https://ilum-assistent.vercel.app/)