"""Route surfaces the rest of the suite does not touch.

- POST /products dual-writes each inserted row to an external SQL table
  via export_sql.
- GET /product returns a single object (one_row=True).
- GET /thumb downloads the thumbnail image (return_fileresponse=True).
- GET /export-status reports the export target (digest, not credentials)
  and its row count, so the dual-write is observable inside the service.
- The service is a plain fastapi.FastAPI object that includes the router,
  plus hand-written /healthz and /export-status routes.

EXPORT_DB_URL holds the SQLAlchemy connection string. Locally it falls back
to a sqlite file next to this file; on a hosted database set it with
`pxt secret set pxt://org:db EXPORT_DB_URL=...` and restart the service.
"""

import os
from pathlib import Path

import pixeltable as pxt
import pixeltable.functions as pxtf
import sqlalchemy as sa
from fastapi import FastAPI
from pixeltable.serving import FastAPIRouter, SqlExport

TableModel = pxt.model_base()

_EXPORT = SqlExport(
    db_connect=os.environ.get('EXPORT_DB_URL', f'sqlite:///{Path(__file__).parent / "export.db"}'),
    table='products',
)
_engine = sa.create_engine(_EXPORT.db_connect)

# The export target table must exist before the first insert lands. Creating
# it at import is idempotent and does not touch the pixeltable catalog.
with _engine.begin() as _conn:
    _conn.execute(
        sa.text('CREATE TABLE IF NOT EXISTS products (sku VARCHAR(64), name VARCHAR(256), price FLOAT, slug VARCHAR(256))')
    )


@pxt.udf
def slugify(name: str) -> str:
    return name.strip().lower().replace(' ', '-')


class Products(TableModel, name='products'):
    sku: pxt.String
    name: pxt.String
    price: pxt.Float
    photo: pxt.Image | None

    slug = slugify(name)
    thumb = pxtf.image.resize(photo, (128, 128))


@pxt.query
def by_sku(sku: str):
    return Products.where(Products.sku == sku).select(
        sku=Products.sku, name=Products.name, price=Products.price, slug=Products.slug
    )


@pxt.query
def thumb_for(sku: str):
    return Products.where(Products.sku == sku).select(thumb=Products.thumb)


router = FastAPIRouter(name='export')
router.add_insert_route(
    Products,
    path='/products',
    inputs=[Products.sku, Products.name, Products.price, Products.photo],
    outputs=[Products.sku, Products.name, Products.price, Products.slug],
    export_sql=_EXPORT,
)
router.add_query_route(path='/product', query=by_sku, method='get', one_row=True)
router.add_query_route(path='/thumb', query=thumb_for, method='get', one_row=True, return_fileresponse=True)

app = FastAPI()
app.include_router(router)


@app.get('/healthz')
def healthz() -> dict:
    return {'ok': True}


@app.get('/export-status')
def export_status() -> dict:
    with _engine.connect() as conn:
        rows = conn.execute(sa.text('SELECT COUNT(*) FROM products')).scalar()
    return {'target': _EXPORT.display_dict(), 'rows': rows}
