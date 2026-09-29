select event_id, user_id, event_type, occurred_at, source_ip
from {{ source('raw', 'raw_access_events') }}
