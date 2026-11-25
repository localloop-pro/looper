"""Regression tests for classify_post bugs (issue #210)."""
from services.facebook_pipeline import classify_post


def test_rating_is_never_outside_1_to_5():
    assert 1 <= classify_post("Recommend Bondi Cafe, 9 5 seats great")["estimated_rating"] <= 5
    assert 1 <= classify_post("Recommend Bondi Cafe, paid $45 stars")["estimated_rating"] <= 5


def test_found_does_not_block_a_review():
    assert classify_post("I found Bondi Cafe, highly recommend")["is_review"] is True


def test_iso_inside_a_word_is_not_a_stop_phrase():
    assert classify_post("Highly recommend Isotonic Bondi Cafe")["is_review"] is True


def test_business_name_does_not_start_with_lowercase_verb():
    names = [b["name"] for b in classify_post("Tried Bondi Plumbing Co, ok")["businesses"]]
    assert "Tried Bondi" not in names
