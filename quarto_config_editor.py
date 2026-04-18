import copy
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import yaml

from dialog_dirty_utils import DirtyStateController, confirm_discard_changes
from ui_theme import COLORS, center_on_parent, style_dialog


class QuartoConfigEditor(tk.Toplevel):
    PROJECT_TYPES = ("book", "website", "article", "manuscript")
    LANG_OPTIONS = ("de", "en", "fr", "es", "it", "nl", "pl")
    TOC_DEPTH_OPTIONS = ("1", "2", "3", "4", "5", "6")
    SECTION_NUMBERING_OPTIONS = ("none", "1", "1.1", "1.1.1", "I", "A")
    PAPER_SIZE_OPTIONS = ("a4", "a5", "letter", "legal")
    WIDOW_ORPHAN_OPTIONS = ("auto", "1", "2", "3", "4")
    RIGHTS_LICENSE_OPTIONS = (
        "all-rights-reserved",
        "cc-by-4.0",
        "cc-by-sa-4.0",
        "cc-by-nd-4.0",
        "cc-by-nc-4.0",
        "cc-by-nc-sa-4.0",
        "cc-by-nc-nd-4.0",
        "public-domain",
    )
    FRONTMATTER_PROFILE_OPTIONS = (
        "none",
        "minimal",
        "standard",
        "extended",
        "publisher-print",
        "publisher-ebook",
    )
    HTML_THEME_OPTIONS = (
        "default",
        "cosmo",
        "flatly",
        "journal",
        "litera",
        "lumen",
        "lux",
        "materia",
        "minty",
        "morph",
        "pulse",
        "quartz",
        "sandstone",
        "simplex",
        "sketchy",
        "slate",
        "solar",
        "spacelab",
        "superhero",
        "united",
        "vapor",
        "yeti",
        "zephyr",
    )

    def __init__(self, parent, yaml_path, on_save=None):
        super().__init__(parent)
        self.parent = parent
        self.yaml_path = Path(yaml_path)
        self.on_save = on_save

        self._base_title = "Quarto.yml konfigurieren"
        self.title(self._base_title)
        self._dirty_controller = DirtyStateController(self, self._base_title)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        center_on_parent(self, parent, 760, 620)
        self.config_data = self._load_config()

        self.project_type_var = None
        self.output_dir_var = None
        self.book_title_var = None
        self.book_subtitle_var = None
        self.author_var = None
        self.lang_var = None
        self.book_description_var = None
        self.book_keywords_var = None
        self.publisher_var = None
        self.imprint_var = None
        self.isbn_print_var = None
        self.isbn_ebook_var = None
        self.edition_var = None
        self.rights_holder_var = None
        self.rights_license_var = None
        self.frontmatter_profile_var = None
        self.profile_hint_var = None
        self.typst_keep_typ_var = None
        self.typst_toc_var = None
        self.typst_toc_depth_var = None
        self.typst_number_sections_var = None
        self.typst_section_numbering_var = None
        self.typst_papersize_var = None
        self.typst_widows_var = None
        self.typst_orphans_var = None
        self.html_theme_var = None
        self.html_toc_var = None
        self._initial_form_values = {}

        self._build_ui()

    def _load_config(self):
        if not self.yaml_path.exists():
            return {}
        try:
            with self.yaml_path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
            return loaded if isinstance(loaded, dict) else {}
        except (OSError, yaml.YAMLError, ValueError, TypeError) as exc:
            messagebox.showerror(
                "Fehler beim Laden von _quarto.yml",
                f"Die Datei konnte nicht gelesen oder geparst werden:\n{self.yaml_path}\n\nGrund:\n{exc}",
                parent=self,
            )
            return {}

    def _build_ui(self):
        style_dialog(self)

        root = tk.Frame(self, bg=COLORS["app_bg"])
        root.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(root, bg=COLORS["app_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS["app_bg"])
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(content_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        header = tk.Frame(content, bg=COLORS["app_bg"], padx=16, pady=14)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="Quarto-Konfiguration",
            bg=COLORS["app_bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Bearbeitet die wichtigsten Buch- und Formatoptionen in _quarto.yml.",
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        self._build_project_section(content)
        self._build_book_section(content)
        self._build_publisher_section(content)
        self._build_typst_section(content)
        self._build_html_section(content)
        self._capture_initial_form_values()
        self._refresh_dirty_state()
        self._start_dirty_watch()

        btn_row = ttk.Frame(content, padding=(16, 16))
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Abbrechen", style="Tool.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_row, text="Speichern", style="Accent.TButton", command=self._save).pack(side=tk.RIGHT)

    def _build_project_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Projekt", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        project_type = str(self._get_nested("project", "type", default="book"))
        if project_type not in self.PROJECT_TYPES:
            project_type = "book"
        self.project_type_var = tk.StringVar(value=project_type)
        self.output_dir_var = tk.StringVar(value=self._get_nested("project", "output-dir", default="export/_book"))

        self._add_row(
            body,
            "Projekt-Typ",
            self._readonly_combo(body, self.project_type_var, self.PROJECT_TYPES, width=18),
            0,
        )
        self._add_row(body, "Output-Ordner", ttk.Entry(body, textvariable=self.output_dir_var, width=40), 1)

    def _build_book_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Buch", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        self.book_title_var = tk.StringVar(value=self._get_nested("book", "title", default=""))
        self.book_subtitle_var = tk.StringVar(value=self._get_root_or_book("subtitle", default=""))
        self.author_var = tk.StringVar(value=self._normalize_author(self._get_nested("author", default="")))
        lang_value = str(self._get_nested("lang", default="de"))
        if lang_value not in self.LANG_OPTIONS:
            lang_value = "de"
        self.lang_var = tk.StringVar(value=lang_value)
        self.book_description_var = tk.StringVar(value=self._get_root_or_book("description", default=""))
        self.book_keywords_var = tk.StringVar(value=self._normalize_keywords(self._get_root_or_book("keywords", default=[])))

        self._add_row(body, "Buchtitel", ttk.Entry(body, textvariable=self.book_title_var, width=50), 0)
        self._add_row(body, "Untertitel", ttk.Entry(body, textvariable=self.book_subtitle_var, width=50), 1)
        self._add_row(body, "Autor(en)", ttk.Entry(body, textvariable=self.author_var, width=50), 2)
        self._add_row(
            body,
            "Sprache",
            self._readonly_combo(body, self.lang_var, self.LANG_OPTIONS, width=10),
            3,
        )
        self._add_row(body, "Beschreibung", ttk.Entry(body, textvariable=self.book_description_var, width=60), 4)
        self._add_row(body, "Keywords (CSV)", ttk.Entry(body, textvariable=self.book_keywords_var, width=60), 5)

    def _build_publisher_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Verlagsspezifika", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        self.publisher_var = tk.StringVar(value=self._get_root_or_book("publisher", default=""))
        self.imprint_var = tk.StringVar(value=self._get_root_or_book("imprint", default=""))
        self.isbn_print_var = tk.StringVar(value=self._get_root_or_book("isbn-print", default=""))
        self.isbn_ebook_var = tk.StringVar(value=self._get_root_or_book("isbn-ebook", default=""))
        self.edition_var = tk.StringVar(value=str(self._get_root_or_book("edition", default="1")))
        self.rights_holder_var = tk.StringVar(value=self._get_root_or_book("rights-holder", default=""))
        rights_license = str(self._get_root_or_book("rights-license", default="all-rights-reserved"))
        if rights_license not in self.RIGHTS_LICENSE_OPTIONS:
            rights_license = "all-rights-reserved"
        self.rights_license_var = tk.StringVar(value=rights_license)
        frontmatter_profile = str(self._get_root_or_book("frontmatter-profile", default="standard"))
        if frontmatter_profile not in self.FRONTMATTER_PROFILE_OPTIONS:
            frontmatter_profile = "standard"
        self.frontmatter_profile_var = tk.StringVar(value=frontmatter_profile)
        self.profile_hint_var = tk.StringVar(value="")

        edition_values = tuple(str(index) for index in range(1, 11))
        if self.edition_var.get() not in edition_values:
            self.edition_var.set("1")

        self._add_row(body, "Verlag", ttk.Entry(body, textvariable=self.publisher_var, width=40), 0)
        self._add_row(body, "Imprint", ttk.Entry(body, textvariable=self.imprint_var, width=40), 1)
        self._add_row(body, "ISBN Print", ttk.Entry(body, textvariable=self.isbn_print_var, width=24), 2)
        self._add_row(body, "ISBN eBook", ttk.Entry(body, textvariable=self.isbn_ebook_var, width=24), 3)
        self._add_row(
            body,
            "Auflage",
            self._readonly_combo(body, self.edition_var, edition_values, width=8),
            4,
        )
        self._add_row(body, "Rechteinhaber", ttk.Entry(body, textvariable=self.rights_holder_var, width=40), 5)
        rights_combo = self._readonly_combo(body, self.rights_license_var, self.RIGHTS_LICENSE_OPTIONS, width=20)
        self._add_row(
            body,
            "Rechte/Lizenz",
            rights_combo,
            6,
        )
        frontmatter_combo = self._readonly_combo(body, self.frontmatter_profile_var, self.FRONTMATTER_PROFILE_OPTIONS, width=20)
        self._add_row(
            body,
            "Frontmatter-Profil",
            frontmatter_combo,
            7,
        )

        rights_combo.bind("<<ComboboxSelected>>", self._on_profile_related_change)
        frontmatter_combo.bind("<<ComboboxSelected>>", self._on_profile_related_change)

        tk.Label(
            body,
            text=(
                "Profil-Mapping: none=ohne Frontmatter, minimal=Basisdaten, standard=Standardbuch, "
                "extended=erweiterte Metadaten, publisher-print=Druckfokus, publisher-ebook=eBook-Fokus"
            ),
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
            justify="left",
            wraplength=640,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

        tk.Label(
            body,
            text=(
                "Lizenz-Mapping: all-rights-reserved=alle Rechte vorbehalten, cc-*=Creative-Commons-Varianten, "
                "public-domain=gemeinfrei"
            ),
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
            justify="left",
            wraplength=640,
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(2, 0))

        tk.Label(
            body,
            textvariable=self.profile_hint_var,
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8, "italic"),
            justify="left",
            wraplength=640,
        ).grid(row=10, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Button(
            body,
            text="Empfohlene Defaults anwenden",
            style="Tool.TButton",
            command=self._apply_profile_defaults,
        ).grid(row=11, column=1, sticky="w", pady=(8, 0))

        ttk.Button(
            body,
            text="Auf Dateistand zurücksetzen",
            style="Tool.TButton",
            command=self._reset_to_loaded_defaults,
        ).grid(row=11, column=2, sticky="w", padx=(8, 0), pady=(8, 0))

        self._update_profile_recommendation_hint()

    def _build_typst_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Format: typst", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        self.typst_keep_typ_var = tk.BooleanVar(value=bool(self._get_nested("format", "typst", "keep-typ", default=True)))
        self.typst_toc_var = tk.BooleanVar(value=bool(self._get_nested("format", "typst", "toc", default=True)))
        self.typst_toc_depth_var = tk.StringVar(value=str(self._get_nested("format", "typst", "toc-depth", default=3)))
        self.typst_number_sections_var = tk.BooleanVar(value=bool(self._get_nested("format", "typst", "number-sections", default=True)))
        section_numbering = str(self._get_nested("format", "typst", "section-numbering", default="1.1.1"))
        if section_numbering not in self.SECTION_NUMBERING_OPTIONS:
            section_numbering = "1.1.1"
        self.typst_section_numbering_var = tk.StringVar(value=section_numbering)

        papersize = str(self._get_nested("format", "typst", "papersize", default="a4"))
        if papersize not in self.PAPER_SIZE_OPTIONS:
            papersize = "a4"
        self.typst_papersize_var = tk.StringVar(value=papersize)

        widows_value = self._normalize_widow_orphan(self._get_nested("format", "typst", "widows", default="auto"))
        orphans_value = self._normalize_widow_orphan(self._get_nested("format", "typst", "orphans", default="auto"))
        self.typst_widows_var = tk.StringVar(value=widows_value)
        self.typst_orphans_var = tk.StringVar(value=orphans_value)

        if self.typst_toc_depth_var.get() not in self.TOC_DEPTH_OPTIONS:
            self.typst_toc_depth_var.set("3")

        ttk.Checkbutton(body, text="keep-typ", variable=self.typst_keep_typ_var).grid(row=0, column=0, sticky="w", padx=(0, 18), pady=4)
        ttk.Checkbutton(body, text="toc", variable=self.typst_toc_var).grid(row=0, column=1, sticky="w", padx=(0, 18), pady=4)
        ttk.Checkbutton(body, text="number-sections", variable=self.typst_number_sections_var).grid(row=0, column=2, sticky="w", pady=4)

        self._add_row(
            body,
            "toc-depth",
            self._readonly_combo(body, self.typst_toc_depth_var, self.TOC_DEPTH_OPTIONS, width=8),
            1,
        )
        self._add_row(
            body,
            "section-numbering",
            self._readonly_combo(body, self.typst_section_numbering_var, self.SECTION_NUMBERING_OPTIONS, width=10),
            2,
        )
        self._add_row(
            body,
            "papersize",
            self._readonly_combo(body, self.typst_papersize_var, self.PAPER_SIZE_OPTIONS, width=10),
            3,
        )
        self._add_row(
            body,
            "Schusterjungen (widows)",
            self._readonly_combo(body, self.typst_widows_var, self.WIDOW_ORPHAN_OPTIONS, width=10),
            4,
        )
        self._add_row(
            body,
            "Hurenkinder (orphans)",
            self._readonly_combo(body, self.typst_orphans_var, self.WIDOW_ORPHAN_OPTIONS, width=10),
            5,
        )

        tk.Label(
            body,
            text="Hinweis: widows/orphans wirken nur, wenn Template/Renderer diese Typst-Optionen auswertet.",
            bg=COLORS["app_bg"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8),
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _build_html_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Format: html", style="Section.TLabelframe")
        frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        body = tk.Frame(frame, bg=COLORS["app_bg"], padx=12, pady=10)
        body.pack(fill=tk.X)

        html_theme = str(self._get_nested("format", "html", "theme", default="cosmo"))
        if html_theme not in self.HTML_THEME_OPTIONS:
            html_theme = "cosmo"
        self.html_theme_var = tk.StringVar(value=html_theme)
        self.html_toc_var = tk.BooleanVar(value=bool(self._get_nested("format", "html", "toc", default=True)))

        self._add_row(
            body,
            "theme",
            self._readonly_combo(body, self.html_theme_var, self.HTML_THEME_OPTIONS, width=16),
            0,
        )
        ttk.Checkbutton(body, text="toc", variable=self.html_toc_var).grid(row=0, column=2, sticky="w", padx=(12, 0), pady=4)

    def _readonly_combo(self, parent, variable, values, width):
        combo = ttk.Combobox(parent, textvariable=variable, values=list(values), state="readonly", width=width)
        return combo

    def _add_row(self, parent, label_text, widget, row):
        tk.Label(
            parent,
            text=label_text,
            bg=COLORS["app_bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        widget.grid(row=row, column=1, sticky="w", pady=4)

    def _get_nested(self, *keys, default=None):
        cur = self.config_data
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                return default
            cur = cur[key]
        return cur

    def _get_root_or_book(self, key, default=None):
        if isinstance(self.config_data, dict) and key in self.config_data:
            return self.config_data[key]
        return self._get_nested("book", key, default=default)

    def _set_nested(self, target, keys, value):
        cur = target
        for key in keys[:-1]:
            nxt = cur.get(key)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[key] = nxt
            cur = nxt
        cur[keys[-1]] = value

    def _remove_nested(self, target, keys):
        cur = target
        parents = []
        for key in keys[:-1]:
            if not isinstance(cur, dict) or key not in cur:
                return
            parents.append((cur, key))
            cur = cur[key]

        if isinstance(cur, dict) and keys[-1] in cur:
            del cur[keys[-1]]

        for parent, key in reversed(parents):
            node = parent.get(key)
            if isinstance(node, dict) and not node:
                del parent[key]
            else:
                break

    def _normalize_author(self, author_value):
        if isinstance(author_value, list):
            return ", ".join(str(item) for item in author_value if str(item).strip())
        return str(author_value or "")

    def _normalize_keywords(self, keywords_value):
        if isinstance(keywords_value, list):
            return ", ".join(str(item) for item in keywords_value if str(item).strip())
        return str(keywords_value or "")

    def _parse_csv_list(self, raw_text):
        return [part.strip() for part in str(raw_text or "").split(",") if part.strip()]

    def _normalize_widow_orphan(self, raw_value):
        value = str(raw_value).strip().lower()
        if value in self.WIDOW_ORPHAN_OPTIONS:
            return value
        if value.isdigit() and value in self.WIDOW_ORPHAN_OPTIONS:
            return value
        return "auto"

    def _on_profile_related_change(self, _event=None):
        self._update_profile_recommendation_hint()

    def _collect_form_values(self):
        return {
            "project_type": self.project_type_var.get(),
            "output_dir": self.output_dir_var.get(),
            "book_title": self.book_title_var.get(),
            "book_subtitle": self.book_subtitle_var.get(),
            "author": self.author_var.get(),
            "lang": self.lang_var.get(),
            "book_description": self.book_description_var.get(),
            "book_keywords": self.book_keywords_var.get(),
            "publisher": self.publisher_var.get(),
            "imprint": self.imprint_var.get(),
            "isbn_print": self.isbn_print_var.get(),
            "isbn_ebook": self.isbn_ebook_var.get(),
            "edition": self.edition_var.get(),
            "rights_holder": self.rights_holder_var.get(),
            "rights_license": self.rights_license_var.get(),
            "frontmatter_profile": self.frontmatter_profile_var.get(),
            "typst_keep_typ": bool(self.typst_keep_typ_var.get()),
            "typst_toc": bool(self.typst_toc_var.get()),
            "typst_toc_depth": self.typst_toc_depth_var.get(),
            "typst_number_sections": bool(self.typst_number_sections_var.get()),
            "typst_section_numbering": self.typst_section_numbering_var.get(),
            "typst_papersize": self.typst_papersize_var.get(),
            "typst_widows": self.typst_widows_var.get(),
            "typst_orphans": self.typst_orphans_var.get(),
            "html_theme": self.html_theme_var.get(),
            "html_toc": bool(self.html_toc_var.get()),
        }

    def _capture_initial_form_values(self):
        self._initial_form_values = self._collect_form_values()
        self._dirty_controller.capture_initial(self._initial_form_values)

    def _start_dirty_watch(self):
        self._dirty_controller.start_polling(self._collect_form_values, interval_ms=350)

    def _refresh_dirty_state(self):
        if not self._initial_form_values:
            return
        current_values = self._collect_form_values()
        self._dirty_controller.refresh(current_values)

    def _apply_form_values(self, values):
        self.project_type_var.set(values.get("project_type", "book"))
        self.output_dir_var.set(values.get("output_dir", "export/_book"))
        self.book_title_var.set(values.get("book_title", ""))
        self.book_subtitle_var.set(values.get("book_subtitle", ""))
        self.author_var.set(values.get("author", ""))
        self.lang_var.set(values.get("lang", "de"))
        self.book_description_var.set(values.get("book_description", ""))
        self.book_keywords_var.set(values.get("book_keywords", ""))
        self.publisher_var.set(values.get("publisher", ""))
        self.imprint_var.set(values.get("imprint", ""))
        self.isbn_print_var.set(values.get("isbn_print", ""))
        self.isbn_ebook_var.set(values.get("isbn_ebook", ""))
        self.edition_var.set(values.get("edition", "1"))
        self.rights_holder_var.set(values.get("rights_holder", ""))
        self.rights_license_var.set(values.get("rights_license", "all-rights-reserved"))
        self.frontmatter_profile_var.set(values.get("frontmatter_profile", "standard"))
        self.typst_keep_typ_var.set(bool(values.get("typst_keep_typ", True)))
        self.typst_toc_var.set(bool(values.get("typst_toc", True)))
        self.typst_toc_depth_var.set(values.get("typst_toc_depth", "3"))
        self.typst_number_sections_var.set(bool(values.get("typst_number_sections", True)))
        self.typst_section_numbering_var.set(values.get("typst_section_numbering", "1.1.1"))
        self.typst_papersize_var.set(values.get("typst_papersize", "a4"))
        self.typst_widows_var.set(values.get("typst_widows", "auto"))
        self.typst_orphans_var.set(values.get("typst_orphans", "auto"))
        self.html_theme_var.set(values.get("html_theme", "cosmo"))
        self.html_toc_var.set(bool(values.get("html_toc", True)))
        self._update_profile_recommendation_hint()
        self._refresh_dirty_state()

    def _reset_to_loaded_defaults(self):
        if not self._initial_form_values:
            return

        current_values = self._collect_form_values()
        has_unsaved_changes = current_values != self._initial_form_values
        if has_unsaved_changes:
            proceed = confirm_discard_changes(
                self,
                "Änderungen verwerfen?",
                "Es gibt ungespeicherte Änderungen.\n\n"
                "Soll wirklich auf den geladenen Dateistand zurückgesetzt werden?",
            )
            if not proceed:
                return

        self._apply_form_values(self._initial_form_values)
        messagebox.showinfo(
            "Zurückgesetzt",
            "Alle Felder wurden auf den beim Öffnen geladenen Dateistand zurückgesetzt (noch nicht gespeichert).",
            parent=self,
        )

    def _update_profile_recommendation_hint(self):
        profile = (self.frontmatter_profile_var.get() if self.frontmatter_profile_var else "standard") or "standard"
        license_value = (self.rights_license_var.get() if self.rights_license_var else "all-rights-reserved") or "all-rights-reserved"

        profile_hints = {
            "none": "ohne Frontmatter; setze mind. Rechteinhaber/Lizenz explizit",
            "minimal": "reduziert; empfehlenswert für kurze Non-Fiction oder interne Dokumente",
            "standard": "ausgewogen; guter Default für die meisten Buchprojekte",
            "extended": "umfangreich; geeignet für größere Metadaten-/Reihenprojekte",
            "publisher-print": "Druckfokus; Empfehlung: typst papersize a5/a4, toc-depth 2-3, widows/orphans >= 2",
            "publisher-ebook": "eBook-Fokus; Empfehlung: html toc aktiv, schlanke Frontmatter, klare Kapitelstruktur",
        }
        license_hints = {
            "all-rights-reserved": "klassischer Verlagsstandard",
            "cc-by-4.0": "Nutzung mit Namensnennung erlaubt",
            "cc-by-sa-4.0": "wie CC-BY, aber Weitergabe unter gleichen Bedingungen",
            "cc-by-nd-4.0": "Weitergabe erlaubt, keine Bearbeitungen",
            "cc-by-nc-4.0": "nicht-kommerzielle Nutzung mit Namensnennung",
            "cc-by-nc-sa-4.0": "nicht-kommerziell + ShareAlike",
            "cc-by-nc-nd-4.0": "nicht-kommerziell, keine Bearbeitungen",
            "public-domain": "weitgehend frei nutzbar ohne klassische Rechtebindung",
        }

        profile_hint = profile_hints.get(profile, "projektspezifisch")
        license_hint = license_hints.get(license_value, "lizenzabhängig")
        self.profile_hint_var.set(
            f"Kontext-Hinweis: Profil '{profile}' = {profile_hint}. Lizenz '{license_value}' = {license_hint}. "
            "(Empfehlungstext; setzt keine Werte automatisch.)"
        )

    def _apply_profile_defaults(self):
        profile = (self.frontmatter_profile_var.get() if self.frontmatter_profile_var else "standard") or "standard"

        defaults_by_profile = {
            "none": {
                "typst_toc": True,
                "typst_toc_depth": "2",
                "typst_number_sections": True,
                "typst_papersize": "a4",
                "typst_widows": "auto",
                "typst_orphans": "auto",
                "html_toc": True,
            },
            "minimal": {
                "typst_toc": True,
                "typst_toc_depth": "2",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "auto",
                "typst_orphans": "auto",
                "html_toc": True,
            },
            "standard": {
                "typst_toc": True,
                "typst_toc_depth": "3",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "2",
                "typst_orphans": "2",
                "html_toc": True,
            },
            "extended": {
                "typst_toc": True,
                "typst_toc_depth": "4",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "2",
                "typst_orphans": "2",
                "html_toc": True,
            },
            "publisher-print": {
                "typst_toc": True,
                "typst_toc_depth": "3",
                "typst_number_sections": True,
                "typst_papersize": "a5",
                "typst_widows": "2",
                "typst_orphans": "2",
                "html_toc": False,
            },
            "publisher-ebook": {
                "typst_toc": True,
                "typst_toc_depth": "2",
                "typst_number_sections": True,
                "typst_papersize": "a4",
                "typst_widows": "auto",
                "typst_orphans": "auto",
                "html_toc": True,
            },
        }

        chosen = defaults_by_profile.get(profile, defaults_by_profile["standard"])

        self.typst_toc_var.set(bool(chosen["typst_toc"]))
        self.typst_toc_depth_var.set(chosen["typst_toc_depth"])
        self.typst_number_sections_var.set(bool(chosen["typst_number_sections"]))
        self.typst_papersize_var.set(chosen["typst_papersize"])
        self.typst_widows_var.set(chosen["typst_widows"])
        self.typst_orphans_var.set(chosen["typst_orphans"])
        self.html_toc_var.set(bool(chosen["html_toc"]))

        self._update_profile_recommendation_hint()
        self._refresh_dirty_state()
        messagebox.showinfo(
            "Defaults angewendet",
            (
                "Folgende Empfehlungen wurden gesetzt (noch nicht gespeichert):\n"
                f"- typst.toc: {chosen['typst_toc']}\n"
                f"- typst.toc-depth: {chosen['typst_toc_depth']}\n"
                f"- typst.number-sections: {chosen['typst_number_sections']}\n"
                f"- typst.papersize: {chosen['typst_papersize']}\n"
                f"- typst.widows: {chosen['typst_widows']}\n"
                f"- typst.orphans: {chosen['typst_orphans']}\n"
                f"- html.toc: {chosen['html_toc']}"
            ),
            parent=self,
        )

    def _save(self):
        title = self.book_title_var.get().strip()
        subtitle = self.book_subtitle_var.get().strip()
        author = self.author_var.get().strip()
        lang = self.lang_var.get().strip() or "de"
        description = self.book_description_var.get().strip()
        keywords = self._parse_csv_list(self.book_keywords_var.get())

        publisher = self.publisher_var.get().strip()
        imprint = self.imprint_var.get().strip()
        isbn_print = self.isbn_print_var.get().strip()
        isbn_ebook = self.isbn_ebook_var.get().strip()
        edition = self.edition_var.get().strip() or "1"
        rights_holder = self.rights_holder_var.get().strip()
        rights_license = self.rights_license_var.get().strip() or "all-rights-reserved"
        frontmatter_profile = self.frontmatter_profile_var.get().strip() or "standard"

        project_type = self.project_type_var.get().strip() or "book"
        output_dir = self.output_dir_var.get().strip() or "export/_book"
        theme = self.html_theme_var.get().strip() or "cosmo"
        section_numbering = self.typst_section_numbering_var.get().strip() or "1.1.1"
        papersize = self.typst_papersize_var.get().strip() or "a4"
        widows = self.typst_widows_var.get().strip().lower() or "auto"
        orphans = self.typst_orphans_var.get().strip().lower() or "auto"

        if project_type not in self.PROJECT_TYPES:
            messagebox.showerror("Ungültiger Wert", "Projekt-Typ ist ungültig.", parent=self)
            return
        if lang not in self.LANG_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "Sprache ist ungültig.", parent=self)
            return
        if self.typst_toc_depth_var.get() not in self.TOC_DEPTH_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "toc-depth ist ungültig.", parent=self)
            return
        toc_depth = int(self.typst_toc_depth_var.get())
        if section_numbering not in self.SECTION_NUMBERING_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "section-numbering ist ungültig.", parent=self)
            return
        if papersize not in self.PAPER_SIZE_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "papersize ist ungültig.", parent=self)
            return
        if theme not in self.HTML_THEME_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "HTML-Theme ist ungültig.", parent=self)
            return
        if widows not in self.WIDOW_ORPHAN_OPTIONS or orphans not in self.WIDOW_ORPHAN_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "widows/orphans ist ungültig.", parent=self)
            return
        if rights_license not in self.RIGHTS_LICENSE_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "Rechte/Lizenz ist ungültig.", parent=self)
            return
        if frontmatter_profile not in self.FRONTMATTER_PROFILE_OPTIONS:
            messagebox.showerror("Ungültiger Wert", "Frontmatter-Profil ist ungültig.", parent=self)
            return

        updated = copy.deepcopy(self.config_data)

        self._set_nested(updated, ("project", "type"), project_type)
        self._set_nested(updated, ("project", "output-dir"), output_dir)
        self._set_nested(updated, ("book", "title"), title)
        self._set_nested(updated, ("subtitle",), subtitle)
        self._set_nested(updated, ("description",), description)
        self._set_nested(updated, ("keywords",), keywords)
        self._set_nested(updated, ("author",), author)
        self._set_nested(updated, ("lang",), lang)

        self._set_nested(updated, ("publisher",), publisher)
        self._set_nested(updated, ("imprint",), imprint)
        self._set_nested(updated, ("isbn-print",), isbn_print)
        self._set_nested(updated, ("isbn-ebook",), isbn_ebook)
        self._set_nested(updated, ("edition",), edition)
        self._set_nested(updated, ("rights-holder",), rights_holder)
        self._set_nested(updated, ("rights-license",), rights_license)
        self._set_nested(updated, ("frontmatter-profile",), frontmatter_profile)

        for legacy_key in (
            "subtitle",
            "description",
            "keywords",
            "publisher",
            "imprint",
            "isbn-print",
            "isbn-ebook",
            "edition",
            "rights-holder",
            "rights-license",
            "frontmatter-profile",
        ):
            self._remove_nested(updated, ("book", legacy_key))

        self._set_nested(updated, ("format", "typst", "keep-typ"), bool(self.typst_keep_typ_var.get()))
        self._set_nested(updated, ("format", "typst", "toc"), bool(self.typst_toc_var.get()))
        self._set_nested(updated, ("format", "typst", "toc-depth"), toc_depth)
        self._set_nested(updated, ("format", "typst", "number-sections"), bool(self.typst_number_sections_var.get()))
        self._set_nested(updated, ("format", "typst", "section-numbering"), section_numbering)
        self._set_nested(updated, ("format", "typst", "papersize"), papersize)
        if widows == "auto":
            self._remove_nested(updated, ("format", "typst", "widows"))
        else:
            self._set_nested(updated, ("format", "typst", "widows"), int(widows))
        if orphans == "auto":
            self._remove_nested(updated, ("format", "typst", "orphans"))
        else:
            self._set_nested(updated, ("format", "typst", "orphans"), int(orphans))

        self._set_nested(updated, ("format", "html", "theme"), theme)
        self._set_nested(updated, ("format", "html", "toc"), bool(self.html_toc_var.get()))

        try:
            with self.yaml_path.open("w", encoding="utf-8") as handle:
                yaml.dump(updated, handle, sort_keys=False, allow_unicode=True, indent=2)
        except OSError as exc:
            messagebox.showerror("Fehler", f"Konnte _quarto.yml nicht speichern:\n{exc}", parent=self)
            return

        if callable(self.on_save):
            self.on_save(updated)

        self._dirty_controller.stop_polling()

        self.destroy()
