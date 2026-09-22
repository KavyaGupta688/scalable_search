import io
import json
import uuid
import numpy as np
from PIL import Image
import pytest
from core import signal_lossless
from core.crypto import create_tracking_payload, generate_watermark_token
from core.integrated_watermark import watermark, methods_for
from core.injectors.extractor import extract_token_from_bytes

SECRET = 'test-only-lossless-key-' * 3
ID = str(uuid.uuid4())


@pytest.mark.parametrize('fmt,mode', [('PNG','P'),('PNG','I;16'),('BMP','RGB'),('TIFF','RGB'),('WEBP','RGBA')])
def test_lossless_variants(fmt, mode):
    rng = np.random.default_rng(91)
    if mode == 'I;16':
        pixels = rng.integers(4000, 61000, (512, 514), dtype=np.uint16)
    else:
        shape = (512,514) if mode == 'P' else (512,514,len(mode))
        pixels = rng.integers(25,230,shape,dtype=np.uint8)
    image = Image.fromarray(pixels)
    if mode == 'P': image = image.convert('P')
    raw = io.BytesIO(); image.save(raw, fmt, lossless=True)
    output = signal_lossless.embed_bytes(raw.getvalue(), ID, SECRET)
    assert signal_lossless.extract_bytes(output, SECRET) == ID
    assert signal_lossless.extract_bytes(output, SECRET+'bad') is None
    decoded = Image.open(io.BytesIO(output))
    assert decoded.format == fmt and decoded.size == image.size
    a = np.asarray(image.convert('RGB') if mode == 'P' else image).astype(float)
    b = np.asarray(decoded).astype(float)
    max_value = 65535 if mode == 'I;16' else 255
    assert 10*np.log10(max_value**2/np.mean((a-b)**2)) > 40
    if mode == 'RGBA': np.testing.assert_array_equal(a[:,:,-1],b[:,:,-1])
    if mode == 'I;16': assert b.max() > 255


def test_animation_keeps_frames_and_timing():
    frames = [Image.new('RGBA',(512,512),(90+i*30,110,140,180)) for i in range(2)]
    raw = io.BytesIO(); frames[0].save(raw,'PNG',save_all=True,append_images=frames[1:],duration=[120,180],loop=3)
    output = signal_lossless.embed_bytes(raw.getvalue(),ID,SECRET)
    assert signal_lossless.extract_bytes(output, SECRET) == ID
    image = Image.open(io.BytesIO(output))
    assert image.n_frames == 2 and image.info['loop'] == 3
    for i,duration in enumerate([120,180]):
        image.seek(i)
        assert image.info['duration'] == duration
        assert np.all(np.asarray(image)[:,:,-1] == 180)


def test_unsupported_training_data_remains_identical():
    for name,data in [('data.csv',b'a,b\n1,2\n'),('data.json',b'{"label":"dog"}'),('file.heic',b'unknown')]:
        assert methods_for(name) == ['sidecar-HMAC-SHA256']
        assert watermark(data,'test-token',name) == data


def test_pdf_metadata_keeps_pages_and_token():
    from pypdf import PdfWriter, PdfReader
    writer=PdfWriter(); writer.add_blank_page(width=100,height=100)
    raw=io.BytesIO(); writer.write(raw)
    token=generate_watermark_token(create_tracking_payload('u','u@example.test','doc'))
    output=watermark(raw.getvalue(),token,'file.pdf')
    assert len(PdfReader(io.BytesIO(output)).pages) == 1
    assert extract_token_from_bytes(output)[0] == token


@pytest.mark.parametrize('planes,greyscale,alpha',[(2,True,True),(3,False,False),(4,False,True)])
def test_png16_color_precision_and_alpha(planes,greyscale,alpha):
    import png
    rng=np.random.default_rng(103)
    pixels=rng.integers(4000,61000,(512,514,planes),dtype=np.uint16)
    buffer=io.BytesIO()
    png.Writer(width=514,height=512,greyscale=greyscale,alpha=alpha,bitdepth=16).write(buffer,pixels.reshape(512,-1))
    output=signal_lossless.embed_bytes(buffer.getvalue(),ID,SECRET)
    assert signal_lossless.extract_bytes(output,SECRET)==ID
    assert signal_lossless.extract_bytes(output,SECRET+'wrong') is None
    _,_,values,info=png.Reader(bytes=output).read_flat()
    recovered=np.asarray(values,dtype=np.uint16).reshape(pixels.shape)
    assert info['bitdepth']==16 and info['planes']==planes
    if alpha: np.testing.assert_array_equal(recovered[:,:,-1],pixels[:,:,-1])
    mse=np.mean((pixels.astype(float)-recovered)**2)
    assert 10*np.log10(65535**2/mse)>40
