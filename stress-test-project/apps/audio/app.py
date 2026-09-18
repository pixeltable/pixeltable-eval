import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions, transcriptions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class AudioFiles(TableModel, name='audio_files'):
    """Store audio files with transcription and analysis."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    audio: pxt.Audio
    description: pxt.String | None
    language: pxt.String | None
    
    # Transcribe audio using the OpenAI transcription API
    transcription = transcriptions(audio, model='whisper-1')

    # Analyze transcription sentiment
    sentiment = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Analyze the sentiment of this audio transcription. Return only positive, negative, or neutral: {}', transcription.text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    # Generate summary
    summary = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Summarize this audio transcription in 2-3 sentences: {}', transcription.text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class Podcasts(TableModel, name='podcasts'):
    """Store podcast episodes with segmentation."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    episode_title: pxt.String
    audio: pxt.Audio
    host_name: pxt.String
    guest_name: pxt.String | None
    
    # Transcribe podcast
    transcript = transcriptions(audio, model='whisper-1')

    # Extract topics
    topics = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Extract 3-5 main topics from this podcast transcript. Return as comma-separated list: {}', transcript.text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    # Generate episode summary
    episode_summary = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Write a 2-paragraph summary of this podcast episode: {}', transcript.text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


# FastAPI routes
audio_router = FastAPIRouter(name='audio')
audio_router.add_insert_route(
    AudioFiles,
    path='/audio',
    inputs=[AudioFiles.title, AudioFiles.audio, AudioFiles.description, AudioFiles.language],
    outputs=[AudioFiles.id, AudioFiles.transcription, AudioFiles.sentiment, AudioFiles.summary]
)

podcast_router = FastAPIRouter(name='podcasts')
podcast_router.add_insert_route(
    Podcasts,
    path='/podcasts',
    inputs=[Podcasts.episode_title, Podcasts.audio, Podcasts.host_name, Podcasts.guest_name],
    outputs=[Podcasts.id, Podcasts.transcript, Podcasts.topics, Podcasts.episode_summary]
)
