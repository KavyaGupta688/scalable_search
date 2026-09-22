import pytest
from modules.ai_tag_description_generation.worker.pipeline.nsfw_policy import explicit_nudity_score, EXPLICIT_CLASSES, NON_EXPLICIT_CLASSES


def test_non_explicit_detections_do_not_block_search():
    assert explicit_nudity_score([{'class':c,'score':0.99} for c in NON_EXPLICIT_CLASSES]) == 0


@pytest.mark.parametrize('label',sorted(EXPLICIT_CLASSES))
def test_explicit_detections_still_require_review(label):
    assert explicit_nudity_score([{'class':'FACE_FEMALE','score':0.99},{'class':label,'score':0.85}]) == 0.85


@pytest.mark.parametrize('detection',[{'class':'NEW_CLASS','score':0.9},{'class':'FACE_MALE','score':float('nan')},{'class':'ANUS_EXPOSED','score':-1}])
def test_unrecognized_or_invalid_output_is_not_cleared(detection):
    with pytest.raises(ValueError): explicit_nudity_score([detection])
