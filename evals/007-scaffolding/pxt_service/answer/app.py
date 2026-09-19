"""Reference solution for the pxt service eval.

Apply and serve:
    pxt init                          # once, if the dir has no project root
    pxt schema update app.py movies   # creates the catalog dir + tables
    pxt service update app.py movies  # starts HTTP; OpenAPI docs at /docs
"""
import pixeltable as pxt
from pixeltable.functions.openai import chat_completions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Reviews(TableModel, name='reviews'):
    title: pxt.String
    review_text: pxt.String
    sentiment = chat_completions(
        messages=[{
            'role': 'user',
            'content': 'Classify this movie review as positive, negative, or neutral. '
                'Reply with exactly one word.\n\nReview: ' + review_text,  # noqa: F821
        }],
        model='gpt-4o-mini',
    ).choices[0].message.content
    summary = chat_completions(
        messages=[{
            'role': 'user',
            'content': 'Summarize this movie review in one sentence:\n\n' + review_text,  # noqa: F821
        }],
        model='gpt-4o-mini',
    ).choices[0].message.content


api = FastAPIRouter(name='reviews')
api.add_insert_route(
    Reviews,
    path='/analyze',
    inputs=[Reviews.title, Reviews.review_text],
    outputs=[Reviews.title, Reviews.sentiment, Reviews.summary],
)
