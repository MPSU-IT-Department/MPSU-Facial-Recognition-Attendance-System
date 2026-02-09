import customtkinter as ctk
from tkinter import messagebox

from enroll_student import StudentRegistrationWindow
from ui_utils import bring_window_to_front



class InstructorConsoleView(ctk.CTkFrame):
	"""Placeholder view for the instructor console."""

	def __init__(self, master, instructor_name=None, instructor_id=None, server_url=None, api_key=None, on_close=None, on_logout=None, on_end_class=None, **kwargs):
		# Filter out callback-like arguments (starting with 'on_') that aren't standard CTkFrame parameters
		# These are custom callbacks and shouldn't be passed to the parent CTkFrame
		filtered_kwargs = {k: v for k, v in kwargs.items() if not k.startswith('on_')}
		
		# Set default fg_color if not provided
		if 'fg_color' not in filtered_kwargs:
			filtered_kwargs['fg_color'] = ("#f0f8f0", "#1e4a1e")
		
		super().__init__(master, **filtered_kwargs)
		self.on_close = on_close
		self.on_logout = on_logout
		self.on_end_class = on_end_class
		self.instructor_name = instructor_name or "Instructor"
		self.instructor_id = instructor_id
		self.server_url = server_url
		self.api_key = api_key
		self.registration_window = None

		self._build_layout()

	def _build_layout(self):
		header = ctk.CTkFrame(self, fg_color=("#228B22", "#2e8b57"))
		header.pack(fill="x")

		title = ctk.CTkLabel(
			header,
			text=f"Instructor Console",
			font=("Arial", 26, "bold"),
			text_color=("white", "#e6ffe6"),
		)
		title.pack(pady=20)

		content = ctk.CTkFrame(self, fg_color=("#e8f5e8", "#1e4a1e"))
		content.pack(fill="both", expand=True, padx=40, pady=40)

		greeting = ctk.CTkLabel(
			content,
			text=f"Welcome, {self.instructor_name}!",
			font=("Arial", 22, "bold"),
			text_color=("#006400", "#90EE90"),
		)
		greeting.pack(pady=(20, 10))

		placeholder = ctk.CTkLabel(
			content,
			text="",
			font=("Arial", 18),
			text_color=("#2d5a2d", "#c1f0c1"),
		)
		placeholder.pack(pady=(0, 40))

		button_row = ctk.CTkFrame(content, fg_color="transparent")
		button_row.pack(pady=10)

		register_btn = ctk.CTkButton(
			button_row,
			text="Register Students",
			font=("Arial", 18, "bold"),
			width=220,
			height=60,
			fg_color=("#007bff", "#0d6efd"),
			hover_color=("#0056b3", "#0a58ca"),
			command=self._open_registration_window,
		)
		register_btn.pack(side="left", padx=10)

		close_btn = ctk.CTkButton(
			button_row,
			text="Return to Class",
			font=("Arial", 18, "bold"),
			width=220,
			height=60,
			fg_color=("#006400", "#228B22"),
			hover_color=("#004d00", "#1e5a1e"),
			command=self._handle_close,
		)
		close_btn.pack(side="left", padx=10)

		end_class_btn = ctk.CTkButton(
			button_row,
			text="End Class",
			font=("Arial", 18, "bold"),
			width=220,
			height=60,
			fg_color=("#dc3545", "#c82333"),
			hover_color=("#a71d2a", "#7f151f"),
			command=self._handle_end_class,
		)
		end_class_btn.pack(side="left", padx=10)

	def _open_registration_window(self):
		if not self.instructor_id:
			messagebox.showerror("Register Students", "Instructor information is unavailable. Please re-authenticate and try again.")
			return

		if self.registration_window and self.registration_window.winfo_exists():
			self.registration_window.focus_force()
			bring_window_to_front(self.registration_window)
			return

		try:
			self.registration_window = StudentRegistrationWindow(
				self.winfo_toplevel(),
				instructor_id=self.instructor_id,
				server_url=self.server_url,
				api_key=self.api_key,
			)
			self.registration_window.lift()
			self.registration_window.focus_force()
			bring_window_to_front(self.registration_window)
			self.registration_window.bind(
				"<Destroy>",
				lambda event: self._on_registration_closed(event),
			)
		except Exception as exc:
			messagebox.showerror("Register Students", f"Unable to open registration window: {exc}")

	def _on_registration_closed(self, event):
		if event.widget == self.registration_window:
			self.registration_window = None

	def _handle_end_class(self):
		if self.on_end_class:
			self.on_end_class()

	def _handle_close(self):
		if self.on_close:
			try:
				self.on_close(True)
			except TypeError:
				self.on_close()
