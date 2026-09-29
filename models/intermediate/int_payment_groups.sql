with payments as (
    select * from {{ ref('stg_transactions') }} where payment_status = 'paid'
)
select vendor_id, date(paid_at) as paid_date, any_value(business_unit) as business_unit,
       count(*) as payment_count, sum(amount) as total_amount,
       array_agg(concat('transactions/', transaction_id) order by transaction_id) as evidence_refs
from payments
where amount < 10000
group by vendor_id, paid_date
