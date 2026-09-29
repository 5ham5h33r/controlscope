select user_id, user_name, employment_status, privileged, business_unit
from {{ source('raw', 'raw_users') }}
