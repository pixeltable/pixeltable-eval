import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


@pxt.udf
def sale_size(revenue: float) -> str:
    if revenue > 1000:
        return 'LARGE'
    if revenue > 500:
        return 'MEDIUM'
    return 'SMALL'


@pxt.udf
def customer_tier(total_spent: float) -> str:
    if total_spent > 5000:
        return 'VIP'
    if total_spent > 1000:
        return 'Premium'
    return 'Standard'


@pxt.udf
def avg_order_value(total_spent: float, purchase_count: int) -> float | None:
    if purchase_count <= 0:
        return None
    return total_spent / purchase_count


@pxt.udf
def stock_status(stock_level: int, reorder_point: int) -> str:
    if stock_level <= 0:
        return 'out_of_stock'
    if stock_level <= reorder_point:
        return 'low_stock'
    if stock_level <= reorder_point * 2:
        return 'adequate'
    return 'well_stocked'


class SalesData(TableModel, name='sales_data'):
    """Store sales records with analytics."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    product_id: pxt.String
    sale_date: pxt.String
    quantity: pxt.Int
    price: pxt.Float
    region: pxt.String
    salesperson: pxt.String | None

    revenue = quantity * price
    size = sale_size(revenue)


class CustomerData(TableModel, name='customers'):
    """Store customer information with analysis."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    customer_id: pxt.String
    name: pxt.String
    email: pxt.String
    join_date: pxt.String
    total_spent: pxt.Float
    purchase_count: pxt.Int

    avg_order_value = avg_order_value(total_spent, purchase_count)
    tier = customer_tier(total_spent)

    customer_insights = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Analyze this customer profile. Name: {}, Spent: {}, Orders: {}. Write 2-3 sentences about their value and preferences.', name, total_spent, purchase_count)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class InventoryData(TableModel, name='inventory'):
    """Store inventory data with predictions."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    sku: pxt.String
    product_name: pxt.String
    stock_level: pxt.Int
    reorder_point: pxt.Int
    lead_time_days: pxt.Int
    unit_cost: pxt.Float

    status = stock_status(stock_level, reorder_point)
    inventory_value = stock_level * unit_cost

    restock_recommendation = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Product {} has {} units in stock, reorder point is {}, lead time is {} days. Should we reorder? Give a 2-3 sentence recommendation.', product_name, stock_level, reorder_point, lead_time_days)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


sales_router = FastAPIRouter(name='sales')
sales_router.add_insert_route(
    SalesData,
    path='/sales',
    inputs=[SalesData.product_id, SalesData.sale_date, SalesData.quantity, SalesData.price, SalesData.region],
    outputs=[SalesData.id, SalesData.revenue, SalesData.size]
)

customer_router = FastAPIRouter(name='customers')
customer_router.add_insert_route(
    CustomerData,
    path='/customers',
    inputs=[CustomerData.customer_id, CustomerData.name, CustomerData.email, CustomerData.join_date, CustomerData.total_spent, CustomerData.purchase_count],
    outputs=[CustomerData.id, CustomerData.avg_order_value, CustomerData.tier, CustomerData.customer_insights]
)

inventory_router = FastAPIRouter(name='inventory')
inventory_router.add_insert_route(
    InventoryData,
    path='/inventory',
    inputs=[InventoryData.sku, InventoryData.product_name, InventoryData.stock_level, InventoryData.reorder_point, InventoryData.lead_time_days, InventoryData.unit_cost],
    outputs=[InventoryData.id, InventoryData.status, InventoryData.inventory_value, InventoryData.restock_recommendation]
)
