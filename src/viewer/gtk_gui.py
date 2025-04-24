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
        save_crop_callback: Callable[[Tuple[int, int, int, int], str], None] = None,
        highlight_mode_callback: Callable[[bool], None] = None,
        highlight_tile_callback: Callable[[Tuple[int, int], Optional[bool]], None] = None,
        get_highlight_tile_callback: Callable[[], np.ndarray] = None,
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
        self.crop_callback = save_crop_callback
        self.get_highlight_tile_callback = get_highlight_tile_callback
        
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
        self._crop_pending = False
        
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
        
        # Crop button
        crop_button = Gtk.Button(label="Crop")
        crop_button.connect("clicked", self._on_crop_clicked)
        menu_bar.append(crop_button)
        
        # Highlight mode toggle button
        self.highlight_button = Gtk.ToggleButton(label="Highlight Mode")
        self.highlight_button.connect("toggled", self._on_highlight_toggled)
        menu_bar.append(self.highlight_button)
        
        # Save highlight coordinates button
        save_highlight_button = Gtk.Button(label="Save Highlight Coords")
        save_highlight_button.connect("clicked", self._on_save_highlight_clicked)
        menu_bar.append(save_highlight_button)
        
        # Statistics label
        self.stats_label = Gtk.Label(label="")
        self.stats_label.set_hexpand(True)
        self.stats_label.set_halign(Gtk.Align.END)
        self.stats_label.set_margin_end(10)
        menu_bar.append(self.stats_label)
        
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
                if self._crop_pending and self.crop_callback:
                    # Show file save dialog for crop
                    self._show_save_dialog((x1, y1, x2, y2))
                    self._crop_pending = False
                elif self.select_callback:
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
        """Display statistics in the menu bar label."""
        self.stats_label.set_text(s)
        self.stats_label.set_tooltip_text(s)  # Also set as tooltip for longer text

    def _on_crop_clicked(self, button):
        """Handle crop button click by enabling selection mode for cropping."""
        self._crop_pending = True
        # We don't need to change any UI state as the crop will happen on selection release
    
    def _show_save_dialog(self, selection):
        """Show a file save dialog and save the crop if a path is selected."""
        dialog = Gtk.FileChooserDialog(
            title="Save Crop",
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Save", Gtk.ResponseType.ACCEPT,
        )
        
        # Add filters for image files
        filter_png = Gtk.FileFilter()
        filter_png.set_name("PNG files")
        filter_png.add_pattern("*.png")
        dialog.add_filter(filter_png)
        
        filter_tiff = Gtk.FileFilter()
        filter_tiff.set_name("TIFF files")
        filter_tiff.add_pattern("*.tiff")
        dialog.add_filter(filter_tiff)
        
        filter_jpg = Gtk.FileFilter()
        filter_jpg.set_name("JPEG files")
        filter_jpg.add_pattern("*.jpg")
        dialog.add_filter(filter_jpg)
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        # Set default name
        dialog.set_current_name("crop.tiff")
        
        # Connect response handler with selection data
        dialog.connect("response", lambda d, r: self._on_save_dialog_response(d, r, selection))
        dialog.show()
    
    def _on_save_dialog_response(self, dialog, response, selection):
        """Handle the response from the save dialog."""
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            if self.crop_callback:
                self.crop_callback(selection, file_path)
        dialog.destroy()

    def _on_save_highlight_clicked(self, button):
        """Handle save highlight coordinates button click."""
        if not self.get_highlight_tile_callback:
            self._show_error_dialog("No highlight tile callback available")
            return
            
        try:
            # Try to get the highlighted coordinates
            highlight_coords = self.get_highlight_tile_callback()
            if highlight_coords is None or len(highlight_coords) == 0:
                self._show_error_dialog("No highlighted area available")
                return
                
            # Show save dialog
            self._show_save_coords_dialog(highlight_coords)
        except ValueError as e:
            self._show_error_dialog(f"Highlight data not ready: {str(e)}")
    
    def _show_save_coords_dialog(self, coords):
        """Show a file save dialog for the highlight coordinates."""
        dialog = Gtk.FileChooserDialog(
            title="Save Highlight Coordinates",
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL,
            "_Save", Gtk.ResponseType.ACCEPT,
        )
        
        # Add filters for text and CSV files
        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("Text files")
        filter_txt.add_pattern("*.txt")
        dialog.add_filter(filter_txt)
        
        filter_csv = Gtk.FileFilter()
        filter_csv.set_name("CSV files")
        filter_csv.add_pattern("*.csv")
        dialog.add_filter(filter_csv)
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        # Set default name
        dialog.set_current_name("highlight_coords.csv")
        
        # Connect response handler with coordinates data
        dialog.connect("response", lambda d, r: self._on_save_coords_response(d, r, coords))
        dialog.show()
    
    def _on_save_coords_response(self, dialog, response, coords):
        """Handle the response from the save coordinates dialog."""
        if response == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_file().get_path()
            try:
                # Save coordinates to the selected file
                with open(file_path, 'w') as f:
                    # If coords is a numpy array, convert to list for easier handling
                    if hasattr(coords, 'tolist'):
                        coords = coords.tolist()
                    
                    # Write coordinates based on their structure
                    if isinstance(coords, list):
                        if all(isinstance(item, (list, tuple)) for item in coords):
                            # List of coordinates
                            for coord in coords:
                                f.write(','.join(map(str, coord)) + '\n')
                        else:
                            # Single coordinate
                            f.write(','.join(map(str, coords)))
                    else:
                        # Just convert to string and save
                        f.write(str(coords))
                
                self._show_info_dialog(f"Coordinates saved to {file_path}")
            except Exception as e:
                self._show_error_dialog(f"Error saving coordinates: {str(e)}")
        
        dialog.destroy()
    
    def _show_error_dialog(self, message):
        """Show an error dialog with the given message."""
        dialog = Gtk.MessageDialog(
            transient_for=None,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()
    
    def _show_info_dialog(self, message):
        """Show an information dialog with the given message."""
        dialog = Gtk.MessageDialog(
            transient_for=None,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()
