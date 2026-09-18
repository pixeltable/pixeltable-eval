import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


@pxt.udf
def sale_price(price: float) -> float:
    return round(price * 0.85, 2)


class Products(TableModel, name='products'):
    """Product catalog with full CRUD routes."""
    sku = pxt.Column(pxt.String, primary_key=True)
    name: pxt.String
    category: pxt.String
    price: pxt.Float
    stock: pxt.Int

    total_value = price * stock
    discounted = sale_price(price)

    __indexes__ = [pxt.BtreeIndex(category)]


router = FastAPIRouter(name='products')
router.add_insert_route(
    Products,
    path='/products',
    inputs=[Products.sku, Products.name, Products.category, Products.price, Products.stock],
    outputs=[Products.sku, Products.total_value, Products.discounted]
)
router.add_update_route(
    Products,
    path='/products/update',
    inputs=[Products.price, Products.stock],
    outputs=[Products.sku, Products.price, Products.total_value, Products.discounted]
)
router.add_delete_route(
    Products,
    path='/products/delete',
    match_columns=[Products.sku]
)
router.add_compute_route(
    Products,
    path='/products/preview',
    inputs=[Products.sku, Products.name, Products.category, Products.price, Products.stock],
    outputs=[Products.total_value, Products.discounted]
)
