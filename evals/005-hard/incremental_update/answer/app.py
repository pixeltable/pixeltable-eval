"""Reference answer for 005-hard/incremental_update.

Two insert waves compute only on new rows; a column added afterwards
backfills everything. No recreation, no re-inserts.
"""

import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions

pxt.create_dir('analytics', if_exists='ignore')

articles = pxt.create_table(
    'analytics.articles',
    {'title': pxt.String, 'body': pxt.String, 'source': pxt.String},
    if_exists='ignore',
)


@pxt.udf
def word_count(text: str) -> int:
    return len(text.split())


articles.add_computed_column(word_count=word_count(articles.body), if_exists='ignore')

articles.add_computed_column(
    sentiment=chat_completions(
        model='gpt-4o-mini',
        messages=[{
            'role': 'user',
            'content': pxtf.string.format(
                'Classify the sentiment (positive/negative/neutral): {}', articles.body
            ),
        }],
    ).choices[0].message.content,
    if_exists='ignore',
)

articles.add_computed_column(
    keywords=chat_completions(
        model='gpt-4o-mini',
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Extract 5 keywords as a JSON array: {}', articles.body),
        }],
    ).choices[0].message.content,
    if_exists='ignore',
)

# First wave: these three rows compute word_count/sentiment/keywords on insert.
articles.insert([
    {'title': 'One', 'body': 'Pixeltable makes pipelines declarative and pleasant.', 'source': 'blog'},
    {'title': 'Two', 'body': 'Terrible onboarding; nothing worked as documented.', 'source': 'forum'},
    {'title': 'Three', 'body': 'Solid incremental compute, mediocre docs.', 'source': 'blog'},
])

# Second wave: only these two new rows trigger the same computed columns.
articles.insert([
    {'title': 'Four', 'body': 'I love how computed columns just backfill.', 'source': 'forum'},
    {'title': 'Five', 'body': 'The worst API ergonomics I have seen this year.', 'source': 'blog'},
])

# Added after data exists: backfills all five rows automatically.
articles.add_computed_column(
    reading_time_minutes=articles.word_count / 200.0,
    if_exists='ignore',
)

negative = articles.where(articles.sentiment == 'negative').select(
    articles.title, articles.sentiment, articles.reading_time_minutes
)
print(negative.collect())
