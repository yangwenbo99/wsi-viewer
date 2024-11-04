import pyvips

def resize_image_edge(image: pyvips.Image, target_length: int, resize_shorter: bool) -> pyvips.Image:
    """Resize the image so that its specified edge is of the target length,
    maintaining the aspect ratio.

    Args:
        image (pyvips.Image): The image to resize.
        target_length (int): The target length for the specified edge.
        resize_shorter (bool): True to resize the shorter edge, False for the longer edge.

    Returns:
        pyvips.Image: The resized image.
    """
    current_width, current_height = image.width, image.height
    if resize_shorter:
        scale_factor = (
            target_length / current_height
            if current_height < current_width
            else target_length / current_width
        )
    else:
        scale_factor = (
            target_length / current_height
            if current_height > current_width
            else target_length / current_width
        )

    resized_image = image.resize(scale_factor)
    return resized_image


def resize_image_box(image: pyvips.Image, target_width: int, target_height: int) -> pyvips.Image:
    """Resize the image to fit within the specified box, maintaining the aspect ratio.

    Args:
        image (pyvips.Image): The image to resize.
        target_width (int): The target width of the box.
        target_height (int): The target height of the box.

    Returns:
        pyvips.Image: The resized image.
    """
    scale_factor = min(target_width / image.width, target_height / image.height)
    resized_image = image.resize(scale_factor)
    return resized_image
