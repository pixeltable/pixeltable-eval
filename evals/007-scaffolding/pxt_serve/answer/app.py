"""Reference solution for pxt serve eval."""
import pixeltable as pxt
from pixeltable.functions.openai import chat_completions

pxt.create_dir('movies', if_exists='ignore')
t = pxt.create_table(
    'movies.reviews',
    {'title': pxt.String, 'review_text': pxt.String},
    if_exists='ignore',
)

t.add_computed_column(
    sentiment=chat_completions(
        messages=[{
            'role': 'user',
            'content': t.review_text.apply(
                lambda x: f'Classify this movie review as positive, negative, or neutral. '
                f'Reply with exactly one word.\n\nReview: {x}'
            ),
        }],
        model='gpt-4o-mini',
    ).choices[0].message.content,
    if_exists='ignore',
)

t.add_computed_column(
    summary=chat_completions(
        messages=[{
            'role': 'user',
            'content': t.review_text.apply(
                lambda x: f'Summarize this movie review in one sentence:\n\n{x}'
            ),
        }],
        model='gpt-4o-mini',
    ).choices[0].message.content,
    if_exists='ignore',
)


@pxt.query
def analyze_review(title: str, review_text: str):
    t = pxt.get_table('movies.reviews')
    t.insert([{'title': title, 'review_text': review_text}])
    return t.select(t.title, t.sentiment, t.summary).order_by(t.title).limit(1)
