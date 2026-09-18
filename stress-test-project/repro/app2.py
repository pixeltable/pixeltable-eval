import pixeltable as pxt
import pixeltable.functions as pxtf

TableModel = pxt.model_base()


class T(TableModel, name='repro_t2'):
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    name: pxt.String
    msg = {'type': 'text', 'text': name}
