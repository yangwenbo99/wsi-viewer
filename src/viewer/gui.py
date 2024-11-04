import tkinter as tk
from tkinter import ttk
from typing import Tuple, Callable
import pyvips
from PIL import Image, ImageTk

class SlideViewer(tk.Frame):
    def __init__(
        self,
        master: tk.Tk,
        open_callback: Callable[[str], None],
        zoom_in_callback: Callable[[Tuple[int, int], float], None],
        zoom_out_callback: Callable[[Tuple[int, int], float], None],
        select_callback: Callable[[Tuple[int, int, int, int]], None],
        drag_callback: Callable[[Tuple[int, int, int, int]], None],
        resize_callback: Callable[[], None]
    ) -> None:
        super().__init__(master)
        self.master = master
        self.callbacks = {
            'open': open_callback,
            'zoom_in': zoom_in_callback,
            'zoom_out': zoom_out_callback,
            'select': select_callback,
            'resize': resize_callback,
            'drag': drag_callback,
        }
        
        self._setup_ui()
        self.current_image = None
        self.select_mode = False
        self.start_x = None
        self.start_y = None
        self.resize_timer = None
        self.scroll_timer = None
        self.drag_timer = None

        self.wheel_delta = 0  # For zoom in/out using mouse wheel
        
    def _setup_ui(self) -> None:
        # Create toolbar
        self.toolbar = ttk.Frame(self, width=100)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        
        # Create buttons
        btn_open = ttk.Button(self.toolbar, text="Open", 
                            command=self._handle_open)
        btn_zoom_in = ttk.Button(self.toolbar, text="Zoom In", 
                               command=self._handle_zoom_in)
        btn_zoom_out = ttk.Button(self.toolbar, text="Zoom Out",
                                command=self._handle_zoom_out)
        self.btn_select = ttk.Button(self.toolbar, text="Select",
                              command=self._handle_select_mode)
        
        btn_open.pack(pady=5)
        btn_zoom_in.pack(pady=5)
        btn_zoom_out.pack(pady=5)
        self.btn_select.pack(pady=5)
        
        # Create image display area
        self.display_frame = ttk.Frame(self)
        self.display_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.display_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind('<Button-1>', self._on_mouse_down)
        self.canvas.bind('<B1-Motion>', self._on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        self.bind('<Configure>', self._handle_resize)

        # Bind mouse wheel events
        self.canvas.bind('<MouseWheel>', self._on_mouse_scroll)  # Windows
        self.canvas.bind('<Button-4>', self._on_mouse_scroll)    # Linux scroll up
        self.canvas.bind('<Button-5>', self._on_mouse_scroll)    # Linux scroll down

        
    def get_display_area_size(self) -> Tuple[int, int]:
        '''
        Get the size of the display area
        @returns: (width, height)
        '''
        return (self.canvas.winfo_width(), self.canvas.winfo_height())
        
    def show_image(self, image: pyvips.Image) -> None:
        ''' Convert VIPS image to PIL Image for display
        '''
        mem_img = image.write_to_memory()
        pil_img = Image.frombytes('RGB', (image.width, image.height), mem_img)
        photo = ImageTk.PhotoImage(pil_img)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.current_image = photo  # Keep reference to prevent garbage collection
        
    def _handle_open(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename()
        if path:
            self.callbacks['open'](path)
            
    def _handle_zoom_in(self) -> None:
        center = (self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2)
        self.callbacks['zoom_in'](center)
        
    def _handle_zoom_out(self) -> None:
        center = (self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2)
        self.callbacks['zoom_out'](center)
        
    def _handle_select_mode(self) -> None:
        self.select_mode = not self.select_mode
        self.btn_select.config(text="Exit Select" if self.select_mode else "Select")
        
    def _on_mouse_down(self, event) -> None:
        self.start_x = event.x
        self.start_y = event.y
        
    def _on_mouse_drag(self, event) -> None:
        if self.start_x is None:
            return
        if self.select_mode:
            self.canvas.delete("selection")
            self.canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline="red", tags="selection"
            )
        else:
            movement = (self.start_x, self.start_y, event.x, event.y)
            if self.scroll_timer is not None:
                self.after_cancel(self.scroll_timer)
            self.scroll_timer = self.after(
                10,  # debounce delay
                lambda: self._handle_drag(movement))

    def _handle_drag(self, movement: Tuple[int, int, int, int]) -> None:
        self.callbacks['drag'](movement)
        self.start_x, self.start_y = movement[-2:]
            
    def _on_mouse_up(self, event) -> None:
        if self.select_mode and self.start_x is not None:
            selection = (self.start_x, self.start_y, event.x, event.y)
            self.callbacks['select'](selection)
        self.start_x = None
        self.start_y = None

    def _handle_resize(self, event) -> None:
        """Debounced window resize handler"""
        if self.resize_timer is not None:
            self.after_cancel(self.resize_timer)
        
        self.resize_timer = self.after(
            250,  # 250ms debounce delay
            lambda: self.callbacks['resize']()
        )

    def _on_mouse_scroll(self, event) -> None:
        """Handle mouse scroll events with debouncing"""
        if self.scroll_timer is not None:
            self.after_cancel(self.scroll_timer)
            
        # Get scroll delta (normalized between platforms)
        if event.num == 4:
            delta = 120  # Linux scroll up
        elif event.num == 5:
            delta = -120  # Linux scroll down
        else:
            delta = event.delta  # Windows

        if delta < 0:
            self.wheel_delta -= 1
        else:
            self.wheel_delta += 1
        
        self.scroll_timer = self.after(
            250,  # debounce delay
            lambda: self._handle_scroll_zoom((event.x, event.y))
        )
        
    def _handle_scroll_zoom(self, pos: Tuple[int, int]) -> None:
        """Execute the zoom callback based on scroll direction"""
        if self.wheel_delta == 0:
            return
        ratio = 2 ** self.wheel_delta
        self.wheel_delta = 0
        self.callbacks['zoom_in'](pos, ratio)
