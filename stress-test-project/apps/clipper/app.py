import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions, transcriptions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Podcasts(TableModel, name='podcasts'):
    """Source audio for chunked transcription."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    audio: pxt.Audio


class Segments(TableModel, name='segments', base=Podcasts, iterator=pxtf.audio.audio_splitter(Podcasts.audio, duration=30.0, overlap=5.0)):
    """One row per ~30s audio segment (segment_start, segment_end, audio_segment)."""
    segment_len = segment_end - segment_start

    transcript = transcriptions(audio_segment, model='whisper-1').text

    gist = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('One-line summary of this transcript excerpt from {}: {}', title, transcript)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


router = FastAPIRouter(name='podcasts')
router.add_insert_route(
    Podcasts,
    path='/podcasts',
    inputs=[Podcasts.title, Podcasts.audio],
    outputs=[Podcasts.id]
)
