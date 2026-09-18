import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Images(TableModel, name='images'):
    """Store images with computer vision analysis."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    image: pxt.Image
    description: pxt.String | None
    category: pxt.String | None

    width = pxtf.image.width(image)
    height = pxtf.image.height(image)
    metadata = pxtf.image.get_metadata(image)

    description_ai = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': 'Describe this image in 2-3 sentences.', 'type': 'text'}, {'image_url': image, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    objects = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': 'List 5 objects you see in this image. Return as comma-separated list.', 'type': 'text'}, {'image_url': image, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class ProductImages(TableModel, name='product_images'):
    """Store product images for e-commerce."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    product_name: pxt.String
    image: pxt.Image
    price: pxt.Float
    brand: pxt.String | None

    product_description = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': pxtf.string.format('Write a product description for this e-commerce image of "{}".', product_name), 'type': 'text'},
                {'image_url': image, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    features = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': 'Extract 3-5 key product features from this image. Return as bullet points.', 'type': 'text'}, {'image_url': image, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    marketing_copy = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': pxtf.string.format('Write a 2-paragraph marketing description for "{}" priced at {}.', product_name, price), 'type': 'text'},
                {'image_url': image, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class Screenshots(TableModel, name='screenshots'):
    """Store app screenshots with UI analysis."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    app_name: pxt.String
    screenshot: pxt.Image
    platform: pxt.String

    ui_analysis = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': 'Analyze this app screenshot UI. What are the main UI elements?', 'type': 'text'}, {'image_url': screenshot, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    text_content = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': 'Extract all visible text from this screenshot.', 'type': 'text'}, {'image_url': screenshot, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    ux_feedback = chat_completions(
        messages=[{
            'role': 'user',
            'content': [
                {'text': 'Evaluate this app UI. What works well and what could be improved?', 'type': 'text'}, {'image_url': screenshot, 'type': 'image_url'},
            ],
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


image_router = FastAPIRouter(name='images')
image_router.add_insert_route(
    Images,
    path='/images',
    inputs=[Images.title, Images.image, Images.description],
    outputs=[Images.id, Images.description_ai, Images.objects, Images.width, Images.height]
)

product_router = FastAPIRouter(name='products')
product_router.add_insert_route(
    ProductImages,
    path='/products',
    inputs=[ProductImages.product_name, ProductImages.image, ProductImages.price, ProductImages.brand],
    outputs=[ProductImages.id, ProductImages.product_description, ProductImages.features, ProductImages.marketing_copy]
)

screenshot_router = FastAPIRouter(name='screenshots')
screenshot_router.add_insert_route(
    Screenshots,
    path='/screenshots',
    inputs=[Screenshots.app_name, Screenshots.screenshot, Screenshots.platform],
    outputs=[Screenshots.id, Screenshots.ui_analysis, Screenshots.text_content, Screenshots.ux_feedback]
)
