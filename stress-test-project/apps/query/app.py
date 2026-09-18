import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import embeddings
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Articles(TableModel, name='articles'):
    """Articles with an embedding index and parameterized query routes."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    topic: pxt.String
    body: pxt.String

    __indexes__ = [pxt.EmbeddingIndex(column=body, string_embed=embeddings.using(model='text-embedding-3-small'))]


@pxt.query
def search_articles(text: str, n: int):
    sim = Articles.body.similarity(text)
    return (
        Articles
        .where(sim > 0.4)
        .order_by(sim, asc=False)
        .select(Articles.title, Articles.topic, score=sim)
        .limit(n)
    )


@pxt.query
def by_topic(topic: str):
    return Articles.where(Articles.topic == topic).select(Articles.title, Articles.body)


router = FastAPIRouter(name='articles')
router.add_insert_route(
    Articles,
    path='/articles',
    inputs=[Articles.title, Articles.topic, Articles.body],
    outputs=[Articles.id]
)
router.add_query_route(path='/search', query=search_articles)
router.add_query_route(path='/topic', query=by_topic, method='get')
