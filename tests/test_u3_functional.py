"""End-to-end canary for the u3 functional check.

Runs a known-good TableModel + FastAPIRouter app through the real sandbox:
pxt init, schema update, service update, POST /analyze, cleanup. If this
fails, the harness is broken -- not the agents it grades. Computed columns
use local pxtf functions so no provider keys are needed.
"""

import shutil
import sys
from pathlib import Path

import pytest

from eval.sandbox import PixeltableSandbox
from eval.stories.u3_service import U3ServiceVerifier

APP = '''\
import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Reviews(TableModel, name='reviews'):
    title: pxt.String
    review_text: pxt.String
    sentiment = pxtf.string.upper(review_text)
    summary = pxtf.string.format('Summary: {}', review_text)


router = FastAPIRouter(name='ingest')
router.add_insert_route(
    Reviews,
    path='/analyze',
    inputs=[Reviews.title, Reviews.review_text],
    outputs=[Reviews.title, Reviews.sentiment, Reviews.summary],
)
'''


@pytest.mark.slow
def test_u3_functional_check_passes_reference_app():
    if not (Path(sys.executable).parent / "pxt").exists() and not shutil.which("pxt"):
        pytest.skip("pxt CLI not available next to this interpreter")

    with PixeltableSandbox(timeout=600) as sandbox:
        run = sandbox.exec_code(APP)
        assert run.success, f"reference app failed to execute:\n{run.stderr}"

        check = U3ServiceVerifier().functional_check(sandbox)

    assert check.get("pass") is True, f"functional check rejected the reference app: {check}"
    assert check.get("post_status") == 200, check
