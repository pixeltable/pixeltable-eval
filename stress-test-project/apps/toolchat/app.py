import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions, embeddings, invoke_tools
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class KB(TableModel, name='kb'):
    """Knowledge base with an embedding index."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    topic: pxt.String
    content: pxt.String

    __indexes__ = [pxt.EmbeddingIndex(column=content, string_embed=embeddings.using(model='text-embedding-3-small'))]


@pxt.query
def kb_lookup(text: str):
    """Look up knowledge-base entries relevant to `text`."""
    sim = KB.content.similarity(text)
    return KB.order_by(sim, asc=False).select(KB.topic, KB.content, score=sim).limit(3)


class Questions(TableModel, name='questions'):
    """Questions answered by a plain chat column."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    question: pxt.String

    answer = chat_completions(
        messages=[{'role': 'user', 'content': question}],
        model='gpt-4o-mini'
    ).choices[0].message.content


kb_router = FastAPIRouter(name='kb')
kb_router.add_insert_route(
    KB,
    path='/kb',
    inputs=[KB.topic, KB.content],
    outputs=[KB.id]
)
kb_router.add_query_route(path='/lookup', query=kb_lookup)

q_router = FastAPIRouter(name='questions')
q_router.add_insert_route(
    Questions,
    path='/ask',
    inputs=[Questions.question],
    outputs=[Questions.id, Questions.answer]
)
