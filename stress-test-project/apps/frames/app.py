import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Videos(TableModel, name='videos'):
    """Source videos for frame-level analysis."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    video: pxt.Video

    duration = pxtf.video.get_duration(video)


class Frames(TableModel, name='frames', base=Videos, iterator=pxtf.video.frame_iterator(Videos.video, num_frames=4)):
    """One row per sampled frame."""
    thumb = pxtf.image.resize(frame, (320, 240))

    caption = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'image_url': frame, 'type': 'image_url'},
                {'text': pxtf.string.format('Describe this frame from {} in one sentence.', title), 'type': 'text'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


router = FastAPIRouter(name='videos')
router.add_insert_route(
    Videos,
    path='/videos',
    inputs=[Videos.title, Videos.video],
    outputs=[Videos.id, Videos.duration]
)
