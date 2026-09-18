import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Photos(TableModel, name='photos'):
    """Multipart image upload + processed image round-trip."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    name: pxt.String
    image: pxt.Image

    thumb = pxtf.image.resize(image, (256, 256))
    meta = pxtf.image.get_metadata(image)


router = FastAPIRouter(name='photos')
router.add_insert_route(
    Photos,
    path='/upload',
    inputs=[Photos.name],
    uploadfile_inputs=[Photos.image],
    outputs=[Photos.id, Photos.meta]
)
router.add_compute_route(
    Photos,
    path='/resize',
    uploadfile_inputs=[Photos.image],
    outputs=[Photos.thumb],
    return_fileresponse=True
)
