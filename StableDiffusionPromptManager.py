import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tempfile
import os
import atexit
import subprocess
import sys
import json
import re
import glob

# Optional image preview support for JPEG/WebP
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


class StableDiffusionPromptManager(tk.Tk):
    """
    A powerful and resizable GUI for managing Stable Diffusion prompts,
    featuring interactive line-by-line batch management and automatic cleanup.
    """
    def __init__(self):
        super().__init__()
        self.title("Stable Diffusion Prompt Manager")
        # Startup 100px wider/taller than before (was 1000x900)
        self.geometry("1100x1000")
        self.minsize(700, 600)

        # --- Enhanced Cleanup ---
        self._cleanup_old_files()  # Run cleanup on startup

        self._configure_styles()
        self.temp_file_handle, self.temp_file_path = None, None
        self._create_temp_file()
        atexit.register(self._cleanup)  # Standard cleanup for the current file on exit
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.undo_stack, self.redo_stack = [], []
        self.line_count_var = tk.StringVar(value="Lines in Batch: 0")

        # Template/preview state
        self._template_preview_images = []   # keep refs to PhotoImage to prevent GC
        self._last_template_dir = None       # recent folder used in the browser
        self._current_template_path = None   # last loaded template path

        # Persistent settings (default folder, etc.)
        self.settings_path = os.path.join(os.path.expanduser("~"), ".sdpm_settings.json")
        self.settings = self._load_settings()
        self.default_template_dir = tk.StringVar(value=self.settings.get("default_template_dir", ""))

        self._create_widgets()
        self._bind_events()
        self._save_state()

    # ---------------- Settings ----------------
    def _load_settings(self):
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_settings(self):
        try:
            data = dict(self.settings)
            data["default_template_dir"] = self.default_template_dir.get()
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    # ---------------- Cleanup ----------------
    def _cleanup_old_files(self):
        """Scans for and deletes orphaned temp files from previous runs."""
        temp_dir = tempfile.gettempdir()
        search_pattern = os.path.join(temp_dir, 'sd_prompt_*.txt')
        old_files = glob.glob(search_pattern)
        if not old_files:
            return
        for f_path in old_files:
            try:
                os.remove(f_path)
            except OSError:
                pass

    def _configure_styles(self):
        style = ttk.Style()
        self.PROMPT_COLOR = "#e1f5fe"
        self.NEGATIVE_COLOR = "#ffcdd2"
        self.BATCH_COLOR = "#e8f5e9"
        self.SCRATCHPAD_COLOR = "#f3e5f5"
        style.configure("Prompts.TLabelframe", background=self.PROMPT_COLOR)
        style.configure("Prompts.TLabelframe.Label", background=self.PROMPT_COLOR, font=('Helvetica', 10, 'bold'))
        style.configure("Negative.TLabelframe", background=self.NEGATIVE_COLOR)
        style.configure("Negative.TLabelframe.Label", background=self.NEGATIVE_COLOR, font=('Helvetica', 10, 'bold'))
        style.configure("Batch.TLabelframe", background=self.BATCH_COLOR)
        style.configure("Batch.TLabelframe.Label", background=self.BATCH_COLOR, font=('Helvetica', 10, 'bold'))
        style.configure("Scratchpad.TLabelframe", background=self.SCRATCHPAD_COLOR)
        style.configure("Scratchpad.TLabelframe.Label", background=self.SCRATCHPAD_COLOR, font=('Helvetica', 10, 'bold'))

    def _create_temp_file(self):
        try:
            self.temp_file_handle, self.temp_file_path = tempfile.mkstemp(suffix=".txt", prefix="sd_prompt_", text=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create temporary file: {e}")
            self.destroy()

    def _cleanup(self):
        """Cleans up the temp file for the current session."""
        if self.temp_file_handle is not None:
            try:
                os.close(self.temp_file_handle)
            except Exception:
                pass
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.remove(self.temp_file_path)
            except OSError:
                pass

    def _on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self._save_settings()
            self.destroy()

    # ---------------- UI ----------------
    def _create_widgets(self):
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1); main_frame.rowconfigure(0, weight=1)

        paned_window = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned_window.grid(row=0, column=0, sticky="nsew", pady=5)

        # --- 1. PROMPTS SECTION ---
        prompts_pane = self._create_pane(paned_window, 3)
        prompts_frame = self._create_labelframe(prompts_pane, "1. Compose Prompt", "Prompts.TLabelframe")
        prompts_frame.columnconfigure(1, weight=1)
        text_config = {'wrap': tk.WORD, 'undo': True, 'relief': 'solid', 'bd': 1}
        self.top_text = self._create_text_widget(prompts_frame, 0, "Top:", self.PROMPT_COLOR, 5, text_config)
        self.middle_text = self._create_text_widget(prompts_frame, 1, "Middle:", self.PROMPT_COLOR, 5, text_config)
        self.bottom_text = self._create_text_widget(prompts_frame, 2, "Bottom:", self.PROMPT_COLOR, 5, text_config)

        # --- 2. NEGATIVE PROMPTS ---
        negative_pane = self._create_pane(paned_window, 3)
        neg_prompts_frame = self._create_labelframe(negative_pane, "Negative Prompts", "Negative.TLabelframe")
        self.negative_text = tk.Text(neg_prompts_frame, height=5, **text_config)
        self.negative_text.pack(fill="both", expand=True, padx=5, pady=5)

        # --- 3. BATCH SECTION with Line Management ---
        batch_pane = self._create_pane(paned_window, 4)
        batch_frame = self._create_labelframe(batch_pane, "2. Build & Manage Batch", "Batch.TLabelframe")
        batch_frame.rowconfigure(0, weight=1); batch_frame.columnconfigure(0, weight=1)

        listbox_frame = ttk.Frame(batch_frame, style="Batch.TLabelframe")
        listbox_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        listbox_frame.rowconfigure(0, weight=1); listbox_frame.columnconfigure(0, weight=1)
        self.batch_listbox = tk.Listbox(listbox_frame, relief='solid', bd=1, selectmode=tk.SINGLE)
        self.batch_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.batch_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.batch_listbox.config(yscrollcommand=scrollbar.set)

        # Right-side controls (Copy button lives here)
        self.line_mgmt_frame = ttk.Frame(batch_frame, style="Batch.TLabelframe")
        self.line_mgmt_frame.grid(row=0, column=1, sticky="ns", padx=(10, 0), pady=5)
        self.edit_line_btn = ttk.Button(self.line_mgmt_frame, text="Edit", command=self._edit_line, state=tk.DISABLED)
        self.edit_line_btn.pack(fill="x", pady=2)
        self.remove_line_btn = ttk.Button(self.line_mgmt_frame, text="Remove", command=self._remove_line, state=tk.DISABLED)
        self.remove_line_btn.pack(fill="x", pady=2)
        self.move_up_btn = ttk.Button(self.line_mgmt_frame, text="Move Up ↑", command=lambda: self._move_line(-1), state=tk.DISABLED)
        self.move_up_btn.pack(fill="x", pady=(10, 2))
        self.move_down_btn = ttk.Button(self.line_mgmt_frame, text="Move Down ↓", command=lambda: self._move_line(1), state=tk.DISABLED)
        self.move_down_btn.pack(fill="x", pady=2)

        # Copy Whole Prompt button in the sidebar
        self.copy_line_btn = tk.Button(
            self.line_mgmt_frame, text="Copy Whole Prompt", command=self._copy_whole_prompt,
            font=('Helvetica', 10, 'bold'), bg="#9C27B0", fg="white",
            activebackground="#7B1FA2", activeforeground="white", relief=tk.RAISED, bd=2,
            state=tk.DISABLED
        )
        self.copy_line_btn.pack(fill="x", pady=(10, 2))

        # Bottom row under list: add/save/clear
        batch_buttons_frame = ttk.Frame(batch_frame, style="Batch.TLabelframe")
        batch_buttons_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        add_button = tk.Button(
            batch_buttons_frame, text="Add to Batch", command=self._add_to_batch,
            font=('Helvetica', 12, 'bold'), bg="#4CAF50", fg="white",
            activebackground="#45a049", activeforeground="white", relief=tk.RAISED, bd=2
        )
        add_button.pack(side="left", expand=True, fill="x", padx=2, pady=5)

        save_button = tk.Button(
            batch_buttons_frame, text="Save Batch to Temp File", command=self._save_batch_to_temp_file,
            font=('Helvetica', 10, 'bold'), bg="#2196F3", fg="white",
            activebackground="#1E88E5", activeforeground="white", relief=tk.RAISED, bd=2
        )
        save_button.pack(side="left", expand=True, fill="x", padx=2, pady=5)

        ttk.Button(batch_buttons_frame, text="Clear All", command=self._clear_batch)\
            .pack(side="left", expand=True, fill="x", padx=2, pady=5)

        ttk.Label(batch_frame, textvariable=self.line_count_var, background=self.BATCH_COLOR)\
            .grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        # --- 4. SCRATCHPAD ---
        scratchpad_pane = self._create_pane(paned_window, 2)
        scratchpad_frame = self._create_labelframe(scratchpad_pane, "Scratchpad (Not Saved)", "Scratchpad.TLabelframe")
        self.scratchpad_text = tk.Text(scratchpad_frame, height=5, **text_config)
        self.scratchpad_text.pack(fill="both", expand=True, padx=5, pady=5)

        # --- UTILITY and TEMPLATE frames ---
        actions_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        actions_frame.grid(row=1, column=0, sticky="ew", pady=5)
        for i in range(4): actions_frame.columnconfigure(i, weight=1)
        ttk.Button(actions_frame, text="Undo", command=self._undo).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(actions_frame, text="Redo", command=self._redo).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(actions_frame, text="Open Temp File Location", command=self._open_file_location).grid(row=0, column=2, sticky="ew", padx=2)
        ttk.Button(actions_frame, text="Edit Temp File", command=self._edit_temp_file).grid(row=0, column=3, sticky="ew", padx=2)

        template_frame = ttk.LabelFrame(main_frame, text="Template Management", padding="10")
        template_frame.grid(row=2, column=0, sticky="ew", pady=5)
        template_frame.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(template_frame, text="Save Current as Template", command=self._save_template).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(template_frame, text="Load Template", command=self._load_template_browser).grid(row=0, column=1, sticky="ew", padx=2)

        # Default template folder UI
        ttk.Label(template_frame, text="Default Template Folder:").grid(row=1, column=0, sticky="e", padx=2, pady=(8, 0))
        self.default_folder_entry = ttk.Entry(template_frame, textvariable=self.default_template_dir)
        self.default_folder_entry.grid(row=1, column=1, sticky="ew", padx=2, pady=(8, 0))
        ttk.Button(template_frame, text="Change…", command=self._change_default_folder).grid(row=1, column=2, sticky="ew", padx=2, pady=(8, 0))
        ttk.Button(template_frame, text="Clear", command=self._clear_default_folder).grid(row=1, column=3, sticky="ew", padx=2, pady=(8, 0))

    def _create_pane(self, parent, weight):
        pane = ttk.Frame(parent)
        parent.add(pane, weight=weight)
        pane.columnconfigure(0, weight=1); pane.rowconfigure(0, weight=1)
        return pane

    def _create_labelframe(self, parent, text, style):
        frame = ttk.LabelFrame(parent, text=text, padding="10", style=style)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)
        return frame

    def _create_text_widget(self, parent, row, label, color, height, config):
        ttk.Label(parent, text=label, background=color).grid(row=row, column=0, sticky=tk.NW, pady=2)
        text_widget = tk.Text(parent, height=height, **config)
        text_widget.grid(row=row, column=1, sticky="nsew")
        parent.rowconfigure(row, weight=1)
        return text_widget

    def _bind_events(self):
        for widget in [self.top_text, self.middle_text, self.bottom_text, self.negative_text]:
            widget.bind("<KeyRelease>", self._on_text_change)
        self.batch_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

    def _on_text_change(self, event=None): self._save_state()
    def _clean_text(self, text): return re.sub(r'\s+', ' ', text).strip()

    def _get_combined_prompt(self, parts_list):
        """Joins a list of text parts into a single string."""
        cleaned_parts = [self._clean_text(part) for part in parts_list]
        return ", __________ ,".join(filter(None, cleaned_parts))

    def _add_to_batch(self):
        main_prompt_parts = [w.get("1.0", tk.END) for w in [self.top_text, self.middle_text, self.bottom_text]]
        prompt = self._get_combined_prompt(main_prompt_parts)
        if not prompt:
            messagebox.showwarning("Warning", "Cannot add an empty prompt.")
            return
        self.batch_listbox.insert(tk.END, prompt)
        self._update_line_count()

    # NEW: Copy whole selected prompt to clipboard
    def _copy_whole_prompt(self):
        selection = self.batch_listbox.curselection()
        if not selection:
            messagebox.showinfo("Copy Whole Prompt", "Select a prompt line to copy.")
            return
        text = self.batch_listbox.get(selection[0])
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update_idletasks()
            messagebox.showinfo("Copy Whole Prompt", "Prompt copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard: {e}")

    def _update_line_count(self): self.line_count_var.set(f"Lines in Batch: {self.batch_listbox.size()}")

    def _clear_batch(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the entire batch?"):
            self.batch_listbox.delete(0, tk.END)
            self._on_listbox_select()
            self._update_line_count()

    def _save_batch_to_temp_file(self):
        content = "\n".join(self.batch_listbox.get(0, tk.END))
        if not content:
            messagebox.showwarning("Warning", "Batch is empty. Nothing to save.")
            return
        try:
            with open(self.temp_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Batch saved to temporary file:\n{self.temp_file_path}")
        except Exception as e: messagebox.showerror("Error", f"Failed to save to temp file: {e}")

    def _on_listbox_select(self, event=None):
        is_selected = bool(self.batch_listbox.curselection())
        new_state = tk.NORMAL if is_selected else tk.DISABLED
        self.edit_line_btn.config(state=new_state)
        self.remove_line_btn.config(state=new_state)
        self.move_up_btn.config(state=new_state)
        self.move_down_btn.config(state=new_state)
        self.copy_line_btn.config(state=new_state)

    def _edit_line(self):
        selection = self.batch_listbox.curselection()
        if not selection: return
        original_index = selection[0]
        original_text = self.batch_listbox.get(original_index)

        # --- EDITOR WINDOW ---
        editor = tk.Toplevel(self)
        editor.title("Edit Prompt In Sections")
        editor.geometry("800x400")
        editor.minsize(600, 300)
        editor.transient(self); editor.grab_set()

        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(0, weight=1)

        prompts_frame = self._create_labelframe(editor, "Edit Prompt Parts", "Prompts.TLabelframe")

        text_config = {'wrap': tk.WORD, 'undo': True, 'relief': 'solid', 'bd': 1}
        edit_top = self._create_text_widget(prompts_frame, 0, "Top:", self.PROMPT_COLOR, 5, text_config)
        edit_mid = self._create_text_widget(prompts_frame, 1, "Middle:", self.PROMPT_COLOR, 5, text_config)
        edit_bot = self._create_text_widget(prompts_frame, 2, "Bottom:", self.PROMPT_COLOR, 5, text_config)

        prompt_parts = original_text.split(', __________ ,')
        text_widgets = [edit_top, edit_mid, edit_bot]
        for i, part in enumerate(prompt_parts):
            if i < len(text_widgets):
                text_widgets[i].insert("1.0", part)

        def save_edit():
            new_parts = [w.get("1.0", tk.END) for w in [edit_top, edit_mid, edit_bot]]
            new_text = self._get_combined_prompt(new_parts)
            if new_text:
                self.batch_listbox.delete(original_index)
                self.batch_listbox.insert(original_index, new_text)
                self.batch_listbox.select_set(original_index)
            editor.destroy()

        button_frame = ttk.Frame(editor, padding=10)
        button_frame.grid(row=1, column=0, sticky='ew')
        button_frame.columnconfigure((0, 1), weight=1)

        save_btn = ttk.Button(button_frame, text="Save Changes", command=save_edit, style="Accent.TButton")
        save_btn.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        ttk.Style().configure("Accent.TButton", font=('Helvetica', 10, 'bold'))

        cancel_btn = ttk.Button(button_frame, text="Cancel", command=editor.destroy)
        cancel_btn.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        editor.bind('<Escape>', lambda e: editor.destroy())
        edit_top.focus_set()

    def _remove_line(self):
        selection = self.batch_listbox.curselection()
        if not selection: return
        self.batch_listbox.delete(selection[0])
        self._on_listbox_select()
        self._update_line_count()

    def _move_line(self, direction):
        selection = self.batch_listbox.curselection()
        if not selection: return

        idx = selection[0]
        new_idx = idx + direction

        if 0 <= new_idx < self.batch_listbox.size():
            line_text = self.batch_listbox.get(idx)
            self.batch_listbox.delete(idx)
            self.batch_listbox.insert(new_idx, line_text)
            self.batch_listbox.select_set(new_idx)
            self.batch_listbox.activate(new_idx)

    def _get_current_state(self):
        return {"top": self.top_text.get("1.0", tk.END).strip(),
                "middle": self.middle_text.get("1.0", tk.END).strip(),
                "bottom": self.bottom_text.get("1.0", tk.END).strip(),
                "negative": self.negative_text.get("1.0", tk.END).strip()}

    def _save_state(self):
        current_state = self._get_current_state()
        if not self.undo_stack or self.undo_stack[-1] != current_state:
            self.undo_stack.append(current_state)
            self.redo_stack.clear()

    def _set_state(self, state):
        widgets_map = {self.top_text: "top", self.middle_text: "middle",
                       self.bottom_text: "bottom", self.negative_text: "negative"}
        for widget, key in widgets_map.items():
            widget.delete("1.0", tk.END); widget.insert("1.0", state.get(key, ""))

    def _undo(self):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self._set_state(self.undo_stack[-1])
        else: messagebox.showinfo("Info", "Nothing to undo.")

    def _redo(self):
        if self.redo_stack:
            state_to_restore = self.redo_stack.pop()
            self.undo_stack.append(state_to_restore)
            self._set_state(state_to_restore)
        else: messagebox.showinfo("Info", "Nothing to redo.")

    def _open_file_location(self):
        if not os.path.exists(self.temp_file_path):
            messagebox.showerror("Error", "Temp file doesn't exist. Save the batch first.")
            return
        try:
            if sys.platform == "win32": subprocess.run(['explorer', '/select,', self.temp_file_path])
            elif sys.platform == "darwin": subprocess.run(['open', '-R', self.temp_file_path])
            else: subprocess.run(['xdg-open', os.path.dirname(self.temp_file_path)])
        except Exception as e: messagebox.showerror("Error", f"Could not open file location: {e}")

    def _edit_temp_file(self):
        if not os.path.exists(self.temp_file_path):
            messagebox.showerror("Error", "Temp file doesn't exist. Save the batch first.")
            return
        try:
            if sys.platform == "win32": os.startfile(self.temp_file_path)
            elif sys.platform == "darwin": subprocess.run(['open', self.temp_file_path])
            else: subprocess.run(['xdg-open', self.temp_file_path])
        except Exception as e: messagebox.showerror("Error", f"Failed to open file for editing: {e}")

    def _get_all_data(self):
        current_prompts = self._get_current_state()
        return {"prompt_parts": {k: v for k, v in current_prompts.items() if k != 'negative'},
                "negative_prompt": current_prompts["negative"]}

    def _load_data(self, data):
        try:
            state_to_load = {"top": data.get("prompt_parts", {}).get("top", ""),
                             "middle": data.get("prompt_parts", {}).get("middle", ""),
                             "bottom": data.get("prompt_parts", {}).get("bottom", ""),
                             "negative": data.get("negative_prompt", "")}
            self._set_state(state_to_load)
            self._save_state()
            messagebox.showinfo("Success", "Template loaded successfully.")
        except Exception as e: messagebox.showerror("Error", f"Failed to load data: {e}")

    # ---------- Save with default image selection + preselect current template name ----------
    def _save_template(self):
        # If a template is loaded, preselect its folder+name; otherwise use defaults
        if self._current_template_path and os.path.isfile(self._current_template_path):
            initialdir = os.path.dirname(self._current_template_path)
            initialfile = os.path.basename(self._current_template_path)
        else:
            initialdir = self.default_template_dir.get() or self._last_template_dir or os.getcwd()
            # Suggest a simple default filename
            initialfile = "template.json"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialdir=initialdir,
            initialfile=initialfile
        )
        if not filepath: return
        try:
            data = self._get_all_data()

            folder = os.path.dirname(filepath) or "."
            stem = os.path.splitext(os.path.basename(filepath))[0]
            matches = self._find_related_media(folder, stem)

            default_image = None
            image_matches = [m for m in matches if m.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
            if len(image_matches) == 1:
                default_image = os.path.basename(image_matches[0])
            elif len(image_matches) > 1:
                default_image = self._choose_default_image_dialog(image_matches)

            if default_image:
                data["default_image"] = default_image  # store just the filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

            # Remember this folder/file for convenience
            self._last_template_dir = folder
            self._current_template_path = filepath
            messagebox.showinfo("Success", f"Template saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")

    # ---------- Template browser with image/video preview & default folder support ----------
    def _load_template_browser(self):
        # Prefer default folder; let user change within the browser
        directory = self.default_template_dir.get().strip()
        if not directory or not os.path.isdir(directory):
            initialdir = self._last_template_dir or os.getcwd()
            directory = filedialog.askdirectory(initialdir=initialdir, title="Select Template Folder")
            if not directory:
                return
        self._last_template_dir = directory

        self._open_template_browser_window(directory)

    def _open_template_browser_window(self, directory):
        json_files = sorted(glob.glob(os.path.join(directory, "*.json")))
        win = tk.Toplevel(self)
        # Larger load-template UI
        win.title(f"Load Template — {directory}")
        win.geometry("1080x740")  # was ~980x640; +100 both ways
        win.minsize(960, 620)
        win.transient(self); win.grab_set()

        # Layout: give more width to the left list so long names fit better
        win.columnconfigure(0, weight=2, minsize=360)  # wider left column
        win.columnconfigure(1, weight=3)
        win.rowconfigure(0, weight=1)
        win.rowconfigure(1, weight=0)

        # Left: list of templates
        left = ttk.Frame(win, padding=10)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(3, weight=1)
        ttk.Label(left, text="Templates").grid(row=0, column=0, sticky="w")

        if not json_files:
            ttk.Label(left, text="(No .json templates found in this folder)").grid(row=1, column=0, sticky="w", pady=(4, 4))

        # Wider listbox + horizontal scrollbar so long names are readable
        listbox = tk.Listbox(left, selectmode=tk.SINGLE, exportselection=False, width=50)
        listbox.grid(row=3, column=0, sticky="nsew")
        hbar = ttk.Scrollbar(left, orient="horizontal", command=listbox.xview)
        hbar.grid(row=4, column=0, sticky="ew")
        listbox.configure(xscrollcommand=hbar.set)
        for path in json_files:
            listbox.insert(tk.END, os.path.basename(path))

        # Right: preview area
        right = ttk.Frame(win, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self._template_preview_images = []  # reset preview image refs

        name_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=name_var, font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w")

        preview_canvas = tk.Canvas(right, bd=1, relief="solid", width=720, height=440)
        preview_canvas.grid(row=1, column=0, sticky="nsew", pady=(6, 6))

        files_frame = ttk.Frame(right)
        files_frame.grid(row=2, column=0, sticky="ew")
        files_frame.columnconfigure(0, weight=1)
        files_list_var = tk.StringVar(value=[])
        files_listbox = tk.Listbox(files_frame, listvariable=files_list_var, height=6, exportselection=False)
        files_listbox.grid(row=0, column=0, sticky="ew")

        # Bottom buttons
        btns = ttk.Frame(win, padding=10)
        btns.grid(row=1, column=0, columnspan=2, sticky="ew")
        for i in range(5): btns.columnconfigure(i, weight=1)

        load_btn = ttk.Button(btns, text="Load Selected", state=tk.DISABLED)
        load_btn.grid(row=0, column=0, sticky="ew", padx=5)
        change_folder_btn = ttk.Button(btns, text="Change Folder…")
        change_folder_btn.grid(row=0, column=1, sticky="ew", padx=5)
        set_default_btn = ttk.Button(btns, text="Set Current as Default")
        set_default_btn.grid(row=0, column=2, sticky="ew", padx=5)
        open_folder_btn = ttk.Button(btns, text="Open Folder", command=lambda: self._open_dir(directory))
        open_folder_btn.grid(row=0, column=3, sticky="ew", padx=5)
        close_btn = ttk.Button(btns, text="Close", command=win.destroy)
        close_btn.grid(row=0, column=4, sticky="ew", padx=5)

        def refresh_preview(json_path):
            base = os.path.basename(json_path)  # show full file name incl. extension
            name_var.set(base)

            # Find related media
            matches = self._find_related_media(os.path.dirname(json_path), os.path.splitext(base)[0])

            # Show filenames list (mark default)
            shown_names = []
            for m in matches:
                label = os.path.basename(m)
                if self._is_default_image(json_path, m):
                    label += "  (default)"
                shown_names.append(label)
            files_list_var.set(shown_names)

            # Show preview
            preview_canvas.delete("all")
            # If canvas hasn't realized size yet, use fallback sizes
            cw = preview_canvas.winfo_width() or 720
            ch = preview_canvas.winfo_height() or 440
            img_path = self._pick_preview_image(json_path, matches)
            if img_path:
                img_obj = self._load_thumbnail(img_path, max_size=(cw, ch))
                if img_obj:
                    self._template_preview_images = [img_obj]  # keep ref
                    x = max(0, (cw - img_obj.width()) // 2)
                    y = max(0, (ch - img_obj.height()) // 2)
                    preview_canvas.create_image(x, y, image=img_obj, anchor="nw")
                else:
                    preview_canvas.create_text(10, 10, text="(Image preview not available. PNG/GIF always work; JPEG/WebP need Pillow.)", anchor="nw")
            else:
                preview_canvas.create_text(10, 10, text="(No image found for this template)", anchor="nw")

        def on_select(_event=None):
            sel = listbox.curselection()
            if not sel:
                load_btn.config(state=tk.DISABLED)
                name_var.set("")
                files_list_var.set([])
                preview_canvas.delete("all")
                return
            idx = sel[0]
            json_path = json_files[idx]
            refresh_preview(json_path)
            load_btn.config(state=tk.NORMAL)

        def do_load():
            sel = listbox.curselection()
            if not sel: return
            json_path = json_files[sel[0]]
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._load_data(data)
                # Record the path so Save uses it as default selection
                self._current_template_path = json_path
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load template: {e}")

        def do_change_folder():
            initialdir = self._last_template_dir or directory
            new_dir = filedialog.askdirectory(initialdir=initialdir, title="Select Template Folder")
            if not new_dir:
                return
            win.destroy()
            self._last_template_dir = new_dir
            self._open_template_browser_window(new_dir)

        def do_set_default():
            self.default_template_dir.set(directory)
            self._save_settings()
            messagebox.showinfo("Default Folder", f"Default template folder set to:\n{directory}")

        # Redraw preview when canvas resizes to ensure first image shows
        def on_canvas_resize(_evt=None):
            sel = listbox.curselection()
            if sel:
                refresh_preview(json_files[sel[0]])

        preview_canvas.bind("<Configure>", on_canvas_resize)

        # Bindings / commands
        listbox.bind("<<ListboxSelect>>", on_select)
        load_btn.config(command=do_load)
        change_folder_btn.config(command=do_change_folder)
        set_default_btn.config(command=do_set_default)

        # Preselect first (if any) and force a second-pass redraw so image shows
        if json_files:
            listbox.selection_set(0)
            win.update_idletasks()
            on_select()
            # Force another pass after the window fully maps to ensure preview renders
            win.after(120, on_select)

    # ---------- helpers for template browser ----------
    def _open_dir(self, directory):
        try:
            if sys.platform == "win32":
                subprocess.run(['explorer', directory])
            elif sys.platform == "darwin":
                subprocess.run(['open', directory])
            else:
                subprocess.run(['xdg-open', directory])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open directory: {e}")

    def _find_related_media(self, folder, stem):
        """
        Find images/videos in the same folder that match naming:
        stem.ext, stem-01.ext, stem_01.ext, stem01.ext, stem-02.ext, etc.
        """
        exts = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mov', '.avi', '.mkv', '.webm']
        # Allow hyphen/underscore/space/number variants by a broad wildcard
        patterns = [os.path.join(folder, f"{stem}*{ext}") for ext in exts]
        # Include exact name too
        patterns += [os.path.join(folder, f"{stem}{ext}") for ext in exts]
        matches = set()
        for pat in patterns:
            for p in glob.glob(pat):
                base = os.path.basename(p)
                if base.lower().startswith(stem.lower()):
                    matches.add(p)
        # Sort: images first, then videos; then lexicographically
        def sort_key(p):
            is_image = p.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
            return (0 if is_image else 1, os.path.basename(p).lower())
        return sorted(matches, key=sort_key)

    def _is_default_image(self, json_path, media_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            default = data.get("default_image")
            if not default:
                return False
            return os.path.basename(media_path) == os.path.basename(default)
        except Exception:
            return False

    def _pick_preview_image(self, json_path, matches):
        # prefer explicit default_image if set and is an image; else first image
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            default = data.get("default_image")
        except Exception:
            default = None
        if default:
            folder = os.path.dirname(json_path)
            candidate = os.path.join(folder, default)
            if os.path.exists(candidate) and candidate.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                return candidate
        for m in matches:
            if m.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                return m
        return None

    def _load_thumbnail(self, path, max_size=(720, 440)):
        """
        Returns a Tk PhotoImage for preview. Supports:
        - PNG/GIF always via Tk PhotoImage
        - JPEG/WebP if Pillow is available
        """
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in ('.png', '.gif'):
                img = tk.PhotoImage(file=path)
                # downscale via subsample (integer only) to fit max_size
                w, h = img.width(), img.height()
                factor_w = max(1, int(w / max_size[0]))
                factor_h = max(1, int(h / max_size[1]))
                factor = max(factor_w, factor_h)
                if factor > 1:
                    img = img.subsample(factor, factor)
                return img
            elif ext in ('.jpg', '.jpeg', '.webp'):
                if not PIL_AVAILABLE:
                    return None
                im = Image.open(path)
                im.thumbnail(max_size)
                return ImageTk.PhotoImage(im)
            else:
                return None
        except Exception:
            return None

    def _choose_default_image_dialog(self, image_paths):
        """
        Let the user pick a default image among multiple matches.
        Returns the chosen basename or None.
        """
        dlg = tk.Toplevel(self)
        dlg.title("Choose Default Image")
        dlg.geometry("700x500")
        dlg.minsize(600, 400)
        dlg.transient(self); dlg.grab_set()

        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        ttk.Label(dlg, text="Select the default image for this template:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

        frame = ttk.Frame(dlg, padding=10)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(frame, bd=1, relief="solid")
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.columnconfigure(1, weight=1)

        choice = tk.StringVar(value=os.path.basename(image_paths[0]))
        previews = []

        def add_row(img_path, row):
            thumb = self._load_thumbnail(img_path, max_size=(200, 150))
            if thumb:
                previews.append(thumb)
                label = tk.Label(inner, image=thumb)
            else:
                label = tk.Label(inner, text="[no preview]")
            label.grid(row=row, column=0, padx=8, pady=8, sticky="w")
            rb = ttk.Radiobutton(inner, text=os.path.basename(img_path), value=os.path.basename(img_path), variable=choice)
            rb.grid(row=row, column=1, sticky="w", padx=6)

        for i, p in enumerate(image_paths):
            add_row(p, i)

        def on_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", on_configure)

        btns = ttk.Frame(dlg, padding=10)
        btns.grid(row=2, column=0, sticky="ew")
        btns.columnconfigure((0,1), weight=1)
        result = {"val": None}

        def ok():
            result["val"] = choice.get()
            dlg.destroy()

        def cancel():
            result["val"] = None
            dlg.destroy()

        ttk.Button(btns, text="OK", command=ok).grid(row=0, column=0, sticky="ew", padx=5)
        ttk.Button(btns, text="Cancel", command=cancel).grid(row=0, column=1, sticky="ew", padx=5)

        dlg.wait_window()
        return result["val"]

    # ---------- Default folder helpers ----------
    def _change_default_folder(self):
        initialdir = self.default_template_dir.get() or self._last_template_dir or os.getcwd()
        folder = filedialog.askdirectory(initialdir=initialdir, title="Choose Default Template Folder")
        if not folder:
            return
        self.default_template_dir.set(folder)
        self._save_settings()

    def _clear_default_folder(self):
        self.default_template_dir.set("")
        self._save_settings()

    # ---------- Legacy loader entry maintained ----------
    def _load_template(self):
        self._load_template_browser()


if __name__ == "__main__":
    app = StableDiffusionPromptManager()
    app.mainloop()
