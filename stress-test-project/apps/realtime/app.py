import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


@pxt.udf
def alert_level(temperature: float, humidity: float) -> str:
    if temperature > 30:
        return 'high_temp'
    if temperature < 10:
        return 'low_temp'
    if humidity > 80:
        return 'high_humidity'
    return 'normal'


@pxt.udf
def severity(bytes_transferred: int) -> str:
    if bytes_transferred > 10000000:
        return 'high'
    if bytes_transferred > 1000000:
        return 'medium'
    return 'low'


@pxt.udf
def behavior_pattern(activity_score: float) -> str:
    if activity_score > 50:
        return 'heavy_user'
    if activity_score > 20:
        return 'active_user'
    return 'light_user'


class SensorData(TableModel, name='sensor_data'):
    """Store real-time sensor data."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    sensor_id: pxt.String
    timestamp: pxt.String
    temperature: pxt.Float
    humidity: pxt.Float
    pressure: pxt.Float
    location: pxt.String

    comfort_index = (temperature * 0.5 + humidity * 0.5) / 100
    alert = alert_level(temperature, humidity)


class NetworkEvents(TableModel, name='network_events'):
    """Store network monitoring events."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    event_id: pxt.String
    timestamp: pxt.String
    source_ip: pxt.String
    destination_ip: pxt.String
    protocol: pxt.String
    bytes_transferred: pxt.Int
    status: pxt.String

    data_rate_mbps = bytes_transferred / 1000000
    event_severity = severity(bytes_transferred)

    security_alert = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Analyze this network event. Source: {}, Destination: {}, Protocol: {}, Bytes: {}. Is this potentially suspicious? Give a 2-3 sentence assessment.', source_ip, destination_ip, protocol, bytes_transferred)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class UserActivity(TableModel, name='user_activity'):
    """Store user activity logs."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    user_id: pxt.String
    timestamp: pxt.String
    action: pxt.String
    resource: pxt.String
    ip_address: pxt.String
    user_agent: pxt.String

    activity_score = pxtf.string.len(action) * 2 + pxtf.string.len(resource) * 1.5
    pattern = behavior_pattern(activity_score)

    behavior_insights = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Analyze this user activity. Action: {}, Resource: {}, IP: {}. What does this suggest about user behavior? Give 2-3 sentences.', action, resource, ip_address)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


sensor_router = FastAPIRouter(name='sensors')
sensor_router.add_insert_route(
    SensorData,
    path='/sensors',
    inputs=[SensorData.sensor_id, SensorData.timestamp, SensorData.temperature, SensorData.humidity, SensorData.pressure, SensorData.location],
    outputs=[SensorData.id, SensorData.comfort_index, SensorData.alert]
)

network_router = FastAPIRouter(name='network')
network_router.add_insert_route(
    NetworkEvents,
    path='/network',
    inputs=[NetworkEvents.event_id, NetworkEvents.timestamp, NetworkEvents.source_ip, NetworkEvents.destination_ip, NetworkEvents.protocol, NetworkEvents.bytes_transferred, NetworkEvents.status],
    outputs=[NetworkEvents.id, NetworkEvents.data_rate_mbps, NetworkEvents.event_severity, NetworkEvents.security_alert]
)

activity_router = FastAPIRouter(name='activity')
activity_router.add_insert_route(
    UserActivity,
    path='/activity',
    inputs=[UserActivity.user_id, UserActivity.timestamp, UserActivity.action, UserActivity.resource, UserActivity.ip_address, UserActivity.user_agent],
    outputs=[UserActivity.id, UserActivity.activity_score, UserActivity.pattern, UserActivity.behavior_insights]
)
