from typing import Tuple, Optional, Union
import pyvips
import numpy as np

from .gui import SlideViewer
from ..utils import resize_image_edge, resize_image_box

class ImageHandler:
    def __init__(self) -> None:
        self.src_image: pyvips.Image = None
        self.current_view = (-1, -1, -1, -1) # left, top, right, bottom
        self.gui: SlideViewer = None

        self.highlight_mode = False
        # Should be a np array corresponding to each tile
        self.highlighted_area = None

    def set_gui(self, gui: SlideViewer) -> None:
        self.gui = gui
        
    def open_image(self, path: str) -> None:
        # Init the class
        image: pyvips.Image = pyvips.Image.new_from_file(path)
        self.current_view = (0, 0, image.width, image.height, )
        self.src_image = image

        # Resize the image
        self.show_current_view()

    def _init_highlighted_tiles(self) -> None:
        import tifffile
        with tifffile.TiffFile(self.src_image.filename) as tiff:
            page = tiff.pages[0]
            if not page.is_tiled:
                self.highlighted_area = np.zeros((1, 1), dtype=np.bool)
                return
            tile_width = page.tags['TileWidth'].value
            tile_length = page.tags['TileLength'].value
            image_width = page.imagewidth
            image_length = page.imagelength
            tiles_per_row = (image_width + tile_width - 1) // tile_width
            tiles_per_col = (image_length + tile_length - 1) // tile_length
            self.tile_width = tile_width
            self.tile_length = tile_length
            # The order is important for following code to check whether the 
            # tile array is initialized or not.
            self.highlighted_area = np.zeros((tiles_per_col, tiles_per_row), dtype=np.bool)


    def show_current_view(self) -> None:
        if self.src_image is None:
            return
        w, h = self.gui.get_display_area_size()
        image = self.src_image.extract_area(
                self.current_view[0], self.current_view[1],
                self.current_view[2] - self.current_view[0],
                self.current_view[3] - self.current_view[1])
        self.current_image = resize_image_box(image, w, h)

        if self.highlight_mode:
            if self.highlighted_area is None:
                self._init_highlighted_tiles()
            print("Drawing highlight overlay")
            print(self.highlighted_area)
            self.current_image = self._draw_highlight_overlay(self.current_image)

        self.gui.show_image(self.current_image)
        self.gui.show_statistics(
                f"Image: {self.src_image.width}x{self.src_image.height}\n"
                f"View: {self.current_view[0]} {self.current_view[1]} {self.current_view[2]} {self.current_view[3]}\n"
                f"View size: {self.current_view[2] - self.current_view[0]}x{self.current_view[3] - self.current_view[1]}\n"
                f"Display: {w}x{h}"
                )

    def set_highlight_mode(self, mode: Optional[bool] = None) -> None:
        '''
        Set whether highlight mode is enabled.  

        @param mode: True to enable highlight mode, False to disable it,
                     or 't' to toggle the mode.
        '''
        if mode in [True, False]:
            self.highlight_mode = mode
        elif mode is None:
            self.highlight_mode = not self.highlight_mode
        else:
            raise ValueError("Invalid mode. Use True, False, or 't' to toggle.")
        self.show_current_view()


    def set_highlight_tile(
            self, loc_disp: Tuple[int, int], 
            value: Optional[bool] = None) -> None:
        '''Set whether a tile is highlighted.  If value is None, toggle 
        the highlight.
        '''
        if self.highlighted_area is None:
            raise ValueError("Highlighted area is not initialized. Set highlight mode on first.")

        loc_src = self.disp_coord_to_src(loc_disp)
        tile_x = loc_src[0] // self.tile_width
        tile_y = loc_src[1] // self.tile_length
        if tile_x < 0 or tile_y < 0:
            return
        if tile_x >= self.highlighted_area.shape[1] or tile_y >= self.highlighted_area.shape[0]:
            return
        value = value if value is not None else not self.highlighted_area[tile_y, tile_x]
        self.highlighted_area[tile_y, tile_x] = value
        self.show_current_view()


    def _draw_highlight_overlay(self, display_image: pyvips.Image) -> pyvips.Image:
        '''Draw highlight overlay. 

        Currently, the boundaries of each tile are drawn in red and the
        highlighted tiles are filled with transparent green.
        '''
        scale_x = scale_y = self.get_display_to_source_scale()

        start_tile_x = int(self.current_view[0]) // self.tile_width
        start_tile_y = int(self.current_view[1]) // self.tile_length
        end_tile_x = int(self.current_view[2] + self.tile_width - 1) // self.tile_width
        end_tile_y = int(self.current_view[3] + self.tile_length - 1) // self.tile_length

        # Prepare display image with alpha channel
        if display_image.bands == 3:
            display_with_alpha = display_image.bandjoin(255)  # Add alpha channel
        else:
            display_with_alpha = display_image

        # Create overlay image with RGBA
        overlay = pyvips.Image.black(display_image.width, display_image.height, bands=4)
        if hasattr(display_image, 'interpretation'):
            overlay = overlay.copy(interpretation="srgb")
        
        # Draw tile boundaries in red
        print(start_tile_x, end_tile_x, start_tile_y, end_tile_y)
        for tx in range(start_tile_x, end_tile_x + 1):
            x_pos = (tx * self.tile_width - self.current_view[0]) / scale_x
            if 0 <= x_pos < display_image.width:
                line = pyvips.Image.black(1, display_image.height, bands=4)
                line = line.new_from_image([255, 0, 0, 128])  # Red with 50% opacity
                overlay = overlay.insert(line, int(x_pos), 0)
        
        for ty in range(start_tile_y, end_tile_y + 1):
            y_pos = (ty * self.tile_length - self.current_view[1]) / scale_y
            if 0 <= y_pos < display_image.height:
                line = pyvips.Image.black(display_image.width, 1, bands=4)
                line = line.new_from_image([255, 0, 0, 128])  # Red with 50% opacity
                overlay = overlay.insert(line, 0, int(y_pos))
        
        # Fill highlighted tiles with transparent green
        for ty in range(start_tile_y, end_tile_y):
            for tx in range(start_tile_x, end_tile_x):
                if tx < self.highlighted_area.shape[1] and ty < self.highlighted_area.shape[0] and self.highlighted_area[ty, tx]:
                    # Calculate tile position in display coordinates
                    x1 = max(0, int((tx * self.tile_width - self.current_view[0]) / scale_x))
                    y1 = max(0, int((ty * self.tile_length - self.current_view[1]) / scale_y))
                    x2 = min(display_image.width, int(((tx + 1) * self.tile_width - self.current_view[0]) / scale_x))
                    y2 = min(display_image.height, int(((ty + 1) * self.tile_length - self.current_view[1]) / scale_y))
                    
                    if x2 > x1 and y2 > y1:
                        # Create a green rectangle with 30% opacity
                        rect = pyvips.Image.black(x2 - x1, y2 - y1, bands=4)
                        rect = rect.new_from_image([0, 255, 0, 76])  # Green with 30% opacity
                        overlay = overlay.insert(rect, x1, y1)
        
        # Composite the overlay onto the display image
        result = display_with_alpha.composite(overlay, "over")
        
        return result


    def fix_boundaries(self) -> None:
        '''
        Fix the current view boundaries so that it is within the image.
        '''
        new_src_left, new_src_top, new_src_right, new_src_bottom = self.current_view
        # First, shift exccessive area on the right/bottom to left/top
        if new_src_right > self.src_image.width:
            new_src_left -= new_src_right - self.src_image.width
            new_src_right = self.src_image.width
        if new_src_bottom > self.src_image.height:
            new_src_top -= new_src_bottom - self.src_image.height
            new_src_bottom = self.src_image
        # Then, shift exccessive area on the left/top to right/bottom
        # After this, we guarentee the left and top are within the image and 
        # the aspect ratio is maintained.
        if new_src_left < 0:
            new_src_right -= new_src_left
            new_src_left = 0
        if new_src_top < 0:
            new_src_bottom -= new_src_top
            new_src_top = 0
        # Finally, if the area is unreasonably large, we shrink it to fit the image
        if new_src_right > self.src_image.width:
            new_src_right = self.src_image.width
        if new_src_bottom > self.src_image.height:
            new_src_bottom = self.src_image.height
        self.current_view = (new_src_left, new_src_top, new_src_right, new_src_bottom)

    def fill_display_area(self) -> None:
        '''Set the current view to fill the display area.'''
        disp_w = self.current_view[2] - self.current_view[0]
        disp_h = self.current_view[3] - self.current_view[1]
        area_w, area_h = self.gui.get_display_area_size()
        area_aspect = area_w / area_h
        disp_aspect = disp_w / disp_h
        if disp_aspect > area_aspect:
            # Image is wider than display area
            disp_h = int(disp_w / area_aspect)
        elif disp_aspect < area_aspect:
            # Image is taller than display area
            disp_w = int(disp_h * area_aspect)


    def redraw_image_resize(self) -> None:
        if self.src_image is None:
            return
        new_disp_w, new_disp_h = self.gui.get_display_area_size()
        old_disp_w, old_disp_h = self.current_image.width, self.current_image.height
        old_src_w, old_src_h = self.current_view[2] - self.current_view[0], self.current_view[3] - self.current_view[1]
        src_scale_center = (self.current_view[0] + self.current_view[2]) / 2, (self.current_view[1] + self.current_view[3]) / 2
        disp_to_src_scale = max(old_src_w / old_disp_w, old_src_h / old_disp_h)
        new_src_w, new_src_h = new_disp_w * disp_to_src_scale, new_disp_h * disp_to_src_scale
        new_src_left = int(src_scale_center[0] - new_src_w / 2)
        new_src_top = int(src_scale_center[1] - new_src_h / 2)
        new_src_right = int(src_scale_center[0] + new_src_w / 2)
        new_src_bottom = int(src_scale_center[1] + new_src_h / 2)

        self.current_view = (new_src_left, new_src_top, new_src_right, new_src_bottom)
        print(self.current_view)
        # Check boundaries
        self.fix_boundaries()
        print(self.current_view)
        self.show_current_view()

    def get_display_to_source_scale(self) -> float:
        disp_w, disp_h = self.gui.get_display_area_size()
        old_src_w, old_src_h = self.current_view[2] - self.current_view[0], self.current_view[3] - self.current_view[1]
        disp_to_src_scale = max(old_src_w / disp_w, old_src_h / disp_h)
        return disp_to_src_scale

    def disp_coord_to_src(self, disp: Tuple[int, int]) -> Tuple[int, int]:
        '''Convert display coordinates to source coordinates.'''
        disp_to_src_scale = self.get_display_to_source_scale()
        src_x = int(self.current_view[0] + disp[0] * disp_to_src_scale)
        src_y = int(self.current_view[1] + disp[1] * disp_to_src_scale)
        return (src_x, src_y)


    def scale_image(self, center_disp: Tuple[int, int], factor: float) -> None:
        disp_to_src_scale = self.get_display_to_source_scale()
        disp_w, disp_h = self.gui.get_display_area_size()

        # If the display area's aspect ratio and source patch's aspect ratio 
        # are different, this means the source patch is not filling the display 
        # area, probably because the user has zoomed out. In this case, we 
        # need to pretent the display area is filled with the source patch.
        old_src_w = disp_w * disp_to_src_scale
        old_src_h = disp_h * disp_to_src_scale

        src_center_x, src_center_y = self.disp_coord_to_src(center_disp)
        new_src_w = old_src_w / factor
        new_src_h = old_src_h / factor
        new_src_left = int(src_center_x - new_src_w / 2)
        new_src_top = int(src_center_y - new_src_h / 2)
        new_src_right = int(src_center_x + new_src_w / 2)
        new_src_bottom = int(src_center_y + new_src_h / 2)
        self.current_view = (new_src_left, new_src_top, new_src_right, new_src_bottom)
        self.fix_boundaries()
        self.show_current_view()

    def drag(self, movement: Tuple[int, int, int, int]) -> None:
        if self.src_image is None:
            return None
        disp_to_src_scale = self.get_display_to_source_scale()

        dx, dy = movement[2] - movement[0], movement[3] - movement[1]
        dx, dy = dx * disp_to_src_scale, dy * disp_to_src_scale
        dview = (-dx, -dy, -dx, -dy)
        self.current_view = (p + dp for p, dp in zip(self.current_view, dview))
        self.fix_boundaries()
        self.show_current_view()
        
    def zoom_in(self, center: Tuple[int, int], factor: float = 2) -> None:
        if self.src_image is None:
            return None

        self.scale_image(center, factor)
        
    def zoom_out(self, center: Tuple[int, int], factor: float = 2) -> None:
        self.scale_image(center, 1 / factor)
        
    def zoom_select(self, selection: Tuple[int, int, int, int]) -> None:
        if self.src_image is None:
            return None
        x1, y1, x2, y2 = selection
        select_width = abs(x2 - x1)
        select_height = abs(y2 - y1)
        select_center = ((x1 + x2) // 2, (y1 + y2) // 2)

        disp_w, disp_h = self.gui.get_display_area_size()
        # old_src_w, old_src_h = self.current_view[2] - self.current_view[0], self.current_view[3] - self.current_view[1]
        disp_to_select_scale = max(select_width / disp_w, select_height / disp_h)
        if disp_to_select_scale > 0:
            self.scale_image(select_center, 1 / disp_to_select_scale)

        # return self.src_image.extract_area(left, top, width, height)

    def save_crop(self, disp_selection: Tuple[int, int, int, int], 
                  save_path: str) -> None:
        disp_w, disp_h = self.gui.get_display_area_size()
        disp_selection_rel = (
                disp_selection[0] / disp_w, disp_selection[1] / disp_h, 
                disp_selection[2] / disp_w, disp_selection[3] / disp_h)
        src_left = self.current_view[0] + disp_selection_rel[0] * (self.current_view[2] - self.current_view[0])
        src_top = self.current_view[1] + disp_selection_rel[1] * (self.current_view[3] - self.current_view[1])
        src_width = (disp_selection_rel[2] - disp_selection_rel[0]) * (self.current_view[2] - self.current_view[0])
        src_height = (disp_selection_rel[3] - disp_selection_rel[1]) * (self.current_view[3] - self.current_view[1])
        cropped_image = self.src_image.extract_area(
                src_left, src_top, src_width, src_height)
        cropped_image.write_to_file(save_path)

