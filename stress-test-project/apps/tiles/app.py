import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Maps(TableModel, name='maps'):
    """Large images split into tiles for per-tile analysis."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    name: pxt.String
    image: pxt.Image


class Tiles(TableModel, name='tiles', base=Maps, iterator=pxtf.image.tile_iterator(Maps.image, tile_size=(512, 512))):
    """One row per tile (tile, tile_coord, tile_box)."""
    tile_w = pxtf.image.width(tile)

    note = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'image_url': tile, 'type': 'image_url'},
                {'text': 'What does this image tile contain? One line.', 'type': 'text'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


router = FastAPIRouter(name='maps')
router.add_insert_route(
    Maps,
    path='/maps',
    inputs=[Maps.name, Maps.image],
    outputs=[Maps.id]
)
