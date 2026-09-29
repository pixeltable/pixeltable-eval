"""Reference answer for 007-scaffolding/crud_service (story u4).

TableModel with a UDF-computed slug; insert -> query -> delete routes that
chain through the stored row. Applied with pxt schema update and served
with pxt service update.
"""

import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


@pxt.udf
def slugify(name: str) -> str:
    return '-'.join(name.lower().split())


class Products(TableModel, name='products'):
    sku: pxt.String
    name: pxt.String
    price: pxt.Float
    slug = slugify(name)
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)


router = FastAPIRouter(name='catalog')
router.add_insert_route(
    Products,
    path='/products',
    inputs=[Products.sku, Products.name, Products.price],
    outputs=[Products.id, Products.sku, Products.slug],
)


@pxt.query
def get_product(sku: str):
    return Products.where(Products.sku == sku).select(
        Products.sku, Products.name, Products.price, Products.slug
    )


router.add_query_route(path='/product', query=get_product, method='get', one_row=True)
router.add_delete_route(Products, path='/products/delete')

# Commands:
#   pxt init
#   pxt schema update app.py my_app
#   pxt service update app.py my_app
