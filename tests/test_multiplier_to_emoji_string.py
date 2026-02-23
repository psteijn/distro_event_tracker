
from main import multiplier_to_emoji_string
from config import EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE, EMOJI_FIFTY, EMOJI_TWENTY_FIVE


def test_multiplier_to_emoji_string_thresholds():
    assert multiplier_to_emoji_string(1.0) == EMOJI_HUNDRED
    assert multiplier_to_emoji_string(1.5) == EMOJI_HUNDRED

    assert multiplier_to_emoji_string(0.9) == EMOJI_SEVENTY_FIVE
    assert multiplier_to_emoji_string(0.75) == EMOJI_SEVENTY_FIVE

    assert multiplier_to_emoji_string(0.74) == EMOJI_FIFTY
    assert multiplier_to_emoji_string(0.5) == EMOJI_FIFTY

    assert multiplier_to_emoji_string(0.49) == EMOJI_TWENTY_FIVE
    assert multiplier_to_emoji_string(0.25) == EMOJI_TWENTY_FIVE
    assert multiplier_to_emoji_string(0.1) == EMOJI_TWENTY_FIVE
