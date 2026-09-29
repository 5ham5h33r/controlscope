select transaction_id, vendor_id, invoice_id, amount, currency,
       business_unit, initiator_id, nullif(approver_id, '') as approver_id,
       paid_at, payment_status
from {{ source('raw', 'raw_transactions') }}
