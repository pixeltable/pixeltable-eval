import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions, transcriptions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class VideoFiles(TableModel, name='video_files'):
    """Store video files with transcription and analysis."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    video: pxt.Video
    description: pxt.String | None

    duration = pxtf.video.get_duration(video)
    audio_track = pxtf.video.extract_audio(video)
    transcript = transcriptions(audio_track, model='whisper-1')

    video_summary = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Write a 3-4 sentence summary of this video based on its transcript: {}', transcript.text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class Lectures(TableModel, name='lectures'):
    """Store educational lectures with chapter detection."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    lecture_video: pxt.Video
    instructor: pxt.String
    subject: pxt.String

    audio_track = pxtf.video.extract_audio(lecture_video)
    transcript = transcriptions(audio_track, model='whisper-1')

    chapters = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Divide this lecture transcript into 3-5 logical chapters with titles. Format: "Chapter X: Title". Transcript: {}', transcript.text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    concepts = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Extract the 5 most important concepts from this lecture. Return as bullet points: {}', transcript.text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


video_router = FastAPIRouter(name='video')
video_router.add_insert_route(
    VideoFiles,
    path='/video',
    inputs=[VideoFiles.title, VideoFiles.video, VideoFiles.description],
    outputs=[VideoFiles.id, VideoFiles.duration, VideoFiles.transcript, VideoFiles.video_summary]
)

lecture_router = FastAPIRouter(name='lectures')
lecture_router.add_insert_route(
    Lectures,
    path='/lectures',
    inputs=[Lectures.title, Lectures.lecture_video, Lectures.instructor, Lectures.subject],
    outputs=[Lectures.id, Lectures.transcript, Lectures.chapters, Lectures.concepts]
)
