import argparse
import tkinter as tk
from .viewer.gui import SlideViewer
from .viewer.image_handler import ImageHandler

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Whole Slide Image Viewer")
    parser.add_argument("--frontend", "-f", choices=["tk", "gtk"], default="tk",
                        help="Choose the frontend: tk (Tkinter) or gtk (GTK4)")
    parser.add_argument("path", nargs="?", default=None,
                        help="Path to the whole slide image file to open (optional)")
    args = parser.parse_args()
    
    if args.frontend == "gtk":
        # Use GTK4 frontend
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        from .viewer.gtk_gui import GTKSlideViewer
        
        # Create application
        app = Gtk.Application(application_id="ca.uwaterloo.ivc.wsi-viewer")
        
        # Store the path to open later in the activate handler
        app.wsi_path = args.path
        
        app.connect("activate", on_activate)
        app.run(None)
    else:
        # Use Tkinter frontend (default)
        root = tk.Tk()
        root.title("Whole Slide Image Viewer")
        
        # Create image handler
        handler = ImageHandler()
        
        # Create viewer with callbacks
        viewer = SlideViewer(
            root,
            open_callback=handler.open_image, 
            zoom_in_callback=handler.zoom_in,
            zoom_out_callback=handler.zoom_out,
            select_callback=handler.zoom_select,
            resize_callback=handler.redraw_image_resize,
            drag_callback=handler.drag,
            save_crop_callback=handler.save_crop
        )
        viewer.pack(fill=tk.BOTH, expand=True)
        handler.set_gui(viewer)
        
        # Open the image if path is provided
        if args.path:
            handler.open_image(args.path)
        
        # Start the application
        root.mainloop()

def on_activate(app):
    # Create main window
    from gi.repository import Gtk
    win = Gtk.ApplicationWindow(application=app)
    win.set_title("Whole Slide Image Viewer")
    win.set_default_size(800, 600)
    
    # Create image handler
    handler = ImageHandler()
    
    # Create viewer with callbacks
    from .viewer.gtk_gui import GTKSlideViewer
    viewer = GTKSlideViewer(
        win,
        open_callback=handler.open_image, 
        zoom_in_callback=handler.zoom_in,
        zoom_out_callback=handler.zoom_out,
        select_callback=handler.zoom_select,
        resize_callback=handler.redraw_image_resize,
        drag_callback=handler.drag,
        highlight_mode_callback=handler.set_highlight_mode,
        highlight_tile_callback=handler.set_highlight_tile
    )
    
    # Set the viewer as the window's child
    win.set_child(viewer)
    handler.set_gui(viewer)
    
    # Open the image if path is provided
    if hasattr(app, 'wsi_path') and app.wsi_path:
        handler.open_image(app.wsi_path)
    
    # Show the window
    win.present()

if __name__ == "__main__":
    main()
