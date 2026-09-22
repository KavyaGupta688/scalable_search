"""Map NudeNet object detections to the explicit-nudity review policy.

Faces, feet, bellies, armpits and covered body parts are detector labels,
not evidence of explicit nudity. Unknown/malformed output fails closed.
"""
import math

EXPLICIT_CLASSES = frozenset({
    'BUTTOCKS_EXPOSED', 'FEMALE_BREAST_EXPOSED',
    'FEMALE_GENITALIA_EXPOSED', 'MALE_GENITALIA_EXPOSED', 'ANUS_EXPOSED',
})
NON_EXPLICIT_CLASSES = frozenset({
    'FEMALE_GENITALIA_COVERED', 'FACE_FEMALE', 'FACE_MALE',
    'MALE_BREAST_EXPOSED', 'FEET_EXPOSED', 'BELLY_COVERED',
    'FEET_COVERED', 'ARMPITS_COVERED', 'ARMPITS_EXPOSED',
    'BELLY_EXPOSED', 'ANUS_COVERED', 'FEMALE_BREAST_COVERED',
    'BUTTOCKS_COVERED',
})


def explicit_nudity_score(detections):
    score = 0.0
    for detection in detections:
        label = detection['class']
        value = float(detection['score'])
        if label not in EXPLICIT_CLASSES | NON_EXPLICIT_CLASSES:
            raise ValueError(f'Unknown NudeNet class: {label}')
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Invalid NudeNet score')
        if label in EXPLICIT_CLASSES:
            score = max(score, value)
    return score
