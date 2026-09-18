import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.document import document_splitter
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Docs(TableModel, name='pipe_docs'):
    """Source documents for a two-level chunking pipeline."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    name: pxt.String
    doc: pxt.Document


class Paras(TableModel, name='paras', base=Docs, iterator=document_splitter(Docs.doc, separators='paragraph')):
    """Paragraph chunks."""
    n_chars = pxtf.string.len(text)


class Sentences(TableModel, name='sentences', base=Paras, iterator=pxtf.string.string_splitter(Paras.text, separators='sentence')):
    """Sentences inside each paragraph (view over a view)."""
    word_count = pxtf.string.count(text, ' ') + 1


router = FastAPIRouter(name='pipe_docs')
router.add_insert_route(
    Docs,
    path='/docs',
    inputs=[Docs.name, Docs.doc],
    outputs=[Docs.id]
)
