import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Metrics(TableModel, name='metrics'):
    """Timestamped events: date bucketing + a custom aggregate."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    kind: pxt.String
    ts: pxt.Timestamp
    value: pxt.Float

    day = pxtf.timestamp.date(ts)
    hour = pxtf.timestamp.hour(ts)
    weekday = pxtf.timestamp.weekday(ts)
    month = pxtf.timestamp.month(ts)


@pxt.uda
class p90(pxt.Aggregator):
    """Approximate 90th percentile."""
    def __init__(self):
        self.vals = []

    def update(self, v: float):
        if v is not None:
            self.vals.append(v)

    def value(self) -> float | None:
        if not self.vals:
            return None
        s = sorted(self.vals)
        return s[min(int(len(s) * 0.9), len(s) - 1)]


@pxt.query
def daily_stats(kind: str):
    return (
        Metrics
        .where(Metrics.kind == kind)
        .group_by(Metrics.day)
        .select(Metrics.day, n=pxtf.count(Metrics.id), total=pxtf.sum(Metrics.value), hi=pxtf.max(Metrics.value), p90=p90(Metrics.value))
    )


router = FastAPIRouter(name='metrics')
router.add_insert_route(
    Metrics,
    path='/metrics',
    inputs=[Metrics.kind, Metrics.ts, Metrics.value],
    outputs=[Metrics.id, Metrics.day, Metrics.hour, Metrics.weekday]
)
router.add_query_route(path='/daily', query=daily_stats, method='get')
