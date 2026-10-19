"""Read WebP dimensions before Pillow allocates its animation frame buffers."""


def webp_pixels(stream, size):
    try:
        header = stream.read(12)
        if header[:4] != b"RIFF" or header[8:] != b"WEBP":
            return None
        while stream.tell() + 8 <= size:
            chunk = stream.read(8)
            length = int.from_bytes(chunk[4:], "little")
            start = stream.tell()
            if start + length > size:
                raise ValueError("Invalid WebP chunk")
            data = stream.read(min(length, 10))
            if chunk[:4] == b"VP8X" and len(data) == 10:
                return (1 + int.from_bytes(data[4:7], "little")) * (
                    1 + int.from_bytes(data[7:10], "little")
                )
            if (
                chunk[:4] == b"VP8 "
                and len(data) == 10
                and data[3:6] == b"\x9d\x01\x2a"
            ):
                return (int.from_bytes(data[6:8], "little") & 0x3FFF) * (
                    int.from_bytes(data[8:10], "little") & 0x3FFF
                )
            if chunk[:4] == b"VP8L" and len(data) >= 5 and data[0] == 0x2F:
                bits = int.from_bytes(data[1:5], "little")
                return (1 + (bits & 0x3FFF)) * (1 + ((bits >> 14) & 0x3FFF))
            stream.seek(start + length + (length & 1))
        raise ValueError("Missing WebP dimensions")
    finally:
        stream.seek(0)
