"""End-to-end canaries for the u4/u5 functional checks.

Same contract as test_u3_functional: a known-good app must pass its own
functional check through the real sandbox. u4's app is the crud_service
reference answer (pure-Python computed column, no provider keys); u5's is a
hermetic incremental pipeline (UDF sentiment, no LLM calls).
"""

import shutil
import sys
from pathlib import Path

import pytest

from eval.sandbox import PixeltableSandbox
from eval.stories.u4_crud_service import U4CrudServiceVerifier
from eval.stories.u5_incremental import U5IncrementalVerifier

CRUD_ANSWER = (
    Path(__file__).parent.parent
    / "evals/007-scaffolding/crud_service/answer/app.py"
)

# Same semantics as the incremental_update answer but with a deterministic
# UDF standing in for the LLM sentiment so the run needs no provider keys.
U5_HERMETIC_APP = '''\
import pixeltable as pxt

pxt.create_dir('analytics', if_exists='ignore')

articles = pxt.create_table(
    'analytics.articles',
    {'title': pxt.String, 'body': pxt.String, 'source': pxt.String},
    if_exists='ignore',
)


@pxt.udf
def word_count(text: str) -> int:
    return len(text.split())


@pxt.udf
def sentiment(text: str) -> str:
    return 'negative' if 'worst' in text or 'Terrible' in text else 'positive'


@pxt.udf
def keywords(text: str) -> str:
    return ','.join(sorted(set(text.lower().split()))[:5])


articles.add_computed_column(word_count=word_count(articles.body), if_exists='ignore')
articles.add_computed_column(sentiment=sentiment(articles.body), if_exists='ignore')
articles.add_computed_column(keywords=keywords(articles.body), if_exists='ignore')

articles.insert([
    {'title': 'One', 'body': 'Pixeltable makes pipelines declarative.', 'source': 'blog'},
    {'title': 'Two', 'body': 'Terrible onboarding experience.', 'source': 'forum'},
    {'title': 'Three', 'body': 'Solid incremental compute.', 'source': 'blog'},
])
articles.insert([
    {'title': 'Four', 'body': 'I love computed columns.', 'source': 'forum'},
    {'title': 'Five', 'body': 'The worst API ergonomics.', 'source': 'blog'},
])

articles.add_computed_column(
    reading_time_minutes=articles.word_count / 200.0,
    if_exists='ignore',
)

negative = articles.where(articles.sentiment == 'negative').select(
    articles.title, articles.sentiment, articles.reading_time_minutes
)
print(negative.collect())
'''


def _has_pxt() -> bool:
    return (Path(sys.executable).parent / "pxt").exists() or bool(shutil.which("pxt"))


@pytest.mark.slow
def test_u4_functional_check_passes_reference_app():
    if not _has_pxt():
        pytest.skip("pxt CLI not available next to this interpreter")
    app = CRUD_ANSWER.read_text()
    with PixeltableSandbox(timeout=600) as sandbox:
        run = sandbox.exec_code(app)
        assert run.success, f"reference app failed to execute:\n{run.stderr}"
        check = U4CrudServiceVerifier().functional_check(sandbox)
    assert check.get("pass") is True, f"functional check rejected the reference app: {check}"


@pytest.mark.slow
def test_u5_functional_check_passes_hermetic_app():
    with PixeltableSandbox(timeout=600) as sandbox:
        run = sandbox.exec_code(U5_HERMETIC_APP)
        assert run.success, f"hermetic app failed to execute:\n{run.stderr}"
        check = U5IncrementalVerifier().functional_check(sandbox)
    assert check.get("pass") is True, f"functional check rejected the app: {check}"
    assert check.get("row_count") == 5
