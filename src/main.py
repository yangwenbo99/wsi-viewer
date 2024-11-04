import tkinter as tk
from .viewer.gui import SlideViewer
from .viewer.image_handler import ImageHandler

def main():
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
        drag_callback=handler.drag
    )
    viewer.pack(fill=tk.BOTH, expand=True)
    handler.set_gui(viewer)
    
    # Start the application
    root.mainloop()

if __name__ == "__main__":
    main()
