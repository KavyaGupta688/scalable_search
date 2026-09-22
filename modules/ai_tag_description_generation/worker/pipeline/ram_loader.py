"""Load the installed RAM++ Swin-L checkpoint without a duplicate tensor copy.

Retains RAM's position-table interpolation and legacy key conversion. Memory
mapping plus assignment uses the same checkpoint weights and inference dtype.
"""
from pathlib import Path
import torch


def load_checkpoint(model, path, image_size=384):
    from ram.models.utils import CONFIG_PATH, read_json, interpolate_relative_pos_embed
    config = read_json(str(Path(CONFIG_PATH) / 'configs' / 'swin' / f'config_swinL_{image_size}.json'))
    checkpoint = torch.load(str(path), map_location='cpu', weights_only=True, mmap=True)
    state = checkpoint['model']
    for key in list(state):
        if 'relative_position_bias_table' in key:
            state[key] = interpolate_relative_pos_embed(state[key], (2 * config['window_size'] - 1) ** 2, param_name=key)
        elif 'relative_position_index' in key or 'attn_mask' in key:
            del state[key]
        elif 'vision_multi' in key:
            state[key.replace('vision_multi', 'tagging_head')] = state.pop(key)
    return model.load_state_dict(state, strict=False, assign=True)
