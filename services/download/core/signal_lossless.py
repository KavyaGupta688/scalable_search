"""Bounded lossless-format pixel watermarking using the PNG v1 carrier.

Palette input is expanded to truecolor; animation uses composited RGBA frames.
16-bit PNG samples remain 16-bit, including color and alpha.
This is not resilient to arbitrary resampling, cropping or recompression.
"""
import io
import struct
import numpy as np
from PIL import Image, ImageSequence
from core.signal_png import embed_pixels, extract_pixels


def _open(data):
    if len(data) > 64 * 1024**2:
        raise ValueError("Lossless signal input limit is 64 MiB")
    if data.startswith(b'\x89PNG') and data[24] == 16 and data[25] != 0:
        raise ValueError("16-bit color/alpha PNG requires a precision-preserving codec; only PNG16 grayscale is supported")
    image = Image.open(io.BytesIO(data))
    if image.format not in {"PNG", "BMP", "TIFF", "WEBP"}:
        raise ValueError("Expected PNG, BMP, TIFF or lossless WebP")
    if image.width * image.height * getattr(image, 'n_frames', 1) > 16_000_000:
        raise ValueError("Lossless image limit is 16 million pixels across all frames")
    if image.format == 'WEBP' and not _lossless_webp(data):
        raise ValueError("Signal WebP requires a lossless VP8L source")
    return image


def _lossless_webp(data):
    # Check actual RIFF chunks, including nested animation frame chunks.
    def chunks(raw, start=0):
        while start + 8 <= len(raw):
            tag, size = raw[start:start+4], struct.unpack('<I', raw[start+4:start+8])[0]
            body = raw[start+8:start+8+size]
            yield tag
            if tag == b'ANMF':
                yield from chunks(body, 16)
            start += 8 + size + size % 2
    tags = list(chunks(data, 12))
    return b'VP8L' in tags and b'VP8 ' not in tags


def _pixels(frame):
    if frame.mode in {'I', 'I;16', 'I;16B', 'I;16L'}:
        data = np.asarray(frame)
        if data.min() < 0 or data.max() > 65535:
            raise ValueError("Only unsigned 16-bit grayscale is supported")
        return data.astype(np.float64) / 257, 'L', True
    if frame.mode in {'P', '1'}:
        frame = frame.convert('RGBA' if 'transparency' in frame.info else 'RGB')
    if frame.mode not in {'L', 'LA', 'RGB', 'RGBA'}:
        raise ValueError("Unsupported lossless pixel mode: " + frame.mode)
    return np.asarray(frame).copy(), frame.mode, False


def embed_bytes(data, download_id, secret):
    if data.startswith(b'\x89PNG') and len(data) > 25 and data[24] == 16:
        return _embed_png16(data, download_id, secret)
    with _open(data) as source:
        fmt, info = source.format, dict(source.info)
        frames, durations = [], []
        for frame in ImageSequence.Iterator(source):
            durations.append(frame.info.get('duration', 100))
            pixels, mode, high = _pixels(frame)
            if high:
                # Same QIM carrier, float calculations avoid reducing sample depth.
                from core.signal_png import _blocks, STEP, DOMAIN
                from core.signal_payload import encode, positions, COPIES
                import pywt
                from scipy.fft import idctn
                low, detail, coeff = _blocks(pixels)
                rows, cols = coeff.shape[:2]
                bits = np.tile(encode(download_id, secret, DOMAIN), COPIES)
                for index, bit in zip(positions(rows*cols, len(bits), secret, DOMAIN), bits):
                    r,c = divmod(index, cols)
                    target = float(bit)*STEP/2
                    coeff[r,c,2,3] = STEP*np.round((coeff[r,c,2,3]-target)/STEP)+target
                low[:rows*8,:cols*8] = idctn(coeff, axes=(-2,-1), norm='ortho').transpose(0,2,1,3).reshape(rows*8,cols*8)
                marked = pywt.idwt2((low,detail),'haar',mode='symmetric')[:pixels.shape[0],:pixels.shape[1]]
                output = np.clip(np.round(marked*257),0,65535).astype(np.uint16)
            else:
                output = embed_pixels(pixels, mode, download_id, secret)
            frames.append(Image.fromarray(output))
        kwargs = {k: info[k] for k in ('icc_profile','exif','dpi') if k in info}
        if fmt == 'WEBP': kwargs.update(lossless=True, exact=True)
        if len(frames) > 1:
            kwargs.update(save_all=True, append_images=frames[1:])
            if fmt in {'PNG','WEBP'}: kwargs.update(duration=durations, loop=info.get('loop',0))
            if fmt == 'PNG': kwargs.update(disposal=0, blend=0)
        out = io.BytesIO()
        frames[0].save(out, format=fmt, **kwargs)
        result = out.getvalue()
    with _open(result) as check:
        if getattr(check, 'n_frames', 1) != len(frames):
            raise ValueError("Watermark changed the image frame count")
        for frame in ImageSequence.Iterator(check):
            pixels, mode, _ = _pixels(frame)
            if extract_pixels(pixels, mode, secret) != download_id.lower():
                raise ValueError("Watermark failed recovery after encoding; no output delivered")
    return result


def extract_bytes(data, secret):
    if data.startswith(b'\x89PNG') and len(data) > 25 and data[24] == 16:
        pixels, mode, _ = _read_png16(data)
        return extract_pixels(pixels / 257.0, mode, secret)
    with _open(data) as source:
        ids = set()
        for frame in ImageSequence.Iterator(source):
            pixels, mode, _ = _pixels(frame)
            value = extract_pixels(pixels, mode, secret)
            if value: ids.add(value)
        if len(ids) > 1:
            raise ValueError("Image frames contain conflicting authenticated watermarks")
        return next(iter(ids), None)


def _read_png16(data):
    import png
    if len(data) > 64*1024**2 or len(data) < 33:
        raise ValueError('PNG16 input limit is 64 MiB')
    width,height = struct.unpack('>II',data[16:24])
    if width*height > 16_000_000:
        raise ValueError('PNG16 limit is 16 million pixels')
    if any(tag == b'acTL' for tag,_ in _png_chunks(data)):
        raise ValueError('Animated PNG16 is not supported; use 8-bit animation or static PNG16')
    width,height,values,info = png.Reader(bytes=data).read_flat()
    planes=info['planes']
    pixels=np.asarray(values,dtype=np.uint16).reshape((height,width) if planes==1 else (height,width,planes))
    mode=('LA' if info['alpha'] else 'L') if info['greyscale'] else ('RGBA' if info['alpha'] else 'RGB')
    return pixels,mode,info


def _png_chunks(data):
    offset=8
    while offset+12 <= len(data):
        length=struct.unpack('>I',data[offset:offset+4])[0]
        end=offset+12+length
        if end > len(data): raise ValueError('Truncated PNG chunk')
        yield data[offset+4:offset+8], data[offset:end]
        offset=end


def _embed_png16(data, download_id, secret):
    import png
    import pywt
    from scipy.fft import idctn
    from core.signal_png import _blocks, _luminance, STEP, DOMAIN
    from core.signal_payload import encode, positions, COPIES
    pixels,mode,info=_read_png16(data)
    y=_luminance(pixels/257.0, mode)
    low,detail,coeff=_blocks(y)
    rows,cols=coeff.shape[:2]
    bits=np.tile(encode(download_id,secret,DOMAIN),COPIES)
    for index,bit in zip(positions(rows*cols,len(bits),secret,DOMAIN),bits):
        r,c=divmod(index,cols); target=float(bit)*STEP/2
        coeff[r,c,2,3]=STEP*np.round((coeff[r,c,2,3]-target)/STEP)+target
    low[:rows*8,:cols*8]=idctn(coeff,axes=(-2,-1),norm='ortho').transpose(0,2,1,3).reshape(rows*8,cols*8)
    delta=(pywt.idwt2((low,detail),'haar',mode='symmetric')[:y.shape[0],:y.shape[1]]-y)*257
    output=pixels.copy()
    if mode=='L': output=np.clip(np.round(pixels.astype(float)+delta),0,65535).astype(np.uint16)
    elif mode=='LA': output[:,:,0]=np.clip(np.round(pixels[:,:,0].astype(float)+delta),0,65535).astype(np.uint16)
    else: output[:,:,:3]=np.clip(np.round(pixels[:,:,:3].astype(float)+delta[:,:,None]),0,65535).astype(np.uint16)
    out=io.BytesIO()
    png.Writer(width=pixels.shape[1],height=pixels.shape[0],bitdepth=16,greyscale=info['greyscale'],alpha=info['alpha']).write(out,output.reshape(pixels.shape[0],-1))
    encoded=out.getvalue()
    # Retain original color management, text and physical resolution chunks.
    ancillary=b''.join(chunk for tag,chunk in _png_chunks(data) if tag in {b'iCCP',b'gAMA',b'cHRM',b'sRGB',b'pHYs',b'tEXt',b'zTXt',b'iTXt',b'eXIf'})
    result=encoded[:33]+ancillary+encoded[33:]
    if extract_bytes(result,secret) != download_id.lower():
        raise ValueError('PNG16 post-write recovery failed; no output delivered')
    return result
