import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Orders(TableModel, name='orders'):
    """Nested JSON payloads: keys, counts, array ops, map/filter/sort."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    customer: pxt.String
    payload: pxt.Json

    top_keys = pxtf.json.keys(payload)
    n_items = pxtf.json.len(payload.get('items'))
    prices = pxtf.map(payload.get('items'), lambda e: e.get('price'))
    sorted_tags = pxtf.sort(payload.get('tags'))
    has_coupon = payload.contains('coupon')
    packed = pxtf.json.dumps(payload)


router = FastAPIRouter(name='orders')
router.add_insert_route(
    Orders,
    path='/orders',
    inputs=[Orders.customer, Orders.payload],
    outputs=[Orders.id, Orders.top_keys, Orders.n_items, Orders.prices, Orders.sorted_tags, Orders.has_coupon]
)
