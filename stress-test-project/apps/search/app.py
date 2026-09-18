import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions, embeddings
from pixeltable.functions.document import document_splitter
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()

embed_model = embeddings.using(model='text-embedding-3-small')


class KnowledgeBase(TableModel, name='knowledge_base'):
    """Store knowledge base documents."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    doc: pxt.Document
    category: pxt.String


class KbChunks(TableModel, name='kb_chunks', base=KnowledgeBase,
               iterator=document_splitter(KnowledgeBase.doc, separators='paragraph')):
    """View: one row per paragraph, with an embedding index on `text`."""

    __indexes__ = [pxt.EmbeddingIndex(column=text, string_embed=embed_model)]

    chunk_summary = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Summarize this text in one sentence: {}', text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class FAQ(TableModel, name='faq'):
    """Store FAQ entries with similarity search."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    question: pxt.String
    answer: pxt.String
    category: pxt.String

    __indexes__ = [pxt.EmbeddingIndex(column=question, string_embed=embed_model)]

    related_questions = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Generate 3 similar questions to this FAQ. Format as "Q1, Q2, Q3": {}', question)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class Products(TableModel, name='products'):
    """Store product information with semantic search."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    name: pxt.String
    description: pxt.String
    price: pxt.Float
    category: pxt.String

    __indexes__ = [pxt.EmbeddingIndex(column=description, string_embed=embed_model)]

    recommendations = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Suggest 3 similar products to this one. Format as "Product 1, Product 2, Product 3": {} - {}', name, description)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


@pxt.query
def search_knowledge(query: str, limit: int = 5):
    """Semantic search over knowledge base chunks."""
    sim = KbChunks.text.similarity(string=query)
    return (
        KbChunks.order_by(sim, asc=False)
        .limit(limit)
        .select(KbChunks.title, KbChunks.category, KbChunks.text, similarity=sim)
    )


@pxt.query
def search_faq(query: str, limit: int = 5):
    """Semantic search over FAQ questions."""
    sim = FAQ.question.similarity(string=query)
    return (
        FAQ.order_by(sim, asc=False)
        .limit(limit)
        .select(FAQ.question, FAQ.answer, FAQ.category, similarity=sim)
    )


@pxt.query
def search_products(query: str, limit: int = 5):
    """Semantic search over product descriptions."""
    sim = Products.description.similarity(string=query)
    return (
        Products.order_by(sim, asc=False)
        .limit(limit)
        .select(Products.name, Products.description, Products.price, Products.category, similarity=sim)
    )


kb_router = FastAPIRouter(name='knowledge')
kb_router.add_insert_route(
    KnowledgeBase,
    path='/knowledge',
    inputs=[KnowledgeBase.title, KnowledgeBase.doc, KnowledgeBase.category],
    outputs=[KnowledgeBase.id]
)
kb_router.add_query_route(path='/knowledge/search', query=search_knowledge, method='post')

faq_router = FastAPIRouter(name='faq')
faq_router.add_insert_route(
    FAQ,
    path='/faq',
    inputs=[FAQ.question, FAQ.answer, FAQ.category],
    outputs=[FAQ.id, FAQ.related_questions]
)
faq_router.add_query_route(path='/faq/search', query=search_faq, method='post')

product_router = FastAPIRouter(name='products')
product_router.add_insert_route(
    Products,
    path='/products',
    inputs=[Products.name, Products.description, Products.price, Products.category],
    outputs=[Products.id, Products.recommendations]
)
product_router.add_query_route(path='/products/search', query=search_products, method='post')
