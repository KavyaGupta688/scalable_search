import sys
from types import SimpleNamespace
import torch
from modules.ai_tag_description_generation.worker.pipeline.ram_loader import load_checkpoint


def test_memory_mapped_ram_loader_preserves_weights_and_legacy_names(tmp_path, monkeypatch):
    class SmallModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.tagging_head = torch.nn.Linear(2, 1)
            self.relative_position_bias_table = torch.nn.Parameter(torch.zeros(9, 1))
    expected = torch.tensor([[0.125, -0.75]])
    table = torch.arange(9, dtype=torch.float32).reshape(9, 1)
    checkpoint = tmp_path / 'checkpoint.pth'
    torch.save({'model': {'vision_multi.weight': expected, 'vision_multi.bias': torch.tensor([0.5]),
                         'relative_position_bias_table': table, 'relative_position_index': torch.ones(1),
                         'attn_mask': torch.ones(1)}}, checkpoint)
    def interpolate(value, count, param_name):
        assert count == 9 and param_name == 'relative_position_bias_table'
        return value
    monkeypatch.setitem(sys.modules, 'ram.models.utils', SimpleNamespace(CONFIG_PATH='/unused',
                        read_json=lambda _: {'window_size':2}, interpolate_relative_pos_embed=interpolate))
    model = SmallModel()
    result = load_checkpoint(model, checkpoint)
    assert not result.missing_keys and not result.unexpected_keys
    assert torch.equal(model.tagging_head.weight, expected)
    assert torch.equal(model.relative_position_bias_table, table)
    assert model.tagging_head.weight.dtype == torch.float32
    assert torch.equal(model.tagging_head(torch.ones(1, 2)), torch.tensor([[-0.125]]))
