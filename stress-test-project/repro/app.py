import pixeltable as pxt
import pixeltable.functions as pxtf

TableModel = pxt.model_base()


class T(TableModel, name='repro_t'):
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    name: pxt.String
    meta = {'zzz': 'a', 'aaa': 'b'}
    greet = f'hi {name}'
