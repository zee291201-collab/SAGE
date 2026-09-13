# SAGE — Setup Guide

**Smart Autonomous Guidance Entity**

SAGE is designed to run locally with Ollama as its model runtime. This guide explains how to install SAGE on a new **macOS, Windows, or Linux** machine, install the required Qwen models, configure the local knowledge system, and launch SAGE.

> **Recommended approach:** keep the SAGE source code in the GitHub repository, but let Ollama manage the model files locally. Do not commit large model weights to the repository.

---

## 1. Requirements

### Software

- Git
- Python 3
- Ollama
- A working local copy of the SAGE repository

Ollama currently supports **macOS, Windows, and Linux**. The official Ollama quickstart documents the local CLI and API, including the `/api/chat` endpoint used by applications. citeturn395644search6

### Hardware

SAGE can run on different hardware, but model speed and maximum context depend heavily on RAM/VRAM and the hardware backend available to Ollama.

For an 8B Q4-style model, **16 GB system memory is a practical target** for a machine like the M2 MacBook Air, although performance will vary by device.

---

# 2. Install Ollama

## macOS

Current Ollama macOS downloads require **macOS 14 Sonoma or later** according to the official download page. citeturn395644search10

Install Ollama using the official app, or use the official installer command where appropriate:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Then verify:

```bash
ollama --version
```

Start Ollama if it is not already running:

```bash
ollama serve
```

If you installed the macOS application, Ollama may already be running in the background.

---

## Linux

Use the official installer:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:

```bash
ollama --version
```

Start the server when needed:

```bash
ollama serve
```

The official Linux download page currently provides this installer command. citeturn395644search9

---

## Windows

Install Ollama using the official Windows installer.

The Ollama project also documents the PowerShell installer:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Then open PowerShell and verify:

```powershell
ollama --version
```

Ollama's official repository lists Windows installation alongside macOS and Linux. citeturn395644search11

---

# 3. Verify the Ollama API

SAGE communicates with Ollama through its local HTTP API.

Check that the local service is reachable:

```bash
curl http://localhost:11434/api/tags
```

A working Ollama installation should return a JSON response describing locally available models.

You can also test the chat endpoint directly:

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"hello"}],"stream":false}'
```

The official Ollama quickstart documents the `/api/chat` endpoint and local port `11434`. citeturn395644search6

---

# 4. Download the Qwen Models

SAGE can use different models for different tasks. The repository configuration should determine which model names your current SAGE build expects.

For the standard Qwen3 setup used during development, pull the base models with:

```bash
ollama pull qwen3:8b
ollama pull qwen3:4b
```

Then check:

```bash
ollama list
```

Do not assume the exact tag is interchangeable with another tag. The model name in SAGE must match the model available to Ollama.

---

# 5. Create the SAGE Custom Models

If your repository contains a **Modelfile** for a custom SAGE model, use that Modelfile instead of trying to manually reproduce the model configuration.

A Modelfile is Ollama's blueprint for a customized model. It can define the base model, parameters, system prompt, template, adapter, and other configuration. citeturn395644search2

Example:

```text
FROM qwen3:8b
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.05
PARAMETER num_ctx 4096
```

From the directory containing the Modelfile:

```bash
ollama create sage-qwen -f Modelfile
```

Then test it:

```bash
ollama run sage-qwen
```

Ollama officially documents `ollama create` and `ollama run` for Modelfile-based models. citeturn395644search2

If your SAGE repository uses a second model, build it using its own Modelfile and name it exactly as referenced by SAGE.

---

# 6. Clone SAGE

Choose a directory for the project, then clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-SAGE-REPOSITORY.git
cd YOUR-SAGE-REPOSITORY
```

Or, if you already downloaded the repository:

```bash
cd /path/to/SAGE
```

---

# 7. Install Python Dependencies

Create an optional virtual environment:

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Then install the dependencies listed by your project, for example:

```bash
pip install -r requirements.txt
```

If the repository does not contain a `requirements.txt`, install the packages required by the current SAGE source instead of inventing a dependency list.

---

# 8. Configure the Local Knowledge Base

SAGE's knowledge system is intended to search material stored locally before using external research.

The expected structure is roughly:

```text
SAGE/
├── sage.py
├── request_router.py
├── input_interpreter.py
├── function_router.py
├── model_router.py
├── executor.py
├── deterministic_tools.py
├── knowledge.py
├── research_v3.py
├── knowledge/
├── personality.txt
├── identity.json
├── memory.json
└── settings.json
```

Put your source documents in the repository's configured `knowledge/` directory.

Then use SAGE's knowledge-maintenance command if supported by your current build:

```text
rebuild knowledge
```

Or:

```text
knowledge status
```

The exact indexing implementation belongs to the version of `knowledge.py` included with the repository.

---

# 9. Check the Model Names in SAGE

Before launching, open the current `sage.py` and router/model configuration files and check the model names.

For example:

```python
MODEL = "sage-qwen"
```

If the model router refers to names such as:

```text
sage-qwen
sage-qwen-fast
sage-vision
```

those models must actually exist in Ollama or the corresponding routes must be changed to the models installed on the new device.

Check available models with:

```bash
ollama list
```

This prevents errors such as:

```text
model not found
```

or API failures caused by requesting a model that does not exist locally.

---

# 10. Launch SAGE

### macOS / Linux

```bash
python3 sage.py
```

### Windows

```powershell
py sage.py
```

Do not assume `python` exists on every system. Many macOS and Linux installations use `python3`, while Windows commonly uses `py`.

---

# 11. Verify the Complete System

Run these checks in order.

### Check Python syntax

macOS / Linux:

```bash
python3 -m py_compile sage.py
```

Windows:

```powershell
py -m py_compile sage.py
```

### Check Ollama

```bash
ollama --version
ollama list
```

### Check the Ollama API

```bash
curl http://localhost:11434/api/tags
```

### Check the SAGE import chain

macOS / Linux:

```bash
python3 -c "import request_router; print('request_router OK')"
```

Windows:

```powershell
py -c "import request_router; print('request_router OK')"
```

Then launch SAGE.

---

# 12. Expected Request Flow

The intended SAGE architecture is:

```text
                         USER
                           │
                           ▼
                  INPUT INTERPRETER
                           │
                           ▼
                   FUNCTION ROUTER
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    CONVERSATION      DETERMINISTIC     INFORMATIONAL
          │                │                │
          ▼                ▼                ▼
       INSTANT          EXECUTE       LOCAL KNOWLEDGE
                                             │
                                      Useful information?
                                         /          \
                                       YES          NO
                                        │             │
                                        ▼             ▼
                                   AI SYNTHESIS      WEB
                                        │             │
                                        │             ▼
                                        │        AI SYNTHESIS
                                        │             │
                                        └──────┬──────┘
                                               ▼
                                          FINAL RESPONSE
                                               │
                                               ▼
                                              SAGE
```

The important rule is:

> **Local knowledge comes before web research.**

The AI model is the synthesis layer when the current SAGE build is configured to use one. It should receive the retrieved evidence, remove irrelevant material, combine useful information, and phrase the final answer naturally.

---

# 13. Model Switching

If model switching is enabled in the version you cloned, the model router should select the model based on the request.

A typical arrangement is:

```text
Simple / fast language task → fast model
Complex reasoning           → reasoning model
Image understanding         → vision model
Deterministic calculation   → no AI model
```

The names are configuration values, not universal Ollama model names. Always verify them with:

```bash
ollama list
```

---

# 14. Troubleshooting

## `ollama: command not found`

Ollama is not installed correctly or its executable is not available in your shell's PATH.

Reinstall Ollama and open a new terminal session.

## `404 Client Error: ... /api/chat`

First check:

```bash
curl http://localhost:11434/api/tags
```

Then check:

```bash
ollama list
```

Finally test the exact model name directly with `ollama run <model>`.

## `model not found`

The model name requested by SAGE does not exist in Ollama.

Use:

```bash
ollama list
```

Then either pull/build the required model or change SAGE's model configuration.

## `NameError` or `ImportError`

These usually indicate that the SAGE source files are out of sync.

Make sure the complete router set came from the same repository revision. In particular, interfaces between:

```text
input_interpreter.py
function_router.py
model_router.py
executor.py
request_router.py
```

must match.

## SAGE is very slow

Check whether a request is unnecessarily invoking an AI model.

The intended fast paths are:

```text
conversation → deterministic response
math / fixed operation → deterministic engine
```

Only requests that actually need language-model synthesis should invoke Ollama.

---

# 15. Moving SAGE to Another Computer

The easiest migration method is:

```text
GitHub repository
      ↓
New computer
      ↓
Install Python + Ollama
      ↓
Pull Qwen models
      ↓
Recreate SAGE custom models with Modelfiles
      ↓
Clone repository
      ↓
Install Python dependencies
      ↓
Rebuild local knowledge index
      ↓
Run SAGE
```

Do **not** copy Ollama's internal model directory between operating systems unless you specifically know what you are doing. Re-pulling or recreating the models through Ollama is simpler and less error-prone.

---

# 16. Recommended GitHub Repository Layout

Keep the repository portable:

```text
SAGE/
├── sage.py
├── request_router.py
├── input_interpreter.py
├── function_router.py
├── model_router.py
├── executor.py
├── deterministic_tools.py
├── knowledge.py
├── research_v3.py
├── Modelfile
├── personality.txt
├── identity.json
├── memory.json
├── settings.json
├── knowledge/
├── requirements.txt
└── README.md
```

Avoid committing machine-specific or generated data such as:

```text
.venv/
__pycache__/
*.pyc
.env
large model weights
local caches
temporary databases
```

Use `.gitignore` for those files.

---

# 17. First Boot Checklist

```text
[ ] Python installed
[ ] Ollama installed
[ ] Ollama service running
[ ] `ollama list` works
[ ] Qwen base model installed
[ ] SAGE custom model created, if required
[ ] Git repository cloned
[ ] Python dependencies installed
[ ] Knowledge documents present
[ ] Knowledge index rebuilt
[ ] `sage.py` passes py_compile
[ ] SAGE starts
[ ] Simple conversation is fast
[ ] Local knowledge retrieval works
[ ] AI synthesis works
[ ] Web fallback works only when required
```

---

## Final Note

SAGE is designed to remain **local-first**. Ollama provides the local model runtime; the SAGE code determines how requests are interpreted, routed, answered deterministically, searched locally, synthesized by an AI model, or escalated to read-only web research.

The repository should contain the **system**, while each device provides its own local runtime, models, hardware acceleration, and generated knowledge index.
