"""Sentence splitting decides what a grammar card, a sentence pair and an error-detection number cover,
so a cut in the middle of a sentence turns into a fragment card. One rule, same as frontend splitSentences."""
import pytest

from app.services.text_utils import split_sentences


def parts(text):
    return [text[a:b] for a, b in split_sentences(text)]


def test_plain_sentences():
    assert parts("I like cats. They are cute! Are you sure?") == ["I like cats.", "They are cute!", "Are you sure?"]


def test_a_question_quoted_inside_a_sentence_does_not_end_it():
    t = 'In order to answer the question "why is polarization increasing?" we should focus on the public first.'
    assert parts(t) == [t]


def test_a_quoted_sentence_followed_by_a_capital_still_ends():
    assert parts('He asked "Why?" Then he left.') == ['He asked "Why?"', "Then he left."]


@pytest.mark.parametrize("text", [
    "Many countries, e.g. Korea and Japan, have this problem.",
    "Some fields, i.e. physics, need math.",
    "Mr. Kim and Dr. Lee met in the U.S. last year.",
    "The rate rose to 3.5 percent this year.",
])
def test_abbreviations_and_decimals_do_not_end_a_sentence(text):
    assert parts(text) == [text]


def test_lowercase_after_a_period_continues_the_sentence():
    # a learner typo like "etc. and" must not create a fragment that starts in lowercase
    t = "We need food, water, etc. and we also need shelter."
    assert parts(t) == [t]


def test_newlines_end_a_sentence_even_without_punctuation():
    assert parts("Title line\nThe essay starts here.") == ["Title line", "The essay starts here."]


def test_last_sentence_without_punctuation_is_kept():
    assert parts("First one. Second one") == ["First one.", "Second one"]


def test_spans_point_into_the_original_text():
    t = "  One.  Two?  "
    assert [(a, b) for a, b in split_sentences(t)] == [(2, 6), (8, 12)]
