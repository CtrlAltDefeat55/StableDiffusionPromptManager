# StableDiffusionPromptManager

A lightweight **Tkinter** desktop app to build, batch, and manage **Stable Diffusion prompts** with a friendly UI, undo/redo, a negative‑prompt area, a scratchpad, and a **Template Browser** that previews related images and lets you set a default image per template.

> This project focuses on **prompt composition and organization**. It does not launch Stable Diffusion; copy the generated prompts wherever you run SD (WebUI, ComfyUI, Invoke, etc.).

## 📸 Screenshots
<!-- Replace these placeholders with real screenshots from your system -->
<img alt="Main UI" src="./assets/sdpm-ui.png" width="800">
<br/>
<img alt="Load Templates (Low)" src="./assets/sdpm-templates-low.png" width="800">

## ✨ Features

- **Three‑part prompt composer** (*Top / Middle / Bottom*) joined with a visible separator (`, __________ ,`).
- **Negative Prompts** pane to keep unwanted tokens in one place.
- **Batch builder**: add composed lines, reorder (↑/↓), edit a line in its 3 parts, remove, and **copy whole prompt** to clipboard.
- **Save Batch to Temp File** and open the folder/file directly from the app.
- **Scratchpad** for throwaway notes (not saved).
- **Template Management**:
  - Save current UI state to **JSON** (stores `prompt_parts` and `negative_prompt`; also records a `default_image` if you pick one).
  - **Load Template** browser with file list and **image preview**.
  - **Default template folder** preference (persisted).
  - Optional image previews: PNG/GIF always; **JPEG/WebP require Pillow**.
- **Automatic cleanup** of orphaned temp files at startup.
- **Undo/Redo** of prompt fields.

## 🧰 Requirements

- **Python 3.9+**
- **Tkinter/ttk** (bundled with standard Python on Windows/macOS; on Linux install your distro’s `python3-tk`)
- **Pillow** (recommended) for JPEG/WebP previews in the template browser

See **[requirements.txt](./requirements.txt)**.

## 🚀 Quick Start (Windows)

```powershell
py -3 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python "Stable Diffusion Prompt File Manager.py"
```
> Prefer no spaces? Rename to `stable_diffusion_prompt_manager.py` and run `python stable_diffusion_prompt_manager.py`.

More detail: **[INSTALL-Windows.md](./INSTALL-Windows.md)**

## 🖱️ How It Works

1. Write **Top / Middle / Bottom** prompt parts.  
2. Add optional **Negative prompts**.  
3. Click **Add to Batch** to append a full prompt line formed as `Top, __________ ,Middle, __________ ,Bottom`.  
4. Select a line to **Edit / Remove / Move** or **Copy Whole Prompt**.  
5. **Save Batch to Temp File** to get a text file of all lines (the app can open the folder or the file for you).  
6. Use **Save Current as Template** to capture your current fields into a JSON.  
7. Use **Load Template** to browse a folder of JSON templates with image previews and pick one to populate the UI.

### Template files

Saved templates look like:

```jsonc
{
  "prompt_parts": {"top": "...", "middle": "...", "bottom": "..."},
  "negative_prompt": "...",
  "default_image": "mytemplate-01.png"   // optional, stored as filename only
}
```

When loading, the browser lists images/videos in the same folder with similar names (e.g., `mytemplate.png`, `mytemplate-01.jpg`) and previews the default or first image. The **Default Template Folder** setting and last-used folder are remembered across runs.

## 📂 Project Layout

```
StableDiffusionPromptManager/
├─ assets/
│  ├─ sdpm-ui.png                # replace with a real screenshot
│  └─ sdpm-templates-low.png     # replace with a real screenshot of the Load Template view
├─ INSTALL-Windows.md
├─ README.md
├─ requirements.txt
└─ Stable Diffusion Prompt File Manager.py   # main script (rename if you like)
```

## 🔗 Quick Links

- ▶️ **Run it:** [`Stable Diffusion Prompt File Manager.py`](./Stable%20Diffusion%20Prompt%20File%20Manager.py)
- 📦 **Install (Windows):** [`INSTALL-Windows.md`](./INSTALL-Windows.md)
- 🧩 **Dependencies:** [`requirements.txt`](./requirements.txt)

## 🧪 Build a single-file EXE (optional)

```powershell
pip install pyinstaller
pyinstaller --name StableDiffusionPromptManager --onefile --windowed "Stable Diffusion Prompt File Manager.py"
```

## 🛠️ Troubleshooting

- **No previews for JPEG/WebP** → install Pillow (`pip install Pillow`). PNG/GIF preview without Pillow.
- **`tkinter` not found (Linux/WSL)** → install `python3-tk` from your distro.
- **Temp file missing** → click **Save Batch to Temp File** first; then use **Open Temp File Location** or **Edit Temp File**.

## 🙏 Credits

- UI/UX pattern for Windows setup and quick‑start adapted from similar Tkinter/PyQt app READMEs and install guides in past projects.
- Built with love for artists who iterate on prompts.

---

**License**: MIT (or your choice). Add a `LICENSE` file if you want a specific license.
