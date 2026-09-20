"""Reference solution: PDF RAG with Pixeltable."""
import pixeltable as pxt
from pixeltable.functions.document import document_splitter
from pixeltable.functions.openai import chat_completions, embeddings

pxt.create_dir('app', if_exists='ignore')

docs = pxt.create_table('app.documents', {'doc': pxt.Document}, if_exists='ignore')
docs.insert([{'doc': f'docs/{f}'} for f in __import__('os').listdir('docs') if f.endswith('.pdf')])

chunks = pxt.create_view(
    'app.chunks', docs,
    iterator=document_splitter(docs.doc, separators='token_limit', limit=300),
    if_exists='ignore'
)

chunks.add_embedding_index(
    'text',
    embedding=embeddings.using(model='text-embedding-3-small'),
    if_exists='ignore'
)


@pxt.query
def search_chunks(query: str, limit: int = 5):
    sim = chunks.text.similarity(string=query)
    return chunks.order_by(sim, asc=False).limit(limit).select(chunks.text, sim)


def ask(question: str) -> str:
    sim = chunks.text.similarity(string=question)
    context_rows = chunks.order_by(sim, asc=False).limit(5).select(chunks.text).collect()
    context = "\n".join(row['text'] for row in context_rows)
    prompt = f"Answer based on context:\n{context}\n\nQuestion: {question}"

    answer_table = pxt.create_table('app.answers', {
        'question': pxt.String,
        'context': pxt.String,
    }, if_exists='ignore')

    answer_table.add_computed_column(
        answer=chat_completions(
            messages=[{'role': 'user', 'content': answer_table.question + '\n\nContext: ' + answer_table.context}],
            model='gpt-4o-mini'
        ).choices[0].message.content,
        if_exists='ignore'
    )

    answer_table.insert([{'question': question, 'context': context}])
    result = answer_table.where(answer_table.question == question).select(answer_table.answer).collect()
    return result[0]['answer'] if result else "No answer found"


if __name__ == '__main__':
    print(ask("How many vacation days do employees get?"))
