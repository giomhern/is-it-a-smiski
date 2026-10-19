"""Shared image preprocessing without importing the training framework."""

import numpy as np
from PIL import Image, ImageOps

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]


def preprocess_image(image):
    ImageOps.exif_transpose(image, in_place=True)
    if image.mode == "RGB":
        image = image.resize((224, 224), Image.Resampling.BILINEAR)
    else:
        # Convert one band in tiles to avoid a second full-resolution RGB frame.
        bands = []
        for channel in range(3):
            with Image.new("L", image.size) as band:
                for top in range(0, image.height, 512):
                    for left in range(0, image.width, 512):
                        box = (
                            left,
                            top,
                            min(left + 512, image.width),
                            min(top + 512, image.height),
                        )
                        with image.crop(box) as tile, tile.convert("RGB") as rgb:
                            band.paste(rgb.getchannel(channel), box)
                bands.append(band.resize((224, 224), Image.Resampling.BILINEAR))
        image = Image.merge("RGB", bands)
    pixels = np.asarray(image, dtype=np.float32).transpose(2, 0, 1)
    pixels = (pixels / np.float32(255) - MEAN) / STD
    return np.ascontiguousarray(pixels)
