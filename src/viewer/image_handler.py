from typing import Tuple, Optional
import pyvips

from .gui import SlideViewer
from ..utils import resize_image_edge, resize_image_box

class ImageHandler:
    def __init__(self) -> None:
        self.src_image: pyvips.Image = None
        self.current_view = (-1, -1, -1, -1) # left, top, right, bottom
        self.gui: SlideViewer = None

    def set_gui(self, gui: SlideViewer) -> None:
        self.gui = gui
        
    def open_image(self, path: str) -> None:
        # Init the class
        image: pyvips.Image = pyvips.Image.new_from_file(path)
        self.current_view = (0, 0, image.width, image.height, )
        self.src_image = image

        # Resize the image
        self.show_current_view()


    def show_current_view(self) -> None:
        if self.src_image is None:
            return
        w, h = self.gui.get_display_area_size()
        image = self.src_image.extract_area(
                self.current_view[0], self.current_view[1],
                self.current_view[2] - self.current_view[0],
                self.current_view[3] - self.current_view[1])
        self.current_image = resize_image_box(image, w, h)
        self.gui.show_image(self.current_image)

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


    def scale_image(self, center_disp: Tuple[int, int], factor: float) -> None:
        disp_to_src_scale = self.get_display_to_source_scale()
        disp_w, disp_h = self.gui.get_display_area_size()

        # If the display area's aspect ratio and source patch's aspect ratio 
        # are different, this means the source patch is not filling the display 
        # area, probably because the user has zoomed out. In this case, we 
        # need to pretent the display area is filled with the source patch.
        old_src_w = disp_w * disp_to_src_scale
        old_src_h = disp_h * disp_to_src_scale

        src_center_x = self.current_view[0] + center_disp[0] * disp_to_src_scale
        src_center_y = self.current_view[1] + center_disp[1] * disp_to_src_scale
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
        self.scale_image(select_center, 1 / disp_to_select_scale)

        # return self.src_image.extract_area(left, top, width, height)
