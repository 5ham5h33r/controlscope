select vendor_id, vendor_name, active, business_unit
from {{ source('raw', 'raw_vendors') }}
