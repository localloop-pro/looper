"""Facebook review-import pipeline: post classifier + DB importer.

No network: run_pipeline's Graph API branch is exercised with a fake httpx.get.
Known classifier defects are tracked in issues, not asserted here.
"""
import httpx
import pytest

import models
from services import facebook_pipeline as fb


def test_stop_phrase_is_never_a_review():
    out = fb.classify_post("Selling my couch, highly recommend a look!")
    assert out["is_review"] is False
    assert out["confidence"] == 0.0
    assert out["businesses"] == []
    assert "selling" in out["reason"]


def test_recommendation_post_extracts_business_and_category():
    out = fb.classify_post("Bondi Vet saved our puppy. Can't recommend enough. 5 stars")
    assert out["is_review"] is True
    assert {"name": "Bondi", "category": "vet"} in out["businesses"]
    assert out["estimated_rating"] == 5


def test_post_without_signals_is_not_a_review():
    out = fb.classify_post("Bondi Cafe opens at seven")
    assert out["is_review"] is False
    assert out["confidence"] == 0.0


def test_confidence_is_capped_at_one():
    out = fb.classify_post(
        "recommended best amazing fantastic favourite highly recommend must try"
    )
    assert out["confidence"] == 1.0


def test_sentiment_needs_a_margin_of_two():
    # one positive word is not enough to flip neutral
    assert fb.classify_post("great Bondi Cafe, recommend")["sentiment"] == "neutral"
    pos = fb.classify_post("great and amazing and fantastic Bondi Cafe, recommend")
    assert pos["sentiment"] == "positive" and pos["estimated_rating"] == 5
    neg = fb.classify_post("terrible awful worst Bondi Cafe, recommend not")
    assert neg["sentiment"] == "negative" and neg["estimated_rating"] == 1


def test_explicit_fraction_rating_overrides_sentiment():
    out = fb.classify_post("Recommend Bondi Cafe 4/5")
    assert out["estimated_rating"] == 4


def test_non_name_words_are_filtered_from_business_names():
    out = fb.classify_post("Recommend Amazing Bondi Cafe")
    names = [b["name"] for b in out["businesses"]]
    assert names and all("amazing" not in n.lower() for n in names)


def test_summary_is_truncated_to_200_chars():
    out = fb.classify_post("recommend " + "x" * 500)
    assert len(out["summary"]) <= 200


def _post(**kw):
    base = {
        "is_review": True,
        "author_id": "u1",
        "author_name": "Sarah M.",
        "post_id": "p1",
        "businesses": [{"name": "Bondi Wholefoods", "category": "café"}],
        "estimated_rating": 5,
        "summary": "great",
    }
    base.update(kw)
    return base


def test_import_skips_non_reviews(db):
    assert fb.import_to_db(_post(is_review=False), db) == []
    assert db.query(models.Review).count() == 0


def test_import_creates_user_business_and_review(db):
    ids = fb.import_to_db(_post(), db)
    db.commit()
    assert len(ids) == 1
    review = db.query(models.Review).one()
    assert review.rating == 5
    assert review.source == "facebook_import"
    assert review.facebook_post_id == "p1"
    assert review.verified_visit is False
    biz = db.query(models.Business).one()
    assert (biz.name, biz.category, biz.source) == ("Bondi Wholefoods", "café", "facebook")
    assert db.query(models.User).one().mobile_number == "fb_u1"


def test_import_reuses_existing_user_and_business(db):
    fb.import_to_db(_post(post_id="p1"), db)
    fb.import_to_db(_post(post_id="p2"), db)
    db.commit()
    assert db.query(models.User).count() == 1
    assert db.query(models.Business).count() == 1
    assert db.query(models.Review).count() == 2


def test_import_one_review_per_business_mention(db):
    post = _post(businesses=[
        {"name": "Alpha", "category": "café"},
        {"name": "Beta", "category": "vet"},
    ])
    assert len(fb.import_to_db(post, db)) == 2
    assert db.query(models.Business).count() == 2


def test_import_truncates_long_author_name(db):
    fb.import_to_db(_post(author_name="N" * 300), db)
    assert len(db.query(models.User).one().first_name) == 100


def test_demo_mode_runs_without_credentials(db):
    imported, skipped = fb.run_pipeline()
    assert imported >= 1
    assert imported + skipped >= 4  # 5 sample posts; one may import 2 reviews
    assert db.query(models.Review).count() == imported


class _Resp:
    def __init__(self, status, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text

    def json(self):
        return self._body


def test_graph_api_error_returns_none_and_imports_nothing(db, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(500, text="boom"))
    assert fb.run_pipeline("tok", "grp") is None
    assert db.query(models.Review).count() == 0


def test_graph_api_posts_are_classified_and_empty_messages_skipped(db, monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(url=url, params=params)
        return _Resp(200, {"data": [
            {"id": "1", "from": {"id": "9", "name": "Ann"},
             "message": "Highly recommend Bondi Bakery, best bread. 5/5"},
            {"id": "2", "message": ""},
            {"id": "3", "message": "Selling a bike"},
        ]})

    monkeypatch.setattr(httpx, "get", fake_get)
    imported, skipped = fb.run_pipeline("tok", "grp", limit=7)
    assert (imported, skipped) == (1, 2)
    assert "/grp/feed" in seen["url"] and seen["params"]["limit"] == 7
    assert db.query(models.Review).one().facebook_post_id == "1"
