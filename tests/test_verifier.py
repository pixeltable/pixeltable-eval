"""Self-tests for the grading layer.

These run without a runner or a sandbox: they exercise the static analysis
and scoring paths of the verifiers so a broken regex or pattern list shows
up as a test failure instead of silently mis-graded agent output.
"""

import re

import pytest

from eval.stories.u1_pdf_rag import U1PdfRagVerifier
from eval.stories.u2_scaffolding import U2ScaffoldingVerifier
from eval.stories.u3_service import U3ServiceVerifier
from eval.verifier import HALLUCINATED_APIS, StoryVerifier, command_evidence

# --- command_evidence: prose earns no credit, commands do ---

def test_command_evidence_picks_up_bash_blocks():
    transcript = (
        "I will now create the tables.\n"
        "```bash\n"
        "pxt schema update app.py my_app\n"
        "pxt service update app.py my_app\n"
        "```\n"
        "The service is now running.\n"
    )
    ev = command_evidence(transcript)
    assert "pxt schema update" in ev
    assert "pxt service update" in ev
    assert "running" not in ev


def test_command_evidence_picks_up_tool_call_lines():
    transcript = "blah\n⏺ pxt service update app.py my_app\nmore prose\n"
    assert "pxt service update" in command_evidence(transcript)


def test_command_evidence_ignores_prose_and_python():
    transcript = (
        "You should run pxt service update to start it.\n"
        "```python\n"
        "import pixeltable as pxt\n"
        "```\n"
    )
    assert command_evidence(transcript) == ""


def test_command_evidence_untagged_shell_block():
    transcript = "```\npxt init\ncd my_app\n```\n"
    assert "pxt init" in command_evidence(transcript)


# --- hallucination list: every pattern must fire on a real snippet ---

HALLUCINATION_SNIPPETS = {
    "openai.vision": "resp = openai.vision.chat(messages)",
    "pixeltable.iterators": "from pixeltable.iterators import document_splitter",
    "pxt.Table": "t = pxt.Table('docs', schema)",
    "pxt.load_table": "t = pxt.load_table('docs')",
    "pxt.connect": "pxt.connect('localhost')",
    ".similarity() positional": "t.text.similarity('query')",
    "from pixeltable import Table": "from pixeltable import Table",
    "pxt.Required": "name: pxt.Required[pxt.String]",
    "pxt serve": "pxt serve app.py",
    "tool.pixeltable.serve": "[tool.pixeltable.serve]\nport = 8000",
    "[[service]]": "[[service]]\npath = '/x'",
    "pixeltable-new flags": "uvx pixeltable-new myproj --backend fastapi",
    "embeddings(model=...)": "embeddings(model='intfloat/e5-large-v2')",
    "Model.view()": "chunks = Documents.view(iterator=document_splitter(document=Documents.doc))",
    "base= iterator": "pxt.create_view('chunks', base=document_splitter(document=docs.doc))",
    "self_path": "img.self_path",
}


def test_every_hallucination_pattern_fires():
    """Each entry in HALLUCINATED_APIS must match at least one snippet; a
    pattern that matches nothing is dead weight and hides drift."""
    corpus = "\n".join(HALLUCINATION_SNIPPETS.values())
    unmatched = [
        desc for pattern, desc in HALLUCINATED_APIS
        if not re.search(pattern, corpus, re.MULTILINE)
    ]
    assert not unmatched, f"patterns match nothing in the corpus: {unmatched}"


@pytest.mark.parametrize("desc,snippet", list(HALLUCINATION_SNIPPETS.items()))
def test_hallucination_snippet_detected(desc, snippet):
    """Each crafted snippet is actually caught by its intended pattern."""
    fired = [d for p, d in HALLUCINATED_APIS if re.search(p, snippet, re.MULTILINE)]
    assert any(desc.split(" ")[0] in f or f.startswith(desc.split(" ")[0]) for f in fired), \
        f"snippet for {desc!r} fired {fired} instead"


# --- static scoring on known-good / known-bad code ---

GOOD_U3_APP = '''\
import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions import openai
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Reviews(TableModel, name='reviews'):
    title: pxt.String
    review_text: pxt.String
    sentiment = openai.chat_completions(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': pxtf.string.format(
            'Classify: {}', review_text)}],
    ).choices[0].message.content
    summary = openai.chat_completions(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': pxtf.string.format(
            'Summarize in one sentence: {}', review_text)}],
    ).choices[0].message.content


router = FastAPIRouter(name='api')
router.add_insert_route(
    Reviews, path='/analyze',
    inputs=[Reviews.title, Reviews.review_text],
    outputs=[Reviews.title, Reviews.sentiment, Reviews.summary],
)
'''

GOOD_U3_COMMANDS = "pxt init\npxt schema update app.py eval_app\npxt service update app.py eval_app\n"

BAD_APP = '''\
import pandas as pd
from langchain import OpenAI
import uvicorn

df = pd.DataFrame()
uvicorn.run(app)
'''


def test_u3_static_pass_on_reference_style_code():
    v = U3ServiceVerifier()
    res = v.verify(GOOD_U3_APP, transcript=f"```bash\n{GOOD_U3_COMMANDS}```")
    assert res.static_pass, f"missing: {[k for k, ok in res.positive_hits.items() if not ok]}"
    assert not res.negative_hits or not any(res.negative_hits.values())
    assert res.hallucination_count == 0


def test_u3_static_flags_antipatterns():
    v = U3ServiceVerifier()
    res = v.verify(BAD_APP)
    assert res.hallucination_count >= 0
    fired = [d for d, hit in res.negative_hits.items() if hit]
    assert fired
    assert not res.static_pass


def test_skipped_functional_reweights_to_static():
    """No sandbox -> composite is just the static score."""
    v = U3ServiceVerifier()
    res = v.verify(GOOD_U3_APP, transcript=f"```bash\n{GOOD_U3_COMMANDS}```")
    assert res.functional_pass is None
    assert res.score == res.static_score


def test_describing_commands_earns_no_credit():
    """Positive patterns must not fire on prose; only on artifacts."""
    v = U3ServiceVerifier()
    res = v.verify("", transcript="You should run pxt service update and pxt schema update.")
    assert res.score == 0.0


def test_all_story_verifiers_instantiate():
    for cls in (U1PdfRagVerifier, U2ScaffoldingVerifier, U3ServiceVerifier):
        v = cls()
        assert v.story_id
        assert v.positive_patterns and v.negative_patterns
        assert isinstance(v, StoryVerifier)
