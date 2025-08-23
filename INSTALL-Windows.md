# Install & Run — Windows (StableDiffusionPromptManager)

These steps set up **StableDiffusionPromptManager** on **Windows 10/11**.

> This app does **not** run Stable Diffusion or touch your models; it’s a GUI to help you compose and manage prompts and template files you can copy into your own SD workflow.

## 1) Install prerequisites

- **Python 3.9+** — https://www.python.org/downloads/
- *(Optional)* **Git** for cloning — https://git-scm.com/

## 2) Get the code

- **ZIP:** Download the repo ZIP from GitHub → extract
- **Git:**
```powershell
git clone https://github.com/<you>/StableDiffusionPromptManager.git
cd StableDiffusionPromptManager
```

## 3) Create and activate a virtual environment
```powershell
py -3 -m venv venv
.\venv\Scripts\activate
```
To deactivate later:
```powershell
deactivate
```

> **Activation script blocked?** Temporarily allow scripts for this session:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate
```

## 4) Install Python dependencies
```powershell
pip install -r requirements.txt
```

> `Pillow` enables JPEG/WebP previews in the template browser. PNG/GIF previews work without Pillow.

## 5) Run the app

If you keep the original filename with spaces:
```powershell
python "Stable Diffusion Prompt File Manager.py"
```

If you rename it (recommended) to `stable_diffusion_prompt_manager.py`:
```powershell
python stable_diffusion_prompt_manager.py
```

A window titled **“Stable Diffusion Prompt Manager”** will open.

## 6) (Optional) Build a single EXE

```powershell
pip install pyinstaller
pyinstaller --name StableDiffusionPromptManager --onefile --windowed "Stable Diffusion Prompt File Manager.py"
# EXE appears in .\dist\StableDiffusionPromptManager.exe
```

## Troubleshooting

- **`No module named 'tkinter'` (Linux/WSL)** → install your distro’s Tk package (e.g., `sudo apt install python3-tk`).
- **Images don’t preview** → for JPEG/WebP previews, ensure `Pillow` is installed. PNG/GIF should always preview.
- **Can’t activate venv (policy)** → see the `Set-Execution-Policy` command above.
