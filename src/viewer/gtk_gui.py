import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import numpy as np
from typing import Tuple, Callable, Optional
import pyvips

class GTKSlideViewer(Gtk.Box):
    """GTK4 implementation of the slide viewer with the same interface as SlideViewer."""
    
    def __init__(
        self,
        parent,
        open_callback: Callable[[str], None] = None,
        zoom_in_callback: Callable[[Tuple[int, int], float], None] = None,
        zoom_out_callback: Callable[[Tuple[int, int], float], None] = None,
        select_callback: Callable[[Tuple[int, int, int, int]], None] = None,
        resize_callback: Callable[[], None] = None,
        drag_callback: Callable[[Tuple[int, int, int, int]], None] = None,
        highlight_mode_callback: Callable[[bool], None] = None,
        highlight_tile_callback: Callable[[Tuple[int, int], Optional[bool]], None] = None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        # Store callbacks
        self.open_callback = open_callback
        self.zoom_in_callback = zoom_in_callback
        self.zoom_out_callback = zoom_out_callback
        self.select_callback = select_callback
        self.resize_callback = resize_callback
        self.drag_callback = drag_callback
        self.highlight_mode_callback = highlight_mode_callback
        self.highlight_tile_callback = highlight_tile_callback
        
        # Create UI components
        self._create_menu_bar()
        self._create_display_area()
        
        # Selection and drag state
        self.selecting = False
        self.dragging = False
        self.selection_start = (0, 0)
        self.selection_end = (0, 0)
        self.drag_start = (0, 0)
        self.drag_current = (0, 0)
        
        # Image display state
        self.current_image = None
        self.pixbuf = None
        
        # Highlight mode state
        self.highlight_mode = False
        
        # Set up event controllers
        self._setup_event_controllers()
        
        # Connect resize signal
        self.display_area.connect("resize", self._on_resize)
    
    def _create_menu_bar(self):
        # Create menu bar
        menu_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        
        # File menu button
        file_button = Gtk.Button(label="Open")
        file_button.connect("clicked", self._on_open_clicked)
        menu_bar.append(file_button)
        
        # Zoom controls
        zoom_in_button = Gtk.Button(label="Zoom In")
        zoom_in_button.connect("clicked", self._on_zoom_in_clicked)
        menu_bar.append(zoom_in_button)
        
        zoom_out_button = Gtk.Button(label="Zoom Out")
        zoom_out_button.connect("clicked", self._on_zoom_out_clicked)
        menu_bar.append(zoom_out_button)
        
        # Highlight mode toggle button
        self.highlight_button = Gtk.ToggleButton(label="Highlight Mode")
        self.highlight_button.connect("toggled", self._on_highlight_toggled)
        menu_bar.append(self.highlight_button)
        
        self.append(menu_bar)
    
    def _create_display_area(self):
        # Create scrolled window for the display area
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        
        # Create drawing area for image display
        self.display_area = Gtk.DrawingArea()
        self.display_area.set_draw_func(self._draw_func)
        
        scrolled_window.set_child(self.display_area)
        self.append(scrolled_window)
    
    def _setup_event_controllers(self):
        # Mouse click and motion controller
        click_controller = Gtk.GestureClick.new()
        click_controller.set_button(0)  # Listen to all mouse buttons
        click_controller.connect("pressed", self._on_mouse_pressed)
        click_controller.connect("released", self._on_mouse_released)
        self.display_area.add_controller(click_controller)
        
        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("motion", self._on_mouse_motion)
        self.display_area.add_controller(motion_controller)
        
        # Scroll controller for zooming
        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll_controller.connect("scroll", self._on_scroll)
        self.display_area.add_controller(scroll_controller)
        self.current_mouse_position = (0, 0)
        
        # Key controller
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.display_area.add_controller(key_controller)
    
    def _draw_func(self, area, cr, width, height):
        if self.pixbuf:
            # Draw the image
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
            
            # Draw selection rectangle if selecting
            if self.selecting:
                cr.set_source_rgba(0.0, 0.0, 1.0, 0.3)  # Semi-transparent blue
                x1, y1 = self.selection_start
                x2, y2 = self.selection_end
                cr.rectangle(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
                cr.fill()
                
                # Draw border
                cr.set_source_rgba(0.0, 0.0, 1.0, 0.8)  # More opaque blue
                cr.set_line_width(1)
                cr.rectangle(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
                cr.stroke()
    
    def _on_open_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Open Image",
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Open", Gtk.ResponseType.ACCEPT,
        )
        
        # Add filters for image files
        filter_images = Gtk.FileFilter()
        filter_images.set_name("Image files")
        filter_images.add_mime_type("image/*")
        dialog.add_filter(filter_images)
        
        dialog.connect("response", self._on_file_dialog_response)
        dialog.show()
    
    def _on_file_dialog_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            if self.open_callback:
                self.open_callback(file_path)
        dialog.destroy()
    
    def _on_zoom_in_clicked(self, button):
        if self.zoom_in_callback:
            # Get center of display area
            width, height = self.get_display_area_size()
            center = (width // 2, height // 2)
            self.zoom_in_callback(center)
    
    def _on_zoom_out_clicked(self, button):
        if self.zoom_out_callback:
            # Get center of display area
            width, height = self.get_display_area_size()
            center = (width // 2, height // 2)
            self.zoom_out_callback(center)
    
    def _on_mouse_pressed(self, gesture, n_press, x, y):
        button = gesture.get_current_button()
        if button == 1:  # Left button
            if self.highlight_mode and self.highlight_tile_callback:
                # In highlight mode, clicking toggles tile highlight
                self.highlight_tile_callback((x, y), None)
            else:
                # Normal selection mode
                self.selecting = True
                self.selection_start = (x, y)
                self.selection_end = (x, y)
        elif button == 3:  # Right button
            self.dragging = True
            self.drag_start = (x, y)
            self.drag_current = (x, y)
    
    def _on_mouse_released(self, gesture, n_press, x, y):
        button = gesture.get_current_button()
        if button == 1 and self.selecting:  # Left button
            self.selecting = False
            self.selection_end = (x, y)
            
            # Check if selection is large enough
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
                if self.select_callback:
                    self.select_callback((x1, y1, x2, y2))
            
            # Trigger redraw
            self.display_area.queue_draw()
        
        elif button == 3 and self.dragging:  # Right button
            self.dragging = False
            if self.drag_callback:
                x1, y1 = self.drag_start
                x2, y2 = (x, y)
                self.drag_callback((x1, y1, x2, y2))
    
    def _on_mouse_motion(self, controller, x, y):
        self.current_mouse_position = (x, y)
        if self.selecting:
            self.selection_end = (x, y)
            self.display_area.queue_draw()
        elif self.dragging:
            self.drag_current = (x, y)
    
    def _on_scroll(self, controller, dx, dy):
        # In GTK 4, we need to get the position differently
        # Get the current position from the motion controller
        if dy < 0:  # Scroll up - zoom in
            if self.zoom_in_callback:
                self.zoom_in_callback(self.current_mouse_position)
        elif dy > 0:  # Scroll down - zoom out
            if self.zoom_out_callback:
                self.zoom_out_callback(self.current_mouse_position)
        
        return True
    
    def _on_key_pressed(self, controller, keyval, keycode, state):
        # Handle keyboard shortcuts if needed
        pass
    
    def _on_resize(self, widget, width, height):
        if self.resize_callback:
            self.resize_callback()
    
    def get_display_area_size(self) -> Tuple[int, int]:
        """Return the current size of the display area."""
        width = self.display_area.get_width()
        height = self.display_area.get_height()
        return width, height
    
    def show_image(self, image: pyvips.Image) -> None:
        """Display the given image in the viewer."""
        self.current_image = image
        
        # Convert pyvips image to GdkPixbuf
        # First convert to numpy array
        if image.bands == 3:
            # RGB image
            data = np.ndarray(
                buffer=image.write_to_memory(),
                dtype=np.uint8,
                shape=[image.height, image.width, 3]
            )
            # Convert to GdkPixbuf
            self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                GLib.Bytes.new(data.tobytes()),
                GdkPixbuf.Colorspace.RGB,
                False,  # has_alpha
                8,      # bits_per_sample
                image.width,
                image.height,
                image.width * 3  # rowstride
            )
        else:
            # With alpha channel
            data = np.ndarray(
                buffer=image.write_to_memory(),
                dtype=np.uint8,
                shape=[image.height, image.width, 4]
            )
            # Convert to GdkPixbuf
            self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                GLib.Bytes.new(data.tobytes()),
                GdkPixbuf.Colorspace.RGB,
                True,  # has_alpha
                8,      # bits_per_sample
                image.width,
                image.height,
                image.width * 4  # rowstride
            )
        
        # Trigger redraw
        self.display_area.queue_draw()
    
    def pack(self, **kwargs):
        """Compatibility method for Tkinter's pack."""
        # This method exists for compatibility with the Tkinter interface
        # In GTK, the widget is already added to its parent in __init__
        pass 

    def _on_highlight_toggled(self, button):
        """Handle highlight mode toggle button."""
        self.highlight_mode = button.get_active()
        if self.highlight_mode_callback:
            self.highlight_mode_callback(self.highlight_mode)


    def show_statistics(self, s: str):
        '''Dummy method to be implemented
        '''
        pass
